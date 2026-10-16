"""The gate: independent recomputation + verdict.

Design rule (the "independent recomputation principle"): the gate recomputes
its quantity from *raw per-sample records*, never from a precomputed summary
field. An analyst therefore cannot pass the gate by editing a summary number.
"""
from __future__ import annotations

from .protocol import Protocol, Verdict


def auc(scores, labels) -> float:
    """Rank-based AUC (Mann-Whitney U). Pure Python, no dependencies."""
    pos = [s for s, l in zip(scores, labels) if int(l) == 1]
    neg = [s for s, l in zip(scores, labels) if int(l) == 0]
    if not pos or not neg:
        return 0.5
    paired = sorted(zip(scores, [int(l) for l in labels]))
    n = len(paired)
    rank_of = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and paired[j + 1][0] == paired[i][0]:
            j += 1
        avg = (i + j) / 2.0 + 1.0  # average rank (1-based) for ties
        for k in range(i, j + 1):
            rank_of[k] = avg
        i = j + 1
    r_pos = sum(rank_of[k] for k, (_, l) in enumerate(paired) if l == 1)
    n_pos, n_neg = len(pos), len(neg)
    u = r_pos - n_pos * (n_pos + 1) / 2.0
    return u / (n_pos * n_neg)


def pearson(a, b) -> float:
    n = len(a)
    if n < 2:
        return 0.0
    ma, mb = sum(a) / n, sum(b) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = sum((x - ma) ** 2 for x in a) ** 0.5
    db = sum((y - mb) ** 2 for y in b) ** 0.5
    if da == 0 or db == 0:
        return 0.0
    return num / (da * db)


def independent_recompute(protocol: Protocol, results: dict) -> dict:
    """Recompute the gate quantity from raw samples (ignore summary fields)."""
    samples = results.get("samples", [])
    held = [s for s in samples if s.get("split") == "held_out"]
    if not held:
        held = samples  # fall back to all samples if no split given
    scores = [float(s["score"]) for s in held]
    labels = [int(s["label"]) for s in held]
    return {
        "n_held_out": len(held),
        "n_positive": sum(labels),
        "held_out_auc": round(auc(scores, labels), 4),
        "source": "recomputed_from_raw_samples",
    }


def check(protocol: Protocol, results: dict) -> dict:
    """Return {verdict, evidence} for one preregistered study."""
    # 1) A pre-execution rejection (if recorded) takes priority — the study
    #    was refused before running, so there is no AUC to speak of.
    if results.get("rejection") is not None:
        return {"verdict": Verdict.PRE_EXECUTION_REJECTION.value,
                "evidence": results["rejection"]}

    ev = independent_recompute(protocol, results)
    crit = protocol.success_criteria or {}
    auc_min = crit.get("held_out_auc_min")
    min_pos = crit.get("min_positive_held_out", 0)

    ok_auc = auc_min is None or ev["held_out_auc"] >= auc_min
    ok_power = ev["n_positive"] >= min_pos

    if ok_auc and ok_power:
        verdict = Verdict.SUCCESS.value
    elif ok_auc and not ok_power:
        # Signal present but under-powered — do not overclaim.
        verdict = Verdict.WEAK.value
    else:
        verdict = Verdict.FAILURE.value

    ev["criteria"] = {"held_out_auc_min": auc_min, "min_positive_held_out": min_pos}
    return {"verdict": verdict, "evidence": ev}
