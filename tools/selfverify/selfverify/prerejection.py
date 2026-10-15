"""PR-2b-style pre-execution rejection.

A proposed substitute metric can be refused *before* the experiment runs when
it is analytically redundant with the original — i.e. when their measured
coupling exceeds a preregistered threshold. This is a first-class outcome, not
a failure: "we did not run it, because running it would be uninformative".
"""
from __future__ import annotations

from .gate import pearson
from .protocol import Protocol


def coupling(arm_a, arm_b) -> float:
    return abs(pearson(arm_a, arm_b))


def evaluate_rejection(protocol: Protocol, results: dict) -> list:
    """Evaluate every reject rule against the observed arms."""
    arms = {a["name"]: a["values"] for a in results.get("arms", [])}
    out = []
    for rule in protocol.reject_rules or []:
        if rule.get("type") != "coupling":
            continue
        a, b = rule["arm_a"], rule["arm_b"]
        if a not in arms or b not in arms:
            out.append({"rule": "coupling", "arms": [a, b],
                        "rejected": False, "error": "arm_not_found"})
            continue
        c = coupling(arms[a], arms[b])
        out.append({
            "rule": "coupling",
            "arms": [a, b],
            "corr": round(c, 4),
            "corr_min": rule.get("corr_min", 0.5),
            "rejected": c >= rule.get("corr_min", 0.5),
        })
    return out
