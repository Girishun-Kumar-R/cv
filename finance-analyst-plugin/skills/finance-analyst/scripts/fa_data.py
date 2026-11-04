"""Load canonical input CSVs (see references/input-formats.md) into typed rows."""
from __future__ import annotations

import os
from decimal import Decimal

from fa_common import (TEMPLATES, ZERO, normal_side, parse_amount, parse_date, read_csv, sha256_file)


def load_inputs(input_dir, dayfirst=True):
    """Return {'datasets': {kind: dataset}} for every canonical file present.

    Parse failures are recorded, never guessed: a failed cell becomes None and is
    listed in dataset['parse_errors'] for the data-quality checks.
    """
    datasets = {}
    for kind, tpl in TEMPLATES.items():
        path = os.path.join(input_dir, tpl["file"])
        if not os.path.isfile(path):
            continue
        rows, headers = read_csv(path)
        parsed, errors = [], []
        for line_no, raw in enumerate(rows, start=2):
            out = {"_line": line_no}
            for col, typ in tpl["columns"].items():
                cell = raw.get(col)
                if cell is not None and cell == "":
                    cell = None
                try:
                    if typ == "dec":
                        out[col] = parse_amount(cell)
                    elif typ == "date":
                        out[col] = parse_date(cell, dayfirst=dayfirst)
                    else:
                        out[col] = cell
                except (ValueError, KeyError) as exc:
                    errors.append({"line": line_no, "column": col, "value": cell, "error": str(exc),
                                   "type": typ})
                    out[col] = None
            parsed.append(out)
        datasets[kind] = {
            "dataset_id": f"DS-{kind.upper().replace('_', '-')}",
            "kind": kind,
            "file": tpl["file"],
            "path": os.path.abspath(path),
            "sha256": sha256_file(path),
            "headers": headers,
            "missing_columns": [c for c in tpl["required"] if c not in headers],
            "rows": parsed,
            "row_count": len(parsed),
            "parse_errors": errors,
        }
    return {"input_dir": os.path.abspath(input_dir), "datasets": datasets}


def date_coverage(ds):
    dates = []
    for col, typ in TEMPLATES[ds["kind"]]["columns"].items():
        if typ != "date":
            continue
        dates.extend(r[col] for r in ds["rows"] if r.get(col) is not None)
    if not dates:
        return None
    return {"earliest": min(dates).isoformat(), "latest": max(dates).isoformat()}


def source_manifest(data):
    out = []
    for kind in sorted(data["datasets"]):
        ds = data["datasets"][kind]
        currencies = sorted({r.get("currency") for r in ds["rows"] if r.get("currency")})
        out.append({
            "dataset_id": ds["dataset_id"],
            "dataset_type": kind,
            "file": ds["file"],
            "sha256": ds["sha256"],
            "record_count_retrieved": ds["row_count"],
            "date_coverage": date_coverage(ds),
            "currencies_in_file": currencies or ["not stated (assumed run currency)"],
            "parse_error_count": len(ds["parse_errors"]),
        })
    return out


def input_ref(data, kind):
    ds = data["datasets"].get(kind)
    if not ds:
        return None
    return {"dataset_id": ds["dataset_id"], "file": ds["file"], "sha256": ds["sha256"],
            "record_count": ds["row_count"]}


# ----------------------------------------------------------------------------
# Trial balance helpers
# ----------------------------------------------------------------------------

def natural(row, which):
    """Natural amount (positive in the class's normal state) for opening/period/closing."""
    d = row.get(f"{which}_debit") or ZERO
    c = row.get(f"{which}_credit") or ZERO
    if normal_side(row.get("account_class") or "") == "debit":
        return d - c
    return c - d


def oriented(row, which, side):
    """Amount oriented to a statement GROUP's normal side (contra accounts come out negative)."""
    d = row.get(f"{which}_debit") or ZERO
    c = row.get(f"{which}_credit") or ZERO
    return d - c if side == "debit" else c - d


def signed_debit(row, which):
    return (row.get(f"{which}_debit") or ZERO) - (row.get(f"{which}_credit") or ZERO)


def tb_periods(data):
    """Group trial balance rows by period_label."""
    ds = data["datasets"].get("trial_balance")
    periods = {}
    if not ds:
        return periods
    for r in ds["rows"]:
        label = r.get("period_label")
        if label is None:
            continue
        p = periods.setdefault(label, {"label": label, "start": r.get("period_start"), "end": r.get("period_end"),
                                       "rows": []})
        p["rows"].append(r)
    return periods


def sum_natural(period, classes, which):
    total = Decimal("0")
    found = False
    for r in period["rows"]:
        if r.get("account_class") in classes:
            total += natural(r, which)
            found = True
    return total, found
