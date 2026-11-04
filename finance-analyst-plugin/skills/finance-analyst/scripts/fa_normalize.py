"""Convert a raw export into a canonical input CSV using a mapping file.

    python3 fa_normalize.py --mapping mapping.json --out DATA_DIR/<canonical file>.csv

Mapping keys (see templates/mappings/*.json for examples):
  kind                      canonical template (trial_balance, bank_transactions, ar_open_items, ...)
  source_file               raw CSV path (relative to the mapping file)
  columns                   {canonical_column: source_column}
  constants                 {canonical_column: value}         e.g. period labels, bank_account_ref
  dayfirst                  true (default) for Indian DD/MM/YYYY dates
  skip_first_cell_patterns  regexes; rows whose first non-empty cell matches are skipped (titles, totals)
  amount_scale              multiply amounts (e.g. "100000" when the export is in lakhs)
  minor_units               true when amounts are in paise/cents (divide by 100)
  signed_to_split           {"source": col, "debit": canon, "credit": canon, "positive_is": "debit"|"credit"}
  drcr_to_split             {"source": col, "debit": canon, "credit": canon}   for '1,234.00 Dr' style cells
  blank_pair_zero           [["debit", "credit"], ...]  a blank side becomes 0 only when the other side has a value
  class_map_file            CSV from fa_classify.py (account_id/account_name -> proposed_class, confirmed)
  allow_unconfirmed_classes false (default): unconfirmed mappings are left blank and reported
  mode                      "two_snapshots" (trial_balance only): opening_file + closing_file trial balances
                            "as at" two dates; movement = closing - opening. Requires "absent_means_zero": true
                            to treat ledgers missing from one snapshot as zero (trial balances omit zero balances).

Nothing is guessed: unparseable cells are left blank and listed in <out>.log.json.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fa_common import (TEMPLATES, ZERO, is_ambiguous_dayfirst, json_default, parse_amount, parse_date,  # noqa: E402
                       read_csv, write_csv)


def _fmt(v, typ):
    if v is None:
        return ""
    if typ == "date":
        return v.isoformat()
    if typ == "dec":
        return format(v, "f")
    return v


class Normalizer:
    def __init__(self, mapping, base_dir):
        self.m = mapping
        self.base = base_dir
        self.kind = mapping["kind"]
        if self.kind not in TEMPLATES:
            raise SystemExit(f"unknown kind {self.kind}; choose one of {sorted(TEMPLATES)}")
        self.tpl = TEMPLATES[self.kind]
        self.log = {"kind": self.kind, "rows_in": 0, "rows_out": 0, "skipped_rows": [], "errors": [],
                    "conversions": {}, "warnings": []}
        self.scale = Decimal(str(mapping.get("amount_scale", "1")))
        if mapping.get("minor_units"):
            self.scale = self.scale / Decimal(100)
        self.dayfirst = mapping.get("dayfirst", True)
        self.classes = self._load_classes()
        self.date_evidence = {}

    def note(self, key):
        self.log["conversions"][key] = self.log["conversions"].get(key, 0) + 1

    def _load_classes(self):
        path = self.m.get("class_map_file")
        if not path:
            return None
        rows, _ = read_csv(os.path.join(self.base, path))
        out = {}
        for r in rows:
            ok = (r.get("confirmed") or "").lower() in ("yes", "y", "true") or self.m.get("allow_unconfirmed_classes")
            cls = r.get("proposed_class") if ok else None
            for key in (r.get("account_id"), r.get("account_name")):
                if key:
                    out[key.strip().lower()] = cls
        return out

    def amount(self, raw, where):
        try:
            v = parse_amount(raw)
        except ValueError as exc:
            self.log["errors"].append({"where": where, "value": raw, "error": str(exc)})
            return None
        if v is None:
            return None
        if self.scale != 1:
            self.note("amount_scaled")
        return v * self.scale

    def skip(self, raw_row, headers):
        cells = [raw_row.get(h) for h in headers if raw_row.get(h)]
        if not cells:
            return "empty row"
        for pat in self.m.get("skip_first_cell_patterns", []):
            if re.search(pat, cells[0], re.IGNORECASE):
                return f"first cell matches /{pat}/"
        return None

    def convert(self, raw_row, line):
        out = {}
        cols = self.m.get("columns", {})
        for col, typ in self.tpl["columns"].items():
            if col in self.m.get("constants", {}):
                val = self.m["constants"][col]
            elif col in cols and cols[col]:
                val = raw_row.get(cols[col])
                val = None if val in ("", None) else val
            else:
                val = None
            if val is None:
                out[col] = None
                continue
            if typ == "date":
                try:
                    out[col] = parse_date(val, self.dayfirst)
                    ev = self.date_evidence.setdefault(col, {"day_first_proof": 0, "month_first_proof": 0,
                                                             "ambiguous": 0})
                    mm = re.fullmatch(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})", str(val).strip())
                    if mm:
                        if int(mm.group(1)) > 12:
                            ev["day_first_proof"] += 1
                        elif int(mm.group(2)) > 12:
                            ev["month_first_proof"] += 1
                        elif is_ambiguous_dayfirst(val):
                            ev["ambiguous"] += 1
                except ValueError as exc:
                    self.log["errors"].append({"where": f"line {line} {col}", "value": val, "error": str(exc)})
                    out[col] = None
            elif typ == "dec":
                out[col] = self.amount(val, f"line {line} {col}")
            else:
                out[col] = str(val).strip()
        for spec_key, sign_mode in (("signed_to_split", "signed"), ("drcr_to_split", "drcr")):
            sp = self.m.get(spec_key)
            if not sp:
                continue
            v = self.amount(raw_row.get(sp["source"]), f"line {line} {sp['source']}")
            if v is None:
                continue
            if sign_mode == "signed" and sp.get("positive_is", "debit") == "credit":
                v = -v
            out[sp["debit"]] = v if v > 0 else ZERO
            out[sp["credit"]] = -v if v < 0 else ZERO
            self.note(spec_key)
        for a, b in self.m.get("blank_pair_zero", []):
            if out.get(a) is None and out.get(b) is not None:
                out[a] = ZERO
                self.note(f"{a}_blank_set_zero_other_side_present")
            elif out.get(b) is None and out.get(a) is not None:
                out[b] = ZERO
                self.note(f"{b}_blank_set_zero_other_side_present")
        if "account_class" in self.tpl["columns"] and not out.get("account_class") and self.classes is not None:
            key = (out.get("account_id") or out.get("account_name") or "").strip().lower()
            name_key = (out.get("account_name") or "").strip().lower()
            cls = self.classes.get(key) or self.classes.get(name_key)
            out["account_class"] = cls
            if cls is None:
                self.log["warnings"].append(f"line {line}: no confirmed account_class for '{out.get('account_name')}'")
        return out

    def standard(self):
        rows, headers = read_csv(os.path.join(self.base, self.m["source_file"]))
        out = []
        for line, r in enumerate(rows, start=2):
            self.log["rows_in"] += 1
            why = self.skip(r, headers)
            if why:
                self.log["skipped_rows"].append({"line": line, "reason": why})
                continue
            out.append(self.convert(r, line))
        return out

    def two_snapshots(self):
        if not self.m.get("absent_means_zero"):
            raise SystemExit("two_snapshots mode needs \"absent_means_zero\": true after confirming that the "
                             "trial balance exports omit zero-balance ledgers")
        snaps = {}
        names, classes = {}, {}
        for which in ("opening", "closing"):
            rows, headers = read_csv(os.path.join(self.base, self.m[f"{which}_file"]))
            bal = {}
            for line, r in enumerate(rows, start=2):
                self.log["rows_in"] += 1
                why = self.skip(r, headers)
                if why:
                    self.log["skipped_rows"].append({"file": which, "line": line, "reason": why})
                    continue
                c = self.convert(r, f"{which}:{line}")
                key = c.get("account_id") or c.get("account_name")
                if not key:
                    continue
                names[key] = c.get("account_name") or key
                if c.get("account_class"):
                    classes[key] = c["account_class"]
                cols = self.m["snapshot_columns"]
                if "balance" in cols:
                    v = self.amount(r.get(cols["balance"]), f"{which}:{line} {cols['balance']}")
                else:
                    d = self.amount(r.get(cols["debit"]), f"{which}:{line} {cols['debit']}") or ZERO
                    cr = self.amount(r.get(cols["credit"]), f"{which}:{line} {cols['credit']}") or ZERO
                    v = d - cr
                if v is None:
                    continue
                bal[key] = bal.get(key, ZERO) + v
            snaps[which] = bal
        out = []
        consts = self.m.get("constants", {})
        for key in sorted(set(snaps["opening"]) | set(snaps["closing"])):
            o = snaps["opening"].get(key)
            c = snaps["closing"].get(key)
            if o is None or c is None:
                self.note("ledger_absent_from_one_snapshot_treated_as_zero")
            o, c = o or ZERO, c or ZERO
            mv = c - o
            row = {"account_id": key, "account_name": names[key], "account_class": classes.get(key),
                   "opening_debit": max(o, ZERO), "opening_credit": max(-o, ZERO),
                   "period_debit": max(mv, ZERO), "period_credit": max(-mv, ZERO),
                   "closing_debit": max(c, ZERO), "closing_credit": max(-c, ZERO)}
            for k in ("period_label", "period_start", "period_end"):
                row[k] = parse_date(consts[k]) if k != "period_label" else consts[k]
            if row["account_class"] is None:
                self.log["warnings"].append(f"no confirmed account_class for '{names[key]}'")
            out.append(row)
        self.log["warnings"].append("Period movements are net (closing - opening) per ledger.")
        return out

    def run(self, out_path):
        rows = self.two_snapshots() if self.m.get("mode") == "two_snapshots" else self.standard()
        cols = list(self.tpl["columns"])
        missing_required = [c for c in self.tpl["required"] if all(r.get(c) is None for r in rows)]
        if missing_required:
            self.log["warnings"].append(f"required column(s) entirely blank: {missing_required}")
        write_csv(out_path, [{c: _fmt(r.get(c), self.tpl['columns'][c]) for c in cols} for r in rows], cols)
        self.log["rows_out"] = len(rows)
        for col, ev in self.date_evidence.items():
            assumed = "day_first_proof" if self.dayfirst else "month_first_proof"
            other = "month_first_proof" if self.dayfirst else "day_first_proof"
            if ev[other]:
                self.log["errors"].append({"where": col, "error": f"{ev[other]} value(s) contradict the configured "
                                                                  f"date orientation (dayfirst={self.dayfirst})"})
            elif ev["ambiguous"] and not ev[assumed]:
                self.log["warnings"].append(f"{col}: all {ev['ambiguous']} slash-dates are ambiguous between "
                                            f"day/month orders; read with dayfirst={self.dayfirst} - confirm")
        self.log["date_orientation_evidence"] = self.date_evidence
        with open(out_path + ".log.json", "w", encoding="utf-8") as fh:
            json.dump(self.log, fh, indent=2, default=json_default)
        return self.log


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mapping", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    with open(a.mapping, encoding="utf-8") as fh:
        mapping = json.load(fh)
    log = Normalizer(mapping, os.path.dirname(os.path.abspath(a.mapping))).run(a.out)
    print(f"{log['kind']}: {log['rows_in']} rows in, {log['rows_out']} out, {len(log['skipped_rows'])} skipped, "
          f"{len(log['errors'])} error(s), {len(log['warnings'])} warning(s) -> {a.out}")
    for w in log["warnings"][:10]:
        print("  warning:", w)
    for e in log["errors"][:10]:
        print("  error:", e)
    return 0 if not log["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
