"""Shared helpers for the Finance Analyst toolkit.

Standard library only (Python 3.8+). Money is always decimal.Decimal; binary
floats are never used for money, equality tests or tolerances.
"""
from __future__ import annotations

import csv
import datetime as _dt
import hashlib
import json
import os
import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, getcontext

getcontext().prec = 34

SPEC_FILE_NAME = "finance-analyst.yaml"
TOOLKIT_VERSION = "0.2.0"
FORMULA_VERSION = "1.0"
ZERO = Decimal("0")
PAISA = Decimal("0.01")

# --------------------------------------------------------------------------
# Canonical account classes (mirror of canonical_data_model.account_classes
# in finance-analyst.yaml; fa_spec.py verifies they stay identical).
# --------------------------------------------------------------------------
ACCOUNT_CLASSES = {
    "assets": {
        "non_current": ["property_plant_equipment", "capital_work_in_progress", "intangible_assets",
                        "non_current_investments", "long_term_loans_and_advances", "deferred_tax_assets",
                        "other_non_current_assets"],
        "current": ["inventories", "trade_receivables", "cash_and_cash_equivalents", "other_bank_balances",
                    "current_investments", "short_term_loans_and_advances", "gst_input_credit_receivable",
                    "tds_tcs_receivable", "prepaid_expenses", "other_current_assets"],
    },
    "liabilities": {
        "non_current": ["long_term_borrowings", "deferred_tax_liabilities", "other_long_term_liabilities",
                        "long_term_provisions"],
        "current": ["short_term_borrowings", "current_maturities_of_long_term_debt", "trade_payables_msme",
                    "trade_payables_others", "gst_payable", "tds_payable", "other_statutory_dues",
                    "advances_from_customers", "other_current_liabilities", "short_term_provisions"],
    },
    "equity": ["share_capital", "reserves_and_surplus", "retained_earnings", "partners_capital_accounts",
               "proprietor_capital", "drawings"],
    "income": ["revenue_from_operations", "sales_returns_and_allowances", "other_operating_revenue",
               "other_income"],
    "expenses": {
        "cost_of_revenue": ["cost_of_materials_consumed", "purchases_of_stock_in_trade", "changes_in_inventories",
                            "direct_expenses", "freight_inward", "subcontracting"],
        "operating": ["employee_benefits_expense", "selling_and_marketing", "advertising", "marketplace_fees",
                      "payment_gateway_fees", "logistics_and_shipping", "rent", "utilities", "professional_fees",
                      "technology_and_software", "travel", "repairs_and_maintenance", "insurance",
                      "bad_debts_and_provisions", "office_and_admin", "miscellaneous_operating"],
        "separately_reported": ["depreciation_and_amortisation", "finance_costs", "exceptional_items",
                                "prior_period_items", "foreign_exchange_loss_gain"],
        "tax": ["current_tax", "deferred_tax"],
    },
    "special": ["suspense", "unclassified", "intercompany", "inter_branch"],
}


def _flatten(node):
    if isinstance(node, list):
        return list(node)
    out = []
    for v in node.values():
        out.extend(_flatten(v))
    return out


ASSET_CLASSES = set(_flatten(ACCOUNT_CLASSES["assets"]))
CURRENT_ASSET_CLASSES = set(ACCOUNT_CLASSES["assets"]["current"])
LIABILITY_CLASSES = set(_flatten(ACCOUNT_CLASSES["liabilities"]))
CURRENT_LIABILITY_CLASSES = set(ACCOUNT_CLASSES["liabilities"]["current"])
EQUITY_CLASSES = set(ACCOUNT_CLASSES["equity"])
INCOME_CLASSES = set(ACCOUNT_CLASSES["income"])
EXPENSE_CLASSES = set(_flatten(ACCOUNT_CLASSES["expenses"]))
COST_OF_REVENUE_CLASSES = set(ACCOUNT_CLASSES["expenses"]["cost_of_revenue"])
OPERATING_EXPENSE_CLASSES = set(ACCOUNT_CLASSES["expenses"]["operating"])
TAX_CLASSES = set(ACCOUNT_CLASSES["expenses"]["tax"])
SPECIAL_CLASSES = set(ACCOUNT_CLASSES["special"])
ALL_CLASSES = ASSET_CLASSES | LIABILITY_CLASSES | EQUITY_CLASSES | INCOME_CLASSES | EXPENSE_CLASSES | SPECIAL_CLASSES
PNL_CLASSES = INCOME_CLASSES | EXPENSE_CLASSES
BORROWING_CLASSES = {"long_term_borrowings", "short_term_borrowings", "current_maturities_of_long_term_debt"}
TRADE_PAYABLE_CLASSES = {"trade_payables_msme", "trade_payables_others"}
# Contra classes keep their own normal balance (debit) although they sit under income/equity.
DEBIT_NORMAL_CONTRA = {"sales_returns_and_allowances", "drawings"}


def normal_side(account_class: str) -> str:
    """Return 'debit' or 'credit' for the class's normal balance."""
    if account_class in DEBIT_NORMAL_CONTRA:
        return "debit"
    if account_class in ASSET_CLASSES or account_class in EXPENSE_CLASSES:
        return "debit"
    if account_class in LIABILITY_CLASSES or account_class in EQUITY_CLASSES or account_class in INCOME_CLASSES:
        return "credit"
    return "debit"  # special classes: shown as signed debit balance


# --------------------------------------------------------------------------
# Canonical input templates (file-import fallback and connector output target)
# --------------------------------------------------------------------------
TEMPLATES = {
    "trial_balance": {
        "file": "trial_balance.csv",
        "columns": {"period_label": "str", "period_start": "date", "period_end": "date", "account_id": "str",
                    "account_name": "str", "account_class": "class", "opening_debit": "dec", "opening_credit": "dec",
                    "period_debit": "dec", "period_credit": "dec", "closing_debit": "dec", "closing_credit": "dec"},
        "required": ["period_label", "period_start", "period_end", "account_id", "account_name", "account_class",
                     "opening_debit", "opening_credit", "period_debit", "period_credit", "closing_debit",
                     "closing_credit"],
    },
    "bank_transactions": {
        "file": "bank_transactions.csv",
        "columns": {"bank_account_ref": "str", "transaction_date": "date", "value_date": "date", "narration": "str",
                    "reference": "str", "debit": "dec", "credit": "dec", "balance": "dec", "currency": "str",
                    "category": "str"},
        "required": ["bank_account_ref", "transaction_date", "narration", "debit", "credit", "balance"],
    },
    "ar_open_items": {
        "file": "ar_open_items.csv",
        "columns": {"customer_id": "str", "customer_name": "str", "customer_gstin": "str", "invoice_number": "str",
                    "invoice_date": "date", "due_date": "date", "amount_outstanding": "dec", "currency": "str"},
        "required": ["customer_id", "invoice_number", "invoice_date", "amount_outstanding"],
    },
    "ap_open_items": {
        "file": "ap_open_items.csv",
        "columns": {"supplier_id": "str", "supplier_name": "str", "supplier_gstin": "str",
                    "msme_classification": "str", "bill_number": "str", "bill_date": "date", "due_date": "date",
                    "amount_outstanding": "dec", "currency": "str"},
        "required": ["supplier_id", "bill_number", "bill_date", "amount_outstanding"],
    },
    "sales_lines": {
        "file": "sales_lines.csv",
        "columns": {"invoice_number": "str", "invoice_date": "date", "customer_id": "str", "customer_name": "str",
                    "sku": "str", "channel": "str", "quantity": "dec", "taxable_value": "dec", "tax_amount": "dec",
                    "currency": "str"},
        "required": ["invoice_number", "invoice_date", "customer_id", "taxable_value", "tax_amount"],
    },
    "budget": {
        "file": "budget.csv",
        "columns": {"budget_version": "str", "approval_status": "str", "period_label": "str",
                    "account_class": "class", "amount": "dec"},
        "required": ["budget_version", "approval_status", "period_label", "account_class", "amount"],
    },
    "settlements": {
        "file": "settlements.csv",
        "columns": {"provider": "str", "settlement_id": "str", "settlement_date": "date", "gross_amount": "dec",
                    "fees": "dec", "tax_on_fees": "dec", "refunds": "dec", "withholdings": "dec",
                    "adjustments": "dec", "net_amount": "dec", "bank_reference": "str", "currency": "str"},
        "required": ["provider", "settlement_id", "settlement_date", "gross_amount", "fees", "net_amount"],
    },
    "journal_lines": {
        "file": "journal_lines.csv",
        "columns": {"journal_id": "str", "posting_date": "date", "account_id": "str", "debit": "dec",
                    "credit": "dec", "narration": "str"},
        "required": ["journal_id", "posting_date", "account_id", "debit", "credit"],
    },
}

# --------------------------------------------------------------------------
# Language rules shared with the spec (communication / accounting_integrity)
# --------------------------------------------------------------------------
PROHIBITED_PHRASES = ["You are GST compliant.", "Your returns are correct.", "Ready to file.",
                      "Audit-ready (as an assurance claim)."]
PROHIBITED_PATTERNS = [r"\byou are (fully )?gst[- ]compliant\b", r"\byour returns are correct\b",
                       r"\bready to file\b", r"\baudit[- ]ready\b", r"\bguaranteed\b", r"\brisk[- ]free\b"]
STANDARD_DISCLAIMER = (
    "This analysis is prepared from the data you authorised and provided, using documented methods. "
    "It is decision support, not an audit, review, tax, legal or investment opinion. Figures labelled "
    "estimate, forecast or hypothesis carry uncertainty. Please review material decisions, tax matters and "
    "statutory filings with your Chartered Accountant or other qualified adviser."
)


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------
_CURRENCY_TOKENS = re.compile(r"(₹|INR|Rs\.?|rs\.?)", re.IGNORECASE)


def parse_amount(raw, allow_blank=True):
    """Parse a money/quantity string into Decimal.

    Handles Indian and international grouping ('1,23,456.78'), currency symbols,
    parentheses or trailing minus negatives, unicode minus, and Dr/Cr suffixes
    (Dr -> positive, Cr -> negative; i.e. debit-positive convention).
    Returns None for blank input when allow_blank is True.
    """
    if raw is None:
        if allow_blank:
            return None
        raise ValueError("blank amount")
    if isinstance(raw, Decimal):
        return raw
    if isinstance(raw, int):
        return Decimal(raw)
    if isinstance(raw, float):
        raise TypeError("binary float is not accepted for money; pass a string")
    s = str(raw).strip()
    if s == "" or s in {"-", "--"}:
        if allow_blank:
            return None
        raise ValueError("blank amount")
    sign = 1
    s = s.replace("−", "-").replace(" ", " ")
    m = re.search(r"\b(dr|cr)\.?\s*$", s, re.IGNORECASE)
    if m:
        if m.group(1).lower() == "cr":
            sign = -sign
        s = s[: m.start()].strip()
    s = _CURRENCY_TOKENS.sub("", s).strip()
    if s.startswith("(") and s.endswith(")"):
        sign = -sign
        s = s[1:-1].strip()
    if s.endswith("-") and not s.startswith("-"):
        sign = -sign
        s = s[:-1].strip()
    s = s.replace(",", "").replace(" ", "")
    if not re.fullmatch(r"[-+]?\d+(\.\d+)?", s):
        raise ValueError(f"not a number: {raw!r}")
    try:
        value = Decimal(s)
    except InvalidOperation as exc:  # pragma: no cover - guarded by regex
        raise ValueError(f"not a number: {raw!r}") from exc
    return value * sign


_MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct",
                                       "nov", "dec"], start=1)}


def parse_date(raw, dayfirst=True):
    """Parse common date strings; day-first by default (Indian sources)."""
    if raw is None:
        return None
    if isinstance(raw, _dt.date):
        return raw
    s = str(raw).strip()
    if s == "":
        return None
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})(?:[T ].*)?", s)
    if m:
        return _dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.fullmatch(r"(\d{4})/(\d{1,2})/(\d{1,2})", s)
    if m:
        return _dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.fullmatch(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})", s)
    if m:
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y += 2000
        day, month = (a, b) if dayfirst else (b, a)
        return _dt.date(y, month, day)
    m = re.fullmatch(r"(\d{1,2})[- ]([A-Za-z]{3})[A-Za-z]*[- ,]+(\d{2,4})", s)
    if m:
        y = int(m.group(3))
        if y < 100:
            y += 2000
        return _dt.date(y, _MONTHS[m.group(2).lower()], int(m.group(1)))
    raise ValueError(f"unrecognised date: {raw!r}")


def is_ambiguous_dayfirst(raw) -> bool:
    """True when a dd/mm vs mm/dd string could be read both ways."""
    m = re.fullmatch(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})", str(raw).strip())
    return bool(m) and int(m.group(1)) <= 12 and int(m.group(2)) <= 12 and m.group(1) != m.group(2)


def dec(value):
    """Decimal from a canonical CSV cell (blank -> None)."""
    return parse_amount(value, allow_blank=True)


def dec0(value):
    v = dec(value)
    return ZERO if v is None else v


# --------------------------------------------------------------------------
# Formatting (presentation only; calculations never use formatted values)
# --------------------------------------------------------------------------

def quantize(value: Decimal, places: str = "0.01") -> Decimal:
    return value.quantize(Decimal(places), rounding=ROUND_HALF_UP)


def indian_group(int_digits: str) -> str:
    if len(int_digits) <= 3:
        return int_digits
    head, tail = int_digits[:-3], int_digits[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return ",".join(parts + [tail])


def _group_number(value: Decimal, decimals: int) -> str:
    q = quantize(abs(value), "1" if decimals == 0 else "0." + "0" * decimals)
    text = format(q, "f")
    if "." in text:
        int_part, frac = text.split(".")
        return indian_group(int_part) + "." + frac
    return indian_group(text)


SCALE_FACTORS = {"units": Decimal("1"), "thousands": Decimal("1000"), "lakhs": Decimal("100000"),
                 "crores": Decimal("10000000")}
SCALE_LABELS = {"units": "₹", "thousands": "₹ in thousands", "lakhs": "₹ in lakhs", "crores": "₹ in crores"}


def choose_scale(values) -> str:
    """metadata.defaults.number_format.auto_scale_rule (largest figure picks lakhs/crores), plus one
    implementation rule: step down a level when a non-zero line would show below 0.10 in that scale,
    so small lines are not hidden as 0.00."""
    vals = [abs(v) for v in values if v is not None]
    if not vals:
        return "units"
    biggest = max(vals)
    if biggest >= Decimal("10000000"):
        scale = "crores"
    elif biggest >= Decimal("100000"):
        scale = "lakhs"
    else:
        return "units"
    order = ["units", "lakhs", "crores"]
    while scale != "units" and any(0 < v < SCALE_FACTORS[scale] / 10 for v in vals):
        scale = order[order.index(scale) - 1]
    return scale


def fmt_money(value, mode="narrative", scale="units", negative="minus"):
    """Format INR. mode='narrative' -> '₹12.35 lakh'; mode='table' -> number in the given scale."""
    if value is None:
        return "n/a"
    value = Decimal(value)
    neg = value < 0
    if mode == "table":
        factor = SCALE_FACTORS[scale]
        body = _group_number(value / factor, 2)
        if neg:
            return f"({body})" if negative == "parentheses" else f"-{body}"
        return body
    a = abs(value)
    if a >= Decimal("10000000"):
        body = f"₹{_group_number(a / Decimal('10000000'), 2)} crore"
    elif a >= Decimal("100000"):
        body = f"₹{_group_number(a / Decimal('100000'), 2)} lakh"
    else:
        body = f"₹{_group_number(a, 2)}"
    return f"-{body}" if neg else body


def fmt_value(value, unit, mode="narrative", scale="units"):
    if value is None:
        return "n/a"
    value = Decimal(value)
    if unit == "money":
        return fmt_money(value, mode=mode, scale=scale, negative="parentheses" if mode == "table" else "minus")
    if unit == "percent":
        return f"{quantize(value * 100, '0.1')}%"
    if unit == "ratio":
        return f"{quantize(value, '0.01')}"
    if unit == "days":
        return f"{quantize(value, '1')} days"
    if unit == "months":
        return f"{quantize(value, '0.1')} months"
    if unit == "count":
        return indian_group(str(int(quantize(value, '1'))))
    if unit == "index":
        return f"{quantize(value, '1')}"
    return str(value)


# --------------------------------------------------------------------------
# Files
# --------------------------------------------------------------------------

def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        rows = []
        for row in reader:
            rows.append({(k or "").strip(): (v.strip() if isinstance(v, str) else v) for k, v in row.items()})
        return rows, [h.strip() for h in (reader.fieldnames or [])]


def write_csv(path, rows, columns):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def json_default(obj):
    if isinstance(obj, Decimal):
        return format(obj, "f")
    if isinstance(obj, (_dt.date, _dt.datetime)):
        return obj.isoformat()
    if isinstance(obj, set):
        return sorted(obj)
    raise TypeError(f"not serialisable: {type(obj)}")


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False, default=json_default)
        fh.write("\n")


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def skill_dir() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def spec_path() -> str:
    return os.path.join(skill_dir(), SPEC_FILE_NAME)


def now_ist() -> str:
    ist = _dt.timezone(_dt.timedelta(hours=5, minutes=30))
    return _dt.datetime.now(ist).replace(microsecond=0).isoformat()


# --------------------------------------------------------------------------
# GSTIN structure (accounting_integrity.checks.ai_gstin_structure)
# --------------------------------------------------------------------------
_GSTIN_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z][A-Z0-9][0-9A-Z]$")


def gstin_check_char(first14: str) -> str:
    total = 0
    for i, ch in enumerate(first14):
        product = _GSTIN_CHARS.index(ch) * (2 if i % 2 else 1)
        total += product // 36 + product % 36
    return _GSTIN_CHARS[(36 - total % 36) % 36]


def validate_gstin(gstin: str):
    """Return (ok, reason). Structure + check character per the published algorithm."""
    g = (gstin or "").strip().upper()
    if len(g) != 15:
        return False, "length is not 15"
    if not _GSTIN_RE.match(g):
        return False, "pattern mismatch (state code, PAN, entity code, check character)"
    if not (1 <= int(g[:2]) <= 38 or g[:2] in {"97", "99"}):
        return False, "state code out of range"
    if gstin_check_char(g[:14]) != g[14]:
        return False, "check character mismatch"
    return True, "ok"


# --------------------------------------------------------------------------
# Calculation register (evidence_and_audit.calculation_record)
# --------------------------------------------------------------------------
class CalcRegister:
    def __init__(self):
        self.records = []

    def add(self, metric_id, value, unit, formula, inputs, period, readiness="ready", warnings=None,
            label="calculated", parameters=None, dimension=None, basis="accrual", entity=None):
        calc_id = f"CALC-{len(self.records) + 1:04d}"
        rec = {
            "calc_id": calc_id,
            "metric_id": metric_id,
            "formula_version": FORMULA_VERSION,
            "formula_text": formula,
            "inputs": inputs,
            "parameters": parameters or {},
            "period": period,
            "entity_scope": entity,
            "dimension": dimension,
            "basis": basis,
            "value": None if value is None else format(Decimal(value), "f"),
            "unit": unit,
            "readiness": readiness,
            "label": label,
            "warnings": warnings or [],
        }
        self.records.append(rec)
        return calc_id

    def find(self, metric_id, period=None, dimension=None):
        for r in self.records:
            if r["metric_id"] != metric_id:
                continue
            if period is not None and (r["period"] or {}).get("label") != period:
                continue
            if dimension is None and r["dimension"] is not None:
                continue
            if dimension is not None and r["dimension"] != dimension:
                continue
            return r
        return None


def safe_div(n, d):
    if n is None or d is None or d == 0:
        return None
    return Decimal(n) / Decimal(d)
