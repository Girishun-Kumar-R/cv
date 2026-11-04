# Implementation status — toolkit v0.2.0 against spec v1.2.0

Only the items marked **implemented** have working code in `scripts/` and automated tests in
`tests/test_toolkit.py`. Everything else is specified in `finance-analyst.yaml` but must not be described to the
customer as computed by this plugin.

Test run when packaged: 47 tests (24 toolkit + 23 reflex engine), all passing, on Python 3.11, 3.12 and 3.13
(Linux). Not tested inside the Claude Desktop or Cowork sandboxes themselves.

## Workflow stages

| Stage | How it is delivered | Status |
|---|---|---|
| Activation, capability discovery | SKILL.md instructions + `fa_spec.py list/section/validate` | implemented (instructions + spec tool) |
| Onboarding, connector selection, authorisation guidance | SKILL.md + `references/stage-playbook.md` (Claude conversation) | instructions only — no code needed |
| Data discovery (files) | `fa_discover.py` (CSV; XLSX when `openpyxl` is installed) | implemented, tested via manual run |
| Data discovery (connectors) | Claude uses the session's own connector tools, read-only | instructions only; depends on the customer's connectors |
| Requirements and readiness | Readiness per calculation in `fa_metrics.py`; planning by Claude from spec `data_requirements` | implemented for toolkit metrics |
| Normalisation and mapping | `fa_classify.py`, `fa_normalize.py` (Indian number formats, Dr/Cr, scale, minor units, day-first dates, two-snapshot trial balance) | implemented, tested |
| Validation (data quality + integrity) | `fa_checks.py` | implemented for the checks listed below |
| Reconciliation | `fa_reconcile.py` | implemented for the rules listed below |
| Metric calculation | `fa_metrics.py` (exact decimals, calculation register) | implemented for 48 metrics |
| Analysis, investigation, recommendations | Claude reasoning over the register, written to `narrative.json` | instructions + verifier enforcement |
| Proactive reflex (stage `proactive_reflex`) | `fa_reflex.py`: 11 rules, thresholds, dedup/merge, limits, approval gates, data requests, insights, prioritised actions | implemented, tested |
| Scenarios | 8 deterministic reflex scenarios (collect overdue, DSO reduction, settlement recovery, margin restoration, cost normalisation, MSME clearance) | implemented, tested; general scenario modelling **not implemented** |
| Charts | `fa_charts.py`: aging_stacked_bar, waterfall_bridge, variance_bar_diverging, pareto_chart, bar_comparison (SVG) | implemented for reflex charts, tested; other chart types **not implemented** |
| Forecasting, anomaly statistics | Spec only | **not implemented** |
| Combined report | `fa_report.py` (one Markdown report, simple/comprehensive) | implemented, tested |
| Independent verification | `fa_verify.py` (separate code path) | implemented, tested |
| Delivery | Chat summary + files; host tools for DOCX/PDF; email draft only with approval | instructions only |

## Metrics (48 implemented)

gross_revenue, sales_returns_and_allowances, net_revenue, revenue_growth, cogs, gross_profit, gross_margin,
operating_expenses, expense_by_category, cost_category_variance, expense_growth, cost_to_revenue_ratio, ebitda,
ebitda_margin, operating_profit, operating_margin, profit_before_tax, net_profit, net_margin, effective_tax_rate,
period_over_period_variance, cash_balance, current_ratio, quick_ratio, working_capital, accounts_receivable,
ar_aging, accounts_payable, ap_aging, inventory_value, inventory_turnover, dso, dpo, dio, cash_conversion_cycle,
outstanding_debt, finance_costs, interest_coverage_ratio, debt_to_equity, revenue_by_customer, revenue_by_product,
revenue_by_channel, customer_concentration, budget_variance, net_burn, cash_runway, marketplace_fees,
settlement_variance.

Notes:
- `revenue_by_*` and `customer_concentration` use the sales register's taxable value (excl. GST); returns are not
  allocated to customers/products.
- `dpo` uses COGS as the denominator (partial) unless `credit_purchases_incl_tax` is supplied in the run config.
- `net_burn` excludes financing/transfer lines only when the bank file has a `category` column.
- `marketplace_fees` sums the fee component of settlements (excl. GST on fees and withholdings).

Reflex derived calculations (18) and scenarios (8), all recomputed independently by `fa_verify.py`:
rx_ar_overdue_total, rx_ar_overdue_share, rx_ar_overdue_by_customer, rx_customer_revenue_share,
rx_customer_open_receivables, rx_settlement_unlocated, rx_settlement_days_unlocated, rx_settlement_component,
rx_bank_book_difference, rx_margin_change, rx_cost_growth_gap, rx_budget_shortfall, rx_msme_overdue_total,
rx_msme_overdue_by_supplier, rx_msme_max_days, rx_near_term_obligations, rx_near_term_receipts,
rx_near_term_coverage; scn_collect_overdue_cash, scn_collect_overdue_dso, scn_collect_overdue_dso_change,
scn_dso_reduction_cash_release, scn_settlement_recovery_cash, scn_margin_restoration_price_increase,
scn_cost_normalisation_saving, scn_msme_clearance_cash_after.

**Specified but not implemented (27 registry metrics):** variable_costs, fixed_costs, contribution_margin,
contribution_margin_ratio, operating_cash_flow, capital_expenditure, free_cash_flow, dscr, order_count,
average_order_value, customer_profitability, repeat_purchase_rate, marketplace_fee_rate, gateway_fee_rate,
return_rate, refund_rate, sku_contribution_margin, forecast_variance, forecast_accuracy, break_even_revenue,
margin_of_safety, payroll_cost, payroll_to_revenue_ratio, revenue_per_employee, vendor_spend_concentration,
average_selling_price, discount_rate.

## Checks

| Family | Implemented | Specified only |
|---|---|---|
| Data quality | dq_missing_records (bank running-balance breaks), dq_empty_fields, dq_invalid_values, dq_duplicates, dq_invalid_dates, dq_date_gaps, dq_currency_mismatch, dq_unexpected_negative, dq_misclassification (name-based), dq_missing_category, dq_stale_data, dq_period_incompatibility | dq_unit_scale, dq_sign_inconsistency, dq_out_of_range, dq_account_name_inconsistency, dq_missing_history, dq_partial_import, dq_extraction_error, dq_timezone_cutoff, dq_tax_inclusion_ambiguity |
| Accounting integrity | ai_debit_credit_balance, ai_trial_balance, ai_balance_sheet_equation, ai_opening_closing_rollforward, ai_ledger_to_statement (sales register vs ledger revenue), ai_cash_movement (bank vs book balance), ai_ar_aging_tieout, ai_ap_aging_tieout, ai_settlement_reconciliation, ai_gstin_structure, ai_suspense_and_unclassified, ai_msme_payables_timing | ai_revenue_expense_classification, ai_cogs_consistency, ai_gst_mismatch, ai_tax_treatment_consistency, ai_prior_period_adjustments, ai_statement_consistency, ai_intercompany, ai_tds_tcs_credit_tieout |
| Reconciliation | rec_settlement_to_bank (UTR strong key, then exact amount + date window as probable) | the other 10 rules |
| Verification | 17 checks incl. independent recomputation (registry and reflex figures), register tie-out, cross-footing, claim evidence (narrative and reflex items), topic consistency (warning), masking, boundary language, double-count guard, ver_chart_data, ver_approval_gates | ver_bridge_integrity, ver_period_unit_basis, ver_labels_present, translation_figure_integrity |

## Known limitations

- INR only (other currencies are refused by the run config check rather than converted).
- One entity per run; no consolidation or intercompany elimination.
- Trial balance must carry opening, movement and closing columns (or two "as at" snapshots via the normaliser).
- Bank statement balances are taken per account from the last line on or before the period end.
- GSTIN check-character validation is tested against the GSTN-published sample `27AAPFU0939F1ZV`.
- The topic-consistency check is a keyword heuristic and reports warnings, not failures.
- The reflex engine cannot call connectors itself: it emits read-only data requests that the agent fulfils within
  the task (or the customer provides as files). Vendor drill-downs and bank-ledger BRS requests are analysed by
  the agent outside the verified toolkit.
- Approvals are recorded in an `approvals.json` file; the plugin has no native approval UI.
- Reflex thresholds are configurable attention flags; defaults are documented, not universal benchmarks.
