"""
Physical tiering bridge (层1/层2 IP 隔离机制).

The public MIT repo (lm203688/flybrain-connectome) ships the *schema, CLI shells,
docs, gates and stubs*. The Tier-2 IP — module profiles, combination-rule tables,
discovery pipelines, data artifacts and HMAC signing — lives ONLY in the private
repo `lm203688/flybrain-connectome-core` (installed as the `flybrain_core`
package) or a local checkout pointed to by $FLYBRAIN_CORE.

This module is the single seam: public code calls `core_available()` and, when
False, returns a graceful "Tier-2 required" response instead of crashing or
leaking the IP. When the private package IS present, the full 40-tool surface is
active; without it, the Tier-2-dependent tools degrade to a stub (36
functional tools on a bare public install — 40 minus the 4 Tier-2-dependent
tools).

Nothing in this file embeds Tier-2 content.
"""
from __future__ import annotations
import importlib
import os
import sys
from pathlib import Path
from typing import Any

# Tools whose behaviour depends on Tier-2 IP. On a bare public install these
# degrade to a stub; with flybrain_core installed they are fully functional.
# Scoped precisely: only the four combinator tools read the proprietary rule
# tables (12 combination + 7 nesting rules, 4 multiplier semantics, 27 data-driven
# candidates). Other developer/module tools were previously listed here but are NOT
# Tier-2: list_neuropils / get_neuropil_detail read male_cns/neuropil_stats.json
# (aggregate synapse counts, Tier-1 data), and list_modules / get_module /
# check_module_compatibility read MODULE_PROFILES in module_registry.py (module
# definitions and presets, Tier-1 schema/config).
CORE_DEPENDENT_TOOLS = [
    "list_combination_rules", "validate_combination", "expand_organism",
    "get_multiplier_metrics",
]

# Tier-2 artifacts that must NOT ship in the public tree. Single source of
# truth for Gate 8's absence assertion.
#
# stubbed=True  -> a Tier-1 interface stub occupies this path in the public
#                  repo (the real implementation lives privately)
# stubbed=False -> the path must be fully absent from the public tree
TIER2_ARTIFACTS = [
    ("flybrain-connectome-mcp/module_combinator.py", True),
    ("data/worm/worm_modules.json", False),
    ("male_cns/discovered_modules.json", False),
    ("male_cns/discovered_modules_neuropil.json", False),
    ("male_cns/superclass_matrix.json", False),
    ("male_cns/superclass_neuropil_matrix.json", False),
    ("male_cns/candidate_combination_rules.json", False),
    ("scripts/module_discovery/README.md", False),
    ("scripts/module_discovery/step1_build_matrix.py", False),
    ("scripts/module_discovery/step1b_neuropil_cluster.py", False),
    ("scripts/module_discovery/step1c_worm_modules.py", False),
    ("scripts/module_discovery/step2_cluster.py", False),
    ("scripts/module_discovery/step3_build_library.py", False),
    ("scripts/module_discovery/step4_superclass_neuropil.py", False),
    ("scripts/data_driven_rules.py", False),
    ("data/worm/neuron_nt_mapping.json", False),
    ("data/worm/worm_modules_nt_annotated.json", False),
]

# A stubbed path is only a stub if it carries no Tier-2 payload. These
# identifiers mark proprietary content; their presence means the real
# implementation leaked back into the public tree.
TIER2_LEAK_MARKERS = [
    "COMBINATION_RULES =", "NESTING_RULES =", "MULTIPLIER_SEMANTICS =",
    "def _load_fly_units", "def _load_neuropil_units", "def _load_worm_units",
    "def _load_candidate_rules",
]

ROOT = Path(__file__).resolve().parents[1]


def _discover_local_core() -> bool:
    local = os.environ.get("FLYBRAIN_CORE")
    if local and Path(local).exists():
        sys.path.insert(0, str(Path(local).resolve()))
        return True
    return False


def core_available() -> bool:
    """True iff the Tier-2 package `flybrain_core` can be imported."""
    if _discover_local_core():
        try:
            importlib.import_module("flybrain_core")
            return True
        except Exception:
            return False
    try:
        importlib.import_module("flybrain_core")
        return True
    except Exception:
        return False


def require_core(tool_name: str) -> dict | None:
    """
    Guard for a Tier-2 tool. Returns None when core is available (caller should
    proceed). Returns a 'Tier-2 required' envelope when core is absent so the
    public server degrades gracefully instead of crashing.
    """
    if core_available():
        return None
    return {
        "status": "tier2_required",
        "tool": tool_name,
        "message": ("This capability requires the proprietary Tier-2 package "
                    "`flybrain_core` (private). Install it or set FLYBRAIN_CORE "
                    "to a local checkout to activate."),
    }


def functional_tool_count() -> int:
    """Total advertised tools minus the Tier-2-dependent ones when core absent."""
    TOTAL = 40
    return TOTAL if core_available() else TOTAL - len(CORE_DEPENDENT_TOOLS)


def tiering_status() -> dict:
    return {
        "core_available": core_available(),
        "total_tools": 40,
        "functional_tools": functional_tool_count(),
        "degraded_tools": [] if core_available() else CORE_DEPENDENT_TOOLS,
        "canonical_tier2_repo": "lm203688/flybrain-connectome-core (private)",
    }
