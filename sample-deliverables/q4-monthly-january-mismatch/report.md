# Financial Analysis Report — Quarter Test Co (fictional)

Period: **Q4 FY2025-26** (2026-01-01 to 2026-03-31) · Basis: accrual · Currency: INR · Run FA-20261104-081725 · Generated 2026-11-04T13:47:25+05:30 (IST)

**Status: Calculations verified; some figures are blocked by critical data issues.** Calculations: independently recomputed on 2026-11-04T13:47:27+05:30 (IST), 24/24 verification checks passed (passed). Data validation: 1 critical, 0 high, 0 medium, 0 low open issue(s) (0 informational); 0 unresolved reconciliation exception(s); 4 partial, 45 blocked, 14 needs-data calculation(s).

## Executive summary

No narrative summary was supplied; key metrics follow.

## Key metrics

| Metric | Q4 FY2025-26 | Readiness |
|---|---:|---|
| Net revenue | ₹33.00 lakh | ready |
| Gross margin | 40.9% | ready |
| EBITDA margin | 22.4% | ready |
| Profit before tax (no tax provision booked) | ₹5.90 lakh | ready |
| Cash and bank balance | ₹11.40 lakh ⚠ | partial ⚠ |
| Current ratio | N/M | ready |
| Days sales outstanding | 0 days ⚠ | partial ⚠ |
| Cash conversion cycle | 0 days ⚠ | partial ⚠ |
| Debt-to-equity | 0.00 | ready |
| Cash runway | needs data | needs data |

## Findings by evidence class

Verified findings use only calculations that are ready and are not scenarios. Exceptions, estimates and hypotheses are kept separate and are not facts.

### Verified findings

No verified findings were stated for this run.

### Unresolved reconciliation exceptions

None.


### Estimates and scenarios (not facts)

None.

### Hypotheses to test

None.

### Data gaps affecting results

1. Critical data issues (ISS-0001) block 15 metric(s); figures that depend on them are withheld rather than estimated. *(auto-generated)* — evidence: ISS-0001
2. The cash figure is a book balance not yet verified against a bank statement. *(auto-generated)* — evidence: CALC-0079
3. DPO uses COGS as its denominator; a purchase register would make DPO and the cash conversion cycle exact. *(auto-generated)* — evidence: CALC-0077, metric:dpo
4. Profit after tax is not stated because no tax provision is booked; profit before tax is shown under its own label. *(auto-generated)* — evidence: CALC-0013

## Recommendations

No recommendations were supplied for this run.

## Profit and loss

| Line (₹ in lakhs) | Q4 FY2025-26 |
|---|---:|
| Gross revenue | 33.00 |
| Less: returns & allowances | 0.00 |
| Net revenue | 33.00 |
| Cost of goods sold | 19.50 |
| Gross profit | 13.50 |
| Operating expenses (excl. D&A) | 6.10 |
| EBITDA | 7.40 |
| Operating profit | 5.90 |
| Profit before tax | 5.90 |
| Profit after tax (net profit) | needs data |

| Margin | Q4 FY2025-26 |
|---|---:|
| Gross margin | 40.9% |
| EBITDA margin | 22.4% |
| Operating margin | 17.9% |
| Net margin (after tax) | needs data |
| Cost-to-revenue ratio | 77.6% |

## Monthly profit and loss

Withheld: the sub-period trial balances do not reconcile to the period total (ISS-0001). Period figures above come from the period trial balance.

## Expenses by category

| Category (₹ in lakhs) | Q4 FY2025-26 |
|---|---:|
| Depreciation and amortisation | 1.50 |
| Employee benefits expense | 6.10 |
| Purchases of stock in trade | 19.50 |

## Liquidity, working capital and debt

| Balance at 2026-03-31 (₹ in lakhs) | Amount |
|---|---:|
| Cash and bank (statement) | 11.40 ⚠ |
| Trade receivables | 0.00 |
| Inventory | 0.00 |
| Trade payables | 0.00 |
| Working capital | 11.40 |
| Operating working capital | 0.00 |
| Outstanding borrowings | 0.00 |

| Indicator | Value | Readiness |
|---|---:|---|
| Current ratio | N/M | ready |
| Quick ratio | N/M | ready |
| Days sales outstanding | 0 days ⚠ | partial ⚠ |
| Days payables outstanding | 0 days ⚠ | partial ⚠ |
| Cash conversion cycle | 0 days ⚠ | partial ⚠ |
| Interest coverage | N/A | ready |
| Debt-to-equity | 0.00 | ready |
| Average monthly net burn | needs data | needs data |
| Cash runway | needs data | needs data |

## Proactive insights (Reflex Engine)

Ran automatically after the analysis, inside this task only (no background monitoring). Rules evaluated: 11; triggers found: 4; investigated: 4; suppressed: 0; deferred: 0; approvals pending: 0. Everything below was computed read-only from the data provided; nothing was sent, uploaded, paid or posted.

### Triggered findings

| # | Finding | Rule(s) | Severity | Confidence |
|---|---|---|---|---|
| 1 | Critical data issues block part of the analysis | rx_critical_data_blockers | critical | 0.90 |
| 2 | Cash balance is a book figure without a bank statement | rx_partial_metric_upgrade | low | 0.90 |
| 3 | DPO uses COGS because credit purchases are not available | rx_partial_metric_upgrade | low | 0.90 |
| 4 | Profit after tax not stated: no tax provision booked | rx_partial_metric_upgrade | low | 0.90 |

Insights from these investigations appear under Findings by evidence class.

### Prioritised actions (auto-generated)

| Rank | Action | Expected impact | Impact | Confidence | Effort | Priority | Approval |
|---|---|---|---|---|---|---:|---|
| 1 | Re-export the affected source data and re-run the analysis | Unblocks the withheld metrics. | low | high | low | 1.00 | not needed |

### Additional data requested (read-only)

- REQ-902be2c7beb2 (requested): corrected source export from accounting system or customer export → the dataset named in the issue. Critical issues ISS-0001 block dependent metrics; a corrected export is needed.
- REQ-1e49ee63c417 (requested): bank_transactions from bank statement or authorised bank connector → bank_transactions.csv. Cash is a book balance; a statement verifies it.
- REQ-91fc3cb6ab90 (requested): credit purchases including GST from accounting system (purchase register) → run_config.json: credit_purchases_incl_tax. Makes DPO and the cash conversion cycle ready instead of partial.
- REQ-cb9861497ada (requested): tax provision for the period from accounting system or Chartered Accountant → trial_balance.csv (current_tax / deferred_tax lines). Net profit is before tax because no provision is booked; tax is never estimated.

## Data quality and accounting integrity

Issues by severity: critical 1.

| Issue | Check | Severity | Description |
|---|---|---|---|
| ISS-0001 | ai_period_rollup | critical | Sub-period trial balances do not roll up to Q4 FY2025-26: profit after all booked expenses by sub-period 2026-01 100000.00, 2026-02 200000.00, 2026-03 240000.00 vs period 590000.00 (difference 50000.00). The monthly breakdown is withheld; period totals come from the period trial balance. |

## Limitations — what could not be fully analysed

- Profit after tax (net profit) (`net_profit`, Q4 FY2025-26): **needs data** — No tax provision booked for the period: profit after tax (net profit) is not stated; profit before tax is shown under its own label. Tax is never estimated.
- Net margin (after tax) (`net_margin`, Q4 FY2025-26): **needs data** — No tax provision booked for the period: profit after tax (net profit) is not stated; profit before tax is shown under its own label. Tax is never estimated.
- Effective tax rate (books) (`effective_tax_rate`, Q4 FY2025-26): **needs data** — Book measure only; not a tax computation.; No tax provision booked for the period: profit after tax (net profit) is not stated; profit before tax is shown under its own label. Tax is never estimated.
- Gross revenue (`gross_revenue`, 2026-01): **blocked** — blocked by critical issue(s) ISS-0001
- Sales returns & allowances (`sales_returns_and_allowances`, 2026-01): **blocked** — blocked by critical issue(s) ISS-0001
- Net revenue (`net_revenue`, 2026-01): **blocked** — blocked by critical issue(s) ISS-0001
- Cost of goods sold (`cogs`, 2026-01): **blocked** — blocked by critical issue(s) ISS-0001
- Gross profit (`gross_profit`, 2026-01): **blocked** — blocked by critical issue(s) ISS-0001
- Gross margin (`gross_margin`, 2026-01): **blocked** — blocked by critical issue(s) ISS-0001
- Operating expenses (excl. D&A) (`operating_expenses`, 2026-01): **blocked** — blocked by critical issue(s) ISS-0001
- EBITDA (`ebitda`, 2026-01): **blocked** — blocked by critical issue(s) ISS-0001; Non-GAAP measure; other income excluded.
- EBITDA margin (`ebitda_margin`, 2026-01): **blocked** — blocked by critical issue(s) ISS-0001
- Operating profit (`operating_profit`, 2026-01): **blocked** — blocked by critical issue(s) ISS-0001
- Operating margin (`operating_margin`, 2026-01): **blocked** — blocked by critical issue(s) ISS-0001
- Profit before tax (`profit_before_tax`, 2026-01): **blocked** — blocked by critical issue(s) ISS-0001
- Profit after tax (net profit) (`net_profit`, 2026-01): **blocked** — blocked by critical issue(s) ISS-0001; No tax provision booked for the period: profit after tax (net profit) is not stated; profit before tax is shown under its own label. Tax is never estimated.
- Net margin (after tax) (`net_margin`, 2026-01): **blocked** — blocked by critical issue(s) ISS-0001; No tax provision booked for the period: profit after tax (net profit) is not stated; profit before tax is shown under its own label. Tax is never estimated.
- Effective tax rate (books) (`effective_tax_rate`, 2026-01): **blocked** — blocked by critical issue(s) ISS-0001; Book measure only; not a tax computation.; No tax provision booked for the period: profit after tax (net profit) is not stated; profit before tax is shown under its own label. Tax is never estimated.
- Days sales outstanding (`dso`, Q4 FY2025-26): **partial** — Alternative input: net revenue excluding GST used as denominator; DSO is overstated roughly by the tax share because receivables include GST.
- Days payables outstanding (`dpo`, Q4 FY2025-26): **partial** — Alternative input: COGS used as denominator (payables include GST and non-inventory purchases); provide credit purchases including GST for a ready DPO.
- Cash conversion cycle (`cash_conversion_cycle`, Q4 FY2025-26): **partial** — Inherits DSO/DPO limitations.
- Cash and bank balance (`cash_balance`, Q4 FY2025-26): **partial** — Book balance only; no bank statement provided to verify it.
- Average monthly net burn (`net_burn`, Q4 FY2025-26): **needs data** — needs bank_transactions.csv
- Cash runway (`cash_runway`, Q4 FY2025-26): **needs data** — needs bank_transactions.csv
- Receivables aging (`ar_aging` [bucket=total], Q4 FY2025-26): **needs data** — needs ar_open_items.csv
- Payables aging (`ap_aging` [bucket=total], Q4 FY2025-26): **needs data** — needs ap_open_items.csv
- Revenue by customer (`revenue_by_customer` [key=all], Q4 FY2025-26): **needs data** — needs sales_lines.csv
- Revenue by product (`revenue_by_product` [key=all], Q4 FY2025-26): **needs data** — needs sales_lines.csv
- Revenue by channel (`revenue_by_channel` [key=all], Q4 FY2025-26): **needs data** — needs sales_lines.csv
- Customer concentration (`customer_concentration` [key=all], Q4 FY2025-26): **needs data** — needs sales_lines.csv
- Budget variance (`budget_variance` [account_class=all, measure=variance], Q4 FY2025-26): **needs data** — needs budget.csv
- Marketplace / gateway fees (`marketplace_fees` [provider=all], Q4 FY2025-26): **needs data** — needs settlements.csv
- Settlement variance (`settlement_variance`, Q4 FY2025-26): **needs data** — needs settlements.csv

## Scope, sources and method

- `trial_balance.csv` (trial_balance): 36 rows, coverage 2026-01-01 to 2026-03-31, SHA-256 651c5f8cb935…

- Formulas: finance-analyst.yaml metrics.registry, formula_version 1.0; spec version 1.3.0; toolkit 0.3.0.
- Amounts exclude GST unless stated. Tables state their scale. ⚠ marks a partial figure; see Limitations.
- Materiality for highlighting movements: two of (≥ ₹25,000; ≥ 10% of base; ≥ 0.5% of net revenue) unless configured otherwise.

## Appendix — definitions used in this report

| Metric | Definition (formula) | Basis |
|---|---|---|
| Gross revenue (`gross_revenue`) | ledger(revenue_from_operations, period) | accrual, amounts excl. GST |
| Sales returns & allowances (`sales_returns_and_allowances`) | ledger(sales_returns_and_allowances, period) | accrual, amounts excl. GST |
| Net revenue (`net_revenue`) | gross_revenue + ledger(other_operating_revenue) - sales_returns_and_allowances | accrual, amounts excl. GST |
| Cost of goods sold (`cogs`) | ledger(cost_of_revenue classes, period) | accrual, amounts excl. GST |
| Gross profit (`gross_profit`) | net_revenue - cogs | accrual, amounts excl. GST |
| Gross margin (`gross_margin`) | gross_profit / net_revenue | accrual |
| Operating expenses (excl. D&A) (`operating_expenses`) | ledger(operating expense classes, period) | accrual, amounts excl. GST |
| EBITDA (`ebitda`) | gross_profit - operating_expenses | accrual, amounts excl. GST |
| EBITDA margin (`ebitda_margin`) | ebitda / net_revenue | accrual |
| Operating profit (`operating_profit`) | ebitda - ledger(depreciation_and_amortisation) | accrual, amounts excl. GST |
| Operating margin (`operating_margin`) | operating_profit / net_revenue | accrual |
| Profit before tax (`profit_before_tax`) | operating_profit + other_income - finance_costs - (exceptional + prior_period + fx) | accrual, amounts excl. GST |
| Cost-to-revenue ratio (`cost_to_revenue_ratio`) | (cogs + operating_expenses) / net_revenue | accrual |
| Expenses by category (`expense_by_category`) | group_by(ledger(expense classes), class) | accrual, amounts excl. GST |
| Trade receivables (`accounts_receivable`) | balance(trade_receivables, as_of) | accrual, amounts excl. GST |
| Trade payables (`accounts_payable`) | balance(trade payable classes, as_of) | accrual, amounts excl. GST |
| Inventory (`inventory_value`) | balance(inventories, as_of) | accrual, amounts excl. GST |
| Working capital (`working_capital`) | balance(current_assets) - balance(current_liabilities) | accrual, amounts excl. GST |
| Outstanding borrowings (`outstanding_debt`) | balance(borrowing classes, as_of) | accrual, amounts excl. GST |
| Finance costs (`finance_costs`) | ledger(finance_costs, period) | accrual, amounts excl. GST |
| Debt-to-equity (`debt_to_equity`) | outstanding_debt / (equity + unappropriated current profit) | accrual |
| Days sales outstanding (`dso`) | avg_balance(trade_receivables) / credit_sales_incl_tax * days(period) | accrual |
| Days payables outstanding (`dpo`) | avg_balance(trade_payables) / credit_purchases_incl_tax * days(period) | accrual |
| Cash conversion cycle (`cash_conversion_cycle`) | dio + dso - dpo | accrual |
| Cash and bank balance (`cash_balance`) | balance(cash_and_cash_equivalents) [book] | cash, amounts excl. GST |

## Appendix — source trace for key figures

| calc_id | Metric | Source |
|---|---|---|
| CALC-0001 | gross_revenue | accounts 4000 |
| CALC-0003 | net_revenue | accounts 4000 |
| CALC-0004 | cogs | accounts 5000 |
| CALC-0005 | gross_profit | accounts 4000, 5000 |
| CALC-0007 | operating_expenses | accounts 6000 |
| CALC-0008 | ebitda | accounts 4000, 5000, 6000 |
| CALC-0010 | operating_profit | accounts 4000, 5000, 6000, 6100 |
| CALC-0012 | profit_before_tax | accounts 4000, 5000, 6000, 6100 |
| CALC-0017 | expense_by_category | accounts 6100 |
| CALC-0018 | expense_by_category | accounts 6000 |
| CALC-0019 | expense_by_category | accounts 5000 |

## Appendix — calculation register

| calc_id | metric | dimension | period | value | readiness |
|---|---|---|---|---:|---|
| CALC-0001 | gross_revenue | — | Q4 FY2025-26 | 3300000.00 | ready |
| CALC-0002 | sales_returns_and_allowances | — | Q4 FY2025-26 | 0 | ready |
| CALC-0003 | net_revenue | — | Q4 FY2025-26 | 3300000.00 | ready |
| CALC-0004 | cogs | — | Q4 FY2025-26 | 1950000.00 | ready |
| CALC-0005 | gross_profit | — | Q4 FY2025-26 | 1350000.00 | ready |
| CALC-0006 | gross_margin | — | Q4 FY2025-26 | 0.4090909090909090909090909090909091 | ready |
| CALC-0007 | operating_expenses | — | Q4 FY2025-26 | 610000.00 | ready |
| CALC-0008 | ebitda | — | Q4 FY2025-26 | 740000.00 | ready |
| CALC-0009 | ebitda_margin | — | Q4 FY2025-26 | 0.2242424242424242424242424242424242 | ready |
| CALC-0010 | operating_profit | — | Q4 FY2025-26 | 590000.00 | ready |
| CALC-0011 | operating_margin | — | Q4 FY2025-26 | 0.1787878787878787878787878787878788 | ready |
| CALC-0012 | profit_before_tax | — | Q4 FY2025-26 | 590000.00 | ready |
| CALC-0013 | net_profit | — | Q4 FY2025-26 | — | needs_data |
| CALC-0014 | net_margin | — | Q4 FY2025-26 | — | needs_data |
| CALC-0015 | effective_tax_rate | — | Q4 FY2025-26 | — | needs_data |
| CALC-0016 | cost_to_revenue_ratio | — | Q4 FY2025-26 | 0.7757575757575757575757575757575758 | ready |
| CALC-0017 | expense_by_category | account_class=depreciation_and_amortisation | Q4 FY2025-26 | 150000.00 | ready |
| CALC-0018 | expense_by_category | account_class=employee_benefits_expense | Q4 FY2025-26 | 610000.00 | ready |
| CALC-0019 | expense_by_category | account_class=purchases_of_stock_in_trade | Q4 FY2025-26 | 1950000.00 | ready |
| CALC-0020 | gross_revenue | — | 2026-01 | — | blocked |
| CALC-0021 | sales_returns_and_allowances | — | 2026-01 | — | blocked |
| CALC-0022 | net_revenue | — | 2026-01 | — | blocked |
| CALC-0023 | cogs | — | 2026-01 | — | blocked |
| CALC-0024 | gross_profit | — | 2026-01 | — | blocked |
| CALC-0025 | gross_margin | — | 2026-01 | — | blocked |
| CALC-0026 | operating_expenses | — | 2026-01 | — | blocked |
| CALC-0027 | ebitda | — | 2026-01 | — | blocked |
| CALC-0028 | ebitda_margin | — | 2026-01 | — | blocked |
| CALC-0029 | operating_profit | — | 2026-01 | — | blocked |
| CALC-0030 | operating_margin | — | 2026-01 | — | blocked |
| CALC-0031 | profit_before_tax | — | 2026-01 | — | blocked |
| CALC-0032 | net_profit | — | 2026-01 | — | blocked |
| CALC-0033 | net_margin | — | 2026-01 | — | blocked |
| CALC-0034 | effective_tax_rate | — | 2026-01 | — | blocked |
| CALC-0035 | gross_revenue | — | 2026-02 | — | blocked |
| CALC-0036 | sales_returns_and_allowances | — | 2026-02 | — | blocked |
| CALC-0037 | net_revenue | — | 2026-02 | — | blocked |
| CALC-0038 | cogs | — | 2026-02 | — | blocked |
| CALC-0039 | gross_profit | — | 2026-02 | — | blocked |
| CALC-0040 | gross_margin | — | 2026-02 | — | blocked |
| CALC-0041 | operating_expenses | — | 2026-02 | — | blocked |
| CALC-0042 | ebitda | — | 2026-02 | — | blocked |
| CALC-0043 | ebitda_margin | — | 2026-02 | — | blocked |
| CALC-0044 | operating_profit | — | 2026-02 | — | blocked |
| CALC-0045 | operating_margin | — | 2026-02 | — | blocked |
| CALC-0046 | profit_before_tax | — | 2026-02 | — | blocked |
| CALC-0047 | net_profit | — | 2026-02 | — | blocked |
| CALC-0048 | net_margin | — | 2026-02 | — | blocked |
| CALC-0049 | effective_tax_rate | — | 2026-02 | — | blocked |
| CALC-0050 | gross_revenue | — | 2026-03 | — | blocked |
| CALC-0051 | sales_returns_and_allowances | — | 2026-03 | — | blocked |
| CALC-0052 | net_revenue | — | 2026-03 | — | blocked |
| CALC-0053 | cogs | — | 2026-03 | — | blocked |
| CALC-0054 | gross_profit | — | 2026-03 | — | blocked |
| CALC-0055 | gross_margin | — | 2026-03 | — | blocked |
| CALC-0056 | operating_expenses | — | 2026-03 | — | blocked |
| CALC-0057 | ebitda | — | 2026-03 | — | blocked |
| CALC-0058 | ebitda_margin | — | 2026-03 | — | blocked |
| CALC-0059 | operating_profit | — | 2026-03 | — | blocked |
| CALC-0060 | operating_margin | — | 2026-03 | — | blocked |
| CALC-0061 | profit_before_tax | — | 2026-03 | — | blocked |
| CALC-0062 | net_profit | — | 2026-03 | — | blocked |
| CALC-0063 | net_margin | — | 2026-03 | — | blocked |
| CALC-0064 | effective_tax_rate | — | 2026-03 | — | blocked |
| CALC-0065 | accounts_receivable | — | Q4 FY2025-26 | 0 | ready |
| CALC-0066 | accounts_payable | — | Q4 FY2025-26 | 0 | ready |
| CALC-0067 | inventory_value | — | Q4 FY2025-26 | 0 | ready |
| CALC-0068 | working_capital | — | Q4 FY2025-26 | 1140000.00 | ready |
| CALC-0069 | working_capital | variant=operating | Q4 FY2025-26 | 0 | ready |
| CALC-0070 | current_ratio | — | Q4 FY2025-26 | — | ready |
| CALC-0071 | quick_ratio | — | Q4 FY2025-26 | — | ready |
| CALC-0072 | outstanding_debt | — | Q4 FY2025-26 | 0 | ready |
| CALC-0073 | finance_costs | — | Q4 FY2025-26 | 0 | ready |
| CALC-0074 | interest_coverage_ratio | — | Q4 FY2025-26 | — | ready |
| CALC-0075 | debt_to_equity | — | Q4 FY2025-26 | 0 | ready |
| CALC-0076 | dso | — | Q4 FY2025-26 | 0 | partial |
| CALC-0077 | dpo | — | Q4 FY2025-26 | 0 | partial |
| CALC-0078 | cash_conversion_cycle | — | Q4 FY2025-26 | 0 | partial |
| CALC-0079 | cash_balance | — | Q4 FY2025-26 | 1140000.00 | partial |
| CALC-0080 | net_burn | — | Q4 FY2025-26 | — | needs_data |
| CALC-0081 | cash_runway | — | Q4 FY2025-26 | — | needs_data |
| CALC-0082 | ar_aging | bucket=total | Q4 FY2025-26 | — | needs_data |
| CALC-0083 | ap_aging | bucket=total | Q4 FY2025-26 | — | needs_data |
| CALC-0084 | revenue_by_customer | key=all | Q4 FY2025-26 | — | needs_data |
| CALC-0085 | revenue_by_product | key=all | Q4 FY2025-26 | — | needs_data |
| CALC-0086 | revenue_by_channel | key=all | Q4 FY2025-26 | — | needs_data |
| CALC-0087 | customer_concentration | key=all | Q4 FY2025-26 | — | needs_data |
| CALC-0088 | budget_variance | account_class=all, measure=variance | Q4 FY2025-26 | — | needs_data |
| CALC-0089 | marketplace_fees | provider=all | Q4 FY2025-26 | — | needs_data |
| CALC-0090 | settlement_variance | — | Q4 FY2025-26 | — | needs_data |

## Disclaimer

This analysis is prepared from the data you authorised and provided, using documented methods. It is decision support, not an audit, review, tax, legal or investment opinion. Figures labelled estimate, forecast or hypothesis carry uncertainty. Please review material decisions, tax matters and statutory filings with your Chartered Accountant or other qualified adviser.
GST and income-tax data checks test consistency between datasets only and do not confirm compliance or filing correctness. Items listed for review are screening results, not findings of wrongdoing.

## Verification

| Check | Status | Details |
|---|---|---|
| ver_no_fabrication | passed | all inputs exist with matching hashes |
| ver_recompute_figures | passed | 15 figures recomputed independently and matched |
| ver_register_tieout | passed | 44 rendered figures tie to the register |
| ver_placeholders_resolved | passed | none left |
| ver_narrative_raw_numbers | passed | narrative uses placeholders for all figures |
| ver_cross_footing | passed | statement, aging, budget and variance identities hold |
| ver_claim_evidence | passed | every finding and recommendation cites valid evidence |
| ver_claim_topic_consistency | passed | cited figures match the topics mentioned |
| ver_direction_words | passed | no contradictions found |
| ver_limitations_disclosed | passed | every non-ready metric is listed under Limitations |
| ver_masking | passed | no unmasked identifiers detected |
| ver_boundary_language | passed | no prohibited assurance language |
| ver_disclaimers | passed | standard disclaimer present |
| ver_double_count_guard | passed | no bank line or settlement counted twice |
| ver_conflict_figures | passed | conflict figures recompute |
| ver_status_consistency | passed | status line counts equal the issue, reconciliation and calculation registers |
| ver_profit_labels | passed | every profit mention names its level and cites it |
| ver_savings_claims | passed | no unsupported savings claims |
| ver_leakage_classification | passed | no recoverable, reversal or timing item called leakage |
| ver_evidence_separation | passed | verified findings, exceptions, estimates and hypotheses are separated |
| ver_source_trace | passed | 17 figure(s) traced to accounts or source rows and re-added |
| ver_excel_formulas | passed | 15 formulas evaluated independently, 15 equal their register values; LibreOffice: ok (15 compared, 0 mismatches) |
| ver_chart_data | passed | 0 charted value(s) match the register |
| ver_approval_gates | passed | no external or financial action executed; prepared files match approvals |

Draft SHA-256: cec6f6c5fda23d300ab3a67fd6807c434e75d2ea691f5eaa0a3ad091156bab09
