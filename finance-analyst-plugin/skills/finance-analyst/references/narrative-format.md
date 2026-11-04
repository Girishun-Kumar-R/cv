# Writing narrative.json

The narrative carries Claude's reasoning: executive summary, findings and recommendations. Figures never appear
as typed text; they are inserted from the calculation register when `fa_run.py --narrative` renders the report,
and `fa_verify.py` rejects typed money, percentages and lakh/crore amounts.

## Structure

```json
{
  "title": "Half-Year Financial Review",
  "executive_summary": ["Net revenue was {{metric:net_revenue}}, up {{metric:revenue_growth}}."],
  "findings": [
    {"statement": "Receivables of {{metric:ar_aging[bucket=181_365]}} are more than 180 days past due.",
     "refs": ["metric:ar_aging[bucket=181_365]"], "label": "fact"}
  ],
  "recommendations": [
    {"title": "Follow up the receivable more than 180 days past due",
     "rationale": "It is {{metric:ar_aging[bucket=181_365]}} from one customer.",
     "impact": "Up to {{metric:ar_aging[bucket=181_365]}} of cash if collected in full.",
     "refs": ["metric:ar_aging[bucket=181_365]"], "confidence": "medium", "effort": "low",
     "professional_review_needed": false}
  ]
}
```

A complete example is `examples/sample-sme/narrative.json`; a blank template is
`templates/narrative.template.json`.

## Placeholders

| Placeholder | Resolves to |
|---|---|
| `{{metric:ID}}` | Metric for the current period, no dimension |
| `{{metric:ID@comparison}}` | Same metric for the comparison period |
| `{{metric:ID[key=value,key2=value2]}}` | Dimensioned record, e.g. `ar_aging[bucket=91_180]`, `budget_variance[account_class=rent,measure=variance]`, `customer_concentration[measure=top_1_share]`, `revenue_by_customer[customer_id=C001]`, `period_over_period_variance[line=net_profit,measure=percent]` |
| `{{calc:CALC-0042}}` | A specific calculation (check its metric and dimension in `calc_register.json` first) |
| `{{input:VALUE|SOURCE}}` | A customer-supplied assumption, rendered "VALUE (SOURCE)", e.g. `{{input:10 days|customer target}}` |

Dimension keys and values are exactly those in `calc_register.json` (`bucket`: not_due, 1_30, 31_60, 61_90,
91_180, 181_365, over_365, total).

## Evidence references (`refs`)

Every finding and recommendation needs at least one valid reference:
- `metric:ID` or `metric:ID[key=value]` — a computed (not blocked/needs-data) register record;
- `CALC-NNNN` — a calculation id;
- `check:CHECK_ID` — an issue raised in this run (e.g. `check:ai_msme_payables_timing`);
- `ISS-NNNN` — a specific issue; `CON-BANK-BOOK`, `CON-SALES-LEDGER` — source-conflict records.
- Reflex figures can be cited like any metric, e.g. `metric:rx_ar_overdue_total[threshold_days=90]` with
  `{{metric:rx_ar_overdue_total[threshold_days=90]}}`, or `metric:scn_collect_overdue_cash` with
  `{{metric:scn_collect_overdue_cash}}`.

Each figure placeholder in an item must also appear in its `refs` (same metric). Do not cite a figure for a topic
it does not measure (the verifier warns when, for example, a receivables statement cites only revenue figures).

## Writing rules

- Lead with the answer; one idea per finding.
- Label each finding: `fact` (cites only ready, non-scenario figures), `limited` (relies on a partial figure),
  `estimate` (scenario or indicative figure), `hypothesis` (say how it could be confirmed), or `customer_provided`.
  The report groups them into Verified findings, Findings with stated limitations, Unresolved reconciliation
  exceptions, Estimates and scenarios, and Hypotheses; `ver_evidence_separation` rejects a `fact` that cites a
  scenario or a partial figure.
- Profit: always name the level — gross profit, EBITDA, operating profit, profit before tax, profit after tax
  (net profit) — and cite that metric. "Net profit" needs `net_profit` ready (tax provision booked).
  `ver_profit_labels` rejects "profit" alone and a level that does not match the cited figure.
- Savings: words like save, saving, cut costs or "cost X less" need `{{input:VALUE|SOURCE}}` from a customer,
  quote or contract. Mechanical or indicative figures (e.g. `scn_cost_normalisation_saving`) are gaps, not
  savings (`ver_savings_claims`).
- Leakage: GST on fees and TCS/TDS withheld are recoverable tax credits, refunds are revenue reversals, and
  settlements within the timing window are timing differences. Use "potential leakage" only when citing
  `settlement_variance[class=unexplained]` or an unexplained `rx_settlement_unlocated`
  (`ver_leakage_classification`).
- Use directional words that match the sign of the figure ("rose" only for a positive change).
- Recommendations: imperative and specific, tied to findings, with confidence, effort and whether a Chartered
  Accountant should review. No investment products, named lenders, tax positions or filing actions.
- Never write "compliant", "ready to file", "audit-ready", "guaranteed" or "risk-free".
- Never include unmasked PAN, Aadhaar, bank account or card numbers.
