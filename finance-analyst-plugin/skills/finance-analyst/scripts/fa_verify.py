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
    r"\b(receivable|debtor|overdue|collect)": {
        "ar_aging", "accounts_receivable", "dso", "revenue_by_customer", "rx_ar_overdue_total", "rx_ar_overdue_share",
        "rx_ar_overdue_by_customer", "rx_customer_open_receivables", "rx_near_term_receipts",
        "scn_collect_overdue_cash", "scn_collect_overdue_dso", "scn_collect_overdue_dso_change",
        "scn_dso_reduction_cash_release"},
    r"\b(payable|creditor|supplier|vendor)": {
        "ap_aging", "accounts_payable", "dpo", "rx_msme_overdue_total", "rx_msme_overdue_by_supplier",
        "rx_msme_max_days", "rx_near_term_obligations", "scn_msme_clearance_cash_after", "rx_cost_growth_gap",
        "scn_cost_normalisation_saving", "cost_category_variance", "expense_by_category"},
    r"\b(cash|bank balance|runway|burn)": {
        "cash_balance", "net_burn", "cash_runway", "settlement_variance", "rx_bank_book_difference",
        "rx_settlement_unlocated", "rx_near_term_coverage", "scn_collect_overdue_cash", "scn_settlement_recovery_cash",
        "scn_msme_clearance_cash_after", "scn_dso_reduction_cash_release", "rx_ar_overdue_total",
        "rx_customer_open_receivables", "rx_msme_overdue_total"},
    r"\b(margin)": {"gross_margin", "ebitda_margin", "operating_margin", "net_margin", "cost_to_revenue_ratio",
                    "rx_margin_change", "scn_margin_restoration_price_increase"},
    r"\b(settlement|payout)": {"settlement_variance", "marketplace_fees", "rx_settlement_unlocated",
                               "rx_settlement_days_unlocated", "rx_settlement_component", "scn_settlement_recovery_cash"},
    r"\b(budget)": {"budget_variance", "rx_budget_shortfall"},
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
        if mode == "chart" and a < Decimal(100000):
            return ("-" if v < 0 else "") + f"₹{fnum(a, '1')}"
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

    labels = [(k, config[k]["label"]) for k in ("current_period", "comparison_period") if config.get(k)]
    labels += [("sub_period", lb) for lb in periods if lb not in {x[1] for x in labels}]
    for key, lab in labels:
        if lab not in periods:
            continue
        rows = periods[lab]
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
        if key == "sub_period":
            continue
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
                basis = (b.get("amount_basis") or "").strip().lower()
                if basis == "tax_inclusive":
                    continue
                if b["account_class"] == "revenue_from_operations":
                    actual = out.get(("gross_revenue" if basis == "gross_revenue" else "net_revenue", cur["label"], ()))
                else:
                    actual = pl(rows, {b["account_class"]})
                key = (("account_class", b["account_class"]), ("measure", "variance"))
                out[("budget_variance", cur["label"], key)] = actual - num(b["amount"])
                out[("budget_variance", cur["label"], (("account_class", b["account_class"]),
                                                        ("measure", "actual")))] = actual
    return out, periods, bank


# ---------------------------------------------------------------- reflex recompute

def _d(iso):
    import datetime as _dt
    return _dt.date.fromisoformat(iso)


def recompute_reflex(input_dir, config, register, indep, periods, bank):
    """Independent recomputation of every reflex derived/scenario calculation (reflex_engine §35)."""
    cur, cmpp = config["current_period"], config.get("comparison_period")
    lab = cur["label"]
    as_of, start = _d(cur["end"]), _d(cur["start"])
    days = Decimal((as_of - start).days + 1)
    ar = load(os.path.join(input_dir, "ar_open_items.csv")) or []
    ap = load(os.path.join(input_dir, "ap_open_items.csv")) or []
    st = load(os.path.join(input_dir, "settlements.csv")) or []
    sales = load(os.path.join(input_dir, "sales_lines.csv")) or []
    budget = load(os.path.join(input_dir, "budget.csv")) or []
    window = int(config.get("reconciliation", {}).get("settlement_to_bank_days", 5))
    cash = indep.get(("cash_balance", lab, ()))
    rows_c = periods.get(lab, [])
    rows_p = periods.get(cmpp["label"], []) if cmpp else []

    def pl(rows, cls):
        return sum((nat(r, "period") for r in rows if r["account_class"] == cls), Z)

    def ar_ref(r):
        return _d(r["due_date"] or r["invoice_date"])

    def overdue(thr, cust=None):
        return sum((num(r["amount_outstanding"]) for r in ar if (as_of - ar_ref(r)).days > thr
                    and (cust is None or r["customer_id"] == cust)), Z)

    def msme(max_days, sup=None):
        sel = [r for r in ap if (r.get("msme_classification") or "").lower() in ("micro", "small")
               and (as_of - _d(r["bill_date"])).days > max_days and (sup is None or r["supplier_id"] == sup)]
        return sum((num(r["amount_outstanding"]) for r in sel), Z), max([(as_of - _d(r["bill_date"])).days
                                                                         for r in sel] or [0])

    def unlocated(row):
        net = (num(row["gross_amount"]) - num(row["fees"]) - num(row.get("tax_on_fees")) - num(row.get("refunds"))
               - num(row.get("withholdings")) + num(row.get("adjustments")))
        utr = (row.get("bank_reference") or "").upper()
        for b in bank or []:
            if num(b.get("credit")) > 0 and utr and (utr == (b.get("reference") or "").upper()
                                                     or utr in (b.get("narration") or "").upper()):
                return abs(num(b["credit"]) - net)
        if not utr:
            for b in bank or []:
                lag = (_d(b["transaction_date"]) - _d(row["settlement_date"])).days
                if num(b.get("credit")) == net and 0 <= lag <= window:
                    return Z
        return net

    credit_sales = sum((num(r["taxable_value"]) + num(r["tax_amount"]) for r in sales
                        if cur["start"] <= r["invoice_date"] <= cur["end"]), Z)
    ar_o = sum((nat(r, "opening") for r in rows_c if r["account_class"] == "trade_receivables"), Z)
    ar_c = sum((nat(r, "closing") for r in rows_c if r["account_class"] == "trade_receivables"), Z)
    nr_c, nr_p = indep.get(("net_revenue", lab, ())), indep.get(("net_revenue", cmpp["label"], ())) if cmpp else None
    rg = (nr_c - nr_p) / abs(nr_p) if nr_c is not None and nr_p else None
    thr_rec = next((r for r in register if r["metric_id"] == "rx_ar_overdue_total"), None)
    msme_rec = next((r for r in register if r["metric_id"] == "rx_msme_overdue_total"), None)
    out = {}
    for r in register:
        m = r["metric_id"]
        if not (m.startswith("rx_") or m.startswith("scn_")):
            continue
        dims = r["dimension"] or {}
        v = None
        if m == "rx_ar_overdue_total":
            v = overdue(int(dims["threshold_days"]))
        elif m == "rx_ar_overdue_share":
            v = overdue(int(dims["threshold_days"])) / sum((num(x["amount_outstanding"]) for x in ar), Z)
        elif m == "rx_ar_overdue_by_customer":
            v = overdue(int(dims["threshold_days"]), dims["customer_id"])
        elif m == "rx_customer_revenue_share":
            sel = [x for x in sales if cur["start"] <= x["invoice_date"] <= cur["end"]]
            tot = sum((num(x["taxable_value"]) for x in sel), Z)
            v = sum((num(x["taxable_value"]) for x in sel if x["customer_id"] == dims["customer_id"]), Z) / tot
        elif m == "rx_customer_open_receivables":
            v = sum((num(x["amount_outstanding"]) for x in ar if x["customer_id"] == dims["customer_id"]), Z)
        elif m == "rx_settlement_unlocated":
            v = unlocated(next(x for x in st if x["settlement_id"] == dims["settlement_id"]))
        elif m == "rx_settlement_days_unlocated":
            v = Decimal((as_of - _d(next(x for x in st if x["settlement_id"] == dims["settlement_id"])[
                "settlement_date"])).days)
        elif m == "rx_settlement_component":
            v = sum((num(x.get(dims["component"])) for x in st if cur["start"] <= x["settlement_date"] <= cur["end"]),
                    Z)
        elif m == "rx_bank_book_difference" and cash is not None:
            v = cash - sum((nat(x, "closing") for x in rows_c if x["account_class"] == "cash_and_cash_equivalents"), Z)
        elif m == "rx_margin_change" and cmpp:
            key = {"gross_margin": "gross_profit", "ebitda_margin": "ebitda"}[dims["margin"]]
            v = (indep[(key, lab, ())] / nr_c) - (indep[(key, cmpp["label"], ())] / nr_p)
        elif m == "rx_cost_growth_gap" and rg is not None:
            a, b = pl(rows_c, dims["account_class"]), pl(rows_p, dims["account_class"])
            v = (a - b) / abs(b) - rg
        elif m == "rx_budget_shortfall":
            b = next(x for x in budget if x["period_label"] == lab and x["account_class"] == dims["account_class"])
            basis = (b.get("amount_basis") or "").strip().lower()
            if dims["account_class"] == "revenue_from_operations":
                actual = indep.get(("gross_revenue" if basis == "gross_revenue" else "net_revenue", lab, ()))
            else:
                actual = pl(rows_c, dims["account_class"])
            v = abs(actual - num(b["amount"]))
        elif m == "rx_msme_overdue_total":
            v = msme(int(dims["max_days"]))[0]
        elif m == "rx_msme_overdue_by_supplier":
            v = msme(int(dims["max_days"]), dims["supplier_id"])[0]
        elif m == "rx_msme_max_days":
            v = Decimal(msme(int(dims["max_days"]))[1])
        elif m in ("rx_near_term_obligations", "rx_near_term_receipts", "rx_near_term_coverage"):
            obl = sum((num(x["amount_outstanding"]) for x in ap if (_d(x["due_date"] or x["bill_date"]) - as_of).days
                       <= 30), Z)
            rcp = sum((num(x["amount_outstanding"]) for x in ar if x.get("due_date")
                       and 0 < (_d(x["due_date"]) - as_of).days <= 30), Z)
            v = {"rx_near_term_obligations": obl, "rx_near_term_receipts": rcp,
                 "rx_near_term_coverage": (cash + rcp) / obl if cash is not None and obl else None}[m]
        elif m == "scn_collect_overdue_cash" and cash is not None and thr_rec:
            v = cash + overdue(int(thr_rec["dimension"]["threshold_days"]))
        elif m in ("scn_collect_overdue_dso", "scn_collect_overdue_dso_change") and thr_rec and credit_sales:
            new = (ar_o + ar_c - overdue(int(thr_rec["dimension"]["threshold_days"]))) / 2 / credit_sales * days
            v = new if m == "scn_collect_overdue_dso" else new - ((ar_o + ar_c) / 2 / credit_sales * days)
        elif m == "scn_dso_reduction_cash_release" and credit_sales:
            v = Decimal(dims["dso_reduction_days"]) * credit_sales / days
        elif m == "scn_settlement_recovery_cash" and cash is not None:
            v = cash + sum((unlocated(x) for x in st if cur["start"] <= x["settlement_date"] <= cur["end"]), Z)
        elif m == "scn_margin_restoration_price_increase" and cmpp:
            gm_p = indep[("gross_profit", cmpp["label"], ())] / nr_p
            v = indep[("cogs", lab, ())] / (1 - gm_p) / nr_c - 1
        elif m == "scn_cost_normalisation_saving" and rg is not None:
            a, b = pl(rows_c, dims["account_class"]), pl(rows_p, dims["account_class"])
            v = a - b * (1 + rg)
        elif m == "scn_msme_clearance_cash_after" and cash is not None and msme_rec:
            v = cash - msme(int(msme_rec["dimension"]["max_days"]))[0]
        out[(m, lab, tuple(sorted(dims.items())))] = v
    return out


NON_RELAXABLE = {"restricted_read", "customer_confirmation", "external_action", "financial_write"}
ALLOWED_STATUS = {
    "connector_read": {"requested", "shared", "pending_approval", "approved_requested", "not_requested_round_limit",
                       "deferred"},
    "gated": {"pending_approval", "approved", "approved_prepared", "rejected", "deferred"},
    "local": {"done", "skipped", "deferred", "scheduled_after_investigations"},
}


def check_approval_gates(run_dir, rx):
    problems = []
    if not rx or not rx.get("enabled"):
        return problems
    approvals = {}
    path = os.path.join(run_dir, "approvals.json")
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            approvals = {a["approval_id"]: a for a in json.load(fh).get("approved", [])}
    for cls in NON_RELAXABLE:
        if rx.get("config", {}).get("approvals", {}).get(cls) != "approval_required":
            problems.append(f"approval gate for {cls} is not approval_required")
    for inv in rx.get("investigations", []):
        for a in inv["actions"]:
            cls = a["action_class"]
            if cls in NON_RELAXABLE:
                if a["gate"] != "approval_required":
                    problems.append(f"{a['action_id']}: gate {a['gate']} for {cls}")
                if a["status"] not in ALLOWED_STATUS["gated"]:
                    problems.append(f"{a['action_id']}: status {a['status']} not allowed for {cls}")
                if a["status"] in ("approved", "approved_prepared") and a.get("approval_id") not in approvals:
                    problems.append(f"{a['action_id']}: marked approved without a matching approval record")
                if cls == "financial_write" and a.get("execution") not in (None, "customer"):
                    problems.append(f"{a['action_id']}: financial write must be executed by the customer")
            elif cls == "connector_read":
                if a.get("gate") not in ("auto_if_authorized", "approval_required"):
                    problems.append(f"{a['action_id']}: invalid connector gate {a.get('gate')}")
                if a["status"] not in ALLOWED_STATUS["connector_read"]:
                    problems.append(f"{a['action_id']}: status {a['status']} not allowed for connector_read")
            elif a["status"] not in ALLOWED_STATUS["local"]:
                problems.append(f"{a['action_id']}: unexpected status {a['status']}")
    for q in rx.get("approval_requests", []):
        if q["status"] in ("approved", "approved_prepared") and q["approval_id"] not in approvals:
            problems.append(f"{q['approval_id']}: approved without a matching approval record")
    listed = set()
    for p in rx.get("prepared", []):
        listed.add(p["file"])
        if p["approval_id"] not in approvals:
            problems.append(f"{p['file']}: prepared without an approved approval_id")
        if not os.path.isfile(os.path.join(run_dir, p["file"])):
            problems.append(f"{p['file']}: listed but missing")
        if p["action_class"] == "financial_write" and p["status"] != "prepared_customer_executes":
            problems.append(f"{p['file']}: financial write not marked customer-executed")
        if p["action_class"] == "external_action" and p["status"] != "prepared_not_sent":
            problems.append(f"{p['file']}: external action not marked not-sent")
    folder = os.path.join(run_dir, "prepared")
    if os.path.isdir(folder):
        for name in os.listdir(folder):
            if f"prepared/{name}" not in listed:
                problems.append(f"prepared/{name}: file not produced by an approved request")
    return problems


def check_charts(run_dir, rx, by_id):
    problems, n = [], 0
    for ch in (rx or {}).get("charts", []):
        spec_path = os.path.join(run_dir, ch["json"])
        svg_path = os.path.join(run_dir, ch["svg"])
        if not os.path.isfile(spec_path) or not os.path.isfile(svg_path):
            problems.append(f"{ch['chart_id']}: chart files missing")
            continue
        with open(spec_path, encoding="utf-8") as fh:
            spec = json.load(fh)
        with open(svg_path, encoding="utf-8") as fh:
            svg = fh.read()
        items = [(s, s.get("sign", 1)) for s in spec.get("series", [])]
        items += [(it, 1) for g in spec.get("groups", []) for it in g["items"]]
        for it, sign in items:
            n += 1
            rec = by_id.get(it["calc_id"])
            if rec is None or rec["value"] is None:
                problems.append(f"{ch['chart_id']}: {it['calc_id']} not a computed register value")
                continue
            if Decimal(str(it["value"])) != Decimal(rec["value"]) * sign:
                problems.append(f"{ch['chart_id']}: {it['calc_id']} charted {it['value']} but register has "
                                f"{rec['value']}")
            unit = it.get("unit", spec.get("unit", "money"))
            expect = fmt(it["value"], unit, "chart" if unit == "money" else "narrative", "units")
            if it.get("value_label") != expect:
                problems.append(f"{ch['chart_id']}: label {it.get('value_label')!r} expected {expect!r}")
            from xml.sax.saxutils import escape as _esc
            if _esc(expect) not in svg:
                problems.append(f"{ch['chart_id']}: value {expect!r} not drawn in the SVG")
        if "<title" not in svg or "<desc" not in svg:
            problems.append(f"{ch['chart_id']}: missing accessible title/description")
    return problems, n


# ---------------------------------------------------------------- 1.3.0 hardening checks

def status_overall(counts, outcome):
    """Overall status rule shared by fa_run (report_generation.status_line)."""
    if outcome == "failed":
        return "NOT VERIFIED"
    iss, rd = counts["issues"], counts["readiness"]
    if iss["critical"]:
        return "Calculations verified; some figures are blocked by critical data issues"
    if rd["blocked"]:
        return "Calculations verified; some figures are blocked"
    remain = []
    if iss["high"] or iss["medium"] or iss["low"]:
        remain.append("open data issues")
    if counts["exceptions"]:
        remain.append("unresolved reconciliation exceptions")
    if rd["partial"] or rd["needs_data"]:
        remain.append("partial or data-limited figures")
    if not remain:
        return "Calculations verified; no open data issues or exceptions"
    text = remain[0] if len(remain) == 1 else ", ".join(remain[:-1]) + " and " + remain[-1]
    return f"Calculations verified; {text} remain"


def independent_counts(issues, recon, register):
    sev = {k: 0 for k in ("critical", "high", "medium", "low", "informational")}
    for i in issues:
        if i.get("status", "open") == "open":
            sev[i["severity"]] += 1
    exc = sum(1 for rule in recon.get("rules", []) for r in rule.get("records", [])
              if r["match_status"] in ("unmatched", "conflicting", "probable_match", "requires_review"))
    exc += sum(1 for c in recon.get("conflicts", []) if c["status"] != "resolved")
    rd = {k: sum(1 for r in register if r["readiness"] == k) for k in ("partial", "blocked", "needs_data")}
    return {"issues": sev, "exceptions": exc, "readiness": rd}


STATUS_RE = re.compile(r"Data validation: (\d+) critical, (\d+) high, (\d+) medium, (\d+) low open issue\(s\) "
                       r"\((\d+) informational\); (\d+) unresolved reconciliation exception\(s\); (\d+) partial, "
                       r"(\d+) blocked, (\d+) needs-data calculation\(s\)")


def check_status(report, issues, recon, register):
    problems = []
    m = STATUS_RE.search(report)
    if not m or "STATUS_OVERALL_PLACEHOLDER" not in report or "VERIFICATION_STATUS_PLACEHOLDER" not in report:
        return ["status line missing or malformed"]
    c = independent_counts(issues, recon, register)
    got = [int(x) for x in m.groups()]
    want = [c["issues"][k] for k in ("critical", "high", "medium", "low", "informational")] + [c["exceptions"]] + [
        c["readiness"][k] for k in ("partial", "blocked", "needs_data")]
    if got != want:
        problems.append(f"status counts {got} differ from registers {want}")
    for phrase in ("fully validated", "all checks passed with no exceptions", "no issues found"):
        if phrase in report.lower() and (c["exceptions"] or sum(c["issues"].values()) - c["issues"]["informational"]):
            problems.append(f"report says '{phrase}' while issues or exceptions are open")
    return problems


PROFIT_WORD = re.compile(r"\bprofits?\b", re.IGNORECASE)
PROFIT_QUAL = {"gross": {"gross_profit", "gross_margin"}, "operating": {"operating_profit", "operating_margin"},
               "ebitda": {"ebitda", "ebitda_margin"}, "before tax": {"profit_before_tax"},
               "after tax": {"net_profit", "net_margin"}, "net": {"net_profit", "net_margin"}}
PROFIT_FAMILY = set().union(*PROFIT_QUAL.values())
SAVINGS_RE = re.compile(r"\b(sav(?:e|es|ed|ing|ings)|cost(?:s)? (?:\S+ )?less|cheaper|cut(?:ting)? (?:the )?costs?|"
                        r"reduc(?:e|ing|tion)(?: in)?(?: the)? costs?)\b", re.IGNORECASE)
LEAK_RE = re.compile(r"\b(leak(?:s|age|ages)?|(?:revenue|cash|settlement|financial|money|payout)\s+loss(?:es)?|"
                     r"lost\s+(?:revenue|cash|money|payouts?)|loss\s+of\s+(?:revenue|cash|money|funds))\b", re.IGNORECASE)
LEAK_NEG = re.compile(r"\b(?:not|never|no)\s+(?:a |an |any |the )?(?:confirmed |real |actual )?(?:leak\w*|loss\w*)",
                      re.IGNORECASE)
EVIDENCE_HEADINGS = ["### Verified findings", "### Unresolved reconciliation exceptions",
                     "### Estimates and scenarios (not facts)", "### Hypotheses to test"]


def _cited(item_text, refs, by_id, register):
    """Register records cited by placeholders and refs of one item."""
    recs = []
    for mm in PLACEHOLDER.finditer(item_text):
        kind, key, dims_txt, which = mm.group(1), mm.group(2), mm.group(3), mm.group(4)
        if kind == "calc":
            if key in by_id:
                recs.append(by_id[key])
            continue
        dims = dict(p.split("=", 1) for p in (dims_txt or "").split(",") if "=" in p)
        for r in register:
            if r["metric_id"] == key and all((r["dimension"] or {}).get(k) == v for k, v in dims.items()) and (
                    bool(dims) or not r["dimension"]):
                recs.append(r)
                break
    for ref in refs or []:
        if ref in by_id:
            recs.append(by_id[ref])
        elif ref.startswith("metric:"):
            body = ref[7:]
            mid, _, dims_txt = body.partition("[")
            dims = dict(p.split("=", 1) for p in dims_txt.rstrip("]").split(",") if "=" in p)
            for r in register:
                if r["metric_id"] == mid and all((r["dimension"] or {}).get(k) == v for k, v in dims.items()) and (
                        bool(dims) or not r["dimension"]):
                    recs.append(r)
                    break
    return recs


def text_items(narrative, rx):
    """(kind, text, refs, evidence_class) for every generated sentence that can carry claims."""
    out = []
    for i, t in enumerate(narrative.get("executive_summary") or [], 1):
        out.append((f"executive_summary #{i}", t, [], "fact"))
    for i, f in enumerate(narrative.get("findings") or [], 1):
        cls = {"estimate": "estimate", "hypothesis": "hypothesis", "limited": "fact_with_limitations",
               "customer_provided": "fact_with_limitations"}.get(f.get("label") or "fact", "fact")
        out.append((f"finding #{i}", f.get("statement", ""), f.get("refs"), cls))
    for i, r in enumerate(narrative.get("recommendations") or [], 1):
        out.append((f"recommendation #{i}", " ".join(str(r.get(k, "")) for k in ("title", "rationale", "impact")),
                    r.get("refs"), "recommendation"))
    for inv in (rx or {}).get("investigations", []):
        for n, ins in enumerate(inv["insights"], 1):
            out.append((f"reflex insight {inv['investigation_id']}#{n}", ins["text"], ins["refs"],
                        ins.get("evidence_class", "fact")))
    for r in (rx or {}).get("recommendations", []):
        out.append((f"reflex action {r.get('recommendation_id')}",
                    " ".join(str(r.get(k, "")) for k in ("title", "rationale", "impact")), r.get("refs"),
                    "recommendation"))
    return out


def check_profit_labels(items, by_id, register):
    problems = []
    for kind, text, refs, cls in items:
        plain = PLACEHOLDER.sub("", INPUT_PLACEHOLDER.sub("", text))
        cited = {r["metric_id"]: r for r in _cited(text, refs, by_id, register)}
        for mm in PROFIT_WORD.finditer(plain):
            before = plain[max(0, mm.start() - 12):mm.start()].lower()
            after = plain[mm.end():mm.end() + 14].lower()
            if after.startswith(" and loss") or after.startswith("-and-loss"):
                continue
            qual = None
            for q in ("gross", "operating", "ebitda", "net"):
                if re.search(rf"\b{q}\s*$", before):
                    qual = q
            if re.match(r"\s*(before|after)[ -]tax", after):
                qual = "before tax" if "before" in after[:8] else "after tax"
            if qual is None:
                problems.append(f"{kind}: unqualified 'profit' — say gross, EBITDA, operating, before tax or after tax")
                continue
            negated = re.match(r"[^.;]{0,30}\b(?:is |are )?(?:not stated|not available|cannot be stated|unavailable|"
                               r"withheld)\b", plain[mm.end():], re.IGNORECASE) or re.search(r"\bno\s+(?:\w+\s+)?$",
                                                                                          before)
            if negated or cls == "data_gap":
                continue  # statements that a profit level is NOT available are allowed
            fam = set(cited) & PROFIT_FAMILY
            if fam and not fam & PROFIT_QUAL[qual]:
                problems.append(f"{kind}: says '{qual} profit' but cites {sorted(fam)}")
            if qual in ("net", "after tax"):
                npf = cited.get("net_profit") or cited.get("net_margin")
                if npf is None or npf["readiness"] != "ready":
                    problems.append(f"{kind}: '{qual} profit' requires a ready net_profit (tax provision booked)")
    return problems


def check_savings(items, by_id, register):
    problems = []
    for kind, text, refs, _ in items:
        plain = PLACEHOLDER.sub("", text)
        if not SAVINGS_RE.search(INPUT_PLACEHOLDER.sub("", plain)):
            continue
        supported = INPUT_PLACEHOLDER.search(text) or any(
            (r.get("parameters") or {}).get("evidence_class") == "supported" for r in _cited(text, refs, by_id,
                                                                                            register))
        if not supported:
            problems.append(f"{kind}: '{SAVINGS_RE.search(plain).group(0)}' without a customer-supplied or "
                            "contract-evidenced figure")
    return problems


def check_leakage(items, by_id, register, rx, run_dir):
    problems = []
    for kind, text, refs, _ in items:
        plain = LEAK_NEG.sub("", PLACEHOLDER.sub("", text))
        plain = re.sub(r"profit\s+and\s+loss", "", plain, flags=re.IGNORECASE)
        if not LEAK_RE.search(plain):
            continue
        ok = any((r["metric_id"] == "rx_settlement_unlocated" and (r.get("parameters") or {}).get("nature") ==
                  "unexplained") or (r["metric_id"] == "settlement_variance" and (r["dimension"] or {}).get("class")
                                     == "unexplained") for r in _cited(text, refs, by_id, register))
        if not ok:
            problems.append(f"{kind}: uses '{LEAK_RE.search(plain).group(0)}' without citing an unexplained "
                            "shortfall beyond the timing window")
    for ch in (rx or {}).get("charts", []):
        path = os.path.join(run_dir, ch["json"])
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as fh:
                spec = json.load(fh)
            for s in spec.get("series", []):
                if s.get("nature") in ("recoverable_tax_credit", "revenue_reversal") and LEAK_RE.search(s["label"]):
                    problems.append(f"{ch['chart_id']}: '{s['label']}' labels a {s['nature']} as a loss")
    return problems


def check_evidence_separation(items, by_id, register, report, recon):
    problems = []
    for h in EVIDENCE_HEADINGS:
        if h not in report:
            problems.append(f"report section missing: {h}")
    for kind, text, refs, cls in items:
        if cls != "fact" or kind.startswith("executive_summary"):
            continue
        for r in _cited(text, refs, by_id, register):
            prm = r.get("parameters") or {}
            if prm.get("reflex") == "scenario" or prm.get("evidence_class") in ("indicative", "upper_bound"):
                problems.append(f"{kind}: verified finding cites scenario/estimate {r['calc_id']} ({r['metric_id']})")
            elif r["readiness"] != "ready":
                problems.append(f"{kind}: verified finding cites {r['readiness']} {r['calc_id']} ({r['metric_id']})")
    sec = report.split("### Unresolved reconciliation exceptions", 1)[1].split("\n### ", 1)[0] \
        if "### Unresolved reconciliation exceptions" in report else ""
    for rule in recon.get("rules", []):
        for r in rule.get("records", []):
            if r["match_status"] in ("unmatched", "conflicting", "probable_match") and r["settlement_id"] not in sec:
                problems.append(f"exception {r['settlement_id']} ({r['match_status']}) not listed as unresolved")
    for c in recon.get("conflicts", []):
        if c["status"] != "resolved" and c["conflict_id"] not in sec:
            problems.append(f"open conflict {c['conflict_id']} not listed as unresolved")
    return problems


TB_TRACED = {"gross_revenue", "sales_returns_and_allowances", "net_revenue", "cogs", "operating_expenses",
             "gross_profit", "ebitda", "operating_profit", "profit_before_tax", "net_profit", "finance_costs",
             "accounts_receivable", "accounts_payable", "inventory_value", "outstanding_debt", "expense_by_category"}
READD_TB = {"gross_revenue", "sales_returns_and_allowances", "cogs", "operating_expenses", "finance_costs",
            "expense_by_category"}
ROW_TRACED = {"ar_aging": ("ar_open_items.csv", "amount_outstanding"), "ap_aging": ("ap_open_items.csv",
                                                                                   "amount_outstanding"),
              "rx_ar_overdue_by_customer": ("ar_open_items.csv", "amount_outstanding"),
              "rx_customer_open_receivables": ("ar_open_items.csv", "amount_outstanding"),
              "rx_msme_overdue_by_supplier": ("ap_open_items.csv", "amount_outstanding"),
              "revenue_by_customer": ("sales_lines.csv", "taxable_value"),
              "revenue_by_product": ("sales_lines.csv", "taxable_value"),
              "revenue_by_channel": ("sales_lines.csv", "taxable_value")}


def check_source_trace(register, input_dir, periods):
    problems, traced = [], 0
    cache = {}

    def lines_of(fname):
        if fname not in cache:
            rows = load(os.path.join(input_dir, fname)) or []
            cache[fname] = {i + 2: r for i, r in enumerate(rows)}
        return cache[fname]
    for r in register:
        if r["value"] is None:
            continue
        if not r["inputs"] or any(not i.get("sha256") for i in r["inputs"]):
            problems.append(f"{r['calc_id']}: no hashed source dataset")
        prm = r.get("parameters") or {}
        m = r["metric_id"]
        if m in TB_TRACED:
            accts = prm.get("source_accounts")
            if accts is None or (not accts and Decimal(r["value"]) != 0):
                problems.append(f"{r['calc_id']} {m}: no contributing accounts listed")
                continue
            traced += 1
            if m in READD_TB:
                rows = [x for x in periods.get(r["period"]["label"], []) if x["account_id"] in accts]
                if sum((nat(x, "period") for x in rows), Z) != Decimal(r["value"]):
                    problems.append(f"{r['calc_id']} {m}: listed accounts do not re-add to the figure")
        elif m in ROW_TRACED:
            fname, col = ROW_TRACED[m]
            rows = prm.get("source_rows")
            if rows is None:
                problems.append(f"{r['calc_id']} {m}: no source rows listed")
                continue
            traced += 1
            data = lines_of(fname)
            if sum((num(data[i][col]) for i in rows if i in data), Z) != Decimal(r["value"]):
                problems.append(f"{r['calc_id']} {m}: listed rows of {fname} do not re-add to the figure")
    return problems, traced


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


def verify(run_dir, input_dir, excel_libreoffice=True):
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
    rx = j("reflex.json") if os.path.isfile(os.path.join(run_dir, "reflex.json")) else {}
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
    reflex_indep = recompute_reflex(input_dir, config, register, indep, periods, bank)
    for key, v in reflex_indep.items():
        if v is None:
            reflex_indep[key] = "not_recomputable"
    indep.update(reflex_indep)
    mism, compared = [], 0
    for r in register:
        key = (r["metric_id"], (r["period"] or {}).get("label"), tuple(sorted((r["dimension"] or {}).items())))
        if key in indep and r["readiness"] not in ("blocked", "needs_data"):
            compared += 1
            if indep[key] == "not_recomputable":
                mism.append(f"{r['calc_id']} {r['metric_id']}: no independent recomputation possible")
            elif not close(r["value"], indep[key], r["unit"]):
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
    reflex_items = {"reflex_insights": [ins for inv in rx.get("investigations", []) for ins in inv["insights"]],
                    "reflex_recommendations": rx.get("recommendations", [])}
    sources = dict(narrative)
    sources.update(reflex_items)
    for kind in ("findings", "recommendations", "reflex_insights", "reflex_recommendations"):
        for n, item in enumerate(sources.get(kind) or [], 1):
            refs = item.get("refs") or []
            if not refs:
                ce.append(f"{kind} #{n} has no evidence references")
            for ref in refs:
                if not ref_ok(ref):
                    ce.append(f"{kind} #{n} cites unknown reference {ref}")
            text = " ".join(strings_in({k: v for k, v in item.items() if k in ("statement", "title", "rationale",
                                                                               "impact", "text")}))
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
    for kind in ("findings", "recommendations", "reflex_insights", "reflex_recommendations"):
        for n, item in enumerate(sources.get(kind) or [], 1):
            item = {k: v for k, v in item.items() if k in ("statement", "title", "rationale", "impact", "text")}
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
        line = re.sub(r"\b(?:APR|REQ|INV|RXR|CALC|ISS|CON)-[0-9A-Za-z]+(?:-[0-9A-Za-z]+)*", "", line)  # own ids
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

    # 1.3.0 hardening checks
    items = text_items(narrative, rx)
    st = check_status(report, issues, recon, register)
    add("ver_status_consistency", not st, st or "status line counts equal the issue, reconciliation and calculation "
                                                 "registers")
    pl_problems = check_profit_labels(items, by_id, register)
    add("ver_profit_labels", not pl_problems, pl_problems or "every profit mention names its level and cites it")
    sv_problems = check_savings(items, by_id, register)
    add("ver_savings_claims", not sv_problems, sv_problems or "no unsupported savings claims")
    lk_problems = check_leakage(items, by_id, register, rx, run_dir)
    add("ver_leakage_classification", not lk_problems, lk_problems or "no recoverable, reversal or timing item called "
                                                                      "leakage")
    ev_problems = check_evidence_separation(items, by_id, register, report, recon)
    add("ver_evidence_separation", not ev_problems, ev_problems or "verified findings, exceptions, estimates and "
                                                                   "hypotheses are separated")
    tr_problems, traced = check_source_trace(register, input_dir, periods)
    add("ver_source_trace", not tr_problems, tr_problems or f"{traced} figure(s) traced to accounts or source rows "
                                                            "and re-added")
    months_cf = []
    sub_labels = {r["period"]["label"] for r in register if r["metric_id"] == "profit_before_tax"} - {
        config["current_period"]["label"], (config.get("comparison_period") or {}).get("label")}
    if sub_labels:
        for metric in ("net_revenue", "gross_profit", "operating_expenses", "ebitda", "profit_before_tax"):
            vals = [val(metric, lb) for lb in sub_labels]
            tot = val(metric, config["current_period"]["label"])
            if None not in vals and tot is not None and sum(vals, Z) != tot:
                months_cf.append(f"{metric}: months sum to {sum(vals, Z)} vs period {tot}")
    if months_cf:
        add("ver_cross_footing", False, months_cf)

    # Excel dashboard formulas (independent evaluator + LibreOffice when present)
    wb_path = os.path.join(run_dir, "dashboard.xlsx")
    if os.path.isfile(wb_path):
        import fa_xlsx_audit
        res = fa_xlsx_audit.audit(wb_path, register, use_libreoffice=excel_libreoffice)
        with open(os.path.join(run_dir, "dashboard_audit.json"), "w", encoding="utf-8") as fh:
            json.dump({k: v for k, v in res.items() if k != "cells"}, fh, indent=2, default=str)
        add("ver_excel_formulas", res["status"] == "passed",
            res["problems"] or (f"{res['formulas']} formulas evaluated independently, {res['mapped_checks']} equal "
                                f"their register values; LibreOffice: {res['libreoffice']['status']}"
                                + (f" ({res['libreoffice'].get('compared')} compared, 0 mismatches)"
                                   if res["libreoffice"].get("compared") else "")))
    else:
        add("ver_excel_formulas", True, "no workbook generated in this run")

    # reflex: chart data and approval gates
    chart_problems, charted = check_charts(run_dir, rx, by_id)
    add("ver_chart_data", not chart_problems, chart_problems or f"{charted} charted value(s) match the register")
    gate_problems = check_approval_gates(run_dir, rx)
    add("ver_approval_gates", not gate_problems, gate_problems or "no external or financial action executed; "
                                                                  "prepared files match approvals")

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
