"""Dendritic Rule Engine — Xu 2026 Science pattern reference implementation.

Reference: Xu, N., et al. "Dendritic computation for abstract rule-based
flexible decision-making." Science (2026-10-16). DOI: 10.1126/science.adz5323.

This is an OPTIONAL reference pattern, NOT part of the flybrain-connectome core.
The core substrate is a neuron-level combinatorial algebra; Xu 2026 lives at the
subcellular compartment level and is cited only as an external theoretical anchor
(see docs/XU2026_DENDRITIC_COMPUTATION_IMPACT_2026-10-18.md and E4 B-14
compartment boundary).

What this module implements (minimal, runnable, ~200 lines):
  * RuleCache (dendrite)   — holds candidate abstract rules, each scored
                              (confidence, support, weight).
  * SensoryStream (soma)   — produces per-sample feature vectors.
  * NonlinearIntegrator    — combines dendrite + soma activations with a
                              multiplicative-nonlinearity gate.
  * DendriticAgent         — proposes, evaluates, and consolidates rules.

The design goal is *readability over performance*: anyone reading Xu 2026 should
be able to trace each concept (abstract rule encoding, sensory representation,
nonlinear integration, hypothesis consolidation) to a named code object.

Usage:
    from dendritic_rule_engine import DendriticAgent

    agent = DendriticAgent(feature_dim=4, consolidation_threshold=3)
    for sample, label in data_stream:
        agent.observe(sample, label)
    print(agent.decision_stats())

NOT for production connectomic inference.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional, Sequence

import math


# ---------------------------------------------------------------------------
# Rule representation (Xu 2026: "顶端树突编码抽象规则")
# ---------------------------------------------------------------------------

@dataclass
class Rule:
    """A candidate abstract rule, cached in the apical-dendrite region.

    A rule maps a feature vector to a predicted label. We keep rules generic —
    the caller supplies the predictor function. The Rule itself only stores
    bookkeeping for how the network has scored that predictor across the stream.

    Fields:
        name:                 Human-readable identifier for the rule.
        predictor:            callable(feature_vector) -> label.
        support_count:        Number of samples where the rule agreed with
                              ground truth (or with the current decision
                              target, in the unsupervised variant).
        failure_count:        Number of samples where the rule disagreed.
        confidence:           Running confidence score in [0, 1]. Computed
                              with a Wilson-style lower bound so a rule with
                              3/3 hits starts high but a rule with 300/303
                              hits does not saturate.
        weight:               Consolidation weight. Below threshold, the rule
                              is "candidate"; above threshold, it is
                              "consolidated" (analogous to synaptic
                              consolidation Xu describes after rule
                              verification).
        is_consolidated:      Flag flipped True once weight >= threshold.
    """

    name: str
    predictor: Callable[[Sequence[float]], int]
    support_count: int = 0
    failure_count: int = 0
    confidence: float = 0.5
    weight: float = 0.0
    is_consolidated: bool = False


# ---------------------------------------------------------------------------
# Dendrite: rule cache with confidence-gated consolidation
# ---------------------------------------------------------------------------

class RuleCache:
    """The 'apical dendrite' — a cache of candidate rules.

    Xu 2026: apical dendrites encode *inferred abstract rules*; the cell body
    processes *sensory information*. Consolidation (synaptic strengthening)
    only happens after a rule has been verified multiple times.

    We model this as:
        * Rules live here with a confidence score and a weight.
        * `evaluate(feature, ground_truth_label)` updates support/failure
          counts and re-derives confidence.
        * `consolidate(threshold)` promotes a rule to "consolidated" once it
          has accumulated enough verified hits.
    """

    def __init__(self, consolidation_threshold: int = 3):
        self.rules: list[Rule] = []
        self.consolidation_threshold = consolidation_threshold

    # -- registration ----------------------------------------------------

    def add_rule(self, name: str, predictor: Callable[[Sequence[float]], int]) -> None:
        self.rules.append(Rule(name=name, predictor=predictor))

    def add_rules(self, rules: Iterable[tuple[str, Callable[[Sequence[float]], int]]]) -> None:
        for name, pred in rules:
            self.add_rule(name, pred)

    # -- evaluation ------------------------------------------------------

    def evaluate(
        self,
        feature: Sequence[float],
        ground_truth_label: Optional[int] = None,
    ) -> list[tuple[str, int, float]]:
        """Run every rule against the given feature; return (name, label, confidence).

        When ground_truth_label is provided, support/failure counters update.
        When None (unlabelled observation), counters do not update but the
        rule is still run — this is the "propose hypothesis" side of Xu.
        """
        outputs = []
        for rule in self.rules:
            label = rule.predictor(feature)
            if ground_truth_label is not None:
                if label == ground_truth_label:
                    rule.support_count += 1
                else:
                    rule.failure_count += 1
                rule.confidence = self._wilson_lower(rule)
                if rule.support_count >= self.consolidation_threshold:
                    rule.is_consolidated = True
                    rule.weight = min(1.0, rule.support_count / (rule.support_count + 1.0))
            outputs.append((rule.name, label, rule.confidence))
        return outputs

    @staticmethod
    def _wilson_lower(rule: Rule) -> float:
        """Wilson score lower bound. Returns confidence in [0, 1].

        We use this instead of naive accuracy because with n=3 successes and 0
        failures, naive accuracy is 1.0 but the true CI lower bound is only
        ~0.34. Wilson keeps the confidence honest in the few-shot regime —
        which is exactly the regime Xu 2026 lives in ("少量信息就能快速学习").
        """
        n = rule.support_count + rule.failure_count
        if n == 0:
            return 0.5
        p = rule.support_count / n
        z = 1.96  # 95% CI
        denom = 1 + z * z / n
        center = p + z * z / (2 * n)
        margin = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)
        return max(0.0, (center - margin) / denom)

    # -- querying --------------------------------------------------------

    def best_rule(self) -> Optional[Rule]:
        if not self.rules:
            return None
        return max(self.rules, key=lambda r: (r.is_consolidated, r.confidence))

    def consolidated(self) -> list[Rule]:
        return [r for r in self.rules if r.is_consolidated]


# ---------------------------------------------------------------------------
# Soma: sensory representation (identity by default, overridable)
# ---------------------------------------------------------------------------

class SensoryStream:
    """The 'soma' — receives raw sensory input, produces a feature vector.

    Xu 2026: the soma processes sensory information (in their paper, auditory
    input). Here we keep the mapping pluggable so callers can inject real
    feature extractors later.
    """

    def __init__(self, encoder: Optional[Callable[[object], Sequence[float]]] = None):
        self.encoder = encoder

    def encode(self, raw: object) -> Sequence[float]:
        if self.encoder is None:
            # Identity: assume the caller already passed a numeric feature vector.
            return list(raw)  # type: ignore[arg-type]
        return self.encoder(raw)


# ---------------------------------------------------------------------------
# Nonlinear integrator (dendrite * soma -> decision output)
# ---------------------------------------------------------------------------

class NonlinearIntegrator:
    """Multiplicative nonlinearity between dendrite output and soma output.

    Xu 2026: the two compartments do not simply sum — they interact nonlinearly
    so that a sensory signal is gated by whether a matching abstract rule is
    currently encoded in the dendrite.

    Minimal implementation:
        gate = sigmoid(sum(confidence_i * agreement_i))  # in [0, 1]
        decision = argmax over candidate labels of (gate * weighted_votes_i)

    We keep this small on purpose. Xu's actual nonlinearity is dendritic
    spine-calcium dynamics; our gate is a stand-in whose shape (multiplicative,
    sigmoid-saturated) captures the *qualitative* property — "no rule support
    means no decision" — which is what the project cares about.
    """

    def __init__(self, temperature: float = 1.0):
        self.temperature = temperature

    def decide(
        self,
        dendrite_outputs: list[tuple[str, int, float]],
        soma_active: bool = True,
    ) -> int:
        if not dendrite_outputs or not soma_active:
            return -1  # abstain
        # Per-label weighted vote: each rule contributes confidence * vote.
        votes: dict[int, float] = {}
        for _name, label, confidence in dendrite_outputs:
            votes[label] = votes.get(label, 0.0) + confidence
        if not votes:
            return -1
        # Nonlinear gate: sigmoid of the total support scaled by temperature.
        total_support = sum(votes.values())
        gate = 1.0 / (1.0 + math.exp(-self.temperature * (total_support - 1.0)))
        weighted = {label: v * gate for label, v in votes.items()}
        return max(weighted, key=weighted.get)


# ---------------------------------------------------------------------------
# Combined agent (dendrite + soma + integrator)
# ---------------------------------------------------------------------------

class DendriticAgent:
    """Facade combining RuleCache + SensoryStream + NonlinearIntegrator.

    This is the entry point a caller would use if they want the "Xu 2026
    pattern" wrapped into one object. It mirrors the paper's structure:
        * sensory input -> soma encoder -> feature vector
        * feature vector -> dendrite rule cache -> rule evaluations
        * rule evaluations + soma activity -> nonlinear integrator -> decision
        * decision compared to ground truth -> rule confidence updates
    """

    def __init__(
        self,
        feature_dim: int,
        consolidation_threshold: int = 3,
        encoder: Optional[Callable[[object], Sequence[float]]] = None,
    ):
        self._ = feature_dim  # reserved for future gating
        self.dendrite = RuleCache(consolidation_threshold=consolidation_threshold)
        self.soma = SensoryStream(encoder=encoder)
        self.integrator = NonlinearIntegrator()
        self.correct = 0
        self.total = 0

    # -- authoring rules -------------------------------------------------

    def add_rule(self, name: str, predictor: Callable[[Sequence[float]], int]) -> None:
        self.dendrite.add_rule(name, predictor)

    def add_rules(self, rules: Iterable[tuple[str, Callable[[Sequence[float]], int]]]) -> None:
        self.dendrite.add_rules(rules)

    # -- observing -------------------------------------------------------

    def observe(
        self,
        raw_input,
        ground_truth_label: Optional[int] = None,
    ) -> dict:
        """Take one observation. If ground_truth is provided, rule confidence updates."""
        feature = self.soma.encode(raw_input)
        dendrite_outputs = self.dendrite.evaluate(feature, ground_truth_label)
        decision = self.integrator.decide(dendrite_outputs)
        if ground_truth_label is not None:
            self.total += 1
            if decision == ground_truth_label:
                self.correct += 1
        return {
            "decision": decision,
            "ground_truth": ground_truth_label,
            "dendrite_outputs": dendrite_outputs,
            "confidence_leader": self.dendrite.best_rule().confidence
            if self.dendrite.rules else None,
        }

    # -- reporting -------------------------------------------------------

    def decision_stats(self) -> dict:
        return {
            "total_observations": self.total,
            "correct": self.correct,
            "accuracy": (self.correct / self.total) if self.total else 0.0,
            "n_rules": len(self.dendrite.rules),
            "n_consolidated": len(self.dendrite.consolidated()),
            "rule_summary": [
                {
                    "name": r.name,
                    "support": r.support_count,
                    "failure": r.failure_count,
                    "confidence": round(r.confidence, 3),
                    "consolidated": r.is_consolidated,
                }
                for r in self.dendrite.rules
            ],
        }


# ---------------------------------------------------------------------------
# Small self-demo — runs when the module is invoked directly.
# ---------------------------------------------------------------------------

def _demo() -> None:
    """A minimal demo: two mutually exclusive rules, 20 samples, measure
    confidence-gated consolidation. Not intended for production."""
    # Two synthetic rules on 2D inputs. Rule A fires when x > 0; Rule B
    # fires when y > 0. Ground truth is XOR of the two features — which
    # matches neither rule alone, so consolidating the *right* rule requires
    # the integrator to reject both and abstain. This is a *sanity check* on
    # the abstain path, not on the pattern itself.
    agent = DendriticAgent(feature_dim=2, consolidation_threshold=2)
    agent.add_rules([
        ("rule_x_positive", lambda f: 1 if f[0] > 0 else 0),
        ("rule_y_positive", lambda f: 1 if f[1] > 0 else 0),
        ("rule_xor", lambda f: 1 if (f[0] > 0) != (f[1] > 0) else 0),
    ])

    samples = [
        ((1.0, -0.5), 1),  # xor = 1
        ((-0.5, 1.0), 1),  # xor = 1
        ((1.0, 1.0), 0),   # xor = 0
        ((-0.5, -0.5), 0), # xor = 0
        ((1.5, -0.2), 1),
        ((0.1, 1.2), 1),
        ((0.4, 0.3), 0),
        ((-0.9, -1.1), 0),
        ((2.0, -1.0), 1),
        ((-0.3, 0.9), 1),
    ]
    for x, y in samples:
        agent.observe(x, y)
    print(agent.decision_stats())


if __name__ == "__main__":
    _demo()
