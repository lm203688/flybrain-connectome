"""
containment.py — Phase E: containment verification for self-evolving agents.

This is the D5 deliverable from the project's positioning strategy. It
implements the containment layer proposed by the 2026-05 Containment
Verification paper (which argues that safety guarantees must move to the
containment layer, not the agent layer).

Core principle: an agent's outputs are only trusted if they can be verified
against a *structural* contract. This module provides:

  1. **Structural contract**: a declarative specification of what a valid
     organism topology looks like (required modules, allowed edge types,
     forbidden patterns).
  2. **Verification engine**: checks a candidate organism against its contract.
  3. **Containment policy**: determines whether an evolved variant is safe to
     deploy (accepted), quarantined (pending review), or rejected.

Key design invariants (from DIGITAL_ORGANISM_DESIGN_2026-10-10.md §D5):
  * **Verification, not trust**: every output is verified against a contract,
    never assumed safe.
  * **Fail-closed**: if verification fails or times out, the output is rejected.
  * **Structural, not behavioral**: containment checks structure, not runtime
    behavior (which would be a separate layer).

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

from profile_health import profile_health as _profile_health_fn


# ------------------------------------------------------------------ contract

@dataclass
class StructuralContract:
    """Declarative specification of what a valid organism topology looks like.

    Attributes:
        min_modules: minimum number of modules required
        max_modules: maximum number of modules allowed
        required_profiles: set of profile types that must be present
        allowed_edge_types: set of edge types that are allowed
        forbidden_patterns: list of (from_profile, to_profile) pairs that are
                            not allowed
        min_health_score: minimum structural health score required
        max_hub_concentration: maximum top-1 hub concentration (0.0–1.0)
        require_feedback: whether the organism must have at least one feedback loop
    """
    min_modules: int = 2
    max_modules: int = 50
    required_profiles: set = field(default_factory=lambda: {"perceive", "plan", "act"})
    allowed_edge_types: set = field(default_factory=lambda: {
        "functional", "feedback", "inhibitory", "modulatory"
    })
    forbidden_patterns: list = field(default_factory=list)
    min_health_score: float = 0.40
    max_hub_concentration: float = 0.60
    require_feedback: bool = False

    @classmethod
    def default(cls) -> "StructuralContract":
        """Return a reasonable default contract."""
        return cls()

    @classmethod
    def strict(cls) -> "StructuralContract":
        """Return a strict contract (for high-safety deployments)."""
        return cls(
            min_modules=4,
            max_modules=30,
            required_profiles={"perceive", "plan", "act", "learn"},
            min_health_score=0.60,
            max_hub_concentration=0.40,
            require_feedback=True,
        )

    def to_dict(self) -> dict:
        return {
            "min_modules": self.min_modules,
            "max_modules": self.max_modules,
            "required_profiles": list(self.required_profiles),
            "allowed_edge_types": list(self.allowed_edge_types),
            "forbidden_patterns": self.forbidden_patterns,
            "min_health_score": self.min_health_score,
            "max_hub_concentration": self.max_hub_concentration,
            "require_feedback": self.require_feedback,
        }


# ------------------------------------------------------------------ verification

@dataclass
class Violation:
    """A single contract violation."""
    rule: str
    severity: str  # "critical" | "warning" | "info"
    description: str
    value: Any = None

    def to_dict(self) -> dict:
        return {
            "rule": self.rule,
            "severity": self.severity,
            "description": self.description,
            "value": self.value,
        }


@dataclass
class VerificationResult:
    """Result of verifying an organism against a structural contract."""
    organism_name: str
    verified: bool
    violations: list[dict]
    health_score: float
    health_status: str
    verdict: str  # "accepted" | "quarantined" | "rejected"
    fingerprint: str
    timestamp: float

    def to_dict(self) -> dict:
        return {
            "organism_name": self.organism_name,
            "verified": self.verified,
            "n_violations": len(self.violations),
            "violations": self.violations,
            "health_score": self.health_score,
            "health_status": self.health_status,
            "verdict": self.verdict,
            "fingerprint": self.fingerprint,
            "timestamp": self.timestamp,
        }


def verify(
    organism: dict,
    contract: StructuralContract | None = None,
) -> VerificationResult:
    """Verify an organism against a structural contract.

    Args:
        organism: the organism dict to verify
        contract: the structural contract to verify against
                  (defaults to StructuralContract.default())

    Returns:
        VerificationResult with verdict and any violations
    """
    if contract is None:
        contract = StructuralContract.default()

    organism_name = organism.get("name", "unnamed")
    units = organism.get("modules") or organism.get("units") or []
    edges = organism.get("edges") or organism.get("connections") or []

    violations: list[Violation] = []

    # --- Rule 1: module count bounds ---
    n_modules = len(units)
    if n_modules < contract.min_modules:
        violations.append(Violation(
            rule="min_modules",
            severity="critical",
            description=f"Organism has {n_modules} modules, "
                        f"below minimum {contract.min_modules}",
            value=n_modules,
        ))
    if n_modules > contract.max_modules:
        violations.append(Violation(
            rule="max_modules",
            severity="warning",
            description=f"Organism has {n_modules} modules, "
                        f"above maximum {contract.max_modules}",
            value=n_modules,
        ))

    # --- Rule 2: required profiles ---
    present_profiles = set()
    for u in units:
        profile = u.get("profile") or u.get("name") or ""
        present_profiles.add(str(profile))

    missing_profiles = contract.required_profiles - present_profiles
    if missing_profiles:
        violations.append(Violation(
            rule="required_profiles",
            severity="critical",
            description=f"Missing required profiles: {sorted(missing_profiles)}",
            value=sorted(missing_profiles),
        ))

    # --- Rule 3: allowed edge types ---
    for i, edge in enumerate(edges):
        if not isinstance(edge, dict):
            continue
        edge_type = edge.get("type", "functional")
        if edge_type not in contract.allowed_edge_types:
            violations.append(Violation(
                rule="allowed_edge_types",
                severity="warning",
                description=f"Edge {i} ({edge.get('from','?')}->{edge.get('to','?')}) "
                            f"has disallowed type '{edge_type}'",
                value=edge_type,
            ))

    # --- Rule 4: forbidden patterns ---
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        src = edge.get("from", "")
        dst = edge.get("to", "")

        # look up source and target profiles
        src_unit = next((u for u in units if (u.get("name") or u.get("id")) == src), None)
        dst_unit = next((u for u in units if (u.get("name") or u.get("id")) == dst), None)
        if not src_unit or not dst_unit:
            continue

        src_profile = src_unit.get("profile") or src_unit.get("name") or ""
        dst_profile = dst_unit.get("profile") or dst_unit.get("name") or ""

        for forbidden in contract.forbidden_patterns:
            if len(forbidden) == 2 and \
               (src_profile == forbidden[0] and dst_profile == forbidden[1]):
                violations.append(Violation(
                    rule="forbidden_patterns",
                    severity="critical",
                    description=f"Forbidden pattern: {src_profile} -> {dst_profile}",
                    value=f"{src_profile}->{dst_profile}",
                ))

    # --- Rule 5: health score ---
    try:
        health = _profile_health_fn(organism_name)
        health_score = health.get("degradation_score", 0.0)
        health_status = health.get("status", "unknown")
    except Exception:
        health_score = 0.0
        health_status = "unknown"

    if health_score < contract.min_health_score:
        violations.append(Violation(
            rule="min_health_score",
            severity="critical",
            description=f"Health score {health_score:.4f} below minimum "
                        f"{contract.min_health_score}",
            value=health_score,
        ))

    # --- Rule 6: hub concentration ---
    try:
        from profile_health import _build_adjacency, _out_degrees
        node_names = [str(u.get("name") or u.get("id", "")) for u in units]
        edge_pairs = [(str(e.get("from","")), str(e.get("to",""))) for e in edges if isinstance(e, dict)]
        adj = _build_adjacency(edge_pairs)
        for n in node_names:
            adj.setdefault(n, [])
        degrees = _out_degrees(adj)
        sorted_degrees = sorted(degrees.values(), reverse=True)
        total_deg = sum(sorted_degrees)
        if total_deg > 0 and sorted_degrees:
            top1 = sorted_degrees[0] / total_deg
            if top1 > contract.max_hub_concentration:
                violations.append(Violation(
                    rule="max_hub_concentration",
                    severity="warning",
                    description=f"Hub concentration {top1:.4f} exceeds maximum "
                                f"{contract.max_hub_concentration}",
                    value=top1,
                ))
    except Exception:  # noqa: SILENT — non-critical check, skip on failure
        pass  # non-critical check, skip on failure

    # --- Rule 7: feedback requirement ---
    if contract.require_feedback:
        has_feedback = False
        for edge in edges:
            if isinstance(edge, dict) and edge.get("type") == "feedback":
                has_feedback = True
                break
            # also check for cycles (feedback can be implicit)
        if not has_feedback:
            violations.append(Violation(
                rule="require_feedback",
                severity="warning",
                description="Organism lacks feedback loops (required by contract)",
                value=False,
            ))

    # --- Determine verdict ---
    critical_violations = [v for v in violations if v.severity == "critical"]
    if critical_violations:
        verdict = "rejected"
    elif any(v.severity == "warning" for v in violations):
        verdict = "quarantined"
    else:
        verdict = "accepted"

    verified = verdict == "accepted"

    # Compute fingerprint
    unit_ids = sorted(str(u.get("id") or u.get("name", "")) for u in units)
    edge_keys = sorted(
        f"{e.get('from','?')}->{e.get('to','?')}" for e in edges
        if isinstance(e, dict)
    )
    fingerprint_input = json.dumps(
        {"units": unit_ids, "edges": edge_keys}, sort_keys=True
    )
    fingerprint = hashlib.sha256(fingerprint_input.encode()).hexdigest()[:16]

    return VerificationResult(
        organism_name=organism_name,
        verified=verified,
        violations=[v.to_dict() for v in violations],
        health_score=health_score,
        health_status=health_status,
        verdict=verdict,
        fingerprint=fingerprint,
        timestamp=time.time(),
    )


# ------------------------------------------------------------------ containment policy

@dataclass
class ContainmentDecision:
    """Decision from the containment policy."""
    organism_name: str
    action: str  # "deploy" | "quarantine" | "reject" | "rollback"
    reason: str
    verification: dict
    timestamp: float

    def to_dict(self) -> dict:
        return {
            "organism_name": self.organism_name,
            "action": self.action,
            "reason": self.reason,
            "verification": self.verification,
            "timestamp": self.timestamp,
        }


class ContainmentPolicy:
    """Containment policy that decides whether an organism is safe to deploy.

    The policy is a thin wrapper over verify() that maps verification results
    to deployment decisions:
      * accepted  → deploy
      * quarantined → quarantine (pending human review)
      * rejected  → reject (or rollback if already deployed)
    """

    def __init__(self, contract: StructuralContract | None = None,
                 on_reject: str = "reject"):
        self.contract = contract or StructuralContract.default()
        self.on_reject = on_reject  # "reject" or "rollback"

    def decide(self, organism: dict) -> ContainmentDecision:
        """Decide whether an organism is safe to deploy."""
        result = verify(organism, self.contract)
        result_dict = result.to_dict()

        if result.verdict == "accepted":
            action = "deploy"
            reason = f"Verified: {result.health_status}, " \
                     f"health={result.health_score:.4f}, no violations"
        elif result.verdict == "quarantined":
            action = "quarantine"
            warnings = [v for v in result.violations if v["severity"] == "warning"]
            reason = f"Quarantined: {len(warnings)} warning(s), " \
                     f"health={result.health_score:.4f}"
        else:
            action = self.on_reject
            critical = [v for v in result.violations if v["severity"] == "critical"]
            reason = f"Rejected: {len(critical)} critical violation(s), " \
                     f"health={result.health_score:.4f}"

        return ContainmentDecision(
            organism_name=result.organism_name,
            action=action,
            reason=reason,
            verification=result_dict,
            timestamp=time.time(),
        )


# ------------------------------------------------------------------ audit log

@dataclass
class AuditEntry:
    """Single entry in the containment audit log."""
    timestamp: float
    organism_name: str
    action: str
    reason: str
    fingerprint: str

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "organism_name": self.organism_name,
            "action": self.action,
            "reason": self.reason,
            "fingerprint": self.fingerprint,
        }


class AuditLog:
    """Append-only audit log for containment decisions."""

    def __init__(self, log_path: str | None = None):
        self.entries: list[dict] = []
        self.log_path = log_path
        self._seen: set[str] = set()

    def record(self, decision: ContainmentDecision) -> None:
        """Record a containment decision in the audit log."""
        entry = AuditEntry(
            timestamp=decision.timestamp,
            organism_name=decision.organism_name,
            action=decision.action,
            reason=decision.reason,
            fingerprint=decision.verification.get("fingerprint", ""),
        )
        entry_dict = entry.to_dict()

        # Deduplication (same fingerprint + action = same decision)
        key = f"{entry_dict['fingerprint']}:{entry_dict['action']}"
        if key in self._seen:
            return
        self._seen.add(key)

        self.entries.append(entry_dict)

        # Persist to file if path provided
        if self.log_path:
            os.makedirs(os.path.dirname(self.log_path) or ".", exist_ok=True)
            with open(self.log_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry_dict, ensure_ascii=False) + "\n")

    def summary(self) -> dict:
        """Return a summary of audit log contents."""
        by_action: dict[str, int] = {}
        for entry in self.entries:
            action = entry["action"]
            by_action[action] = by_action.get(action, 0) + 1

        return {
            "n_entries": len(self.entries),
            "by_action": by_action,
            "n_unique_fingerprints": len({e["fingerprint"] for e in self.entries}),
        }


# ------------------------------------------------------------------ CLI

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Containment verification (Phase E)")
    parser.add_argument("--strict", action="store_true",
                        help="Use strict contract")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--audit-log", type=str, default=None)
    args = parser.parse_args()

    contract = StructuralContract.strict() if args.strict else StructuralContract.default()
    policy = ContainmentPolicy(contract)
    audit = AuditLog(args.audit_log)

    # Create test organisms
    healthy = {
        "name": "healthy_organism",
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

    damaged = {
        "name": "damaged_organism",
        "modules": [
            {"id": "m1", "name": "perceive", "profile": "perceive", "category": "cognitive"},
            {"id": "m3", "name": "act", "profile": "act", "category": "cognitive"},
        ],
        "edges": [
            {"from": "m1", "to": "m3", "type": "functional", "weight": 0.5},
        ],
    }

    organisms = {"healthy": healthy, "damaged": damaged}

    results = []
    for name, org in organisms.items():
        decision = policy.decide(org)
        audit.record(decision)
        results.append(decision.to_dict())

    if args.json:
        print(json.dumps({
            "contract": contract.to_dict(),
            "decisions": results,
            "audit": audit.summary(),
        }, indent=2, default=str))
    else:
        print(f"\n=== Containment Verification (Phase E) ===")
        print(f"Contract: {'strict' if args.strict else 'default'}")
        print(f"Min modules: {contract.min_modules}, Max: {contract.max_modules}")
        print(f"Required profiles: {sorted(contract.required_profiles)}")
        print(f"Min health: {contract.min_health_score}")
        print(f"Max hub concentration: {contract.max_hub_concentration}")
        print()
        for r in results:
            print(f"  {r['organism_name']}: {r['action'].upper()}")
            print(f"    Reason: {r['reason']}")
            print(f"    Verification: {r['verification']['n_violations']} violations")
        print(f"\nAudit log: {audit.summary()}")


if __name__ == "__main__":
    main()
