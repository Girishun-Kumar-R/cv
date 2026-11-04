"""Lightweight discovery of customer-provided files (§5) - metadata only, no raw rows printed.

    python3 fa_discover.py --dir FOLDER [--recursive] [--out discovery.json]

For each CSV (and XLSX when openpyxl is installed): size, SHA-256, sheet/columns,
row count, best-matching canonical template, date coverage of date-like columns and
totals of amount-like columns. Files are never modified.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fa_common import TEMPLATES, json_default, parse_amount, parse_date, read_csv, sha256_file  # noqa: E402

DATE_HINTS = ("date", "dt", "period", "as on", "as_of", "dated")
AMOUNT_HINTS = ("amount", "debit", "credit", "balance", "value", "total", "dr", "cr", "net", "gross", "fee",
                "tax", "outstanding")


def match_template(headers):
    hs = {h.strip().lower() for h in headers}
    best, score = None, 0.0
    for kind, tpl in TEMPLATES.items():
        req = tpl["required"]
        s = sum(1 for c in req if c in hs) / len(req)
        if s > score:
            best, score = kind, s
    return {"template": best if score >= 0.6 else None, "required_columns_present": round(score, 2),
            "is_canonical": score == 1.0,
            "next_step": "use as-is" if score == 1.0 else "write a mapping and run fa_normalize.py"}


def profile_table(headers, rows):
    out = {"columns": headers, "row_count": len(rows), "date_columns": {}, "amount_columns": {}}
    for h in headers:
        low = h.lower()
        vals = [r.get(h) for r in rows if r.get(h) not in (None, "")]
        if any(k in low for k in DATE_HINTS):
            parsed, bad = [], 0
            for v in vals:
                try:
                    parsed.append(parse_date(v))
                except ValueError:
                    bad += 1
            if parsed:
                out["date_columns"][h] = {"earliest": min(parsed), "latest": max(parsed), "unparseable": bad}
        if any(k in low for k in AMOUNT_HINTS):
            total, bad, n = 0, 0, 0
            for v in vals:
                try:
                    a = parse_amount(v)
                    if a is not None:
                        total += a
                        n += 1
                except (ValueError, TypeError):
                    bad += 1
            if n:
                out["amount_columns"][h] = {"non_blank": n, "sum": total, "unparseable": bad}
    out["template_match"] = match_template(headers)
    return out


def discover(folder, recursive=False):
    results = []
    walker = os.walk(folder) if recursive else [(folder, [], os.listdir(folder))]
    for root, _, files in walker:
        for name in sorted(files):
            path = os.path.join(root, name)
            if not os.path.isfile(path) or name.startswith("."):
                continue
            ext = name.lower().rsplit(".", 1)[-1] if "." in name else ""
            item = {"file": os.path.relpath(path, folder), "bytes": os.path.getsize(path), "sha256": sha256_file(path),
                    "type": ext}
            if ext in ("csv", "tsv", "txt"):
                try:
                    rows, headers = read_csv(path)
                    item["tables"] = [profile_table(headers, rows)]
                except (UnicodeDecodeError, OSError) as exc:
                    item["error"] = f"could not read as UTF-8 CSV: {exc}"
            elif ext in ("xlsx", "xlsm"):
                try:
                    import openpyxl  # type: ignore
                    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
                    item["tables"] = []
                    for ws in wb.worksheets:
                        it = ws.iter_rows(values_only=True)
                        header = next(it, None) or []
                        headers = [str(h).strip() if h is not None else "" for h in header]
                        rows = [{headers[i]: ("" if v is None else str(v)) for i, v in enumerate(r)
                                 if i < len(headers)} for r in it]
                        t = profile_table(headers, rows)
                        t["sheet"] = ws.title
                        item["tables"].append(t)
                except ImportError:
                    item["error"] = "openpyxl not installed: export this workbook to CSV or install openpyxl"
            elif ext == "pdf":
                item["note"] = "PDF: extract tables with the host's PDF tools, then reconcile to printed totals"
            else:
                item["note"] = "not a supported tabular format"
            results.append(item)
    return results


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", required=True)
    ap.add_argument("--recursive", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    res = discover(a.dir, a.recursive)
    text = json.dumps(res, indent=2, ensure_ascii=False, default=json_default)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    for item in res:
        for t in item.get("tables", []):
            m = t["template_match"]
            print(f"{item['file']}{'#' + t['sheet'] if t.get('sheet') else ''}: {t['row_count']} rows, "
                  f"{len(t['columns'])} cols, template={m['template']} ({m['required_columns_present']:.0%} of "
                  f"required columns){' canonical' if m['is_canonical'] else ''}")
        if item.get("error") or item.get("note"):
            print(f"{item['file']}: {item.get('error') or item.get('note')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
