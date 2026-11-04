"""Excel dashboard with live formulas, built from the calculation register (needs openpyxl).

    python3 fa_xlsx.py --run-dir RUN [--out RUN/dashboard.xlsx]

Every figure is either a lookup of a register value by calc_id (sheet "Data") or a formula built from other
cells (subtotals, roll-ups, variances). Sheet "_map" lists each presented cell with the calc_id it must equal
(or ZERO for check cells that must be 0) so fa_xlsx_audit.py can validate every formula independently.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

INDIAN = '[>=10000000]##\\,##\\,##\\,##0.00;[>=100000]##\\,##\\,##0.00;##,##0.00'
PCT = "0.0%"


def build(run_dir, out_path=None):
    try:
        import openpyxl
        from openpyxl.styles import Alignment, Font, PatternFill
    except ImportError:
        return None, "openpyxl not installed — Excel dashboard skipped"
    with open(os.path.join(run_dir, "calc_register.json"), encoding="utf-8") as fh:
        reg = json.load(fh)
    with open(os.path.join(run_dir, "run_config.json"), encoding="utf-8") as fh:
        cfg = json.load(fh)
    cur = cfg["current_period"]["label"]
    cmpl = (cfg.get("comparison_period") or {}).get("label")
    wb = openpyxl.Workbook()
    data = wb.active
    data.title = "Data"
    data.append(["calc_id", "metric_id", "dimension", "period", "value", "unit", "readiness", "formula", "source"])
    for r in reg:
        dim = ", ".join(f"{k}={v}" for k, v in (r["dimension"] or {}).items())
        src = "; ".join(i["file"] for i in r["inputs"])
        data.append([r["calc_id"], r["metric_id"], dim, (r["period"] or {}).get("label"),
                     float(r["value"]) if r["value"] is not None else None, r["unit"], r["readiness"],
                     r["formula_text"], src])
    n = len(reg) + 1
    mp = wb.create_sheet("_map")
    mp.append(["sheet", "cell", "calc_id"])
    bold = Font(bold=True)
    head_fill = PatternFill("solid", fgColor="DCE6F1")

    def find(metric, period=cur, **dims):
        for r in reg:
            if r["metric_id"] == metric and (r["period"] or {}).get("label") == period and (r["dimension"] or {}) == dims:
                return r
        return None

    def lookup(rec):
        return f'=INDEX(Data!$E$2:$E${n},MATCH("{rec["calc_id"]}",Data!$A$2:$A${n},0))'

    def put(ws, cell, rec_or_formula, fmt=None, calc_id=None):
        ws[cell] = rec_or_formula if isinstance(rec_or_formula, str) else lookup(rec_or_formula)
        if fmt:
            ws[cell].number_format = fmt
        cid = calc_id or (rec_or_formula["calc_id"] if isinstance(rec_or_formula, dict) else None)
        if cid:
            mp.append([ws.title, cell, cid])

    def header(ws, row, values):
        for i, v in enumerate(values, 1):
            c = ws.cell(row=row, column=i, value=v)
            c.font, c.fill = bold, head_fill

    # Dashboard
    db = wb.create_sheet("Dashboard", 0)
    db["A1"] = f"{cfg.get('company_name')} — dashboard ({cur})"
    db["A1"].font = Font(bold=True, size=14)
    db["A2"] = "All values are lookups of the verified calculation register or formulas on them; amounts excl. GST."
    header(db, 4, ["Metric", "Value", "Definition"])
    row = 5
    kpis = [("Net revenue", "net_revenue", INDIAN), ("Gross profit", "gross_profit", INDIAN),
            ("EBITDA", "ebitda", INDIAN), ("Profit before tax", "profit_before_tax", INDIAN),
            ("Profit after tax (net profit)", "net_profit", INDIAN), ("Cash and bank (statement)", "cash_balance", INDIAN),
            ("Current ratio", "current_ratio", "0.00"), ("Days sales outstanding", "dso", "0")]
    cells = {}
    for label, metric, fmt in kpis:
        rec = find(metric)
        db.cell(row=row, column=1, value=label)
        if rec and rec["value"] is not None:
            put(db, f"B{row}", rec, fmt)
            db.cell(row=row, column=3, value=rec["formula_text"])
            cells[metric] = f"B{row}"
        else:
            db.cell(row=row, column=2, value="not stated")
            db.cell(row=row, column=3, value="; ".join((rec or {}).get("warnings", [])) or "not available")
        row += 1
    for label, num, den, metric in (("Gross margin", "gross_profit", "net_revenue", "gross_margin"),
                                    ("EBITDA margin", "ebitda", "net_revenue", "ebitda_margin")):
        rec = find(metric)
        if rec and num in cells and den in cells:
            db.cell(row=row, column=1, value=label)
            put(db, f"B{row}", f"={cells[num]}/{cells[den]}", PCT, rec["calc_id"])
            db.cell(row=row, column=3, value=rec["formula_text"])
            row += 1
    db.column_dimensions["A"].width, db.column_dimensions["B"].width, db.column_dimensions["C"].width = 34, 18, 70

    # P&L by period with formula subtotals and monthly roll-up
    pl = wb.create_sheet("P&L", 1)
    months = sorted({(r["period"]["start"], r["period"]["label"]) for r in reg if r["metric_id"] == "net_revenue"
                     and r["period"]["label"] not in (cur, cmpl) and r["value"] is not None})
    periods = [lbl for _, lbl in months] + [cur] + ([cmpl] if cmpl else [])
    header(pl, 1, ["Line"] + periods + (["Sum of months", "Difference (months - period)"] if months else []))
    lines = [("Net revenue", "net_revenue"), ("Cost of goods sold", "cogs"), ("Gross profit", None),
             ("Operating expenses (excl. D&A)", "operating_expenses"), ("EBITDA", None),
             ("Operating profit", "operating_profit"), ("Profit before tax", "profit_before_tax")]
    from openpyxl.utils import get_column_letter as col
    for i, (label, metric) in enumerate(lines, 2):
        pl.cell(row=i, column=1, value=label)
        for j, per in enumerate(periods, 2):
            ref = f"{col(j)}{i}"
            if metric:
                rec = find(metric, per)
                if rec and rec["value"] is not None:
                    put(pl, ref, rec, INDIAN)
            elif label == "Gross profit":
                rec = find("gross_profit", per)
                put(pl, ref, f"={col(j)}2-{col(j)}3", INDIAN, rec["calc_id"] if rec else None)
            elif label == "EBITDA":
                rec = find("ebitda", per)
                put(pl, ref, f"={col(j)}4-{col(j)}5", INDIAN, rec["calc_id"] if rec else None)
        if months:
            sc, dc = len(periods) + 2, len(periods) + 3
            first, last = col(2), col(1 + len(months))
            pl.cell(row=i, column=sc, value=f"=SUM({first}{i}:{last}{i})").number_format = INDIAN
            curcol = col(2 + len(months))
            pl.cell(row=i, column=dc, value=f"={col(sc)}{i}-{curcol}{i}").number_format = INDIAN
            mp.append(["P&L", f"{col(dc)}{i}", "ZERO"])
    pl.column_dimensions["A"].width = 32
    for j in range(2, len(periods) + 4):
        pl.column_dimensions[col(j)].width = 16

    # Budget
    bd = wb.create_sheet("Budget", 2)
    header(bd, 1, ["Line", "Actual", "Budget", "Variance", "Variance %", "Basis"])
    i = 2
    for r in reg:
        d = r["dimension"] or {}
        if r["metric_id"] != "budget_variance" or d.get("measure") != "variance" or d.get("account_class") == "all":
            continue
        cls = d["account_class"]
        a, b = find("budget_variance", account_class=cls, measure="actual"), find("budget_variance",
                                                                                   account_class=cls, measure="budget")
        p = find("budget_variance", account_class=cls, measure="variance_pct")
        prm = r.get("parameters") or {}
        bd.cell(row=i, column=1, value=cls.replace("_", " "))
        if a and a["value"] is not None and b and b["value"] is not None:
            put(bd, f"B{i}", a, INDIAN)
            put(bd, f"C{i}", b, INDIAN)
            put(bd, f"D{i}", f"=B{i}-C{i}", INDIAN, r["calc_id"])
            if p and p["value"] is not None:
                put(bd, f"E{i}", f"=D{i}/ABS(C{i})", PCT, p["calc_id"])
        else:
            bd.cell(row=i, column=2, value="blocked: " + "; ".join(r["warnings"]))
        bd.cell(row=i, column=6, value=f"actual = {prm.get('comparator_metric')}; budget {prm.get('amount_basis')}")
        i += 1
    bd.column_dimensions["A"].width, bd.column_dimensions["F"].width = 30, 52

    # Aging
    ag = wb.create_sheet("Aging", 3)
    header(ag, 1, ["Bucket", "Receivables", "Payables"])
    buckets = ["not_due", "1_30", "31_60", "61_90", "91_180", "181_365", "over_365"]
    for k, b in enumerate(buckets, 2):
        ag.cell(row=k, column=1, value=b.replace("_", "–"))
        for c, metric in (("B", "ar_aging"), ("C", "ap_aging")):
            rec = find(metric, bucket=b)
            if rec and rec["value"] is not None:
                put(ag, f"{c}{k}", rec, INDIAN)
    t = len(buckets) + 2
    ag.cell(row=t, column=1, value="Total")
    for c, metric in (("B", "ar_aging"), ("C", "ap_aging")):
        rec = find(metric, bucket="total")
        if rec and rec["value"] is not None:
            put(ag, f"{c}{t}", f"=SUM({c}2:{c}{t - 1})", INDIAN, rec["calc_id"])
    for ws in (db, pl, bd, ag):
        ws.freeze_panes = "A2" if ws is not db else "A5"
        for row_cells in ws.iter_rows():
            for c in row_cells:
                c.alignment = Alignment(vertical="top", wrap_text=c.column == 3 and ws is db)
    mp.sheet_state = "hidden"
    out = out_path or os.path.join(run_dir, "dashboard.xlsx")
    wb.save(out)
    return out, "ok"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    out, msg = build(a.run_dir, a.out)
    print(out or msg)
    return 0 if out else 4


if __name__ == "__main__":
    sys.exit(main())
