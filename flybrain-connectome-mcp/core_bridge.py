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
active; without it, the Tier-2-dependent tools degrade to a stub (target: 31
functional tools on a bare public install — 40 minus the 9 Tier-2-dependent
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
CORE_DEPENDENT_TOOLS = [
    "list_combination_rules", "validate_combination", "expand_organism",
    "get_multiplier_metrics",
    "list_neuropils", "get_neuropil_detail", "get_module",
    "check_module_compatibility", "list_modules",
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
