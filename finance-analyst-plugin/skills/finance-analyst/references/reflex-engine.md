# Proactive Financial Reflex Engine — operating guide

Spec: `finance-analyst.yaml` section `reflex_engine` (v1.2.0) and workflow stage `proactive_reflex`.
Code: `scripts/fa_reflex.py` (engine), `scripts/fa_charts.py` (SVG charts). It runs automatically inside
`fa_run.py` after metrics are calculated, within the current task only — there is no scheduler, monitor, server or
background service.

## What happens on every `fa_run.py` run

1. **Detect** — 11 configurable rules evaluate the calculation register, issues and reconciliation:
   critical data blockers, overdue receivables, customer concentration, settlement shortfall, bank-vs-book
   difference, margin decline, cost-category spike, budget overrun, MSME payment timing, liquidity pressure,
   partial-metric upgrades.
2. **Filter** — severity (`min_severity`), confidence (`min_confidence`) and acknowledgements; duplicates by
   fingerprint are dropped; triggers on the same subject are merged into one investigation.
3. **Prioritise and limit** — severity, then amount, then confidence. Work beyond `execution_limits` is deferred
   and listed (never silently dropped).
4. **Investigate (automatic, read-only)** — local reads of provided data, derived calculations and scenarios
   (added to the calculation register as `rx_*` / `scn_*` records), charts in `<run>/charts/`.
5. **Gate** — additional connector data becomes a *data request*; anything external or financial becomes an
   *approval request*. Nothing is sent, uploaded, paid, posted or filed.
6. **Report** — insights, scenarios, prioritised actions, charts, data requests and approvals appear in the
   "Proactive insights (Reflex Engine)" section of the one combined report; `fa_verify.py` recomputes every
   reflex figure independently, checks chart data against the register (`ver_chart_data`) and checks gate
   integrity (`ver_approval_gates`).

Outputs: `<run>/reflex.json` (everything above), `<run>/charts/*.svg|json`, and `<run>/prepared/*` only for
approved items.

## Agent duties after a run

1. Read `<run>/reflex.json`: `investigations`, `recommendations`, `data_requests`, `approval_requests`,
   `deferred`, `suppressed`, `warnings`.
2. **Data requests** (`action_class: connector_read`, always read-only):
   - `status: requested` and `gate: auto_if_authorized` — fulfil it now **only if** a connector for that source is
     already authorised and has already been used in this task, the call is read-only, and it stays within the
     listed filters. Otherwise ask the customer for the export (one batched message).
   - `status: pending_approval` — the customer has tightened `connector_read`; ask first.
   - Write the result to the stated canonical target (`references/input-formats.md`), then re-run `fa_run.py`
     with `--reflex-round 2`. At most `max_reflex_rounds` (default 2) rounds per task; after that requests show
     `not_requested_round_limit` and are passed to the customer instead.
   - Targets marked "analysed by the agent" (vendor drill-downs, bank ledger lines for a BRS) are outside the
     verified toolkit: compute them with deterministic code, show the code's result as a separately labelled
     working, and do not merge those figures into the verified report.
3. **Approval requests** — present every `pending_approval` item once, together, in plain language: what it is,
   why, and exactly what happens on approval. Record the answer in an `approvals.json`:

   ```json
   {"approved": [{"approval_id": "APR-…", "approved_by": "customer", "approved_at": "2026-11-04T10:00:00+05:30",
                  "scope": "draft reminders only"}],
    "rejected": [{"approval_id": "APR-…", "reason": "will phone instead"}]}
   ```

   Re-run with `--approvals approvals.json`. Approved `external_action` items produce drafts marked NOT SENT in
   `prepared/`; sending them is a separate step the customer does (or explicitly approves for a connected mail
   tool as a draft). Approved `financial_write` items produce proposals only (e.g.
   `prepared/msme_payment_proposal.csv`); the customer executes payments in their own bank. The plugin never pays,
   posts, refunds or files. `customer_confirmation` items (e.g. probable settlement matches) are applied by adding
   the ids to `run_config.reconciliation.customer_confirmed_matches` and re-running.
4. **Narrative** — adopt, edit or drop the auto-generated insights and recommendations in `narrative.json`
   (same placeholder rules). Do not restate reflex figures as typed numbers.

## Configuration (`run_config.json` → `"reflex": {...}`)

Defaults are in `templates/reflex_rules.json` (identical to the spec; `fa_spec.py validate` checks this). Override
any key by deep merge, for example:

```json
"reflex": {
  "min_severity": "medium",
  "min_confidence": "0.60",
  "execution_limits": {"max_triggers": 6, "max_charts": 3},
  "deduplication": {"acknowledged_file": "/path/to/acknowledged.json", "reopen_if_worsened_pct": "0.25"},
  "approvals": {"connector_read": "approval_required"},
  "rules": {"rx_customer_concentration": {"params": {"top1_share_at_least": "0.40"}},
            "rx_liquidity_pressure": {"enabled": false},
            "rx_bank_book_difference": {"severity": "high"}}
}
```

- Thresholds are attention flags the customer can tune; they are not judgements of good or bad.
- `approvals.connector_read` may be `auto_if_authorized` (default) or `approval_required`.
- Gates for `restricted_read`, `customer_confirmation`, `external_action` and `financial_write` cannot be relaxed;
  attempts are ignored with warning `FA-W-RFX-003`, shown in the report.
- Acknowledged findings: `{"acknowledged": [{"fingerprint": "<from reflex.json>", "amount": "700000",
  "acknowledged_at": "2026-10-01"}]}`. They stay suppressed unless the amount worsens by
  `reopen_if_worsened_pct`.
- `--no-reflex` skips the engine for a run; base metrics are unaffected (reflex only appends to the register).

## Rule summary

| Rule | Fires when (defaults) | Investigation |
|---|---|---|
| rx_critical_data_blockers | any critical issue | list blocked metrics; request corrected export |
| rx_overdue_receivables | > 90 days past due ≥ 10% of receivables and ≥ ₹25,000 (high if ≥ 25%) | overdue by customer, customer revenue share, collect-overdue and DSO scenarios, aging chart, draft reminders (approval) |
| rx_customer_concentration | top customer ≥ 30% of sales register | top-customer shares, open receivables, Pareto chart |
| rx_settlement_shortfall | settlement unmatched/conflicting | unlocated amount and days, components, recovery scenario, waterfall, later bank lines (request), draft query (approval) |
| rx_bank_book_difference | statement ≠ book by ≥ ₹10 (high if ≥ ₹25,000) | difference, book-side bank ledger lines (request) |
| rx_margin_decline | gross or EBITDA margin down ≥ 1 point | margin change, price-restoration scenario, margin chart |
| rx_cost_category_spike | category growth − revenue growth ≥ 10 points and increase ≥ ₹25,000 | growth gap, normalisation saving, chart, vendor bills (request) |
| rx_budget_overrun | unfavourable ≥ ₹25,000 and (≥ 5% of budget or ≥ 1% of revenue) | shortfall, budget variance chart |
| rx_msme_payables_timing | micro/small supplier bills > 45 days | totals, oldest age, cash-after scenario, payment proposal (approval; customer executes) |
| rx_liquidity_pressure | quick ratio < 1.00 or runway < 6 months while burning | 30-day obligations vs cash + receipts, DSO-release scenario |
| rx_partial_metric_upgrade | key metric partial for a fixable reason | data request or customer confirmation |
