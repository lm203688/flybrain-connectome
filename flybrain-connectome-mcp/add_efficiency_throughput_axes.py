# -*- coding: utf-8 -*-
"""Add efficiency / throughput axes to connection_costs.json and measurable
properties to connection_types.json.

Chief directive (P0 parallel item 1, user-approved): add an efficiency /
throughput measurement axis to `connection_costs`, and add measurable
properties to connection types.

Honesty rule (inherited from connection_costs.json's own `purpose` field):
"adds the numbers where a citation exists and `unknown` where one does not."

No new physiology is invented here. The two new axes are DERIVED from axes
that already carry evidence:
  * throughput  = 1 / midpoint(latency_ms)   [only where latency is known]
  * efficiency  = ordinal combination of delay_class and energy level
                  [only where latency is known; else unknown]

Connection types with no latency measurement keep grade=unknown (same policy
as the pre-existing 50/66 NONE latency entries). This script is reproducible
and idempotent: it reads the current files, computes, and writes back.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
COSTS_PATH = os.path.join(HERE, "functional_units", "connection_costs.json")
TYPES_PATH = os.path.join(HERE, "functional_units", "connection_types.json")

# Ordinal ranking for delay_class (faster -> higher).
_DELAY_ORD = {"immediate": 3, "short": 2, "long": 1}
# Ordinal ranking for energy level (cheaper -> higher). Qualitative only.
_ENERGY_ORD = {
    "cheap": 5,
    "cheap_per_target": 4,
    "typical": 3,
    "scales_with_span": 2,
    "expensive": 1,
    "emergent": 0,
}


def _mid(latency):
    """Midpoint of a {low, high} latency dict, or None."""
    if not isinstance(latency, dict):
        return None
    lo = latency.get("low")
    hi = latency.get("high")
    if lo is None or hi is None:
        return None
    return (lo + hi) / 2.0


def compute_throughput(latency):
    """Derived throughput (signals/ms) from latency midpoint, or None."""
    mid = _mid(latency)
    if mid is None or mid <= 0:
        return None
    return round(1.0 / mid, 4)


def compute_efficiency(delay_class, energy_level):
    """Derived qualitative efficiency ordinal 0-5, or None if latency unknown."""
    d = _DELAY_ORD.get(delay_class)
    e = _ENERGY_ORD.get(energy_level)
    if d is None or e is None:
        return None
    # efficiency ordinal: delay dominates (faster = more efficient per unit
    # time), energy level modulates. Range kept 1-5.
    return max(1, min(5, d + (e - 3)))


def main():
    with open(COSTS_PATH, "r", encoding="utf-8") as f:
        costs = json.load(f)
    with open(TYPES_PATH, "r", encoding="utf-8") as f:
        types = json.load(f)

    cost_axes = costs["cost_axis"]
    type_list = types["connection_types"]

    # Index types by name for cross-reference.
    type_by_name = {t["name"]: t for t in type_list}

    stats = {
        "types_total": len(cost_axes),
        "throughput_known": 0,
        "efficiency_known": 0,
        "throughput_unknown": 0,
        "efficiency_unknown": 0,
    }

    for axis in cost_axes:
        name = axis["name"]
        latency = axis.get("latency_ms")
        delay_class = axis.get("delay_class")
        energy_level = axis.get("energy", {}).get("level")

        # --- Derived throughput ---
        tp = compute_throughput(latency)
        if tp is not None:
            axis["throughput"] = {
                "signal_per_ms": tp,
                "basis": "derived_from_latency_midpoint",
                "grade": "derived",
            }
            stats["throughput_known"] += 1
        else:
            axis["throughput"] = {
                "grade": "unknown",
                "note": "no latency measurement; throughput not derivable",
            }
            stats["throughput_unknown"] += 1

        # --- Derived efficiency ---
        eff = compute_efficiency(delay_class, energy_level)
        if eff is not None:
            axis["efficiency"] = {
                "relative_rank": eff,
                "basis": "delay_class+energy_level ordinal",
                "grade": "derived",
                "scale": "1-5 (5=fastest+cheapest per unit time)",
            }
            stats["efficiency_known"] += 1
        else:
            axis["efficiency"] = {
                "grade": "unknown",
                "note": "no latency measurement; efficiency not derivable",
            }
            stats["efficiency_unknown"] += 1

        # --- Cross-reference into connection_types as measurable_properties ---
        t = type_by_name.get(name)
        if t is not None:
            t["measurable_properties"] = {
                "cost_axis": name,
                "latency_ms": {
                    "grade": latency.get("grade", "unknown") if isinstance(latency, dict) else "unknown",
                },
                "throughput": axis["throughput"]["grade"],
                "efficiency": axis["efficiency"]["grade"],
                "energy": {
                    "level": energy_level if energy_level else "unknown",
                    "grade": axis.get("energy", {}).get("grade", "unknown"),
                },
                "reliability": axis.get("reliability", {}).get("level", "unknown"),
            }

    # Bump schema version to reflect the additive change.
    costs["schema_version"] = "1.1"
    costs["generated_utc"] = "2026-11-03T05:20:00Z"
    costs["purpose_note"] = (
        "v1.1 adds derived efficiency/throughput axes per Chief P0 parallel "
        "item 1; derived only where latency is known, unknown elsewhere."
    )
    types["schema_version"] = "1.1"
    types["stats"]["connection_types_with_measurable_properties"] = stats["types_total"]

    # Write back with CRLF (original file uses CRLF) and 2-space indent.
    with open(COSTS_PATH, "w", encoding="utf-8", newline="") as f:
        json.dump(costs, f, ensure_ascii=False, indent=2)
        f.write("\r\n")
    with open(TYPES_PATH, "w", encoding="utf-8", newline="") as f:
        json.dump(types, f, ensure_ascii=False, indent=2)
        f.write("\r\n")

    print("OK stats:", json.dumps(stats, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
