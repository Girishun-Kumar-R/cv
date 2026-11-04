"""Independent verification (§24) of a rendered report.

Deliberately does NOT import fa_metrics, fa_data, fa_report or fa_common: it re-reads
the canonical CSVs, recomputes core figures with its own code, re-formats register
values with its own formatter, and checks claims, language and masking.

Usage: python3 fa_verify.py --run-dir RUN_DIR --input-dir INPUT_DIR
Exit code 0 = passed / passed_with_warnings, 3 = failed.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from decimal import ROUND_HALF_UP, Decimal, getcontext

getcontext().prec = 34
Z = Decimal("0")
DEBIT_NORMAL_PREFIXES = None  # computed from register-independent class lists below

ASSET = {"property_plant_equipment", "capital_work_in_progress", "intangible_assets", "non_current_investments",
         "long_term_loans_and_advances", "deferred_tax_assets", "other_non_current_assets", "inventories",
         "trade_receivables", "cash_and_cash_equivalents", "other_bank_balances", "current_investments",
         "short_term_loans_and_advances", "gst_input_credit_receivable", "tds_tcs_receivable", "prepaid_expenses",
         "other_current_assets"}
CUR_ASSET = {"inventories", "trade_receivables", "cash_and_cash_equivalents", "other_bank_balances",
             "current_investments", "short_term_loans_and_advances", "gst_input_credit_receivable",
             "tds_tcs_receivable", "prepaid_expenses", "other_current_assets"}
CUR_LIAB = {"short_term_borrowings", "current_maturities_of_long_term_debt", "trade_payables_msme",
            "trade_payables_others", "gst_payable", "tds_payable", "other_statutory_dues", "advances_from_customers",
            "other_current_liabilities", "short_term_provisions"}
COR = {"cost_of_materials_consumed", "purchases_of_stock_in_trade", "changes_in_inventories", "direct_expenses",
       "freight_inward", "subcontracting"}
OPEX = {"employee_benefits_expense", "selling_and_marketing", "advertising", "marketplace_fees",
        "payment_gateway_fees", "logistics_and_shipping", "rent", "utilities", "professional_fees",
        "technology_and_software", "travel", "repairs_and_maintenance", "insurance", "bad_debts_and_provisions",
        "office_and_admin", "miscellaneous_operating"}
SEP = {"exceptional_items", "prior_period_items", "foreign_exchange_loss_gain"}
TAX = {"current_tax", "deferred_tax"}
EXPENSE = COR | OPEX | SEP | TAX | {"depreciation_and_amortisation", "finance_costs"}
DEBIT_NORMAL = ASSET | EXPENSE | {"sales_returns_and_allowances", "drawings", "suspense", "unclassified",
                                  "intercompany", "inter_branch"}
BORROW = {"long_term_borrowings", "short_term_borrowings", "current_maturities_of_long_term_debt"}
PROHIBITED = [r"\byou are (fully )?gst[- ]compliant\b", r"\byour returns are correct\b", r"\bready to file\b",
              r"\baudit[- ]ready\b", r"\bguaranteed\b", r"\brisk[- ]free\b"]
DISCLAIMER_KEY = "It is decision support, not an audit, review, tax, legal or investment opinion."
RAW_FIGURE = re.compile(r"(₹|\bRs\.?|\bINR\b)\s*\d|\b\d{1,3}(,\d{2,3})+(\.\d+)?\b|\b\d+(\.\d+)?\s*(%|lakh|crore|cr\b)",
                        re.IGNORECASE)
PLACEHOLDER = re.compile(r"\{\{(calc|metric):([A-Za-z0-9_\-]+)(?:\[([^\]{}]+)\])?(?:@(current|comparison))?\}\}")
TOPICS = {
    r"\b(receivable|debtor|overdue|collect)": {"ar_aging", "accounts_receivable", "dso", "revenue_by_customer"},
    r"\b(payable|creditor|supplier|vendor)": {"ap_aging", "accounts_payable", "dpo"},
    r"\b(cash|bank balance|runway|burn)": {"cash_balance", "net_burn", "cash_runway", "settlement_variance"},
    r"\b(margin)": {"gross_margin", "ebitda_margin", "operating_margin", "net_margin", "cost_to_revenue_ratio"},
    r"\b(settlement|payout)": {"settlement_variance", "marketplace_fees"},
    r"\b(budget)": {"budget_variance"},
    r"\b(inventory|stock)": {"inventory_value", "dio", "inventory_turnover"},
}
INPUT_PLACEHOLDER = re.compile(r"\{\{input:([^|{}]+)\|([^{}]*)\}\}")


# ---------------------------------------------------------------- utilities

def num(s):
    if s is None or str(s).strip() == "":
        return Z
    return Decimal(str(s).replace(",", "").strip())


def load(path):
    if not os.path.isfile(path):
        return None
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return [{(k or "").strip(): (v or "").strip() for k, v in r.items()} for r in csv.DictReader(fh)]


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        h.update(fh.read())
    return h.hexdigest()


def nat(row, which):
    d, c = num(row.get(f"{which}_debit")), num(row.get(f"{which}_credit"))
    return d - c if row.get("account_class") in DEBIT_NORMAL else c - d


def group3(digits):
    if len(digits) <= 3:
        return digits
    head, tail = digits[:-3], digits[-3:]
    chunks = []
    while len(head) > 2:
        chunks.insert(0, head[-2:])
        head = head[:-2]
    return ",".join(([head] if head else []) + chunks + [tail])


def fnum(v, places):
    q = abs(v).quantize(Decimal(places), rounding=ROUND_HALF_UP)
    t = format(q, "f")
    i, _, f = t.partition(".")
    return group3(i) + ("." + f if f else "")


def fmt(value, unit, mode, scale):
    v = Decimal(value)
    if unit == "money":
        if mode == "table":
            div = {"units": Decimal(1), "thousands": Decimal(1000), "lakhs": Decimal(100000),
                   "crores": Decimal(10000000)}[scale]
            body = fnum(v / div, "0.01")
            return f"({body})" if v < 0 else body
        a = abs(v)
        if a >= Decimal(10000000):
            body = f"₹{fnum(a / Decimal(10000000), '0.01')} crore"
        elif a >= Decimal(100000):
            body = f"₹{fnum(a / Decimal(100000), '0.01')} lakh"
        else:
            body = f"₹{fnum(a, '0.01')}"
        return ("-" if v < 0 else "") + body
    if unit == "percent":
        return f"{(v * 100).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)}%"
    if unit == "ratio":
        return f"{v.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)}"
    if unit == "days":
        return f"{v.quantize(Decimal('1'), rounding=ROUND_HALF_UP)} days"
    if unit == "months":
        return f"{v.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)} months"
    if unit == "index":
        return f"{v.quantize(Decimal('1'), rounding=ROUND_HALF_UP)}"
    if unit == "count":
        return group3(str(int(v.quantize(Decimal('1'), rounding=ROUND_HALF_UP))))
    return str(v)


def close(a, b, unit):
    if a is None or b is None:
        return a is None and b is None
    if unit == "money":
        return Decimal(a) == Decimal(b)
    return abs(Decimal(a) - Decimal(b)) <= Decimal("1e-12")


# ---------------------------------------------------------------- recompute

def recompute(input_dir, config):
    """Independent figures keyed by (metric_id, period_label, dimension-tuple)."""
    out = {}
    tb = load(os.path.join(input_dir, "trial_balance.csv")) or []
    periods = {}
    for r in tb:
        periods.setdefault(r["period_label"], []).append(r)

    def pl(rows, classes):
        return sum((nat(r, "period") for r in rows if r["account_class"] in classes), Z)

    def bal(rows, classes, which="closing"):
        return sum((nat(r, which) for r in rows if r["account_class"] in classes), Z)

    for key in ("current_period", "comparison_period"):
        p = config.get(key)
        if not p or p["label"] not in periods:
            continue
        rows = periods[p["label"]]
        lab = p["label"]
        gross = pl(rows, {"revenue_from_operations"})
        ret = pl(rows, {"sales_returns_and_allowances"})
        nr = gross + pl(rows, {"other_operating_revenue"}) - ret
        cogs = pl(rows, COR)
        opex = pl(rows, OPEX)
        gp = nr - cogs
        ebitda = gp - opex
        op = ebitda - pl(rows, {"depreciation_and_amortisation"})
        pbt = op + pl(rows, {"other_income"}) - pl(rows, {"finance_costs"}) - pl(rows, SEP)
        npf = pbt - pl(rows, TAX)
        for m, v in (("gross_revenue", gross), ("sales_returns_and_allowances", ret), ("net_revenue", nr),
                     ("cogs", cogs), ("gross_profit", gp), ("operating_expenses", opex), ("ebitda", ebitda),
                     ("operating_profit", op), ("profit_before_tax", pbt), ("net_profit", npf)):
            out[(m, lab, ())] = v
        if nr != 0:
            out[("gross_margin", lab, ())] = gp / nr
            out[("net_margin", lab, ())] = npf / nr
        if key == "current_period":
            ca, cl = bal(rows, CUR_ASSET), bal(rows, CUR_LIAB)
            inv = bal(rows, {"inventories"})
            pre = bal(rows, {"prepaid_expenses"})
            out[("accounts_receivable", lab, ())] = bal(rows, {"trade_receivables"})
            out[("accounts_payable", lab, ())] = bal(rows, {"trade_payables_msme", "trade_payables_others"})
            out[("inventory_value", lab, ())] = inv
            out[("outstanding_debt", lab, ())] = bal(rows, BORROW)
            out[("working_capital", lab, ())] = ca - cl
            if cl != 0:
                out[("current_ratio", lab, ())] = ca / cl
                out[("quick_ratio", lab, ())] = (ca - inv - pre) / cl
    cur = config["current_period"]
    cmpp = config.get("comparison_period")
    if cmpp and ("net_revenue", cmpp["label"], ()) in out and ("net_revenue", cur["label"], ()) in out:
        b = out[("net_revenue", cmpp["label"], ())]
        if b != 0:
            out[("revenue_growth", cur["label"], ())] = (out[("net_revenue", cur["label"], ())] - b) / abs(b)
    bank = load(os.path.join(input_dir, "bank_transactions.csv"))
    if bank:
        last = {}
        for r in bank:
            if r.get("transaction_date") and r["transaction_date"] <= cur["end"] and r.get("balance"):
                last[r["bank_account_ref"]] = num(r["balance"])
        out[("cash_balance", cur["label"], ())] = sum(last.values(), Z)
    for fname, metric in (("ar_open_items.csv", "ar_aging"), ("ap_open_items.csv", "ap_aging")):
        rows = load(os.path.join(input_dir, fname))
        if rows:
            out[(metric, cur["label"], (("bucket", "total"),))] = sum((num(r["amount_outstanding"]) for r in rows), Z)
    sales = load(os.path.join(input_dir, "sales_lines.csv"))
    if sales:
        per = {}
        for r in sales:
            if cur["start"] <= r["invoice_date"] <= cur["end"]:
                per[r["customer_id"]] = per.get(r["customer_id"], Z) + num(r["taxable_value"])
        total = sum(per.values(), Z)
        if total:
            out[("customer_concentration", cur["label"], (("measure", "top_1_share"),))] = max(per.values()) / total
    budget = load(os.path.join(input_dir, "budget.csv"))
    if budget and cur["label"] in periods:
        rows = periods[cur["label"]]
        for b in budget:
            if b["period_label"] == cur["label"]:
                actual = pl(rows, {b["account_class"]})
                out[("budget_variance", cur["label"],
                     (("account_class", b["account_class"]), ("measure", "variance")))] = actual - num(b["amount"])
    return out, periods, bank


# ---------------------------------------------------------------- main checks

def strings_in(obj, skip=("refs", "label", "confidence", "effort", "professional_review_needed")):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, list):
        for x in obj:
            yield from strings_in(x, skip)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if k not in skip:
                yield from strings_in(v, skip)


def verify(run_dir, input_dir):
    def j(name):
        with open(os.path.join(run_dir, name), encoding="utf-8") as fh:
            return json.load(fh)
    config = j("run_config.json")
    register = j("calc_register.json")
    manifest = j("render_manifest.json")
    sources = j("source_manifest.json")
    issues = j("issues.json")
    recon = j("reconciliation.json")
    narrative = j("narrative.json") if os.path.isfile(os.path.join(run_dir, "narrative.json")) else {}
    with open(os.path.join(run_dir, "report_draft.md"), encoding="utf-8") as fh:
        report = fh.read()
    by_id = {r["calc_id"]: r for r in register}
    checks = []

    def add(cid, ok, details, warn=False):
        checks.append({"id": cid, "status": "passed" if ok else ("warning" if warn else "failed"),
                       "details": details})

    # ver_no_fabrication
    problems = []
    ids = set()
    for s in sources:
        ids.add(s["dataset_id"])
        path = os.path.join(input_dir, s["file"])
        if not os.path.isfile(path):
            problems.append(f"{s['file']} missing")
        elif sha(path) != s["sha256"]:
            problems.append(f"{s['file']} hash changed since the run")
    for r in register:
        for i in r["inputs"]:
            if i["dataset_id"] not in ids:
                problems.append(f"{r['calc_id']} cites unknown dataset {i['dataset_id']}")
    add("ver_no_fabrication", not problems, problems or "all inputs exist with matching hashes")

    # ver_recompute_figures
    indep, periods, bank = recompute(input_dir, config)
    mism, compared = [], 0
    for r in register:
        key = (r["metric_id"], (r["period"] or {}).get("label"), tuple(sorted((r["dimension"] or {}).items())))
        if key in indep and r["readiness"] not in ("blocked", "needs_data"):
            compared += 1
            if not close(r["value"], indep[key], r["unit"]):
                mism.append(f"{r['calc_id']} {r['metric_id']}: register {r['value']} vs recomputed {indep[key]}")
    add("ver_recompute_figures", not mism and compared > 0 or (not mism and not periods),
        mism or f"{compared} figures recomputed independently and matched")

    # ver_register_tieout
    bad = []
    for m in manifest:
        if m.get("calc_id") is None:
            bad.append(f"unresolved placeholder {m.get('placeholder')} in {m.get('context')}")
            continue
        rec = by_id.get(m["calc_id"])
        if rec is None:
            bad.append(f"{m['calc_id']} not in register")
            continue
        if rec["value"] is not None:
            expect = fmt(rec["value"], rec["unit"], m["mode"], m["scale"])
            if expect != m["rendered"]:
                bad.append(f"{m['calc_id']} rendered {m['rendered']!r}, expected {expect!r}")
        if m["rendered"] not in report:
            bad.append(f"{m['calc_id']} value {m['rendered']!r} not found in report")
    add("ver_register_tieout", not bad, bad or f"{len(manifest)} rendered figures tie to the register")

    # placeholders resolved
    leftovers = PLACEHOLDER.findall(report) or INPUT_PLACEHOLDER.findall(report) or (
        "[unresolved reference]" in report) or ("{{" in report)
    add("ver_placeholders_resolved", not leftovers, "unresolved placeholders present" if leftovers else "none left")

    # narrative raw figures
    raw = []
    for s in strings_in(narrative):
        for mm in INPUT_PLACEHOLDER.finditer(s):
            if not mm.group(2).strip():
                raw.append(f"input placeholder without a source label: {mm.group(0)}")
        stripped = PLACEHOLDER.sub("", INPUT_PLACEHOLDER.sub("", s))
        for mm in RAW_FIGURE.finditer(stripped):
            raw.append(f"{mm.group(0)!r} in: {s[:80]}")
    add("ver_narrative_raw_numbers", not raw, raw or "narrative uses placeholders for all figures")

    # cross-footing identities
    cf = []

    def val(metric, period, **dims):
        for r in register:
            if r["metric_id"] == metric and (r["period"] or {}).get("label") == period and (
                    (r["dimension"] or {}) == dims) and r["value"] is not None:
                return Decimal(r["value"])
        return None
    for p in [config["current_period"]] + ([config["comparison_period"]] if config.get("comparison_period") else []):
        lab = p["label"]
        for a, b, c, name in (("gross_profit", "net_revenue", "cogs", "GP = NR - COGS"),
                              ("ebitda", "gross_profit", "operating_expenses", "EBITDA = GP - opex")):
            va, vb, vc = val(a, lab), val(b, lab), val(c, lab)
            if None not in (va, vb, vc) and va != vb - vc:
                cf.append(f"{lab}: {name} fails")
    for metric in ("ar_aging", "ap_aging"):
        total = val(metric, config["current_period"]["label"], bucket="total")
        if total is not None:
            parts = sum((Decimal(r["value"]) for r in register if r["metric_id"] == metric and
                         (r["dimension"] or {}).get("bucket") not in (None, "total") and r["value"] is not None), Z)
            if parts != total:
                cf.append(f"{metric}: buckets {parts} != total {total}")
    for r in register:
        d = r["dimension"] or {}
        if r["metric_id"] == "budget_variance" and d.get("measure") == "variance" and r["value"] is not None:
            a = val("budget_variance", r["period"]["label"], account_class=d["account_class"], measure="actual")
            b = val("budget_variance", r["period"]["label"], account_class=d["account_class"], measure="budget")
            if None not in (a, b) and Decimal(r["value"]) != a - b:
                cf.append(f"budget {d['account_class']}: variance != actual - budget")
        if r["metric_id"] == "period_over_period_variance" and d.get("measure") == "amount" and r["value"]:
            cmpl = config["comparison_period"]["label"]
            c, b = val(d["line"], r["period"]["label"]), val(d["line"], cmpl)
            if None not in (c, b) and Decimal(r["value"]) != c - b:
                cf.append(f"variance {d['line']}: != current - comparison")
    add("ver_cross_footing", not cf, cf or "statement, aging, budget and variance identities hold")

    # claims and evidence
    valid_refs = set(by_id) | {i["issue_id"] for i in issues} | {c["conflict_id"] for c in recon.get("conflicts", [])}
    valid_refs |= {f"metric:{r['metric_id']}" for r in register if r["readiness"] not in ("blocked", "needs_data")}
    valid_refs |= {f"check:{i['check_id']}" for i in issues}

    def ref_ok(ref):
        if ref in valid_refs:
            return True
        m = re.fullmatch(r"metric:([a-z0-9_]+)\[([^\]]+)\]", ref)
        if m:
            dims = dict(p.split("=", 1) for p in m.group(2).split(",") if "=" in p)
            return any(r["metric_id"] == m.group(1) and all((r["dimension"] or {}).get(k.strip()) == v.strip()
                                                            for k, v in dims.items())
                       and r["readiness"] not in ("blocked", "needs_data") for r in register)
        return False

    def ph_metric(match):
        kind, key = match.group(1), match.group(2)
        if kind == "calc":
            return (by_id.get(key) or {}).get("metric_id")
        return key
    ce = []
    for kind in ("findings", "recommendations"):
        for n, item in enumerate(narrative.get(kind) or [], 1):
            refs = item.get("refs") or []
            if not refs:
                ce.append(f"{kind} #{n} has no evidence references")
            for ref in refs:
                if not ref_ok(ref):
                    ce.append(f"{kind} #{n} cites unknown reference {ref}")
            text = " ".join(strings_in(item))
            cited = {r.split(":", 1)[1].split("[", 1)[0] for r in refs if r.startswith("metric:")}
            cited |= {by_id[r]["metric_id"] for r in refs if r in by_id}
            for mm in PLACEHOLDER.finditer(text):
                metric = ph_metric(mm)
                if metric and metric not in cited:
                    ce.append(f"{kind} #{n}: figure {mm.group(0)} ({metric}) is not listed in refs")
            for ph in re.findall(r"\{\{calc:([A-Za-z0-9\-]+)\}\}", text):
                rec = by_id.get(ph)
                if rec and rec["readiness"] in ("blocked", "needs_data"):
                    ce.append(f"{kind} #{n} relies on {ph} which is {rec['readiness']}")
    add("ver_claim_evidence", not ce, ce or "every finding and recommendation cites valid evidence")

    # topic consistency (heuristic, warning only)
    tw = []
    for kind in ("findings", "recommendations"):
        for n, item in enumerate(narrative.get(kind) or [], 1):
            text = " ".join(strings_in(item)).lower()
            metrics = {ph_metric(mm) for mm in PLACEHOLDER.finditer(" ".join(strings_in(item)))} - {None}
            if not metrics:
                continue
            mentioned = [(re.search(pat, text).group(0), allowed) for pat, allowed in TOPICS.items()
                         if re.search(pat, text)]
            if mentioned and not any(metrics & allowed for _, allowed in mentioned):
                tw.append(f"{kind} #{n} mentions {', '.join(repr(w) for w, _ in mentioned)} but cites only "
                          f"{sorted(metrics)}")
    add("ver_claim_topic_consistency", not tw, tw or "cited figures match the topics mentioned", warn=True)

    # direction words vs sign (basic)
    dw = []
    for n, item in enumerate(narrative.get("findings") or [], 1):
        st = item.get("statement", "")
        for ph in re.findall(r"\{\{calc:([A-Za-z0-9\-]+)\}\}", st):
            rec = by_id.get(ph)
            if rec and rec["value"] is not None and rec["metric_id"] in (
                    "period_over_period_variance", "revenue_growth", "expense_growth", "cost_category_variance"):
                v = Decimal(rec["value"])
                low = st.lower()
                if v > 0 and re.search(r"\b(fell|decreased|declined|dropped|lower)\b", low) and not re.search(
                        r"\b(rose|increased|grew|higher)\b", low):
                    dw.append(f"finding #{n}: says decrease but {ph} is positive")
                if v < 0 and re.search(r"\b(rose|increased|grew|higher)\b", low) and not re.search(
                        r"\b(fell|decreased|declined|dropped|lower)\b", low):
                    dw.append(f"finding #{n}: says increase but {ph} is negative")
    add("ver_direction_words", not dw, dw or "no contradictions found")

    # limitations disclosed
    lim_text = report.split("## Limitations", 1)[1].split("\n## ", 1)[0] if "## Limitations" in report else ""
    missing = sorted({r["metric_id"] for r in register if r["readiness"] != "ready"
                      and f"`{r['metric_id']}`" not in lim_text})
    add("ver_limitations_disclosed", not missing, missing or "every non-ready metric is listed under Limitations")

    # masking
    mk = []
    for line in report.splitlines():
        if line.startswith("| CALC-") or "SHA-256" in line:
            continue
        no_gstin = re.sub(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z][A-Z0-9][0-9A-Z]\b", "", line)
        if re.search(r"\b[A-Z]{5}\d{4}[A-Z]\b", no_gstin):
            mk.append(f"possible unmasked PAN: {line[:80]}")
        if re.search(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}\b", line):
            mk.append(f"possible Aadhaar-like number: {line[:80]}")
        if re.search(r"(?<![\d.,])\d{9,}(?![\d.,])", line):
            mk.append(f"possible unmasked account number: {line[:80]}")
    add("ver_masking", not mk, mk or "no unmasked identifiers detected")

    # boundary language
    bl = [p for p in PROHIBITED if re.search(p, report, re.IGNORECASE)]
    add("ver_boundary_language", not bl, bl or "no prohibited assurance language")

    add("ver_disclaimers", DISCLAIMER_KEY in report, "standard disclaimer present" if DISCLAIMER_KEY in report
        else "standard disclaimer missing")

    # double count guard in settlement matching
    dc = []
    for rule in recon.get("rules", []):
        lines = [r["bank_line"] for r in rule.get("records", []) if r.get("bank_line") is not None]
        if len(lines) != len(set(lines)):
            dc.append(f"{rule['rule_id']}: a bank line is matched to more than one settlement")
        sids = [r["settlement_id"] for r in rule.get("records", [])]
        if len(sids) != len(set(sids)):
            dc.append(f"{rule['rule_id']}: a settlement appears twice")
    add("ver_double_count_guard", not dc, dc or "no bank line or settlement counted twice")

    # conflict figures recomputed
    cfx = []
    for c in recon.get("conflicts", []):
        if c["conflict_id"] == "CON-BANK-BOOK" and bank is not None:
            cur = config["current_period"]
            stmt = indep.get(("cash_balance", cur["label"], ()))
            book = sum((nat(r, "closing") for r in periods.get(cur["label"], [])
                        if r["account_class"] == "cash_and_cash_equivalents"), Z)
            if stmt is not None and (Decimal(str(c["figures"][0]["value"])) != stmt or
                                     Decimal(str(c["figures"][1]["value"])) != book):
                cfx.append("bank vs book conflict figures do not recompute")
    add("ver_conflict_figures", not cfx, cfx or "conflict figures recompute")

    failed = [c for c in checks if c["status"] == "failed"]
    warned = [c for c in checks if c["status"] == "warning"]
    outcome = "failed" if failed else ("passed_with_warnings" if warned else "passed")
    return {"outcome": outcome, "passed_checks": sum(c["status"] == "passed" for c in checks),
            "total_checks": len(checks), "draft_sha256": hashlib.sha256(report.encode("utf-8")).hexdigest(),
            "checks": checks}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--input-dir", required=True)
    a = ap.parse_args(argv)
    res = verify(a.run_dir, a.input_dir)
    with open(os.path.join(a.run_dir, "verification.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, ensure_ascii=False)
    print(f"verification: {res['outcome']} ({res['passed_checks']}/{res['total_checks']} checks passed)")
    for c in res["checks"]:
        if c["status"] != "passed":
            print(f"  {c['status'].upper()} {c['id']}: {c['details']}")
    return 3 if res["outcome"] == "failed" else 0


if __name__ == "__main__":
    sys.exit(main())
