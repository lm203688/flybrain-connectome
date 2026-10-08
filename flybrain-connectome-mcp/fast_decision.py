"""
Operational definition of "fast local decision" (D1 of the foundation roadmap).

WHY THIS MODULE EXISTS
----------------------
The roadmap's north-star claim is deliberately hard to state precisely, and
vagueness is what killed the earlier claims in this repo (compute advantage
0/7, energy advantage 0/24, cross-unit emergence fully withdrawn): each was
phrased as a wish and was later measured as a negative. So D1 is only the
**definition** -- nothing here is run, nothing here is a result. It fixes:

  * what "fast" means (a step budget `k`, measured in recurrent steps),
  * what "local" means (the readout may only touch one module's neurons),
  * what "good enough" means (an explicit quality threshold, not a ranking),
  * and the comparison that makes it a hypothesis rather than a preference
    (a local curve against a global curve at the SAME quality threshold).

The key design decision, made because the earlier failures were all about
comparing **quality at a fixed time budget**: this module compares
**time at a fixed quality**. That is the axis nobody measured here before,
so it is neither a re-run of a withdrawn claim nor a restatement of one.

Nothing in this module is a measurement. `NOT_MEASURED` names what a decision
spec cannot speak to, so a specification is never read back as a result.

Public API
----------
    DecisionSpec                 the frozen definition of one experiment arm
    steps_to_quality()           first step at which a curve clears the bar
    time_quality_curve()         local vs global at a fixed quality threshold
    fast_decision_record()       one fully attributable record (for reports)
    local_fingerprint()          the structural fingerprint D2 must test
    DEFAULT_SPECS                the three canonical arms (afferent / remote / global)

CLI
---
    python fast_decision.py --selftest

Stdlib only, by design (same promise as `topology_profile`).
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, asdict
from typing import Optional

DECISION_SPEC_VERSION = "1.0"

# What a decision *specification* cannot say. Named so a reader never promotes
# a definition into a result.
NOT_MEASURED = [
    "dynamics",              # no reservoir is run here
    "energy",                # no spiking model is run here
    "task_performance",      # nothing is measured; only defined
    "biological_validity",   # a local readout is not a biological claim
]

# Canonical arms. "afferent" is the module that receives the input directly;
# "remote" is a module that can only learn what was routed to it; "global" is
# the unconstrained readout over every neuron (the ceiling baseline).
ARM_AFFERENT = "local_afferent"
ARM_REMOTE = "local_remote"
ARM_GLOBAL = "global"

DEFAULT_SPECS = {
    ARM_AFFERENT: {"label": "local readout over the input-bearing module"},
    ARM_REMOTE: {"label": "local readout over a module the input did not touch"},
    ARM_GLOBAL: {"label": "readout over every neuron (ceiling baseline)"},
}


@dataclass(frozen=True)
class DecisionSpec:
    """A frozen, fully attributable definition of one experiment arm.

    Every field is deliberately plain data so a spec can be dumped into JSON and
    re-read on another machine and mean the same thing. `frozen=True` because a
    mutable definition is how a result becomes unfalsifiable.
    """
    arm: str
    horizon: int                      # k: the step budget
    quality_threshold: float          # minimum accuracy to count as "decided"
    require_local_readout: bool       # True => one module's neurons only
    neurons: Optional[list] = None    # which neurons the readout may touch
    task: str = "parity_prefix"       # see fast_decision_experiment for the run
    global_baseline: Optional[float] = None
    label: str = ""

    def __post_init__(self):
        if self.horizon < 1:
            raise ValueError("horizon must be >= 1 step, got %r" % (self.horizon,))
        if not 0.0 < self.quality_threshold <= 1.0:
            raise ValueError("quality_threshold must be in (0, 1], got %r"
                             % (self.quality_threshold,))
        if self.arm not in DEFAULT_SPECS:
            raise ValueError("unknown arm %r; expected one of %s"
                             % (self.arm, sorted(DEFAULT_SPECS)))
        if self.require_local_readout and not self.neurons:
            raise ValueError("a local arm must name the neurons it may read")
        if not self.require_local_readout and self.neurons:
            raise ValueError("a global arm must not restrict neurons")

    @property
    def is_local(self) -> bool:
        return self.require_local_readout

    def as_dict(self) -> dict:
        d = asdict(self)
        d["spec_version"] = DECISION_SPEC_VERSION
        return d


def steps_to_quality(curve: dict[int, float], threshold: float) -> Optional[int]:
    """First step at which accuracy clears the threshold, else None.

    `curve` maps step -> accuracy. Steps are scanned in increasing order, so the
    answer is the *first* crossing, not the best. A curve that never reaches the
    threshold returns None -- which is a legitimate result ("cannot decide
    within the budget"), and must be printed rather than silently dropped.
    """
    for t in sorted(curve):
        if curve[t] >= threshold:
            return int(t)
    return None


def accuracy_at_step(curve: dict[int, float], t: int, default: float = 0.0) -> float:
    """Accuracy at a step the experiment did not run (before the first step)."""
    return float(curve.get(int(t), default))


def time_quality_curve(spec: DecisionSpec, curve: dict[int, float],
                       baseline_curve: Optional[dict[int, float]] = None) -> dict:
    """Compare one arm's accuracy-over-time curve against a baseline curve.

    The comparison is at a *fixed quality* (spec.quality_threshold): who reaches
    it, and in how many steps. This is the axis the repo's earlier claims did not
    use (they compared quality at a fixed budget), and it is the whole reason D3
    exists as a separate question.
    """
    mine = {int(k): float(v) for k, v in curve.items()}
    first = steps_to_quality(mine, spec.quality_threshold)
    peak = max(mine.values()) if mine else 0.0
    out = {
        "arm": spec.arm,
        "spec_version": DECISION_SPEC_VERSION,
        "horizon": spec.horizon,
        "quality_threshold": spec.quality_threshold,
        "curve": {str(k): round(v, 4) for k, v in sorted(mine.items())},
        "steps_to_quality": first,
        "decides_within_horizon": (first is not None and first <= spec.horizon),
        "peak_accuracy": round(peak, 4),
        "n_steps_measured": len(mine),
    }
    if baseline_curve:
        base = {int(k): float(v) for k, v in baseline_curve.items()}
        b_first = steps_to_quality(base, spec.quality_threshold)
        out["baseline_arm"] = ARM_GLOBAL if spec.arm != ARM_GLOBAL else None
        out["baseline_steps_to_quality"] = b_first
        out["baseline_curve"] = {str(k): round(v, 4) for k, v in sorted(base.items())}
        if first is None and b_first is None:
            out["advantage_steps"] = None
            out["advantage_label"] = "neither reaches the threshold"
        elif first is None:
            out["advantage_steps"] = None
            out["advantage_label"] = "this arm never reaches the threshold"
        elif b_first is None:
            out["advantage_steps"] = -first
            out["advantage_label"] = "this arm reaches the threshold; baseline does not"
        else:
            delta = first - b_first
            out["advantage_steps"] = -delta
            if delta < 0:
                out["advantage_label"] = "faster than baseline"
            elif delta == 0:
                out["advantage_label"] = "no difference"
            else:
                out["advantage_label"] = "slower than baseline"
    return out


def local_fingerprint(profile: dict) -> dict:
    """The structural fingerprint D2 is asked to predict from.

    These are exactly the quantities a structural profile already computes, so
    the fingerprint costs nothing new to collect. Kept deliberately short: D2's
    previous attempt died by over-fitting (the isolation predictor reached
    26/27 with six features and two topologies that were structurally identical
    at 0.01 precision yet decided oppositely). Fewer, interpretable features is
    the honest posture.
    """
    size = profile.get("size", {})
    return {
        "n_nodes": size.get("n_nodes"),
        "n_edges": size.get("n_edges"),
        "density": size.get("density"),
        "n_modules": size.get("n_modules"),
        "spectral_radius": profile.get("spectral_radius"),
        "modularity_q": profile.get("modularity_q"),
        "reciprocity": profile.get("reciprocity"),
        "feedback_edge_fraction": profile.get("feedback_edge_fraction"),
        "motifs": profile.get("motifs", {}),
        "signature": profile.get("profile_signature"),
    }


def fast_decision_record(spec: DecisionSpec, curve: dict[int, float],
                         fingerprint: Optional[dict] = None,
                         baseline_curve: Optional[dict[int, float]] = None,
                         extra: Optional[dict] = None) -> dict:
    """One fully attributable record: spec + curve + verdict + honest boundary."""
    rec = {
        "spec_version": DECISION_SPEC_VERSION,
        "spec": spec.as_dict(),
        "result": time_quality_curve(spec, curve, baseline_curve),
        "structural_fingerprint": fingerprint,
        "not_measured": NOT_MEASURED,
        "caveat": (
            "Steps are recurrent integration steps, not milliseconds; there is no "
            "clock in this framework. 'Decides within horizon' means a linear "
            "readout trained on that many integration steps clears the stated "
            "accuracy bar -- it is not a claim about a running system, a spiking "
            "network, or a biological neuron."
        ),
    }
    if extra:
        rec.update(extra)
    return rec


# --------------------------------------------------------------------- CLI

def _self_test() -> int:
    fails: list[str] = []

    def check(name, cond, detail=""):
        print("  [%s] %s %s" % ("PASS" if cond else "FAIL", name,
                                ("- " + str(detail)) if detail else ""))
        if not cond:
            fails.append(name)

    # 1. a spec pins its own invariants
    spec = DecisionSpec(arm=ARM_AFFERENT, horizon=4, quality_threshold=0.85,
                        require_local_readout=True, neurons=[0, 1, 2])
    check("local spec pins its arm", spec.is_local)
    check("spec dumps to json",
          json.loads(json.dumps(spec.as_dict()))["arm"] == ARM_AFFERENT)
    bad = (ValueError, TypeError)
    for kwargs, why in (
        (dict(arm=ARM_AFFERENT, horizon=0, quality_threshold=0.8,
              require_local_readout=True, neurons=[0]), "horizon 0"),
        (dict(arm=ARM_AFFERENT, horizon=4, quality_threshold=1.5,
              require_local_readout=True, neurons=[0]), "threshold 1.5"),
        (dict(arm="made_up", horizon=4, quality_threshold=0.8,
              require_local_readout=True, neurons=[0]), "unknown arm"),
        (dict(arm=ARM_AFFERENT, horizon=4, quality_threshold=0.8,
              require_local_readout=True), "local arm with no neurons"),
        (dict(arm=ARM_GLOBAL, horizon=4, quality_threshold=0.8,
              require_local_readout=False, neurons=[0]), "global arm with neurons"),
    ):
        try:
            DecisionSpec(**kwargs)
            check("reject %s" % why, False, "no error raised")
        except bad:
            check("reject %s" % why, True)

    # 2. steps_to_quality is the FIRST crossing and can be None
    check("first crossing, not best",
          steps_to_quality({1: 0.9, 2: 0.4, 3: 0.95}, 0.85) == 1)
    check("never reaching returns None",
          steps_to_quality({1: 0.5, 2: 0.6}, 0.9) is None)
    check("unsorted input still gives first crossing",
          steps_to_quality({5: 0.9, 2: 0.3}, 0.8) == 5)
    check("empty curve returns None", steps_to_quality({}, 0.5) is None)
    check("accuracy_at_step default",
          accuracy_at_step({2: 0.9}, 1, default=0.0) == 0.0)

    # 3. local beats global, at a fixed quality
    s_local = DecisionSpec(arm=ARM_AFFERENT, horizon=6, quality_threshold=0.85,
                           require_local_readout=True, neurons=[0, 1])
    s_glob = DecisionSpec(arm=ARM_GLOBAL, horizon=6, quality_threshold=0.85,
                          require_local_readout=False)
    local = {1: 0.55, 2: 0.72, 3: 0.9, 4: 0.94}
    glob = {1: 0.50, 2: 0.60, 3: 0.68, 4: 0.74, 5: 0.88, 6: 0.92}
    r_local = time_quality_curve(s_local, local, glob)
    r_glob = time_quality_curve(s_glob, glob, local)
    check("local reaches in 3", r_local["steps_to_quality"] == 3)
    check("local within horizon", r_local["decides_within_horizon"] is True)
    check("local is faster (advantage 2)", r_local["advantage_steps"] == 2,
          r_local["advantage_steps"])
    check("global reaches in 5", r_glob["steps_to_quality"] == 5)
    check("global is slower", r_glob["advantage_steps"] == -2, r_glob["advantage_steps"])
    check("labels are honest",
          r_local["advantage_label"] == "faster than baseline"
          and r_glob["advantage_label"] == "slower than baseline",
          (r_local["advantage_label"], r_glob["advantage_label"]))

    # 4. the failure modes must be printable, not silently dropped
    never = {1: 0.3, 2: 0.4, 3: 0.42}
    r_never = time_quality_curve(s_local, never, glob)
    check("never-reaches is explicit",
          r_never["steps_to_quality"] is None
          and r_never["decides_within_horizon"] is False
          and "never" in r_never["advantage_label"],
          r_never["advantage_label"])
    r_both = time_quality_curve(s_local, {1: 0.2}, {1: 0.2})
    check("both-miss is explicit",
          r_both["advantage_label"] == "neither reaches the threshold")

    # 5. over-budget is not the same as not-deciding
    over = {1: 0.2, 2: 0.3, 3: 0.4, 4: 0.5, 5: 0.6, 6: 0.7, 7: 0.9}
    r_over = time_quality_curve(DecisionSpec(
        arm=ARM_AFFERENT, horizon=4, quality_threshold=0.85,
        require_local_readout=True, neurons=[0, 1]), over, glob)
    check("over-budget recorded as such",
          r_over["steps_to_quality"] == 7
          and r_over["decides_within_horizon"] is False)

    # 6. fingerprint comes from an existing profile, adds nothing new
    from topology_profile import profile
    prof = profile({"nodes": [{"id": "a", "module": 0}, {"id": "b", "module": 0},
                              {"id": "c", "module": 1}],
                    "edges": [{"from": "a", "to": "b"}, {"from": "b", "to": "c"},
                              {"from": "c", "to": "a"}]})
    fp = local_fingerprint(prof)
    check("fingerprint carries the signature", fp["signature"] == prof["profile_signature"])
    check("fingerprint keeps module count", fp["n_modules"] == 2)

    # 7. a record is fully attributable and carries the honest boundary
    rec = fast_decision_record(s_local, local, fp, glob)
    check("record nests spec + result",
          rec["spec"]["arm"] == ARM_AFFERENT and rec["result"]["arm"] == ARM_AFFERENT)
    check("record declares what it did not measure",
          set(rec["not_measured"]) >= {"dynamics", "energy", "task_performance"})
    check("record states steps are not milliseconds",
          "not milliseconds" in rec["caveat"])
    check("record round-trips through json",
          json.loads(json.dumps(rec))["result"]["steps_to_quality"] == 3)

    print("=" * 60)
    if fails:
        print("FAST-DECISION SPEC SELF-TEST: FAIL (%d)" % len(fails))
        return 1
    print("FAST-DECISION SPEC SELF-TEST: PASS")
    return 0


def _cli(argv: list[str]) -> int:
    if "--selftest" in argv:
        return _self_test()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
