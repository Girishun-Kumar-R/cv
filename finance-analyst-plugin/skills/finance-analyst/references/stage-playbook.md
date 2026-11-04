# Stage playbook

Operational detail for each workflow stage. The spec section to read before each stage is given in brackets;
print it with `python3 scripts/fa_spec.py section <key>` (or `get <dotted.path>` for one entry).

## 1. Onboarding  [onboarding, metadata.customer_settings]

- Load anything already known (a saved profile in the customer's chosen workspace folder, if they authorised one).
- Infer before asking: company and legal name from accounting profile, invoice or statement headers; state from
  the GSTIN's first two digits; FY from accounting settings or statement periods; basis from the presence of
  receivable/payable ledgers and accruals.
- Ask only for what `onboarding.ask_policy.ask_only_when` allows. Use one message, at most four numbered
  questions, each with a recommended default, and accept "defaults"/"skip". Example:

  ```
  I found: Sample Traders Pvt Ltd (from the trial balance header), FY April–March, accrual basis.
  Please confirm or change:
    1) Period — a) H1 FY2025-26 vs H1 FY2024-25 (recommended)  b) last 12 months  c) other
    2) Depth  — a) Simple brief (recommended)  b) Comprehensive  c) Custom sections
  Reply e.g. "1a 2a" or "defaults".
  ```
- Record each value's provenance (inferred / customer-provided / default) in `run_config.json` notes.

## 2. Connector selection and authorisation guidance  [connectors, runtime_contract.human_authorization]

- List the tools actually present in this session. Map them to catalog entries by their declared names and
  descriptions only.
- For each candidate, run one read-only probe (list organisations/accounts, or fetch one record with a narrow
  date filter). Mark it ready only if the probe succeeded.
- Present four groups: ready now; available after connecting in the app's connector settings; file import
  (always); needs custom setup (e.g. TallyPrime, Account Aggregator, gateways without connectors) with the export
  alternative from the catalog's `fallback_import_methods`.
- Authorisation guidance: tell the customer where to connect (their app's connector/integration settings or the
  provider's OAuth screen) and to come back when done. Never request or accept credentials, OTPs, API keys or
  file passwords. Re-probe after they confirm.
- Read-only even when scopes allow writes; mention this if write scopes are visible.

## 3. Data discovery  [data_discovery]

- Files: `python3 scripts/fa_discover.py --dir <folder> --out <run>/discovery.json`. It reports row counts,
  columns, template match, date coverage and amount totals without printing records.
- Connectors: entity list → dataset list → metadata (fields, earliest/latest dates, counts) using minimal pages.
- Summarise coverage only when it limits the request (e.g. "bank data covers April–August only").
- Do not open unrelated files or mailboxes; restricted data (employee-level payroll, full account numbers) only
  when the objective needs it and the customer approves.

## 4. Objective, metrics and readiness  [orchestration.objective_parsing, data_requirements, analysis_modules]

- Restate the objective in one line with entity, period, comparison and depth.
- Map to modules via their `triggers`, then to metrics. Check each metric's `required_inputs` against what is
  available. Mark readiness and, for anything not ready, name the exact file/report needed and how to export it,
  or offer a narrower valid analysis. Never substitute averages, typical values or remembered figures.
- Check which metrics the toolkit implements (`references/implementation-status.md`); plan to state any
  specified-but-not-implemented analysis as out of scope for this run.

## 5. Retrieval, normalisation and multi-source orchestration  [orchestration, source_of_truth, canonical_data_model]

- Retrieve each dataset once per run with the union of needed fields and dates; paginate to the end; respect
  rate-limit signals; stop at the retrieval boundaries in the spec and ask before expanding.
- Write canonical CSVs (`references/input-formats.md`). Use code for conversions; record each conversion
  (minor units → rupees, UTC → IST, report scale → rupees, sign conventions).
- Multiple sources for one figure: the posted ledger is the authority for accrual revenue and profit; bank
  statements for bank balances; settlement reports for fees; approved budget files for budgets. The pipeline
  shows conflicts (`CON-SALES-LEDGER`, `CON-BANK-BOOK`) with both figures — never pick one silently.
- One source for many metrics: retrieve once and reuse (the trial balance feeds most metrics).
- Account mapping: `fa_classify.py` proposes classes; ask the customer to confirm material or low-confidence
  rows in one batch; set `confirmed=yes`; unconfirmed rows stay unclassified and are disclosed.

## 6. Validation and reconciliation  [data_quality, accounting_integrity, reconciliation]

- Run `fa_run.py` (it runs checks and reconciliation before metrics). Severity effects: critical blocks
  dependent metrics; high makes them partial; medium/low are disclosed.
- Explain critical and high issues in plain language with the fix (e.g. "The trial balance does not balance by
  ₹100 — please re-export it"). Never adjust source amounts to make checks pass.
- Settlement matching: UTR matches are confirmed; exact-amount-within-window matches are probable and need
  customer confirmation before being treated as confirmed; unmatched settlements are leads, not proof of loss.

## 7. Analysis and investigation  [analysis_modules, investigation, anomaly_risk_opportunity]

- Work from `calc_register.json` and `signals.json` (material movements by the spec's materiality defaults).
- For each material movement, decompose with registered figures (e.g. revenue vs cost lines, category
  variances, aging buckets). Classify explanations as timing, volume, price/rate, mix, one-off, classification,
  accounting adjustment, data issue or unexplained, and grade evidence as confirmed/likely/hypothesis.
- Ask the customer for business context only for material hypotheses that the data cannot test; label answers
  `customer_provided`.
- Risks and opportunities: describe from evidence (concentration, overdue receivables, MSME timing flags,
  settlement gaps, liquidity). Quantify only with registered figures or `{{input:...}}` assumptions.

## 8. Recommendations  [recommendations]

- Each recommendation: specific action, rationale tied to findings, impact using placeholders, refs,
  confidence, effort, CA review flag. Prioritise by impact × confidence ÷ effort. Group into next 30 days /
  90 days when there are several.
- Exclude anything without evidence. No investment, lending-product, tax-position or filing advice.

## 9. Report depth and generation  [report_catalog, report_depth, report_generation]

- Suggest at most five report types from the catalog that fit the objective and readiness; default to the one
  answering the question. Selected reports are combined into ONE report.
- `--depth simple`: headline, KPIs, findings, recommendations, P&L, liquidity, aging, budget, settlements,
  critical/high issues, limitations, sources, disclaimer. `--depth comprehensive` adds expense categories,
  revenue breakdowns, all issues and the calculation register appendix. Custom: control content through the
  narrative and state omitted sections.

## 10. Verification and delivery  [verification, delivery, security_privacy]

- `fa_run.py` verifies automatically; exit 0 = verified, 3 = failed. Read `verification.json`, fix, re-run (max
  two loops). If still failing, remove the failing narrative items or deliver an explanation-only summary.
- In chat: 3–6 bullet summary with figures copied exactly from `report.md`, the verification line, key
  limitations, and the report path. Offer next steps (comprehensive depth, missing data that would upgrade
  partial metrics, exports).
- Converting to DOCX/PDF/XLSX: use host document skills on the verified content only; do not recompute or
  retype figures. Mention that the conversion is a rendering of the verified Markdown.
- Uploads, shares and emails need explicit approval each time; prefer drafts; do not attach raw data unless asked.
- If the session environment may be discarded, tell the customer to download or save the outputs.
