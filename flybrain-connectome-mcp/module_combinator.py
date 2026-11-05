"""
Tier-2 stub - module combination-rule middleware (interface only).

The real implementation is **proprietary** and lives only in the private repo
lm203688/flybrain-connectome-core (installable as the flybrain_core package).
It contains:

  * 12 combination rules with per-rule evidence citations
  * 7 nesting rules (incl. cross-species role binding)
  * 4 multiplier semantics (combinatorial / structural / performance / cross-species)
  * 27 data-driven candidate rules derived from the real 27x27 connectome matrix
  * The discovered module libraries the rules are grounded in
    (8 superclass units, 10 neuropil units, 12 worm units)

None of that is shipped in this MIT repository. This file is a **thin seam**:
every public call below tries the real package first and, when it is absent,
returns a structured tier2_required envelope instead of raising. The four MCP
tools that depend on the middleware therefore degrade gracefully rather than
crash, and the advertised tool surface stays intact.

Nothing in this file embeds Tier-2 content: no rule tables, no clustering
artifacts, no module profiles, no evidence citations.

Activation (either works):
  pip install flybrain-connectome-core        # private index, token gated
  FLYBRAIN_CORE=/path/to/checkout python ...   # local private checkout

Interface contract (stable across versions):
  SCHEMA_VERSION = 1.1
  list_rules() / validate_combination(combos) / validate_nesting(chain, max_depth)
  expand_organism(spec) / get_multiplier_metrics(spec=None)
  audit_rules_against_data() / suggest_combinations(max_suggestions)
  cross_species_consistency() / find_rule(from_cat, to_cat) / find_all_rules(...)
"""
from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

# Combinator rules schema version. This is the *interface* version and stays in
# the open tier; the rule *payloads* are Tier-2 and versioned privately.
SCHEMA_VERSION = "1.1"

ROOT = Path(__file__).resolve().parents[1]

_CORE_MODULE = "flybrain_core.module_combinator"

# MCP tool each public function maps to, so the envelope can name the exact
# capability that is missing.
_TOOL = {
    "list_rules": "list_combination_rules",
    "validate_combination": "validate_combination",
    "validate_nesting": "validate_combination",
    "expand_organism": "expand_organism",
    "get_multiplier_metrics": "get_multiplier_metrics",
    "audit_rules_against_data": "list_combination_rules",
    "suggest_combinations": "list_combination_rules",
    "cross_species_consistency": "list_combination_rules",
    "find_rule": "validate_combination",
    "find_all_rules": "validate_combination",
}


def _core():
    """Import the real Tier-2 implementation, or None when unavailable."""
    try:
        return importlib.import_module(_CORE_MODULE)
    except Exception:
        return None


def _gated(fn_name):
    """Structured degradation envelope. Never raises, never leaks content."""
    from core_bridge import require_core
    return require_core(_TOOL.get(fn_name, fn_name))


def _passthrough(fn_name, *args, **kwargs):
    """Use the real implementation when present, else degrade gracefully."""
    # Ensure the private checkout (env or sibling) is on sys.path before the
    # import below — core_bridge.core_available() triggers discovery, which is
    # what actually adds the checkout to sys.path. Without this, _core() fails
    # to import even when the core is installed/configured.
    try:
        from core_bridge import core_available
        core_available()
    except Exception:  # noqa: SILENT — core availability probe; fallback if unavailable
        pass
    m = _core()
    if m is not None and hasattr(m, fn_name):
        return getattr(m, fn_name)(*args, **kwargs)
    return _gated(fn_name)


def list_rules():
    """All combination rules, nesting rules and multiplier semantics."""
    return _passthrough("list_rules")


def validate_combination(combos, **kwargs):
    """Validate a proposed cross-module connection list."""
    return _passthrough("validate_combination", combos, **kwargs)


def validate_nesting(chain, max_depth=3, **kwargs):
    """Validate a nested module chain."""
    return _passthrough("validate_nesting", chain, max_depth=max_depth, **kwargs)


def expand_organism(spec, **kwargs):
    """Expand a compact organism spec into full per-module topology."""
    return _passthrough("expand_organism", spec, **kwargs)


def suggest_combinations(max_suggestions=10, **kwargs):
    """Suggest module combinations from observed downstream targets."""
    return _passthrough("suggest_combinations", max_suggestions=max_suggestions, **kwargs)


def cross_species_consistency():
    """Cross-species (fly vs worm) rule conservation report."""
    return _passthrough("cross_species_consistency")


def find_rule(from_cat, to_cat, **kwargs):
    """Best-matching rule for a from -> to category pair."""
    return _passthrough("find_rule", from_cat, to_cat, **kwargs)


def find_all_rules(from_cat, to_cat, **kwargs):
    """Every matching rule for a from -> to category pair."""
    return _passthrough("find_all_rules", from_cat, to_cat, **kwargs)


def tier2_status():
    """Report whether the Tier-2 middleware is active in this install."""
    from core_bridge import tiering_status
    return tiering_status()


# --- F2 connectome-build pinning (user m00070 / Chief m00061) -----------------
# "Which connectome build determines what the model can do" (flybench, F2).
# The functional-unit library now declares its embodied connectome build in
# functional_units.json -> connectome_build. Every validation/simulation result
# is traceable to a pinned build; if the declared build disagrees with the
# DATA_MANIFEST the engine WARNs instead of silently assuming consistency.

_CONNECTOME_BUILD_FIELDS = (
    "dataset", "manifest_generated_utc", "anchors_sha256",
    "measured_edges_neuron_subgraph", "pinned",
)


def check_connectome_build() -> dict:
    """Verify the functional-unit library's pinned connectome build.

    Returns a structured report:
      {ok, consistent, build, manifest, warning, checks}
    Never raises; a missing file or field degrades to ``ok: False, warning``
    rather than crashing the combinator seam.
    """
    report = {
        "ok": False,
        "consistent": False,
        "build": None,
        "manifest": None,
        "warning": None,
        "checks": {},
    }
    import json
    fu_path = ROOT / "flybrain-connectome-mcp" / "functional_units" / "functional_units.json"
    manifest_path = ROOT / "DATA_MANIFEST.json"
    if not fu_path.exists():
        report["warning"] = f"functional_units.json not found: {fu_path}"
        return report
    if not manifest_path.exists():
        report["warning"] = f"DATA_MANIFEST.json not found: {manifest_path}"
        return report
    try:
        fu = json.loads(fu_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - honest degrade
        report["warning"] = f"unreadable build/manifest: {exc}"
        return report

    build = fu.get("connectome_build")
    if not isinstance(build, dict):
        report["warning"] = (
            "functional_units.json has no connectome_build declaration; "
            "the library is not pinned to a connectome build (F2)."
        )
        return report

    # Extract the declared build identity and the manifest identity.
    declared_dataset = build.get("dataset", "")
    manifest_dataset = manifest.get("dataset", "")
    declared_utc = build.get("manifest_generated_utc")
    manifest_utc = manifest.get("generated_utc")
    declared_sha = build.get("anchors_sha256")
    emb = fu.get("embodiment_source", {})
    manifest_sha = emb.get("sha256") if isinstance(emb, dict) else None

    checks = {
        "dataset_match": bool(declared_dataset) and declared_dataset == manifest_dataset,
        "generated_utc_match": bool(declared_utc) and declared_utc == manifest_utc,
        "anchors_sha256_present": bool(declared_sha),
        "anchors_sha256_match": bool(declared_sha) and declared_sha == manifest_sha,
        "pinned": bool(build.get("pinned", False)),
        "measured_edges_declared": bool(build.get("measured_edges_neuron_subgraph")),
    }
    consistent = (
        checks["dataset_match"]
        and checks["generated_utc_match"]
        and checks["anchors_sha256_match"]
        and checks["pinned"]
    )

    warnings = []
    if not checks["dataset_match"]:
        warnings.append(
            f"dataset mismatch: library='{declared_dataset}' manifest='{manifest_dataset}'"
        )
    if not checks["generated_utc_match"]:
        warnings.append(
            f"manifest generated_utc mismatch: library='{declared_utc}' manifest='{manifest_utc}'"
        )
    if not checks["anchors_sha256_match"]:
        warnings.append(
            f"anchors sha256 mismatch: library='{declared_sha}' manifest='{manifest_sha}'"
        )
    if not checks["pinned"]:
        warnings.append("connectome_build.pinned is not True; the build is not pinned (F2).")

    report.update({
        "ok": True,
        "consistent": consistent,
        "build": {k: build.get(k) for k in _CONNECTOME_BUILD_FIELDS},
        "manifest": {
            "dataset": manifest_dataset,
            "generated_utc": manifest_utc,
            "file_count": manifest.get("file_count"),
        },
        "warning": "; ".join(warnings) if warnings else None,
        "checks": checks,
    })
    return report


def _attach_build_check(result, fn_name):
    """Attach the F2 build check to a result, merging into a dict result."""
    check = check_connectome_build()
    if isinstance(result, dict):
        result = dict(result)
        result["connectome_build_check"] = check
        if not check.get("consistent") and check.get("warning"):
            # Surface as a non-blocking warning alongside the payload.
            result.setdefault("warnings", [])
            if isinstance(result["warnings"], list):
                result["warnings"].append(
                    {"code": "connectome_build_mismatch", "detail": check["warning"]}
                )
    return result


def get_multiplier_metrics(spec=None, **kwargs):
    """Multiplier semantics with honest measured / unmeasured flags."""
    return _attach_build_check(_passthrough("get_multiplier_metrics", spec, **kwargs),
                               "get_multiplier_metrics")


def audit_rules_against_data():
    """Reconcile curated rules against the data-driven candidate rules."""
    return _attach_build_check(_passthrough("audit_rules_against_data"),
                               "audit_rules_against_data")


__all__ = [
    "SCHEMA_VERSION", "ROOT",
    "list_rules", "validate_combination", "validate_nesting", "expand_organism",
    "get_multiplier_metrics", "audit_rules_against_data", "suggest_combinations",
    "cross_species_consistency", "find_rule", "find_all_rules", "tier2_status",
    "check_connectome_build",
]
