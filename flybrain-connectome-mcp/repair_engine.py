"""
repair_engine.py — Phase D: orchestration layer over atomic repair patches.

This is the D2 deliverable from the project's positioning strategy. It wraps
the existing `repair.py` primitives (Patch, RepairOperator, RepairLoop,
RepairValidator) with a higher-level engine that:

  1. Accepts a damaged organism and its pre-damage signature
  2. Runs the SkillOpt-Lite 4-step cycle: Trace → Explore → Consensus → Validate
  3. Accepts patches only if they restore structural health (no invented fitness)
  4. Archives accepted patches for replay

Key design invariants (from DIGITAL_ORGANISM_DESIGN_2026-10-10.md §D2):
  * **Structural acceptance**: metric is `1 - distance(repaired, pre_damage) /
    distance(damaged, pre_damage)`. This is NOT a task-metric improvement — it
    measures how much of the *topological damage* was undone.
  * **No fitness function**: unlike SkillOpt-Lite (arXiv:2607.03451), which
    optimizes for task accuracy, this engine optimizes for *structural
    restoration*. This is the project's key differentiator.
  * **Reversible patches**: every accepted patch has a reverse operation.
  * **Dead-zone guard**: patches with Δ < dead_zone (default 0.02) are
    rejected as statistical noise.

Stdlib-only. Zero external dependencies.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import random
import sys
import time
from dataclasses import dataclass, field
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..")))

# ------------------------------------------------------------------ imports

from repair import (
    Patch,
    RepairOperator,
    RepairValidator,
    signature_distance,
    repair_improvement,
)
from profile_health import profile_health as _profile_health_fn

# ------------------------------------------------------------------ config

@dataclass
class RepairEngineConfig:
    """Tuning parameters for the repair engine."""
    max_candidates: int = 20
    max_steps: int = 8
    dead_zone: float = 0.02
    accept_threshold: float = 0.30   # minimum improvement to accept
    rng_seed: int = 42
    verbose: bool = False


# ------------------------------------------------------------------ engine

@dataclass
class RepairStep:
    """Record of a single repair step."""
    step: int
    patch_kind: str
    patch_id: str
    improvement: float
    accepted: bool
    reason: str

    def to_dict(self) -> dict:
        return {
            "step": self.step,
            "patch_kind": self.patch_kind,
            "patch_id": self.patch_id,
            "improvement": self.improvement,
            "accepted": self.accepted,
            "reason": self.reason,
        }


@dataclass
class RepairEngineReport:
    """Full report from the repair engine."""
    organism_name: str
    initial_signature: str
    final_signature: str
    pre_damage_signature: str
    initial_health: float
    final_health: float
    steps: list[dict]
    n_accepted: int
    n_total_candidates: int
    accepted_patches: list[dict]
    wall_clock_s: float

    def to_dict(self) -> dict:
        return {
            "organism_name": self.organism_name,
            "initial_signature": self.initial_signature,
            "final_signature": self.final_signature,
            "pre_damage_signature": self.pre_damage_signature,
            "initial_health": self.initial_health,
            "final_health": self.final_health,
            "health_delta": round(self.final_health - self.initial_health, 6),
            "n_steps": len(self.steps),
            "n_accepted": self.n_accepted,
            "n_total_candidates": self.n_total_candidates,
            "steps": [s.to_dict() for s in self.steps],
            "accepted_patches": self.accepted_patches,
            "wall_clock_s": round(self.wall_clock_s, 3),
        }


class RepairEngine:
    """Orchestration layer for structural repair.

    Wraps the existing RepairOperator / RepairLoop / RepairValidator with
    a higher-level interface that:
      1. Enumerates candidate patches
      2. Evaluates each by structural improvement
      3. Accepts only patches above the dead-zone threshold
      4. Applies accepted patches sequentially
      5. Records the full audit trail
    """

    def __init__(self, config: RepairEngineConfig | None = None):
        self.config = config or RepairEngineConfig()
        self.validator = RepairValidator(dead_zone=self.config.dead_zone)
        self.operator = RepairOperator()
        self.rng = random.Random(self.config.rng_seed)

    def repair(
        self,
        organism: dict,
        pre_damage_signature: str,
    ) -> RepairEngineReport:
        """Run the repair engine on a damaged organism.

        Args:
            organism: the damaged organism dict
            pre_damage_signature: topology signature of the organism before damage

        Returns:
            RepairEngineReport with full audit trail
        """
        start_time = time.time()
        org_name = organism.get("name", "unnamed")

        # initial state
        initial_sig = _fingerprint(organism)
        initial_health = _health_score(organism)

        current = copy.deepcopy(organism)
        steps: list[RepairStep] = []
        accepted_patches: list[dict] = []
        n_accepted = 0
        n_total = 0

        for step_idx in range(self.config.max_steps):
            # Enumerate candidates
            candidates = self.operator.enumerate_candidates(
                current,
                pre_damage_signature=pre_damage_signature,
                max_candidates=self.config.max_candidates,
                rng=self.rng,
            )

            if not candidates:
                if self.config.verbose:
                    print(f"  step {step_idx}: no candidates generated")
                break

            # Evaluate each candidate
            best_patch = None
            best_improvement = -1.0

            for patch in candidates:
                n_total += 1
                # Apply patch to a copy
                try:
                    candidate_org = patch.apply(copy.deepcopy(current))
                except Exception as exc:
                    if self.config.verbose:
                        print(f"  step {step_idx}: patch {patch.patch_id} "
                              f"apply failed: {exc}")
                    continue

                # Compute improvement
                candidate_sig = _fingerprint(candidate_org)
                improvement = repair_improvement(
                    pre_damage_signature,
                    initial_sig,
                    candidate_sig,
                )

                # Check if accepted
                accepted, imp, reason = self.validator.evaluate(
                    improvement=improvement,
                    min_acceptance=self.config.accept_threshold,
                )

                step_record = RepairStep(
                    step=step_idx,
                    patch_kind=patch.kind,
                    patch_id=patch.patch_id,
                    improvement=imp,
                    accepted=accepted,
                    reason=reason,
                )
                steps.append(step_record)

                if accepted and imp > best_improvement:
                    best_patch = patch
                    best_improvement = imp

            # Apply best patch
            if best_patch is not None:
                try:
                    current = best_patch.apply(current)
                    n_accepted += 1
                    accepted_patches.append(best_patch.as_dict())
                    if self.config.verbose:
                        print(f"  step {step_idx}: accepted {best_patch.kind} "
                              f"Δ={best_improvement:+.4f}")
                except Exception as exc:
                    if self.config.verbose:
                        print(f"  step {step_idx}: apply failed: {exc}")

            else:
                if self.config.verbose:
                    print(f"  step {step_idx}: no accepted candidates")

            # Early termination if improvement is marginal
            if best_improvement < self.config.dead_zone:
                if self.config.verbose:
                    print(f"  step {step_idx}: improvement below dead-zone, stopping")
                break

        # Final state
        final_sig = _fingerprint(current)
        final_health = _health_score(current)
        wall_clock = time.time() - start_time

        return RepairEngineReport(
            organism_name=org_name,
            initial_signature=initial_sig,
            final_signature=final_sig,
            pre_damage_signature=pre_damage_signature,
            initial_health=initial_health,
            final_health=final_health,
            steps=steps,
            n_accepted=n_accepted,
            n_total_candidates=n_total,
            accepted_patches=accepted_patches,
            wall_clock_s=wall_clock,
        )


# ------------------------------------------------------------------ helpers

def _fingerprint(organism: dict) -> str:
    """Compute a structural fingerprint of an organism."""
    units = organism.get("modules") or organism.get("units") or []
    edges = organism.get("edges") or organism.get("connections") or []
    unit_ids = sorted(str(u.get("id") or u.get("name", "")) for u in units)
    edge_keys = sorted(
        f"{e.get('from','?')}->{e.get('to','?')}" for e in edges
        if isinstance(e, dict)
    )
    fingerprint_input = json.dumps(
        {"units": unit_ids, "edges": edge_keys}, sort_keys=True
    )
    return hashlib.sha256(fingerprint_input.encode()).hexdigest()


def _health_score(organism: dict) -> float:
    """Get structural health score for an organism."""
    name = organism.get("name", "unnamed")
    try:
        result = _profile_health_fn(name)
        return result.get("degradation_score", 0.0)
    except Exception:
        return 0.0


# ------------------------------------------------------------------ CLI

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Repair engine (Phase D)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-steps", type=int, default=8)
    parser.add_argument("--threshold", type=float, default=0.30)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    config = RepairEngineConfig(
        max_steps=args.max_steps,
        accept_threshold=args.threshold,
        rng_seed=args.seed,
        verbose=args.verbose,
    )

    # Create a test damaged organism
    original = {
        "name": "test_organism",
        "modules": [
            {"id": "m1", "name": "perceive", "profile": "perceive", "category": "cognitive"},
            {"id": "m2", "name": "plan", "profile": "plan", "category": "cognitive"},
            {"id": "m3", "name": "act", "profile": "act", "category": "cognitive"},
            {"id": "m4", "name": "learn", "profile": "learn", "category": "cognitive"},
        ],
        "edges": [
            {"from": "m1", "to": "m2", "type": "functional", "weight": 0.8},
            {"from": "m2", "to": "m3", "type": "functional", "weight": 0.7},
            {"from": "m3", "to": "m1", "type": "feedback", "weight": 0.3},
            {"from": "m4", "to": "m2", "type": "functional", "weight": 0.5},
        ],
    }

    # Simulate damage: remove one module and its edges
    damaged = copy.deepcopy(original)
    damaged["modules"] = [m for m in damaged["modules"] if m["id"] != "m4"]
    damaged["edges"] = [
        e for e in damaged["edges"]
        if e.get("from") != "m4" and e.get("to") != "m4"
    ]

    # Get pre-damage signature
    pre_damage_sig = _fingerprint(original)

    engine = RepairEngine(config)
    report = engine.repair(damaged, pre_damage_signature=pre_damage_sig)
    result = report.to_dict()

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(f"\n=== Repair Engine (Phase D) ===")
        print(f"Organism: {result['organism_name']}")
        print(f"Initial health:  {result['initial_health']:.4f}")
        print(f"Final health:    {result['final_health']:.4f}")
        print(f"Δ health:        {result.get('health_delta', 0):+.4f}")
        print(f"Steps:           {result['n_steps']}")
        print(f"Accepted:        {result['n_accepted']}/{result['n_total_candidates']}")
        print(f"Accepted patches: {len(result['accepted_patches'])}")
        print(f"Wall clock:      {result['wall_clock_s']:.3f}s")


if __name__ == "__main__":
    main()
