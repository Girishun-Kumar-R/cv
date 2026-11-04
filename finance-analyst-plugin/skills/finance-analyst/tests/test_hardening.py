"""Regression tests for the 1.3.0 audit hardening (spec changelog 1.3.0).

Each test reproduces one class of defect found in a customer report audit and proves the plugin now
prevents it: validation-status contradiction, revenue-vs-budget basis mismatch, monthly ("January") profit
discrepancy, misleading profit labels, unsupported savings, leakage misclassification, mixing of evidence
classes, untraceable figures, Excel formula errors, and PDF/chart output.
"""
import csv
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from decimal import Decimal as D

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
SAMPLE = os.path.join(SKILL, "examples", "sample-sme")
sys.path.insert(0, os.path.join(SKILL, "scripts"))

import fa_render  # noqa: E402
import fa_run  # noqa: E402
import fa_verify  # noqa: E402
import fa_xlsx_audit  # noqa: E402

TB_COLS = ["period_label", "period_start", "period_end", "account_id", "account_name", "account_class",
           "opening_debit", "opening_credit", "period_debit", "period_credit", "closing_debit", "closing_credit"]


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)


def read_text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def tb_rows(label, start, end, accounts, opening, movements):
    """Trial balance rows; signed debit-positive opening and movement per account (must net to zero)."""
    assert sum(opening.values()) == 0 and sum(movements.values()) == 0, (label, movements)
    rows = []
    for aid, (name, cls) in accounts.items():
        o, m = D(opening.get(aid, 0)), D(movements.get(aid, 0))
        c = o + m
        rows.append({"period_label": label, "period_start": start, "period_end": end, "account_id": aid,
                     "account_name": name, "account_class": cls, "opening_debit": f"{max(o, D(0)):.2f}",
                     "opening_credit": f"{max(-o, D(0)):.2f}", "period_debit": f"{max(m, D(0)):.2f}",
                     "period_credit": f"{max(-m, D(0)):.2f}", "closing_debit": f"{max(c, D(0)):.2f}",
                     "closing_credit": f"{max(-c, D(0)):.2f}"})
    return rows


ACCOUNTS = {"4000": ("Sales", "revenue_from_operations"), "5000": ("Purchases", "purchases_of_stock_in_trade"),
            "6000": ("Salaries", "employee_benefits_expense"), "6100": ("Depreciation",
                                                                      "depreciation_and_amortisation"),
            "6300": ("Provision for income tax", "current_tax"), "1000": ("Plant", "property_plant_equipment"),
            "1300": ("Bank", "cash_and_cash_equivalents"), "2000": ("Capital", "share_capital"),
            "2500": ("Provision for tax", "short_term_provisions")}
MONTHS = [("2026-01", "2026-01-01", "2026-01-31", 1000000, 600000, 200000),
          ("2026-02", "2026-02-01", "2026-02-28", 1100000, 650000, 200000),
          ("2026-03", "2026-03-01", "2026-03-31", 1200000, 700000, 210000)]


def quarter_fixture(folder, tax=True, january_salary_extra=0):
    """Q4 FY2025-26 with three monthly trial balances that roll up exactly (unless january_salary_extra)."""
    os.makedirs(folder, exist_ok=True)
    opening = {"1000": 600000, "1300": 400000, "2000": -1000000}
    rows, bal = [], dict(opening)
    q = {k: 0 for k in ACCOUNTS}
    for label, start, end, sales, purchases, salaries in MONTHS:
        mv = {"4000": -sales, "5000": purchases, "6000": salaries, "6100": 50000, "1000": -50000}
        if tax:
            mv["6300"], mv["2500"] = 30000, -30000
        mv["1300"] = -(mv["4000"] + mv["5000"] + mv["6000"])
        for k, v in mv.items():
            q[k] += v
        month_mv = dict(mv)
        if label == "2026-01" and january_salary_extra:  # a January booking missing from the quarter ledger
            month_mv["6000"] += january_salary_extra
            month_mv["1300"] -= january_salary_extra
        rows += tb_rows(label, start, end, ACCOUNTS, bal, month_mv)
        bal = {k: bal.get(k, 0) + month_mv.get(k, 0) for k in ACCOUNTS}
    rows = tb_rows("Q4 FY2025-26", "2026-01-01", "2026-03-31", ACCOUNTS, opening, q) + rows
    with open(os.path.join(folder, "trial_balance.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=TB_COLS)
        w.writeheader()
        w.writerows(rows)
    write_json(os.path.join(folder, "run_config.json"), {
        "company_name": "Quarter Test Co (fictional)", "entity_id": "ENT-Q", "currency": "INR",
        "current_period": {"label": "Q4 FY2025-26", "start": "2026-01-01", "end": "2026-03-31"}})


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.data = os.path.join(self.tmp, "data")
        shutil.copytree(SAMPLE, self.data)
        self.out = os.path.join(self.tmp, "run")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def run_fa(self, data=None, narrative=None, formats=("md",), cfg=None, depth="comprehensive"):
        data = data or self.data
        with redirect_stdout(io.StringIO()):
            self.code = fa_run.run(data, cfg or os.path.join(data, "run_config.json"), self.out, narrative, depth,
                                   formats=formats, excel_libreoffice=False)
        self.reg = read_json(os.path.join(self.out, "calc_register.json"))
        self.ver = read_json(os.path.join(self.out, "verification.json"))
        self.issues = read_json(os.path.join(self.out, "issues.json"))
        self.report = read_text(os.path.join(self.out, "report.md"))
        return self.code

    def rec(self, metric, period=None, **dims):
        for r in self.reg:
            if r["metric_id"] == metric and (r["dimension"] or {}) == dims and (
                    period is None or r["period"]["label"] == period):
                return r
        raise KeyError((metric, period, dims))

    def status(self, check):
        return [c["status"] for c in self.ver["checks"] if c["id"] == check]

    def narrative(self, statement, refs, label="fact"):
        p = os.path.join(self.tmp, "n.json")
        write_json(p, {"findings": [{"statement": statement, "refs": refs, "label": label}]})
        return p

    def edit_csv(self, name, fn, folder=None):
        path = os.path.join(folder or self.data, name)
        with open(path, encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        cols = list(rows[0])
        cols = fn(rows) or cols
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)


class TestValidationStatus(Base):
    def test_status_line_separates_calculations_from_open_data_issues(self):
        self.run_fa()
        line = next(ln for ln in self.report.splitlines() if ln.startswith("**Status:"))
        self.assertIn("Calculations verified; open data issues, unresolved reconciliation exceptions and partial or "
                      "data-limited figures remain", line)
        self.assertIn("0 critical, 1 high, 3 medium, 0 low open issue(s) (1 informational); 3 unresolved "
                      "reconciliation exception(s); 3 partial, 0 blocked, 0 needs-data", line)
        self.assertNotIn("Verified by independent recomputation", self.report)  # the old contradictory stamp
        self.assertEqual(self.status("ver_status_consistency"), ["passed"])

    def test_failed_verification_never_says_verified(self):
        self.run_fa(narrative=self.narrative("Revenue was ₹1.18 crore.", ["metric:net_revenue"]))
        line = next(ln for ln in self.report.splitlines() if ln.startswith("**Status:"))
        self.assertTrue(line.startswith("**Status: NOT VERIFIED.**"))
        self.assertIn("VERIFICATION FAILED", line)
        self.assertNotIn("Calculations verified", line)

    def test_status_rule(self):
        z = {"issues": {k: 0 for k in ("critical", "high", "medium", "low", "informational")}, "exceptions": 0,
             "readiness": {"partial": 0, "blocked": 0, "needs_data": 0}}
        self.assertEqual(fa_verify.status_overall(z, "passed"), "Calculations verified; no open data issues or "
                                                                 "exceptions")
        z["issues"]["informational"] = 2
        self.assertIn("no open data issues", fa_verify.status_overall(z, "passed"))
        z["readiness"]["needs_data"] = 3  # e.g. optional datasets not supplied: not called "open issues"
        self.assertEqual(fa_verify.status_overall(z, "passed"),
                         "Calculations verified; partial or data-limited figures remain")
        z["exceptions"] = 1
        self.assertEqual(fa_verify.status_overall(z, "passed"), "Calculations verified; unresolved reconciliation "
                                                                 "exceptions and partial or data-limited figures remain")
        z["readiness"]["needs_data"], z["issues"]["high"] = 0, 1
        self.assertEqual(fa_verify.status_overall(z, "passed"), "Calculations verified; open data issues and "
                                                                 "unresolved reconciliation exceptions remain")
        z["readiness"]["blocked"] = 1  # blocked by a basis rule, not a critical issue
        self.assertEqual(fa_verify.status_overall(z, "passed"), "Calculations verified; some figures are blocked")
        z["issues"]["critical"] = 1
        self.assertIn("blocked by critical", fa_verify.status_overall(z, "passed_with_warnings"))
        self.assertEqual(fa_verify.status_overall(z, "failed"), "NOT VERIFIED")

    def test_tampered_status_counts_are_detected(self):
        self.run_fa()
        p = os.path.join(self.out, "report_draft.md")
        text = read_text(p).replace("1 high, 3 medium", "0 high, 0 medium")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
        res = fa_verify.verify(self.out, self.data, excel_libreoffice=False)
        self.assertEqual(next(c["status"] for c in res["checks"] if c["id"] == "ver_status_consistency"), "failed")


class TestBudgetBasis(Base):
    def test_revenue_budget_compared_with_net_revenue(self):
        self.run_fa()
        actual = self.rec("budget_variance", account_class="revenue_from_operations", measure="actual")
        self.assertEqual(D(actual["value"]), D(self.rec("net_revenue", "H1 FY2025-26")["value"]))
        self.assertEqual(actual["parameters"]["comparator_metric"], "net_revenue")
        self.assertEqual(D(self.rec("budget_variance", account_class="revenue_from_operations",
                                    measure="variance")["value"]), D("-700000"))
        self.assertIn("Revenue (net, as in P&L)", self.report)

    def test_declared_gross_basis_uses_gross_revenue(self):
        def f(rows):
            for r in rows:
                if r["account_class"] == "revenue_from_operations":
                    r["amount_basis"] = "gross_revenue"
        self.edit_csv("budget.csv", f)
        self.run_fa()
        self.assertEqual(D(self.rec("budget_variance", account_class="revenue_from_operations",
                                    measure="variance")["value"]), D("-500000"))
        self.assertEqual(self.ver["outcome"], "passed")

    def test_unstated_basis_is_disclosed_not_silent(self):
        def f(rows):
            for r in rows:
                del r["amount_basis"]
            return ["budget_version", "approval_status", "period_label", "account_class", "amount"]
        self.edit_csv("budget.csv", f)
        self.run_fa()
        r = self.rec("budget_variance", account_class="revenue_from_operations", measure="variance")
        self.assertEqual(r["readiness"], "partial")
        self.assertTrue(any("amount_basis not stated" in w for w in r["warnings"]))

    def test_tax_inclusive_budget_is_blocked(self):
        def f(rows):
            for r in rows:
                r["amount_basis"] = "tax_inclusive"
        self.edit_csv("budget.csv", f)
        self.run_fa()
        r = self.rec("budget_variance", account_class="revenue_from_operations", measure="variance")
        self.assertEqual((r["readiness"], r["value"]), ("blocked", None))


class TestMonthlyRollup(Base):
    def test_months_roll_up_to_the_period(self):
        q = os.path.join(self.tmp, "q")
        quarter_fixture(q)
        self.assertEqual(self.run_fa(data=q), 0)
        months = [D(self.rec("profit_before_tax", m[0])["value"]) for m in MONTHS]
        # Jan 10L-6L-2L-0.5L = 1.5L; Feb 11L-6.5L-2L-0.5L = 2L; Mar 12L-7L-2.1L-0.5L = 2.4L
        self.assertEqual(months, [D("150000"), D("200000"), D("240000")])
        self.assertEqual(sum(months), D(self.rec("profit_before_tax", "Q4 FY2025-26")["value"]))
        self.assertNotIn("ai_period_rollup", [i["check_id"] for i in self.issues])
        self.assertIn("## Monthly profit and loss", self.report)
        self.assertEqual(self.ver["outcome"], "passed")

    def test_january_discrepancy_is_caught_and_withheld(self):
        q = os.path.join(self.tmp, "q")
        quarter_fixture(q, january_salary_extra=40000)
        self.run_fa(data=q)
        roll = [i for i in self.issues if i["check_id"] == "ai_period_rollup"]
        self.assertEqual(len(roll), 1)
        self.assertEqual(roll[0]["severity"], "critical")
        self.assertTrue(any("account 6000" in e and "months sum to 650000" in e for e in roll[0]["evidence"]))
        self.assertTrue(any("2026-03 closing differs from Q4 FY2025-26 closing for account 6000" in e
                            for e in roll[0]["evidence"]))
        self.assertIsNone(self.rec("profit_before_tax", "2026-01")["value"])  # month withheld, not published
        self.assertEqual(self.rec("profit_before_tax", "Q4 FY2025-26")["readiness"], "ready")
        self.assertIn("Withheld: the sub-period trial balances do not reconcile", self.report)
        self.assertNotEqual(self.ver["outcome"], "failed")


class TestProfitLabels(Base):
    def test_no_tax_provision_means_no_net_profit_label(self):
        q = os.path.join(self.tmp, "q")
        quarter_fixture(q, tax=False)
        self.run_fa(data=q)
        npf = self.rec("net_profit", "Q4 FY2025-26")
        self.assertEqual((npf["readiness"], npf["value"]), ("needs_data", None))
        self.assertIn("| Profit before tax (no tax provision booked) |", self.report)
        self.assertNotIn("| Net profit |", self.report)
        self.assertEqual(self.status("ver_profit_labels"), ["passed"])

    def test_mislabelled_profit_is_rejected(self):
        self.run_fa(narrative=self.narrative("Net profit was {{metric:profit_before_tax}}.",
                                             ["metric:profit_before_tax"]))
        self.assertEqual(self.status("ver_profit_labels"), ["failed"])
        self.run_fa(narrative=self.narrative("Profit rose to {{metric:profit_before_tax}}.",
                                             ["metric:profit_before_tax"]))
        self.assertEqual(self.status("ver_profit_labels"), ["failed"])
        self.run_fa(narrative=self.narrative("Profit before tax rose to {{metric:profit_before_tax}}.",
                                             ["metric:profit_before_tax"]))
        self.assertEqual(self.status("ver_profit_labels"), ["passed"])

    def test_net_profit_claim_without_tax_provision_is_rejected(self):
        q = os.path.join(self.tmp, "q")
        quarter_fixture(q, tax=False)
        self.run_fa(data=q, narrative=self.narrative("Net profit improved to {{metric:profit_before_tax}}.",
                                                     ["metric:profit_before_tax"]))
        self.assertEqual(self.status("ver_profit_labels"), ["failed"])


class TestSavingsAndLeakage(Base):
    def test_reflex_never_calls_indicative_gaps_savings(self):
        self.run_fa()
        rx = read_json(os.path.join(self.out, "reflex.json"))
        texts = [i["text"] for inv in rx["investigations"] for i in inv["insights"]]
        texts += [" ".join([r["title"], r["rationale"], r["impact"]]) for r in rx["recommendations"]]
        self.assertFalse([t for t in texts if fa_verify.SAVINGS_RE.search(t)])
        cost = [r for r in rx["recommendations"] if r["rule_id"] == "rx_cost_category_spike"]
        self.assertTrue(cost and all(r["impact_basis"] == "indicative" and r["impact_level"] == "low" for r in cost))
        self.assertEqual(self.status("ver_savings_claims"), ["passed"])

    def test_unsupported_saving_claim_rejected_and_supported_one_accepted(self):
        self.run_fa(narrative=self.narrative(
            "Renegotiating could save {{metric:scn_cost_normalisation_saving[account_class=marketplace_fees]}}.",
            ["metric:scn_cost_normalisation_saving[account_class=marketplace_fees]"], "estimate"))
        self.assertEqual(self.status("ver_savings_claims"), ["failed"])
        self.run_fa(narrative=self.narrative(
            "The renewed contract would save {{input:₹40,000 a half-year|vendor quote dated 2026-10-01}} on "
            "marketplace fees.", ["metric:marketplace_fees[provider=all]"], "estimate"))
        self.assertEqual(self.status("ver_savings_claims"), ["passed"])

    def test_settlement_within_window_is_timing_not_leakage(self):
        self.run_fa()
        self.assertEqual(D(self.rec("settlement_variance", **{"class": "timing"})["value"]), D("246020"))
        self.assertEqual(D(self.rec("settlement_variance", **{"class": "unexplained"})["value"]), D("0"))
        rx = read_json(os.path.join(self.out, "reflex.json"))
        inv = next(i for i in rx["investigations"] if i["subject"] == "settlement:MA-SET-0003")
        self.assertEqual(inv["severity"], "low")
        self.assertTrue(any("timing difference" in i["text"] and "not a loss" in i["text"] for i in inv["insights"]))
        self.assertEqual(self.status("ver_leakage_classification"), ["passed"])

    def test_settlement_beyond_window_is_unexplained(self):
        cfg = read_json(os.path.join(self.data, "run_config.json"))
        cfg["reconciliation"]["settlement_to_bank_days"] = 2
        p = os.path.join(self.tmp, "cfg.json")
        write_json(p, cfg)
        self.run_fa(cfg=p)
        self.assertEqual(D(self.rec("settlement_variance", **{"class": "unexplained"})["value"]), D("246020"))
        rx = read_json(os.path.join(self.out, "reflex.json"))
        inv = next(i for i in rx["investigations"] if i["subject"] == "settlement:MA-SET-0003")
        self.assertEqual(inv["severity"], "high")
        self.assertTrue(any("may be leakage" in i["text"] for i in inv["insights"]))
        self.assertEqual(self.status("ver_leakage_classification"), ["passed"])

    def test_recoverable_items_called_leakage_are_rejected(self):
        self.run_fa(narrative=self.narrative("TCS withheld by the marketplace is revenue leakage of "
                                             "{{metric:rx_settlement_component[component=withholdings]}}.",
                                             ["metric:rx_settlement_component[component=withholdings]"]))
        self.assertEqual(self.status("ver_leakage_classification"), ["failed"])
        self.run_fa(narrative=self.narrative("Settlement leakage is {{metric:settlement_variance[class=timing]}}.",
                                             ["metric:settlement_variance[class=timing]"]))
        self.assertEqual(self.status("ver_leakage_classification"), ["failed"])

    def test_waterfall_marks_recoverable_credits(self):
        self.run_fa()
        spec = read_json(os.path.join(self.out, "charts", "rx-settlement-waterfall.json"))
        nature = {s["label"]: s["nature"] for s in spec["series"]}
        self.assertEqual(nature["GST on fees (credit)"], "recoverable_tax_credit")
        self.assertEqual(nature["TCS/TDS (tax credit)"], "recoverable_tax_credit")
        svg = read_text(os.path.join(self.out, "charts", "rx-settlement-waterfall.svg"))
        self.assertIn("#7A8CA3", svg)


class TestEvidenceAndTrace(Base):
    def test_sections_are_separated_and_exceptions_listed(self):
        self.run_fa()
        for h in fa_verify.EVIDENCE_HEADINGS:
            self.assertIn(h, self.report)
        sec = self.report.split("### Unresolved reconciliation exceptions", 1)[1].split("\n### ", 1)[0]
        for ident in ("GX-SET-0002", "MA-SET-0003", "CON-BANK-BOOK"):
            self.assertIn(ident, sec)
        verified = self.report.split("### Verified findings", 1)[1].split("\n### ", 1)[0]
        self.assertNotIn("Scenario", verified)
        self.assertEqual(self.status("ver_evidence_separation"), ["passed"])

    def test_scenario_stated_as_fact_is_rejected(self):
        self.run_fa(narrative=self.narrative("Cash is {{metric:scn_collect_overdue_cash}}.",
                                             ["metric:scn_collect_overdue_cash"], "fact"))
        self.assertEqual(self.status("ver_evidence_separation"), ["failed"])
        self.run_fa(narrative=self.narrative("If overdue receivables are collected, cash would be "
                                             "{{metric:scn_collect_overdue_cash}}.",
                                             ["metric:scn_collect_overdue_cash"], "estimate"))
        self.assertEqual(self.status("ver_evidence_separation"), ["passed"])

    def test_source_trace_and_tampering(self):
        self.run_fa()
        self.assertEqual(self.status("ver_source_trace"), ["passed"])
        self.assertEqual(self.rec("ar_aging", bucket="181_365")["parameters"]["source_rows"], [6])  # INV-0950
        self.assertIn("4000", self.rec("gross_revenue", "H1 FY2025-26")["parameters"]["source_accounts"])
        p = os.path.join(self.out, "calc_register.json")
        reg = read_json(p)
        for r in reg:
            if r["metric_id"] == "ar_aging" and r["dimension"] == {"bucket": "total"}:
                r["parameters"]["source_rows"] = r["parameters"]["source_rows"][:-1]
        write_json(p, reg)
        res = fa_verify.verify(self.out, self.data, excel_libreoffice=False)
        self.assertEqual(next(c["status"] for c in res["checks"] if c["id"] == "ver_source_trace"), "failed")


class TestDeliverables(Base):
    def test_excel_dashboard_formulas_validate(self):
        try:
            import openpyxl  # noqa: F401
        except ImportError:
            self.skipTest("openpyxl not installed")
        q = os.path.join(self.tmp, "q")
        quarter_fixture(q)
        self.run_fa(data=q, formats=("md", "xlsx"))
        self.assertEqual(self.status("ver_excel_formulas"), ["passed"])
        res = fa_xlsx_audit.audit(os.path.join(self.out, "dashboard.xlsx"), self.reg, use_libreoffice=False)
        self.assertGreater(res["mapped_checks"], 20)
        diffs = [c for c in res["cells"] if c["sheet"] == "P&L" and c["formula"].startswith("=") and "-" in
                 c["formula"] and c["cell"].startswith("G")]
        self.assertTrue(diffs and all(abs(c["value"]) < 1e-6 for c in diffs))  # months - period = 0

    @unittest.skipUnless(shutil.which("soffice") or shutil.which("libreoffice"), "LibreOffice not installed")
    def test_libreoffice_agrees_with_independent_evaluator(self):
        try:
            import openpyxl  # noqa: F401
        except ImportError:
            self.skipTest("openpyxl not installed (dashboard not generated)")
        self.run_fa(formats=("md", "xlsx"))
        res = fa_xlsx_audit.audit(os.path.join(self.out, "dashboard.xlsx"), self.reg, use_libreoffice=True)
        self.assertEqual(res["libreoffice"]["status"], "ok")
        self.assertGreater(res["libreoffice"]["compared"], 40)
        self.assertEqual(res["libreoffice"]["mismatches"], [])

    def test_wrong_month_reference_and_bad_values_are_caught(self):
        try:
            import openpyxl
        except ImportError:
            self.skipTest("openpyxl not installed")
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "P&L"
        ws.append(["Line", "Jan", "Feb", "Mar"])
        ws.append(["Revenue", 100, 110, 120])
        ws.append(["Costs", 60, 65, 70])
        ws.append(["Profit before tax", "=B2-C3", "=C2-C3", "=D2-D3"])  # January points at February's costs
        ws.append(["Check", "=B4/0", "=SUM(B4:D4)", "=E9"])
        path = os.path.join(self.tmp, "customer.xlsx")
        wb.save(path)
        res = fa_xlsx_audit.audit(path)
        self.assertEqual(res["status"], "failed")
        self.assertTrue(any(x["cell"] == "B4" for x in res["inconsistent_formulas"]))
        self.assertTrue(any("#DIV/0!" in p for p in res["problems"]))
        self.assertEqual(next(c["value"] for c in res["cells"] if c["cell"] == "B4"), 35.0)  # 100 - 65

    def test_html_and_pdf_layout(self):
        self.run_fa(formats=("md", "html", "pdf"))
        html_text = read_text(os.path.join(self.out, "report.html"))
        self.assertIn('<div class="status', html_text)
        self.assertIn("<svg", html_text)  # charts embedded as vectors
        self.assertNotIn("|---", html_text)  # every Markdown table converted
        self.assertIn("@page", html_text)
        if fa_render.find_browser():
            pdf = os.path.join(self.out, "report.pdf")
            self.assertTrue(os.path.isfile(pdf) and os.path.getsize(pdf) > 20000)
            with open(pdf, "rb") as fh:
                self.assertEqual(fh.read(5), b"%PDF-")

    def test_chart_text_is_readable(self):
        self.run_fa()
        svg = read_text(os.path.join(self.out, "charts", "rx-budget-variance.svg"))
        sizes = [float(x) for x in re.findall(r'font-size="([\d.]+)"', svg)]
        self.assertGreaterEqual(min(sizes), 10)
        self.assertIn("<tspan", svg)  # long category labels wrapped
        self.assertIn("₹50,000<", svg)  # whole rupees below one lakh in charts


if __name__ == "__main__":
    unittest.main()
