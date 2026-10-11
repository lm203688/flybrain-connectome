"""
Gate 34 — Fusion B two-stage LLM pipeline correctness.

Checks (all stdlib, zero tokens burned):
  1. TwoStageLLMBackend implements LLMBackend protocol
  2. answer_confidence_score returns correct values on canonical cases
  3. High-confidence cheap answer → returned directly, no escalation
  4. Low-confidence cheap answer → escalated to strong, strong wins
  5. Empty / hedge cheap answer → escalated
  6. Stats counter is accurate (cheap_calls, strong_calls, escalations, cheap_hits)
  7. Cheap-hit rate / escalation rate properties are consistent
  8. min_confidence boundary conditions (0.0 accepts all; 1.0 escalates all)
  9. The two-stage backend works transparently with all 4 orchestrators
 10. Injected-defect tests (4)

Exit 0 = PASS. Exit 1 = FAIL (any assertion).

Discipline per OPEN_SOURCE_FUSION §4 Fusion B:
  * The two-stage backend is a routing layer, not a judgement layer.
  * It must NEVER downgrade a strong answer into a cheap one.
  * Escalation is always to the strong model — never silent-drop.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "flybrain-connectome-mcp"))

from llm_orchestrator import (  # noqa: E402
    TwoStageLLMBackend,
    answer_confidence_score,
    StubLLM,
    ORCHESTRATORS,
    get_orchestrator,
)


# ============================================================= checks


def _check_1_protocol() -> list[str]:
    """TwoStageLLMBackend must implement LLMBackend.chat() -> str."""
    errs: list[str] = []
    cheap = StubLLM([], default_response="answer")
    strong = StubLLM([], default_response="answer")
    backend = TwoStageLLMBackend(cheap, strong, min_confidence=0.5)
    out = backend.chat("sys", "user")
    if not isinstance(out, str):
        errs.append(f"chat() must return str, got {type(out).__name__}")
    if not hasattr(backend, "chat") or not hasattr(backend, "stats"):
        errs.append("backend must expose chat() and .stats")
    return errs


def _check_2_confidence_score() -> list[str]:
    """answer_confidence_score canonical values."""
    errs: list[str] = []
    cases = [
        ("", 0.0),
        ("   ", 0.0),
        ("hub", 1.0),
        ("inhibitory_hub", 1.0),
        ("7", 1.0),
        ("-1", 1.0),
        ("I don't know", 0.0),
        ("unknown", 0.0),
        ("not sure", 0.0),
        ("i'm not sure", 0.0),
        ("cannot determine", 0.0),
        ("This is a moderately detailed answer of about 250 chars that "
         "does not contain hedging but is too long to count as a clean "
         "short token, so it should be classified as medium confidence "
         "since the length exceeds 40 chars and there is no hedge.", 0.5),
    ]
    for text, expected in cases:
        got = answer_confidence_score(text)
        if got != expected:
            errs.append(
                f"confidence({text[:40]!r}...) = {got} expected {expected}"
            )
    return errs


def _check_3_high_confidence_no_escalation() -> list[str]:
    """Cheap answer that is high-confidence → returned as-is."""
    errs: list[str] = []
    cheap = StubLLM([], default_response="hub_x")
    strong = StubLLM([], default_response="hub_strong")
    backend = TwoStageLLMBackend(cheap, strong, min_confidence=0.5)
    out = backend.chat("sys", "Which is the hub?")
    if out != "hub_x":
        errs.append(f"expected cheap answer 'hub_x', got {out!r}")
    if backend.stats["escalations"] != 0:
        errs.append(f"expected 0 escalations, got {backend.stats['escalations']}")
    if backend.stats["strong_calls"] != 0:
        errs.append("strong backend should not have been called")
    return errs


def _check_4_low_confidence_escalates() -> list[str]:
    """Cheap answer is a hedge → escalate, strong wins."""
    errs: list[str] = []
    cheap = StubLLM([], default_response="I don't know")
    strong = StubLLM([], default_response="hub_strong")
    backend = TwoStageLLMBackend(cheap, strong, min_confidence=0.5)
    out = backend.chat("sys", "Which is the hub?")
    if out != "hub_strong":
        errs.append(f"expected strong answer 'hub_strong', got {out!r}")
    if backend.stats["escalations"] != 1:
        errs.append(f"expected 1 escalation, got {backend.stats['escalations']}")
    if backend.stats["strong_calls"] != 1:
        errs.append(f"expected 1 strong call, got {backend.stats['strong_calls']}")
    return errs


def _check_5_empty_escalates() -> list[str]:
    """Empty cheap answer → escalate."""
    errs: list[str] = []
    cheap = StubLLM([], default_response="")
    strong = StubLLM([], default_response="hub_strong")
    backend = TwoStageLLMBackend(cheap, strong, min_confidence=0.5)
    out = backend.chat("sys", "Which is the hub?")
    if out != "hub_strong":
        errs.append(f"expected strong answer, got {out!r}")
    if backend.stats["escalations"] != 1:
        errs.append(f"expected 1 escalation, got {backend.stats['escalations']}")
    return errs


def _check_6_stats_counter() -> list[str]:
    """Stats counters are exact."""
    errs: list[str] = []
    cheap = StubLLM([], default_response="ok")
    strong = StubLLM([], default_response="ok_strong")
    backend = TwoStageLLMBackend(cheap, strong, min_confidence=0.5)
    # 5 cheap hits (no escalation)
    for _ in range(5):
        backend.chat("sys", "q")
    # then switch cheap to a hedger
    cheap_hedge = StubLLM([], default_response="unknown")
    backend.cheap = cheap_hedge
    # 3 escalations
    for _ in range(3):
        backend.chat("sys", "q")
    if backend.stats["cheap_calls"] != 8:
        errs.append(f"cheap_calls should be 8, got {backend.stats['cheap_calls']}")
    if backend.stats["strong_calls"] != 3:
        errs.append(f"strong_calls should be 3, got {backend.stats['strong_calls']}")
    if backend.stats["escalations"] != 3:
        errs.append(f"escalations should be 3, got {backend.stats['escalations']}")
    if backend.stats["cheap_hits"] != 5:
        errs.append(f"cheap_hits should be 5, got {backend.stats['cheap_hits']}")
    if backend.stats["total_calls"] != 8:
        errs.append(f"total_calls should be 8, got {backend.stats['total_calls']}")
    return errs


def _check_7_rate_properties() -> list[str]:
    """cheap_hit_rate + escalation_rate sum to 1 when no other path."""
    errs: list[str] = []
    cheap = StubLLM([], default_response="ok")
    strong = StubLLM([], default_response="ok")
    backend = TwoStageLLMBackend(cheap, strong, min_confidence=0.5)
    for _ in range(10):
        backend.chat("s", "u")
    if abs(backend.cheap_hit_rate - 1.0) > 1e-9:
        errs.append(f"cheap_hit_rate should be 1.0, got {backend.cheap_hit_rate}")
    if abs(backend.escalation_rate - 0.0) > 1e-9:
        errs.append(f"escalation_rate should be 0.0, got {backend.escalation_rate}")
    # Now make cheap always hedge
    backend.cheap = StubLLM([], default_response="unknown")
    for _ in range(5):
        backend.chat("s", "u")
    # After 15 total: 10 hits + 5 escalations
    expected_cheap = 10 / 15
    expected_esc = 5 / 15
    if abs(backend.cheap_hit_rate - expected_cheap) > 1e-9:
        errs.append(f"cheap_hit_rate expected {expected_cheap}, got {backend.cheap_hit_rate}")
    if abs(backend.escalation_rate - expected_esc) > 1e-9:
        errs.append(f"escalation_rate expected {expected_esc}, got {backend.escalation_rate}")
    return errs


def _check_8_min_confidence_boundaries() -> list[str]:
    """min_confidence=0.0 accepts all cheap; =1.0 requires perfect."""
    errs: list[str] = []
    # min_confidence=0.0: everything is accepted (score >= 0 always true)
    cheap = StubLLM([], default_response="I don't know")
    strong = StubLLM([], default_response="strong")
    backend = TwoStageLLMBackend(cheap, strong, min_confidence=0.0)
    out = backend.chat("s", "u")
    if out != "I don't know":
        errs.append("min_confidence=0.0 must accept hedged cheap answer")
    if backend.stats["escalations"] != 0:
        errs.append("min_confidence=0.0 must not escalate")
    # min_confidence=1.0: only perfect short clean answers accepted
    cheap_ok = StubLLM([], default_response="hub")
    backend2 = TwoStageLLMBackend(cheap_ok, strong, min_confidence=1.0)
    out2 = backend2.chat("s", "u")
    if out2 != "hub":
        errs.append("min_confidence=1.0 must accept clean short token")
    if backend2.stats["escalations"] != 0:
        errs.append("min_confidence=1.0 must accept clean short token without escalation")
    # medium confidence answer at min_confidence=1.0 must escalate
    cheap_medium = StubLLM([], default_response="A longish answer that is over "
                                                "40 chars so it counts as medium "
                                                "confidence and requires escalation.")
    backend3 = TwoStageLLMBackend(cheap_medium, strong, min_confidence=1.0)
    out3 = backend3.chat("s", "u")
    if out3 != "strong":
        errs.append("min_confidence=1.0 must escalate medium-confidence answer")
    return errs


def _check_9_works_with_all_topologies() -> list[str]:
    """TwoStage backend must be transparent to all 4 orchestrators."""
    errs: list[str] = []
    # Stub returns "hub" for any prompt (high confidence, no escalation)
    cheap = StubLLM([], default_response="hub")
    strong = StubLLM([], default_response="hub")
    backend = TwoStageLLMBackend(cheap, strong, min_confidence=0.5)
    for tname in ("sequential", "fan_out", "hierarchical", "router"):
        orch = get_orchestrator(tname, backend, evidence=None)
        ans = orch.run("Which is the hub?")
        if ans.text != "hub":
            errs.append(f"{tname}: expected 'hub', got {ans.text!r}")
    return errs


def _check_10_no_silent_downgrade() -> list[str]:
    """Escalation must NEVER silently downgrade — strong always wins."""
    errs: list[str] = []
    # Cheap gives a hedge, strong gives the real answer
    cheap = StubLLM([], default_response="unknown")
    strong = StubLLM([], default_response="inhibitory_hub")
    backend = TwoStageLLMBackend(cheap, strong, min_confidence=0.5)
    out = backend.chat("s", "u")
    if out != "inhibitory_hub":
        errs.append(f"expected strong answer, got {out!r}")
    # The cheap answer must NEVER leak through after escalation
    if "unknown" in out or "don't know" in out.lower():
        errs.append("cheap hedge leaked through escalation")
    return errs


# ============================================================= injected defects

def _inject_defect_min_confidence_out_of_range() -> list[str]:
    """min_confidence > 1.0 must raise ValueError."""
    errs: list[str] = []
    cheap = StubLLM([], default_response="x")
    strong = StubLLM([], default_response="x")
    try:
        TwoStageLLMBackend(cheap, strong, min_confidence=1.5)
        errs.append("min_confidence=1.5 must raise ValueError")
    except ValueError:
        pass  # expected
    try:
        TwoStageLLMBackend(cheap, strong, min_confidence=-0.1)
        errs.append("min_confidence=-0.1 must raise ValueError")
    except ValueError:
        pass
    return errs


def _inject_defect_weak_escalation() -> list[str]:
    """TwoStage must ALWAYS escalate on low confidence, never guess."""
    errs: list[str] = []
    cheap = StubLLM([], default_response="I don't know")
    strong = StubLLM([], default_response="real_answer")
    backend = TwoStageLLMBackend(cheap, strong, min_confidence=0.5)
    out = backend.chat("s", "u")
    # If the backend ever returned the cheap answer despite escalation
    # being needed, this fails
    if out == "I don't know":
        errs.append("backend must not return hedged cheap answer on low confidence")
    return errs


def _inject_defect_stats_drift() -> list[str]:
    """Stats must be exact — no silent drift."""
    errs: list[str] = []
    cheap = StubLLM([], default_response="ok")
    strong = StubLLM([], default_response="ok")
    backend = TwoStageLLMBackend(cheap, strong, min_confidence=0.5)
    backend.chat("s", "u")
    if backend.stats["cheap_calls"] != 1:
        errs.append("cheap_calls should increment by 1 per chat()")
    if backend.stats["total_calls"] != 1:
        errs.append("total_calls should increment by 1 per chat()")
    # Second call
    backend.chat("s", "u")
    if backend.stats["cheap_calls"] != 2:
        errs.append("cheap_calls should be 2 after two chats")
    return errs


def _inject_defect_protocol_broken() -> list[str]:
    """TwoStage must conform to LLMBackend protocol (chat-only interface)."""
    errs: list[str] = []
    cheap = StubLLM([], default_response="x")
    strong = StubLLM([], default_response="x")
    backend = TwoStageLLMBackend(cheap, strong, min_confidence=0.5)
    if not callable(getattr(backend, "chat", None)):
        errs.append("TwoStage must expose chat()")
    # Call with the protocol signature
    try:
        out = backend.chat("system", "user")
        if not isinstance(out, str):
            errs.append("chat() must return str")
    except TypeError as e:
        errs.append(f"chat() signature broken: {e}")
    return errs


# ============================================================= main


def main() -> int:
    checks = [
        ("1. LLMBackend protocol", _check_1_protocol),
        ("2. answer_confidence_score values", _check_2_confidence_score),
        ("3. high-confidence cheap answer → no escalation", _check_3_high_confidence_no_escalation),
        ("4. low-confidence cheap answer → escalate to strong", _check_4_low_confidence_escalates),
        ("5. empty cheap answer → escalate", _check_5_empty_escalates),
        ("6. stats counters exact", _check_6_stats_counter),
        ("7. rate properties consistent", _check_7_rate_properties),
        ("8. min_confidence boundary conditions", _check_8_min_confidence_boundaries),
        ("9. works transparently with all 4 topologies", _check_9_works_with_all_topologies),
        ("10. no silent downgrade on escalation", _check_10_no_silent_downgrade),
    ]
    defect_checks = [
        ("D1. min_confidence out of range → ValueError", _inject_defect_min_confidence_out_of_range),
        ("D2. weak escalation → hedge leaks", _inject_defect_weak_escalation),
        ("D3. stats drift", _inject_defect_stats_drift),
        ("D4. protocol broken", _inject_defect_protocol_broken),
    ]

    all_ok = True
    for name, fn in checks:
        errs = fn()
        if errs:
            all_ok = False
            print(f"  FAIL {name}")
            for e in errs:
                print(f"       - {e}")
        else:
            print(f"  PASS {name}")

    for name, fn in defect_checks:
        errs = fn()
        if errs:
            all_ok = False
            print(f"  FAIL {name} (defect injection)")
            for e in errs:
                print(f"       - {e}")
        else:
            print(f"  PASS {name} (defect injection)")

    print()
    if all_ok:
        print("GATE 34 PASS — Fusion B two-stage pipeline correct")
        return 0
    print("GATE 34 FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
