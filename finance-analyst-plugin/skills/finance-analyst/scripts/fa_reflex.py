"""Proactive Financial Reflex Engine (finance-analyst.yaml §35 reflex_engine).

Runs inside fa_run.py after metrics are calculated (or standalone on a finished run):

    python3 fa_reflex.py --run-dir RUN --input-dir DATA [--approvals approvals.json] [--round 2]

What it does, deterministically and only within the current task:
  1. evaluates configurable trigger rules on the calculation register, issues and reconciliation;
  2. filters by severity, confidence and acknowledgements; de-duplicates and merges by subject;
  3. orders by priority and applies execution limits (work beyond a limit is deferred, never dropped);
  4. runs each trigger's playbook: local reads, derived calculations and scenarios (added to the
     calculation register so fa_verify.py recomputes them), charts (SVG bound to calc_ids);
  5. emits data requests for additional authorised data, and approval requests for anything
     external or financial; prepares drafts/proposals only for approved approval_ids;
  6. composes insights and prioritised recommendations with figures as register placeholders.

It never calls connectors, sends messages, uploads files, pays, posts or files anything.
"""
from __future__ import annotations

import argparse
import copy
import csv
import datetime as _dt
import hashlib
import json
import os
import sys
import time
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fa_charts import label as chart_label  # noqa: E402
from fa_charts import render_svg  # noqa: E402
from fa_common import (ZERO, CalcRegister, fmt_money, json_default, read_json, skill_dir, write_json)  # noqa: E402
from fa_data import input_ref, natural, tb_periods  # noqa: E402

SEVERITIES = ["informational", "low", "medium", "high", "critical"]
CONFIDENCE = {"ready": Decimal("0.90"), "partial": Decimal("0.60"), "probable": Decimal("0.50"),
              "heuristic": Decimal("0.40")}
RULE_IDS = ["rx_critical_data_blockers", "rx_overdue_receivables", "rx_customer_concentration",
            "rx_settlement_shortfall", "rx_bank_book_difference", "rx_margin_decline", "rx_cost_category_spike",
            "rx_budget_overrun", "rx_msme_payables_timing", "rx_liquidity_pressure", "rx_partial_metric_upgrade"]
DERIVED_IDS = ["rx_ar_overdue_total", "rx_ar_overdue_share", "rx_ar_overdue_by_customer", "rx_customer_revenue_share",
               "rx_customer_open_receivables", "rx_settlement_unlocated", "rx_settlement_days_unlocated",
               "rx_settlement_component", "rx_bank_book_difference", "rx_margin_change", "rx_cost_growth_gap",
               "rx_budget_shortfall", "rx_msme_overdue_total", "rx_msme_overdue_by_supplier", "rx_msme_max_days",
               "rx_near_term_obligations", "rx_near_term_receipts", "rx_near_term_coverage"]
SCENARIO_IDS = ["scn_collect_overdue_cash", "scn_collect_overdue_dso", "scn_collect_overdue_dso_change",
                "scn_dso_reduction_cash_release", "scn_settlement_recovery_cash",
                "scn_margin_restoration_price_increase", "scn_cost_normalisation_saving",
                "scn_msme_clearance_cash_after"]
ACTION_GATES = {"local_read": "auto", "local_compute": "auto", "scenario": "auto", "chart": "auto",
                "connector_read": "configurable", "restricted_read": "approval_required",
                "customer_confirmation": "approval_required", "external_action": "approval_required",
                "financial_write": "approval_required"}
NON_RELAXABLE = ["restricted_read", "customer_confirmation", "external_action", "financial_write"]
# Cost categories excluded from the spike rule (volume-driven; the margin rule covers them).
SPIKE_EXCLUDED = {"purchases_of_stock_in_trade", "changes_in_inventories", "cost_of_materials_consumed"}
BUCKET_LABELS = {"not_due": "Not due", "1_30": "1–30 days", "31_60": "31–60 days", "61_90": "61–90 days",
                 "91_180": "91–180 days", "181_365": "181–365 days", "over_365": "Over 365 days"}


class LimitReached(Exception):
    pass


def D(x):
    return Decimal(str(x))


def deep_merge(base, over):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def fingerprint(*parts):
    return hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:12]


def default_config():
    return read_json(os.path.join(skill_dir(), "templates", "reflex_rules.json"))


def load_config(run_cfg):
    cfg = deep_merge(default_config(), run_cfg.get("reflex") or {})
    warnings = []
    for cls in NON_RELAXABLE:
        if cfg["approvals"].get(cls) != "approval_required":
            warnings.append({"code": "FA-W-RFX-003", "message": f"approvals.{cls} cannot be relaxed; kept "
                                                                 f"approval_required (was "
                                                                 f"{cfg['approvals'].get(cls)!r})"})
            cfg["approvals"][cls] = "approval_required"
    if cfg["approvals"].get("connector_read") not in ("auto_if_authorized", "approval_required"):
        warnings.append({"code": "FA-W-RFX-003", "message": "approvals.connector_read must be auto_if_authorized "
                                                            "or approval_required; using approval_required"})
        cfg["approvals"]["connector_read"] = "approval_required"
    if cfg.get("min_severity") not in SEVERITIES:
        cfg["min_severity"] = "low"
    return cfg, warnings


class Reflex:
    def __init__(self, data, run_cfg, reg, issues, recon, out_dir, approvals=None, round_no=1):
        self.data, self.run_cfg, self.reg, self.issues, self.recon = data, run_cfg, reg, issues, recon
        self.out_dir = out_dir
        self.cfg, self.config_warnings = load_config(run_cfg)
        self.limits = self.cfg["execution_limits"]
        self.cur = run_cfg["current_period"]
        self.cmp = run_cfg.get("comparison_period")
        self.as_of = _dt.date.fromisoformat(self.cur["end"])
        self.days = Decimal((self.as_of - _dt.date.fromisoformat(self.cur["start"])).days + 1)
        mat = run_cfg.get("materiality", {})
        self.floor = D(mat.get("absolute_floor_inr", "25000"))
        self.round_no = round_no
        self.approved = {a["approval_id"]: a for a in (approvals or {}).get("approved", [])}
        self.rejected = {a["approval_id"]: a for a in (approvals or {}).get("rejected", [])}
        self.calc_index, self.charts, self.requests, self.approval_requests = {}, {}, {}, {}
        self.prepared, self.deferred, self.suppressed = [], [], []
        self.n_derived = self.n_scen = 0
        self.post = {}
        self.t0 = time.monotonic()

    # ------------------------------------------------------------------ register access
    def rec(self, metric, which="current", **dims):
        p = self.cur if which == "current" else self.cmp
        if not p:
            return None
        for r in self.reg.records:
            if r["metric_id"] == metric and (r["period"] or {}).get("label") == p["label"] and \
                    (r["dimension"] or {}) == dims:
                return r
        return None

    def val(self, metric, which="current", **dims):
        r = self.rec(metric, which, **dims)
        if not r or r["value"] is None or r["readiness"] in ("blocked", "needs_data"):
            return None
        return Decimal(r["value"])

    @staticmethod
    def conf(*records, probable=False):
        vals = []
        for r in records:
            if r is None:
                continue
            vals.append(CONFIDENCE["ready"] if r["readiness"] == "ready" else CONFIDENCE["partial"])
        c = min(vals) if vals else CONFIDENCE["heuristic"]
        return min(c, CONFIDENCE["probable"]) if probable else c

    def add_calc(self, metric_id, value, unit, formula, kinds, dims=None, params=None, readiness="ready",
                 warnings=None, scenario=False, label="derived"):
        key = (metric_id, tuple(sorted((dims or {}).items())))
        if key in self.calc_index:
            return self.calc_index[key]
        if self.n_derived + self.n_scen >= int(self.limits["max_derived_calcs"]):
            raise LimitReached("max_derived_calcs")
        if scenario and self.n_scen >= int(self.limits["max_scenarios"]):
            raise LimitReached("max_scenarios")
        if scenario:
            self.n_scen += 1
        else:
            self.n_derived += 1
        inputs = [r for r in (input_ref(self.data, k) for k in kinds) if r]
        p = dict(params or {})
        p["reflex"] = "scenario" if scenario else "derived"
        cid = self.reg.add(metric_id, value, unit, formula, inputs,
                           {"label": self.cur["label"], "start": self.cur["start"], "end": self.cur["end"]},
                           readiness=readiness, warnings=warnings or [], label="scenario" if scenario else label,
                           parameters=p, dimension=dims or None, entity=self.run_cfg.get("entity_id"))
        self.calc_index[key] = cid
        return cid

    def rows(self, kind):
        ds = self.data["datasets"].get(kind)
        return ds["rows"] if ds else []

    # ------------------------------------------------------------------ trigger helpers
    def trig(self, rule_id, subject, title, severity, amount, confidence, evidence, facts=None):
        return {"rule_id": rule_id, "subject": subject, "title": title, "severity": severity,
                "amount": amount, "confidence": confidence, "evidence": [e for e in evidence if e],
                "facts": facts or {}, "fingerprint": fingerprint(rule_id, subject, self.cur["label"])}

    @staticmethod
    def up(sev):
        return SEVERITIES[min(SEVERITIES.index(sev) + 1, len(SEVERITIES) - 1)]

    def base(self, rule_id):
        sev = self.rule_cfg(rule_id).get("severity")
        return sev if sev in SEVERITIES else "medium"

    def rule_cfg(self, rule_id):
        return self.cfg["rules"].get(rule_id, {})

    def params(self, rule_id):
        return self.rule_cfg(rule_id).get("params", {})

    def ar_overdue(self, threshold):
        out = {}
        names = {}
        for r in self.rows("ar_open_items"):
            ref = r.get("due_date") or r.get("invoice_date")
            if ref is None or r.get("amount_outstanding") is None:
                continue
            if (self.as_of - ref).days > threshold:
                cid = r.get("customer_id")
                out[cid] = out.get(cid, ZERO) + r["amount_outstanding"]
                names[cid] = r.get("customer_name") or cid
        return out, names

    def msme_overdue(self, max_days):
        out, names, max_age, bills = {}, {}, 0, []
        for r in self.rows("ap_open_items"):
            if (r.get("msme_classification") or "").lower() not in ("micro", "small") or not r.get("bill_date"):
                continue
            age = (self.as_of - r["bill_date"]).days
            if age > max_days and r.get("amount_outstanding"):
                sid = r.get("supplier_id")
                out[sid] = out.get(sid, ZERO) + r["amount_outstanding"]
                names[sid] = r.get("supplier_name") or sid
                max_age = max(max_age, age)
                bills.append(r)
        return out, names, max_age, bills

    # ------------------------------------------------------------------ rules
    def r_critical(self, p):
        crit = [i for i in self.issues if i["severity"] == "critical"]
        if not crit:
            return []
        return [self.trig("rx_critical_data_blockers", "data_blockers",
                          "Critical data issues block part of the analysis", self.base("rx_critical_data_blockers"),
                          None, CONFIDENCE["ready"],
                          [i["issue_id"] for i in crit], {"issue_ids": [i["issue_id"] for i in crit]})]

    def r_overdue(self, p):
        total_rec = self.rec("ar_aging", bucket="total")
        total = self.val("ar_aging", bucket="total")
        if not total:
            return []
        by_cust, names = self.ar_overdue(int(p["overdue_days"]))
        over = sum(by_cust.values(), ZERO)
        share = over / total
        if share < D(p["min_share_of_receivables"]) or over < self.floor:
            return []
        sev = self.base("rx_overdue_receivables")
        if share >= D(p["escalate_share"]) or over >= 4 * self.floor:
            sev = self.up(sev)
        return [self.trig("rx_overdue_receivables", "receivables",
                          f"Receivables more than {p['overdue_days']} days past due", sev, over,
                          self.conf(total_rec), [total_rec["calc_id"]],
                          {"by_customer": by_cust, "names": names, "over": over, "threshold": int(p["overdue_days"])})]

    def r_concentration(self, p):
        r = self.rec("customer_concentration", measure="top_1_share")
        share = self.val("customer_concentration", measure="top_1_share")
        if share is None or share < D(p["top1_share_at_least"]):
            return []
        tops = sorted((x for x in self.reg.records if x["metric_id"] == "revenue_by_customer" and x["value"]
                       and x["period"]["label"] == self.cur["label"]),
                      key=lambda x: (-Decimal(x["value"]), x["dimension"]["customer_id"]))
        if not tops:
            return []
        top = tops[0]
        cid = top["dimension"]["customer_id"]
        name = (top.get("parameters") or {}).get("name") or cid
        return [self.trig("rx_customer_concentration", f"customer:{cid}", f"High dependence on {name}",
                          self.base("rx_customer_concentration"),
                          Decimal(top["value"]), self.conf(r, top), [r["calc_id"], top["calc_id"]],
                          {"customer_id": cid, "name": name})]

    def r_settlement(self, p):
        rule = next((x for x in self.recon.get("rules", []) if x["rule_id"] == "rec_settlement_to_bank"), None)
        if not rule or rule.get("status") != "completed":
            return []
        out = []
        for rec in rule["records"]:
            if rec["match_status"] == "unmatched":
                amt = D(rec["expected_net"])
            elif rec["match_status"] == "conflicting" and rec.get("difference") is not None:
                amt = abs(D(rec["difference"]))
            else:
                continue
            if amt <= Decimal("1.00"):
                continue
            sv = self.rec("settlement_variance")
            window = int(self.run_cfg.get("reconciliation", {}).get("settlement_to_bank_days", 5))
            sdate = rec.get("settlement_date")
            days = (self.as_of - (sdate if isinstance(sdate, _dt.date) else _dt.date.fromisoformat(str(sdate)))).days \
                if sdate else None
            timing = rec["match_status"] == "unmatched" and days is not None and days <= window
            nature = "timing" if timing else "unexplained"
            title = (f"Settlement {rec['settlement_id']} not yet in bank data (within the {window}-day timing window)"
                     if timing else f"Settlement {rec['settlement_id']}: unexplained shortfall beyond the timing window")
            out.append(self.trig("rx_settlement_shortfall", f"settlement:{rec['settlement_id']}", title,
                                 "low" if timing else self.base("rx_settlement_shortfall"), amt,
                                 self.conf(sv) if sv else CONFIDENCE["partial"],
                                 [sv["calc_id"] if sv else None, "check:ai_settlement_reconciliation"],
                                 {"record": rec, "nature": nature, "window": window, "days": days}))
        return out

    def r_bank_book(self, p):
        c = next((x for x in self.recon.get("conflicts", []) if x["conflict_id"] == "CON-BANK-BOOK"), None)
        if not c or c["status"] == "resolved":
            return []
        diff = D(c["aligned_difference"])
        if abs(diff) < D(p["min_abs_difference_inr"]):
            return []
        sev = self.base("rx_bank_book_difference")
        if abs(diff) >= self.floor:
            sev = self.up(sev)
        return [self.trig("rx_bank_book_difference", "bank_book", "Bank and book balances differ at period end",
                          sev, abs(diff), CONFIDENCE["ready"], ["CON-BANK-BOOK", "check:ai_cash_movement"],
                          {"difference": diff, "bank": D(c["figures"][0]["value"]), "book": D(c["figures"][1]["value"])})]

    def r_margin(self, p):
        if not self.cmp:
            return []
        out = []
        nr = self.val("net_revenue")
        for m in ("gross_margin", "ebitda_margin"):
            a, b = self.val(m), self.val(m, "comparison")
            if a is None or b is None:
                continue
            change = a - b
            if change <= -D(p["min_decline"]):
                out.append(self.trig("rx_margin_decline", f"margin:{m}", f"{m.replace('_', ' ').capitalize()} declined",
                                     self.base("rx_margin_decline"), abs(change) * (nr or ZERO), self.conf(self.rec(m), self.rec(m, "comparison")),
                                     [self.rec(m)["calc_id"], self.rec(m, "comparison")["calc_id"]],
                                     {"metric": m, "change": change}))
        return out

    def r_cost_spike(self, p):
        rg = self.val("revenue_growth")
        if rg is None:
            return []
        out = []
        for r in self.reg.records:
            d = r["dimension"] or {}
            if r["metric_id"] != "cost_category_variance" or d.get("measure") != "percent" or r["value"] is None:
                continue
            cls = d["account_class"]
            if cls in SPIKE_EXCLUDED:
                continue
            growth = Decimal(r["value"])
            amt_rec = self.rec("cost_category_variance", account_class=cls, measure="amount")
            inc = Decimal(amt_rec["value"]) if amt_rec and amt_rec["value"] is not None else ZERO
            if growth - rg >= D(p["min_growth_gap"]) and inc >= self.floor:
                sev = self.base("rx_cost_category_spike")
                if inc >= 4 * self.floor:
                    sev = self.up(sev)
                out.append(self.trig("rx_cost_category_spike", f"account_class:{cls}",
                                     f"{cls.replace('_', ' ').capitalize()} grew faster than revenue", sev, inc,
                                     self.conf(r, amt_rec), [r["calc_id"], amt_rec["calc_id"]],
                                     {"account_class": cls, "growth": growth, "increase": inc}))
        return out

    def r_budget(self, p):
        nr = self.val("net_revenue") or ZERO
        out = []
        for r in self.reg.records:
            d = r["dimension"] or {}
            if r["metric_id"] != "budget_variance" or d.get("measure") != "variance" or r["value"] is None:
                continue
            if (r.get("parameters") or {}).get("favourability") != "unfavourable":
                continue
            cls = d["account_class"]
            var = abs(Decimal(r["value"]))
            pct_r = self.rec("budget_variance", account_class=cls, measure="variance_pct")
            pct = abs(Decimal(pct_r["value"])) if pct_r and pct_r["value"] is not None else ZERO
            if var >= self.floor and (pct >= D(p["min_variance_pct"]) or var >= D(p["min_revenue_share"]) * nr):
                out.append(self.trig("rx_budget_overrun", f"account_class:{cls}",
                                     f"{cls.replace('_', ' ').capitalize()} is unfavourable to budget",
                                     self.base("rx_budget_overrun"), var,
                                     self.conf(r), [r["calc_id"], pct_r["calc_id"] if pct_r else None],
                                     {"account_class": cls, "variance_calc": r["calc_id"]}))
        return out

    def r_msme(self, p):
        by_sup, names, max_age, bills = self.msme_overdue(int(p["max_days"]))
        if not by_sup:
            return []
        total = sum(by_sup.values(), ZERO)
        return [self.trig("rx_msme_payables_timing", "msme_payables",
                          f"MSME supplier bills outstanding beyond {p['max_days']} days",
                          self.base("rx_msme_payables_timing"), total,
                          CONFIDENCE["ready"], ["check:ai_msme_payables_timing"],
                          {"by_supplier": by_sup, "names": names, "max_age": max_age, "bills": bills,
                           "max_days": int(p["max_days"])})]

    def r_liquidity(self, p):
        q = self.val("quick_ratio")
        runway = self.val("cash_runway")
        burn = self.val("net_burn")
        hit = (q is not None and q < D(p["quick_ratio_below"])) or (
            runway is not None and burn and burn > 0 and runway < D(p["runway_months_below"]))
        if not hit:
            return []
        ap_due = sum((r["amount_outstanding"] for r in self.rows("ap_open_items") if r.get("amount_outstanding")
                      and (r.get("due_date") or r.get("bill_date")) and
                      ((r.get("due_date") or r.get("bill_date")) - self.as_of).days <= 30), ZERO)
        recs = [self.rec("quick_ratio"), self.rec("cash_runway")]
        return [self.trig("rx_liquidity_pressure", "liquidity", "Near-term liquidity is tight",
                          self.base("rx_liquidity_pressure"), ap_due,
                          self.conf(*[r for r in recs if r]), [r["calc_id"] for r in recs if r],
                          {"quick_ratio": q, "runway": runway})]

    def r_partial(self, p):
        out = []
        dpo = self.rec("dpo")
        if dpo and dpo["readiness"] == "partial" and dpo.get("label") != "customer_provided":
            out.append(self.trig("rx_partial_metric_upgrade", "data_gap:credit_purchases_incl_tax",
                                 "DPO uses COGS because credit purchases are not available",
                                 self.base("rx_partial_metric_upgrade"), None,
                                 CONFIDENCE["ready"], [dpo["calc_id"]], {"key": "credit_purchases_incl_tax"}))
        rule = next((x for x in self.recon.get("rules", []) if x["rule_id"] == "rec_settlement_to_bank"), None)
        probable = [r for r in (rule or {}).get("records", []) if r["match_status"] == "probable_match"]
        if probable:
            sv = self.rec("settlement_variance")
            out.append(self.trig("rx_partial_metric_upgrade", "data_gap:probable_settlement_matches",
                                 "Settlement matches need customer confirmation",
                                 self.base("rx_partial_metric_upgrade"), None, CONFIDENCE["ready"],
                                 [sv["calc_id"] if sv else None], {"key": "probable_settlement_matches",
                                                                   "records": probable}))
        npf = self.rec("net_profit")
        if npf and npf["readiness"] == "needs_data" and any("No tax provision" in w for w in npf["warnings"]):
            out.append(self.trig("rx_partial_metric_upgrade", "data_gap:tax_provision",
                                 "Profit after tax not stated: no tax provision booked",
                                 self.base("rx_partial_metric_upgrade"), None, CONFIDENCE["ready"],
                                 [npf["calc_id"]], {"key": "tax_provision"}))
        cash = self.rec("cash_balance")
        if cash and cash.get("label") == "derived":
            out.append(self.trig("rx_partial_metric_upgrade", "data_gap:bank_statement",
                                 "Cash balance is a book figure without a bank statement",
                                 self.base("rx_partial_metric_upgrade"), None,
                                 CONFIDENCE["ready"], [cash["calc_id"]], {"key": "bank_statement"}))
        return out

    RULE_FUNCS = {"rx_critical_data_blockers": r_critical, "rx_overdue_receivables": r_overdue,
                  "rx_customer_concentration": r_concentration, "rx_settlement_shortfall": r_settlement,
                  "rx_bank_book_difference": r_bank_book, "rx_margin_decline": r_margin,
                  "rx_cost_category_spike": r_cost_spike, "rx_budget_overrun": r_budget,
                  "rx_msme_payables_timing": r_msme, "rx_liquidity_pressure": r_liquidity,
                  "rx_partial_metric_upgrade": r_partial}

    # ------------------------------------------------------------------ gates, requests, approvals
    def gate(self, cls):
        g = ACTION_GATES[cls]
        if g == "configurable":
            return self.cfg["approvals"]["connector_read"]
        return self.cfg["approvals"].get(cls, g) if g != "auto" else "auto"

    def data_request(self, inv, rule_id, source, dataset, target, filters, reason):
        fp = fingerprint("REQ", source, dataset, json.dumps(filters, sort_keys=True, default=str))
        rid = f"REQ-{fp}"
        if rid in self.requests:
            self.requests[rid]["subjects"].append(inv["subject"])
            return {"status": "shared", "request_id": rid}
        if len(self.requests) >= int(self.limits["max_data_requests"]):
            raise LimitReached("max_data_requests")
        gate = self.gate("connector_read")
        if self.round_no > int(self.limits["max_reflex_rounds"]):
            status = "not_requested_round_limit"
        elif gate == "approval_required":
            status = "approved_requested" if self.approval_for(rid) else "pending_approval"
        else:
            status = "requested"
        self.requests[rid] = {"request_id": rid, "rule_id": rule_id, "subjects": [inv["subject"]],
                              "action_class": "connector_read", "gate": gate, "status": status,
                              "source_category": source, "dataset": dataset, "canonical_target": target,
                              "filters": filters, "reason": reason, "read_only": True,
                              "fulfil": "Use an already-authorised, read-only connector in this task, or ask the "
                                        "customer for the export; write it to the canonical target and re-run "
                                        "with --reflex-round incremented."}
        if gate == "approval_required":
            self.approval_request(inv, rule_id, rid, "connector_read", f"Read {dataset} from {source}", reason,
                                  "The agent retrieves the data read-only and re-runs the analysis.", "plugin_reads")
        return {"status": status, "request_id": rid}

    def approval_for(self, approval_id):
        return self.approved.get(approval_id)

    def approval_request(self, inv, rule_id, action_id, cls, scope, reason, on_approval, execution):
        aid = action_id if action_id.startswith("REQ-") else f"APR-{fingerprint(rule_id, inv['subject'], action_id)}"
        if aid in self.approval_requests:
            return self.approval_requests[aid]
        if aid in self.approved:
            status = "approved_prepared" if cls in ("external_action", "financial_write") else "approved"
        elif aid in self.rejected:
            status = "rejected"
        else:
            status = "pending_approval"
        req = {"approval_id": aid, "rule_id": rule_id, "subject": inv["subject"], "action_id": action_id,
               "action_class": cls, "gate": "approval_required", "scope": scope, "reason": reason,
               "on_approval": on_approval, "execution": execution, "expires": "end_of_task", "status": status}
        self.approval_requests[aid] = req
        return req

    def prepare(self, req, filename, content):
        """Write a draft/proposal ONLY for an approved request; never sends or executes anything."""
        if req["status"] != "approved_prepared":
            return None
        folder = os.path.join(self.out_dir, "prepared")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, filename)
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(content)
        item = {"file": f"prepared/{filename}", "approval_id": req["approval_id"], "action_class": req["action_class"],
                "execution": req["execution"], "status": "prepared_not_sent" if req["action_class"] ==
                "external_action" else "prepared_customer_executes"}
        self.prepared.append(item)
        req["prepared_file"] = item["file"]
        return item

    # ------------------------------------------------------------------ charts
    def chart(self, chart_id, ctype, title, subtitle, series, alt, unit="money", groups=None, series_names=None):
        if chart_id in self.charts:
            return chart_id
        if len(self.charts) >= int(self.limits["max_charts"]):
            raise LimitReached("max_charts")
        for s in series:
            s["value_label"] = chart_label(s["value"], s.get("unit", unit))
        for g in groups or []:
            for it in g["items"]:
                it["value_label"] = chart_label(it["value"], it.get("unit", unit))
        spec = {"chart_id": chart_id, "type": ctype, "title": title, "subtitle": subtitle, "unit": unit,
                "series": series, "groups": groups or [], "series_names": series_names or [], "alt": alt,
                "source": f"Source: calculation register, run period {self.cur['label']}; values bound to calc_ids.",
                "svg": f"charts/{chart_id}.svg"}
        folder = os.path.join(self.out_dir, "charts")
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, f"{chart_id}.svg"), "w", encoding="utf-8") as fh:
            fh.write(render_svg(spec))
        write_json(os.path.join(folder, f"{chart_id}.json"), spec)
        self.charts[chart_id] = spec
        return chart_id

    # ------------------------------------------------------------------ playbooks
    def run_playbook(self, inv):
        c = inv["calc"]
        for t in inv["triggers"]:
            fn = getattr(self, f"pb_{t['rule_id']}")
            fn(inv, t, c)

    def act(self, inv, action_id, cls, fn):
        if len(inv["actions"]) >= int(self.limits["max_actions_per_trigger"]):
            self.deferred.append({"subject": inv["subject"], "action_id": action_id, "reason": "max_actions_per_trigger"})
            return None
        if time.monotonic() - self.t0 > float(self.limits["max_runtime_seconds"]):
            self.deferred.append({"subject": inv["subject"], "action_id": action_id, "reason": "max_runtime_seconds"})
            return None
        entry = {"action_id": action_id, "action_class": cls, "gate": self.gate(cls), "status": "done"}
        try:
            res = fn() or {}
            entry.update(res)
        except LimitReached as exc:
            entry["status"] = "deferred"
            entry["reason"] = f"limit_reached:{exc}"
            self.deferred.append({"subject": inv["subject"], "action_id": action_id, "reason": f"limit_reached:{exc}"})
        inv["actions"].append(entry)
        return entry

    def insight(self, inv, text, refs, evidence_class="fact"):
        refs = [r for r in refs if r]
        if evidence_class == "fact":
            # a fact that relies on a partial figure is not a verified finding (report_generation evidence_classes)
            for ref in refs:
                rec = next((x for x in self.reg.records if x["calc_id"] == ref), None)
                if rec is None and ref.startswith("metric:"):
                    mid, _, dims = ref[7:].partition("[")
                    dd = dict(p.split("=", 1) for p in dims.rstrip("]").split(",") if "=" in p)
                    rec = self.rec(mid, **dd)
                if rec is not None and rec["readiness"] != "ready":
                    evidence_class = "fact_with_limitations"
        inv["insights"].append({"text": text, "refs": refs, "label": "auto-generated",
                                "evidence_class": evidence_class})

    def recommend(self, inv, rule_id, title, rationale, impact_text, impact_calc, effort, refs, approval_id=None,
                  review=False, confidence=None, impact_basis="measured"):
        amt = None
        if impact_calc:
            r = next((x for x in self.reg.records if x["calc_id"] == impact_calc), None)
            amt = abs(Decimal(r["value"])) if r and r["value"] is not None else None
        inv["recommendations"].append({"rule_id": rule_id, "title": title, "rationale": rationale,
                                       "impact": impact_text, "impact_calc_id": impact_calc, "impact_amount": amt,
                                       "effort": effort, "refs": [r for r in refs if r], "approval_id": approval_id,
                                       "professional_review_needed": review, "impact_basis": impact_basis,
                                       "confidence_value": confidence if confidence is not None
                                       else inv["confidence"]})

    def pb_rx_critical_data_blockers(self, inv, t, c):
        blocked = sorted({r["metric_id"] for r in self.reg.records if r["readiness"] == "blocked"})
        self.act(inv, "summarise_blocked_metrics", "local_read", lambda: {"blocked_metrics": blocked})
        ids = ", ".join(t["facts"]["issue_ids"])
        self.act(inv, "request_corrected_export", "connector_read", lambda: self.data_request(
            inv, t["rule_id"], "accounting system or customer export", "corrected source export",
            "the dataset named in the issue", {"issues": t["facts"]["issue_ids"]},
            f"Critical issues {ids} block dependent metrics; a corrected export is needed."))
        self.insight(inv, f"Critical data issues ({ids}) block {len(blocked)} metric(s); figures that depend on them "
                          f"are withheld rather than estimated.", t["evidence"], "data_gap")
        self.recommend(inv, t["rule_id"], "Re-export the affected source data and re-run the analysis",
                       f"Critical issues {ids} prevent reliable figures.", "Unblocks the withheld metrics.", None,
                       "low", t["evidence"], confidence=CONFIDENCE["ready"], impact_basis="none")

    def pb_rx_overdue_receivables(self, inv, t, c):
        f = t["facts"]
        thr = str(f["threshold"])
        total = self.val("ar_aging", bucket="total")
        kinds = ["ar_open_items"]

        def compute():
            c["over"] = self.add_calc("rx_ar_overdue_total", f["over"], "money",
                                      "sum(amount_outstanding where as_of - due_date > threshold_days)", kinds,
                                      {"threshold_days": thr}, {"as_of": self.cur["end"]})
            c["share"] = self.add_calc("rx_ar_overdue_share", f["over"] / total, "percent",
                                       "rx_ar_overdue_total / total open receivables", kinds,
                                       {"threshold_days": thr})
            c["by_cust"] = {}
            for cid in sorted(f["by_customer"], key=lambda k: (-f["by_customer"][k], k)):
                lines = [r["_line"] for r in self.rows("ar_open_items") if r.get("customer_id") == cid and
                         (r.get("due_date") or r.get("invoice_date")) and
                         (self.as_of - (r.get("due_date") or r.get("invoice_date"))).days > f["threshold"]]
                c["by_cust"][cid] = self.add_calc("rx_ar_overdue_by_customer", f["by_customer"][cid], "money",
                                                  "rx_ar_overdue_total grouped by customer", kinds,
                                                  {"customer_id": cid, "threshold_days": thr},
                                                  {"name": f["names"][cid], "source_rows": lines})
            return {"calc_ids": [c["over"], c["share"]] + list(c["by_cust"].values())}
        self.act(inv, "compute_overdue_by_customer", "local_compute", compute)

        def shares():
            sales = self.rows("sales_lines")
            if not sales:
                return {"status": "skipped", "reason": "sales_lines.csv not provided"}
            s, e = _dt.date.fromisoformat(self.cur["start"]), self.as_of
            per = {}
            for r in sales:
                if r.get("invoice_date") and s <= r["invoice_date"] <= e:
                    per[r.get("customer_id")] = per.get(r.get("customer_id"), ZERO) + (r.get("taxable_value") or ZERO)
            tot = sum(per.values(), ZERO)
            ids = []
            for cid in f["by_customer"]:
                if tot:
                    ids.append(self.add_calc("rx_customer_revenue_share", per.get(cid, ZERO) / tot, "percent",
                                             "customer taxable sales / total sales register", ["sales_lines"],
                                             {"customer_id": cid}, {"name": f["names"][cid]}))
            c["cust_share"] = dict(zip(f["by_customer"], ids))
            return {"calc_ids": ids}
        self.act(inv, "read_customer_revenue_share", "local_read", shares)

        def scen():
            cash = self.val("cash_balance")
            dso_rec = self.rec("dso")
            ids = []
            if cash is not None:
                c["scn_cash"] = self.add_calc("scn_collect_overdue_cash", cash + f["over"], "money",
                                              "cash_balance + rx_ar_overdue_total", ["bank_transactions",
                                                                                     "ar_open_items"],
                                              params={"assumption": "Overdue receivables collected in full; "
                                                                    "nothing else changes.",
                                                      "evidence_class": "upper_bound"}, scenario=True)
                ids.append(c["scn_cash"])
            tbp = tb_periods(self.data).get(self.cur["label"])
            denom = D((dso_rec or {}).get("parameters", {}).get("denominator") or 0) if dso_rec else ZERO
            if tbp and dso_rec and dso_rec["value"] is not None and denom:
                ar_o = sum((natural(r, "opening") for r in tbp["rows"] if r.get("account_class") == "trade_receivables"),
                           ZERO)
                ar_c = sum((natural(r, "closing") for r in tbp["rows"] if r.get("account_class") == "trade_receivables"),
                           ZERO)
                new_dso = (ar_o + ar_c - f["over"]) / 2 / denom * self.days
                c["scn_dso"] = self.add_calc("scn_collect_overdue_dso", new_dso, "days",
                                             "((opening AR + closing AR - overdue) / 2) / credit_sales * days",
                                             ["trial_balance", "ar_open_items", "sales_lines"], scenario=True,
                                             readiness=dso_rec["readiness"])
                c["scn_dso_change"] = self.add_calc("scn_collect_overdue_dso_change", new_dso - Decimal(dso_rec["value"]),
                                                    "days", "scn_collect_overdue_dso - dso",
                                                    ["trial_balance", "ar_open_items", "sales_lines"], scenario=True,
                                                    readiness=dso_rec["readiness"])
                ids += [c["scn_dso"], c["scn_dso_change"]]
            return {"calc_ids": ids}
        self.act(inv, "scenario_collect_overdue", "scenario", scen)
        self.act(inv, "scenario_dso_reduction", "scenario", lambda: self._dso_release(c))

        def chart():
            series = []
            for b, lbl in BUCKET_LABELS.items():
                r = self.rec("ar_aging", bucket=b)
                if r and r["value"] is not None:
                    series.append({"label": lbl, "calc_id": r["calc_id"], "value": r["value"]})
            return {"chart_ids": [self.chart("rx-ar-aging", "aging_stacked_bar", "Receivables by days past due",
                                             f"Open receivables at {self.cur['end']}", series,
                                             "Stacked bar of open receivables by aging bucket.")]}
        self.act(inv, "chart_ar_aging", "chart", chart)
        top = next(iter(c.get("by_cust", {})), None)
        apr = self.approval_request(inv, t["rule_id"], "external_draft_collection_reminders", "external_action",
                                    "Draft payment reminder emails to customers with invoices more than "
                                    f"{thr} days past due", "Overdue receivables are material.",
                                    "The plugin prepares draft reminders in prepared/; nothing is sent until you "
                                    "send it or approve sending separately.", "plugin_prepares_draft")
        self.act(inv, "external_draft_collection_reminders", "external_action",
                 lambda: {"status": apr["status"], "approval_id": apr["approval_id"],
                          **({"prepared": self._prepare_reminders(apr, f)} if apr["status"] == "approved_prepared"
                             else {})})
        if c.get("over"):
            name = f["names"].get(top, top) if top else None
            txt = (f"{{{{calc:{c['over']}}}}} of receivables ({{{{calc:{c['share']}}}}}) is more than {thr} days past "
                   f"due")
            refs = [c["over"], c["share"]]
            if top and c["by_cust"].get(top):
                txt += f"; the largest amount is with {name} ({{{{calc:{c['by_cust'][top]}}}}})"
                refs.append(c["by_cust"][top])
            self.insight(inv, txt + ".", refs, "fact")
            est, erefs = [], []
            if c.get("scn_cash"):
                est.append(f"collecting it in full would raise cash to {{{{calc:{c['scn_cash']}}}}}")
                erefs.append(c["scn_cash"])
            if c.get("scn_dso"):
                est.append(f"DSO would be {{{{calc:{c['scn_dso']}}}}} instead of {{{{metric:dso}}}}")
                erefs += [c["scn_dso"], "metric:dso"]
            if est:
                self.insight(inv, "Scenario (receivables): " + "; ".join(est) + ".", erefs, "estimate")
            self.recommend(inv, t["rule_id"], f"Collect receivables more than {thr} days past due"
                           + (f", starting with {name}" if name else ""),
                           f"They total {{{{calc:{c['over']}}}}} and older balances are harder to recover.",
                           f"Up to {{{{calc:{c['over']}}}}} of cash if collected in full (upper bound).", c["over"], "low",
                           [c["over"]] + ([c["by_cust"][top]] if top else []), approval_id=apr["approval_id"],
                           impact_basis="upper_bound")

    def _dso_release(self, c):
        dso_rec = self.rec("dso")
        denom = D((dso_rec or {}).get("parameters", {}).get("denominator") or 0) if dso_rec else ZERO
        if not dso_rec or not denom:
            return {"status": "skipped", "reason": "DSO denominator not available"}
        days = D(self.cfg.get("scenario_parameters", {}).get("dso_reduction_days", 10))
        c["scn_release"] = self.add_calc("scn_dso_reduction_cash_release", days * denom / self.days, "money",
                                         "dso_reduction_days * credit_sales_incl_tax / days(period)",
                                         ["trial_balance", "sales_lines"], {"dso_reduction_days": str(days)},
                                         scenario=True, readiness=dso_rec["readiness"])
        return {"calc_ids": [c["scn_release"]]}

    def _prepare_reminders(self, apr, f):
        lines = ["# Draft payment reminders (NOT SENT)", "",
                 "Prepared by the Finance Analyst plugin after your approval "
                 f"{apr['approval_id']}. Review and send from your own email; nothing has been sent.", ""]
        thr = f["threshold"]
        for r in self.rows("ar_open_items"):
            ref = r.get("due_date") or r.get("invoice_date")
            if ref and (self.as_of - ref).days > thr and r.get("amount_outstanding"):
                lines += [f"## {r.get('customer_name') or r.get('customer_id')}", "",
                          f"Dear {r.get('customer_name') or 'Customer'},", "",
                          f"Our records show invoice {r.get('invoice_number')} dated {r.get('invoice_date')} with "
                          f"{fmt_money(r['amount_outstanding'])} outstanding, due on {ref}. We would be grateful if "
                          "you could arrange payment or let us know of any query.", "", "Regards,", ""]
        return self.prepare(apr, "collection_reminders.md", "\n".join(lines))

    def pb_rx_customer_concentration(self, inv, t, c):
        cid, name = t["facts"]["customer_id"], t["facts"]["name"]

        def shares():
            recs = sorted((x for x in self.reg.records if x["metric_id"] == "revenue_by_customer" and x["value"]
                           and x["period"]["label"] == self.cur["label"]),
                          key=lambda x: (-Decimal(x["value"]), x["dimension"]["customer_id"]))[:10]
            total = sum((Decimal(x["value"]) for x in self.reg.records if x["metric_id"] == "revenue_by_customer"
                         and x["value"] and x["period"]["label"] == self.cur["label"]), ZERO)
            c["shares"] = []
            for x in recs:
                k = x["dimension"]["customer_id"]
                nm = (x.get("parameters") or {}).get("name") or k
                c["shares"].append((k, nm, self.add_calc("rx_customer_revenue_share", Decimal(x["value"]) / total,
                                                         "percent", "customer taxable sales / total sales register",
                                                         ["sales_lines"], {"customer_id": k}, {"name": nm})))
            return {"calc_ids": [s[2] for s in c["shares"]]}
        self.act(inv, "compute_top_customer_shares", "local_compute", shares)

        def open_ar():
            rows = [r for r in self.rows("ar_open_items") if r.get("customer_id") == cid]
            if not rows:
                return {"status": "skipped", "reason": "no open receivables for the customer"}
            c["open_ar"] = self.add_calc("rx_customer_open_receivables",
                                         sum((r.get("amount_outstanding") or ZERO for r in rows), ZERO), "money",
                                         "sum(amount_outstanding) for the customer", ["ar_open_items"],
                                         {"customer_id": cid}, {"name": name,
                                                                "source_rows": [r["_line"] for r in rows]})
            return {"calc_ids": [c["open_ar"]]}
        self.act(inv, "compute_top_customer_open_receivables", "local_compute", open_ar)

        def chart():
            series = [{"label": k, "calc_id": cid_, "value": next(x["value"] for x in self.reg.records
                                                                   if x["calc_id"] == cid_), "unit": "percent"}
                      for k, _, cid_ in c.get("shares", [])]
            return {"chart_ids": [self.chart("rx-customer-pareto", "pareto_chart", "Customer concentration",
                                             "Share of sales register value by customer with cumulative line",
                                             series, "Pareto chart of customer revenue shares.", unit="percent")]}
        self.act(inv, "chart_customer_pareto", "chart", chart)
        share_id = next((s[2] for s in c.get("shares", []) if s[0] == cid), None)
        if share_id:
            txt = f"{name} accounts for {{{{calc:{share_id}}}}} of sales register value"
            refs = [share_id]
            if c.get("open_ar"):
                txt += f"; open receivables from {name} are {{{{calc:{c['open_ar']}}}}}"
                refs.append(c["open_ar"])
            self.insight(inv, txt + ".", refs)
            self.recommend(inv, t["rule_id"], f"Review credit terms and dependence on {name}",
                           f"{name} is {{{{calc:{share_id}}}}} of sales; a delay or loss would hit revenue and cash.",
                           (f"Exposure in open receivables {{{{calc:{c['open_ar']}}}}}." if c.get("open_ar")
                            else "Reduces concentration risk."), c.get("open_ar"), "high", refs,
                           impact_basis="exposure")

    def pb_rx_settlement_shortfall(self, inv, t, c):
        rec = t["facts"]["record"]
        sid = rec["settlement_id"]
        st_rows = {r.get("settlement_id"): r for r in self.rows("settlements")}
        srow = st_rows.get(sid, {})

        def compute():
            c.setdefault("unlocated", {})
            c["unlocated"][sid] = self.add_calc("rx_settlement_unlocated", t["amount"], "money",
                                                "expected net not located in bank credits", ["settlements",
                                                                                             "bank_transactions"],
                                                {"settlement_id": sid}, {"provider": rec.get("provider"),
                                                                         "match_status": rec["match_status"],
                                                                         "nature": t["facts"]["nature"],
                                                                         "source_rows": [srow["_line"]] if srow else []})
            ids = [c["unlocated"][sid]]
            if srow.get("settlement_date"):
                c.setdefault("days", {})[sid] = self.add_calc(
                    "rx_settlement_days_unlocated", Decimal((self.as_of - srow["settlement_date"]).days), "days",
                    "as_of - settlement_date", ["settlements"], {"settlement_id": sid})
                ids.append(c["days"][sid])
            return {"calc_ids": ids}
        self.act(inv, "compute_unlocated_settlements", "local_compute", compute)

        def components():
            s, e = _dt.date.fromisoformat(self.cur["start"]), self.as_of
            rows = [r for r in self.rows("settlements") if r.get("settlement_date") and s <= r["settlement_date"] <= e]
            ids = {}
            for comp in ("gross_amount", "fees", "tax_on_fees", "refunds", "withholdings", "adjustments",
                         "net_amount"):
                ids[comp] = self.add_calc("rx_settlement_component", sum((r.get(comp) or ZERO for r in rows), ZERO),
                                          "money", f"sum({comp}) of settlements in the period", ["settlements"],
                                          {"component": comp})
            c["components"] = ids
            return {"calc_ids": list(ids.values())}
        self.act(inv, "compute_settlement_components", "local_compute", components)

        def scen():
            cash = self.val("cash_balance")
            if cash is None:
                return {"status": "skipped", "reason": "cash balance not available"}
            total = self._all_unlocated()
            c["scn_recovery"] = self.add_calc("scn_settlement_recovery_cash", cash + total, "money",
                                              "cash_balance + sum(unlocated settlements)",
                                              ["bank_transactions", "settlements"], scenario=True,
                                              params={"assumption": "All unlocated settlements are received.",
                                                      "evidence_class": "upper_bound"})
            return {"calc_ids": [c["scn_recovery"]]}
        self.act(inv, "scenario_settlement_recovery", "scenario", scen)

        def chart():
            comp = c.get("components") or {}
            if not comp:
                return {"status": "skipped"}
            order = [("Gross", "gross_amount", 1), ("Fees (cost)", "fees", -1),
                     ("GST on fees (credit)", "tax_on_fees", -1), ("Refunds (reversal)", "refunds", -1),
                     ("TCS/TDS (tax credit)", "withholdings", -1), ("Adjustments", "adjustments", 1)]
            nature = {"gross_amount": "revenue", "fees": "selling_cost", "tax_on_fees": "recoverable_tax_credit",
                      "refunds": "revenue_reversal", "withholdings": "recoverable_tax_credit",
                      "adjustments": "requires_explanation", "net_amount": "expected_net"}
            series = []
            for lbl, key, sign in order:
                r = next(x for x in self.reg.records if x["calc_id"] == comp[key])
                series.append({"label": lbl, "calc_id": comp[key], "value": format(Decimal(r["value"]) * sign, "f"),
                               "sign": sign, "kind": "total" if key == "gross_amount" else "step",
                               "nature": nature[key], "colour": "#7A8CA3" if nature[key] in
                               ("recoverable_tax_credit", "revenue_reversal") else None})
            series[0]["kind"] = "total"
            net = next(x for x in self.reg.records if x["calc_id"] == comp["net_amount"])
            series.append({"label": "Expected net", "calc_id": comp["net_amount"], "value": net["value"], "sign": 1,
                           "kind": "total", "nature": "expected_net"})
            return {"chart_ids": [self.chart("rx-settlement-waterfall", "waterfall_bridge",
                                             "Settlements: gross to expected net",
                                             "Grey-blue steps are recoverable tax credits or reversals, not losses",
                                             series, "Waterfall from gross settlement value to expected net; GST on "
                                                     "fees and TCS/TDS are recoverable credits.")]}
        self.act(inv, "chart_settlement_waterfall", "chart", chart)
        after = srow.get("settlement_date") or self.as_of
        self.act(inv, "connector_read_bank_after_period_end", "connector_read", lambda: self.data_request(
            inv, t["rule_id"], "bank statement or authorised bank connector", "bank_transactions",
            "bank_transactions.csv (append lines after the period end)",
            {"from": (self.as_of + _dt.timedelta(days=1)).isoformat(),
             "to": (after + _dt.timedelta(days=15)).isoformat(), "look_for_reference": rec.get("settlement_id")},
            f"Check whether settlement {sid} arrived after the period end (timing) or is missing."))
        apr = self.approval_request(inv, t["rule_id"], "external_draft_settlement_query", "external_action",
                                    f"Draft a query to {rec.get('provider')} about settlement {sid}",
                                    "Expected settlement not located in the bank data provided.",
                                    "The plugin prepares a draft query in prepared/; you send it.",
                                    "plugin_prepares_draft")
        self.act(inv, "external_draft_settlement_query", "external_action",
                 lambda: {"status": apr["status"], "approval_id": apr["approval_id"],
                          **({"prepared": self.prepare(apr, f"settlement_query_{sid}.md", (
                              f"# Draft settlement query (NOT SENT)\n\nApproval {apr['approval_id']}.\n\n"
                              f"Hello {rec.get('provider')} seller support,\n\nWe have not located settlement {sid} "
                              f"dated {srow.get('settlement_date')} with expected net {fmt_money(t['amount'])} in "
                              f"our bank account. Please confirm the payout status and the bank reference (UTR).\n\n"
                              "Regards,\n"))} if apr["status"] == "approved_prepared" else {})})
        u = c.get("unlocated", {}).get(sid)
        if u:
            nature, window = t["facts"]["nature"], t["facts"]["window"]
            txt = f"Settlement {sid} from {rec.get('provider')} with expected net {{{{calc:{u}}}}} was not located in " \
                  f"the bank data provided"
            refs = [u]
            if c.get("days", {}).get(sid):
                txt += f" ({{{{calc:{c['days'][sid]}}}}} after the settlement date at period end)"
                refs.append(c["days"][sid])
            if nature == "timing":
                txt += f". This is within the {window}-day timing window, so it is treated as a timing difference " \
                       "(possibly in transit), not a loss; later bank lines are requested."
            else:
                txt += f". It is beyond the {window}-day timing window: an unexplained shortfall that may be leakage " \
                       "and needs review; it is not a confirmed loss."
            self.insight(inv, txt, refs, "exception")
            if c.get("scn_recovery"):
                self.insight(inv, f"If all unlocated settlements are received, cash would be "
                                  f"{{{{calc:{c['scn_recovery']}}}}} (scenario).", [c["scn_recovery"]], "estimate")
            self.recommend(inv, t["rule_id"], f"Confirm receipt of settlement {sid} or raise a query with "
                           f"{rec.get('provider')}", f"Expected net {{{{calc:{u}}}}} is not in the bank data.",
                           f"Up to {{{{calc:{u}}}}} of cash if it is still outstanding (upper bound).", u, "low", [u],
                           approval_id=apr["approval_id"], impact_basis="upper_bound")

    def _all_unlocated(self):
        rule = next((x for x in self.recon.get("rules", []) if x["rule_id"] == "rec_settlement_to_bank"), None)
        total = ZERO
        for rec in (rule or {}).get("records", []):
            if rec["match_status"] == "unmatched":
                total += D(rec["expected_net"])
            elif rec["match_status"] == "conflicting" and rec.get("difference") is not None:
                total += abs(D(rec["difference"]))
        return total

    def pb_rx_bank_book_difference(self, inv, t, c):
        f = t["facts"]
        self.act(inv, "compute_bank_book_difference", "local_compute", lambda: {"calc_ids": [c.setdefault(
            "bb", self.add_calc("rx_bank_book_difference", f["difference"], "money",
                                "bank statement balance - book cash_and_cash_equivalents",
                                ["bank_transactions", "trial_balance"]))]})
        self.act(inv, "connector_read_bank_ledger_lines", "connector_read", lambda: self.data_request(
            inv, t["rule_id"], "accounting system (bank ledger)", "bank ledger lines (book side)",
            "journal_lines.csv (bank account lines) — used by the agent to prepare a BRS outside the verified report",
            {"from": (self.as_of - _dt.timedelta(days=15)).isoformat(),
             "to": (self.as_of + _dt.timedelta(days=15)).isoformat()},
            "Identify uncleared cheques, deposits in transit or unrecorded bank charges (toolkit v0.1 does not "
            "implement rec_accounting_to_bank)."))
        if c.get("bb"):
            self.insight(inv, f"The bank statement differs from the book balance by {{{{calc:{c['bb']}}}}} at period "
                              "end; book-side bank ledger lines are requested to explain it.", [c["bb"],
                                                                                              "CON-BANK-BOOK"],
                         "exception")
            self.recommend(inv, t["rule_id"], "Prepare the period-end bank reconciliation statement",
                           f"Bank and book differ by {{{{calc:{c['bb']}}}}}.",
                           "Confirms the cash figure used in this report.", c["bb"], "low", [c["bb"],
                                                                                             "CON-BANK-BOOK"],
                           impact_basis="measured")

    def pb_rx_margin_decline(self, inv, t, c):
        m = t["facts"]["metric"]

        def compute():
            c.setdefault("mchg", {})[m] = self.add_calc("rx_margin_change", t["facts"]["change"], "percent",
                                                        "margin[P] - margin[C]", ["trial_balance"], {"margin": m})
            return {"calc_ids": [c["mchg"][m]]}
        self.act(inv, "compute_margin_change", "local_compute", compute)

        def scen():
            if m != "gross_margin":
                return {"status": "skipped", "reason": "price scenario applies to gross margin"}
            cogs, nr, gm0 = self.val("cogs"), self.val("net_revenue"), self.val("gross_margin", "comparison")
            if None in (cogs, nr, gm0) or nr == 0 or gm0 >= 1:
                return {"status": "skipped", "reason": "inputs not available"}
            c["scn_price"] = self.add_calc("scn_margin_restoration_price_increase", cogs / (1 - gm0) / nr - 1,
                                           "percent", "cogs / (1 - comparison gross_margin) / net_revenue - 1",
                                           ["trial_balance"], scenario=True,
                                           params={"assumption": "Volumes and costs unchanged.",
                                                   "evidence_class": "scenario"})
            return {"calc_ids": [c["scn_price"]]}
        self.act(inv, "scenario_margin_restoration", "scenario", scen)

        def chart():
            groups = []
            for mm in ("gross_margin", "ebitda_margin", "operating_margin", "net_margin"):
                a, b = self.rec(mm), self.rec(mm, "comparison")
                if a and b and a["value"] is not None and b["value"] is not None:
                    groups.append({"label": mm.replace("_", " ").capitalize(), "items": [
                        {"series": self.cur["label"], "calc_id": a["calc_id"], "value": a["value"]},
                        {"series": self.cmp["label"], "calc_id": b["calc_id"], "value": b["value"]}]})
            return {"chart_ids": [self.chart("rx-margins", "bar_comparison", "Margins vs comparison period",
                                             f"{self.cur['label']} vs {self.cmp['label']}", [],
                                             "Grouped bars comparing margins.", unit="percent", groups=groups,
                                             series_names=[self.cur["label"], self.cmp["label"]])]}
        self.act(inv, "chart_margin_comparison", "chart", chart)
        if c.get("mchg", {}).get(m):
            txt = f"{m.replace('_', ' ').capitalize()} changed by {{{{calc:{c['mchg'][m]}}}}} against the comparison " \
                  "period"
            refs = [c["mchg"][m]]
            self.insight(inv, txt + ".", refs, "fact")
            if m == "gross_margin" and c.get("scn_price"):
                self.insight(inv, f"Scenario (pricing): restoring gross margin with prices alone, volumes and costs "
                                  f"unchanged, would need an increase of {{{{calc:{c['scn_price']}}}}}.",
                             [c["scn_price"]], "estimate")
                refs.append(c["scn_price"])
            self.recommend(inv, t["rule_id"], "Review pricing, discounts and input costs to recover the margin",
                           f"Margin change {{{{calc:{c['mchg'][m]}}}}}.", "Recovers margin lost against the comparison "
                           "period.", None, "high", refs, impact_basis="none")

    def pb_rx_cost_category_spike(self, inv, t, c):
        f = t["facts"]
        cls = f["account_class"]
        rg = self.val("revenue_growth")

        def compute():
            c.setdefault("gap", {})[cls] = self.add_calc("rx_cost_growth_gap", f["growth"] - rg, "percent",
                                                         "category growth - revenue_growth", ["trial_balance"],
                                                         {"account_class": cls})
            return {"calc_ids": [c["gap"][cls]]}
        self.act(inv, "compute_cost_growth_gap", "local_compute", compute)

        def scen():
            a = self.val("expense_by_category", account_class=cls)
            b = self.val("expense_by_category", "comparison", account_class=cls)
            if a is None or b is None:
                return {"status": "skipped", "reason": "category amounts not available"}
            c.setdefault("save", {})[cls] = self.add_calc(
                "scn_cost_normalisation_saving", a - b * (1 + rg), "money", "actual_k[P] - actual_k[C] * (1 + "
                "revenue_growth)", ["trial_balance"], {"account_class": cls}, scenario=True,
                params={"assumption": "Indicative gap between actual growth and revenue-proportional growth; not "
                                      "evidence that any reduction is achievable.", "evidence_class": "indicative"})
            return {"calc_ids": [c["save"][cls]]}
        self.act(inv, "scenario_cost_normalisation", "scenario", scen)

        def chart():
            series = []
            for r in self.reg.records:
                if r["metric_id"] == "rx_cost_growth_gap" and r["value"] is not None:
                    series.append({"label": r["dimension"]["account_class"].replace("_", " ").capitalize(),
                                   "calc_id": r["calc_id"], "value": r["value"], "unit": "percent",
                                   "unfavourable": Decimal(r["value"]) > 0})
            return {"chart_ids": [self.chart("rx-cost-growth-gaps", "variance_bar_diverging",
                                             "Cost growth above revenue growth",
                                             "Category growth minus revenue growth (percentage points)", series,
                                             "Diverging bars of cost growth gaps.", unit="percent")]}
        if "rx-cost-growth-gaps" not in self.post:
            self.post["rx-cost-growth-gaps"] = (inv, chart)
            self.act(inv, "chart_cost_growth_gaps", "chart",
                     lambda: {"status": "scheduled_after_investigations", "chart_ids": ["rx-cost-growth-gaps"]})
        self.act(inv, "connector_read_vendor_bills", "connector_read", lambda: self.data_request(
            inv, t["rule_id"], "accounting system (vendor bills)", "supplier_bills by vendor",
            "vendor-level drill-down (analysed by the agent; not a canonical file in v0.1)",
            {"account_class": cls, "periods": [self.cur["label"]] + ([self.cmp["label"]] if self.cmp else [])},
            f"Identify which vendors or contracts drove the increase in {cls.replace('_', ' ')}."))
        if c.get("gap", {}).get(cls):
            lbl = cls.replace("_", " ")
            txt = f"{lbl.capitalize()} grew {{{{calc:{c['gap'][cls]}}}}} faster than revenue (increase " \
                  f"{{{{metric:cost_category_variance[account_class={cls},measure=amount]}}}})"
            refs = [c["gap"][cls], f"metric:cost_category_variance[account_class={cls},measure=amount]"]
            self.insight(inv, txt + ".", refs, "fact")
            if c.get("save", {}).get(cls):
                self.insight(inv, f"Indicative only: {{{{calc:{c['save'][cls]}}}}} of the {lbl} increase is above what "
                                  "revenue growth alone would explain. This is not evidence that the amount can be "
                                  "reduced; vendor or contract evidence is needed.", [c["save"][cls]], "estimate")
                self.insight(inv, f"Hypothesis: the faster growth of {lbl} may reflect a rate or contract change rather "
                                  "than volume; vendor bills would confirm or reject this.",
                             [c["gap"][cls]], "hypothesis")
            self.recommend(inv, t["rule_id"], f"Review {lbl} spend and contracts",
                           f"{lbl.capitalize()} grew {{{{calc:{c['gap'][cls]}}}}} faster than revenue.",
                           (f"Indicative gap {{{{calc:{c['save'][cls]}}}}} above revenue-proportional growth; confirm "
                            "with vendor or contract evidence before treating any amount as recoverable."
                            if c.get("save", {}).get(cls) else "Brings the category back in line with revenue."),
                           c.get("save", {}).get(cls), "medium",
                           refs + ([c["save"][cls]] if c.get("save", {}).get(cls) else []), impact_basis="indicative")

    def pb_rx_budget_overrun(self, inv, t, c):
        cls = t["facts"]["account_class"]

        def compute():
            c.setdefault("short", {})[cls] = self.add_calc("rx_budget_shortfall", t["amount"], "money",
                                                           "abs(unfavourable budget variance)", ["trial_balance",
                                                                                                 "budget"],
                                                           {"account_class": cls})
            return {"calc_ids": [c["short"][cls]]}
        self.act(inv, "compute_budget_shortfall", "local_compute", compute)

        def chart():
            series = []
            for r in self.reg.records:
                d = r["dimension"] or {}
                if r["metric_id"] == "budget_variance" and d.get("measure") == "variance" and r["value"] is not None \
                        and d.get("account_class") != "all":
                    series.append({"label": d["account_class"].replace("_", " ").capitalize(), "calc_id": r["calc_id"],
                                   "value": r["value"],
                                   "unfavourable": (r.get("parameters") or {}).get("favourability") == "unfavourable"})
            return {"chart_ids": [self.chart("rx-budget-variance", "variance_bar_diverging", "Budget variance by line",
                                             "Actual minus budget (orange = unfavourable)", series,
                                             "Diverging bars of budget variances.")]}
        self.act(inv, "chart_budget_variance", "chart", chart)
        if c.get("short", {}).get(cls):
            lbl = cls.replace("_", " ")
            revenue = cls in ("revenue_from_operations", "other_operating_revenue")
            self.insight(inv, f"{lbl.capitalize()} is {{{{calc:{c['short'][cls]}}}}} "
                              f"{'below' if revenue else 'above'} budget "
                              f"({{{{metric:budget_variance[account_class={cls},measure=variance_pct]}}}}).",
                         [c["short"][cls], f"metric:budget_variance[account_class={cls},measure=variance_pct]"])
            self.recommend(inv, t["rule_id"], ("Close the revenue gap to budget" if revenue else
                                               f"Bring {lbl} back within budget"),
                           f"Unfavourable by {{{{calc:{c['short'][cls]}}}}}.",
                           f"{{{{calc:{c['short'][cls]}}}}} against plan (measured).", c["short"][cls], "medium",
                           [c["short"][cls]], impact_basis="measured")

    def pb_rx_msme_payables_timing(self, inv, t, c):
        f = t["facts"]

        def compute():
            c["msme_total"] = self.add_calc("rx_msme_overdue_total", t["amount"], "money",
                                            "sum(outstanding) for micro/small suppliers beyond max_days",
                                            ["ap_open_items"], {"max_days": str(f["max_days"])})
            ids = [c["msme_total"]]
            for sid in sorted(f["by_supplier"]):
                ids.append(self.add_calc("rx_msme_overdue_by_supplier", f["by_supplier"][sid], "money",
                                         "rx_msme_overdue_total grouped by supplier", ["ap_open_items"],
                                         {"supplier_id": sid, "max_days": str(f["max_days"])},
                                         {"name": f["names"][sid], "source_rows": [r["_line"] for r in f["bills"]
                                                                                    if r.get("supplier_id") == sid]}))
            c["msme_days"] = self.add_calc("rx_msme_max_days", Decimal(f["max_age"]), "days", "max(as_of - bill_date)",
                                           ["ap_open_items"], {"max_days": str(f["max_days"])})
            return {"calc_ids": ids + [c["msme_days"]]}
        self.act(inv, "compute_msme_overdue", "local_compute", compute)

        def scen():
            cash = self.val("cash_balance")
            if cash is None:
                return {"status": "skipped", "reason": "cash balance not available"}
            c["scn_msme"] = self.add_calc("scn_msme_clearance_cash_after", cash - t["amount"], "money",
                                          "cash_balance - rx_msme_overdue_total", ["bank_transactions",
                                                                                   "ap_open_items"], scenario=True,
                                          params={"assumption": "All flagged MSME bills paid now.",
                                                  "evidence_class": "scenario"})
            return {"calc_ids": [c["scn_msme"]]}
        self.act(inv, "scenario_msme_clearance", "scenario", scen)
        apr = self.approval_request(inv, t["rule_id"], "financial_prepare_payment_proposal", "financial_write",
                                    "Prepare a payment proposal for MSME bills beyond the statutory period",
                                    "MSME payment-timing flag (review with your Chartered Accountant).",
                                    "The plugin prepares prepared/msme_payment_proposal.csv. It never makes payments; "
                                    "you execute any payment in your own bank.", "customer_executes")

        def proposal():
            out = {"status": apr["status"], "approval_id": apr["approval_id"], "execution": "customer"}
            if apr["status"] == "approved_prepared":
                import io
                buf = io.StringIO()
                w = csv.writer(buf)
                w.writerow(["supplier_id", "supplier_name", "bill_number", "bill_date", "days_outstanding",
                            "amount_outstanding", "note"])
                for r in f["bills"]:
                    w.writerow([r.get("supplier_id"), r.get("supplier_name"), r.get("bill_number"), r.get("bill_date"),
                                (self.as_of - r["bill_date"]).days, format(r["amount_outstanding"], "f"),
                                "Proposal only - execute in your bank after review"])
                out["prepared"] = self.prepare(apr, "msme_payment_proposal.csv", buf.getvalue())
            return out
        self.act(inv, "financial_prepare_payment_proposal", "financial_write", proposal)
        if c.get("msme_total"):
            txt = f"Bills of {{{{calc:{c['msme_total']}}}}} from suppliers classified micro/small are outstanding " \
                  f"beyond {f['max_days']} days (oldest {{{{calc:{c['msme_days']}}}}})"
            refs = [c["msme_total"], c["msme_days"], "check:ai_msme_payables_timing"]
            self.insight(inv, txt + ".", refs, "fact")
            if c.get("scn_msme"):
                self.insight(inv, f"Scenario (MSME bills): paying them now would leave cash at "
                                  f"{{{{calc:{c['scn_msme']}}}}}.", [c["scn_msme"]], "estimate")
                refs.append(c["scn_msme"])
            self.recommend(inv, t["rule_id"], "Review and schedule payment of MSME supplier bills beyond 45 days",
                           f"{{{{calc:{c['msme_total']}}}}} is outstanding beyond the period; payment timing can "
                           "affect tax deductions.", f"Exposure {{{{calc:{c['msme_total']}}}}}.", c["msme_total"],
                           "low", refs, approval_id=apr["approval_id"], review=True, impact_basis="exposure")

    def pb_rx_liquidity_pressure(self, inv, t, c):
        def compute():
            due = sum((r["amount_outstanding"] for r in self.rows("ap_open_items") if r.get("amount_outstanding")
                       and (r.get("due_date") or r.get("bill_date"))
                       and ((r.get("due_date") or r.get("bill_date")) - self.as_of).days <= 30), ZERO)
            rec = sum((r["amount_outstanding"] for r in self.rows("ar_open_items") if r.get("amount_outstanding")
                       and r.get("due_date") and 0 < (r["due_date"] - self.as_of).days <= 30), ZERO)
            cash = self.val("cash_balance")
            c["obl"] = self.add_calc("rx_near_term_obligations", due, "money", "open payables due within 30 days "
                                     "(incl. overdue)", ["ap_open_items"])
            c["rcp"] = self.add_calc("rx_near_term_receipts", rec, "money", "open receivables due within 30 days",
                                     ["ar_open_items"])
            ids = [c["obl"], c["rcp"]]
            if cash is not None and due:
                c["cov"] = self.add_calc("rx_near_term_coverage", (cash + rec) / due, "ratio",
                                         "(cash_balance + near-term receipts) / near-term obligations",
                                         ["bank_transactions", "ar_open_items", "ap_open_items"])
                ids.append(c["cov"])
            return {"calc_ids": ids}
        self.act(inv, "compute_near_term_coverage", "local_compute", compute)
        self.act(inv, "scenario_dso_reduction", "scenario", lambda: self._dso_release(c))
        refs = [r for r in t["evidence"]]
        txt = "Liquidity is tight: quick ratio {{metric:quick_ratio}}"
        if c.get("cov"):
            txt += f"; cash plus receipts due in 30 days cover near-term payables {{{{calc:{c['cov']}}}}} times"
            refs.append(c["cov"])
        self.insight(inv, txt + ".", refs + ["metric:quick_ratio"], "fact")
        if c.get("scn_release"):
            self.recommend(inv, t["rule_id"], "Protect near-term liquidity: accelerate collections and phase payments",
                           "Near-term cover is limited.", f"Scenario: reducing DSO by 10 days would release "
                           f"{{{{calc:{c['scn_release']}}}}}.", c["scn_release"], "medium",
                           refs + [c["scn_release"]], impact_basis="scenario")

    def pb_rx_partial_metric_upgrade(self, inv, t, c):
        key = t["facts"]["key"]
        if key == "credit_purchases_incl_tax":
            self.act(inv, "connector_read_missing_input", "connector_read", lambda: self.data_request(
                inv, t["rule_id"], "accounting system (purchase register)", "credit purchases including GST",
                "run_config.json: credit_purchases_incl_tax", {"period": self.cur["label"]},
                "Makes DPO and the cash conversion cycle ready instead of partial."))
            self.insight(inv, "DPO uses COGS as its denominator; a purchase register would make DPO and the cash "
                              "conversion cycle exact.", t["evidence"] + ["metric:dpo"], "data_gap")
        elif key == "probable_settlement_matches":
            ids = ", ".join(r["settlement_id"] for r in t["facts"]["records"])
            apr = self.approval_request(inv, t["rule_id"], "customer_confirm_probable_matches", "customer_confirmation",
                                        f"Confirm probable settlement-to-bank matches: {ids}",
                                        "Probable matches (exact amount within the date window, no UTR) are not "
                                        "treated as confirmed without your decision.",
                                        "Add the confirmed ids to run_config.reconciliation.customer_confirmed_matches "
                                        "and re-run.", "customer_decides")
            self.act(inv, "customer_confirm_probable_matches", "customer_confirmation",
                     lambda: {"status": apr["status"], "approval_id": apr["approval_id"]})
            self.insight(inv, f"Settlement match(es) {ids} are probable, not confirmed; your confirmation would make "
                              "the settlement variance ready.", t["evidence"] + ["metric:settlement_variance"], "data_gap")
        elif key == "tax_provision":
            self.act(inv, "connector_read_missing_input", "connector_read", lambda: self.data_request(
                inv, t["rule_id"], "accounting system or Chartered Accountant", "tax provision for the period",
                "trial_balance.csv (current_tax / deferred_tax lines)", {"period": self.cur["label"]},
                "Net profit is before tax because no provision is booked; tax is never estimated."))
            self.insight(inv, "Profit after tax is not stated because no tax provision is booked; profit before tax is "
                              "shown under its own label.", t["evidence"], "data_gap")
        elif key == "bank_statement":
            self.act(inv, "connector_read_missing_input", "connector_read", lambda: self.data_request(
                inv, t["rule_id"], "bank statement or authorised bank connector", "bank_transactions",
                "bank_transactions.csv", {"period": self.cur["label"]},
                "Cash is a book balance; a statement verifies it."))
            self.insight(inv, "The cash figure is a book balance not yet verified against a bank statement.",
                         t["evidence"], "data_gap")

    # ------------------------------------------------------------------ orchestration
    def load_acknowledged(self):
        path = self.cfg["deduplication"].get("acknowledged_file")
        if not path:
            return {}
        try:
            data = read_json(path)
        except (OSError, ValueError):
            self.config_warnings.append({"code": "FA-I-RFX-002", "message": f"acknowledged file not readable: {path}"})
            return {}
        return {a["fingerprint"]: a for a in data.get("acknowledged", [])}

    def evaluate(self):
        triggers, evaluated = [], []
        for rid in RULE_IDS:
            rc = self.rule_cfg(rid)
            if not rc.get("enabled", True):
                evaluated.append({"rule_id": rid, "status": "disabled", "triggers": 0})
                continue
            found = self.RULE_FUNCS[rid](self, rc.get("params", {}))
            evaluated.append({"rule_id": rid, "status": "evaluated", "triggers": len(found)})
            triggers.extend(found)
        return triggers, evaluated

    def filter(self, triggers):
        min_sev = SEVERITIES.index(self.cfg["min_severity"])
        min_conf = D(self.cfg["min_confidence"])
        ack = self.load_acknowledged()
        reopen = D(self.cfg["deduplication"].get("reopen_if_worsened_pct", "0.20"))
        seen, accepted = set(), []
        for t in triggers:
            if t["fingerprint"] in seen:
                self.suppressed.append(dict(self._public(t), reason="duplicate_fingerprint"))
                continue
            seen.add(t["fingerprint"])
            if SEVERITIES.index(t["severity"]) < min_sev:
                self.suppressed.append(dict(self._public(t), reason="below_min_severity"))
                continue
            if t["confidence"] < min_conf:
                self.suppressed.append(dict(self._public(t), reason="below_min_confidence"))
                continue
            a = ack.get(t["fingerprint"])
            if a:
                prev = a.get("amount")
                if prev is not None and t["amount"] is not None and t["amount"] >= D(prev) * (1 + reopen):
                    t["reopened"] = f"worsened since acknowledgement on {a.get('acknowledged_at')}"
                else:
                    self.suppressed.append(dict(self._public(t), reason="acknowledged",
                                                acknowledged_at=a.get("acknowledged_at")))
                    continue
            accepted.append(t)
        return accepted

    def merge(self, triggers):
        invs = {}
        for t in triggers:
            key = t["subject"] if self.cfg["deduplication"].get("merge_same_subject", True) else t["fingerprint"]
            inv = invs.get(key)
            if inv is None:
                inv = {"investigation_id": f"INV-{fingerprint('INV', key, self.cur['label'])[:8]}",
                       "subject": t["subject"], "triggers": [], "rules": [], "severity": t["severity"],
                       "confidence": t["confidence"], "amount": t["amount"], "actions": [], "calc": {},
                       "insights": [], "recommendations": []}
                invs[key] = inv
            inv["triggers"].append(t)
            inv["rules"].append(t["rule_id"])
            if SEVERITIES.index(t["severity"]) > SEVERITIES.index(inv["severity"]):
                inv["severity"] = t["severity"]
            inv["confidence"] = min(inv["confidence"], t["confidence"])
            if t["amount"] is not None and (inv["amount"] is None or t["amount"] > inv["amount"]):
                inv["amount"] = t["amount"]
        out = list(invs.values())
        out.sort(key=lambda i: (-SEVERITIES.index(i["severity"]), -(i["amount"] or 0), -i["confidence"],
                                RULE_IDS.index(i["rules"][0]), i["subject"]))
        return out

    @staticmethod
    def _public(t):
        return {k: v for k, v in t.items() if k != "facts"}

    def score(self, rec):
        pr = self.cfg["prioritisation"]
        opex = self.val("operating_expenses")
        months = self.days / Decimal("30.4375")
        monthly = (opex / months) if opex else None
        amt = rec["impact_amount"]
        if rec.get("impact_basis") in ("indicative", "none"):
            amt = None  # indicative figures never drive priority as if they were achievable amounts
        if amt is not None and monthly and amt >= D(pr["impact_high_share_of_monthly_opex"]) * monthly:
            impact = "high"
        elif amt is not None and amt >= self.floor:
            impact = "medium"
        else:
            impact = "low"
        cv = rec["confidence_value"]
        conf = "high" if cv >= Decimal("0.80") else ("medium" if cv >= Decimal("0.55") else "low")
        scores = {"high": 3, "medium": 2, "low": 1}
        p = Decimal(scores[impact]) * D(pr["confidence_scores"][conf]) / Decimal(pr["effort_scores"][rec["effort"]])
        rec.update(impact_level=impact, confidence=conf, priority_score=p.quantize(Decimal("0.01")))
        return rec

    def run(self):
        if not self.cfg.get("enabled", True):
            return {"enabled": False, "config_warnings": self.config_warnings}
        triggers, evaluated = self.evaluate()
        accepted = self.filter(triggers)
        invs = self.merge(accepted)
        limit = int(self.limits["max_triggers"])
        run_invs, deferred_invs = invs[:limit], invs[limit:]
        for inv in deferred_invs:
            self.deferred.append({"subject": inv["subject"], "rules": inv["rules"], "severity": inv["severity"],
                                  "reason": "limit_reached:max_triggers"})
        for inv in run_invs:
            self.run_playbook(inv)
        for chart_id, (inv, fn) in self.post.items():  # aggregate charts drawn after all investigations
            entry = next(a for a in inv["actions"] if a.get("chart_ids") == [chart_id])
            try:
                entry.update(fn() or {}, status="done")
            except LimitReached as exc:
                entry.update(status="deferred", reason=f"limit_reached:{exc}")
                self.deferred.append({"subject": inv["subject"], "action_id": entry["action_id"],
                                      "reason": f"limit_reached:{exc}"})
        recs = []
        for inv in run_invs:
            for r in inv["recommendations"]:
                recs.append(self.score(dict(r, investigation_id=inv["investigation_id"])))
        recs.sort(key=lambda r: (-r["priority_score"], -(r["impact_amount"] or 0), r["title"]))
        for i, r in enumerate(recs, 1):
            r["rank"] = i
            r["recommendation_id"] = f"RXR-{i:03d}"
        out_invs = []
        for inv in run_invs:
            out_invs.append({"investigation_id": inv["investigation_id"], "subject": inv["subject"],
                             "rules": inv["rules"], "severity": inv["severity"], "confidence": inv["confidence"],
                             "amount": inv["amount"], "triggers": [self._public(t) for t in inv["triggers"]],
                             "actions": inv["actions"], "insights": inv["insights"]})
        warnings = list(self.config_warnings)
        if self.deferred:
            warnings.append({"code": "FA-W-RFX-001", "message": f"{len(self.deferred)} item(s) deferred by execution "
                                                                f"limits"})
        if self.suppressed:
            warnings.append({"code": "FA-I-RFX-002", "message": f"{len(self.suppressed)} trigger(s) suppressed"})
        return {"enabled": True, "spec_section": "reflex_engine", "round": self.round_no,
                "config": {k: self.cfg[k] for k in ("min_severity", "min_confidence", "execution_limits",
                                                    "deduplication", "approvals")},
                "rules_evaluated": evaluated, "triggers_found": len(triggers),
                "investigations": out_invs, "recommendations": recs, "suppressed": self.suppressed,
                "deferred": self.deferred, "data_requests": list(self.requests.values()),
                "approval_requests": list(self.approval_requests.values()), "prepared": self.prepared,
                "charts": [{"chart_id": k, "type": v["type"], "title": v["title"], "svg": v["svg"],
                            "json": f"charts/{k}.json"} for k, v in self.charts.items()],
                "derived_calcs": self.n_derived, "scenario_calcs": self.n_scen, "warnings": warnings}


def clear_outputs(out_dir):
    for sub in ("charts", "prepared"):
        folder = os.path.join(out_dir, sub)
        if os.path.isdir(folder):
            for name in os.listdir(folder):
                path = os.path.join(folder, name)
                if os.path.isfile(path):
                    os.remove(path)


def run_reflex(data, run_cfg, reg, issues, recon, out_dir, approvals=None, round_no=1):
    clear_outputs(out_dir)
    return Reflex(data, run_cfg, reg, issues, recon, out_dir, approvals, round_no).run()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--input-dir", required=True)
    ap.add_argument("--approvals")
    ap.add_argument("--round", type=int, default=1)
    a = ap.parse_args(argv)
    from fa_data import load_inputs
    cfg = read_json(os.path.join(a.run_dir, "run_config.json"))
    reg = CalcRegister()
    reg.records = [r for r in read_json(os.path.join(a.run_dir, "calc_register.json"))
                   if (r.get("parameters") or {}).get("reflex") is None]
    approvals = read_json(a.approvals) if a.approvals else None
    res = run_reflex(load_inputs(a.input_dir), cfg, reg, read_json(os.path.join(a.run_dir, "issues.json")),
                     read_json(os.path.join(a.run_dir, "reconciliation.json")), a.run_dir, approvals, a.round)
    write_json(os.path.join(a.run_dir, "reflex.json"), res)
    write_json(os.path.join(a.run_dir, "calc_register.json"), reg.records)
    print(json.dumps({k: res.get(k) for k in ("triggers_found", "derived_calcs", "scenario_calcs")}, default=json_default))
    print("Note: re-render and verify with fa_run.py to include these results in a verified report.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
