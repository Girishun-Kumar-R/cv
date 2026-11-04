"""Acceptance tests for the Finance Analyst toolkit (standard library unittest).

Run from the skill directory:  python3 -m unittest discover -s tests -v
Golden values for the synthetic sample were computed by hand (see comments).
"""
import csv
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from decimal import ROUND_HALF_UP, Decimal as D

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
SCRIPTS = os.path.join(SKILL, "scripts")
SAMPLE = os.path.join(SKILL, "examples", "sample-sme")
sys.path.insert(0, SCRIPTS)

import fa_classify  # noqa: E402
import fa_normalize  # noqa: E402
import fa_run  # noqa: E402
import fa_spec  # noqa: E402
import fa_verify  # noqa: E402
from fa_common import fmt_money, indian_group, parse_amount, parse_date, validate_gstin  # noqa: E402

CUR, CMP = "H1 FY2025-26", "H1 FY2024-25"


def read_text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def read_rows(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def run_pipeline(input_dir, out_dir, narrative=None, depth="comprehensive", config=None):
    with redirect_stdout(io.StringIO()):
        code = fa_run.run(input_dir, config or os.path.join(input_dir, "run_config.json"), out_dir, narrative, depth)
    def load(name):
        with open(os.path.join(out_dir, name), encoding="utf-8") as fh:
            return json.load(fh)
    return code, load


def value(register, metric, period=CUR, **dims):
    for r in register:
        if r["metric_id"] == metric and r["period"]["label"] == period and (r["dimension"] or {}) == dims:
            return r
    raise KeyError((metric, period, dims))


class TestParsing(unittest.TestCase):
    def test_amounts(self):
        self.assertEqual(parse_amount("1,23,456.78"), D("123456.78"))
        self.assertEqual(parse_amount("(1,000.00)"), D("-1000.00"))
        self.assertEqual(parse_amount("5,000.00 Cr"), D("-5000.00"))
        self.assertEqual(parse_amount("₹ 2,500.50 Dr"), D("2500.50"))
        self.assertEqual(parse_amount("Rs. 100-"), D("-100"))
        self.assertIsNone(parse_amount(""))
        with self.assertRaises(ValueError):
            parse_amount("12abc")
        with self.assertRaises(TypeError):
            parse_amount(0.1)

    def test_dates(self):
        self.assertEqual(parse_date("05/04/2025").isoformat(), "2025-04-05")
        self.assertEqual(parse_date("31-Mar-2026").isoformat(), "2026-03-31")
        self.assertEqual(parse_date("2025-09-30").isoformat(), "2025-09-30")

    def test_indian_formatting(self):
        self.assertEqual(indian_group("123456789"), "12,34,56,789")
        self.assertEqual(fmt_money(D("12345678.90")), "₹1.23 crore")
        self.assertEqual(fmt_money(D("1087500")), "₹10.88 lakh")
        self.assertEqual(fmt_money(D("-20000")), "-₹20,000.00")
        self.assertEqual(fmt_money(D("1234567"), mode="table", scale="lakhs"), "12.35")
        self.assertEqual(fmt_money(D("-500000"), mode="table", scale="lakhs", negative="parentheses"), "(5.00)")

    def test_gstin(self):
        self.assertTrue(validate_gstin("27AAPFU0939F1ZV")[0])  # GSTN-published sample GSTIN
        self.assertFalse(validate_gstin("27AAPFU0939F1ZA")[0])  # wrong check character
        self.assertFalse(validate_gstin("27AAPFU0939F1Z")[0])  # wrong length


class TestSamplePipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.code, load = run_pipeline(SAMPLE, cls.tmp, os.path.join(SAMPLE, "narrative.json"))
        cls.load = staticmethod(load)
        cls.reg = load("calc_register.json")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def v(self, metric, period=CUR, **dims):
        r = value(self.reg, metric, period, **dims)
        return None if r["value"] is None else D(r["value"])

    def test_verification_passed(self):
        self.assertEqual(self.code, 0)
        self.assertEqual(self.load("verification.json")["outcome"], "passed")

    def test_profit_and_loss_golden(self):
        # Hand-computed: NR = 1,20,00,000 - 2,00,000; COGS = 80,00,000 - 5,00,000 + 1,00,000; ...
        expect = {"gross_revenue": "12000000", "sales_returns_and_allowances": "200000", "net_revenue": "11800000",
                  "cogs": "7600000", "gross_profit": "4200000", "operating_expenses": "2500000", "ebitda": "1700000",
                  "operating_profit": "1600000", "profit_before_tax": "1450000", "net_profit": "1087500"}
        for m, e in expect.items():
            self.assertEqual(self.v(m), D(e), m)
        self.assertEqual(self.v("net_revenue", CMP), D("9900000"))
        self.assertEqual(self.v("net_profit", CMP), D("745000"))
        self.assertEqual(self.v("revenue_growth"), D("1900000") / D("9900000"))
        self.assertEqual(self.v("gross_margin"), D("4200000") / D("11800000"))

    def test_balance_sheet_and_working_capital_golden(self):
        self.assertEqual(self.v("current_ratio"), D("6000000") / D("2012500"))
        self.assertEqual(self.v("quick_ratio"), D("3500000") / D("2012500"))
        self.assertEqual(self.v("working_capital"), D("3987500"))
        self.assertEqual(self.v("debt_to_equity"), D("2500000") / D("3387500"))
        self.assertEqual(self.v("interest_coverage_ratio"), D("8"))
        q = lambda x: x.quantize(D("1"), rounding=ROUND_HALF_UP)  # noqa: E731
        self.assertEqual(q(self.v("dso")), 26)   # 20,00,000 / 1,41,60,000 x 183
        self.assertEqual(q(self.v("dio")), 54)   # 22,50,000 / 76,00,000 x 183
        self.assertEqual(q(self.v("dpo")), 33)   # 13,50,000 / 76,00,000 x 183 (alternative input)
        self.assertEqual(q(self.v("cash_conversion_cycle")), 48)
        self.assertEqual(value(self.reg, "dpo")["readiness"], "partial")

    def test_cash_aging_sales_budget_settlements(self):
        self.assertEqual(self.v("cash_balance"), D("1280000"))
        self.assertIsNone(self.v("cash_runway"))
        self.assertEqual(value(self.reg, "cash_runway")["parameters"]["result_note"], "not_applicable")
        for b, e in (("not_due", "600000"), ("1_30", "500000"), ("61_90", "400000"), ("91_180", "300000"),
                     ("181_365", "400000"), ("total", "2200000")):
            self.assertEqual(self.v("ar_aging", bucket=b), D(e), b)
        self.assertEqual(self.v("ap_aging", bucket="61_90"), D("300000"))
        self.assertEqual(self.v("customer_concentration", measure="top_1_share"), D("0.35"))
        self.assertEqual(self.v("customer_concentration", measure="hhi").quantize(D("1")), 2406)
        self.assertEqual(self.v("budget_variance", account_class="revenue_from_operations", measure="variance"),
                         D("-500000"))
        self.assertEqual(self.v("marketplace_fees", provider="all"), D("100000"))
        self.assertEqual(self.v("settlement_variance"), D("246020"))
        recs = self.load("reconciliation.json")["rules"][0]["records"]
        self.assertEqual([r["match_status"] for r in recs], ["confirmed_match", "probable_match", "unmatched"])

    def test_issues_expected(self):
        checks = {i["check_id"]: i["severity"] for i in self.load("issues.json")}
        self.assertNotIn("critical", checks.values())
        for c in ("ai_msme_payables_timing", "ai_cash_movement", "ai_settlement_reconciliation"):
            self.assertIn(c, checks)

    def test_report_contains_verified_figures(self):
        text = read_text(os.path.join(self.tmp, "report.md"))
        self.assertIn("₹1.18 crore", text)
        self.assertIn("checks passed", text)
        self.assertIn("decision support, not an audit", text)


class TestFailureModes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.data = os.path.join(self.tmp, "data")
        shutil.copytree(SAMPLE, self.data)
        self.out = os.path.join(self.tmp, "run")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def edit_csv(self, name, fn):
        path = os.path.join(self.data, name)
        rows = list(read_rows(path))
        cols = list(rows[0])
        fn(rows)
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)

    def write_narrative(self, statement, refs):
        p = os.path.join(self.tmp, "n.json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump({"findings": [{"statement": statement, "refs": refs}]}, fh)
        return p

    def test_unbalanced_trial_balance_blocks_metrics(self):
        def f(rows):
            rows[0]["period_credit"] = "12000100.00"
            rows[0]["closing_credit"] = "12000100.00"
        self.edit_csv("trial_balance.csv", f)
        code, load = run_pipeline(self.data, self.out)
        issues = load("issues.json")
        self.assertTrue(any(i["check_id"] == "ai_trial_balance" and i["severity"] == "critical" for i in issues))
        self.assertEqual(value(load("calc_register.json"), "net_revenue")["readiness"], "blocked")
        self.assertIsNone(value(load("calc_register.json"), "net_revenue")["value"])

    def test_blank_amount_is_not_zero(self):
        def f(rows):
            rows[5]["period_debit"] = ""
        self.edit_csv("trial_balance.csv", f)
        code, load = run_pipeline(self.data, self.out)
        self.assertTrue(any(i["check_id"] == "dq_empty_fields" and i["severity"] == "critical"
                            for i in load("issues.json")))
        self.assertEqual(value(load("calc_register.json"), "net_profit")["readiness"], "blocked")

    def test_missing_budget_needs_data(self):
        os.remove(os.path.join(self.data, "budget.csv"))
        code, load = run_pipeline(self.data, self.out)
        r = value(load("calc_register.json"), "budget_variance", account_class="all", measure="variance")
        self.assertEqual(r["readiness"], "needs_data")
        self.assertIsNone(r["value"])

    def test_tampered_figure_fails_verification(self):
        run_pipeline(self.data, self.out)
        p = os.path.join(self.out, "report_draft.md")
        text = read_text(p).replace("₹1.18 crore", "₹1.28 crore")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
        res = fa_verify.verify(self.out, self.data)
        self.assertEqual(res["outcome"], "failed")
        self.assertIn("ver_register_tieout", [c["id"] for c in res["checks"] if c["status"] == "failed"])

    def test_typed_figure_in_narrative_rejected(self):
        n = self.write_narrative("Revenue was ₹1.18 crore this half-year.", ["metric:net_revenue"])
        code, load = run_pipeline(self.data, self.out, n)
        self.assertEqual(code, 3)
        failed = [c["id"] for c in load("verification.json")["checks"] if c["status"] == "failed"]
        self.assertIn("ver_narrative_raw_numbers", failed)
        self.assertIn("VERIFICATION FAILED", read_text(os.path.join(self.out, "report.md")))

    def test_prohibited_assurance_language_rejected(self):
        n = self.write_narrative("You are GST compliant.", ["check:ai_cash_movement"])
        code, load = run_pipeline(self.data, self.out, n)
        self.assertIn("ver_boundary_language",
                      [c["id"] for c in load("verification.json")["checks"] if c["status"] == "failed"])

    def test_unknown_evidence_reference_rejected(self):
        n = self.write_narrative("Net revenue was {{metric:net_revenue}}.", ["CALC-9999"])
        code, load = run_pipeline(self.data, self.out, n)
        self.assertIn("ver_claim_evidence",
                      [c["id"] for c in load("verification.json")["checks"] if c["status"] == "failed"])

    def test_wrong_topic_citation_warned(self):
        n = self.write_narrative("Receivables overdue are {{metric:revenue_by_product[sku=SKU-B]}}.",
                                 ["metric:revenue_by_product[sku=SKU-B]"])
        code, load = run_pipeline(self.data, self.out, n)
        warned = [c["id"] for c in load("verification.json")["checks"] if c["status"] == "warning"]
        self.assertIn("ver_claim_topic_consistency", warned)

    def test_unmasked_account_number_rejected(self):
        n = self.write_narrative("Collections land in account 123456789012.", ["metric:cash_balance"])
        code, load = run_pipeline(self.data, self.out, n)
        self.assertIn("ver_masking", [c["id"] for c in load("verification.json")["checks"] if c["status"] == "failed"])

    def test_changed_input_after_run_detected(self):
        run_pipeline(self.data, self.out)
        with open(os.path.join(self.data, "sales_lines.csv"), "a", encoding="utf-8") as fh:
            fh.write("\n")
        res = fa_verify.verify(self.out, self.data)
        self.assertIn("ver_no_fabrication", [c["id"] for c in res["checks"] if c["status"] == "failed"])


class TestImportTools(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_classifier_matches_sample_classes(self):
        out = os.path.join(self.tmp, "map.csv")
        with redirect_stdout(io.StringIO()):
            fa_classify.main(["--input", os.path.join(SKILL, "examples/raw-exports/tally_trial_balance_closing.csv"),
                              "--name-col", "Particulars", "--group-col", "Group", "--out", out])
        prop = {r["account_name"]: r["proposed_class"] for r in read_rows(out)}
        expected = {r["account_name"]: r["account_class"] for r in
                    read_rows(os.path.join(SAMPLE, "trial_balance.csv"))
                    if r["period_label"] == CUR}
        self.assertEqual(prop, expected)

    def test_normalizer_reproduces_canonical_sample(self):
        tb = os.path.join(self.tmp, "trial_balance.csv")
        bank = os.path.join(self.tmp, "bank_transactions.csv")
        maps = os.path.join(SKILL, "templates", "mappings")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(fa_normalize.main(["--mapping", os.path.join(maps, "tally_trial_balance_two_snapshots.json"),
                                                "--out", tb]), 0)
            self.assertEqual(fa_normalize.main(["--mapping", os.path.join(maps,
                                                                          "bank_statement_withdrawal_deposit.json"),
                                                "--out", bank]), 0)
        got = {r["account_name"]: r for r in read_rows(tb)}
        for e in read_rows(os.path.join(SAMPLE, "trial_balance.csv")):
            if e["period_label"] != CUR:
                continue
            g = got[e["account_name"]]
            self.assertEqual(g["account_class"], e["account_class"])
            for c in ("opening_debit", "opening_credit", "period_debit", "period_credit", "closing_debit",
                      "closing_credit"):
                self.assertEqual(D(g[c]), D(e[c]), (e["account_name"], c))
        got_b = list(read_rows(bank))
        exp_b = list(read_rows(os.path.join(SAMPLE, "bank_transactions.csv")))
        self.assertEqual(len(got_b), len(exp_b))
        for g, e in zip(got_b, exp_b):
            self.assertEqual(g["transaction_date"], e["transaction_date"])
            for c in ("debit", "credit", "balance"):
                self.assertEqual(D(g[c]), D(e[c]))


class TestSpecSync(unittest.TestCase):
    def test_spec_validates_and_matches_toolkit(self):
        try:
            import yaml  # noqa: F401
        except ImportError:
            self.skipTest("PyYAML not installed; spec structure check skipped")
        with redirect_stdout(io.StringIO()) as buf:
            code = fa_spec.cmd_validate()
        self.assertEqual(code, 0, buf.getvalue())

    def test_section_reader_without_yaml(self):
        with redirect_stdout(io.StringIO()) as buf:
            self.assertEqual(fa_spec.cmd_section("workflow"), 0)
        self.assertIn("execution_paths", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
