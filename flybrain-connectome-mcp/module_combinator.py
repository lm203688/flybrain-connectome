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


def get_multiplier_metrics(spec=None, **kwargs):
    """Multiplier semantics with honest measured / unmeasured flags."""
    return _passthrough("get_multiplier_metrics", spec, **kwargs)


def audit_rules_against_data():
    """Reconcile curated rules against the data-driven candidate rules."""
    return _passthrough("audit_rules_against_data")


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


__all__ = [
    "SCHEMA_VERSION", "ROOT",
    "list_rules", "validate_combination", "validate_nesting", "expand_organism",
    "get_multiplier_metrics", "audit_rules_against_data", "suggest_combinations",
    "cross_species_consistency", "find_rule", "find_all_rules", "tier2_status",
]
