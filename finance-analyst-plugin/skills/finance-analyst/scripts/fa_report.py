"""Render ONE combined Markdown report (§23) from the calculation register.

Every figure is inserted from the register by reference and recorded in a render
manifest so fa_verify.py can tie each printed value back to its calc_id.
Narrative (findings, recommendations, executive summary) is supplied by Claude in
narrative.json using placeholders: {{metric:net_revenue}}, {{metric:net_revenue@comparison}},
{{metric:ar_aging[bucket=181_365]}} or {{calc:CALC-0001}}. Assumptions that are not calculated (for example
a customer-provided target) use {{input:VALUE|SOURCE}}, rendered as "VALUE (SOURCE)".
Raw figures typed into narrative text are rejected by the verifier.
"""
from __future__ import annotations

import re
from decimal import Decimal

from fa_common import (SCALE_LABELS, STANDARD_DISCLAIMER, TOOLKIT_VERSION, choose_scale, fmt_value, now_ist)

PLACEHOLDER = re.compile(r"\{\{(calc|metric):([A-Za-z0-9_\-]+)(?:\[([^\]{}]+)\])?(?:@(current|comparison))?\}\}")
INPUT_PLACEHOLDER = re.compile(r"\{\{input:([^|{}]+)\|([^{}]+)\}\}")
READINESS_BADGE = {"ready": "ready", "partial": "partial ⚠", "needs_data": "needs data", "blocked": "blocked ⛔"}
METRIC_NAMES = {
    "gross_revenue": "Gross revenue", "sales_returns_and_allowances": "Sales returns & allowances",
    "net_revenue": "Net revenue", "cogs": "Cost of goods sold", "gross_profit": "Gross profit",
    "gross_margin": "Gross margin", "operating_expenses": "Operating expenses (excl. D&A)", "ebitda": "EBITDA",
    "ebitda_margin": "EBITDA margin", "operating_profit": "Operating profit", "operating_margin": "Operating margin",
    "profit_before_tax": "Profit before tax", "net_profit": "Net profit", "net_margin": "Net margin",
    "effective_tax_rate": "Effective tax rate (books)", "revenue_growth": "Revenue growth",
    "expense_growth": "Operating expense growth", "cost_to_revenue_ratio": "Cost-to-revenue ratio",
    "cash_balance": "Cash and bank balance", "current_ratio": "Current ratio", "quick_ratio": "Quick ratio",
    "working_capital": "Working capital", "accounts_receivable": "Trade receivables",
    "accounts_payable": "Trade payables", "inventory_value": "Inventory", "inventory_turnover": "Inventory turnover",
    "dso": "Days sales outstanding", "dpo": "Days payables outstanding", "dio": "Days inventory outstanding",
    "cash_conversion_cycle": "Cash conversion cycle", "outstanding_debt": "Outstanding borrowings",
    "finance_costs": "Finance costs", "interest_coverage_ratio": "Interest coverage",
    "debt_to_equity": "Debt-to-equity", "net_burn": "Average monthly net burn", "cash_runway": "Cash runway",
    "settlement_variance": "Settlement variance", "marketplace_fees": "Marketplace / gateway fees",
    "customer_concentration": "Customer concentration", "ar_aging": "Receivables aging", "ap_aging": "Payables aging",
    "budget_variance": "Budget variance", "expense_by_category": "Expenses by category",
    "cost_category_variance": "Cost category variance", "period_over_period_variance": "Change vs comparison",
    "revenue_by_customer": "Revenue by customer", "revenue_by_product": "Revenue by product",
    "revenue_by_channel": "Revenue by channel",
}
BUCKET_LABELS = {"not_due": "Not due", "1_30": "1–30 days", "31_60": "31–60 days", "61_90": "61–90 days",
                 "91_180": "91–180 days", "181_365": "181–365 days", "over_365": "Over 365 days", "total": "Total"}
KPI_ORDER = ["net_revenue", "revenue_growth", "gross_margin", "ebitda_margin", "net_profit", "net_margin",
             "cash_balance", "current_ratio", "dso", "cash_conversion_cycle", "debt_to_equity", "cash_runway"]


def parse_dims(text):
    """'bucket=181_365,measure=amount' -> {'bucket': '181_365', 'measure': 'amount'}."""
    out = {}
    for part in (text or "").split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    return out


class Renderer:
    def __init__(self, register, config):
        self.reg = register
        self.config = config
        self.by_id = {r["calc_id"]: r for r in register}
        self.manifest = []
        self.cur = config["current_period"]["label"]
        self.cmpl = (config.get("comparison_period") or {}).get("label")
        self.out_dir = None

    # ------------------------------------------------------------ lookups
    def find(self, metric_id, period=None, **dims):
        period = period or self.cur
        for r in self.reg:
            if r["metric_id"] != metric_id or (r["period"] or {}).get("label") != period:
                continue
            d = r["dimension"] or {}
            if dims:
                if all(d.get(k) == v for k, v in dims.items()):
                    return r
            elif not d:
                return r
        return None

    def rows(self, metric_id, period=None):
        period = period or self.cur
        return [r for r in self.reg if r["metric_id"] == metric_id and (r["period"] or {}).get("label") == period]

    # ------------------------------------------------------------ formatting
    def cell(self, rec, mode="narrative", scale="units", context=""):
        if rec is None:
            return "—"
        note = (rec.get("parameters") or {}).get("result_note")
        if rec["value"] is None:
            text = {"not_meaningful": "N/M", "not_applicable": "N/A"}.get(note) or READINESS_BADGE.get(
                rec["readiness"], "n/a")
        else:
            text = fmt_value(Decimal(rec["value"]), rec["unit"], mode=mode, scale=scale)
        self.manifest.append({"calc_id": rec["calc_id"], "rendered": text, "mode": mode, "scale": scale,
                              "context": context})
        if rec["readiness"] == "partial" and rec["value"] is not None:
            text += " ⚠"
        return text

    def substitute(self, text, context):
        text = INPUT_PLACEHOLDER.sub(lambda m: f"{m.group(1).strip()} ({m.group(2).strip()})", text)

        def repl(m):
            kind, key, dims, which = m.group(1), m.group(2), m.group(3), m.group(4) or "current"
            if kind == "calc":
                rec = self.by_id.get(key)
            else:
                rec = self.find(key, self.cur if which == "current" else self.cmpl, **parse_dims(dims))
            if rec is None:
                self.manifest.append({"calc_id": None, "rendered": "[unresolved]", "placeholder": m.group(0),
                                      "context": context})
                return "[unresolved reference]"
            return self.cell(rec, "narrative", context=context)
        return PLACEHOLDER.sub(repl, text)

    # ------------------------------------------------------------ sections
    def money_table(self, header, lines, periods):
        """lines: list of (label, metric_id, dims). periods: list of (title, label)."""
        recs = [[self.find(m, p, **(d or {})) for (_, p) in periods] for (_, m, d) in lines]
        values = [Decimal(r["value"]) for row in recs for r in row if r and r["value"] is not None
                  and r["unit"] == "money"]
        scale = choose_scale(values)
        out = [f"| {header} ({SCALE_LABELS[scale]}) | " + " | ".join(t for t, _ in periods) + " |",
               "|---|" + "---:|" * len(periods)]
        for (label, _, _), row in zip(lines, recs):
            cells = []
            for r in row:
                if r is not None and r["unit"] == "money":
                    cells.append(self.cell(r, "table", scale, context=f"table:{header}:{label}"))
                else:
                    cells.append(self.cell(r, "narrative", context=f"table:{header}:{label}"))
            out.append(f"| {label} | " + " | ".join(cells) + " |")
        return out

    def kpi_section(self):
        out = ["## Key metrics", "", "| Metric | " + self.cur + (f" | {self.cmpl}" if self.cmpl else "")
               + " | Readiness |", "|---|---:|" + ("---:|" if self.cmpl else "") + "---|"]
        for m in KPI_ORDER:
            r = self.find(m)
            if r is None:
                continue
            row = f"| {METRIC_NAMES.get(m, m)} | {self.cell(r, context='kpi')}"
            if self.cmpl:
                c = self.find(m, self.cmpl)
                row += f" | {self.cell(c, context='kpi') if c else '—'}"
            row += f" | {READINESS_BADGE[r['readiness']]} |"
            out.append(row)
        return out + [""]

    def pnl_section(self):
        lines = [("Gross revenue", "gross_revenue", None), ("Less: returns & allowances",
                                                            "sales_returns_and_allowances", None),
                 ("Net revenue", "net_revenue", None), ("Cost of goods sold", "cogs", None),
                 ("Gross profit", "gross_profit", None), ("Operating expenses (excl. D&A)", "operating_expenses", None),
                 ("EBITDA", "ebitda", None), ("Operating profit", "operating_profit", None),
                 ("Profit before tax", "profit_before_tax", None), ("Net profit", "net_profit", None)]
        if self.find("net_revenue") is None:
            return []
        periods = [(self.cur, self.cur)] + ([(self.cmpl, self.cmpl)] if self.cmpl else [])
        out = ["## Profit and loss", ""] + self.money_table("Line", lines, periods)
        if self.cmpl:
            var_lines = [(lbl, "period_over_period_variance", {"line": m, "measure": "amount"}) for lbl, m, _ in lines]
            out += ["", f"Change vs {self.cmpl}:", ""] + self.money_table("Line", var_lines, [("Change", self.cur)])
            pct = ["| Line | Change % |", "|---|---:|"]
            for lbl, m, _ in lines:
                r = self.find("period_over_period_variance", line=m, measure="percent")
                pct.append(f"| {lbl} | {self.cell(r, context='pnl_pct')} |")
            out += [""] + pct
        margins = ["", "| Margin | " + self.cur + (f" | {self.cmpl}" if self.cmpl else "") + " |",
                   "|---|---:|" + ("---:|" if self.cmpl else "")]
        for m in ("gross_margin", "ebitda_margin", "operating_margin", "net_margin", "cost_to_revenue_ratio"):
            row = f"| {METRIC_NAMES[m]} | {self.cell(self.find(m), context='margins')}"
            if self.cmpl:
                row += f" | {self.cell(self.find(m, self.cmpl), context='margins')}"
            margins.append(row + " |")
        return out + margins + [""]

    def expenses_section(self):
        rows = [r for r in self.rows("expense_by_category")]
        if not rows:
            return []
        lines = [(r["dimension"]["account_class"].replace("_", " ").capitalize(), "expense_by_category",
                  {"account_class": r["dimension"]["account_class"]}) for r in rows]
        periods = [(self.cur, self.cur)] + ([(self.cmpl, self.cmpl)] if self.cmpl else [])
        return ["## Expenses by category", ""] + self.money_table("Category", lines, periods) + [""]

    def balance_section(self):
        if self.find("current_ratio") is None:
            return []
        lines = [("Cash and bank (statement)", "cash_balance", None), ("Trade receivables", "accounts_receivable", None),
                 ("Inventory", "inventory_value", None), ("Trade payables", "accounts_payable", None),
                 ("Working capital", "working_capital", None),
                 ("Operating working capital", "working_capital", {"variant": "operating"}),
                 ("Outstanding borrowings", "outstanding_debt", None)]
        out = ["## Liquidity, working capital and debt", ""] + self.money_table(
            "Balance at " + self.config["current_period"]["end"], lines, [("Amount", self.cur)])
        out += ["", "| Indicator | Value | Readiness |", "|---|---:|---|"]
        for m in ("current_ratio", "quick_ratio", "dso", "dio", "dpo", "cash_conversion_cycle", "inventory_turnover",
                  "interest_coverage_ratio", "debt_to_equity", "net_burn", "cash_runway"):
            r = self.find(m)
            if r is not None:
                out.append(f"| {METRIC_NAMES[m]} | {self.cell(r, context='liquidity')} | "
                           f"{READINESS_BADGE[r['readiness']]} |")
        return out + [""]

    def aging_section(self):
        out = []
        for metric, title in (("ar_aging", "Receivables aging"), ("ap_aging", "Payables aging")):
            if self.find(metric, bucket="total") is None or self.find(metric, bucket="total")["value"] is None:
                continue
            lines = [(BUCKET_LABELS[b], metric, {"bucket": b}) for b in
                     ["not_due", "1_30", "31_60", "61_90", "91_180", "181_365", "over_365", "total"]]
            out += [f"## {title}", ""] + self.money_table("Bucket (days past due)", lines,
                                                         [("Outstanding", self.cur)]) + [""]
        return out

    def revenue_section(self):
        out = []
        for metric, field, title in (("revenue_by_customer", "customer_id", "Top customers"),
                                     ("revenue_by_product", "sku", "Top products"),
                                     ("revenue_by_channel", "channel", "Revenue by channel")):
            rows = [r for r in self.rows(metric) if r["dimension"] and field in r["dimension"]][:10]
            if not rows:
                continue
            lines = []
            for r in rows:
                key = r["dimension"][field]
                name = (r.get("parameters") or {}).get("name")
                lines.append((f"{name} ({key})" if name else key, metric, {field: key}))
            out += [f"## {title} (sales register, excl. GST)", ""] + self.money_table(
                "Item", lines, [("Value", self.cur)]) + [""]
        conc = [self.find("customer_concentration", measure=m) for m in
                ("top_1_share", "top_5_share", "top_10_share", "hhi")]
        if any(c and c["value"] is not None for c in conc):
            out += ["| Concentration | Value |", "|---|---:|"]
            for lbl, c in zip(("Top customer share", "Top 5 share", "Top 10 share", "HHI (0–10,000)"), conc):
                out.append(f"| {lbl} | {self.cell(c, context='concentration')} |")
            out.append("")
        return out

    def budget_section(self):
        rows = [r for r in self.rows("budget_variance") if (r["dimension"] or {}).get("measure") == "variance"
                and r["dimension"]["account_class"] != "all"]
        if not rows:
            return []
        out = ["## Budget vs actual", "", "| Line | Actual | Budget | Variance | Variance % | Assessment |",
               "|---|---:|---:|---:|---:|---|"]
        vals = [Decimal(r["value"]) for r in self.rows("budget_variance") if r["unit"] == "money" and r["value"]]
        scale = choose_scale(vals)
        out[2] = f"| Line ({SCALE_LABELS[scale]}) | Actual | Budget | Variance | Variance % | Assessment |"
        for r in rows:
            cls = r["dimension"]["account_class"]
            a = self.find("budget_variance", account_class=cls, measure="actual")
            b = self.find("budget_variance", account_class=cls, measure="budget")
            p = self.find("budget_variance", account_class=cls, measure="variance_pct")
            fav = (r.get("parameters") or {}).get("favourability") or "—"
            out.append(f"| {cls.replace('_', ' ').capitalize()} | {self.cell(a, 'table', scale, 'budget')} | "
                       f"{self.cell(b, 'table', scale, 'budget')} | {self.cell(r, 'table', scale, 'budget')} | "
                       f"{self.cell(p, context='budget')} | {fav} |")
        return out + [""]

    def settlement_section(self, recon):
        rule = next((x for x in recon.get("rules", []) if x["rule_id"] == "rec_settlement_to_bank"), None)
        if not rule or rule["status"] != "completed":
            return []
        out = ["## Settlements to bank", "", "| Settlement | Provider | Status | Basis |", "|---|---|---|---|"]
        for rec in rule["records"]:
            out.append(f"| {rec['settlement_id']} | {rec['provider']} | {rec['match_status'].replace('_', ' ')} | "
                       f"{'; '.join(rec['match_basis']) or '—'} |")
        sv = self.find("settlement_variance")
        fees = self.find("marketplace_fees", provider="all")
        out += ["", f"- Settlement variance (expected net not located or short): {self.cell(sv, context='settle')}",
                f"- Fees in settlements this period: {self.cell(fees, context='settle')}", ""]
        return out

    def conflicts_section(self, recon):
        if not recon.get("conflicts"):
            return []
        out = ["## Source conflicts", ""]
        for c in recon["conflicts"]:
            figs = "; ".join(f"{f['source']}: {fmt_value(Decimal(str(f['value'])), 'money')}" for f in c["figures"])
            out.append(f"- **{c['item']}** — {figs}. Difference "
                       f"{fmt_value(Decimal(str(c['aligned_difference'])), 'money')}; status {c['status']}. "
                       f"Used: {c['chosen_figure_source']}.")
        return out + [""]

    def issues_section(self, issues, depth):
        out = ["## Data quality and accounting integrity", ""]
        counts = {}
        for i in issues:
            counts[i["severity"]] = counts.get(i["severity"], 0) + 1
        out.append("Issues by severity: " + (", ".join(f"{k} {v}" for k, v in sorted(
            counts.items(), key=lambda kv: ["critical", "high", "medium", "low", "informational"].index(kv[0])))
            or "none") + ".")
        out.append("")
        shown = issues if depth == "comprehensive" else [i for i in issues if i["severity"] in ("critical", "high")]
        if shown:
            out += ["| Issue | Check | Severity | Description |", "|---|---|---|---|"]
            for i in shown:
                out.append(f"| {i['issue_id']} | {i['check_id']} | {i['severity']} | {i['description']} |")
            out.append("")
        return out

    def limitations_section(self):
        lim = [r for r in self.reg if r["readiness"] != "ready"]
        out = ["## Limitations — what could not be fully analysed", ""]
        if not lim:
            return out + ["All computed metrics are ready.", ""]
        seen = set()
        for r in lim:
            key = (r["metric_id"], r["readiness"], tuple(r["warnings"]))
            if key in seen:
                continue
            seen.add(key)
            dim = r["dimension"]
            dim_txt = f" [{', '.join(f'{k}={v}' for k, v in dim.items())}]" if dim else ""
            out.append(f"- {METRIC_NAMES.get(r['metric_id'], r['metric_id'])} (`{r['metric_id']}`{dim_txt}, "
                       f"{(r['period'] or {}).get('label')}): **{r['readiness'].replace('_', ' ')}** — "
                       f"{'; '.join(r['warnings']) or 'see register'}")
        return out + [""]

    def narrative_section(self, narrative):
        out = []
        findings = narrative.get("findings") or []
        recs = narrative.get("recommendations") or []
        out += ["## Findings", ""]
        if not findings:
            out += ["No narrative findings were supplied for this run; the tables above contain the verified "
                    "figures.", ""]
        for i, f in enumerate(findings, 1):
            label = f" *({f['label']})*" if f.get("label") and f["label"] != "fact" else ""
            refs = ", ".join(f.get("refs") or [])
            out.append(f"{i}. {self.substitute(f['statement'], f'finding:{i}')}{label} — evidence: {refs or 'none'}")
        out += ["", "## Recommendations", ""]
        if not recs:
            out += ["No recommendations were supplied for this run.", ""]
        for i, r in enumerate(recs, 1):
            out.append(f"### {i}. {self.substitute(r['title'], f'rec:{i}:title')}")
            out.append("")
            out.append(self.substitute(r.get("rationale", ""), f"rec:{i}:rationale"))
            if r.get("impact"):
                out.append(f"- Expected impact: {self.substitute(r['impact'], f'rec:{i}:impact')}")
            out.append(f"- Confidence: {r.get('confidence', 'not stated')}; effort: {r.get('effort', 'not stated')}")
            if r.get("professional_review_needed"):
                out.append("- Review with your Chartered Accountant before acting.")
            out.append(f"- Evidence: {', '.join(r.get('refs') or []) or 'none'}")
            out.append("")
        return out

    def reflex_section(self, rx, depth):
        if not rx or not rx.get("enabled"):
            return []
        by_id = self.by_id
        invs = rx.get("investigations", [])
        pending = [a for a in rx.get("approval_requests", []) if a["status"] == "pending_approval"]
        out = ["## Proactive insights (Reflex Engine)", "",
               f"Ran automatically after the analysis, inside this task only (no background monitoring). "
               f"Rules evaluated: {len(rx['rules_evaluated'])}; triggers found: {rx['triggers_found']}; investigated: "
               f"{len(invs)}; suppressed: {len(rx['suppressed'])}; deferred: {len(rx['deferred'])}; approvals "
               f"pending: {len(pending)}. Everything below was computed read-only from the data provided; nothing "
               "was sent, uploaded, paid or posted.", ""]
        for w in rx.get("warnings", []):
            if w["code"] == "FA-W-RFX-003":
                out += [f"> Note ({w['code']}): {w['message']}", ""]
        if invs:
            out += ["### Triggered findings", "", "| # | Finding | Rule(s) | Severity | Confidence |",
                    "|---|---|---|---|---|"]
            for i, inv in enumerate(invs, 1):
                titles = "; ".join(t["title"] for t in inv["triggers"])
                out.append(f"| {i} | {titles} | {', '.join(inv['rules'])} | {inv['severity']} | "
                           f"{Decimal(str(inv['confidence'])):.2f} |")
            out.append("")
            insights = [(inv, ins) for inv in invs for ins in inv["insights"]]
            if insights:
                out += ["### Insights (auto-generated)", ""]
                for n, (inv, ins) in enumerate(insights, 1):
                    out.append(f"{n}. {self.substitute(ins['text'], f'reflex:insight:{n}')} — evidence: "
                               f"{', '.join(ins['refs'])}")
                out.append("")
        scen = [r for r in self.reg if (r.get("parameters") or {}).get("reflex") == "scenario"]
        if scen:
            out += ["### Scenarios (deterministic what-ifs)", "", "| Scenario | Result | Formula / assumption |",
                    "|---|---:|---|"]
            for r in scen:
                dim = r["dimension"] or {}
                name = r["metric_id"] + (f" [{', '.join(f'{k}={v}' for k, v in dim.items())}]" if dim else "")
                note = (r.get("parameters") or {}).get("assumption") or r["formula_text"]
                out.append(f"| {name} | {self.cell(r, context='reflex:scenario')} | {note} |")
            out.append("")
        recs = rx.get("recommendations", [])
        if recs:
            out += ["### Prioritised actions (auto-generated)", "",
                    "| Rank | Action | Expected impact | Impact | Confidence | Effort | Priority | Approval |",
                    "|---|---|---|---|---|---|---:|---|"]
            for r in recs:
                apr = next((a for a in rx.get("approval_requests", []) if a["approval_id"] == r.get("approval_id")),
                           None)
                gate = f"{apr['approval_id']} ({apr['status'].replace('_', ' ')})" if apr else "not needed"
                review = " — review with your CA" if r.get("professional_review_needed") else ""
                out.append(f"| {r['rank']} | {r['title']}{review} | {self.substitute(r['impact'], 'reflex:rec')} | "
                           f"{r['impact_level']} | {r['confidence']} | {r['effort']} | {r['priority_score']} | {gate} |")
            out.append("")
        charts = rx.get("charts", [])
        if charts:
            out += ["### Charts", ""]
            for ch in charts:
                out.append(f"![{ch['title']}]({ch['svg']})")
                spec_series = self._chart_series(ch)
                if spec_series:
                    out.append("")
                    out.append("Data: " + "; ".join(f"{lbl} {self.cell(by_id.get(cid), context='reflex:chart')}"
                                                     for lbl, cid in spec_series if by_id.get(cid)))
                out.append("")
        reqs = rx.get("data_requests", [])
        if reqs:
            out += ["### Additional data requested (read-only)", ""]
            for q in reqs:
                out.append(f"- {q['request_id']} ({q['status'].replace('_', ' ')}): {q['dataset']} from "
                           f"{q['source_category']} → {q['canonical_target']}. {q['reason']}")
            out.append("")
        aprs = rx.get("approval_requests", [])
        if aprs:
            out += ["### Approvals needed before any external or financial action", ""]
            for a in aprs:
                out.append(f"- {a['approval_id']} ({a['action_class'].replace('_', ' ')}, "
                           f"{a['status'].replace('_', ' ')}): {a['scope']}. On approval: {a['on_approval']}")
            out.append("")
        if rx.get("prepared"):
            out += ["### Prepared after approval", ""]
            for p in rx["prepared"]:
                out.append(f"- `{p['file']}` for {p['approval_id']}: {p['status'].replace('_', ' ')}")
            out.append("")
        if rx.get("suppressed") or rx.get("deferred"):
            out += ["### Suppressed and deferred", ""]
            if depth == "comprehensive":
                for t in rx.get("suppressed", []):
                    out.append(f"- Suppressed: {t['title']} ({t['rule_id']}, {t['reason'].replace('_', ' ')})")
                for d in rx.get("deferred", []):
                    what = d.get("action_id") or ", ".join(d.get("rules", []))
                    out.append(f"- Deferred: {d['subject']} — {what} ({d['reason']})")
            else:
                out.append(f"{len(rx.get('suppressed', []))} suppressed and {len(rx.get('deferred', []))} deferred "
                           "item(s); see reflex.json or use comprehensive depth for the list.")
            out.append("")
        return out

    def _chart_series(self, ch):
        import json as _json
        import os as _os
        path = _os.path.join(self.out_dir or "", ch["json"]) if getattr(self, "out_dir", None) else None
        if not path or not _os.path.isfile(path):
            return []
        with open(path, encoding="utf-8") as fh:
            spec = _json.load(fh)
        pairs = [(s["label"], s["calc_id"]) for s in spec.get("series", [])]
        for g in spec.get("groups", []):
            pairs += [(f"{g['label']} {it['series']}", it["calc_id"]) for it in g["items"]]
        return pairs

    def render(self, issues, recon, sources, narrative, depth, run_id, spec_version, reflex=None):
        c = self.config
        out = [f"# {narrative.get('title') or 'Financial Analysis Report'} — {c.get('company_name', 'Company')}", "",
               f"Period: **{self.cur}** ({c['current_period']['start']} to {c['current_period']['end']})"
               + (f" compared with **{self.cmpl}**" if self.cmpl else "") +
               f" · Basis: {c.get('reporting_basis', 'accrual')} · Currency: {c.get('currency', 'INR')} · "
               f"Run {run_id} · Generated {now_ist()} (IST)", "",
               "Verification: VERIFICATION_STATUS_PLACEHOLDER", ""]
        out += ["## Executive summary", ""]
        es = narrative.get("executive_summary") or []
        if es:
            out += [f"- {self.substitute(t, f'exec:{i}')}" for i, t in enumerate(es, 1)] + [""]
        else:
            out += ["No narrative summary was supplied; key metrics follow.", ""]
        out += self.kpi_section()
        out += self.narrative_section(narrative)
        out += self.reflex_section(reflex, depth)
        out += self.pnl_section()
        if depth == "comprehensive":
            out += self.expenses_section()
        out += self.balance_section()
        out += self.aging_section()
        if depth == "comprehensive":
            out += self.revenue_section()
        out += self.budget_section()
        out += self.settlement_section(recon)
        out += self.conflicts_section(recon)
        out += self.issues_section(issues, depth)
        out += self.limitations_section()
        out += ["## Scope, sources and method", ""]
        out += [f"- `{s['file']}` ({s['dataset_type']}): {s['record_count_retrieved']} rows, "
                f"coverage {(s['date_coverage'] or {}).get('earliest', '—')} to "
                f"{(s['date_coverage'] or {}).get('latest', '—')}, SHA-256 {s['sha256'][:12]}…" for s in sources]
        out += ["", f"- Formulas: finance-analyst.yaml metrics.registry, formula_version 1.0; spec version "
                    f"{spec_version}; toolkit {TOOLKIT_VERSION}.",
                "- Amounts exclude GST unless stated. Tables state their scale. ⚠ marks a partial figure; see "
                "Limitations.",
                "- Materiality for highlighting movements: two of (≥ ₹25,000; ≥ 10% of base; ≥ 0.5% of net "
                "revenue) unless configured otherwise.", ""]
        if depth == "comprehensive":
            out += ["## Appendix — calculation register", "",
                    "| calc_id | metric | dimension | period | value | readiness |", "|---|---|---|---|---:|---|"]
            for r in self.reg:
                dim = ", ".join(f"{k}={v}" for k, v in (r["dimension"] or {}).items()) or "—"
                out.append(f"| {r['calc_id']} | {r['metric_id']} | {dim} | {(r['period'] or {}).get('label')} | "
                           f"{r['value'] if r['value'] is not None else '—'} | {r['readiness']} |")
            out.append("")
        out += ["## Disclaimer", "", STANDARD_DISCLAIMER,
                "GST and income-tax data checks test consistency between datasets only and do not confirm "
                "compliance or filing correctness. Items listed for review are screening results, not findings of "
                "wrongdoing.", ""]
        return "\n".join(out)


def render_report(register, issues, recon, sources, narrative, config, depth, run_id, spec_version, reflex=None,
                  out_dir=None):
    r = Renderer(register, config)
    r.out_dir = out_dir
    text = r.render(issues, recon, sources, narrative or {}, depth, run_id, spec_version, reflex)
    return text, r.manifest
