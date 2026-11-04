# Finance Analyst AI — Claude plugin

An agentic financial analyst and virtual CFO for Indian SMEs and MSMEs. It follows the master specification
`skills/finance-analyst/finance-analyst.yaml` (v1.1.0) and uses bundled, tested Python scripts for every figure.
It is read-only and runs only when you ask.

## What it does

- Guides first-time onboarding and asks only essential questions.
- Explains which data sources are usable in your session, how to connect them in your app's settings, and how to
  export files when no connector exists. It never asks for passwords, OTPs or API keys.
- Discovers what is in your files (`fa_discover.py`), proposes account classes for Tally-style ledgers
  (`fa_classify.py`) and converts raw exports into standard formats (`fa_normalize.py`).
- Runs data-quality and accounting-integrity checks, reconciles settlements to bank and shows source conflicts.
- Calculates 48 financial metrics with exact decimal arithmetic and a calculation register.
- Lets Claude write findings and recommendations that cite evidence, with every figure inserted from the
  register.
- Produces one combined Markdown report and verifies it independently before presenting it.

See `skills/finance-analyst/references/implementation-status.md` for exactly what is implemented and what is
specified only (forecasting, scenarios, charts and some checks are specified but not implemented).

## Install

Claude Desktop → Customize → Plugins → Upload a plugin → choose `finance-analyst-plugin.zip`.

Requirements in the session where it runs:
- Code execution with Python 3.8 or later (the scripts use the standard library only).
- Optional: PyYAML (`fa_spec.py validate` and `get`), openpyxl (reading `.xlsx` during discovery).
- Your own data: connectors you have authorised in the app, or exported files.

## Try it

Ask, for example:
- "Run a financial health check on the sample company in the finance-analyst plugin."
- "Here are my Tally trial balances and bank statement — why is cash low although we made a profit?"
- "Check my receivables aging and tell me who to follow up first."
- "Reconcile my marketplace settlements with the bank statement."

Self-test from `skills/finance-analyst/`: `python3 -m unittest discover -s tests` (24 tests).

## Privacy and safety

- Read-only: no postings, payments, refunds, filings, emails or setting changes without your explicit approval
  for that specific action (and posting or payment actions are never performed).
- Credentials are never requested in chat. Account numbers are masked in outputs.
- Analysis files stay where you put them; nothing is uploaded unless you ask.
- Decision support only — not an audit, tax, legal or investment opinion. Review tax and statutory matters with
  your Chartered Accountant.

## Contents

```
.claude-plugin/plugin.json
skills/finance-analyst/
  SKILL.md                   adapter instructions for Claude
  finance-analyst.yaml       master specification
  scripts/                   fa_spec, fa_discover, fa_classify, fa_normalize, fa_run (+ checks, reconcile,
                             metrics, report), fa_verify
  references/                stage playbook, input formats, narrative format, implementation status
  templates/                 canonical CSV headers, run config, narrative, example mappings
  examples/                  synthetic sample company and Tally-style raw exports (fictional data)
  tests/                     acceptance tests
```
