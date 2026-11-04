"""Data-quality (§11) and accounting-integrity (§12) checks on canonical inputs.

Every issue uses a check_id defined in finance-analyst.yaml. Checks never
correct values; they record issues with severity, evidence and what they block.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from decimal import Decimal

from fa_common import (ALL_CLASSES, ASSET_CLASSES, EQUITY_CLASSES, EXPENSE_CLASSES, INCOME_CLASSES,
                       LIABILITY_CLASSES, SPECIAL_CLASSES, TEMPLATES, TRADE_PAYABLE_CLASSES, ZERO, validate_gstin)
from fa_data import natural, oriented, signed_debit, tb_periods

ROUNDING_AGGREGATE = Decimal("10.00")
SEVERITY_ORDER = ["critical", "high", "medium", "low", "informational"]
TAX_TOKENS = re.compile(r"\b(gst|cgst|sgst|igst|utgst|cess|tds|tcs)\b", re.IGNORECASE)
FINANCING_TOKENS = re.compile(r"\b(loan|capital introduced|share application|od a/?c|overdraft)\b", re.IGNORECASE)

# Which metric groups an issue on a dataset affects.
DATASET_GROUP = {"trial_balance": "tb", "bank_transactions": "bank", "ar_open_items": "ar",
                 "ap_open_items": "ap", "sales_lines": "sales", "budget": "budget",
                 "settlements": "settlements", "journal_lines": "journals"}


class IssueLog:
    def __init__(self, materiality_abs):
        self.items = []
        self.materiality_abs = materiality_abs

    def add(self, check_id, severity, dataset, description, records=0, amount=None, blocks=None,
            evidence=None, escalate=True):
        if (escalate and severity == "medium" and amount is not None
                and abs(amount) >= self.materiality_abs and check_id.startswith("dq_")):
            severity = "high"
        issue = {
            "issue_id": f"ISS-{len(self.items) + 1:04d}",
            "check_id": check_id,
            "severity": severity,
            "dataset": dataset,
            "records_affected": records,
            "amount_affected": None if amount is None else format(amount, "f"),
            "description": description,
            "status": "open",
            "blocks": blocks if blocks is not None else ([DATASET_GROUP[dataset]] if dataset in DATASET_GROUP
                                                          else []),
            "evidence": evidence or [],
        }
        self.items.append(issue)
        return issue


def _structure_checks(data, log):
    for kind, ds in data["datasets"].items():
        tpl = TEMPLATES[kind]
        if ds["missing_columns"]:
            log.add("dq_empty_fields", "critical", kind,
                    f"{ds['file']}: required column(s) missing: {', '.join(ds['missing_columns'])}.",
                    records=ds["row_count"])
        date_errs = [e for e in ds["parse_errors"] if e["type"] == "date"]
        val_errs = [e for e in ds["parse_errors"] if e["type"] != "date"]
        if date_errs:
            log.add("dq_invalid_dates", "high", kind,
                    f"{ds['file']}: {len(date_errs)} cell(s) with unparseable dates.", records=len(date_errs),
                    evidence=[f"line {e['line']} {e['column']}={e['value']!r}" for e in date_errs[:10]])
        if val_errs:
            log.add("dq_invalid_values", "high", kind,
                    f"{ds['file']}: {len(val_errs)} cell(s) that are not valid numbers.", records=len(val_errs),
                    evidence=[f"line {e['line']} {e['column']}={e['value']!r}" for e in val_errs[:10]])
        blanks = []
        for r in ds["rows"]:
            for col in tpl["required"]:
                if col in ds["headers"] and r.get(col) is None and not any(
                        e["line"] == r["_line"] and e["column"] == col for e in ds["parse_errors"]):
                    blanks.append((r["_line"], col))
        if blanks:
            amount_blank = [b for b in blanks if tpl["columns"][b[1]] == "dec"]
            # A blank trial-balance amount would otherwise be read as zero: block rather than assume.
            sev = "critical" if kind == "trial_balance" and amount_blank else "high"
            log.add("dq_empty_fields", sev, kind,
                    f"{ds['file']}: {len(blanks)} required cell(s) are blank"
                    + (" (blank amounts are never treated as zero)." if amount_blank else "."), records=len(blanks),
                    evidence=[f"line {ln} {col}" for ln, col in blanks[:10]])


def _currency_checks(data, config, log):
    run_ccy = config.get("currency", "INR")
    for kind, ds in data["datasets"].items():
        if "currency" not in ds["headers"]:
            continue
        other = [r for r in ds["rows"] if r.get("currency") and r["currency"].upper() != run_ccy]
        if other:
            log.add("dq_currency_mismatch", "critical", kind,
                    f"{ds['file']}: {len(other)} row(s) not in {run_ccy}; amounts are not added without documented "
                    f"conversion.", records=len(other),
                    evidence=[f"line {r['_line']} currency={r['currency']}" for r in other[:10]])


def _tb_checks(data, config, log):
    periods = tb_periods(data)
    if not periods:
        return
    wanted = {}
    for key in ("current_period", "comparison_period"):
        p = config.get(key)
        if p:
            wanted[p["label"]] = p
    for label, p in wanted.items():
        tbp = periods.get(label)
        if not tbp:
            log.add("dq_period_incompatibility", "high", "trial_balance",
                    f"Trial balance has no rows for period '{label}' named in the run configuration.")
            continue
        if (tbp["start"] and tbp["start"].isoformat() != p["start"]) or (
                tbp["end"] and tbp["end"].isoformat() != p["end"]):
            log.add("dq_period_incompatibility", "high", "trial_balance",
                    f"Period '{label}' dates in the trial balance ({tbp['start']} to {tbp['end']}) differ from the "
                    f"configuration ({p['start']} to {p['end']}).")
    main_labels = {(config.get("current_period") or {}).get("label"), (config.get("comparison_period") or {}).get("label")}
    for label, p in periods.items():
        before = len(log.items)
        _tb_period_checks(label, p, log)
        if label not in main_labels:
            for issue in log.items[before:]:
                issue["blocks"] = ["tb_months"]
                issue["description"] = f"[sub-period] {issue['description']}"


def _tb_period_checks(label, p, log):
    if True:
        rows = p["rows"]
        bad_class = [r for r in rows if r.get("account_class") and r["account_class"] not in ALL_CLASSES]
        if bad_class:
            log.add("dq_invalid_values", "high", "trial_balance",
                    f"Period {label}: {len(bad_class)} account(s) use an unknown account_class.",
                    records=len(bad_class),
                    evidence=[f"{r['account_name']} -> {r['account_class']}" for r in bad_class[:10]])
        missing = [r for r in rows if not r.get("account_class")]
        if missing:
            amt = sum((abs(signed_debit(r, "closing")) for r in missing), ZERO)
            log.add("dq_missing_category", "medium", "trial_balance",
                    f"Period {label}: {len(missing)} account(s) have no account_class.", records=len(missing),
                    amount=amt, evidence=[r["account_name"] for r in missing[:10]])
        special = [r for r in rows if r.get("account_class") in SPECIAL_CLASSES
                   and (signed_debit(r, "closing") != 0 or signed_debit(r, "period") != 0)]
        if special:
            amt = sum((abs(signed_debit(r, "closing")) for r in special), ZERO)
            sev = "high" if amt >= log.materiality_abs else "medium"
            log.add("ai_suspense_and_unclassified", sev, "trial_balance",
                    f"Period {label}: suspense/unclassified/intercompany balances present.", records=len(special),
                    amount=amt, evidence=[f"{r['account_name']} ({r['account_class']})" for r in special[:10]])
        for which in ("opening", "period", "closing"):
            dr = sum((r.get(f"{which}_debit") or ZERO for r in rows), ZERO)
            cr = sum((r.get(f"{which}_credit") or ZERO for r in rows), ZERO)
            if dr != cr:
                log.add("ai_trial_balance", "critical", "trial_balance",
                        f"Period {label}: {which} debits ({dr}) do not equal {which} credits ({cr}).",
                        amount=dr - cr, evidence=[f"difference {dr - cr}"])
        broken = []
        for r in rows:
            if signed_debit(r, "opening") + signed_debit(r, "period") != signed_debit(r, "closing"):
                broken.append(r)
        if broken:
            log.add("ai_opening_closing_rollforward", "high", "trial_balance",
                    f"Period {label}: {len(broken)} account(s) where opening + movement does not equal closing.",
                    records=len(broken), evidence=[r["account_name"] for r in broken[:10]])
        def grp(classes, side):
            return sum((oriented(r, "closing", side) for r in rows if r.get("account_class") in classes), ZERO)
        assets = grp(ASSET_CLASSES | SPECIAL_CLASSES, "debit")
        liab = grp(LIABILITY_CLASSES, "credit")
        equity = grp(EQUITY_CLASSES, "credit")
        income = grp(INCOME_CLASSES, "credit")
        expense = grp(EXPENSE_CLASSES, "debit")
        if assets != liab + equity + (income - expense):
            diff = assets - (liab + equity + income - expense)
            log.add("ai_balance_sheet_equation", "critical", "trial_balance",
                    f"Period {label}: assets do not equal liabilities + equity + unappropriated profit "
                    f"(difference {diff}).", amount=diff)
        tax_named = [r for r in rows if TAX_TOKENS.search(r.get("account_name") or "")
                     and r.get("account_class") in {"revenue_from_operations", "other_operating_revenue",
                                                    "other_income", "purchases_of_stock_in_trade",
                                                    "cost_of_materials_consumed"}]
        fin_named = [r for r in rows if FINANCING_TOKENS.search(r.get("account_name") or "")
                     and r.get("account_class") in INCOME_CLASSES]
        if tax_named or fin_named:
            amt = sum((abs(signed_debit(r, "period")) for r in tax_named + fin_named), ZERO)
            log.add("dq_misclassification", "high" if fin_named else "medium", "trial_balance",
                    f"Period {label}: account(s) whose names suggest tax or financing items are classified as "
                    f"revenue/purchases; please confirm the mapping.", records=len(tax_named) + len(fin_named),
                    amount=amt, evidence=[f"{r['account_name']} -> {r['account_class']}" for r in
                                          (tax_named + fin_named)[:10]])


def _rollup_checks(data, config, log):
    """ai_period_rollup: sub-period (monthly/quarterly) trial balances must roll up to the period total."""
    import datetime as _dt
    periods = tb_periods(data)
    cur = config.get("current_period") or {}
    tot = periods.get(cur.get("label"))
    if not tot:
        return
    s, e = _dt.date.fromisoformat(cur["start"]), _dt.date.fromisoformat(cur["end"])
    skip = {cur["label"], (config.get("comparison_period") or {}).get("label")}
    wanted = config.get("sub_periods")
    subs = sorted((p for lbl, p in periods.items() if lbl not in skip and p["start"] and p["end"]
                   and s <= p["start"] and p["end"] <= e and (wanted is None or lbl in wanted)),
                  key=lambda p: p["start"])
    if not subs:
        return
    problems = []
    if subs[0]["start"] != s or subs[-1]["end"] != e or any(
            b["start"] != a["end"] + _dt.timedelta(days=1) for a, b in zip(subs, subs[1:])):
        problems.append("sub-periods do not cover the period contiguously: "
                        + ", ".join(f"{p['label']} ({p['start']}..{p['end']})" for p in subs))
    acc = lambda p: {r["account_id"]: r for r in p["rows"]}  # noqa: E731
    tot_a = acc(tot)
    sub_a = [acc(p) for p in subs]
    for aid, r in sorted(tot_a.items()):
        mv = sum((signed_debit(m[aid], "period") for m in sub_a if aid in m), ZERO)
        if mv != signed_debit(r, "period"):
            problems.append(f"account {aid} ({r.get('account_name')}): months sum to {mv}, period shows "
                            f"{signed_debit(r, 'period')}")
    for aid, r in sorted(tot_a.items()):
        first_o = signed_debit(sub_a[0][aid], "opening") if aid in sub_a[0] else ZERO
        last_c = signed_debit(sub_a[-1][aid], "closing") if aid in sub_a[-1] else ZERO
        if first_o != signed_debit(r, "opening"):
            problems.append(f"{subs[0]['label']} opening differs from {cur['label']} opening for account {aid} "
                            f"({first_o} vs {signed_debit(r, 'opening')})")
        if last_c != signed_debit(r, "closing"):
            problems.append(f"{subs[-1]['label']} closing differs from {cur['label']} closing for account {aid} "
                            f"({last_c} vs {signed_debit(r, 'closing')})")
    for (pa, ma), (pb, mb) in zip(zip(subs, sub_a), zip(subs[1:], sub_a[1:])):
        for aid in sorted(set(ma) | set(mb)):
            ca = signed_debit(ma[aid], "closing") if aid in ma else ZERO
            ob = signed_debit(mb[aid], "opening") if aid in mb else ZERO
            if ca != ob:
                problems.append(f"{pa['label']} closing differs from {pb['label']} opening for account {aid} "
                                f"({ca} vs {ob})")

    def profit(p):
        return (sum((natural(r, "period") for r in p["rows"] if r.get("account_class") in INCOME_CLASSES
                     and r["account_class"] != "sales_returns_and_allowances"), ZERO)
                - sum((natural(r, "period") for r in p["rows"] if r["account_class"] == "sales_returns_and_allowances"),
                      ZERO)
                - sum((natural(r, "period") for r in p["rows"] if r.get("account_class") in EXPENSE_CLASSES), ZERO))
    month_profit = [(p["label"], profit(p)) for p in subs]
    if problems:
        diff = profit(tot) - sum((v for _, v in month_profit), ZERO)
        log.add("ai_period_rollup", "critical", "trial_balance",
                f"Sub-period trial balances do not roll up to {cur['label']}: profit after all booked expenses by "
                f"sub-period {', '.join(f'{lbl} {v}' for lbl, v in month_profit)} vs period {profit(tot)} "
                f"(difference {diff}). The monthly breakdown is withheld; period totals come from the period trial "
                "balance.", records=len(problems), amount=diff, blocks=["tb_months"], evidence=problems[:12])


def _bank_checks(data, config, log):
    ds = data["datasets"].get("bank_transactions")
    if not ds:
        return
    by_acct = defaultdict(list)
    for r in ds["rows"]:
        by_acct[r.get("bank_account_ref")].append(r)
    for acct, rows in by_acct.items():
        breaks = []
        for prev, cur in zip(rows, rows[1:]):
            if None in (prev.get("balance"), cur.get("balance")):
                continue
            expected = prev["balance"] + (cur.get("credit") or ZERO) - (cur.get("debit") or ZERO)
            if expected != cur["balance"]:
                breaks.append((cur["_line"], expected, cur["balance"]))
        if breaks:
            log.add("dq_missing_records", "high", "bank_transactions",
                    f"Account {acct}: running balance breaks at {len(breaks)} line(s) - rows may be missing or "
                    f"out of order.", records=len(breaks),
                    evidence=[f"line {ln}: expected {e}, statement shows {b}" for ln, e, b in breaks[:10]])
        keys = Counter((r.get("transaction_date"), r.get("narration"), r.get("debit"), r.get("credit"),
                        r.get("balance")) for r in rows)
        dups = [k for k, n in keys.items() if n > 1]
        if dups:
            amt = sum(((k[2] or ZERO) + (k[3] or ZERO) for k in dups), ZERO)
            log.add("dq_duplicates", "high", "bank_transactions",
                    f"Account {acct}: {len(dups)} exact duplicate statement line(s).", records=len(dups), amount=amt)
        dated = sorted(r["transaction_date"] for r in rows if r.get("transaction_date"))
        cur = config.get("current_period")
        if dated and cur:
            import datetime as _dt
            end = _dt.date.fromisoformat(cur["end"])
            start = _dt.date.fromisoformat(cur["start"])
            if (end - dated[-1]).days > 2:
                log.add("dq_stale_data", "medium", "bank_transactions",
                        f"Account {acct}: latest statement line is {dated[-1]} but the period ends {end}; "
                        f"cash figures are 'to {dated[-1]}'.", escalate=False)
            in_period = [d for d in dated if start <= d <= end]
            gaps = [(a, b) for a, b in zip(in_period, in_period[1:]) if (b - a).days > 10]
            if gaps:
                log.add("dq_date_gaps", "medium", "bank_transactions",
                        f"Account {acct}: {len(gaps)} gap(s) longer than 10 days without statement lines - "
                        f"confirm no statement pages are missing.", records=len(gaps),
                        evidence=[f"{a} to {b}" for a, b in gaps[:10]], escalate=False)


def _subledger_checks(data, config, log):
    periods = tb_periods(data)
    cur = config.get("current_period") or {}
    tbp = periods.get(cur.get("label"))
    import datetime as _dt
    as_of = _dt.date.fromisoformat(cur["end"]) if cur.get("end") else None
    for kind, classes, check, party, docno in (
            ("ar_open_items", {"trade_receivables"}, "ai_ar_aging_tieout", "customer_id", "invoice_number"),
            ("ap_open_items", TRADE_PAYABLE_CLASSES, "ai_ap_aging_tieout", "supplier_id", "bill_number")):
        ds = data["datasets"].get(kind)
        if not ds:
            continue
        dups = [k for k, n in Counter((r.get(party), r.get(docno)) for r in ds["rows"]).items() if n > 1]
        if dups:
            log.add("dq_duplicates", "high", kind, f"{ds['file']}: {len(dups)} duplicated document number(s).",
                    records=len(dups), evidence=[f"{p} / {d}" for p, d in dups[:10]])
        neg = [r for r in ds["rows"] if (r.get("amount_outstanding") or ZERO) < 0]
        if neg:
            log.add("dq_unexpected_negative", "medium", kind,
                    f"{ds['file']}: {len(neg)} negative outstanding amount(s) (advances or unapplied credits?).",
                    records=len(neg), amount=sum((r["amount_outstanding"] for r in neg), ZERO))
        if tbp:
            sub_total = sum((r.get("amount_outstanding") or ZERO for r in ds["rows"]), ZERO)
            ctrl = sum((natural(r, "closing") for r in tbp["rows"] if r.get("account_class") in classes), ZERO)
            if abs(sub_total - ctrl) > ROUNDING_AGGREGATE:
                log.add(check, "high", kind,
                        f"Open items total {sub_total} does not agree with the control account balance {ctrl} at "
                        f"{cur.get('end')} (difference {sub_total - ctrl}).", amount=sub_total - ctrl)
    ap = data["datasets"].get("ap_open_items")
    if ap and as_of:
        late = [r for r in ap["rows"] if (r.get("msme_classification") or "").lower() in {"micro", "small"}
                and r.get("bill_date") and (as_of - r["bill_date"]).days > 45]
        if late:
            amt = sum((r.get("amount_outstanding") or ZERO for r in late), ZERO)
            log.add("ai_msme_payables_timing", "medium", "ap_open_items",
                    f"{len(late)} bill(s) from suppliers classified micro/small are outstanding more than 45 days "
                    f"after bill date. Flag for professional review of payment-timing implications; applicability "
                    f"depends on supplier registration, activity and agreed terms.", records=len(late), amount=amt,
                    blocks=[], escalate=False,
                    evidence=[f"{r.get('supplier_name') or r.get('supplier_id')} {r.get('bill_number')} "
                              f"({(as_of - r['bill_date']).days} days)" for r in late[:10]])
        unknown = [r for r in ap["rows"] if not r.get("msme_classification")
                   or r["msme_classification"].lower() == "unknown"]
        if unknown:
            log.add("ai_msme_payables_timing", "informational", "ap_open_items",
                    f"{len(unknown)} open bill(s) have no MSME classification; MSME timing could not be assessed "
                    f"for them.", records=len(unknown), blocks=[], escalate=False)


def _gstin_checks(data, config, log):
    seen = []
    for g in config.get("entity_gstins", []):
        seen.append(("run configuration", g))
    for kind, col in (("ar_open_items", "customer_gstin"), ("ap_open_items", "supplier_gstin")):
        ds = data["datasets"].get(kind)
        if ds and col in ds["headers"]:
            seen.extend((ds["file"], r[col]) for r in ds["rows"] if r.get(col))
    bad = []
    for src, g in seen:
        ok, why = validate_gstin(g)
        if not ok:
            bad.append(f"{src}: {g} ({why})")
    if bad:
        log.add("ai_gstin_structure", "medium", "configuration" if not seen else "multiple",
                f"{len(bad)} GSTIN(s) fail the structure/check-character test.", records=len(bad), evidence=bad[:10],
                blocks=[])


def _journal_checks(data, log):
    ds = data["datasets"].get("journal_lines")
    if not ds:
        return
    totals = defaultdict(lambda: [ZERO, ZERO])
    for r in ds["rows"]:
        t = totals[r.get("journal_id")]
        t[0] += r.get("debit") or ZERO
        t[1] += r.get("credit") or ZERO
    bad = {j: t for j, t in totals.items() if t[0] != t[1]}
    if bad:
        log.add("ai_debit_credit_balance", "critical", "journal_lines",
                f"{len(bad)} journal(s) where debits do not equal credits.", records=len(bad),
                amount=sum((t[0] - t[1] for t in bad.values()), ZERO),
                evidence=[f"{j}: Dr {t[0]} / Cr {t[1]}" for j, t in list(bad.items())[:10]], blocks=["tb"])


def _settlement_checks(data, log):
    ds = data["datasets"].get("settlements")
    if not ds:
        return
    dups = [k for k, n in Counter(r.get("settlement_id") for r in ds["rows"]).items() if n > 1]
    if dups:
        log.add("dq_duplicates", "high", "settlements", f"{len(dups)} duplicated settlement id(s).",
                records=len(dups), evidence=dups[:10])
    bad = []
    for r in ds["rows"]:
        if r.get("gross_amount") is None or r.get("net_amount") is None:
            continue
        expected = (r["gross_amount"] - (r.get("fees") or ZERO) - (r.get("tax_on_fees") or ZERO)
                    - (r.get("refunds") or ZERO) - (r.get("withholdings") or ZERO) + (r.get("adjustments") or ZERO))
        if expected != r["net_amount"]:
            bad.append((r, expected))
    if bad:
        log.add("ai_settlement_reconciliation", "high", "settlements",
                f"{len(bad)} settlement(s) whose components do not add up to the net amount.", records=len(bad),
                amount=sum((r["net_amount"] - e for r, e in bad), ZERO),
                evidence=[f"{r['settlement_id']}: components give {e}, net shown {r['net_amount']}" for r, e in
                          bad[:10]])


def _budget_checks(data, log):
    ds = data["datasets"].get("budget")
    if not ds:
        return
    unapproved = [r for r in ds["rows"] if (r.get("approval_status") or "").lower() != "approved"]
    if unapproved:
        log.add("dq_invalid_values", "informational", "budget",
                f"{len(unapproved)} budget line(s) are not marked approved; variance against them is labelled "
                f"'unapproved budget'.", records=len(unapproved), blocks=[], escalate=False)


def run_checks(data, config):
    log = IssueLog(Decimal(str(config.get("materiality", {}).get("absolute_floor_inr", "25000"))))
    _structure_checks(data, log)
    _currency_checks(data, config, log)
    _tb_checks(data, config, log)
    _rollup_checks(data, config, log)
    _bank_checks(data, config, log)
    _subledger_checks(data, config, log)
    _gstin_checks(data, config, log)
    _journal_checks(data, log)
    _settlement_checks(data, log)
    _budget_checks(data, log)
    return log


def blocked_and_partial_groups(issues):
    blocked, partial = defaultdict(list), defaultdict(list)
    for i in issues:
        for g in i.get("blocks", []):
            if i["severity"] == "critical":
                blocked[g].append(i["issue_id"])
            elif i["severity"] == "high":
                partial[g].append(i["issue_id"])
    return blocked, partial
