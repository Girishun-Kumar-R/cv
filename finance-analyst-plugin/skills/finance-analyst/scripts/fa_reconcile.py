"""Cross-source reconciliation (§10) and source-of-truth conflicts (§8).

Implemented rules:
  rec_settlement_to_bank  - gateway/marketplace settlements to bank credits
Conflict records:
  sales register (sales_lines) vs ledger gross revenue (trial balance)
  bank statement balance vs book bank balance (trial balance)
"""
from __future__ import annotations

import datetime as _dt
from decimal import Decimal

from fa_common import ZERO, fmt_money
from fa_data import natural, tb_periods

ROUNDING_DOC = Decimal("1.00")
ROUNDING_AGG = Decimal("10.00")


def _tokens(text):
    return {t for t in (text or "").upper().replace("/", " ").replace("-", " ").split() if len(t) >= 3}


def reconcile_settlements_to_bank(data, config, issues_log):
    st = data["datasets"].get("settlements")
    bank = data["datasets"].get("bank_transactions")
    result = {"rule_id": "rec_settlement_to_bank", "status": "not_run", "records": [], "summary": {}}
    if not st or not bank:
        result["status"] = "needs_data"
        result["reason"] = "Needs both settlements.csv and bank_transactions.csv."
        return result
    window = int(config.get("reconciliation", {}).get("settlement_to_bank_days", 5))
    confirmed_by_customer = set(config.get("reconciliation", {}).get("customer_confirmed_matches", []))
    credits = [r for r in bank["rows"] if (r.get("credit") or ZERO) > 0]
    used = set()
    records = []
    for s in st["rows"]:
        net = s.get("net_amount")
        ref = (s.get("bank_reference") or "").strip().upper()
        strong = [b for b in credits if ref and b["_line"] not in used and (
            ref == (b.get("reference") or "").strip().upper() or ref in (b.get("narration") or "").upper())]
        rec = {"settlement_id": s.get("settlement_id"), "provider": s.get("provider"),
               "settlement_date": s.get("settlement_date"), "expected_net": net, "bank_line": None,
               "bank_amount": None, "difference": None, "match_status": "unmatched", "match_basis": []}
        if len(strong) == 1:
            b = strong[0]
            used.add(b["_line"])
            diff = b["credit"] - net
            rec.update(bank_line=b["_line"], bank_amount=b["credit"], difference=diff,
                       match_basis=["bank reference (UTR) equals settlement bank_reference"])
            rec["match_status"] = "confirmed_match" if abs(diff) <= ROUNDING_DOC else "conflicting"
        elif len(strong) > 1:
            rec["match_status"] = "conflicting"
            rec["match_basis"] = [f"{len(strong)} bank lines carry the same reference"]
        else:
            cands = []
            for b in credits:
                if b["_line"] in used or s.get("settlement_date") is None or b.get("transaction_date") is None:
                    continue
                lag = (b["transaction_date"] - s["settlement_date"]).days
                if 0 <= lag <= window and b["credit"] == net:
                    provider_hit = (s.get("provider") or "").upper() in (b.get("narration") or "").upper()
                    cands.append((0 if provider_hit else 1, lag, b))
            cands.sort(key=lambda c: (c[0], c[1], c[2]["_line"]))
            if len(cands) == 1 or (len(cands) > 1 and cands[0][:2] != cands[1][:2]):
                b = cands[0][2]
                used.add(b["_line"])
                rec.update(bank_line=b["_line"], bank_amount=b["credit"], difference=b["credit"] - net,
                           match_status="probable_match",
                           match_basis=["exact net amount", f"bank date within {window} days",
                                        "provider name in narration" if cands[0][0] == 0 else "no provider name"])
                if s.get("settlement_id") in confirmed_by_customer:
                    rec["match_status"] = "confirmed_match"
                    rec["match_basis"].append("customer confirmed (run_config.reconciliation."
                                              "customer_confirmed_matches)")
            elif len(cands) > 1:
                rec["match_status"] = "conflicting"
                rec["match_basis"] = [f"{len(cands)} equally good bank candidates"]
        records.append(rec)
    counts = {}
    for r in records:
        counts[r["match_status"]] = counts.get(r["match_status"], 0) + 1
    unmatched_value = sum((r["expected_net"] or ZERO for r in records if r["match_status"] == "unmatched"), ZERO)
    conflicting_value = sum((abs(r["difference"] or ZERO) for r in records if r["match_status"] == "conflicting"),
                            ZERO)
    total = sum((r["expected_net"] or ZERO for r in records), ZERO)
    result.update(status="completed", records=records, summary={
        "settlements": len(records), "by_status": counts, "matched_bank_lines": sorted(used),
        "unmatched_expected_value": unmatched_value, "conflicting_difference_value": conflicting_value,
        "total_expected_net": total})
    if counts.get("unmatched") or counts.get("conflicting"):
        issues_log.add("ai_settlement_reconciliation", "high", "settlements",
                       f"{counts.get('unmatched', 0)} settlement(s) not found in bank credits and "
                       f"{counts.get('conflicting', 0)} conflicting; expected net value not located in the bank "
                       f"data provided: {fmt_money(unmatched_value)}.", records=counts.get("unmatched", 0) + counts.get("conflicting", 0),
                       amount=unmatched_value + conflicting_value, blocks=[], escalate=False,
                       evidence=[r["settlement_id"] for r in records if r["match_status"] in
                                 ("unmatched", "conflicting")][:10])
    return result


def conflict_sales_vs_ledger(data, config):
    sales = data["datasets"].get("sales_lines")
    cur = config.get("current_period") or {}
    tbp = tb_periods(data).get(cur.get("label"))
    if not sales or not tbp:
        return None
    start, end = _dt.date.fromisoformat(cur["start"]), _dt.date.fromisoformat(cur["end"])
    register = sum((r.get("taxable_value") or ZERO for r in sales["rows"]
                    if r.get("invoice_date") and start <= r["invoice_date"] <= end), ZERO)
    ledger = sum((natural(r, "period") for r in tbp["rows"] if r.get("account_class") == "revenue_from_operations"),
                 ZERO)
    diff = register - ledger
    status = "resolved" if abs(diff) <= ROUNDING_AGG else "open"
    return {"conflict_id": "CON-SALES-LEDGER", "item": "gross revenue for the current period",
            "figures": [{"source": "sales_lines.csv (sales register)", "value": register},
                        {"source": "trial_balance.csv (revenue_from_operations)", "value": ledger}],
            "aligned_difference": diff, "classification": "rounding" if status == "resolved" else "unexplained",
            "chosen_figure_source": "trial_balance.csv (posted ledger; source_of_truth.policies.revenue_accrual)",
            "reason": "Posted ledger is the authority for accrual revenue; the register supplies dimensions.",
            "residual_unexplained": ZERO if status == "resolved" else diff, "status": status}


def conflict_bank_vs_book(data, config):
    bank = data["datasets"].get("bank_transactions")
    cur = config.get("current_period") or {}
    tbp = tb_periods(data).get(cur.get("label"))
    if not bank or not tbp:
        return None
    end = _dt.date.fromisoformat(cur["end"])
    latest = {}
    for r in bank["rows"]:
        d = r.get("transaction_date")
        if d is None or d > end or r.get("balance") is None:
            continue
        latest[r.get("bank_account_ref")] = r  # statement order: last line on/before period end wins
    stmt = sum((r["balance"] for r in latest.values()), ZERO)
    book_rows = [r for r in tbp["rows"] if r.get("account_class") == "cash_and_cash_equivalents"]
    book = sum((natural(r, "closing") for r in book_rows), ZERO)
    diff = stmt - book
    status = "resolved" if abs(diff) <= ROUNDING_AGG else "explained_pending_brs"
    return {"conflict_id": "CON-BANK-BOOK", "item": f"cash and bank balance at {cur['end']}",
            "figures": [{"source": "bank_transactions.csv (statement balances)", "value": stmt,
                         "accounts": sorted(str(k) for k in latest)},
                        {"source": "trial_balance.csv (cash_and_cash_equivalents, book)", "value": book,
                         "accounts": [r.get("account_name") for r in book_rows]}],
            "aligned_difference": diff,
            "classification": "rounding" if status == "resolved" else "timing_or_unrecorded_items_requires_brs",
            "chosen_figure_source": "bank statement (source_of_truth.policies.bank_balances)",
            "reason": "Bank records are the authority for bank balances; differences are explained by a bank "
                      "reconciliation statement, never by adjusting either figure.",
            "residual_unexplained": ZERO if status == "resolved" else diff, "status": status,
            "note": "Book cash may include cash-in-hand; statement covers only the accounts provided."}


def run_reconciliation(data, config, issues_log):
    out = {"rules": [], "conflicts": []}
    out["rules"].append(reconcile_settlements_to_bank(data, config, issues_log))
    for fn in (conflict_sales_vs_ledger, conflict_bank_vs_book):
        c = fn(data, config)
        if c:
            out["conflicts"].append(c)
            if c["status"] != "resolved":
                check = "ai_cash_movement" if c["conflict_id"] == "CON-BANK-BOOK" else "ai_ledger_to_statement"
                issues_log.add(check, "medium", "trial_balance",
                               f"{c['item']}: sources differ by {fmt_money(c['aligned_difference'])} "
                               f"({c['classification']}). Both figures are shown; {c['chosen_figure_source']} is "
                               f"used.", amount=c["aligned_difference"], blocks=[], escalate=False)
    return out
