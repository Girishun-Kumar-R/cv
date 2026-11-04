# Canonical input formats

Put canonical CSV files (UTF-8, comma-separated, header row) in one data folder per run. Empty header-only
copies are in `templates/inputs/`. Only `trial_balance.csv` is needed for P&L and balance-sheet metrics; the
others enable the analyses listed. Missing files produce `needs_data`, never assumed values.

Conventions for every file:
- Dates `YYYY-MM-DD` (the normaliser converts DD/MM/YYYY and DD-Mon-YYYY).
- Amounts are plain decimals in rupees (`123456.78`), no grouping commas, no symbols; blank means unknown.
- Amounts exclude GST unless the column says tax (`tax_amount`, `tax_on_fees`).
- `currency` columns, where present, must be `INR` (toolkit v0.1).
- No Aadhaar numbers, full bank account numbers or card numbers. Use masked references such as `XXXX1234`.

| File | Columns (required in bold) | Enables |
|---|---|---|
| `trial_balance.csv` | **period_label, period_start, period_end, account_id, account_name, account_class, opening_debit, opening_credit, period_debit, period_credit, closing_debit, closing_credit** | P&L, margins, balance sheet ratios, working capital, debt, growth (with a second period), integrity checks |
| `bank_transactions.csv` | **bank_account_ref, transaction_date, narration, debit, credit, balance**, value_date, reference, currency, category (`operating`, `investing`, `financing`, `transfer`) | cash balance (bank authority), net burn, runway, settlement-to-bank matching, running-balance checks |
| `ar_open_items.csv` | **customer_id, invoice_number, invoice_date, amount_outstanding**, customer_name, customer_gstin, due_date, currency | receivables aging, AR tie-out to the ledger |
| `ap_open_items.csv` | **supplier_id, bill_number, bill_date, amount_outstanding**, supplier_name, supplier_gstin, msme_classification (`micro`, `small`, `medium`, `not_msme`, `unknown`), due_date, currency | payables aging, AP tie-out, MSME timing flags |
| `sales_lines.csv` | **invoice_number, invoice_date, customer_id, taxable_value, tax_amount**, customer_name, sku, channel, quantity, currency | revenue by customer/product/channel, concentration, DSO denominator incl. GST |
| `budget.csv` | **budget_version, approval_status (`approved`/`draft`), period_label, account_class, amount**, amount_basis (`net_revenue` (default for revenue), `gross_revenue`, `tax_exclusive`, `tax_inclusive` → blocked) | budget vs actual by account class on a stated basis |
| `settlements.csv` | **provider, settlement_id, settlement_date, gross_amount, fees, net_amount**, tax_on_fees, refunds, withholdings, adjustments, bank_reference (UTR), currency | settlement arithmetic check, settlement-to-bank reconciliation, fees, settlement variance |
| `journal_lines.csv` | **journal_id, posting_date, account_id, debit, credit**, narration | debit = credit check per voucher |

## Trial balance rules

- One row per account per period; `period_label` must equal the labels in `run_config.json`.
- `account_class` must be one of the canonical classes in spec `canonical_data_model.account_classes`
  (for example `revenue_from_operations`, `trade_receivables`, `gst_payable`, `employee_benefits_expense`).
  Use `fa_classify.py` to propose them and confirm material ones with the customer.
- Each row satisfies opening + period debits − period credits = closing (checked). The whole TB must balance
  for opening, period and closing columns (checked; failure blocks all TB metrics).
- For a period that starts at the financial-year start, P&L accounts have zero opening balances.
- If only two "as at" trial balances exist (e.g. TallyPrime exports at 1-Apr and 30-Sep), use
  `templates/mappings/tally_trial_balance_two_snapshots.json`; movements are then net per ledger.

## Monthly or quarterly breakdown

Add one trial-balance block per month (its own `period_label`, e.g. `2026-01`, with opening, movement and
closing for that month) in the same `trial_balance.csv` as the period total. Months inside the current period
are detected automatically (or list them in `run_config.sub_periods`). The roll-up check `ai_period_rollup`
requires the months to cover the period contiguously, the month movements per account to add up to the period
movement, each month's closing to equal the next month's opening, and the first and last months to match the
period's opening and closing. If not, the monthly breakdown is withheld (period figures are unaffected) and the
accounts and months that differ are listed.

## Mapping connector data

| Source | Canonical file | Notes |
|---|---|---|
| Accounting trial balance / P&L / balance sheet reports (Zoho Books, Xero, QuickBooks, TallyPrime exports) | `trial_balance.csv` | Prefer a trial balance with opening/movement/closing; map ledgers to classes |
| Accounting AR/AP aging or open invoices/bills | `ar_open_items.csv`, `ap_open_items.csv` | Must tie to the TB control accounts at the period end |
| Accounting sales register / invoice lines | `sales_lines.csv` | Taxable value and tax separately |
| Bank statements or bank connector | `bank_transactions.csv` | Keep statement order; mask account numbers |
| Razorpay / Stripe / PayU / marketplace settlement reports | `settlements.csv` | Razorpay and Stripe amounts are in the smallest currency unit — divide by 100 for INR; convert Unix/UTC timestamps to IST dates; statutory withholdings (TCS/TDS) go in `withholdings`, not `fees` |
| Budget spreadsheets | `budget.csv` | Map budget lines to account classes; record approval status |

## Mapping files for `fa_normalize.py`

A mapping is a JSON file next to (or pointing to) the raw export. Key options: `kind`, `source_file`, `columns`,
`constants`, `dayfirst`, `skip_first_cell_patterns`, `amount_scale` (e.g. `"100000"` for exports in lakhs),
`minor_units`, `signed_to_split`, `drcr_to_split` (for `"1,234.00 Dr"` cells), `blank_pair_zero` (bank
withdrawal/deposit columns where one side is blank), `class_map_file`, `allow_unconfirmed_classes` (default
false), and `mode: "two_snapshots"` for trial balances. Run `python3 scripts/fa_normalize.py --help` for the
full list. The normaliser writes `<out>.log.json` with skipped rows, conversions, errors and date-orientation
evidence; resolve every error and warning before running the pipeline.

## Run configuration

Copy `templates/run_config.template.json`. Required: `company_name`, `current_period {label, start, end}`.
Optional: `comparison_period`, `entity_gstins`, `materiality`, `reconciliation.settlement_to_bank_days`,
`reconciliation.customer_confirmed_matches` (settlement ids the customer confirmed after a reflex
`customer_confirmation` request), `net_burn_window_months`, `credit_purchases_incl_tax` (only if supplied by the
customer or a purchase register), and `reflex` (overrides for `templates/reflex_rules.json`; see
`references/reflex-engine.md`).
