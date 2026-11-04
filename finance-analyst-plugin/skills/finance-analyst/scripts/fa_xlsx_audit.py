"""Independent Excel formula auditor (spec verification.checks.ver_excel_formulas). Standard library only.

    python3 fa_xlsx_audit.py --workbook dashboard.xlsx [--register calc_register.json] [--libreoffice] [--out a.json]

It parses the .xlsx itself (no Excel, no openpyxl), evaluates every formula with its own evaluator and reports:
  - formulas whose evaluated value differs from the cached value stored in the file (when present);
  - for plugin dashboards, formulas whose value differs from the calculation-register value they present
    (sheet "_map": sheet, cell, calc_id);
  - #REF!/#DIV/0!/#N/A results, unsupported functions, circular references;
  - hard-coded numeric constants inside formulas (other than 0, 1 and 100);
  - formulas inconsistent with their neighbours in the same row or column (e.g. one month's column pointing
    at a different row) — compared in relative (R1C1-like) form.
With --libreoffice, the workbook is also recalculated by LibreOffice (a second, independent engine) and both
results are compared. Works on customer workbooks too (no _map sheet needed).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
      "rel": "http://schemas.openxmlformats.org/package/2006/relationships"}
SUPPORTED = {"SUM", "AVERAGE", "MIN", "MAX", "ABS", "ROUND", "IF", "IFERROR", "INDEX", "MATCH", "SUMIF", "COUNT",
             "COUNTA", "SUMPRODUCT", "AND", "OR", "NOT"}
TOL = 1e-6


class XlErr(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def col_to_num(col):
    n = 0
    for ch in col:
        n = n * 26 + ord(ch) - 64
    return n


def num_to_col(n):
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def split_ref(ref):
    m = re.fullmatch(r"\$?([A-Z]{1,3})\$?(\d+)", ref)
    return col_to_num(m.group(1)), int(m.group(2))


# ------------------------------------------------------------------ workbook reader
def read_workbook(path):
    z = zipfile.ZipFile(path)
    names = set(z.namelist())
    shared = []
    if "xl/sharedStrings.xml" in names:
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS):
            shared.append("".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t")))
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    target = {r.get("Id"): r.get("Target") for r in rels.findall("rel:Relationship", NS)}
    sheets = {}
    for s in wb.find("m:sheets", NS).findall("m:sheet", NS):
        rid = s.get(f"{{{NS['r']}}}id")
        t = target[rid].lstrip("/")
        t = t if t.startswith("xl/") else "xl/" + t
        cells = {}
        root = ET.fromstring(z.read(t))
        for c in root.iter(f"{{{NS['m']}}}c"):
            ref, typ = c.get("r"), c.get("t")
            f = c.find("m:f", NS)
            v = c.find("m:v", NS)
            is_ = c.find("m:is", NS)
            val = None
            if v is not None and v.text is not None:
                if typ == "s":
                    val = shared[int(v.text)]
                elif typ in ("str", "inlineStr"):
                    val = v.text
                elif typ == "b":
                    val = v.text == "1"
                elif typ == "e":
                    val = XlErr(v.text)
                else:
                    val = float(v.text)
            elif is_ is not None:
                val = "".join(t.text or "" for t in is_.iter(f"{{{NS['m']}}}t"))
            cells[ref] = {"formula": ("=" + f.text) if f is not None and f.text else None, "cached": val}
        sheets[s.get("name")] = cells
    return sheets


# ------------------------------------------------------------------ formula evaluator
TOKEN = re.compile(r"""\s*(?:
    (?P<str>"(?:[^"]|"")*")|
    (?P<err>\#(?:REF!|DIV/0!|N/A|VALUE!|NAME\?|NUM!|NULL!))|
    (?P<ref>(?:(?:'[^']+'|[A-Za-z_][\w.]*)!)?\$?[A-Z]{1,3}\$?\d+(?::\$?[A-Z]{1,3}\$?\d+)?|
           (?:(?:'[^']+'|[A-Za-z_][\w.]*)!)?\$?[A-Z]{1,3}:\$?[A-Z]{1,3})|
    (?P<num>\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)|
    (?P<func>[A-Z][A-Z0-9.]*(?=\())|
    (?P<bool>TRUE|FALSE)|
    (?P<op><>|<=|>=|[-+*/^&=<>%(),:])
)""", re.VERBOSE)


def tokenize(text):
    pos, out = 0, []
    while pos < len(text):
        m = TOKEN.match(text, pos)
        if not m or m.end() == pos:
            if text[pos:].strip() == "":
                break
            raise XlErr("#NAME?")
        pos = m.end()
        kind = m.lastgroup
        out.append((kind, m.group(kind)))
    return out


class Evaluator:
    def __init__(self, sheets):
        self.sheets = sheets
        self.cache, self.stack = {}, set()
        self.unsupported, self.hardcoded = set(), []

    def cell_value(self, sheet, ref):
        key = (sheet, ref)
        if key in self.cache:
            return self.cache[key]
        cell = self.sheets.get(sheet, {}).get(ref)
        if cell is None:
            return None
        if cell["formula"] is None:
            return cell["cached"]
        if key in self.stack:
            raise XlErr("#CIRCULAR")
        self.stack.add(key)
        try:
            val = self.eval_formula(cell["formula"], sheet)
        except XlErr as exc:
            val = exc
        finally:
            self.stack.discard(key)
        self.cache[key] = val
        return val

    def eval_formula(self, formula, sheet):
        saved = (getattr(self, "toks", None), getattr(self, "i", 0), getattr(self, "sheet", None))
        self.toks, self.i, self.sheet = tokenize(formula[1:]), 0, sheet
        try:  # re-entrant: referenced formulas are evaluated with their own parser state
            val = self.expr()
            if self.i != len(self.toks):
                raise XlErr("#VALUE!")
        finally:
            self.toks, self.i, self.sheet = saved
        if isinstance(val, list):
            val = val[0][0] if val and val[0] else None
        return val

    # recursive descent: comparison > concat > additive > multiplicative > power > unary > primary
    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else (None, None)

    def take(self):
        t = self.toks[self.i]
        self.i += 1
        return t

    def expr(self):
        left = self.concat()
        while self.peek()[1] in ("=", "<>", "<", ">", "<=", ">="):
            op = self.take()[1]
            right = self.concat()
            a, b = self.scalar(left), self.scalar(right)
            left = {"=": a == b, "<>": a != b, "<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b}[op]
        return left

    def concat(self):
        left = self.additive()
        while self.peek()[1] == "&":
            self.take()
            left = f"{self.scalar(left)}{self.scalar(self.additive())}"
        return left

    def additive(self):
        left = self.mult()
        while self.peek()[1] in ("+", "-"):
            op = self.take()[1]
            right = self.mult()
            a, b = self.number(left), self.number(right)
            left = a + b if op == "+" else a - b
        return left

    def mult(self):
        left = self.power()
        while self.peek()[1] in ("*", "/"):
            op = self.take()[1]
            right = self.power()
            a, b = self.number(left), self.number(right)
            if op == "/" and b == 0:
                raise XlErr("#DIV/0!")
            left = a * b if op == "*" else a / b
        return left

    def power(self):
        left = self.unary()
        while self.peek()[1] == "^":
            self.take()
            left = self.number(left) ** self.number(self.unary())
        return left

    def unary(self):
        if self.peek()[1] == "-":
            self.take()
            return -self.number(self.unary())
        if self.peek()[1] == "+":
            self.take()
            return self.unary()
        v = self.primary()
        if self.peek()[1] == "%":
            self.take()
            v = self.number(v) / 100
        return v

    def primary(self):
        kind, text = self.take()
        if kind == "num":
            v = float(text)
            if v not in (0.0, 1.0, 100.0):
                self.hardcoded.append(text)
            return v
        if kind == "str":
            return text[1:-1].replace('""', '"')
        if kind == "bool":
            return text == "TRUE"
        if kind == "err":
            raise XlErr(text)
        if kind == "ref":
            return self.ref(text)
        if kind == "func":
            return self.func(text)
        if text == "(":
            v = self.expr()
            self.take()
            return v
        raise XlErr("#VALUE!")

    def ref(self, text):
        sheet = self.sheet
        if "!" in text:
            sheet, text = text.rsplit("!", 1)
            sheet = sheet.strip("'")
        if sheet not in self.sheets:
            raise XlErr("#REF!")
        text = text.replace("$", "")
        if ":" in text:
            a, b = text.split(":")
            if a.isalpha():  # whole columns
                c1, c2 = col_to_num(a), col_to_num(b)
                rows = [int(re.sub(r"[A-Z]", "", r)) for r in self.sheets[sheet]] or [1]
                r1, r2 = 1, max(rows)
            else:
                (c1, r1), (c2, r2) = split_ref(a), split_ref(b)
            return [[self.cell_value(sheet, f"{num_to_col(c)}{r}") for c in range(c1, c2 + 1)]
                    for r in range(r1, r2 + 1)]
        v = self.cell_value(sheet, text)
        if isinstance(v, XlErr):
            raise v
        return v

    def args(self):
        out = []
        self.take()  # (
        if self.peek()[1] == ")":
            self.take()
            return out
        while True:
            start = self.i
            try:
                out.append(("ok", self.expr()))
            except XlErr as exc:
                out.append(("err", exc))
                depth = 0
                while self.i < len(self.toks):  # skip to the end of this argument
                    t = self.toks[self.i][1]
                    if t == "(":
                        depth += 1
                    elif t == ")":
                        if depth == 0:
                            break
                        depth -= 1
                    elif t == "," and depth == 0:
                        break
                    self.i += 1
            if self.i == start:
                raise XlErr("#VALUE!")
            t = self.take()[1]
            if t == ")":
                return out
            if t != ",":
                raise XlErr("#VALUE!")

    @staticmethod
    def flat(v):
        if isinstance(v, list):
            return [x for row in v for x in row]
        return [v]

    def number(self, v):
        if isinstance(v, list):
            v = v[0][0]
        if isinstance(v, XlErr):
            raise v
        if v is None or v == "":
            return 0.0
        if isinstance(v, bool):
            return 1.0 if v else 0.0
        if isinstance(v, (int, float)):
            return float(v)
        try:
            return float(v)
        except ValueError:
            raise XlErr("#VALUE!")

    def scalar(self, v):
        if isinstance(v, list):
            v = v[0][0]
        if isinstance(v, XlErr):
            raise v
        return v

    def func(self, name):
        if name not in SUPPORTED:
            self.unsupported.add(name)
            raise XlErr("#UNSUPPORTED")
        a = self.args()
        if name == "IFERROR":
            return a[0][1] if a[0][0] == "ok" else a[1][1]
        for kind, v in a:
            if kind == "err":
                raise v
        vals = [v for _, v in a]
        nums = [x for v in vals for x in self.flat(v) if isinstance(x, (int, float)) and not isinstance(x, bool)]
        for v in vals:
            for x in self.flat(v):
                if isinstance(x, XlErr):
                    raise x
        if name == "SUM":
            return float(math.fsum(nums))
        if name == "AVERAGE":
            if not nums:
                raise XlErr("#DIV/0!")
            return math.fsum(nums) / len(nums)
        if name == "MIN":
            return min(nums) if nums else 0.0
        if name == "MAX":
            return max(nums) if nums else 0.0
        if name == "ABS":
            return abs(self.number(vals[0]))
        if name == "ROUND":
            x, d = self.number(vals[0]), int(self.number(vals[1]))
            q = 10 ** d
            return math.floor(abs(x) * q + 0.5) / q * (1 if x >= 0 else -1)
        if name == "IF":
            cond = self.scalar(vals[0])
            return vals[1] if cond else (vals[2] if len(vals) > 2 else False)
        if name == "COUNT":
            return float(len(nums))
        if name == "COUNTA":
            return float(sum(1 for v in vals for x in self.flat(v) if x not in (None, "")))
        if name == "AND":
            return all(self.scalar(v) for v in vals)
        if name == "OR":
            return any(self.scalar(v) for v in vals)
        if name == "NOT":
            return not self.scalar(vals[0])
        if name == "INDEX":
            rng = vals[0] if isinstance(vals[0], list) else [[vals[0]]]
            r = int(self.number(vals[1])) if len(vals) > 1 else 1
            c = int(self.number(vals[2])) if len(vals) > 2 else 1
            if r < 1 or c < 1 or r > len(rng) or c > len(rng[0]):
                raise XlErr("#REF!")
            return rng[r - 1][c - 1]
        if name == "MATCH":
            target, rng = self.scalar(vals[0]), self.flat(vals[1])
            mode = int(self.number(vals[2])) if len(vals) > 2 else 1
            if mode != 0:
                self.unsupported.add("MATCH(approximate)")
                raise XlErr("#UNSUPPORTED")
            for i, x in enumerate(rng, 1):
                if x == target or (isinstance(x, str) and isinstance(target, str) and x.lower() == target.lower()):
                    return float(i)
            raise XlErr("#N/A")
        if name == "SUMIF":
            rng, crit = self.flat(vals[0]), self.scalar(vals[1])
            srng = self.flat(vals[2]) if len(vals) > 2 else rng
            return float(math.fsum(s for x, s in zip(rng, srng) if x == crit and isinstance(s, (int, float))))
        if name == "SUMPRODUCT":
            arrs = [self.flat(v) for v in vals]
            return float(math.fsum(math.prod(self.number(x) for x in t) for t in zip(*arrs)))
        raise XlErr("#UNSUPPORTED")


def relative_form(formula, ref):
    """R1C1-like form so neighbouring formulas can be compared."""
    c0, r0 = split_ref(ref)

    def rel(m):
        sheet, col, row = m.group(1) or "", m.group(3), m.group(5)
        cabs, rabs = m.group(2), m.group(4)
        c = f"C{col_to_num(col)}" if cabs else f"C[{col_to_num(col) - c0}]"
        r = f"R{row}" if rabs else f"R[{int(row) - r0}]"
        return f"{sheet}{r}{c}"
    return re.sub(r"((?:'[^']+'|[A-Za-z_][\w.]*)!)?(\$?)([A-Z]{1,3})(\$?)(\d+)", rel, formula)


def formula_shape(formula):
    """Structure without references/numbers: '=B2-C3' -> '=R-R'; '=SUM(B4:D4)' -> '=SUM(R)'."""
    f = re.sub(r"((?:'[^']+'|[A-Za-z_][\w.]*)!)?\$?[A-Z]{1,3}\$?\d+(?::\$?[A-Z]{1,3}\$?\d+)?", "R", formula)
    return re.sub(r"\d+(?:\.\d+)?", "N", f)


def inconsistent_formulas(sheets):
    """Cells whose relative formula differs from BOTH left and right neighbours that agree with each other —
    i.e. one period column computed differently from the periods around it (the classic wrong-month error)."""
    out = []
    for sname, cells in sheets.items():
        forms = {ref: relative_form(c["formula"], ref) for ref, c in cells.items() if c["formula"]}
        for ref, f in forms.items():
            c, r = split_ref(ref)
            for d1, d2 in ((-1, 1), (1, 2), (-2, -1)):  # both sides, or two on one side (first/last column)
                a = f"{num_to_col(c + d1)}{r}" if c + d1 > 0 else None
                b = f"{num_to_col(c + d2)}{r}" if c + d2 > 0 else None
                if a in forms and b in forms and forms[a] == forms[b] and forms[a] != f and \
                        formula_shape(cells[a]["formula"]) == formula_shape(cells[ref]["formula"]):
                    out.append({"sheet": sname, "cell": ref, "formula": cells[ref]["formula"],
                                "neighbours": [cells[a]["formula"], cells[b]["formula"]]})
                    break
    return out


def libreoffice_values(path):
    exe = shutil.which("soffice") or shutil.which("libreoffice")
    if not exe:
        return None, "LibreOffice not available"
    tmp = tempfile.mkdtemp()
    try:
        subprocess.run([exe, "--headless", "--calc", "--convert-to", "xlsx", "--outdir", tmp, path],
                       capture_output=True, timeout=120, check=False)
        out = os.path.join(tmp, os.path.basename(path))
        if not os.path.isfile(out):
            return None, "LibreOffice conversion failed"
        return read_workbook(out), "ok"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def close(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return abs(a - b) <= TOL * max(1.0, abs(a), abs(b))
    return a == b


def audit(path, register=None, use_libreoffice=False):
    sheets = read_workbook(path)
    ev = Evaluator(sheets)
    results, problems = [], []
    for sname, cells in sheets.items():
        for ref, c in sorted(cells.items()):
            if not c["formula"]:
                continue
            ev.hardcoded = []
            v = ev.cell_value(sname, ref)
            entry = {"sheet": sname, "cell": ref, "formula": c["formula"],
                     "value": v.code if isinstance(v, XlErr) else v}
            if isinstance(v, XlErr):
                problems.append(f"{sname}!{ref}: {v.code} from {c['formula']}")
            if c["cached"] is not None and not isinstance(v, XlErr) and not close(v, c["cached"]):
                problems.append(f"{sname}!{ref}: evaluates to {v} but the file shows {c['cached']}")
            if "#REF!" in c["formula"]:
                problems.append(f"{sname}!{ref}: broken reference in {c['formula']}")
            if ev.hardcoded:
                entry["hardcoded_constants"] = list(ev.hardcoded)
            results.append(entry)
    mapped = 0
    if register is not None and "_map" in sheets:
        by_id = {r["calc_id"]: r for r in register}
        m = sheets["_map"]
        rows = sorted({int(re.sub(r"[A-Z]", "", ref)) for ref in m})
        for r in rows[1:]:
            sh, cell, cid = (m.get(f"{c}{r}", {}).get("cached") for c in "ABC")
            if not sh:
                continue
            rec = by_id.get(cid)
            got = ev.cell_value(sh, cell)
            mapped += 1
            if cid == "ZERO":
                if isinstance(got, XlErr) or not close(float(got or 0), 0.0):
                    problems.append(f"{sh}!{cell}: check cell should be 0 but is {getattr(got, 'code', got)}")
                continue
            if rec is None or rec["value"] is None:
                problems.append(f"{sh}!{cell}: mapped to {cid}, which has no computed value")
            elif isinstance(got, XlErr) or not close(float(got), float(rec["value"])):
                problems.append(f"{sh}!{cell}: shows {getattr(got, 'code', got)} but {cid} is {rec['value']}")
    hard = [e for e in results if e.get("hardcoded_constants")]
    incons = inconsistent_formulas(sheets)
    problems += [f"{x['sheet']}!{x['cell']}: formula {x['formula']} differs from neighbours {x['neighbours']}"
                 for x in incons]
    lo = {"status": "not requested"}
    if use_libreoffice:
        lo_sheets, msg = libreoffice_values(path)
        lo = {"status": msg, "compared": 0, "mismatches": []}
        if lo_sheets:
            for e in results:
                other = lo_sheets.get(e["sheet"], {}).get(e["cell"], {}).get("cached")
                if isinstance(other, XlErr):
                    other = other.code
                lo["compared"] += 1
                if not close(e["value"], other):
                    lo["mismatches"].append(f"{e['sheet']}!{e['cell']}: ours {e['value']} vs LibreOffice {other}")
            problems += [f"LibreOffice disagrees — {x}" for x in lo["mismatches"]]
    return {"workbook": os.path.basename(path), "formulas": len(results), "mapped_checks": mapped,
            "unsupported_functions": sorted(ev.unsupported), "hardcoded_formula_constants": len(hard),
            "inconsistent_formulas": incons, "libreoffice": lo, "problems": problems,
            "status": "passed" if not problems and not ev.unsupported else "failed", "cells": results}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workbook", required=True)
    ap.add_argument("--register")
    ap.add_argument("--libreoffice", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    reg = None
    if a.register:
        with open(a.register, encoding="utf-8") as fh:
            reg = json.load(fh)
    res = audit(a.workbook, reg, a.libreoffice)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=2, default=str)
    print(f"{res['workbook']}: {res['formulas']} formulas, {res['mapped_checks']} register checks, "
          f"{len(res['problems'])} problem(s), unsupported {res['unsupported_functions'] or 'none'}, "
          f"LibreOffice: {res['libreoffice']['status']} -> {res['status']}")
    for p in res["problems"][:20]:
        print("  -", p)
    return 0 if res["status"] == "passed" else 3


if __name__ == "__main__":
    sys.exit(main())
