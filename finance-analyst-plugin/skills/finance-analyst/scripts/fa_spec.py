"""Read and validate finance-analyst.yaml.

    python3 fa_spec.py list                     # top-level sections with line ranges (no dependencies)
    python3 fa_spec.py section workflow         # print one top-level section verbatim (no dependencies)
    python3 fa_spec.py get metrics.registry.dso # print one entry as JSON (needs PyYAML)
    python3 fa_spec.py validate                 # parse, duplicate keys, references, toolkit sync (needs PyYAML)

Exit codes: 0 ok, 1 validation problems, 4 skipped because PyYAML is not installed.
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fa_common import ACCOUNT_CLASSES, PROHIBITED_PHRASES, spec_path  # noqa: E402


def read_text(path=None):
    with open(path or spec_path(), encoding="utf-8") as fh:
        return fh.read()


def top_sections(text):
    lines = text.split("\n")
    starts = [(i, m.group(1)) for i, ln in enumerate(lines) for m in [re.match(r"^([a-z_][a-z0-9_]*):", ln)] if m]
    out = []
    for n, (i, key) in enumerate(starts):
        end = starts[n + 1][0] if n + 1 < len(starts) else len(lines)
        while end > i + 1 and (lines[end - 1].startswith("#") or not lines[end - 1].strip()):
            end -= 1
        out.append((key, i + 1, end))
    return out, lines


def cmd_list():
    secs, _ = top_sections(read_text())
    for key, a, b in secs:
        print(f"{key:32s} lines {a}-{b} ({b - a + 1} lines)")
    return 0


def cmd_section(key):
    secs, lines = top_sections(read_text())
    for k, a, b in secs:
        if k == key:
            print("\n".join(lines[a - 1:b]))
            return 0
    print(f"no top-level section '{key}'. Use: fa_spec.py list")
    return 1


def load_yaml():
    try:
        import yaml  # type: ignore
    except ImportError:
        return None, None

    class DupLoader(yaml.SafeLoader):
        pass

    def construct_mapping(loader, node, deep=False):
        seen = {}
        for key_node, _ in node.value:
            key = loader.construct_object(key_node, deep=deep)
            if key in seen:
                raise ValueError(f"duplicate key {key!r} at line {key_node.start_mark.line + 1}")
            seen[key] = True
        return yaml.SafeLoader.construct_mapping(loader, node, deep)

    DupLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_mapping)
    return yaml.load(read_text(), Loader=DupLoader), yaml


def resolve(doc, parts):
    cur = doc
    for p in parts:
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        elif isinstance(cur, list):
            hit = [e for e in cur if isinstance(e, dict) and p in (e.get("id"), e.get("connector_id"), e.get("code"))]
            if not hit:
                return None, False
            cur = hit[0]
        else:
            return None, False
    return cur, True


def cmd_get(path):
    doc, _ = load_yaml()
    if doc is None:
        print("PyYAML is not installed; use 'fa_spec.py section <top-level-key>' instead.")
        return 4
    node, ok = resolve(doc, path.split("."))
    if not ok:
        print(f"path not found: {path}")
        return 1
    print(json.dumps(node, indent=2, ensure_ascii=False, default=str))
    return 0


def cmd_validate():
    try:
        doc, _ = load_yaml()
    except ValueError as exc:
        print(json.dumps({"status": "failed", "problems": [str(exc)]}, indent=2))
        return 1
    if doc is None:
        print(json.dumps({"status": "skipped", "reason": "PyYAML not installed; structural reading via "
                                                         "'section' still works"}, indent=2))
        return 4
    text = read_text()
    problems = []
    if str(doc["spec"]["schema_version"]).split(".")[0] != "1":
        problems.append("unsupported MAJOR schema version")

    def ids(lst, key="id"):
        vals = [e[key] for e in lst]
        dups = {v for v in vals if vals.count(v) > 1}
        if dups:
            problems.append(f"duplicate ids: {sorted(dups)}")
        return set(vals)

    metric_ids = ids(doc["metrics"]["registry"])
    module_ids = ids(doc["analysis_modules"]["registry"])
    chart_ids = ids(doc["visualizations"]["chart_types"])
    stage_ids = ids(doc["workflow"]["stages"])
    err_codes = ids(doc["error_catalog"]["errors"], "code")
    check_ids = (ids(doc["data_quality"]["checks"]) | ids(doc["accounting_integrity"]["checks"])
                 | ids(doc["reconciliation"]["rules"]) | ids(doc["verification"]["checks"]))
    for m in doc["metrics"]["registry"]:
        for d in m.get("dependencies", []):
            if d not in metric_ids:
                problems.append(f"metric {m['id']}: dependency {d} undefined")
        for v in m.get("visuals", []):
            if v not in chart_ids:
                problems.append(f"metric {m['id']}: visual {v} undefined")
    for mod in doc["analysis_modules"]["registry"]:
        for x in mod.get("input_metrics", []):
            if x not in metric_ids:
                problems.append(f"module {mod['id']}: metric {x} undefined")
        for x in mod.get("related_modules", []):
            if x not in module_ids:
                problems.append(f"module {mod['id']}: related module {x} undefined")
    for st in doc["workflow"]["stages"]:
        for k, v in st["transitions"].items():
            if v not in stage_ids | {"complete", "terminate"}:
                problems.append(f"stage {st['id']}: transition {k}->{v} undefined")
    for code in set(re.findall(r"FA-[EWI]-[A-Z]+-\d{3}", text)):
        if code not in err_codes:
            problems.append(f"error code {code} undefined")
    for cid in set(re.findall(r"\b(?:dq|ai|rec|ver)_[a-z0-9_]+\b", text)):
        if cid not in check_ids:
            problems.append(f"check id {cid} undefined")
    top = set(doc)
    for ref in set(re.findall(r"(?<![\w${.])([a-z_]+(?:\.[a-z_0-9]+){1,6})", text)):
        parts = ref.split(".")
        if parts[0] in top and not resolve(doc, parts)[1]:
            problems.append(f"dotted reference {ref} does not resolve")
    # toolkit <-> spec synchronisation
    sync = []
    from fa_metrics import IMPLEMENTED_METRICS
    for m in IMPLEMENTED_METRICS:
        if m not in metric_ids:
            sync.append(f"toolkit metric {m} not in metrics.registry")
    used = set()
    for f in glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "fa_*.py")):
        with open(f, encoding="utf-8") as fh:
            used |= set(re.findall(r'"((?:dq|ai|rec|ver)_[a-z0-9_]+)"', fh.read()))
    for cid in sorted(used):
        if cid not in check_ids:
            sync.append(f"toolkit check id {cid} not defined in spec")
    if _class_view(doc) != _class_view_tk():
        sync.append("toolkit ACCOUNT_CLASSES differ from canonical_data_model.account_classes")
    # reflex engine: rule ids, derived/scenario ids and default configuration must match the spec
    import fa_reflex
    rx = doc.get("reflex_engine")
    if rx is None:
        sync.append("spec has no reflex_engine section but the toolkit implements it")
    else:
        spec_rules = [r["id"] for r in rx["rules"]]
        if spec_rules != fa_reflex.RULE_IDS:
            sync.append("reflex rule ids differ between spec and fa_reflex.RULE_IDS")
        spec_derived = [d["id"] for d in rx["derived_calculations"]]
        spec_scen = [d["id"] for d in rx["scenarios"]]
        if spec_derived != fa_reflex.DERIVED_IDS:
            sync.append("reflex derived calculation ids differ from the spec")
        if spec_scen != fa_reflex.SCENARIO_IDS:
            sync.append("reflex scenario ids differ from the spec")
        gates = {a["id"]: a["gate"] for a in rx["action_classes"]}
        for cls, gate in fa_reflex.ACTION_GATES.items():
            if gates.get(cls) != gate:
                sync.append(f"reflex action class {cls}: toolkit gate {gate} vs spec {gates.get(cls)}")
        dflt = fa_reflex.default_config()
        spec_d = rx["configuration"]["defaults"]
        for key in ("enabled", "min_severity", "min_confidence", "execution_limits", "deduplication", "approvals",
                    "prioritisation", "scenario_parameters"):
            if dflt.get(key) != spec_d.get(key):
                sync.append(f"templates/reflex_rules.json '{key}' differs from reflex_engine.configuration.defaults")
        for r in rx["rules"]:
            t = dflt["rules"].get(r["id"], {})
            if t.get("params") != r["params"] or t.get("severity") != r["severity"]:
                sync.append(f"templates/reflex_rules.json rule {r['id']} differs from the spec")
    spec_prohibited = doc["accounting_integrity"]["opinion_boundaries"]["required_language"]["prohibited"]
    if list(spec_prohibited) != PROHIBITED_PHRASES:
        sync.append("toolkit PROHIBITED_PHRASES differ from the spec")
    problems += sync
    result = {"status": "passed" if not problems else "failed", "schema_version": doc["spec"]["schema_version"],
              "counts": {"metrics": len(metric_ids), "modules": len(module_ids), "stages": len(stage_ids),
                         "checks": len(check_ids), "errors": len(err_codes)},
              "toolkit_metrics_implemented": len(IMPLEMENTED_METRICS), "toolkit_check_ids_used": sorted(used),
              "problems": problems}
    print(json.dumps(result, indent=2))
    return 0 if not problems else 1


def _lists_only(node):
    if isinstance(node, dict):
        return {k: _lists_only(v) for k, v in node.items() if isinstance(v, (dict, list))}
    return node


def _class_view(doc):
    ac = doc["canonical_data_model"]["account_classes"]
    return _lists_only({k: ac[k] for k in ("assets", "liabilities", "equity", "income", "expenses", "special")})


def _class_view_tk():
    return _lists_only({k: ACCOUNT_CLASSES[k] for k in ("assets", "liabilities", "equity", "income", "expenses",
                                                        "special")})


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd = argv[0]
    if cmd == "list":
        return cmd_list()
    if cmd == "section" and len(argv) == 2:
        return cmd_section(argv[1])
    if cmd == "get" and len(argv) == 2:
        return cmd_get(argv[1])
    if cmd == "validate":
        return cmd_validate()
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
