"""Propose canonical account_class mappings for a chart of accounts / trial balance.

    python3 fa_classify.py --input accounts.csv --name-col "Particulars" [--group-col "Group"]
                           [--balance-col "Closing Balance"] [--id-col "Ledger Code"] --out class_map.csv

Rules: TallyPrime-style group names first, then ledger-name keywords, then the
balance side for tax ledgers. Every row is a PROPOSAL with confidence and rule;
material and low-confidence rows must be confirmed by the customer before use
(workflow stage normalization_and_mapping). Output columns:
account_id, account_name, source_group, proposed_class, confidence, rule, confirmed.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fa_common import ALL_CLASSES, parse_amount, read_csv, write_csv  # noqa: E402

GROUP_RULES = [
    (r"^sundry debtors$", "trade_receivables", "high"),
    (r"^sundry creditors$", "trade_payables_others", "medium"),
    (r"^bank accounts?$", "cash_and_cash_equivalents", "high"),
    (r"^cash[- ]in[- ]hand$", "cash_and_cash_equivalents", "high"),
    (r"^bank od a/?c|^bank occ a/?c|^bank overdraft", "short_term_borrowings", "high"),
    (r"^stock[- ]in[- ]hand$", "inventories", "high"),
    (r"^fixed assets$", "property_plant_equipment", "medium"),
    (r"^investments$", "non_current_investments", "low"),
    (r"^deposits \(asset\)$", "other_non_current_assets", "low"),
    (r"^loans (&|and) advances \(asset\)$", "short_term_loans_and_advances", "low"),
    (r"^current assets$", "other_current_assets", "low"),
    (r"^current liabilities$", "other_current_liabilities", "low"),
    (r"^provisions$", "short_term_provisions", "medium"),
    (r"^secured loans$", "long_term_borrowings", "low"),
    (r"^unsecured loans$", "long_term_borrowings", "low"),
    (r"^loans \(liability\)$", "long_term_borrowings", "low"),
    (r"^capital account$", "share_capital", "low"),
    (r"^reserves (&|and) surplus$", "reserves_and_surplus", "high"),
    (r"^sales accounts?$", "revenue_from_operations", "high"),
    (r"^purchase accounts?$", "purchases_of_stock_in_trade", "medium"),
    (r"^direct incomes?$", "other_operating_revenue", "low"),
    (r"^indirect incomes?$", "other_income", "medium"),
    (r"^direct expenses$", "direct_expenses", "medium"),
    (r"^misc\.? expenses \(asset\)$", "other_non_current_assets", "low"),
    (r"^suspense a/?c$", "suspense", "high"),
    (r"^branch ?/ ?divisions$", "inter_branch", "medium"),
]
NAME_RULES = [
    (r"depreciation|amortis|amortiz", "depreciation_and_amortisation", "high"),
    (r"interest (on|paid)|loan interest|finance charge|processing fee", "finance_costs", "medium"),
    (r"salar|wages|bonus|staff welfare|provident|\bpf\b|\besi\b|gratuity", "employee_benefits_expense", "medium"),
    (r"\brent\b", "rent", "medium"),
    (r"electric|power|water charges|utilit", "utilities", "medium"),
    (r"advertis|marketing|promotion", "advertising", "medium"),
    (r"amazon|flipkart|meesho|marketplace|commission", "marketplace_fees", "low"),
    (r"razorpay|payu|gateway|cashfree|paytm|stripe", "payment_gateway_fees", "low"),
    (r"freight inward|carriage inward", "freight_inward", "medium"),
    (r"freight|courier|shipping|logistic|delivery", "logistics_and_shipping", "low"),
    (r"audit|legal|professional|consult", "professional_fees", "medium"),
    (r"software|subscription|cloud|hosting|internet", "technology_and_software", "low"),
    (r"travel|conveyance", "travel", "medium"),
    (r"repair|maintenance", "repairs_and_maintenance", "medium"),
    (r"insurance", "insurance", "medium"),
    (r"bad debt|doubtful", "bad_debts_and_provisions", "medium"),
    (r"income tax|current tax|provision for tax", "current_tax", "low"),
    (r"deferred tax", "deferred_tax", "low"),
    (r"sales return|returns inward", "sales_returns_and_allowances", "medium"),
    (r"opening stock|closing stock|change in stock", "changes_in_inventories", "low"),
    (r"interest (received|income)|dividend", "other_income", "medium"),
    (r"drawings", "drawings", "high"),
    (r"partner.*capital|capital.*partner", "partners_capital_accounts", "medium"),
    (r"prepaid", "prepaid_expenses", "medium"),
    (r"printing|stationery|office|telephone|postage", "office_and_admin", "low"),
]
DEFINITIVE_GROUP_CLASSES = {"trade_receivables", "trade_payables_others", "cash_and_cash_equivalents",
                            "short_term_borrowings", "inventories", "revenue_from_operations", "reserves_and_surplus",
                            "suspense", "inter_branch", "short_term_provisions", "long_term_borrowings",
                            "share_capital", "property_plant_equipment"}
PRIORITY_NAME_RULES = [
    (r"sales return|returns inward|credit note", "sales_returns_and_allowances", "medium"),
    (r"drawings", "drawings", "high"),
]
TAX_LEDGER = re.compile(r"\b(cgst|sgst|igst|utgst|gst|cess|tds|tcs)\b", re.IGNORECASE)


def propose(name, group, balance):
    n, g = (name or "").strip().lower(), (group or "").strip().lower()
    if TAX_LEDGER.search(n) or g == "duties & taxes" or g == "duties and taxes":
        is_tds = re.search(r"\b(tds|tcs)\b", n)
        if balance is not None and balance > 0:  # debit balance => asset (credit receivable)
            return ("tds_tcs_receivable" if is_tds else "gst_input_credit_receivable"), "medium", \
                "tax ledger with debit balance"
        if re.search(r"\binput\b|\bitc\b", n):
            return "gst_input_credit_receivable", "medium", "tax ledger named input"
        return ("tds_payable" if is_tds else "gst_payable"), "medium", "tax ledger with credit/zero balance"
    for pat, cls, conf in PRIORITY_NAME_RULES:  # contra items that sit inside definitive groups
        if re.search(pat, n):
            return cls, conf, f"name matches /{pat}/"
    for pat, cls, conf in GROUP_RULES:  # balance-sheet and sales groups are definitive
        if cls in DEFINITIVE_GROUP_CLASSES and re.search(pat, g):
            return cls, conf, f"group '{group}'"
    for pat, cls, conf in NAME_RULES:
        if re.search(pat, n):
            return cls, conf, f"name matches /{pat}/"
    for pat, cls, conf in GROUP_RULES:
        if re.search(pat, g):
            return cls, conf, f"group '{group}'"
    if g in ("indirect expenses", "expenses (indirect)"):
        return "miscellaneous_operating", "low", "indirect expense without a specific keyword"
    return "unclassified", "low", "no rule matched - customer confirmation required"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True)
    ap.add_argument("--name-col", required=True)
    ap.add_argument("--group-col")
    ap.add_argument("--balance-col", help="signed closing balance (debit positive) or with Dr/Cr suffix")
    ap.add_argument("--id-col")
    ap.add_argument("--skip", action="append", help="regex for rows to skip (default: grand total / total)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    rows, headers = read_csv(a.input)
    for col in [a.name_col, a.group_col, a.balance_col, a.id_col]:
        if col and col not in headers:
            print(f"column '{col}' not found; available: {headers}")
            return 2
    out = []
    skip = [re.compile(p, re.IGNORECASE) for p in (a.skip or [r"^grand total", r"^total\b"])]
    for r in rows:
        name = r.get(a.name_col)
        if not name or any(p.search(name) for p in skip):
            continue
        if all(not (v or "").strip() for k, v in r.items() if k != a.name_col):
            continue  # title/heading row: only the name cell is filled
        bal = None
        if a.balance_col:
            try:
                bal = parse_amount(r.get(a.balance_col))
            except ValueError:
                bal = None
        cls, conf, rule = propose(name, r.get(a.group_col) if a.group_col else "", bal)
        assert cls in ALL_CLASSES
        out.append({"account_id": r.get(a.id_col) if a.id_col else name, "account_name": name,
                    "source_group": r.get(a.group_col, "") if a.group_col else "", "proposed_class": cls,
                    "confidence": conf, "rule": rule, "confirmed": "no"})
    write_csv(a.out, out, ["account_id", "account_name", "source_group", "proposed_class", "confidence", "rule",
                           "confirmed"])
    low = sum(1 for o in out if o["confidence"] == "low")
    print(f"{len(out)} accounts proposed; {low} low-confidence (confirm before use) -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
