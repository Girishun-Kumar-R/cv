# Half-Year Financial Review — Sample Traders Private Limited (fictional)

Period: **H1 FY2025-26** (2025-04-01 to 2025-09-30) compared with **H1 FY2024-25** · Basis: accrual · Currency: INR · Run FA-20261104-081719 · Generated 2026-11-04T13:47:19+05:30 (IST)

**Status: Calculations verified; open data issues, unresolved reconciliation exceptions and partial or data-limited figures remain.** Calculations: independently recomputed on 2026-11-04T13:47:21+05:30 (IST), 24/24 verification checks passed (passed). Data validation: 0 critical, 1 high, 3 medium, 0 low open issue(s) (1 informational); 3 unresolved reconciliation exception(s); 3 partial, 0 blocked, 0 needs-data calculation(s).

## Executive summary

- Net revenue was ₹1.18 crore, up 19.2% on the comparison half-year (₹99.00 lakh).
- Gross margin was 35.6% against 34.5%; net profit was ₹10.88 lakh.
- Cash at bank was ₹12.80 lakh; the bank statement and the books differ and need a bank reconciliation.
- One marketplace settlement with an expected net value of ₹2.46 lakh ⚠ was not found in the bank data provided.

## Key metrics

| Metric | H1 FY2025-26 | H1 FY2024-25 | Readiness |
|---|---:|---:|---|
| Net revenue | ₹1.18 crore | ₹99.00 lakh | ready |
| Revenue growth | 19.2% | — | ready |
| Gross margin | 35.6% | 34.5% | ready |
| EBITDA margin | 14.4% | 12.8% | ready |
| Profit after tax (net profit) | ₹10.88 lakh | ₹7.45 lakh | ready |
| Net margin (after tax) | 9.2% | 7.5% | ready |
| Cash and bank balance | ₹12.80 lakh | — | ready |
| Current ratio | 2.98 | — | ready |
| Days sales outstanding | 26 days | — | ready |
| Cash conversion cycle | 48 days ⚠ | — | partial ⚠ |
| Debt-to-equity | 0.74 | — | ready |
| Cash runway | N/A | — | ready |

## Findings by evidence class

Verified findings use only calculations that are ready and are not scenarios. Exceptions, estimates and hypotheses are kept separate and are not facts.

### Verified findings

1. Revenue grew faster than operating expenses (19.2% against 16.3%), so EBITDA margin rose to 14.4%. — evidence: metric:revenue_growth, metric:expense_growth, metric:ebitda_margin
2. Receivables of ₹4.00 lakh are more than 180 days past due, all from one customer. — evidence: metric:ar_aging[bucket=181_365]
3. A bill from a supplier classified as micro is outstanding beyond 45 days; payment timing should be reviewed with your Chartered Accountant. — evidence: check:ai_msme_payables_timing
4. ₹7.00 lakh of receivables (31.8%) is more than 90 days past due; the largest amount is with Coastal Traders (₹4.00 lakh). *(auto-generated)* — evidence: CALC-0170, CALC-0171, CALC-0172
5. Sunrise Retail accounts for 35.0% of sales register value; open receivables from Sunrise Retail are ₹6.00 lakh. *(auto-generated)* — evidence: CALC-0180, CALC-0183
6. Revenue from operations is ₹7.00 lakh below budget (-5.6%). *(auto-generated)* — evidence: CALC-0184, metric:budget_variance[account_class=revenue_from_operations,measure=variance_pct]
7. Bills of ₹3.00 lakh from suppliers classified micro/small are outstanding beyond 45 days (oldest 91 days). *(auto-generated)* — evidence: CALC-0185, CALC-0187, check:ai_msme_payables_timing
8. Marketplace fees grew 14.1% faster than revenue (increase ₹1.00 lakh). *(auto-generated)* — evidence: CALC-0189, metric:cost_category_variance[account_class=marketplace_fees,measure=amount]
9. Marketplace fees is ₹50,000.00 above budget (14.3%). *(auto-generated)* — evidence: CALC-0191, metric:budget_variance[account_class=marketplace_fees,measure=variance_pct]
10. Employee benefits expense is ₹1.00 lakh above budget (7.1%). *(auto-generated)* — evidence: CALC-0192, metric:budget_variance[account_class=employee_benefits_expense,measure=variance_pct]
11. Advertising grew 14.1% faster than revenue (increase ₹50,000.00). *(auto-generated)* — evidence: CALC-0204, metric:cost_category_variance[account_class=advertising,measure=amount]

### Unresolved reconciliation exceptions

- Settlement GX-SET-0002 (gateway_x): probable match
- Settlement MA-SET-0003 (marketplace_a): unmatched — within the 5-day timing window
- CON-BANK-BOOK: cash and bank balance at 2025-09-30 — explained pending brs
- The bank statement differs from the book balance by -₹20,000.00 at period end; book-side bank ledger lines are requested to explain it. *(auto-generated)* — evidence: CALC-0193, CON-BANK-BOOK
- Settlement MA-SET-0003 from marketplace_a with expected net ₹2.46 lakh was not located in the bank data provided (5 days after the settlement date at period end). This is within the 5-day timing window, so it is treated as a timing difference (possibly in transit), not a loss; later bank lines are requested. *(auto-generated)* — evidence: CALC-0194, CALC-0195

### Estimates and scenarios (not facts)

1. Collecting the receivables more than 90 days past due (₹7.00 lakh) would raise cash to ₹19.80 lakh. — evidence: metric:rx_ar_overdue_total[threshold_days=90], metric:scn_collect_overdue_cash
2. Scenario (receivables): collecting it in full would raise cash to ₹19.80 lakh; DSO would be 21 days instead of 26 days. *(auto-generated)* — evidence: CALC-0176, CALC-0177, metric:dso
3. Scenario (MSME bills): paying them now would leave cash at ₹9.80 lakh. *(auto-generated)* — evidence: CALC-0188
4. Indicative only: ₹42,424.24 of the marketplace fees increase is above what revenue growth alone would explain. This is not evidence that the amount can be reduced; vendor or contract evidence is needed. *(auto-generated)* — evidence: CALC-0190
5. If all unlocated settlements are received, cash would be ₹15.26 lakh (scenario). *(auto-generated)* — evidence: CALC-0203
6. Indicative only: ₹21,212.12 of the advertising increase is above what revenue growth alone would explain. This is not evidence that the amount can be reduced; vendor or contract evidence is needed. *(auto-generated)* — evidence: CALC-0205

### Hypotheses to test

1. Hypothesis: the faster growth of marketplace fees may reflect a rate or contract change rather than volume; vendor bills would confirm or reject this. *(auto-generated)* — evidence: CALC-0189
2. Hypothesis: the faster growth of advertising may reflect a rate or contract change rather than volume; vendor bills would confirm or reject this. *(auto-generated)* — evidence: CALC-0204

### Data gaps affecting results

1. DPO uses COGS as its denominator; a purchase register would make DPO and the cash conversion cycle exact. *(auto-generated)* — evidence: CALC-0109, metric:dpo

## Recommendations

### 1. Follow up the receivable more than 180 days past due

It is ₹4.00 lakh from a single customer and older balances are harder to collect.
- Expected impact: Up to ₹4.00 lakh of cash if collected in full.
- Confidence: medium; effort: low
- Evidence: metric:ar_aging[bucket=181_365]

### 2. Raise a query on the missing marketplace settlement

Settlement MA-SET-0003 was not located in the bank data provided; it may be in transit or unpaid.
- Expected impact: Up to ₹2.46 lakh ⚠ of expected cash.
- Confidence: medium; effort: low
- Evidence: metric:settlement_variance, check:ai_settlement_reconciliation

### 3. Prepare the bank reconciliation for the period end

Book and statement balances differ; a bank reconciliation statement should explain the difference before the cash figure is relied on.
- Confidence: high; effort: low
- Evidence: CON-BANK-BOOK, check:ai_cash_movement

## Profit and loss

| Line (₹ in lakhs) | H1 FY2025-26 | H1 FY2024-25 |
|---|---:|---:|
| Gross revenue | 120.00 | 100.00 |
| Less: returns & allowances | 2.00 | 1.00 |
| Net revenue | 118.00 | 99.00 |
| Cost of goods sold | 76.00 | 64.80 |
| Gross profit | 42.00 | 34.20 |
| Operating expenses (excl. D&A) | 25.00 | 21.50 |
| EBITDA | 17.00 | 12.70 |
| Operating profit | 16.00 | 11.70 |
| Profit before tax | 14.50 | 9.60 |
| Profit after tax (net profit) | 10.88 | 7.45 |

Change vs H1 FY2024-25:

| Line (₹ in lakhs) | Change |
|---|---:|
| Gross revenue | 20.00 |
| Less: returns & allowances | 1.00 |
| Net revenue | 19.00 |
| Cost of goods sold | 11.20 |
| Gross profit | 7.80 |
| Operating expenses (excl. D&A) | 3.50 |
| EBITDA | 4.30 |
| Operating profit | 4.30 |
| Profit before tax | 4.90 |
| Profit after tax (net profit) | 3.43 |

| Line | Change % |
|---|---:|
| Gross revenue | 20.0% |
| Less: returns & allowances | 100.0% |
| Net revenue | 19.2% |
| Cost of goods sold | 17.3% |
| Gross profit | 22.8% |
| Operating expenses (excl. D&A) | 16.3% |
| EBITDA | 33.9% |
| Operating profit | 36.8% |
| Profit before tax | 51.0% |
| Profit after tax (net profit) | 46.0% |

| Margin | H1 FY2025-26 | H1 FY2024-25 |
|---|---:|---:|
| Gross margin | 35.6% | 34.5% |
| EBITDA margin | 14.4% | 12.8% |
| Operating margin | 13.6% | 11.8% |
| Net margin (after tax) | 9.2% | 7.5% |
| Cost-to-revenue ratio | 85.6% | 87.2% |

## Expenses by category

| Category (₹ in lakhs) | H1 FY2025-26 | H1 FY2024-25 |
|---|---:|---:|
| Advertising | 2.00 | 1.50 |
| Changes in inventories | (5.00) | (2.00) |
| Depreciation and amortisation | 1.00 | 1.00 |
| Employee benefits expense | 15.00 | 13.00 |
| Finance costs | 2.00 | 2.50 |
| Freight inward | 1.00 | 0.80 |
| Marketplace fees | 4.00 | 3.00 |
| Professional fees | 1.00 | 1.00 |
| Purchases of stock in trade | 80.00 | 66.00 |
| Rent | 3.00 | 3.00 |

## Liquidity, working capital and debt

| Balance at 2025-09-30 (₹ in lakhs) | Amount |
|---|---:|
| Cash and bank (statement) | 12.80 |
| Trade receivables | 22.00 |
| Inventory | 25.00 |
| Trade payables | 15.00 |
| Working capital | 39.88 |
| Operating working capital | 32.00 |
| Outstanding borrowings | 25.00 |

| Indicator | Value | Readiness |
|---|---:|---|
| Current ratio | 2.98 | ready |
| Quick ratio | 1.74 | ready |
| Days sales outstanding | 26 days | ready |
| Days inventory outstanding | 54 days | ready |
| Days payables outstanding | 33 days ⚠ | partial ⚠ |
| Cash conversion cycle | 48 days ⚠ | partial ⚠ |
| Inventory turnover | 3.38 | ready |
| Interest coverage | 8.00 | ready |
| Debt-to-equity | 0.74 | ready |
| Average monthly net burn | ₹0.00 | ready |
| Cash runway | N/A | ready |

## Receivables aging

| Bucket (days past due) (₹ in lakhs) | Outstanding |
|---|---:|
| Not due | 6.00 |
| 1–30 days | 5.00 |
| 31–60 days | 0.00 |
| 61–90 days | 4.00 |
| 91–180 days | 3.00 |
| 181–365 days | 4.00 |
| Over 365 days | 0.00 |
| Total | 22.00 |

## Payables aging

| Bucket (days past due) (₹ in lakhs) | Outstanding |
|---|---:|
| Not due | 5.00 |
| 1–30 days | 7.00 |
| 31–60 days | 0.00 |
| 61–90 days | 3.00 |
| 91–180 days | 0.00 |
| 181–365 days | 0.00 |
| Over 365 days | 0.00 |
| Total | 15.00 |

## Top customers (sales register, excl. GST)

| Item (₹ in lakhs) | Value |
|---|---:|
| Sunrise Retail (C001) | 42.00 |
| Metro Wholesale (C002) | 30.00 |
| Lakeview Stores (C003) | 20.00 |
| Hilltop Mart (C004) | 16.00 |
| Coastal Traders (C005) | 12.00 |

## Top products (sales register, excl. GST)

| Item (₹ in lakhs) | Value |
|---|---:|
| SKU-A | 54.00 |
| SKU-B | 40.00 |
| SKU-C | 26.00 |

## Revenue by channel (sales register, excl. GST)

| Item (₹ in lakhs) | Value |
|---|---:|
| direct_b2b | 90.00 |
| marketplace_a | 30.00 |

| Concentration | Value |
|---|---:|
| Top customer share | 35.0% |
| Top 5 share | 100.0% |
| Top 10 share | 100.0% |
| HHI (0–10,000) | 2406 |

## Budget vs actual

| Line (₹ in lakhs) | Actual | Budget | Variance | Variance % | Assessment | Basis |
|---|---:|---:|---:|---:|---|---|
| Advertising | 2.00 | 2.50 | (0.50) | -20.0% | favourable | actual = ledger(advertising); budget basis tax_exclusive |
| Employee benefits expense | 15.00 | 14.00 | 1.00 | 7.1% | unfavourable | actual = ledger(employee_benefits_expense); budget basis tax_exclusive |
| Marketplace fees | 4.00 | 3.50 | 0.50 | 14.3% | unfavourable | actual = ledger(marketplace_fees); budget basis tax_exclusive |
| Rent | 3.00 | 3.00 | 0.00 | 0.0% | neutral | actual = ledger(rent); budget basis tax_exclusive |
| Revenue (net, as in P&L) | 118.00 | 125.00 | (7.00) | -5.6% | unfavourable | actual = net_revenue; budget basis net_revenue |

## Settlements to bank

| Settlement | Provider | Status | Basis |
|---|---|---|---|
| MA-SET-0001 | marketplace_a | confirmed match | bank reference (UTR) equals settlement bank_reference |
| GX-SET-0002 | gateway_x | probable match | exact net amount; bank date within 5 days; provider name in narration |
| MA-SET-0003 | marketplace_a | unmatched | — |

- Settlement variance (expected net not located or short): ₹2.46 lakh ⚠
- Fees in settlements this period: ₹1.00 lakh

## Source conflicts

- **gross revenue for the current period** — sales_lines.csv (sales register): ₹1.20 crore; trial_balance.csv (revenue_from_operations): ₹1.20 crore. Difference ₹0.00; status resolved. Used: trial_balance.csv (posted ledger; source_of_truth.policies.revenue_accrual).
- **cash and bank balance at 2025-09-30** — bank_transactions.csv (statement balances): ₹12.80 lakh; trial_balance.csv (cash_and_cash_equivalents, book): ₹13.00 lakh. Difference -₹20,000.00; status explained_pending_brs. Used: bank statement (source_of_truth.policies.bank_balances).

## Proactive insights (Reflex Engine)

Ran automatically after the analysis, inside this task only (no background monitoring). Rules evaluated: 11; triggers found: 12; investigated: 10; suppressed: 0; deferred: 1; approvals pending: 3. Everything below was computed read-only from the data provided; nothing was sent, uploaded, paid or posted.

### Triggered findings

| # | Finding | Rule(s) | Severity | Confidence |
|---|---|---|---|---|
| 1 | Receivables more than 90 days past due | rx_overdue_receivables | high | 0.90 |
| 2 | High dependence on Sunrise Retail | rx_customer_concentration | medium | 0.90 |
| 3 | Revenue from operations is unfavourable to budget | rx_budget_overrun | medium | 0.90 |
| 4 | MSME supplier bills outstanding beyond 45 days | rx_msme_payables_timing | medium | 0.90 |
| 5 | Marketplace fees grew faster than revenue; Marketplace fees is unfavourable to budget | rx_cost_category_spike, rx_budget_overrun | medium | 0.90 |
| 6 | Employee benefits expense is unfavourable to budget | rx_budget_overrun | medium | 0.90 |
| 7 | Bank and book balances differ at period end | rx_bank_book_difference | medium | 0.90 |
| 8 | Settlement MA-SET-0003 not yet in bank data (within the 5-day timing window) | rx_settlement_shortfall | low | 0.60 |
| 9 | Advertising grew faster than revenue | rx_cost_category_spike | low | 0.90 |
| 10 | DPO uses COGS because credit purchases are not available | rx_partial_metric_upgrade | low | 0.90 |

Insights from these investigations appear under Findings by evidence class.

### Scenarios (deterministic what-ifs)

| Scenario | Result | Formula / assumption |
|---|---:|---|
| scn_collect_overdue_cash | ₹19.80 lakh | Overdue receivables collected in full; nothing else changes. |
| scn_collect_overdue_dso | 21 days | ((opening AR + closing AR - overdue) / 2) / credit_sales * days |
| scn_collect_overdue_dso_change | -5 days | scn_collect_overdue_dso - dso |
| scn_dso_reduction_cash_release [dso_reduction_days=10] | ₹7.74 lakh | dso_reduction_days * credit_sales_incl_tax / days(period) |
| scn_msme_clearance_cash_after | ₹9.80 lakh | All flagged MSME bills paid now. |
| scn_cost_normalisation_saving [account_class=marketplace_fees] | ₹42,424.24 | Indicative gap between actual growth and revenue-proportional growth; not evidence that any reduction is achievable. |
| scn_settlement_recovery_cash | ₹15.26 lakh | All unlocated settlements are received. |
| scn_cost_normalisation_saving [account_class=advertising] | ₹21,212.12 | Indicative gap between actual growth and revenue-proportional growth; not evidence that any reduction is achievable. |

### Prioritised actions (auto-generated)

| Rank | Action | Expected impact | Impact | Confidence | Effort | Priority | Approval |
|---|---|---|---|---|---|---:|---|
| 1 | Collect receivables more than 90 days past due, starting with Coastal Traders | Up to ₹7.00 lakh of cash if collected in full (upper bound). | high | high | low | 3.00 | APR-7fe2ac34a2dc (pending approval) |
| 2 | Review and schedule payment of MSME supplier bills beyond 45 days — review with your CA | Exposure ₹3.00 lakh. | high | high | low | 3.00 | APR-62d4db6079f2 (pending approval) |
| 3 | Confirm receipt of settlement MA-SET-0003 or raise a query with marketplace_a | Up to ₹2.46 lakh of cash if it is still outstanding (upper bound). | high | medium | low | 2.10 | APR-004652098706 (pending approval) |
| 4 | Close the revenue gap to budget | ₹7.00 lakh against plan (measured). | high | high | medium | 1.50 | not needed |
| 5 | Review credit terms and dependence on Sunrise Retail | Exposure in open receivables ₹6.00 lakh. | high | high | high | 1.00 | not needed |
| 6 | Bring employee benefits expense back within budget | ₹1.00 lakh against plan (measured). | medium | high | medium | 1.00 | not needed |
| 7 | Bring marketplace fees back within budget | ₹50,000.00 against plan (measured). | medium | high | medium | 1.00 | not needed |
| 8 | Prepare the period-end bank reconciliation statement | Confirms the cash figure used in this report. | low | high | low | 1.00 | not needed |
| 9 | Review marketplace fees spend and contracts | Indicative gap ₹42,424.24 above revenue-proportional growth; confirm with vendor or contract evidence before treating any amount as recoverable. | low | high | medium | 0.50 | not needed |
| 10 | Review advertising spend and contracts | Indicative gap ₹21,212.12 above revenue-proportional growth; confirm with vendor or contract evidence before treating any amount as recoverable. | low | high | medium | 0.50 | not needed |

### Charts

![Receivables by days past due](charts/rx-ar-aging.svg)

Data: Not due ₹6.00 lakh; 1–30 days ₹5.00 lakh; 31–60 days ₹0.00; 61–90 days ₹4.00 lakh; 91–180 days ₹3.00 lakh; 181–365 days ₹4.00 lakh; Over 365 days ₹0.00

![Customer concentration](charts/rx-customer-pareto.svg)

Data: C001 35.0%; C002 25.0%; C003 16.7%; C004 13.3%; C005 10.0%

![Budget variance by line](charts/rx-budget-variance.svg)

Data: Advertising -₹50,000.00; Employee benefits expense ₹1.00 lakh; Marketplace fees ₹50,000.00; Rent ₹0.00; Revenue from operations -₹7.00 lakh

![Settlements: gross to expected net](charts/rx-settlement-waterfall.svg)

Data: Gross ₹10.00 lakh; Fees (cost) ₹1.00 lakh; GST on fees (credit) ₹18,000.00; Refunds (reversal) ₹30,000.00; TCS/TDS (tax credit) ₹4,000.00; Adjustments ₹0.00; Expected net ₹8.48 lakh

![Cost growth above revenue growth](charts/rx-cost-growth-gaps.svg)

Data: Marketplace fees 14.1%; Advertising 14.1%

### Additional data requested (read-only)

- REQ-7ca894904c1e (requested): supplier_bills by vendor from accounting system (vendor bills) → vendor-level drill-down (analysed by the agent; not a canonical file in v0.1). Identify which vendors or contracts drove the increase in marketplace fees.
- REQ-f860afb809d6 (requested): bank ledger lines (book side) from accounting system (bank ledger) → journal_lines.csv (bank account lines) — used by the agent to prepare a BRS outside the verified report. Identify uncleared cheques, deposits in transit or unrecorded bank charges (toolkit v0.1 does not implement rec_accounting_to_bank).
- REQ-ebb9e15ae43e (requested): bank_transactions from bank statement or authorised bank connector → bank_transactions.csv (append lines after the period end). Check whether settlement MA-SET-0003 arrived after the period end (timing) or is missing.
- REQ-50d29720adb5 (requested): supplier_bills by vendor from accounting system (vendor bills) → vendor-level drill-down (analysed by the agent; not a canonical file in v0.1). Identify which vendors or contracts drove the increase in advertising.
- REQ-d4c861b987ce (requested): credit purchases including GST from accounting system (purchase register) → run_config.json: credit_purchases_incl_tax. Makes DPO and the cash conversion cycle ready instead of partial.

### Approvals needed before any external or financial action

- APR-7fe2ac34a2dc (external action, pending approval): Draft payment reminder emails to customers with invoices more than 90 days past due. On approval: The plugin prepares draft reminders in prepared/; nothing is sent until you send it or approve sending separately.
- APR-62d4db6079f2 (financial write, pending approval): Prepare a payment proposal for MSME bills beyond the statutory period. On approval: The plugin prepares prepared/msme_payment_proposal.csv. It never makes payments; you execute any payment in your own bank.
- APR-004652098706 (external action, pending approval): Draft a query to marketplace_a about settlement MA-SET-0003. On approval: The plugin prepares a draft query in prepared/; you send it.

### Suppressed and deferred

- Deferred: data_gap:probable_settlement_matches — rx_partial_metric_upgrade (limit_reached:max_triggers)

## Data quality and accounting integrity

Issues by severity: high 1, medium 3, informational 1.

| Issue | Check | Severity | Description |
|---|---|---|---|
| ISS-0001 | dq_date_gaps | medium | Account XXXX1234: 7 gap(s) longer than 10 days without statement lines - confirm no statement pages are missing. |
| ISS-0002 | ai_msme_payables_timing | medium | 1 bill(s) from suppliers classified micro/small are outstanding more than 45 days after bill date. Flag for professional review of payment-timing implications; applicability depends on supplier registration, activity and agreed terms. |
| ISS-0003 | ai_msme_payables_timing | informational | 1 open bill(s) have no MSME classification; MSME timing could not be assessed for them. |
| ISS-0004 | ai_settlement_reconciliation | high | 1 settlement(s) not found in bank credits and 0 conflicting; expected net value not located in the bank data provided: ₹2.46 lakh. |
| ISS-0005 | ai_cash_movement | medium | cash and bank balance at 2025-09-30: sources differ by -₹20,000.00 (timing_or_unrecorded_items_requires_brs). Both figures are shown; bank statement (source_of_truth.policies.bank_balances) is used. |

## Limitations — what could not be fully analysed

- Days payables outstanding (`dpo`, H1 FY2025-26): **partial** — Alternative input: COGS used as denominator (payables include GST and non-inventory purchases); provide credit purchases including GST for a ready DPO.
- Cash conversion cycle (`cash_conversion_cycle`, H1 FY2025-26): **partial** — Inherits DSO/DPO limitations.
- Settlement variance (`settlement_variance`, H1 FY2025-26): **partial** — Unmatched settlements may be in transit or missing; a non-zero variance is a lead for review, not proof of platform error.; Includes probable (not confirmed) matches.

## Scope, sources and method

- `ap_open_items.csv` (ap_open_items): 4 rows, coverage 2025-07-01 to 2025-10-15, SHA-256 9accdd8195ad…
- `ar_open_items.csv` (ar_open_items): 5 rows, coverage 2024-11-15 to 2025-10-05, SHA-256 ddd3361ce86b…
- `bank_transactions.csv` (bank_transactions): 17 rows, coverage 2025-04-05 to 2025-09-29, SHA-256 a49af03261e0…
- `budget.csv` (budget): 5 rows, coverage — to —, SHA-256 aeb97c8da318…
- `journal_lines.csv` (journal_lines): 4 rows, coverage 2025-09-30 to 2025-09-30, SHA-256 0881e628f7c8…
- `sales_lines.csv` (sales_lines): 11 rows, coverage 2025-04-02 to 2025-09-12, SHA-256 6376324e2d88…
- `settlements.csv` (settlements): 3 rows, coverage 2025-06-14 to 2025-09-25, SHA-256 f4e5dd11ba87…
- `trial_balance.csv` (trial_balance): 48 rows, coverage 2024-04-01 to 2025-09-30, SHA-256 062a51f55731…

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
| Profit after tax (net profit) (`net_profit`) | profit_before_tax - tax expense | accrual, amounts excl. GST |
| Net margin (after tax) (`net_margin`) | net_profit / net_revenue | accrual |
| Effective tax rate (books) (`effective_tax_rate`) | tax expense / profit_before_tax | accrual |
| Cost-to-revenue ratio (`cost_to_revenue_ratio`) | (cogs + operating_expenses) / net_revenue | accrual |
| Expenses by category (`expense_by_category`) | group_by(ledger(expense classes), class) | accrual, amounts excl. GST |
| Revenue growth (`revenue_growth`) | (net_revenue[P] - net_revenue[C]) / abs(net_revenue[C]) | accrual |
| Operating expense growth (`expense_growth`) | (operating_expenses[P] - operating_expenses[C]) / abs(operating_expenses[C]) | accrual |
| Change vs comparison (`period_over_period_variance`) | gross_revenue[P] - gross_revenue[C] | accrual, amounts excl. GST |
| Cost category variance (`cost_category_variance`) | actual_k[P] - actual_k[C] | accrual, amounts excl. GST |
| Trade receivables (`accounts_receivable`) | balance(trade_receivables, as_of) | accrual, amounts excl. GST |
| Trade payables (`accounts_payable`) | balance(trade payable classes, as_of) | accrual, amounts excl. GST |
| Inventory (`inventory_value`) | balance(inventories, as_of) | accrual, amounts excl. GST |
| Working capital (`working_capital`) | balance(current_assets) - balance(current_liabilities) | accrual, amounts excl. GST |
| Current ratio (`current_ratio`) | current_assets / current_liabilities | accrual |
| Quick ratio (`quick_ratio`) | (current_assets - inventories - prepaid_expenses) / current_liabilities | accrual |
| Outstanding borrowings (`outstanding_debt`) | balance(borrowing classes, as_of) | accrual, amounts excl. GST |
| Finance costs (`finance_costs`) | ledger(finance_costs, period) | accrual, amounts excl. GST |
| Interest coverage (`interest_coverage_ratio`) | operating_profit / finance_costs | accrual |
| Debt-to-equity (`debt_to_equity`) | outstanding_debt / (equity + unappropriated current profit) | accrual |
| Inventory turnover (`inventory_turnover`) | cogs / avg_balance(inventories) | accrual |
| Days inventory outstanding (`dio`) | avg_balance(inventories) / cogs * days(period) | accrual |
| Days sales outstanding (`dso`) | avg_balance(trade_receivables) / credit_sales_incl_tax * days(period) | accrual |
| Days payables outstanding (`dpo`) | avg_balance(trade_payables) / credit_purchases_incl_tax * days(period) | accrual |
| Cash conversion cycle (`cash_conversion_cycle`) | dio + dso - dpo | accrual |
| Cash and bank balance (`cash_balance`) | sum(latest statement balance per account on/before as_of) | cash, amounts excl. GST |
| Average monthly net burn (`net_burn`) | -mean(monthly net cash change, last 3 months) if negative | cash, amounts excl. GST |
| Receivables aging (`ar_aging`) | sum(open balance where days past due in bucket) | accrual, amounts excl. GST |
| Payables aging (`ap_aging`) | sum(open balance where days past due in bucket) | accrual, amounts excl. GST |
| Revenue by customer (`revenue_by_customer`) | group_by(sales register taxable value, customer_id) | accrual, amounts excl. GST |
| Revenue by product (`revenue_by_product`) | group_by(sales register taxable value, sku) | accrual, amounts excl. GST |
| Revenue by channel (`revenue_by_channel`) | group_by(sales register taxable value, channel) | accrual, amounts excl. GST |
| Customer concentration (`customer_concentration`) | sum(top 1 customers) / total | accrual |
| Budget variance (`budget_variance`) | actual - budget; pct = variance / abs(budget) | accrual, amounts excl. GST |
| Marketplace / gateway fees (`marketplace_fees`) | sum(settlement fee components excl. GST on fees) | accrual, amounts excl. GST |
| Settlement variance (`settlement_variance`) | timing: unmatched within settlement_to_bank_days; unexplained: beyond the window or conflicting | accrual, amounts excl. GST |
| rx_ar_overdue_total (`rx_ar_overdue_total`) | sum(amount_outstanding where as_of - due_date > threshold_days) | accrual, amounts excl. GST |
| rx_ar_overdue_share (`rx_ar_overdue_share`) | rx_ar_overdue_total / total open receivables | accrual |
| rx_ar_overdue_by_customer (`rx_ar_overdue_by_customer`) | rx_ar_overdue_total grouped by customer | accrual, amounts excl. GST |
| rx_customer_revenue_share (`rx_customer_revenue_share`) | customer taxable sales / total sales register | accrual |
| scn_collect_overdue_cash (`scn_collect_overdue_cash`) | cash_balance + rx_ar_overdue_total | accrual, amounts excl. GST |
| scn_collect_overdue_dso (`scn_collect_overdue_dso`) | ((opening AR + closing AR - overdue) / 2) / credit_sales * days | accrual |
| scn_collect_overdue_dso_change (`scn_collect_overdue_dso_change`) | scn_collect_overdue_dso - dso | accrual |
| scn_dso_reduction_cash_release (`scn_dso_reduction_cash_release`) | dso_reduction_days * credit_sales_incl_tax / days(period) | accrual, amounts excl. GST |
| rx_customer_open_receivables (`rx_customer_open_receivables`) | sum(amount_outstanding) for the customer | accrual, amounts excl. GST |
| rx_budget_shortfall (`rx_budget_shortfall`) | abs(unfavourable budget variance) | accrual, amounts excl. GST |
| rx_msme_overdue_total (`rx_msme_overdue_total`) | sum(outstanding) for micro/small suppliers beyond max_days | accrual, amounts excl. GST |
| rx_msme_overdue_by_supplier (`rx_msme_overdue_by_supplier`) | rx_msme_overdue_total grouped by supplier | accrual, amounts excl. GST |
| rx_msme_max_days (`rx_msme_max_days`) | max(as_of - bill_date) | accrual |
| scn_msme_clearance_cash_after (`scn_msme_clearance_cash_after`) | cash_balance - rx_msme_overdue_total | accrual, amounts excl. GST |
| rx_cost_growth_gap (`rx_cost_growth_gap`) | category growth - revenue_growth | accrual |
| scn_cost_normalisation_saving (`scn_cost_normalisation_saving`) | actual_k[P] - actual_k[C] * (1 + revenue_growth) | accrual, amounts excl. GST |
| rx_bank_book_difference (`rx_bank_book_difference`) | bank statement balance - book cash_and_cash_equivalents | accrual, amounts excl. GST |
| rx_settlement_unlocated (`rx_settlement_unlocated`) | expected net not located in bank credits | accrual, amounts excl. GST |
| rx_settlement_days_unlocated (`rx_settlement_days_unlocated`) | as_of - settlement_date | accrual |
| rx_settlement_component (`rx_settlement_component`) | sum(gross_amount) of settlements in the period | accrual, amounts excl. GST |
| scn_settlement_recovery_cash (`scn_settlement_recovery_cash`) | cash_balance + sum(unlocated settlements) | accrual, amounts excl. GST |

## Appendix — source trace for key figures

| calc_id | Metric | Source |
|---|---|---|
| CALC-0001 | gross_revenue | accounts 4000 |
| CALC-0002 | sales_returns_and_allowances | accounts 4010 |
| CALC-0003 | net_revenue | accounts 4000, 4010 |
| CALC-0004 | cogs | accounts 5000, 5010, 5020 |
| CALC-0005 | gross_profit | accounts 4000, 4010, 5000, 5010, 5020 |
| CALC-0007 | operating_expenses | accounts 6000, 6010, 6020, 6030, 6040 |
| CALC-0008 | ebitda | accounts 4000, 4010, 5000, 5010, 5020, 6000, 6010, 6020, 6030, 6040 |
| CALC-0010 | operating_profit | accounts 4000, 4010, 5000, 5010, 5020, 6000, 6010, 6020, 6030, 6040, 6100 |
| CALC-0012 | profit_before_tax | accounts 4000, 4010, 4100, 5000, 5010, 5020, 6000, 6010, 6020, 6030, 6040, 6100 … |
| CALC-0013 | net_profit | accounts 4000, 4010, 4100, 5000, 5010, 5020, 6000, 6010, 6020, 6030, 6040, 6100 … |
| CALC-0017 | expense_by_category | accounts 6030 |
| CALC-0018 | expense_by_category | accounts 5010 |
| CALC-0019 | expense_by_category | accounts 6100 |
| CALC-0020 | expense_by_category | accounts 6000 |
| CALC-0021 | expense_by_category | accounts 6200 |
| CALC-0022 | expense_by_category | accounts 5020 |
| CALC-0023 | expense_by_category | accounts 6020 |
| CALC-0024 | expense_by_category | accounts 6040 |
| CALC-0025 | expense_by_category | accounts 5000 |
| CALC-0026 | expense_by_category | accounts 6010 |
| CALC-0095 | accounts_receivable | accounts 1200 |
| CALC-0096 | accounts_payable | accounts 2300 |
| CALC-0097 | inventory_value | accounts 1100 |
| CALC-0102 | outstanding_debt | accounts 2200 |
| CALC-0103 | finance_costs | accounts 6200 |
| CALC-0114 | ar_aging | ar_open_items.csv lines 2 |
| CALC-0115 | ar_aging | ar_open_items.csv lines 3 |
| CALC-0117 | ar_aging | ar_open_items.csv lines 4 |
| CALC-0118 | ar_aging | ar_open_items.csv lines 5 |
| CALC-0119 | ar_aging | ar_open_items.csv lines 6 |
| CALC-0121 | ar_aging | ar_open_items.csv lines 2, 3, 4, 5, 6 |
| CALC-0122 | ap_aging | ap_open_items.csv lines 4, 5 |
| CALC-0123 | ap_aging | ap_open_items.csv lines 3 |
| CALC-0125 | ap_aging | ap_open_items.csv lines 2 |
| CALC-0129 | ap_aging | ap_open_items.csv lines 2, 3, 4, 5 |
| CALC-0130 | revenue_by_customer | sales_lines.csv lines 2, 6, 11 |
| CALC-0131 | revenue_by_customer | sales_lines.csv lines 3, 10 |
| CALC-0132 | revenue_by_customer | sales_lines.csv lines 5, 7 |
| CALC-0133 | revenue_by_customer | sales_lines.csv lines 4, 9 |
| CALC-0134 | revenue_by_customer | sales_lines.csv lines 8, 12 |
| CALC-0135 | revenue_by_product | sales_lines.csv lines 2, 5, 10, 11 |
| CALC-0136 | revenue_by_product | sales_lines.csv lines 3, 4, 7, 12 |
| CALC-0137 | revenue_by_product | sales_lines.csv lines 6, 8, 9 |
| CALC-0138 | revenue_by_channel | sales_lines.csv lines 2, 3, 4, 6, 7, 10, 11 |
| CALC-0139 | revenue_by_channel | sales_lines.csv lines 5, 8, 9, 12 |
| CALC-0144 | budget_variance | trial_balance.csv, budget.csv lines 6 |
| CALC-0145 | budget_variance | trial_balance.csv, budget.csv lines 6 |
| CALC-0146 | budget_variance | trial_balance.csv, budget.csv lines 6 |
| CALC-0147 | budget_variance | trial_balance.csv, budget.csv lines 6 |
| CALC-0148 | budget_variance | trial_balance.csv, budget.csv lines 3 |
| CALC-0149 | budget_variance | trial_balance.csv, budget.csv lines 3 |
| CALC-0150 | budget_variance | trial_balance.csv, budget.csv lines 3 |
| CALC-0151 | budget_variance | trial_balance.csv, budget.csv lines 3 |
| CALC-0152 | budget_variance | trial_balance.csv, budget.csv lines 5 |
| CALC-0153 | budget_variance | trial_balance.csv, budget.csv lines 5 |
| CALC-0154 | budget_variance | trial_balance.csv, budget.csv lines 5 |
| CALC-0155 | budget_variance | trial_balance.csv, budget.csv lines 5 |
| CALC-0156 | budget_variance | trial_balance.csv, budget.csv lines 4 |
| CALC-0157 | budget_variance | trial_balance.csv, budget.csv lines 4 |
| CALC-0158 | budget_variance | trial_balance.csv, budget.csv lines 4 |
| CALC-0159 | budget_variance | trial_balance.csv, budget.csv lines 4 |
| CALC-0160 | budget_variance | trial_balance.csv, budget.csv lines 2 |
| CALC-0161 | budget_variance | trial_balance.csv, budget.csv lines 2 |
| CALC-0162 | budget_variance | trial_balance.csv, budget.csv lines 2 |
| CALC-0163 | budget_variance | trial_balance.csv, budget.csv lines 2 |
| CALC-0172 | rx_ar_overdue_by_customer | ar_open_items.csv lines 6 |
| CALC-0173 | rx_ar_overdue_by_customer | ar_open_items.csv lines 5 |
| CALC-0183 | rx_customer_open_receivables | ar_open_items.csv lines 2 |
| CALC-0186 | rx_msme_overdue_by_supplier | ap_open_items.csv lines 2 |
| CALC-0194 | rx_settlement_unlocated | settlements.csv, bank_transactions.csv lines 4 |

## Appendix — calculation register

| calc_id | metric | dimension | period | value | readiness |
|---|---|---|---|---:|---|
| CALC-0001 | gross_revenue | — | H1 FY2025-26 | 12000000.00 | ready |
| CALC-0002 | sales_returns_and_allowances | — | H1 FY2025-26 | 200000.00 | ready |
| CALC-0003 | net_revenue | — | H1 FY2025-26 | 11800000.00 | ready |
| CALC-0004 | cogs | — | H1 FY2025-26 | 7600000.00 | ready |
| CALC-0005 | gross_profit | — | H1 FY2025-26 | 4200000.00 | ready |
| CALC-0006 | gross_margin | — | H1 FY2025-26 | 0.3559322033898305084745762711864407 | ready |
| CALC-0007 | operating_expenses | — | H1 FY2025-26 | 2500000.00 | ready |
| CALC-0008 | ebitda | — | H1 FY2025-26 | 1700000.00 | ready |
| CALC-0009 | ebitda_margin | — | H1 FY2025-26 | 0.1440677966101694915254237288135593 | ready |
| CALC-0010 | operating_profit | — | H1 FY2025-26 | 1600000.00 | ready |
| CALC-0011 | operating_margin | — | H1 FY2025-26 | 0.1355932203389830508474576271186441 | ready |
| CALC-0012 | profit_before_tax | — | H1 FY2025-26 | 1450000.00 | ready |
| CALC-0013 | net_profit | — | H1 FY2025-26 | 1087500.00 | ready |
| CALC-0014 | net_margin | — | H1 FY2025-26 | 0.09216101694915254237288135593220339 | ready |
| CALC-0015 | effective_tax_rate | — | H1 FY2025-26 | 0.25 | ready |
| CALC-0016 | cost_to_revenue_ratio | — | H1 FY2025-26 | 0.8559322033898305084745762711864407 | ready |
| CALC-0017 | expense_by_category | account_class=advertising | H1 FY2025-26 | 200000.00 | ready |
| CALC-0018 | expense_by_category | account_class=changes_in_inventories | H1 FY2025-26 | -500000.00 | ready |
| CALC-0019 | expense_by_category | account_class=depreciation_and_amortisation | H1 FY2025-26 | 100000.00 | ready |
| CALC-0020 | expense_by_category | account_class=employee_benefits_expense | H1 FY2025-26 | 1500000.00 | ready |
| CALC-0021 | expense_by_category | account_class=finance_costs | H1 FY2025-26 | 200000.00 | ready |
| CALC-0022 | expense_by_category | account_class=freight_inward | H1 FY2025-26 | 100000.00 | ready |
| CALC-0023 | expense_by_category | account_class=marketplace_fees | H1 FY2025-26 | 400000.00 | ready |
| CALC-0024 | expense_by_category | account_class=professional_fees | H1 FY2025-26 | 100000.00 | ready |
| CALC-0025 | expense_by_category | account_class=purchases_of_stock_in_trade | H1 FY2025-26 | 8000000.00 | ready |
| CALC-0026 | expense_by_category | account_class=rent | H1 FY2025-26 | 300000.00 | ready |
| CALC-0027 | gross_revenue | — | H1 FY2024-25 | 10000000.00 | ready |
| CALC-0028 | sales_returns_and_allowances | — | H1 FY2024-25 | 100000.00 | ready |
| CALC-0029 | net_revenue | — | H1 FY2024-25 | 9900000.00 | ready |
| CALC-0030 | cogs | — | H1 FY2024-25 | 6480000.00 | ready |
| CALC-0031 | gross_profit | — | H1 FY2024-25 | 3420000.00 | ready |
| CALC-0032 | gross_margin | — | H1 FY2024-25 | 0.3454545454545454545454545454545455 | ready |
| CALC-0033 | operating_expenses | — | H1 FY2024-25 | 2150000.00 | ready |
| CALC-0034 | ebitda | — | H1 FY2024-25 | 1270000.00 | ready |
| CALC-0035 | ebitda_margin | — | H1 FY2024-25 | 0.1282828282828282828282828282828283 | ready |
| CALC-0036 | operating_profit | — | H1 FY2024-25 | 1170000.00 | ready |
| CALC-0037 | operating_margin | — | H1 FY2024-25 | 0.1181818181818181818181818181818182 | ready |
| CALC-0038 | profit_before_tax | — | H1 FY2024-25 | 960000.00 | ready |
| CALC-0039 | net_profit | — | H1 FY2024-25 | 745000.00 | ready |
| CALC-0040 | net_margin | — | H1 FY2024-25 | 0.07525252525252525252525252525252525 | ready |
| CALC-0041 | effective_tax_rate | — | H1 FY2024-25 | 0.2239583333333333333333333333333333 | ready |
| CALC-0042 | cost_to_revenue_ratio | — | H1 FY2024-25 | 0.8717171717171717171717171717171717 | ready |
| CALC-0043 | expense_by_category | account_class=advertising | H1 FY2024-25 | 150000.00 | ready |
| CALC-0044 | expense_by_category | account_class=changes_in_inventories | H1 FY2024-25 | -200000.00 | ready |
| CALC-0045 | expense_by_category | account_class=depreciation_and_amortisation | H1 FY2024-25 | 100000.00 | ready |
| CALC-0046 | expense_by_category | account_class=employee_benefits_expense | H1 FY2024-25 | 1300000.00 | ready |
| CALC-0047 | expense_by_category | account_class=finance_costs | H1 FY2024-25 | 250000.00 | ready |
| CALC-0048 | expense_by_category | account_class=freight_inward | H1 FY2024-25 | 80000.00 | ready |
| CALC-0049 | expense_by_category | account_class=marketplace_fees | H1 FY2024-25 | 300000.00 | ready |
| CALC-0050 | expense_by_category | account_class=professional_fees | H1 FY2024-25 | 100000.00 | ready |
| CALC-0051 | expense_by_category | account_class=purchases_of_stock_in_trade | H1 FY2024-25 | 6600000.00 | ready |
| CALC-0052 | expense_by_category | account_class=rent | H1 FY2024-25 | 300000.00 | ready |
| CALC-0053 | revenue_growth | — | H1 FY2025-26 | 0.1919191919191919191919191919191919 | ready |
| CALC-0054 | expense_growth | — | H1 FY2025-26 | 0.1627906976744186046511627906976744 | ready |
| CALC-0055 | period_over_period_variance | line=gross_revenue, measure=amount | H1 FY2025-26 | 2000000.00 | ready |
| CALC-0056 | period_over_period_variance | line=gross_revenue, measure=percent | H1 FY2025-26 | 0.2 | ready |
| CALC-0057 | period_over_period_variance | line=sales_returns_and_allowances, measure=amount | H1 FY2025-26 | 100000.00 | ready |
| CALC-0058 | period_over_period_variance | line=sales_returns_and_allowances, measure=percent | H1 FY2025-26 | 1 | ready |
| CALC-0059 | period_over_period_variance | line=net_revenue, measure=amount | H1 FY2025-26 | 1900000.00 | ready |
| CALC-0060 | period_over_period_variance | line=net_revenue, measure=percent | H1 FY2025-26 | 0.1919191919191919191919191919191919 | ready |
| CALC-0061 | period_over_period_variance | line=cogs, measure=amount | H1 FY2025-26 | 1120000.00 | ready |
| CALC-0062 | period_over_period_variance | line=cogs, measure=percent | H1 FY2025-26 | 0.1728395061728395061728395061728395 | ready |
| CALC-0063 | period_over_period_variance | line=gross_profit, measure=amount | H1 FY2025-26 | 780000.00 | ready |
| CALC-0064 | period_over_period_variance | line=gross_profit, measure=percent | H1 FY2025-26 | 0.2280701754385964912280701754385965 | ready |
| CALC-0065 | period_over_period_variance | line=operating_expenses, measure=amount | H1 FY2025-26 | 350000.00 | ready |
| CALC-0066 | period_over_period_variance | line=operating_expenses, measure=percent | H1 FY2025-26 | 0.1627906976744186046511627906976744 | ready |
| CALC-0067 | period_over_period_variance | line=ebitda, measure=amount | H1 FY2025-26 | 430000.00 | ready |
| CALC-0068 | period_over_period_variance | line=ebitda, measure=percent | H1 FY2025-26 | 0.3385826771653543307086614173228346 | ready |
| CALC-0069 | period_over_period_variance | line=operating_profit, measure=amount | H1 FY2025-26 | 430000.00 | ready |
| CALC-0070 | period_over_period_variance | line=operating_profit, measure=percent | H1 FY2025-26 | 0.3675213675213675213675213675213675 | ready |
| CALC-0071 | period_over_period_variance | line=profit_before_tax, measure=amount | H1 FY2025-26 | 490000.00 | ready |
| CALC-0072 | period_over_period_variance | line=profit_before_tax, measure=percent | H1 FY2025-26 | 0.5104166666666666666666666666666667 | ready |
| CALC-0073 | period_over_period_variance | line=net_profit, measure=amount | H1 FY2025-26 | 342500.00 | ready |
| CALC-0074 | period_over_period_variance | line=net_profit, measure=percent | H1 FY2025-26 | 0.4597315436241610738255033557046980 | ready |
| CALC-0075 | cost_category_variance | account_class=advertising, measure=amount | H1 FY2025-26 | 50000.00 | ready |
| CALC-0076 | cost_category_variance | account_class=advertising, measure=percent | H1 FY2025-26 | 0.3333333333333333333333333333333333 | ready |
| CALC-0077 | cost_category_variance | account_class=changes_in_inventories, measure=amount | H1 FY2025-26 | -300000.00 | ready |
| CALC-0078 | cost_category_variance | account_class=changes_in_inventories, measure=percent | H1 FY2025-26 | -1.5 | ready |
| CALC-0079 | cost_category_variance | account_class=depreciation_and_amortisation, measure=amount | H1 FY2025-26 | 0.00 | ready |
| CALC-0080 | cost_category_variance | account_class=depreciation_and_amortisation, measure=percent | H1 FY2025-26 | 0 | ready |
| CALC-0081 | cost_category_variance | account_class=employee_benefits_expense, measure=amount | H1 FY2025-26 | 200000.00 | ready |
| CALC-0082 | cost_category_variance | account_class=employee_benefits_expense, measure=percent | H1 FY2025-26 | 0.1538461538461538461538461538461538 | ready |
| CALC-0083 | cost_category_variance | account_class=finance_costs, measure=amount | H1 FY2025-26 | -50000.00 | ready |
| CALC-0084 | cost_category_variance | account_class=finance_costs, measure=percent | H1 FY2025-26 | -0.2 | ready |
| CALC-0085 | cost_category_variance | account_class=freight_inward, measure=amount | H1 FY2025-26 | 20000.00 | ready |
| CALC-0086 | cost_category_variance | account_class=freight_inward, measure=percent | H1 FY2025-26 | 0.25 | ready |
| CALC-0087 | cost_category_variance | account_class=marketplace_fees, measure=amount | H1 FY2025-26 | 100000.00 | ready |
| CALC-0088 | cost_category_variance | account_class=marketplace_fees, measure=percent | H1 FY2025-26 | 0.3333333333333333333333333333333333 | ready |
| CALC-0089 | cost_category_variance | account_class=professional_fees, measure=amount | H1 FY2025-26 | 0.00 | ready |
| CALC-0090 | cost_category_variance | account_class=professional_fees, measure=percent | H1 FY2025-26 | 0 | ready |
| CALC-0091 | cost_category_variance | account_class=purchases_of_stock_in_trade, measure=amount | H1 FY2025-26 | 1400000.00 | ready |
| CALC-0092 | cost_category_variance | account_class=purchases_of_stock_in_trade, measure=percent | H1 FY2025-26 | 0.2121212121212121212121212121212121 | ready |
| CALC-0093 | cost_category_variance | account_class=rent, measure=amount | H1 FY2025-26 | 0.00 | ready |
| CALC-0094 | cost_category_variance | account_class=rent, measure=percent | H1 FY2025-26 | 0 | ready |
| CALC-0095 | accounts_receivable | — | H1 FY2025-26 | 2200000.00 | ready |
| CALC-0096 | accounts_payable | — | H1 FY2025-26 | 1500000.00 | ready |
| CALC-0097 | inventory_value | — | H1 FY2025-26 | 2500000.00 | ready |
| CALC-0098 | working_capital | — | H1 FY2025-26 | 3987500.00 | ready |
| CALC-0099 | working_capital | variant=operating | H1 FY2025-26 | 3200000.00 | ready |
| CALC-0100 | current_ratio | — | H1 FY2025-26 | 2.981366459627329192546583850931677 | ready |
| CALC-0101 | quick_ratio | — | H1 FY2025-26 | 1.739130434782608695652173913043478 | ready |
| CALC-0102 | outstanding_debt | — | H1 FY2025-26 | 2500000.00 | ready |
| CALC-0103 | finance_costs | — | H1 FY2025-26 | 200000.00 | ready |
| CALC-0104 | interest_coverage_ratio | — | H1 FY2025-26 | 8 | ready |
| CALC-0105 | debt_to_equity | — | H1 FY2025-26 | 0.7380073800738007380073800738007380 | ready |
| CALC-0106 | inventory_turnover | — | H1 FY2025-26 | 3.377777777777777777777777777777778 | ready |
| CALC-0107 | dio | — | H1 FY2025-26 | 54.17763157894736842105263157894737 | ready |
| CALC-0108 | dso | — | H1 FY2025-26 | 25.84745762711864406779661016949152 | ready |
| CALC-0109 | dpo | — | H1 FY2025-26 | 32.50657894736842105263157894736842 | partial |
| CALC-0110 | cash_conversion_cycle | — | H1 FY2025-26 | 47.51851025869759143621766280107047 | partial |
| CALC-0111 | cash_balance | — | H1 FY2025-26 | 1280000.00 | ready |
| CALC-0112 | net_burn | — | H1 FY2025-26 | 0 | ready |
| CALC-0113 | cash_runway | — | H1 FY2025-26 | — | ready |
| CALC-0114 | ar_aging | bucket=not_due | H1 FY2025-26 | 600000.00 | ready |
| CALC-0115 | ar_aging | bucket=1_30 | H1 FY2025-26 | 500000.00 | ready |
| CALC-0116 | ar_aging | bucket=31_60 | H1 FY2025-26 | 0 | ready |
| CALC-0117 | ar_aging | bucket=61_90 | H1 FY2025-26 | 400000.00 | ready |
| CALC-0118 | ar_aging | bucket=91_180 | H1 FY2025-26 | 300000.00 | ready |
| CALC-0119 | ar_aging | bucket=181_365 | H1 FY2025-26 | 400000.00 | ready |
| CALC-0120 | ar_aging | bucket=over_365 | H1 FY2025-26 | 0 | ready |
| CALC-0121 | ar_aging | bucket=total | H1 FY2025-26 | 2200000.00 | ready |
| CALC-0122 | ap_aging | bucket=not_due | H1 FY2025-26 | 500000.00 | ready |
| CALC-0123 | ap_aging | bucket=1_30 | H1 FY2025-26 | 700000.00 | ready |
| CALC-0124 | ap_aging | bucket=31_60 | H1 FY2025-26 | 0 | ready |
| CALC-0125 | ap_aging | bucket=61_90 | H1 FY2025-26 | 300000.00 | ready |
| CALC-0126 | ap_aging | bucket=91_180 | H1 FY2025-26 | 0 | ready |
| CALC-0127 | ap_aging | bucket=181_365 | H1 FY2025-26 | 0 | ready |
| CALC-0128 | ap_aging | bucket=over_365 | H1 FY2025-26 | 0 | ready |
| CALC-0129 | ap_aging | bucket=total | H1 FY2025-26 | 1500000.00 | ready |
| CALC-0130 | revenue_by_customer | customer_id=C001 | H1 FY2025-26 | 4200000.00 | ready |
| CALC-0131 | revenue_by_customer | customer_id=C002 | H1 FY2025-26 | 3000000.00 | ready |
| CALC-0132 | revenue_by_customer | customer_id=C003 | H1 FY2025-26 | 2000000.00 | ready |
| CALC-0133 | revenue_by_customer | customer_id=C004 | H1 FY2025-26 | 1600000.00 | ready |
| CALC-0134 | revenue_by_customer | customer_id=C005 | H1 FY2025-26 | 1200000.00 | ready |
| CALC-0135 | revenue_by_product | sku=SKU-A | H1 FY2025-26 | 5400000.00 | ready |
| CALC-0136 | revenue_by_product | sku=SKU-B | H1 FY2025-26 | 4000000.00 | ready |
| CALC-0137 | revenue_by_product | sku=SKU-C | H1 FY2025-26 | 2600000.00 | ready |
| CALC-0138 | revenue_by_channel | channel=direct_b2b | H1 FY2025-26 | 9000000.00 | ready |
| CALC-0139 | revenue_by_channel | channel=marketplace_a | H1 FY2025-26 | 3000000.00 | ready |
| CALC-0140 | customer_concentration | measure=top_1_share | H1 FY2025-26 | 0.35 | ready |
| CALC-0141 | customer_concentration | measure=top_5_share | H1 FY2025-26 | 1 | ready |
| CALC-0142 | customer_concentration | measure=top_10_share | H1 FY2025-26 | 1 | ready |
| CALC-0143 | customer_concentration | measure=hhi | H1 FY2025-26 | 2405.555555555555555555555555555556 | ready |
| CALC-0144 | budget_variance | account_class=advertising, measure=actual | H1 FY2025-26 | 200000.00 | ready |
| CALC-0145 | budget_variance | account_class=advertising, measure=budget | H1 FY2025-26 | 250000.00 | ready |
| CALC-0146 | budget_variance | account_class=advertising, measure=variance | H1 FY2025-26 | -50000.00 | ready |
| CALC-0147 | budget_variance | account_class=advertising, measure=variance_pct | H1 FY2025-26 | -0.2 | ready |
| CALC-0148 | budget_variance | account_class=employee_benefits_expense, measure=actual | H1 FY2025-26 | 1500000.00 | ready |
| CALC-0149 | budget_variance | account_class=employee_benefits_expense, measure=budget | H1 FY2025-26 | 1400000.00 | ready |
| CALC-0150 | budget_variance | account_class=employee_benefits_expense, measure=variance | H1 FY2025-26 | 100000.00 | ready |
| CALC-0151 | budget_variance | account_class=employee_benefits_expense, measure=variance_pct | H1 FY2025-26 | 0.07142857142857142857142857142857143 | ready |
| CALC-0152 | budget_variance | account_class=marketplace_fees, measure=actual | H1 FY2025-26 | 400000.00 | ready |
| CALC-0153 | budget_variance | account_class=marketplace_fees, measure=budget | H1 FY2025-26 | 350000.00 | ready |
| CALC-0154 | budget_variance | account_class=marketplace_fees, measure=variance | H1 FY2025-26 | 50000.00 | ready |
| CALC-0155 | budget_variance | account_class=marketplace_fees, measure=variance_pct | H1 FY2025-26 | 0.1428571428571428571428571428571429 | ready |
| CALC-0156 | budget_variance | account_class=rent, measure=actual | H1 FY2025-26 | 300000.00 | ready |
| CALC-0157 | budget_variance | account_class=rent, measure=budget | H1 FY2025-26 | 300000.00 | ready |
| CALC-0158 | budget_variance | account_class=rent, measure=variance | H1 FY2025-26 | 0.00 | ready |
| CALC-0159 | budget_variance | account_class=rent, measure=variance_pct | H1 FY2025-26 | 0 | ready |
| CALC-0160 | budget_variance | account_class=revenue_from_operations, measure=actual | H1 FY2025-26 | 11800000.00 | ready |
| CALC-0161 | budget_variance | account_class=revenue_from_operations, measure=budget | H1 FY2025-26 | 12500000.00 | ready |
| CALC-0162 | budget_variance | account_class=revenue_from_operations, measure=variance | H1 FY2025-26 | -700000.00 | ready |
| CALC-0163 | budget_variance | account_class=revenue_from_operations, measure=variance_pct | H1 FY2025-26 | -0.056 | ready |
| CALC-0164 | marketplace_fees | provider=gateway_x | H1 FY2025-26 | 4000.00 | ready |
| CALC-0165 | marketplace_fees | provider=marketplace_a | H1 FY2025-26 | 96000.00 | ready |
| CALC-0166 | marketplace_fees | provider=all | H1 FY2025-26 | 100000.00 | ready |
| CALC-0167 | settlement_variance | class=timing | H1 FY2025-26 | 246020.00 | ready |
| CALC-0168 | settlement_variance | class=unexplained | H1 FY2025-26 | 0 | ready |
| CALC-0169 | settlement_variance | — | H1 FY2025-26 | 246020.00 | partial |
| CALC-0170 | rx_ar_overdue_total | threshold_days=90 | H1 FY2025-26 | 700000.00 | ready |
| CALC-0171 | rx_ar_overdue_share | threshold_days=90 | H1 FY2025-26 | 0.3181818181818181818181818181818182 | ready |
| CALC-0172 | rx_ar_overdue_by_customer | customer_id=C005, threshold_days=90 | H1 FY2025-26 | 400000.00 | ready |
| CALC-0173 | rx_ar_overdue_by_customer | customer_id=C004, threshold_days=90 | H1 FY2025-26 | 300000.00 | ready |
| CALC-0174 | rx_customer_revenue_share | customer_id=C004 | H1 FY2025-26 | 0.1333333333333333333333333333333333 | ready |
| CALC-0175 | rx_customer_revenue_share | customer_id=C005 | H1 FY2025-26 | 0.1 | ready |
| CALC-0176 | scn_collect_overdue_cash | — | H1 FY2025-26 | 1980000.00 | ready |
| CALC-0177 | scn_collect_overdue_dso | — | H1 FY2025-26 | 21.32415254237288135593220338983050 | ready |
| CALC-0178 | scn_collect_overdue_dso_change | — | H1 FY2025-26 | -4.52330508474576271186440677966102 | ready |
| CALC-0179 | scn_dso_reduction_cash_release | dso_reduction_days=10 | H1 FY2025-26 | 773770.4918032786885245901639344262 | ready |
| CALC-0180 | rx_customer_revenue_share | customer_id=C001 | H1 FY2025-26 | 0.35 | ready |
| CALC-0181 | rx_customer_revenue_share | customer_id=C002 | H1 FY2025-26 | 0.25 | ready |
| CALC-0182 | rx_customer_revenue_share | customer_id=C003 | H1 FY2025-26 | 0.1666666666666666666666666666666667 | ready |
| CALC-0183 | rx_customer_open_receivables | customer_id=C001 | H1 FY2025-26 | 600000.00 | ready |
| CALC-0184 | rx_budget_shortfall | account_class=revenue_from_operations | H1 FY2025-26 | 700000.00 | ready |
| CALC-0185 | rx_msme_overdue_total | max_days=45 | H1 FY2025-26 | 300000.00 | ready |
| CALC-0186 | rx_msme_overdue_by_supplier | supplier_id=S001, max_days=45 | H1 FY2025-26 | 300000.00 | ready |
| CALC-0187 | rx_msme_max_days | max_days=45 | H1 FY2025-26 | 91 | ready |
| CALC-0188 | scn_msme_clearance_cash_after | — | H1 FY2025-26 | 980000.00 | ready |
| CALC-0189 | rx_cost_growth_gap | account_class=marketplace_fees | H1 FY2025-26 | 0.1414141414141414141414141414141414 | ready |
| CALC-0190 | scn_cost_normalisation_saving | account_class=marketplace_fees | H1 FY2025-26 | 42424.2424242424242424242424242424 | ready |
| CALC-0191 | rx_budget_shortfall | account_class=marketplace_fees | H1 FY2025-26 | 50000.00 | ready |
| CALC-0192 | rx_budget_shortfall | account_class=employee_benefits_expense | H1 FY2025-26 | 100000.00 | ready |
| CALC-0193 | rx_bank_book_difference | — | H1 FY2025-26 | -20000.00 | ready |
| CALC-0194 | rx_settlement_unlocated | settlement_id=MA-SET-0003 | H1 FY2025-26 | 246020.00 | ready |
| CALC-0195 | rx_settlement_days_unlocated | settlement_id=MA-SET-0003 | H1 FY2025-26 | 5 | ready |
| CALC-0196 | rx_settlement_component | component=gross_amount | H1 FY2025-26 | 1000000.00 | ready |
| CALC-0197 | rx_settlement_component | component=fees | H1 FY2025-26 | 100000.00 | ready |
| CALC-0198 | rx_settlement_component | component=tax_on_fees | H1 FY2025-26 | 18000.00 | ready |
| CALC-0199 | rx_settlement_component | component=refunds | H1 FY2025-26 | 30000.00 | ready |
| CALC-0200 | rx_settlement_component | component=withholdings | H1 FY2025-26 | 4000.00 | ready |
| CALC-0201 | rx_settlement_component | component=adjustments | H1 FY2025-26 | 0 | ready |
| CALC-0202 | rx_settlement_component | component=net_amount | H1 FY2025-26 | 848000.00 | ready |
| CALC-0203 | scn_settlement_recovery_cash | — | H1 FY2025-26 | 1526020.00 | ready |
| CALC-0204 | rx_cost_growth_gap | account_class=advertising | H1 FY2025-26 | 0.1414141414141414141414141414141414 | ready |
| CALC-0205 | scn_cost_normalisation_saving | account_class=advertising | H1 FY2025-26 | 21212.1212121212121212121212121212 | ready |

## Disclaimer

This analysis is prepared from the data you authorised and provided, using documented methods. It is decision support, not an audit, review, tax, legal or investment opinion. Figures labelled estimate, forecast or hypothesis carry uncertainty. Please review material decisions, tax matters and statutory filings with your Chartered Accountant or other qualified adviser.
GST and income-tax data checks test consistency between datasets only and do not confirm compliance or filing correctness. Items listed for review are screening results, not findings of wrongdoing.

## Verification

| Check | Status | Details |
|---|---|---|
| ver_no_fabrication | passed | all inputs exist with matching hashes |
| ver_recompute_figures | passed | 82 figures recomputed independently and matched |
| ver_register_tieout | passed | 244 rendered figures tie to the register |
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
| ver_source_trace | passed | 75 figure(s) traced to accounts or source rows and re-added |
| ver_excel_formulas | passed | 60 formulas evaluated independently, 60 equal their register values; LibreOffice: ok (60 compared, 0 mismatches) |
| ver_chart_data | passed | 26 charted value(s) match the register |
| ver_approval_gates | passed | no external or financial action executed; prepared files match approvals |

Draft SHA-256: b1c01b47777b06b95566544379c34bff9dbdba340121c85bde2824101e6b947e
