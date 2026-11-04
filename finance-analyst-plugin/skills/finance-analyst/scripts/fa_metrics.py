"""Deterministic metric engine (§13) for the subset of metrics implemented in v0.1.

Formulas follow metrics.registry in finance-analyst.yaml (formula_version 1.0).
Every value is written to the calculation register with inputs, readiness and
warnings. Missing inputs give needs_data; critical issues give blocked. No value
is ever estimated to fill a gap.
"""
from __future__ import annotations

import datetime as _dt
from collections import defaultdict
from decimal import Decimal

from fa_checks import blocked_and_partial_groups
from fa_common import (BORROWING_CLASSES, COST_OF_REVENUE_CLASSES, CURRENT_ASSET_CLASSES,
                       CURRENT_LIABILITY_CLASSES, EQUITY_CLASSES, EXPENSE_CLASSES, INCOME_CLASSES,
                       OPERATING_EXPENSE_CLASSES, TAX_CLASSES, TRADE_PAYABLE_CLASSES, ZERO, CalcRegister, safe_div)
from fa_data import input_ref, natural, oriented, tb_periods

IMPLEMENTED_METRICS = [
    "gross_revenue", "sales_returns_and_allowances", "net_revenue", "revenue_growth", "cogs", "gross_profit",
    "gross_margin", "operating_expenses", "expense_by_category", "cost_category_variance", "expense_growth",
    "cost_to_revenue_ratio", "ebitda", "ebitda_margin", "operating_profit", "operating_margin",
    "profit_before_tax", "net_profit", "net_margin", "effective_tax_rate", "period_over_period_variance",
    "cash_balance", "current_ratio", "quick_ratio", "working_capital", "accounts_receivable", "ar_aging",
    "accounts_payable", "ap_aging", "inventory_value", "inventory_turnover", "dso", "dpo", "dio",
    "cash_conversion_cycle", "outstanding_debt", "finance_costs", "interest_coverage_ratio", "debt_to_equity",
    "revenue_by_customer", "revenue_by_product", "revenue_by_channel", "customer_concentration",
    "budget_variance", "net_burn", "cash_runway", "marketplace_fees", "settlement_variance",
]
PNL_LINES = ["gross_revenue", "sales_returns_and_allowances", "net_revenue", "cogs", "gross_profit",
             "operating_expenses", "ebitda", "operating_profit", "profit_before_tax", "net_profit"]
AGING_BUCKETS = [("not_due", None, 0), ("1_30", 1, 30), ("31_60", 31, 60), ("61_90", 61, 90),
                 ("91_180", 91, 180), ("181_365", 181, 365), ("over_365", 366, None)]
DA = {"depreciation_and_amortisation"}
FIN = {"finance_costs"}
OTHER_SEP = {"exceptional_items", "prior_period_items", "foreign_exchange_loss_gain"}


def _d(iso):
    return _dt.date.fromisoformat(iso)


def nm(n, d, params=None):
    """Parameters with result_note=not_meaningful when the denominator is zero."""
    out = dict(params or {})
    if n is not None and d is not None and Decimal(d) == 0:
        out["result_note"] = "not_meaningful"
    return out or None


class Engine:
    def __init__(self, data, config, issues, reconciliation=None):
        self.data = data
        self.config = config
        self.reg = CalcRegister()
        self.periods = tb_periods(data)
        self.cur = config["current_period"]
        self.cmp = config.get("comparison_period")
        self.blocked, self.partial = blocked_and_partial_groups(issues)
        self.recon = reconciliation or {"rules": [], "conflicts": []}
        self.entity = config.get("entity_id")
        self.values = {}  # (metric_id, period_label, dim_key) -> Decimal | None

    # ------------------------------------------------------------------ utils
    def _status(self, groups, needs):
        """Readiness from dataset availability and issue groups."""
        missing = [f for f in needs if f not in self.data["datasets"]]
        if missing:
            return "needs_data", [f"needs {m}.csv" for m in missing]
        warn, readiness = [], "ready"
        for g in groups:
            if self.blocked.get(g):
                return "blocked", [f"blocked by critical issue(s) {', '.join(self.blocked[g])}"]
            if self.partial.get(g):
                readiness = "partial"
                warn.append(f"high-severity issue(s) {', '.join(self.partial[g])} on input data")
        return readiness, warn

    def _inputs(self, kinds):
        return [r for r in (input_ref(self.data, k) for k in kinds) if r]

    def _period(self, which):
        p = self.cur if which == "current" else self.cmp
        return {"label": p["label"], "start": p["start"], "end": p["end"]} if p else None

    def add(self, metric_id, value, unit, formula, kinds, which="current", readiness="ready", warnings=None,
            label="calculated", dimension=None, parameters=None, groups=None, basis="accrual"):
        st, w = self._status(groups if groups is not None else [], kinds)
        if st in ("needs_data", "blocked"):
            value, readiness = None, st
        elif st == "partial" and readiness == "ready":
            readiness = "partial"
        warnings = list(w) + list(warnings or [])
        if value is None and readiness in ("ready", "partial") and not (parameters or {}).get("result_note"):
            readiness = "needs_data"
            warnings.append("required input values are not available for this period")
        if readiness == "partial" and not warnings:
            warnings = ["partial inputs"]
        cid = self.reg.add(metric_id, value, unit, formula, self._inputs(kinds), self._period(which),
                           readiness=readiness, warnings=warnings, label=label, parameters=parameters,
                           dimension=dimension, basis=basis, entity=self.entity)
        key = (metric_id, self._period(which)["label"] if self._period(which) else None,
               tuple(sorted((dimension or {}).items())))
        self.values[key] = None if value is None else Decimal(value)
        return cid

    def get(self, metric_id, which="current", dimension=None):
        p = self._period(which)
        return self.values.get((metric_id, p["label"] if p else None, tuple(sorted((dimension or {}).items()))))

    def pl(self, label, classes):
        p = self.periods.get(label)
        if not p:
            return None, False
        total, found = ZERO, False
        for r in p["rows"]:
            if r.get("account_class") in classes:
                total += natural(r, "period")
                found = True
        return total, found

    def bal(self, label, classes, which="closing"):
        p = self.periods.get(label)
        if not p:
            return None, False
        total, found = ZERO, False
        for r in p["rows"]:
            if r.get("account_class") in classes:
                total += natural(r, which)
                found = True
        return total, found

    def days(self, which="current"):
        p = self._period(which)
        return Decimal((_d(p["end"]) - _d(p["start"])).days + 1)

    # ------------------------------------------------------------- P&L block
    def pnl(self, which):
        p = self._period(which)
        if not p:
            return
        label = p["label"]
        tb = ["trial_balance"]
        g = ["tb", "journals"]
        has_tb = label in self.periods
        if not has_tb and "trial_balance" in self.data["datasets"]:
            for m in PNL_LINES + ["gross_margin", "ebitda_margin", "operating_margin", "net_margin",
                                  "effective_tax_rate", "cost_to_revenue_ratio"]:
                self.reg.add(m, None, "money", "see metrics.registry", self._inputs(tb), p, readiness="needs_data",
                             warnings=[f"trial balance has no rows for period {label}"], entity=self.entity)
            return
        gross, _ = self.pl(label, {"revenue_from_operations"})
        returns, _ = self.pl(label, {"sales_returns_and_allowances"})
        oor, _ = self.pl(label, {"other_operating_revenue"})
        cogs, _ = self.pl(label, COST_OF_REVENUE_CLASSES)
        opex, _ = self.pl(label, OPERATING_EXPENSE_CLASSES)
        da, da_found = self.pl(label, DA)
        fin, _ = self.pl(label, FIN)
        other_inc, _ = self.pl(label, {"other_income"})
        sep, _ = self.pl(label, OTHER_SEP)
        tax, tax_found = self.pl(label, TAX_CLASSES)
        nr = None if gross is None else gross + oor - returns
        gp = None if nr is None else nr - cogs
        ebitda = None if gp is None else gp - opex
        op = None if ebitda is None else ebitda - da
        pbt = None if op is None else op + other_inc - fin - sep
        npf = None if pbt is None else pbt - tax
        no_da = not da_found or da == 0
        no_tax = not tax_found or tax == 0
        self.add("gross_revenue", gross, "money", "ledger(revenue_from_operations, period)", tb, which, groups=g)
        self.add("sales_returns_and_allowances", returns, "money", "ledger(sales_returns_and_allowances, period)",
                 tb, which, groups=g)
        self.add("net_revenue", nr, "money",
                 "gross_revenue + ledger(other_operating_revenue) - sales_returns_and_allowances", tb, which, groups=g)
        self.add("cogs", cogs, "money", "ledger(cost_of_revenue classes, period)", tb, which, groups=g)
        self.add("gross_profit", gp, "money", "net_revenue - cogs", tb, which, groups=g)
        self.add("gross_margin", safe_div(gp, nr), "percent", "gross_profit / net_revenue", tb, which, groups=g,
                 parameters=nm(gp, nr))
        self.add("operating_expenses", opex, "money", "ledger(operating expense classes, period)", tb, which,
                 groups=g)
        self.add("ebitda", ebitda, "money", "gross_profit - operating_expenses", tb, which, groups=g,
                 warnings=["Non-GAAP measure; other income excluded."])
        self.add("ebitda_margin", safe_div(ebitda, nr), "percent", "ebitda / net_revenue", tb, which, groups=g,
                 parameters=nm(ebitda, nr))
        self.add("operating_profit", op, "money", "ebitda - ledger(depreciation_and_amortisation)", tb, which,
                 groups=g, readiness="partial" if no_da else "ready",
                 warnings=["No depreciation/amortisation booked for the period; operating profit may be "
                           "overstated if depreciation is booked only at year end."] if no_da else None)
        self.add("operating_margin", safe_div(op, nr), "percent", "operating_profit / net_revenue", tb, which,
                 groups=g, readiness="partial" if no_da else "ready", parameters=nm(op, nr),
                 warnings=["Inherits operating_profit limitation."] if no_da else None)
        self.add("profit_before_tax", pbt, "money",
                 "operating_profit + other_income - finance_costs - (exceptional + prior_period + fx)", tb, which,
                 groups=g)
        self.add("net_profit", npf, "money", "profit_before_tax - tax expense", tb, which, groups=g,
                 readiness="partial" if no_tax else "ready",
                 warnings=["Tax provision not booked for the period; tax is never estimated."] if no_tax else None)
        self.add("net_margin", safe_div(npf, nr), "percent", "net_profit / net_revenue", tb, which, groups=g,
                 readiness="partial" if no_tax else "ready", parameters=nm(npf, nr))
        etr = safe_div(tax, pbt) if pbt is not None and pbt > 0 else None
        self.add("effective_tax_rate", etr, "percent", "tax expense / profit_before_tax", tb, which, groups=g,
                 parameters={"result_note": "not_meaningful"} if etr is None and pbt is not None else None,
                 warnings=["Book measure only; not a tax computation."])
        self.add("cost_to_revenue_ratio", safe_div(None if cogs is None else cogs + opex, nr), "percent",
                 "(cogs + operating_expenses) / net_revenue", tb, which, groups=g, parameters=nm(cogs, nr))
        p = self.periods[label]
        by_class = defaultdict(lambda: ZERO)
        for r in p["rows"]:
            if r.get("account_class") in EXPENSE_CLASSES - TAX_CLASSES:
                by_class[r["account_class"]] += natural(r, "period")
        for cls in sorted(by_class):
            if by_class[cls] != 0:
                self.add("expense_by_category", by_class[cls], "money", "group_by(ledger(expense classes), class)",
                         tb, which, groups=g, dimension={"account_class": cls})
        self._by_class = getattr(self, "_by_class", {})
        self._by_class[which] = dict(by_class)

    def comparisons(self):
        if not self.cmp:
            return
        tb = ["trial_balance"]
        g = ["tb", "journals"]
        params = {"comparison": self.cmp["label"]}
        for metric, base in (("revenue_growth", "net_revenue"), ("expense_growth", "operating_expenses")):
            c, b = self.get(base), self.get(base, "comparison")
            v = None if c is None or b is None or b == 0 else (c - b) / abs(b)
            self.add(metric, v, "percent", f"({base}[P] - {base}[C]) / abs({base}[C])", tb, groups=g,
                     parameters=dict(params, result_note="not_meaningful") if v is None and b == 0 else params)
        for line in PNL_LINES:
            c, b = self.get(line), self.get(line, "comparison")
            amt = None if c is None or b is None else c - b
            pct = None if amt is None or b == 0 else amt / abs(b)
            self.add("period_over_period_variance", amt, "money", f"{line}[P] - {line}[C]", tb, groups=g,
                     dimension={"line": line, "measure": "amount"}, parameters=params)
            self.add("period_over_period_variance", pct, "percent", f"({line}[P] - {line}[C]) / abs({line}[C])",
                     tb, groups=g, dimension={"line": line, "measure": "percent"}, parameters=nm(amt, b, params))
        cur = getattr(self, "_by_class", {}).get("current", {})
        prev = getattr(self, "_by_class", {}).get("comparison", {})
        for cls in sorted(set(cur) | set(prev)):
            a, b = cur.get(cls, ZERO), prev.get(cls, ZERO)
            self.add("cost_category_variance", a - b, "money", "actual_k[P] - actual_k[C]", tb, groups=g,
                     dimension={"account_class": cls, "measure": "amount"}, parameters=params)
            self.add("cost_category_variance", None if b == 0 else (a - b) / abs(b), "percent",
                     "(actual_k[P] - actual_k[C]) / abs(actual_k[C])", tb, groups=g,
                     dimension={"account_class": cls, "measure": "percent"},
                     parameters=dict(params, result_note="not_meaningful") if b == 0 else params)

    # ------------------------------------------------------- balance sheet block
    def balances(self):
        label = self.cur["label"]
        if label not in self.periods:
            return
        tb = ["trial_balance"]
        g = ["tb", "journals"]
        ca, _ = self.bal(label, CURRENT_ASSET_CLASSES)
        cl, _ = self.bal(label, CURRENT_LIABILITY_CLASSES)
        inv_c, inv_found = self.bal(label, {"inventories"})
        inv_o, _ = self.bal(label, {"inventories"}, "opening")
        pre, _ = self.bal(label, {"prepaid_expenses"})
        ar_c, _ = self.bal(label, {"trade_receivables"})
        ar_o, _ = self.bal(label, {"trade_receivables"}, "opening")
        ap_c, _ = self.bal(label, TRADE_PAYABLE_CLASSES)
        ap_o, _ = self.bal(label, TRADE_PAYABLE_CLASSES, "opening")
        debt, _ = self.bal(label, BORROWING_CLASSES)
        rows = self.periods[label]["rows"]

        def grp(classes, side):
            return sum((oriented(r, "closing", side) for r in rows if r.get("account_class") in classes), ZERO)
        # Equity incl. unappropriated current profit; contra accounts (drawings, returns) reduce their groups.
        equity_total = grp(EQUITY_CLASSES, "credit") + grp(INCOME_CLASSES, "credit") - grp(EXPENSE_CLASSES, "debit")
        self.add("accounts_receivable", ar_c, "money", "balance(trade_receivables, as_of)", tb, groups=g)
        self.add("accounts_payable", ap_c, "money", "balance(trade payable classes, as_of)", tb, groups=g)
        self.add("inventory_value", inv_c, "money", "balance(inventories, as_of)", tb, groups=g)
        self.add("working_capital", ca - cl, "money", "balance(current_assets) - balance(current_liabilities)", tb,
                 groups=g)
        self.add("working_capital", ar_c + inv_c - ap_c, "money",
                 "trade_receivables + inventories - trade_payables", tb, groups=g,
                 dimension={"variant": "operating"})
        self.add("current_ratio", safe_div(ca, cl), "ratio", "current_assets / current_liabilities", tb, groups=g,
                 parameters=nm(ca, cl))
        self.add("quick_ratio", safe_div(ca - inv_c - pre, cl), "ratio",
                 "(current_assets - inventories - prepaid_expenses) / current_liabilities", tb, groups=g,
                 parameters=nm(ca, cl))
        self.add("outstanding_debt", debt, "money", "balance(borrowing classes, as_of)", tb, groups=g)
        fin_v, _ = self.pl(label, FIN)
        self.add("finance_costs", fin_v, "money", "ledger(finance_costs, period)", tb, groups=g)
        op = self.get("operating_profit")
        icr = safe_div(op, fin_v) if fin_v else None
        self.add("interest_coverage_ratio", icr, "ratio", "operating_profit / finance_costs", tb, groups=g,
                 parameters={"result_note": "not_applicable"} if not fin_v else None)
        dte = safe_div(debt, equity_total) if equity_total > 0 else None
        self.add("debt_to_equity", dte, "ratio",
                 "outstanding_debt / (equity + unappropriated current profit)", tb, groups=g,
                 parameters={"result_note": "not_meaningful", "equity": format(equity_total, "f")}
                 if dte is None else {"equity": format(equity_total, "f")},
                 warnings=["Negative or zero net worth - raise risk, ratio not meaningful."]
                 if equity_total <= 0 else None)
        cogs = self.get("cogs")
        days = self.days()
        avg_inv = (inv_o + inv_c) / 2
        avg_ar = (ar_o + ar_c) / 2
        avg_ap = (ap_o + ap_c) / 2
        if inv_found:
            self.add("inventory_turnover", safe_div(cogs, avg_inv), "ratio", "cogs / avg_balance(inventories)", tb,
                     groups=g, parameters=nm(cogs, avg_inv))
            dio = None if safe_div(avg_inv, cogs) is None else safe_div(avg_inv, cogs) * days
            self.add("dio", dio, "days", "avg_balance(inventories) / cogs * days(period)", tb, groups=g,
                     parameters=nm(avg_inv, cogs))
        else:
            dio = ZERO
        sales = self.data["datasets"].get("sales_lines")
        if sales:
            s, e = _d(self.cur["start"]), _d(self.cur["end"])
            credit_sales = sum(((r.get("taxable_value") or ZERO) + (r.get("tax_amount") or ZERO)
                                for r in sales["rows"] if r.get("invoice_date") and s <= r["invoice_date"] <= e),
                               ZERO)
            dso_w, dso_r, kinds = ["Denominator: sales register value including GST (receivables include GST)."], \
                "ready", ["trial_balance", "sales_lines"]
        else:
            credit_sales = self.get("net_revenue")
            dso_w, dso_r, kinds = ["Alternative input: net revenue excluding GST used as denominator; DSO is "
                                   "overstated roughly by the tax share because receivables include GST."], \
                "partial", ["trial_balance"]
        dso = None if safe_div(avg_ar, credit_sales) is None else safe_div(avg_ar, credit_sales) * days
        self.add("dso", dso, "days", "avg_balance(trade_receivables) / credit_sales_incl_tax * days(period)", kinds,
                 groups=g + (["sales"] if sales else []), readiness=dso_r, warnings=dso_w,
                 parameters=nm(avg_ar, credit_sales, {"denominator": format(credit_sales, "f")
                                                      if credit_sales is not None else None,
                                                      "days": format(days, "f")}))
        cp = self.config.get("credit_purchases_incl_tax")
        if cp is not None:
            denom, dpo_r, dpo_w, dpo_label = Decimal(str(cp)), "ready", ["Denominator supplied by customer."], \
                "customer_provided"
        else:
            denom, dpo_r, dpo_label = cogs, "partial", "calculated"
            dpo_w = ["Alternative input: COGS used as denominator (payables include GST and non-inventory "
                     "purchases); provide credit purchases including GST for a ready DPO."]
        dpo = None if safe_div(avg_ap, denom) is None else safe_div(avg_ap, denom) * days
        self.add("dpo", dpo, "days", "avg_balance(trade_payables) / credit_purchases_incl_tax * days(period)", tb,
                 groups=g, readiness=dpo_r, warnings=dpo_w, label=dpo_label,
                 parameters=nm(avg_ap, denom, {"denominator": format(denom, "f") if denom is not None else None}))
        ccc = None if None in (dso, dpo, dio) else dio + dso - dpo
        self.add("cash_conversion_cycle", ccc, "days", "dio + dso - dpo", tb, groups=g,
                 readiness="partial" if "partial" in (dso_r, dpo_r) else "ready",
                 warnings=["Inherits DSO/DPO limitations."] if "partial" in (dso_r, dpo_r) else None)

    # --------------------------------------------------------------- cash block
    def cash(self):
        bank = self.data["datasets"].get("bank_transactions")
        end = _d(self.cur["end"])
        conflict = next((c for c in self.recon.get("conflicts", []) if c["conflict_id"] == "CON-BANK-BOOK"), None)
        if bank:
            latest = {}
            for r in bank["rows"]:
                if r.get("transaction_date") and r["transaction_date"] <= end and r.get("balance") is not None:
                    latest[r.get("bank_account_ref")] = r
            cash = sum((r["balance"] for r in latest.values()), ZERO)
            warn = []
            if conflict and conflict["status"] != "resolved":
                warn.append(f"Bank statement differs from book balance by {conflict['aligned_difference']}; "
                            f"bank figure used (requires bank reconciliation).")
            self.add("cash_balance", cash, "money", "sum(latest statement balance per account on/before as_of)",
                     ["bank_transactions"], groups=["bank"], label="reported", basis="cash", warnings=warn,
                     parameters={"accounts": sorted(str(k) for k in latest)})
        elif self.cur["label"] in self.periods:
            book, _ = self.bal(self.cur["label"], {"cash_and_cash_equivalents"})
            self.add("cash_balance", book, "money", "balance(cash_and_cash_equivalents) [book]", ["trial_balance"],
                     groups=["tb"], readiness="partial", label="derived", basis="cash",
                     warnings=["Book balance only; no bank statement provided to verify it."])
        else:
            self.add("cash_balance", None, "money", "bank statement balances", ["bank_transactions"])
        # net burn over trailing complete months ending at period end
        window = int(self.config.get("net_burn_window_months", 3))
        if not bank:
            self.add("net_burn", None, "money", "mean monthly net cash change", ["bank_transactions"], basis="cash")
            self.add("cash_runway", None, "months", "cash_balance / net_burn", ["bank_transactions"], basis="cash")
            return
        months = []
        y, m = end.year, end.month
        for _ in range(window):
            months.append((y, m))
            y, m = (y, m - 1) if m > 1 else (y - 1, 12)
        has_cat = "category" in bank["headers"] and any(r.get("category") for r in bank["rows"])
        net = {k: ZERO for k in months}
        covered = set()
        for r in bank["rows"]:
            d = r.get("transaction_date")
            if not d or (d.year, d.month) not in net:
                continue
            covered.add((d.year, d.month))
            if has_cat and (r.get("category") or "").lower() in {"financing", "transfer"}:
                continue
            net[(d.year, d.month)] += (r.get("credit") or ZERO) - (r.get("debit") or ZERO)
        earliest = min((r["transaction_date"] for r in bank["rows"] if r.get("transaction_date")), default=None)
        first_month_start = _dt.date(months[-1][0], months[-1][1], 1)
        warn, readiness = [], "ready"
        if not has_cat:
            readiness = "partial"
            warn.append("Bank lines are not categorised, so financing inflows/outflows are not excluded.")
        if earliest is None or earliest > first_month_start:
            readiness = "needs_data"
            warn.append(f"Bank data must start on or before {first_month_start} for a {window}-month window.")
        avg = sum(net.values(), ZERO) / Decimal(window)
        burn = (-avg if avg < 0 else ZERO) if readiness != "needs_data" else None
        self.add("net_burn", burn, "money", f"-mean(monthly net cash change, last {window} months) if negative",
                 ["bank_transactions"], groups=["bank"], readiness=readiness, warnings=warn, basis="cash",
                 parameters={"months": [f"{a}-{b:02d}" for a, b in sorted(months)],
                             "mean_monthly_net_change": format(avg, "f")})
        cash = self.get("cash_balance")
        if burn is None:
            runway, note = None, None
        elif burn == 0:
            runway, note = None, "not_applicable"
        else:
            runway, note = safe_div(cash, burn), None
        self.add("cash_runway", runway, "months", "cash_balance / net_burn", ["bank_transactions"], groups=["bank"],
                 readiness=readiness if readiness != "ready" else "ready", basis="cash",
                 warnings=(["Cash generative over the window; runway not applicable."] if note else []) + warn,
                 parameters={"result_note": note} if note else None)

    # ------------------------------------------------------------- aging block
    def aging(self):
        as_of = _d(self.cur["end"])
        for metric, kind, group, total_metric in (("ar_aging", "ar_open_items", "ar", "accounts_receivable"),
                                                  ("ap_aging", "ap_open_items", "ap", "accounts_payable")):
            ds = self.data["datasets"].get(kind)
            if not ds:
                self.add(metric, None, "money", "open items by days past due", [kind], groups=[group],
                         dimension={"bucket": "total"})
                continue
            buckets = {b[0]: ZERO for b in AGING_BUCKETS}
            no_due = 0
            for r in ds["rows"]:
                ref = r.get("due_date") or r.get("invoice_date") or r.get("bill_date")
                if r.get("due_date") is None:
                    no_due += 1
                amt = r.get("amount_outstanding") or ZERO
                age = (as_of - ref).days if ref else None
                for name, lo, hi in AGING_BUCKETS:
                    if age is None:
                        break
                    if (lo is None and age <= hi) or (lo is not None and age >= lo and (hi is None or age <= hi)):
                        buckets[name] += amt
                        break
            warn = [f"{no_due} item(s) without due date aged from document date."] if no_due else []
            for name, _, _ in AGING_BUCKETS:
                self.add(metric, buckets[name], "money", "sum(open balance where days past due in bucket)", [kind],
                         groups=[group], dimension={"bucket": name}, warnings=warn,
                         parameters={"as_of": self.cur["end"]})
            self.add(metric, sum(buckets.values(), ZERO), "money", "sum(all buckets)", [kind], groups=[group],
                     dimension={"bucket": "total"}, warnings=warn, parameters={"as_of": self.cur["end"]})

    # ------------------------------------------------------------- sales block
    def sales(self):
        ds = self.data["datasets"].get("sales_lines")
        if not ds:
            for m in ("revenue_by_customer", "revenue_by_product", "revenue_by_channel", "customer_concentration"):
                self.add(m, None, "money" if m != "customer_concentration" else "percent", "group_by(...)",
                         ["sales_lines"], groups=["sales"], dimension={"key": "all"})
            return
        s, e = _d(self.cur["start"]), _d(self.cur["end"])
        rows = [r for r in ds["rows"] if r.get("invoice_date") and s <= r["invoice_date"] <= e]
        conflict = next((c for c in self.recon.get("conflicts", []) if c["conflict_id"] == "CON-SALES-LEDGER"), None)
        warn = ["Gross invoiced value from the sales register (excl. GST); returns are not allocated to "
                "customers/products."]
        readiness = "ready"
        if conflict and conflict["status"] != "resolved":
            readiness = "partial"
            warn.append(f"Sales register differs from ledger revenue by {conflict['aligned_difference']}.")
        total = sum((r.get("taxable_value") or ZERO for r in rows), ZERO)
        for metric, field in (("revenue_by_customer", "customer_id"), ("revenue_by_product", "sku"),
                              ("revenue_by_channel", "channel")):
            agg = defaultdict(lambda: ZERO)
            names = {}
            for r in rows:
                k = r.get(field) or "unallocated"
                agg[k] += r.get("taxable_value") or ZERO
                if field == "customer_id" and r.get("customer_name"):
                    names[k] = r["customer_name"]
            for k in sorted(agg, key=lambda x: (-agg[x], x)):
                self.add(metric, agg[k], "money", f"group_by(sales register taxable value, {field})",
                         ["sales_lines"], groups=["sales"], readiness=readiness, warnings=warn,
                         dimension={field: k}, parameters={"name": names.get(k)} if names.get(k) else None)
            if field == "customer_id":
                ranked = sorted(agg.values(), reverse=True)
        for n in (1, 5, 10):
            share = safe_div(sum(ranked[:n], ZERO), total)
            self.add("customer_concentration", share, "percent", f"sum(top {n} customers) / total", ["sales_lines"],
                     groups=["sales"], readiness=readiness, warnings=warn, dimension={"measure": f"top_{n}_share"},
                     parameters=nm(total, total))
        hhi = None if total == 0 else sum(((v / total * 100) ** 2 for v in ranked), ZERO)
        self.add("customer_concentration", hhi, "index", "sum((100 * share_i)^2)", ["sales_lines"], groups=["sales"],
                 readiness=readiness, warnings=warn, dimension={"measure": "hhi"}, parameters=nm(total, total))

    # ------------------------------------------------------------ budget block
    def budget(self):
        ds = self.data["datasets"].get("budget")
        label = self.cur["label"]
        if not ds:
            self.add("budget_variance", None, "money", "actual - budget", ["budget"], groups=["budget"],
                     dimension={"account_class": "all", "measure": "variance"})
            return
        rows = [r for r in ds["rows"] if r.get("period_label") == label]
        if not rows:
            self.add("budget_variance", None, "money", "actual - budget", ["budget"], groups=["budget"],
                     dimension={"account_class": "all", "measure": "variance"},
                     warnings=[f"budget.csv has no lines for period {label}"])
            return
        unapproved = any((r.get("approval_status") or "").lower() != "approved" for r in rows)
        warn = ["Budget not marked approved - labelled 'unapproved budget'."] if unapproved else []
        readiness = "partial" if unapproved else "ready"
        for r in sorted(rows, key=lambda x: x.get("account_class") or ""):
            cls = r.get("account_class")
            actual, _ = self.pl(label, {cls})
            budget = r.get("amount")
            var = None if actual is None or budget is None else actual - budget
            pct = None if var is None or budget == 0 else var / abs(budget)
            fav = None
            if var is not None:
                fav = (var > 0) if cls in INCOME_CLASSES - {"sales_returns_and_allowances"} else (var < 0)
                fav = "favourable" if fav else ("neutral" if var == 0 else "unfavourable")
            kinds = ["trial_balance", "budget"]
            params = {"budget_version": r.get("budget_version"), "favourability": fav}
            pct_params = nm(var, budget, params)
            for measure, val, unit in (("actual", actual, "money"), ("budget", budget, "money"),
                                       ("variance", var, "money"), ("variance_pct", pct, "percent")):
                self.add("budget_variance", val, unit, "actual - budget; pct = variance / abs(budget)", kinds,
                         groups=["tb", "budget"], readiness=readiness, warnings=warn,
                         dimension={"account_class": cls, "measure": measure},
                         parameters=pct_params if measure == "variance_pct" else params)

    # -------------------------------------------------------- settlement block
    def settlements(self):
        ds = self.data["datasets"].get("settlements")
        if not ds:
            self.add("marketplace_fees", None, "money", "sum(settlement fees)", ["settlements"],
                     dimension={"provider": "all"})
            self.add("settlement_variance", None, "money", "expected - credited", ["settlements"])
            return
        s, e = _d(self.cur["start"]), _d(self.cur["end"])
        fees = defaultdict(lambda: ZERO)
        for r in ds["rows"]:
            if r.get("settlement_date") and s <= r["settlement_date"] <= e:
                fees[r.get("provider") or "unknown"] += r.get("fees") or ZERO
        for p in sorted(fees):
            self.add("marketplace_fees", fees[p], "money", "sum(settlement fee components excl. GST on fees)",
                     ["settlements"], groups=["settlements"], dimension={"provider": p},
                     warnings=["Statutory withholdings excluded (tax credits, not fees)."])
        self.add("marketplace_fees", sum(fees.values(), ZERO), "money", "sum over providers", ["settlements"],
                 groups=["settlements"], dimension={"provider": "all"})
        rule = next((x for x in self.recon.get("rules", []) if x["rule_id"] == "rec_settlement_to_bank"), None)
        if not rule or rule["status"] != "completed":
            self.add("settlement_variance", None, "money", "expected net - bank credited",
                     ["settlements", "bank_transactions"], groups=["settlements", "bank"])
            return
        total = ZERO
        for rec in rule["records"]:
            if rec["match_status"] == "unmatched":
                total += rec["expected_net"] or ZERO
            elif rec["difference"] is not None:
                total += -(rec["difference"])
        self.add("settlement_variance", total, "money",
                 "sum(expected net - bank credited); unmatched settlements count in full",
                 ["settlements", "bank_transactions"], groups=["settlements", "bank"],
                 readiness="partial" if rule["summary"]["by_status"].get("probable_match") else "ready",
                 warnings=["Unmatched settlements may be in transit or missing; a non-zero variance is a lead "
                           "for review, not proof of platform error."] +
                          (["Includes probable (not confirmed) matches."]
                           if rule["summary"]["by_status"].get("probable_match") else []))

    def run(self):
        self.pnl("current")
        if self.cmp:
            self.pnl("comparison")
        self.comparisons()
        self.balances()
        self.cash()
        self.aging()
        self.sales()
        self.budget()
        self.settlements()
        return self.reg


def material(var, base, revenue, mat):
    if var is None:
        return False
    floor = Decimal(str(mat.get("absolute_floor_inr", "25000")))
    rel = Decimal(str(mat.get("relative_threshold", "0.10")))
    share = Decimal(str(mat.get("revenue_share_floor", "0.005")))
    tests = [abs(var) >= floor, base is not None and base != 0 and abs(var) >= rel * abs(base),
             revenue is not None and abs(var) >= share * abs(revenue)]
    return sum(tests) >= 2


def signals(reg, config):
    """Deterministic observations for Claude's analysis (no judgement thresholds beyond materiality)."""
    out = []
    mat = config.get("materiality", {})
    nr = reg.find("net_revenue", config["current_period"]["label"])
    revenue = Decimal(nr["value"]) if nr and nr["value"] is not None else None
    if config.get("comparison_period"):
        for r in reg.records:
            if r["metric_id"] != "period_over_period_variance" or (r["dimension"] or {}).get("measure") != "amount":
                continue
            line = r["dimension"]["line"]
            base = reg.find(line, config["comparison_period"]["label"])
            var = None if r["value"] is None else Decimal(r["value"])
            b = None if not base or base["value"] is None else Decimal(base["value"])
            if material(var, b, revenue, mat):
                out.append({"type": "material_movement", "metric_id": line, "calc_ids": [r["calc_id"]],
                            "direction": "increase" if var > 0 else "decrease"})
    over90 = [r for r in reg.records if r["metric_id"] == "ar_aging"
              and (r["dimension"] or {}).get("bucket") in {"91_180", "181_365", "over_365"} and r["value"]
              and Decimal(r["value"]) != 0]
    if over90:
        out.append({"type": "receivables_over_90_days", "metric_id": "ar_aging",
                    "calc_ids": [r["calc_id"] for r in over90]})
    for r in reg.records:
        if r["readiness"] in ("partial", "needs_data", "blocked"):
            out.append({"type": f"readiness_{r['readiness']}", "metric_id": r["metric_id"], "calc_ids": [r["calc_id"]],
                        "dimension": r["dimension"]})
    return out
