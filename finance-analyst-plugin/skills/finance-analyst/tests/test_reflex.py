"""Tests for the Proactive Financial Reflex Engine (finance-analyst.yaml reflex_engine).

Run from the skill directory:  python3 -m unittest discover -s tests -v
Expected values for the synthetic sample were worked out by hand (comments show the arithmetic).
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
from decimal import Decimal as D

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
SAMPLE = os.path.join(SKILL, "examples", "sample-sme")
sys.path.insert(0, os.path.join(SKILL, "scripts"))

import fa_run  # noqa: E402
import fa_verify  # noqa: E402

CUR = "H1 FY2025-26"


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.data = os.path.join(self.tmp, "data")
        shutil.copytree(SAMPLE, self.data)
        self.out = os.path.join(self.tmp, "run")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def config(self, **reflex):
        cfg = read_json(os.path.join(self.data, "run_config.json"))
        if reflex:
            cfg["reflex"] = reflex
        path = os.path.join(self.tmp, "cfg.json")
        write_json(path, cfg)
        return path, cfg

    def run_fa(self, cfg_path=None, approvals=None, round_no=1, reflex=True, narrative=None, depth="comprehensive"):
        with redirect_stdout(io.StringIO()):
            code = fa_run.run(self.data, cfg_path or os.path.join(self.data, "run_config.json"), self.out, narrative,
                              depth, approvals, round_no, reflex)
        self.rx = read_json(os.path.join(self.out, "reflex.json"))
        self.reg = read_json(os.path.join(self.out, "calc_register.json"))
        self.ver = read_json(os.path.join(self.out, "verification.json"))
        return code

    def v(self, metric, **dims):
        for r in self.reg:
            if r["metric_id"] == metric and (r["dimension"] or {}) == dims:
                return None if r["value"] is None else D(r["value"])
        raise KeyError((metric, dims))

    def rules(self):
        return {r for inv in self.rx["investigations"] for r in inv["rules"]}

    def status(self, check):
        return next(c["status"] for c in self.ver["checks"] if c["id"] == check)

    def edit_csv(self, name, fn):
        path = os.path.join(self.data, name)
        with open(path, encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        cols = list(rows[0])
        fn(rows)
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)


class TestSampleReflex(Base):
    def test_triggers_investigations_and_limits(self):
        self.assertEqual(self.run_fa(), 0)
        self.assertEqual(self.ver["outcome"], "passed")
        self.assertEqual(self.rx["triggers_found"], 12)
        self.assertEqual(len(self.rx["investigations"]), 10)  # default max_triggers = 10
        self.assertEqual([d["reason"] for d in self.rx["deferred"]], ["limit_reached:max_triggers"])
        for r in ("rx_overdue_receivables", "rx_settlement_shortfall", "rx_customer_concentration",
                  "rx_budget_overrun", "rx_msme_payables_timing", "rx_cost_category_spike",
                  "rx_bank_book_difference", "rx_partial_metric_upgrade"):
            self.assertIn(r, self.rules())
        self.assertNotIn("rx_margin_decline", self.rules())   # gross margin improved
        self.assertNotIn("rx_liquidity_pressure", self.rules())  # quick ratio 1.74
        merged = next(i for i in self.rx["investigations"] if i["subject"] == "account_class:marketplace_fees")
        self.assertEqual(merged["rules"], ["rx_cost_category_spike", "rx_budget_overrun"])
        first = self.rx["investigations"][0]
        self.assertEqual((first["subject"], first["severity"]), ("receivables", "high"))  # escalated: share >= 25%

    def test_derived_and_scenario_values(self):
        self.run_fa()
        thr = {"threshold_days": "90"}
        self.assertEqual(self.v("rx_ar_overdue_total", **thr), D("700000"))  # C004 3,00,000 + C005 4,00,000
        self.assertEqual(self.v("rx_ar_overdue_share", **thr), D("700000") / D("2200000"))
        self.assertEqual(self.v("rx_ar_overdue_by_customer", customer_id="C005", **thr), D("400000"))
        self.assertEqual(self.v("scn_collect_overdue_cash"), D("1980000"))  # 12,80,000 + 7,00,000
        self.assertEqual(self.v("scn_collect_overdue_dso"), D("1650000") / D("14160000") * 183)
        self.assertEqual(self.v("scn_dso_reduction_cash_release", dso_reduction_days="10"),
                         D("10") * D("14160000") / D("183"))
        self.assertEqual(self.v("rx_settlement_unlocated", settlement_id="MA-SET-0003"), D("246020"))
        self.assertEqual(self.v("rx_settlement_days_unlocated", settlement_id="MA-SET-0003"), D("5"))
        self.assertEqual(self.v("scn_settlement_recovery_cash"), D("1526020"))
        self.assertEqual(self.v("rx_settlement_component", component="tax_on_fees"), D("18000"))
        self.assertEqual(self.v("rx_msme_overdue_total", max_days="45"), D("300000"))
        self.assertEqual(self.v("rx_msme_max_days", max_days="45"), D("91"))
        self.assertEqual(self.v("scn_msme_clearance_cash_after"), D("980000"))
        rg = D("1900000") / D("9900000")
        self.assertEqual(self.v("scn_cost_normalisation_saving", account_class="marketplace_fees"),
                         D("400000") - D("300000") * (1 + rg))
        self.assertEqual(self.v("rx_cost_growth_gap", account_class="advertising"), D("50000") / D("150000") - rg)
        self.assertEqual(self.v("rx_bank_book_difference"), D("-20000"))
        self.assertEqual(self.v("rx_customer_revenue_share", customer_id="C001"), D("0.35"))

    def test_prioritised_recommendations(self):
        self.run_fa()
        recs = self.rx["recommendations"]
        self.assertTrue(recs[0]["title"].startswith("Collect receivables more than 90 days past due"))
        self.assertEqual(recs[0]["priority_score"], "3.00")
        scores = [D(r["priority_score"]) for r in recs]
        self.assertEqual(scores, sorted(scores, reverse=True))
        msme = next(r for r in recs if r["rule_id"] == "rx_msme_payables_timing")
        self.assertTrue(msme["professional_review_needed"])

    def test_gates_requests_and_charts(self):
        self.run_fa()
        aprs = {a["action_class"]: a for a in self.rx["approval_requests"]}
        self.assertEqual(sorted(a["status"] for a in self.rx["approval_requests"]), ["pending_approval"] * 3)
        self.assertEqual(aprs["financial_write"]["execution"], "customer_executes")
        self.assertFalse(self.rx["prepared"])
        self.assertFalse(os.path.isdir(os.path.join(self.out, "prepared")) and
                         os.listdir(os.path.join(self.out, "prepared")))
        self.assertEqual({q["status"] for q in self.rx["data_requests"]}, {"requested"})
        self.assertTrue(all(q["read_only"] for q in self.rx["data_requests"]))
        self.assertIn("credit purchases including GST", [q["dataset"] for q in self.rx["data_requests"]])
        self.assertEqual(len(self.rx["charts"]), 5)
        for ch in self.rx["charts"]:
            with open(os.path.join(self.out, ch["svg"]), encoding="utf-8") as fh:
                svg = fh.read()
            self.assertIn("<title", svg)
        for check in ("ver_chart_data", "ver_approval_gates", "ver_recompute_figures", "ver_claim_topic_consistency"):
            self.assertEqual(self.status(check), "passed", check)
        with open(os.path.join(self.out, "report.md"), encoding="utf-8") as fh:
            report = fh.read()
        self.assertIn("## Proactive insights (Reflex Engine)", report)
        self.assertIn("nothing was sent, uploaded, paid or posted", report)
        self.assertIn("![Receivables by days past due](charts/rx-ar-aging.svg)", report)

    def test_deterministic(self):
        self.run_fa()
        first = json.dumps(self.rx, sort_keys=True)
        with open(os.path.join(self.out, "charts", "rx-settlement-waterfall.svg"), encoding="utf-8") as fh:
            svg1 = fh.read()
        self.run_fa()
        self.assertEqual(json.dumps(self.rx, sort_keys=True), first)
        with open(os.path.join(self.out, "charts", "rx-settlement-waterfall.svg"), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), svg1)


class TestApprovals(Base):
    def ids(self):
        self.run_fa()
        return {a["action_id"]: a["approval_id"] for a in self.rx["approval_requests"]}

    def test_approved_actions_prepare_drafts_only(self):
        ids = self.ids()
        approvals = os.path.join(self.tmp, "approvals.json")
        write_json(approvals, {"approved": [
            {"approval_id": ids["external_draft_collection_reminders"], "approved_by": "customer",
             "approved_at": "2026-11-04T10:00:00+05:30", "scope": "draft reminders"},
            {"approval_id": ids["financial_prepare_payment_proposal"], "approved_by": "customer",
             "approved_at": "2026-11-04T10:00:00+05:30", "scope": "payment proposal"}],
            "rejected": [{"approval_id": ids["external_draft_settlement_query"], "reason": "will call them"}]})
        self.assertEqual(self.run_fa(approvals=approvals), 0)
        status = {a["action_id"]: a["status"] for a in self.rx["approval_requests"]}
        self.assertEqual(status["external_draft_collection_reminders"], "approved_prepared")
        self.assertEqual(status["financial_prepare_payment_proposal"], "approved_prepared")
        self.assertEqual(status["external_draft_settlement_query"], "rejected")
        files = {p["file"]: p for p in self.rx["prepared"]}
        self.assertEqual(files["prepared/collection_reminders.md"]["status"], "prepared_not_sent")
        self.assertEqual(files["prepared/msme_payment_proposal.csv"]["status"], "prepared_customer_executes")
        with open(os.path.join(self.out, "prepared", "collection_reminders.md"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("NOT SENT", text)
        self.assertIn("INV-0950", text)  # Coastal Traders, 289 days past due
        with open(os.path.join(self.out, "prepared", "msme_payment_proposal.csv"), encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual([(r["supplier_id"], r["amount_outstanding"]) for r in rows], [("S001", "300000.00")])
        self.assertFalse(os.path.exists(os.path.join(self.out, "prepared", "settlement_query_MA-SET-0003.md")))
        self.assertEqual(self.status("ver_approval_gates"), "passed")

    def test_gates_cannot_be_relaxed(self):
        cfg, _ = self.config(approvals={"external_action": "auto", "financial_write": "auto"})
        self.assertEqual(self.run_fa(cfg), 0)
        codes = [w["code"] for w in self.rx["warnings"]]
        self.assertEqual(codes.count("FA-W-RFX-003"), 2)
        self.assertEqual(self.rx["config"]["approvals"]["external_action"], "approval_required")
        self.assertTrue(all(a["status"] == "pending_approval" for a in self.rx["approval_requests"]))
        self.assertFalse(self.rx["prepared"])

    def test_connector_reads_can_be_tightened(self):
        cfg, _ = self.config(approvals={"connector_read": "approval_required"})
        self.run_fa(cfg)
        self.assertEqual({q["status"] for q in self.rx["data_requests"]}, {"pending_approval"})
        req_ids = {q["request_id"] for q in self.rx["data_requests"]}
        self.assertTrue(req_ids <= {a["approval_id"] for a in self.rx["approval_requests"]})

    def test_round_limit_stops_new_requests(self):
        self.run_fa(round_no=3)  # max_reflex_rounds = 2
        self.assertEqual({q["status"] for q in self.rx["data_requests"]}, {"not_requested_round_limit"})

    def test_tampering_is_detected(self):
        self.run_fa()
        rx_path = os.path.join(self.out, "reflex.json")
        rx = read_json(rx_path)
        for inv in rx["investigations"]:
            for a in inv["actions"]:
                if a["action_class"] == "external_action":
                    a["status"] = "done"
        write_json(rx_path, rx)
        res = fa_verify.verify(self.out, self.data)
        self.assertEqual(next(c["status"] for c in res["checks"] if c["id"] == "ver_approval_gates"), "failed")
        self.run_fa()
        os.makedirs(os.path.join(self.out, "prepared"), exist_ok=True)
        with open(os.path.join(self.out, "prepared", "payment.csv"), "w", encoding="utf-8") as fh:
            fh.write("pay,everyone\n")
        res = fa_verify.verify(self.out, self.data)
        self.assertEqual(next(c["status"] for c in res["checks"] if c["id"] == "ver_approval_gates"), "failed")

    def test_chart_tampering_is_detected(self):
        self.run_fa()
        path = os.path.join(self.out, "charts", "rx-ar-aging.json")
        spec = read_json(path)
        spec["series"][0]["value"] = "9600000.00"
        write_json(path, spec)
        res = fa_verify.verify(self.out, self.data)
        self.assertEqual(next(c["status"] for c in res["checks"] if c["id"] == "ver_chart_data"), "failed")


class TestThresholdsDedupLimits(Base):
    def test_min_confidence_suppresses(self):
        cfg, _ = self.config(min_confidence="0.95")
        self.run_fa(cfg)
        self.assertFalse(self.rx["investigations"])
        self.assertEqual({s["reason"] for s in self.rx["suppressed"]}, {"below_min_confidence"})
        self.assertEqual(self.ver["outcome"], "passed")

    def test_min_severity_filters(self):
        cfg, _ = self.config(min_severity="high")
        self.run_fa(cfg)
        self.assertEqual({i["severity"] for i in self.rx["investigations"]}, {"high"})
        self.assertEqual(sorted(i["subject"] for i in self.rx["investigations"]),
                         ["receivables", "settlement:MA-SET-0003"])
        self.assertIn("below_min_severity", {s["reason"] for s in self.rx["suppressed"]})

    def test_rule_disable_and_severity_override(self):
        cfg, _ = self.config(rules={"rx_customer_concentration": {"enabled": False},
                                    "rx_bank_book_difference": {"severity": "high"}})
        self.run_fa(cfg)
        self.assertNotIn("rx_customer_concentration", self.rules())
        bb = next(i for i in self.rx["investigations"] if i["subject"] == "bank_book")
        self.assertEqual(bb["severity"], "high")

    def test_merge_can_be_disabled(self):
        cfg, _ = self.config(deduplication={"merge_same_subject": False},
                             execution_limits={"max_triggers": 20})
        self.run_fa(cfg)
        fees = [i for i in self.rx["investigations"] if i["subject"] == "account_class:marketplace_fees"]
        self.assertEqual(len(fees), 2)

    def test_acknowledged_findings_are_suppressed_until_worse(self):
        self.run_fa()
        fp = next(t["fingerprint"] for i in self.rx["investigations"] for t in i["triggers"]
                  if t["rule_id"] == "rx_overdue_receivables")
        ack = os.path.join(self.tmp, "ack.json")
        write_json(ack, {"acknowledged": [{"fingerprint": fp, "amount": "700000", "acknowledged_at": "2026-10-01"}]})
        cfg, _ = self.config(deduplication={"acknowledged_file": ack})
        self.run_fa(cfg)
        self.assertNotIn("rx_overdue_receivables", self.rules())
        self.assertIn("acknowledged", {s["reason"] for s in self.rx["suppressed"]})
        write_json(ack, {"acknowledged": [{"fingerprint": fp, "amount": "500000", "acknowledged_at": "2026-10-01"}]})
        self.run_fa(cfg)  # 7,00,000 >= 5,00,000 x 1.20 -> reopened
        trig = next(t for i in self.rx["investigations"] for t in i["triggers"]
                    if t["rule_id"] == "rx_overdue_receivables")
        self.assertIn("worsened", trig["reopened"])

    def test_execution_limits_defer_work(self):
        cfg, _ = self.config(execution_limits={"max_triggers": 3, "max_charts": 1, "max_data_requests": 1})
        self.assertEqual(self.run_fa(cfg), 0)
        self.assertEqual(len(self.rx["investigations"]), 3)
        self.assertEqual(len(self.rx["charts"]), 1)
        self.assertLessEqual(len(self.rx["data_requests"]), 1)
        reasons = {d["reason"] for d in self.rx["deferred"]}
        self.assertTrue({"limit_reached:max_triggers", "limit_reached:max_charts"} <= reasons)
        self.assertIn("FA-W-RFX-001", [w["code"] for w in self.rx["warnings"]])
        self.assertEqual(self.ver["outcome"], "passed")


class TestRealisticScenarios(Base):
    def test_margin_decline_triggers_price_scenario(self):
        # Current-period purchases +10,00,000 paid from bank (TB stays balanced).
        def f(rows):
            for r in rows:
                if r["period_label"] != CUR:
                    continue
                if r["account_id"] == "5000":
                    r["period_debit"] = "9000000.00"
                    r["closing_debit"] = "9000000.00"
                if r["account_id"] == "1300":
                    r["period_credit"] = "1000000.00"
                    r["closing_debit"] = "300000.00"
        self.edit_csv("trial_balance.csv", f)
        self.assertEqual(self.run_fa(), 0)
        self.assertIn("rx_margin_decline", self.rules())
        gm_c = D("3200000") / D("11800000")
        gm_p = D("3420000") / D("9900000")
        self.assertEqual(self.v("rx_margin_change", margin="gross_margin"), gm_c - gm_p)
        self.assertEqual(self.v("scn_margin_restoration_price_increase"),
                         D("8600000") / (1 - gm_p) / D("11800000") - 1)
        bb = next(i for i in self.rx["investigations"] if i["subject"] == "bank_book")
        self.assertEqual(bb["severity"], "high")  # 9,80,000 difference >= materiality floor
        self.assertIn("rx-margins", [c["chart_id"] for c in self.rx["charts"]])
        self.assertEqual(self.ver["outcome"], "passed")

    def test_liquidity_rule_with_customer_threshold(self):
        cfg, _ = self.config(rules={"rx_liquidity_pressure": {"params": {"quick_ratio_below": "2.00",
                                                                         "runway_months_below": "6"}}},
                             execution_limits={"max_triggers": 20})
        self.run_fa(cfg)
        self.assertIn("rx_liquidity_pressure", self.rules())
        self.assertEqual(self.v("rx_near_term_obligations"), D("1500000"))  # all four open bills due <= 30 days
        self.assertEqual(self.v("rx_near_term_receipts"), D("600000"))      # INV-1041 due 05-Oct
        self.assertEqual(self.v("rx_near_term_coverage"), (D("1280000") + D("600000")) / D("1500000"))
        self.assertEqual(self.ver["outcome"], "passed")

    def test_critical_blockers_first_and_no_guessing(self):
        def f(rows):
            rows[0]["period_credit"] = "12000100.00"
            rows[0]["closing_credit"] = "12000100.00"
        self.edit_csv("trial_balance.csv", f)
        self.run_fa()
        first = self.rx["investigations"][0]
        self.assertEqual((first["rules"], first["severity"]), (["rx_critical_data_blockers"], "critical"))
        for r in ("rx_budget_overrun", "rx_cost_category_spike", "rx_margin_decline"):
            self.assertNotIn(r, self.rules())  # depend on blocked TB metrics
        self.assertEqual(self.status("ver_recompute_figures"), "passed")

    def test_customer_confirmed_match_upgrades_settlement(self):
        cfg_path, cfg = self.config()
        cfg["reconciliation"]["customer_confirmed_matches"] = ["GX-SET-0002"]
        write_json(cfg_path, cfg)
        self.run_fa(cfg_path)
        recon = read_json(os.path.join(self.out, "reconciliation.json"))
        gx = next(r for r in recon["rules"][0]["records"] if r["settlement_id"] == "GX-SET-0002")
        self.assertEqual(gx["match_status"], "confirmed_match")
        sv = next(r for r in self.reg if r["metric_id"] == "settlement_variance")
        self.assertEqual(sv["readiness"], "ready")
        self.assertNotIn("data_gap:probable_settlement_matches",
                         [d.get("subject") for d in self.rx["deferred"]] +
                         [i["subject"] for i in self.rx["investigations"]])

    def test_narrative_can_cite_reflex_figures(self):
        self.assertEqual(self.run_fa(narrative=os.path.join(SAMPLE, "narrative.json")), 0)
        self.assertEqual(self.ver["outcome"], "passed")
        with open(os.path.join(self.out, "report.md"), encoding="utf-8") as fh:
            report = fh.read()
        self.assertIn("would raise cash to ₹19.80 lakh", report)

    def test_disabled_reflex_preserves_base_results(self):
        self.run_fa(reflex=False)
        base = [r for r in self.reg]
        self.assertFalse(self.rx["enabled"])
        with open(os.path.join(self.out, "report.md"), encoding="utf-8") as fh:
            self.assertNotIn("Proactive insights", fh.read())
        self.assertEqual(self.ver["outcome"], "passed")
        self.run_fa(reflex=True)
        self.assertEqual(self.reg[:len(base)], base)  # reflex only appends to the register


if __name__ == "__main__":
    unittest.main()
