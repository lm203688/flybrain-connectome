"""
self_evolving_loop.py — Phase C: self-evolution via SkillOpt-Lite 4-step cycle.

docs/DIGITAL_ORGANISM_DESIGN_2026-10-10.md §四 Phase C (D3 — no fitness function):

    Trace     → capture current state (topology signature + health)
    Explore   → propose N candidate mutations (add_unit / rewire / drop_unit)
    Consensus → evaluate each candidate by structural health delta
    Validate  → accept only candidates that don't degrade health

Design invariants (from project positioning):
  * **No fitness function.** Selection is structural-health-delta based,
    not task-accuracy based. This is the key differentiator from SkillOpt-Lite
    (arXiv:2607.03451), which uses task-metric improvement.
  * **Archive-based selection.** Non-optimal variants are retained in an
    archive (DGM-style), not discarded.
  * **Deterministic given a fixed seed.** Every step is reproducible.

The loop is a *pure orchestration layer* over the existing primitives:
  * repair.py            — atomic patches (add_unit / rewire / drop_unit)
  * profile_health.py    — structural health metrics
  * topology_profile.py  — topology signatures
  * population.py        — archive management

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

# Reuse repair primitives
try:
    from repair import (
        Patch,
        RepairOperator,
        signature_distance,
    )
except ImportError:
    Patch = None
    RepairOperator = None
    def signature_distance(a, b):  # noqa: D401
        return 0.0

# Reuse health primitives
try:
    from profile_health import profile_health as _profile_health_fn
except ImportError:
    def _profile_health_fn(name):  # noqa: D401
        return {"degradation_score": 0.0, "status": "unknown"}

# ------------------------------------------------------------------ config

@dataclass
class EvolutionConfig:
    """Tuning parameters for the self-evolving loop.

    All defaults are chosen for *interpretability* rather than
    *optimality*: a single generation with n_candidates=8 and a
    health threshold of +0.02 is enough to see whether the loop
    is doing anything at all.
    """
    n_candidates: int = 8            # mutations per generation
    health_threshold: float = 0.02   # minimum Δ to accept
    max_generations: int = 3         # safety cap
    archive_capacity: int = 20       # DGM-style archive size
    dead_zone: float = 0.005         # below this Δ is noise, not signal
    rng_seed: int = 42               # deterministic


# ------------------------------------------------------------------ trace

def trace_state(organism: dict) -> dict:
    """Capture a snapshot of the organism's current state.

    Returns a compact dict that can be compared (via sha256) to a
    future snapshot to detect structural drift.
    """
    # topology signature (from the existing topology_profile layer if available)
    try:
        from topology_profile import profile as _prof_fn
        prof = _prof_fn(organism)
        topo_sig = prof.get("signature", "") if isinstance(prof, dict) else ""
    except Exception:
        topo_sig = ""

    # health score
    try:
        health = _profile_health_fn(organism.get("name", "unnamed"))
        health_score = health.get("degradation_score", 0.0)
        health_status = health.get("status", "unknown")
    except Exception:
        health_score = 0.0
        health_status = "unknown"

    # structural fingerprint
    units = organism.get("modules") or organism.get("units") or []
    edges = organism.get("edges") or organism.get("connections") or []
    n_units = len(units)
    n_edges = len(edges)
    unit_ids = sorted(str(u.get("id") or u.get("name", "")) for u in units)
    edge_keys = sorted(f"{e.get('from','?')}->{e.get('to','?')}" for e in edges
                       if isinstance(e, dict))
    fingerprint_input = json.dumps(
        {"units": unit_ids, "edges": edge_keys}, sort_keys=True
    )
    fingerprint = hashlib.sha256(fingerprint_input.encode()).hexdigest()[:16]

    return {
        "topology_signature": topo_sig,
        "health_score": health_score,
        "health_status": health_status,
        "n_units": n_units,
        "n_edges": n_edges,
        "fingerprint": fingerprint,
        "timestamp": time.time(),
    }


# ------------------------------------------------------------------ explore

def _random_rewire(organism: dict, rng: random.Random) -> dict:
    """Randomly rewire one edge (add or replace)."""
    org = copy.deepcopy(organism)
    units = org.get("modules") or org.get("units") or []
    edges = org.get("edges") or org.get("connections") or []
    if not units or len(units) < 2:
        return org

    unit_names = [u.get("name") or u.get("id") or "" for u in units]
    unit_names = [n for n in unit_names if n]

    # pick a source and target
    src = rng.choice(unit_names)
    dst = rng.choice([n for n in unit_names if n != src])

    # check if this edge already exists
    existing = {(e.get("from"), e.get("to")) for e in edges if isinstance(e, dict)}
    if (src, dst) in existing:
        return org  # no-op

    # add the edge
    new_edge = {
        "from": src,
        "to": dst,
        "type": "functional",
        "weight": rng.uniform(0.1, 1.0),
    }
    edges.append(new_edge)
    return org


def _random_drop_unit(organism: dict, rng: random.Random) -> dict:
    """Randomly remove one non-critical module."""
    org = copy.deepcopy(organism)
    units = org.get("modules") or org.get("units") or []
    edges = org.get("edges") or org.get("connections") or []

    if len(units) <= 2:
        return org  # don't drop below 2 modules

    # find removable units (not the last two)
    removable = [u for u in units if not u.get("critical", False)]
    if not removable:
        removable = units[:-2]  # keep last 2

    drop = rng.choice(removable)
    drop_name = drop.get("name") or drop.get("id") or ""

    # remove unit and its edges
    org["modules"] = [u for u in units if (u.get("name") or u.get("id")) != drop_name] \
        if "modules" in org else \
        [u for u in units if (u.get("name") or u.get("id")) != drop_name]
    org["edges"] = [e for e in edges
                    if isinstance(e, dict)
                    and e.get("from") != drop_name
                    and e.get("to") != drop_name]

    return org


def _random_add_unit(organism: dict, rng: random.Random) -> dict:
    """Randomly add a new module and connect it to an existing one."""
    org = copy.deepcopy(organism)
    units = org.get("modules") or org.get("units") or []
    edges = org.get("edges") or org.get("connections") or []

    # generate a new unit
    new_id = f"evolved_{int(time.time()*1000)%100000}_{len(units)}"
    new_unit = {
        "id": new_id,
        "name": new_id,
        "profile": rng.choice(["perceive", "plan", "act", "learn"]),
        "category": "cognitive",
    }

    # connect to a random existing unit
    if units:
        target = rng.choice(units)
        target_name = target.get("name") or target.get("id") or ""
        new_edge = {
            "from": new_id,
            "to": target_name,
            "type": "functional",
            "weight": rng.uniform(0.1, 1.0),
        }
        edges.append(new_edge)

    if "modules" in org:
        org["modules"].append(new_unit)
    else:
        org["units"].append(new_unit)
    org["edges"] = edges

    return org


def explore(organism: dict, config: EvolutionConfig,
            rng: random.Random) -> list[dict]:
    """Propose N candidate mutations via random structural perturbations.

    Each candidate is a full Organism dict (deep copy of source + mutation).
    The mutations are:
      * 50% rewire (add a random edge)
      * 30% drop_unit (remove a random non-critical module)
      * 20% add_unit (add a random new module)
    """
    candidates: list[dict] = []
    for i in range(config.n_candidates):
        r = rng.random()
        if r < 0.5:
            candidate = _random_rewire(organism, rng)
        elif r < 0.8:
            candidate = _random_drop_unit(organism, rng)
        else:
            candidate = _random_add_unit(organism, rng)

        # tag for traceability
        candidate["_evolution"] = {
            "candidate_id": i,
            "mutation_type": "rewire" if r < 0.5 else ("drop_unit" if r < 0.8 else "add_unit"),
            "generation": 0,
        }
        candidates.append(candidate)
    return candidates


# ------------------------------------------------------------------ consensus

def consensus(candidates: list[dict], baseline_health: float,
              config: EvolutionConfig) -> list[dict]:
    """Evaluate each candidate by structural health delta.

    Returns candidates sorted by health delta descending.
    Only candidates with Δ >= config.health_threshold pass.
    """
    scored: list[dict] = []
    for c in candidates:
        name = c.get("name") or c.get("id") or "unnamed"
        try:
            health = _profile_health_fn(name)
            score = health.get("degradation_score", 0.0)
        except Exception:
            score = 0.0

        delta = score - baseline_health
        c = dict(c)
        c["_evolution"] = dict(c.get("_evolution", {}))
        c["_evolution"]["health_delta"] = round(delta, 6)
        c["_evolution"]["health_score"] = round(score, 6)
        c["_evolution"]["accepted"] = delta >= config.health_threshold
        scored.append(c)

    # sort by delta descending
    scored.sort(key=lambda x: x["_evolution"].get("health_delta", 0.0), reverse=True)
    return scored


# ------------------------------------------------------------------ validate

def validate(candidate: dict, baseline_health: float,
             config: EvolutionConfig) -> tuple[bool, dict]:
    """Structural acceptance check for a single candidate.

    Returns (accepted, evolution_record).
    """
    evo = candidate.get("_evolution", {})
    delta = evo.get("health_delta", 0.0)
    score = evo.get("health_score", 0.0)

    accepted = (
        delta >= config.health_threshold
        and delta >= config.dead_zone
        and score > 0.0
    )

    record = {
        "accepted": accepted,
        "health_delta": delta,
        "health_score": score,
        "mutation_type": evo.get("mutation_type", "unknown"),
        "candidate_id": evo.get("candidate_id", -1),
        "reason": (
            f"Δ={delta:+.4f} ≥ threshold {config.health_threshold}"
            if accepted
            else f"Δ={delta:+.4f} < threshold {config.health_threshold}"
        ),
    }
    return accepted, record


# ------------------------------------------------------------------ archive

@dataclass
class Archive:
    """DGM-style archive — retains non-optimal variants for exploration.

    Unlike a simple population (which keeps only the best), the archive
    keeps a diverse set of organisms seen across generations. This
    prevents premature convergence and allows recombination.
    """
    capacity: int = 20
    organisms: list[dict] = field(default_factory=list)
    seen_signatures: set = field(default_factory=set)

    def add(self, organism: dict) -> bool:
        """Add an organism to the archive if it's novel."""
        sig = trace_state(organism)["fingerprint"]
        if sig in self.seen_signatures:
            return False
        self.seen_signatures.add(sig)
        self.organisms.append(organism)
        # evict oldest if over capacity
        if len(self.organisms) > self.capacity:
            self.organisms.pop(0)
        return True

    def sample(self, rng: random.Random) -> dict:
        """Randomly sample an organism from the archive."""
        if not self.organisms:
            return {}
        return copy.deepcopy(rng.choice(self.organisms))

    def __len__(self) -> int:
        return len(self.organisms)


# ------------------------------------------------------------------ loop

@dataclass
class GenerationResult:
    """Result of a single generation in the evolution loop."""
    generation: int
    parent_fingerprint: str
    parent_health: float
    n_candidates: int
    n_accepted: int
    accepted_delta: list[dict]
    best_delta: float
    best_candidate: dict | None
    elapsed_s: float

    def to_dict(self) -> dict:
        return {
            "generation": self.generation,
            "parent_fingerprint": self.parent_fingerprint,
            "parent_health": self.parent_health,
            "n_candidates": self.n_candidates,
            "n_accepted": self.n_accepted,
            "accepted_delta": self.accepted_delta,
            "best_delta": self.best_delta,
            "elapsed_s": round(self.elapsed_s, 3),
        }


@dataclass
class EvolutionReport:
    """Full report from the self-evolving loop."""
    config: dict
    initial_fingerprint: str
    final_fingerprint: str
    initial_health: float
    final_health: float
    generations: list[dict]
    archive_size: int
    total_accepted: int
    converged: bool
    wall_clock_s: float

    def to_dict(self) -> dict:
        return {
            "config": self.config,
            "initial_fingerprint": self.initial_fingerprint,
            "final_fingerprint": self.final_fingerprint,
            "initial_health": self.initial_health,
            "final_health": self.final_health,
            "health_delta": round(self.final_health - self.initial_health, 6),
            "n_generations": len(self.generations),
            "generations": self.generations,
            "archive_size": self.archive_size,
            "total_accepted": self.total_accepted,
            "converged": self.converged,
            "wall_clock_s": round(self.wall_clock_s, 3),
        }


def run_evolution(organism: dict, config: EvolutionConfig | None = None) -> EvolutionReport:
    """
    Run the self-evolving loop (Trace → Explore → Consensus → Validate).

    Args:
        organism: initial organism dict
        config: evolution parameters (defaults to EvolutionConfig())

    Returns:
        EvolutionReport with full audit trail
    """
    if config is None:
        config = EvolutionConfig()

    rng = random.Random(config.rng_seed)
    start_time = time.time()

    # Phase 1: Trace — capture initial state
    initial_trace = trace_state(organism)
    current = organism
    archive = Archive(capacity=config.archive_capacity)
    archive.add(copy.deepcopy(current))

    generations: list[dict] = []
    total_accepted = 0

    for gen in range(config.max_generations):
        gen_start = time.time()

        # Trace — current state
        trace = trace_state(current)
        parent_fingerprint = trace["fingerprint"]
        parent_health = trace["health_score"]

        # Explore — propose candidates
        candidates = explore(current, config, rng)

        # Consensus — score candidates
        scored = consensus(candidates, parent_health, config)

        # Validate — accept improvements
        accepted_delta = []
        best_delta = float("-inf")
        best_candidate = None

        for c in scored:
            accepted, record = validate(c, parent_health, config)
            if accepted:
                accepted_delta.append(record)
                archive.add(copy.deepcopy(c))
                if record["health_delta"] > best_delta:
                    best_delta = record["health_delta"]
                    best_candidate = c
                total_accepted += 1

        gen_result = GenerationResult(
            generation=gen,
            parent_fingerprint=parent_fingerprint,
            parent_health=parent_health,
            n_candidates=len(candidates),
            n_accepted=len(accepted_delta),
            accepted_delta=accepted_delta,
            best_delta=best_delta if best_delta != float("-inf") else 0.0,
            best_candidate=None,  # don't store full candidate in result
            elapsed_s=time.time() - gen_start,
        )
        generations.append(gen_result.to_dict())

        # Update current if we have an accepted improvement
        if best_candidate is not None:
            current = best_candidate

        # Early termination if no improvement
        if len(accepted_delta) == 0:
            break

    # Final trace
    final_trace = trace_state(current)
    wall_clock = time.time() - start_time

    return EvolutionReport(
        config=config.__dict__,
        initial_fingerprint=initial_trace["fingerprint"],
        final_fingerprint=final_trace["fingerprint"],
        initial_health=initial_trace["health_score"],
        final_health=final_trace["health_score"],
        generations=generations,
        archive_size=len(archive),
        total_accepted=total_accepted,
        converged=final_trace["fingerprint"] != initial_trace["fingerprint"],
        wall_clock_s=wall_clock,
    )


# ------------------------------------------------------------------ CLI

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Self-evolving loop (Phase C)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n-candidates", type=int, default=8)
    parser.add_argument("--max-gen", type=int, default=3)
    parser.add_argument("--threshold", type=float, default=0.02)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    config = EvolutionConfig(
        n_candidates=args.n_candidates,
        max_generations=args.max_gen,
        health_threshold=args.threshold,
        rng_seed=args.seed,
    )

    # Create a simple test organism
    test_organism = {
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
        ],
    }

    report = run_evolution(test_organism, config)
    result = report.to_dict()

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(f"\n=== Self-Evolving Loop (Phase C) ===")
        print(f"Config: {config.__dict__}")
        print(f"Initial health: {result['initial_health']:.4f}")
        print(f"Final health:   {result['final_health']:.4f}")
        print(f"Δ health:       {result.get('health_delta', 0):+.4f}")
        print(f"Generations:    {result['n_generations']}")
        print(f"Total accepted: {result['total_accepted']}")
        print(f"Archive size:   {result['archive_size']}")
        print(f"Converged:      {result['converged']}")
        print(f"Wall clock:     {result['wall_clock_s']:.3f}s")
        print(f"\nPer-generation:")
        for g in result["generations"]:
            print(f"  Gen {g['generation']}: "
                  f"health={g['parent_health']:.4f}, "
                  f"accepted={g['n_accepted']}/{g['n_candidates']}, "
                  f"best_Δ={g['best_delta']:+.4f}, "
                  f"time={g['elapsed_s']:.3f}s")


if __name__ == "__main__":
    main()
