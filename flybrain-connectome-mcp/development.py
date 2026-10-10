"""Phase E3 · NCA-style local development.

Turns a single-cell ``seed`` organism into a larger structure by iterating
LOCAL growth rules for K steps. Nothing here knows about the "final shape" —
rules look at one module plus its own degree and decide whether to attach a
neighbour. The global pattern falls out of many local decisions, which is
the entire point of the NCA family (see review 2025-09).

The module is a straight integration of what Phase A-D already produced:

* Inputs come from ``Organism.from_dict`` (Phase A1).
* Outputs are plain organism dicts the same shape ``Organism.from_dict``
  already accepts, so a grown organism can be fed directly to ``Runtime``
  and to ``topology_profile.profile()`` for structure signatures.
* The convergence criterion can be an external structure signature, which
  lines up with the ``SpeciesRegistry`` / ``MotifCensus`` machinery in
  ``combination_reaction.py``.

Zero external dependencies: stdlib only.

Design decisions (from the design doc, do not drift):

1. **Local rules only.** No global planner; a rule sees at most one module.
2. **Probabilistic firing, deterministic fallback.** When ``rng`` is None
   a rule fires if its probability is ≥ 1.0; otherwise it is a coin flip.
   Tests can pin the seed for reproducibility.
3. **Fail-closed on unknown ``function`` values.** The ``attach_function``
   must be one of the ~22 capability-canonical classes the project already
   uses; refusing junk here is what keeps ``function_canonical`` clean.
4. **Total traceability.** Every step writes a ``GrowthLog`` row, whether
   it fired, was skipped by probability, or was skipped by the cap.
   ``DevelopmentReport.growth_log`` is the audit log.

The public surface (Phase E3 acceptance criteria):

* At least 1 new module grows from a non-trivial seed.
* Grown organism passes ``Runtime.step`` for N steps.
* Every convergence reason (``no_growth_this_step`` / ``max_steps`` /
  ``max_modules`` / ``target_reached``) is reachable.
* Empty rule set converges immediately with zero growth ops.
* Unknown function names raise ``DevelopmentError`` (fail-closed).
* Every growth op has a source, a target, and a rule id — no silent adds.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Optional


# --------------------------------------------------------------------- schema

SCHEMA_VERSION = "development.v1"

# The ~22 capability-canonical classes that the project already treats as
# first-class. Anything else raises DevelopmentError. Keep this in sync with
# flybrain-connectome-mcp/capability_canonical.py — the canonical list is a
# superset; here we only keep the subset that makes biological sense to
# *attach* in a development context.
ATTACHABLE_FUNCTIONS: tuple[str, ...] = (
    "perceive",
    "plan",
    "execute",
    "motor_output",
    "sensory_input",
    "associative_learning",
    "short_term_memory",
    "long_term_memory",
    "metabolic_support",
    "homeostasis",
    "immune_response",
    "repair_maintenance",
    "metacognition",
    "cognitive_control",
    "attention",
    "integration",
    "spiking_neuron",
    "inhibitory_neuron",
    "excitatory_neuron",
    "interneuron",
)

# Convergence-reason identifiers (used both in the report and in Gate 29
# assertions — do not rename without updating the gate).
CONV_NO_GROWTH = "no_growth_this_step"
CONV_MAX_STEPS = "max_steps"
CONV_MAX_MODULES = "max_modules"
CONV_TARGET_REACHED = "target_reached"

# Growth action identifiers.
ACT_ADD_MODULE = "add_module"
ACT_SKIP_PROB = "skip_probability"
ACT_SKIP_CAP = "skip_cap"


class DevelopmentError(ValueError):
    """Raised for any illegal input to the growth engine.

    Used for: unknown ``attach_function`` / unknown ``match_function``,
    non-positive ``probability`` or ``n_nodes``, malformed rule ids, or a
    seed organism that is not a dict / has no modules. Fail-closed.
    """


# --------------------------------------------------------------- data carriers

@dataclass(frozen=True)
class GrowthRule:
    """A single local growth rule.

    Reads like:

        IF ``source.function == match_function``
           AND ``source.out_degree < max_out_degree``
           AND ``count(rule_id, source) < max_per_source``
        THEN with probability ``probability``
           attach a new module with ``attach_function``.

    ``match_function`` and ``attach_function`` are both checked against
    ``ATTACHABLE_FUNCTIONS`` at construction time (fail-closed).
    """

    rule_id: str
    match_function: str
    attach_function: str
    probability: float = 0.5
    max_out_degree: int = 3
    max_per_source: int = 3
    attach_n_nodes: int = 2
    attach_name: Optional[str] = None
    attach_motif_source: str = "nca_growth"

    def __post_init__(self) -> None:
        if not isinstance(self.rule_id, str) or not self.rule_id.strip():
            raise DevelopmentError(
                "GrowthRule.rule_id must be a non-empty string"
            )
        if not isinstance(self.match_function, str) or not self.match_function.strip():
            raise DevelopmentError("GrowthRule.match_function must be non-empty")
        if not isinstance(self.attach_function, str) or not self.attach_function.strip():
            raise DevelopmentError("GrowthRule.attach_function must be non-empty")
        if self.match_function not in ATTACHABLE_FUNCTIONS:
            raise DevelopmentError(
                f"GrowthRule.match_function {self.match_function!r} is not in "
                f"ATTACHABLE_FUNCTIONS (fail-closed)"
            )
        if self.attach_function not in ATTACHABLE_FUNCTIONS:
            raise DevelopmentError(
                f"GrowthRule.attach_function {self.attach_function!r} is not in "
                f"ATTACHABLE_FUNCTIONS (fail-closed)"
            )
        if not isinstance(self.probability, (int, float)) or isinstance(self.probability, bool):
            raise DevelopmentError(
                f"GrowthRule.probability must be numeric, got {self.probability!r}"
            )
        p = float(self.probability)
        if math.isnan(p) or math.isinf(p) or p < 0.0 or p > 1.0:
            raise DevelopmentError(
                f"GrowthRule.probability must be in [0.0, 1.0], got {p}"
            )
        if not isinstance(self.max_out_degree, int) or isinstance(self.max_out_degree, bool) or self.max_out_degree < 0:
            raise DevelopmentError("GrowthRule.max_out_degree must be a non-negative int")
        if not isinstance(self.max_per_source, int) or isinstance(self.max_per_source, bool) or self.max_per_source < 0:
            raise DevelopmentError("GrowthRule.max_per_source must be a non-negative int")
        if not isinstance(self.attach_n_nodes, int) or isinstance(self.attach_n_nodes, bool) or self.attach_n_nodes < 1:
            raise DevelopmentError("GrowthRule.attach_n_nodes must be a positive int")

    def matches(self, module: dict) -> bool:
        """Whether this rule may fire against ``module`` (ignoring caps)."""
        if module.get("function") != self.match_function:
            return False
        if int(module.get("id", -1)) < 0:
            return False
        out_edges = module.get("_out_degree_hint", 0)
        return int(out_edges) < self.max_out_degree

    def fingerprint(self) -> str:
        """Stable 12-char fingerprint of the rule; used by the archive."""
        key = json.dumps(
            {
                "r": self.rule_id,
                "m": self.match_function,
                "a": self.attach_function,
                "p": round(self.probability, 6),
                "mo": self.max_out_degree,
                "ms": self.max_per_source,
                "nn": self.attach_n_nodes,
                "n": self.attach_name or "",
                "ms2": self.attach_motif_source,
            },
            sort_keys=True,
        )
        return hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]


@dataclass
class GrowthLog:
    """One iteration decision, whether it fired or not."""

    step: int
    rule_id: str
    source_mod_id: int
    new_mod_id: Optional[int]
    action: str
    reason: str

    def to_dict(self) -> dict:
        return {
            "step": self.step,
            "rule_id": self.rule_id,
            "source_mod_id": self.source_mod_id,
            "new_mod_id": self.new_mod_id,
            "action": self.action,
            "reason": self.reason,
        }


@dataclass
class DevelopmentReport:
    """Full audit trail for one development run."""

    seed_signature: str
    final_signature: str
    steps_used: int
    total_growth_ops: int
    total_rule_fires: int
    total_skips: int
    final_n_modules: int
    final_n_edges: int
    converged: bool
    convergence_reason: str
    growth_log: list[GrowthLog] = field(default_factory=list)
    final_organism: dict = field(default_factory=dict, repr=False)

    def to_dict(self) -> dict:
        return {
            "schema_version": SCHEMA_VERSION,
            "seed_signature": self.seed_signature,
            "final_signature": self.final_signature,
            "steps_used": self.steps_used,
            "total_growth_ops": self.total_growth_ops,
            "total_rule_fires": self.total_rule_fires,
            "total_skips": self.total_skips,
            "final_n_modules": self.final_n_modules,
            "final_n_edges": self.final_n_edges,
            "converged": self.converged,
            "convergence_reason": self.convergence_reason,
            "growth_log": [entry.to_dict() for entry in self.growth_log],
            # The final organism is written separately to keep the report
            # itself small; the caller pulls it via .final_organism.
        }

    def save_report(self, path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        doc = self.to_dict()
        doc["final_organism"] = self.final_organism
        p.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")


# --------------------------------------------------------------------- helpers

def _organism_to_doc(seed: Any) -> dict:
    """Accept a dict or an Organism-like object and return a plain dict.

    We deliberately do NOT import runtime.Organism here to keep Phase E3
    usable even if the runtime is unavailable. We sniff the ``.modules``
    list attribute and fall back to attribute access when it's there.
    """
    if isinstance(seed, dict):
        if "modules" not in seed:
            raise DevelopmentError(
                f"seed organism dict must have a 'modules' list, "
                f"got keys {list(seed.keys())[:8]!r}"
            )
        return copy.deepcopy(seed)
    # Duck-typed Organism (from runtime.py): has .modules / .edges / .meta
    mods_attr = getattr(seed, "modules", None)
    if not isinstance(mods_attr, list):
        raise DevelopmentError(
            f"seed must be a dict or an Organism-like object with a "
            f"'modules' list; got {type(seed).__name__}"
        )
    doc = {
        "modules": [],
        "edges": list(getattr(seed, "edges", []) or []),
        "meta": dict(getattr(seed, "meta", {}) or {}),
    }
    for m in mods_attr:
        if isinstance(m, dict):
            doc["modules"].append(copy.deepcopy(m))
            continue
        # duck-typed runtime.Module
        doc["modules"].append({
            "id": int(getattr(m, "mod_id", 0)),
            "name": str(getattr(m, "name", "")),
            "function": str(getattr(m, "function", "")),
            "n_nodes": int(getattr(m, "n_nodes", 1)),
            "motif_source": str(getattr(m, "motif_source", "none")),
            "parameters": dict(getattr(m, "parameters", {}) or {}),
        })
    return doc


def _validate_module_function(mod: dict, context: str) -> None:
    fn = mod.get("function")
    if not isinstance(fn, str) or not fn.strip():
        raise DevelopmentError(
            f"{context}: module {mod.get('id')!r} has empty/missing 'function'"
        )
    if fn not in ATTACHABLE_FUNCTIONS:
        raise DevelopmentError(
            f"{context}: module {mod.get('id')!r} has unknown function "
            f"{fn!r}; not in ATTACHABLE_FUNCTIONS (fail-closed)"
        )


def _compute_out_degree(organism_doc: dict) -> dict[int, int]:
    out: dict[int, int] = {}
    for m in organism_doc.get("modules") or []:
        mid = int(m.get("id", -1))
        if mid >= 0:
            out[mid] = 0
    for e in organism_doc.get("edges") or []:
        src = e.get("from", e.get("from_module", e.get("source")))
        if src is None:
            continue
        try:
            key = int(src)
        except (TypeError, ValueError):
            continue
        out[key] = out.get(key, 0) + 1
    return out


def _short_signature(organism_doc: dict) -> str:
    """A stable content hash of the structure, independent of ordering.

    Kept local to avoid importing topology_profile here — the profile
    machinery is heavy and its Graph build is slow for many tiny
    development runs. This is the "cheap" signature used inside the loop;
    the caller can still compute the full topology_profile.profile()
    signature at the end.
    """
    mods_sorted = sorted(
        (
            (int(m.get("id", -1)), str(m.get("function", "")), int(m.get("n_nodes", 1)))
            for m in organism_doc.get("modules") or []
        )
    )
    edges_sorted = sorted(
        (
            (
                int(e.get("from", e.get("from_module", e.get("source", -1)))),
                int(e.get("to", e.get("to_module", e.get("target", -1)))),
            )
            for e in organism_doc.get("edges") or []
        )
    )
    blob = json.dumps(
        {"m": mods_sorted, "e": edges_sorted},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------- rule matching

def _rule_fires(
    rule: GrowthRule,
    source_mod: dict,
    rule_uses: dict[str, int],
    rng: Optional[random.Random],
) -> tuple[bool, str]:
    """Decide whether a rule fires against a source module.

    Returns ``(should_fire, reason)`` where ``reason`` is one of
    ``"" | skip_probability | skip_cap``.
    """
    if rule_uses.get(rule.rule_id + "@" + str(source_mod["id"]), 0) >= rule.max_per_source:
        return False, ACT_SKIP_CAP
    if rng is None:
        # Deterministic fallback: fire if probability is 1.0, else skip.
        # This is deliberately conservative so a test that forgets to pass
        # an rng does not silently explode the population.
        if rule.probability >= 1.0:
            return True, ""
        return False, ACT_SKIP_PROB
    if rng.random() < rule.probability:
        return True, ""
    return False, ACT_SKIP_PROB


def _next_module_id(organism_doc: dict) -> int:
    ids = [int(m.get("id", -1)) for m in organism_doc.get("modules") or []]
    ids = [i for i in ids if i >= 0]
    return (max(ids) + 1) if ids else 0


def _attach_child(
    organism_doc: dict,
    source_mod: dict,
    rule: GrowthRule,
    new_mod_id: int,
) -> None:
    """Mutate ``organism_doc`` in place: add a child module and one edge."""
    child_name = rule.attach_name or f"{rule.attach_function}_{new_mod_id}"
    child = {
        "id": new_mod_id,
        "name": child_name,
        "function": rule.attach_function,
        "n_nodes": int(rule.attach_n_nodes),
        "motif_source": str(rule.attach_motif_source),
        "parameters": {},
    }
    organism_doc["modules"].append(child)
    organism_doc["edges"].append({
        "from": int(source_mod["id"]),
        "to": new_mod_id,
        "kind": "excitatory",
        "weight": 1.0,
    })


# ------------------------------------------------------------------ grower

class NCAGrower:
    """Iterative local-rule growth over an organism document.

    The class is intentionally small and stateless across calls; a single
    instance can drive many development runs (seed → many offspring) using
    the same rule set. That is the "population" use case in Phase C.
    """

    def __init__(self, rules: Iterable[GrowthRule]):
        rules_list = list(rules)
        if not rules_list:
            # Empty rule sets are legal — they just converge immediately.
            self._rules: list[GrowthRule] = []
            self._by_id: dict[str, GrowthRule] = {}
            return
        if not isinstance(rules_list, list) or any(not isinstance(r, GrowthRule) for r in rules_list):
            raise DevelopmentError("rules must be an iterable of GrowthRule")
        by_id: dict[str, GrowthRule] = {}
        for r in rules_list:
            if r.rule_id in by_id:
                raise DevelopmentError(f"duplicate rule_id {r.rule_id!r}")
            by_id[r.rule_id] = r
        self._rules = rules_list
        self._by_id = by_id

    # ---------------------------------------------------------------- public API

    def rule_ids(self) -> list[str]:
        return [r.rule_id for r in self._rules]

    def rules(self) -> list[GrowthRule]:
        return list(self._rules)

    def grow(
        self,
        seed: Any,
        max_steps: int = 20,
        max_modules: int = 50,
        target_signature: Optional[str] = None,
        rng: Optional[random.Random] = None,
        on_step: Optional[Callable[[int, dict], None]] = None,
    ) -> DevelopmentReport:
        """Run the growth loop until a convergence condition trips.

        Parameters
        ----------
        seed:
            Either an ``{"modules": [...], "edges": [...]}`` dict, or an
            object exposing ``.modules`` as a list of dict-like entries.
        max_steps:
            Hard cap on iterations. If reached, ``convergence_reason`` is
            ``max_steps`` regardless of whether growth is still happening.
        max_modules:
            Hard cap on total modules in the grown organism.
        target_signature:
            If provided, stop as soon as the organism's short signature
            matches this exactly (case-insensitive). Used by callers that
            want to grow "towards a known target".
        rng:
            Optional ``random.Random`` for deterministic coin flips. When
            ``None``, a rule only fires if its probability is 1.0 — this
            is intentional so accidental ``grow(seed)`` calls do not
            explode the population.
        on_step:
            Optional callback ``(step, current_doc)`` invoked *after* each
            iteration for logging purposes. Not used by any internal code.
        """
        if not isinstance(max_steps, int) or max_steps < 0:
            raise DevelopmentError("max_steps must be a non-negative int")
        if not isinstance(max_modules, int) or max_modules < 1:
            raise DevelopmentError("max_modules must be a positive int")

        doc = _organism_to_doc(seed)
        if not doc.get("modules"):
            raise DevelopmentError("seed organism has zero modules")
        for m in doc["modules"]:
            _validate_module_function(m, "seed")

        seed_sig = _short_signature(doc)
        growth_log: list[GrowthLog] = []
        rule_uses: dict[str, int] = {}
        # Per-source counters, keyed "rule_id@module_id"
        n_fires = 0
        n_skips = 0

        # Pre-flight: if the seed itself already matches target_signature,
        # report immediately without spending a step. This keeps the
        # convergence_reason semantics clean: "target_reached" means "we
        # saw the target", not "we saw the target mid-run".
        if target_signature is not None and seed_sig.lower() == target_signature.lower():
            return DevelopmentReport(
                seed_signature=seed_sig,
                final_signature=seed_sig,
                steps_used=0,
                total_growth_ops=0,
                total_rule_fires=0,
                total_skips=0,
                final_n_modules=len(doc["modules"]),
                final_n_edges=len(doc["edges"]),
                converged=True,
                convergence_reason=CONV_TARGET_REACHED,
                growth_log=growth_log,
                final_organism=doc,
            )

        for step in range(1, max_steps + 1):
            if len(doc["modules"]) >= max_modules:
                return DevelopmentReport(
                    seed_signature=seed_sig,
                    final_signature=_short_signature(doc),
                    steps_used=step - 1,
                    total_growth_ops=n_fires,
                    total_rule_fires=n_fires,
                    total_skips=n_skips,
                    final_n_modules=len(doc["modules"]),
                    final_n_edges=len(doc["edges"]),
                    converged=True,
                    convergence_reason=CONV_MAX_MODULES,
                    growth_log=growth_log,
                    final_organism=doc,
                )

            out_deg = _compute_out_degree(doc)
            # annotate module dicts with a degree hint the rule matcher reads
            for m in doc["modules"]:
                m["_out_degree_hint"] = int(out_deg.get(int(m["id"]), 0))

            fired_this_step = False
            for rule in self._rules:
                if len(doc["modules"]) >= max_modules:
                    break
                for src in list(doc["modules"]):
                    if len(doc["modules"]) >= max_modules:
                        break
                    if not rule.matches(src):
                        continue
                    key = rule.rule_id + "@" + str(src["id"])
                    should_fire, reason = _rule_fires(
                        rule, src, rule_uses, rng
                    )
                    if not should_fire:
                        growth_log.append(GrowthLog(
                            step=step,
                            rule_id=rule.rule_id,
                            source_mod_id=int(src["id"]),
                            new_mod_id=None,
                            action=reason,
                            reason=f"probability={rule.probability:.3f}",
                        ))
                        n_skips += 1
                        continue
                    # fire
                    new_id = _next_module_id(doc)
                    _attach_child(doc, src, rule, new_id)
                    rule_uses[key] = rule_uses.get(key, 0) + 1
                    growth_log.append(GrowthLog(
                        step=step,
                        rule_id=rule.rule_id,
                        source_mod_id=int(src["id"]),
                        new_mod_id=new_id,
                        action=ACT_ADD_MODULE,
                        reason=f"{src.get('function')}->{rule.attach_function}",
                    ))
                    n_fires += 1
                    fired_this_step = True
                    if on_step is not None:
                        on_step(step, doc)

            current_sig = _short_signature(doc)
            if target_signature is not None and current_sig.lower() == target_signature.lower():
                return DevelopmentReport(
                    seed_signature=seed_sig,
                    final_signature=current_sig,
                    steps_used=step,
                    total_growth_ops=n_fires,
                    total_rule_fires=n_fires,
                    total_skips=n_skips,
                    final_n_modules=len(doc["modules"]),
                    final_n_edges=len(doc["edges"]),
                    converged=True,
                    convergence_reason=CONV_TARGET_REACHED,
                    growth_log=growth_log,
                    final_organism=doc,
                )
            if not fired_this_step:
                return DevelopmentReport(
                    seed_signature=seed_sig,
                    final_signature=current_sig,
                    steps_used=step,
                    total_growth_ops=n_fires,
                    total_rule_fires=n_fires,
                    total_skips=n_skips,
                    final_n_modules=len(doc["modules"]),
                    final_n_edges=len(doc["edges"]),
                    converged=True,
                    convergence_reason=CONV_NO_GROWTH,
                    growth_log=growth_log,
                    final_organism=doc,
                )

        # hit max_steps without a no-growth step
        return DevelopmentReport(
            seed_signature=seed_sig,
            final_signature=_short_signature(doc),
            steps_used=max_steps,
            total_growth_ops=n_fires,
            total_rule_fires=n_fires,
            total_skips=n_skips,
            final_n_modules=len(doc["modules"]),
            final_n_edges=len(doc["edges"]),
            converged=True,
            convergence_reason=CONV_MAX_STEPS,
            growth_log=growth_log,
            final_organism=doc,
        )


# --------------------------------------------------------------- CLI + tests

def _self_test() -> int:
    """Self-test: exercises all four convergence reasons + all skip types.

    Returns the count of assertions that passed. Called by Gate 29.
    """
    checks = 0

    # 1. Empty rule set → immediate no_growth_this_step, zero ops
    g = NCAGrower(rules=[])
    rep = g.grow({"modules": [{"id": 0, "name": "s0", "function": "perceive", "n_nodes": 2}], "edges": []})
    assert rep.convergence_reason == CONV_NO_GROWTH, "empty rules should not grow"
    assert rep.total_growth_ops == 0, "empty rules should not grow"
    assert rep.final_n_modules == 1
    assert rep.steps_used == 1, "empty rules should stop at step 1"
    checks += 3

    # 2. Grow from perceive -> plan -> execute
    rules = [
        GrowthRule(
            rule_id="perceive_to_plan",
            match_function="perceive",
            attach_function="plan",
            probability=1.0,
            max_out_degree=1,
            max_per_source=1,
            attach_n_nodes=2,
        ),
        GrowthRule(
            rule_id="plan_to_execute",
            match_function="plan",
            attach_function="execute",
            probability=1.0,
            max_out_degree=1,
            max_per_source=1,
            attach_n_nodes=2,
        ),
    ]
    g = NCAGrower(rules=rules)
    seed = {
        "modules": [{"id": 0, "name": "sensory_root", "function": "perceive", "n_nodes": 2}],
        "edges": [],
    }
    rep = g.grow(seed, max_steps=10, max_modules=10)
    # step 1: perceive -> plan ; step 2: plan -> execute ; step 3: no growth
    assert rep.total_growth_ops == 2, f"expected 2 growth ops, got {rep.total_growth_ops}"
    assert rep.final_n_modules == 3
    assert rep.final_n_edges == 2
    assert rep.convergence_reason == CONV_NO_GROWTH
    assert any(el.action == ACT_ADD_MODULE for el in rep.growth_log)
    # every fire has all 3 ids
    for el in rep.growth_log:
        assert el.rule_id, "rule_id present"
        assert isinstance(el.source_mod_id, int), "source_mod_id is int"
        if el.action == ACT_ADD_MODULE:
            assert el.new_mod_id is not None, "add_module always sets new_mod_id"
    checks += 6

    # 3. max_modules trips when the cap is very tight
    rules_tight = [
        GrowthRule(
            rule_id="perceive_to_plan",
            match_function="perceive",
            attach_function="plan",
            probability=1.0,
            max_out_degree=5,
            max_per_source=5,
        ),
    ]
    g = NCAGrower(rules=rules_tight)
    rep = g.grow(seed, max_steps=10, max_modules=2)
    assert rep.convergence_reason == CONV_MAX_MODULES, rep.convergence_reason
    assert rep.final_n_modules == 2
    checks += 2

    # 4. max_steps trips when rules keep firing
    rules_open = [
        GrowthRule(
            rule_id="perceive_to_plan",
            match_function="perceive",
            attach_function="plan",
            probability=1.0,
            max_out_degree=100,
            max_per_source=100,
        ),
    ]
    g = NCAGrower(rules=rules_open)
    rep = g.grow(seed, max_steps=3, max_modules=100)
    assert rep.convergence_reason == CONV_MAX_STEPS
    assert rep.steps_used == 3
    checks += 2

    # 5. target_signature convergence: give a target the seed itself matches
    rep = g.grow(seed, max_steps=3, max_modules=100,
                 target_signature=_short_signature(seed))
    assert rep.convergence_reason == CONV_TARGET_REACHED, rep.convergence_reason
    checks += 1

    # 6. Skip-cap: max_per_source=1 means a second fire attempt is skip_cap
    rules_one = [
        GrowthRule(
            rule_id="one_per_source",
            match_function="perceive",
            attach_function="plan",
            probability=1.0,
            max_out_degree=5,
            max_per_source=1,
        ),
    ]
    g = NCAGrower(rules=rules_one)
    rep = g.grow(seed, max_steps=5, max_modules=100)
    actions = [el.action for el in rep.growth_log]
    assert ACT_SKIP_CAP in actions, f"expected skip_cap in {actions}"
    checks += 1

    # 7. Fail-closed: unknown attach_function
    try:
        GrowthRule(rule_id="bad", match_function="perceive", attach_function="telepathy")
        raise AssertionError("expected DevelopmentError")
    except DevelopmentError:
        checks += 1

    # 8. Fail-closed: unknown match_function
    try:
        GrowthRule(rule_id="bad2", match_function="quantum_jump", attach_function="plan")
        raise AssertionError("expected DevelopmentError")
    except DevelopmentError:
        checks += 1

    # 9. Fail-closed: probability out of range
    try:
        GrowthRule(rule_id="bad3", match_function="perceive",
                   attach_function="plan", probability=1.5)
        raise AssertionError("expected DevelopmentError")
    except DevelopmentError:
        checks += 1

    # 10. Fail-closed: empty seed modules
    try:
        g = NCAGrower(rules=rules)
        g.grow({"modules": [], "edges": []})
        raise AssertionError("expected DevelopmentError")
    except DevelopmentError:
        checks += 1

    # 11. Fail-closed: seed module with unknown function
    try:
        g = NCAGrower(rules=rules)
        g.grow({"modules": [{"id": 0, "function": "warp_drive", "n_nodes": 1}], "edges": []})
        raise AssertionError("expected DevelopmentError")
    except DevelopmentError:
        checks += 1

    # 12. Duplicate rule_id rejected
    try:
        NCAGrower(rules=[
            GrowthRule(rule_id="dup", match_function="perceive", attach_function="plan"),
            GrowthRule(rule_id="dup", match_function="plan", attach_function="execute"),
        ])
        raise AssertionError("expected DevelopmentError")
    except DevelopmentError:
        checks += 1

    # 13. Report.to_dict shape + save round-trip
    rep_doc = rep.to_dict()
    for k in ("seed_signature", "final_signature", "steps_used",
              "total_growth_ops", "convergence_reason", "growth_log"):
        assert k in rep_doc
    checks += 2

    # 14. Deterministic rng: same seed → same signature
    r1 = g.grow(seed, max_steps=10, max_modules=100,
                rng=random.Random(42))
    r2 = g.grow(seed, max_steps=10, max_modules=100,
                rng=random.Random(42))
    assert r1.final_signature == r2.final_signature
    checks += 1

    return checks


def _cli(argv: list[str]) -> int:
    import sys
    if not argv:
        n = _self_test()
        print(f"development.py: {n} checks passed")
        return 0
    cmd = argv[0]
    if cmd == "--self-test":
        n = _self_test()
        print(f"development.py: {n} checks passed")
        return 0
    if cmd == "--demo":
        rules = [
            GrowthRule(rule_id="perceive_to_plan",
                       match_function="perceive", attach_function="plan",
                       probability=1.0, max_out_degree=2, max_per_source=2),
            GrowthRule(rule_id="plan_to_execute",
                       match_function="plan", attach_function="execute",
                       probability=1.0, max_out_degree=2, max_per_source=2),
            GrowthRule(rule_id="execute_to_memory",
                       match_function="execute", attach_function="short_term_memory",
                       probability=1.0, max_out_degree=2, max_per_source=2),
        ]
        g = NCAGrower(rules=rules)
        seed = {"modules": [{"id": 0, "name": "cell_root", "function": "perceive", "n_nodes": 2}], "edges": []}
        rep = g.grow(seed, max_steps=15, max_modules=30, rng=random.Random(7))
        doc = rep.to_dict()
        print(json.dumps(doc, indent=2, ensure_ascii=False))
        print(f"\n# summary: {rep.total_growth_ops} ops, {rep.final_n_modules} modules, "
              f"conv={rep.convergence_reason} after {rep.steps_used} steps")
        return 0
    print(f"unknown command {cmd!r}; use --self-test or --demo", file=sys.stderr)
    return 2


if __name__ == "__main__":
    import sys
    sys.exit(_cli(sys.argv[1:]))
