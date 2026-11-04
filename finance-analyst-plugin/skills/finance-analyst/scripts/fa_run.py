"""Run the deterministic pipeline on a folder of canonical CSVs.

    python3 fa_run.py --input-dir DATA --config run_config.json --out RUN_DIR
                      [--narrative narrative.json] [--depth simple|comprehensive]

Stages: load -> data-quality & integrity checks -> reconciliation -> metrics ->
signals -> render draft report -> independent verification -> final report.
Outputs in RUN_DIR: run_config.json, source_manifest.json, issues.json,
reconciliation.json, calc_register.json, signals.json, report_draft.md,
render_manifest.json, verification.json, report.md, run_manifest.json.

Exit codes: 0 verified (passed / passed_with_warnings), 2 bad configuration,
3 verification failed (report.md carries a failure banner; do not present its
figures as verified).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fa_checks import run_checks  # noqa: E402
from fa_common import TOOLKIT_VERSION, now_ist, read_json, sha256_file, spec_path, write_json  # noqa: E402
from fa_data import load_inputs, source_manifest  # noqa: E402
from fa_metrics import Engine, signals  # noqa: E402
from fa_reconcile import run_reconciliation  # noqa: E402
from fa_report import render_report  # noqa: E402
import fa_verify  # noqa: E402

DEFAULT_MATERIALITY = {"absolute_floor_inr": "25000", "relative_threshold": "0.10", "revenue_share_floor": "0.005"}


def spec_version():
    try:
        with open(spec_path(), encoding="utf-8") as fh:
            for line in fh:
                if line.strip().startswith("schema_version:"):
                    return line.split(":", 1)[1].strip().strip('"')
    except OSError:
        pass
    return "unknown"


def validate_config(cfg):
    errs = []
    for key in ("company_name", "current_period"):
        if key not in cfg:
            errs.append(f"missing '{key}'")
    for key in ("current_period", "comparison_period"):
        p = cfg.get(key)
        if p is None:
            continue
        for f in ("label", "start", "end"):
            if f not in p:
                errs.append(f"{key}.{f} missing")
        try:
            if _dt.date.fromisoformat(p["start"]) > _dt.date.fromisoformat(p["end"]):
                errs.append(f"{key}: start after end")
        except (KeyError, ValueError):
            errs.append(f"{key}: dates must be YYYY-MM-DD")
    if cfg.get("currency", "INR") != "INR":
        errs.append("toolkit v0.1 formats INR only; set currency to INR or analyse with code directly")
    return errs


def run(input_dir, config_path, out_dir, narrative_path=None, depth="simple"):
    cfg = read_json(config_path)
    cfg.setdefault("currency", "INR")
    cfg.setdefault("reporting_basis", "accrual")
    cfg["materiality"] = dict(DEFAULT_MATERIALITY, **cfg.get("materiality", {}))
    errs = validate_config(cfg)
    if errs:
        print("configuration errors: " + "; ".join(errs))
        return 2
    os.makedirs(out_dir, exist_ok=True)
    started = now_ist()
    run_id = "FA-" + _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    write_json(os.path.join(out_dir, "run_config.json"), cfg)
    data = load_inputs(input_dir)
    if not data["datasets"]:
        print(f"no canonical input files found in {input_dir}; see references/input-formats.md")
        return 2
    sources = source_manifest(data)
    log = run_checks(data, cfg)
    recon = run_reconciliation(data, cfg, log)
    issues = log.items
    engine = Engine(data, cfg, issues, recon)
    reg = engine.run()
    sig = signals(reg, cfg)
    narrative = {}
    if narrative_path:
        narrative = read_json(narrative_path)
        shutil.copyfile(narrative_path, os.path.join(out_dir, "narrative.json"))
    elif os.path.exists(os.path.join(out_dir, "narrative.json")):
        os.remove(os.path.join(out_dir, "narrative.json"))
    write_json(os.path.join(out_dir, "source_manifest.json"), sources)
    write_json(os.path.join(out_dir, "issues.json"), issues)
    write_json(os.path.join(out_dir, "reconciliation.json"), recon)
    write_json(os.path.join(out_dir, "calc_register.json"), reg.records)
    write_json(os.path.join(out_dir, "signals.json"), sig)
    sv = spec_version()
    draft, manifest = render_report(reg.records, issues, recon, sources, narrative, cfg, depth, run_id, sv)
    with open(os.path.join(out_dir, "report_draft.md"), "w", encoding="utf-8") as fh:
        fh.write(draft)
    write_json(os.path.join(out_dir, "render_manifest.json"), manifest)
    ver = fa_verify.verify(out_dir, input_dir)
    write_json(os.path.join(out_dir, "verification.json"), ver)
    if ver["outcome"] == "failed":
        stamp = ("**VERIFICATION FAILED — do not rely on these figures.** "
                 + "; ".join(f"{c['id']}" for c in ver["checks"] if c["status"] == "failed"))
    else:
        stamp = (f"Verified by independent recomputation on {now_ist()} (IST): {ver['passed_checks']}/"
                 f"{ver['total_checks']} checks passed ({ver['outcome'].replace('_', ' ')}).")
    final = draft.replace("VERIFICATION_STATUS_PLACEHOLDER", stamp, 1)
    final += "\n## Verification\n\n| Check | Status | Details |\n|---|---|---|\n"
    for c in ver["checks"]:
        det = c["details"] if isinstance(c["details"], str) else "; ".join(map(str, c["details"]))[:300]
        final += f"| {c['id']} | {c['status']} | {det} |\n"
    final += f"\nDraft SHA-256: {ver['draft_sha256']}\n"
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as fh:
        fh.write(final)
    write_json(os.path.join(out_dir, "run_manifest.json"), {
        "run_id": run_id, "spec_version": sv, "toolkit_version": TOOLKIT_VERSION, "started_at": started,
        "finished_at": now_ist(), "input_dir": os.path.abspath(input_dir), "depth": depth,
        "datasets": [s["dataset_id"] for s in sources], "issue_count": len(issues),
        "calculation_count": len(reg.records), "verification_outcome": ver["outcome"],
        "outputs": {n: sha256_file(os.path.join(out_dir, n)) for n in ("report.md", "calc_register.json",
                                                                        "issues.json")},
        "outcome": "completed" if ver["outcome"] != "failed" else "partial"})
    counts = {}
    for r in reg.records:
        counts[r["readiness"]] = counts.get(r["readiness"], 0) + 1
    sev = {}
    for i in issues:
        sev[i["severity"]] = sev.get(i["severity"], 0) + 1
    print(f"run {run_id}: {len(sources)} dataset(s), {len(reg.records)} calculation(s) {counts}, "
          f"issues {sev or 'none'}")
    print(f"verification: {ver['outcome']} ({ver['passed_checks']}/{ver['total_checks']})")
    for c in ver["checks"]:
        if c["status"] != "passed":
            print(f"  {c['status'].upper()} {c['id']}: {c['details']}")
    print(f"report: {os.path.join(os.path.abspath(out_dir), 'report.md')}")
    return 3 if ver["outcome"] == "failed" else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input-dir", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--narrative")
    ap.add_argument("--depth", choices=["simple", "comprehensive"], default="simple")
    a = ap.parse_args(argv)
    return run(a.input_dir, a.config, a.out, a.narrative, a.depth)


if __name__ == "__main__":
    sys.exit(main())
