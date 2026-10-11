"""
E2-P1 orchestrator base: four multi-agent topologies for the P1 benchmark.

This module is deliberately backend-agnostic. The `LLMBackend` protocol
accepts any callable matching `chat(system: str, user: str) -> str`, so
the exact same orchestration logic can be pointed at:

  * a real HTTP backend (SenseNova proxy, GLM queue, or a future Ollama
    4090 endpoint)
  * a stub that returns scripted answers, for Gate 30 unit tests

Four topologies are implemented. They are chosen to mirror the four
AdaptOrch-style shapes named in the arXiv:2602.16873 paper we are
comparing against:

  1. SEQUENTIAL  — one agent → another agent. The second sees the first
                   agent's answer verbatim as context.
  2. FAN_OUT     — N agents answer in parallel; a judge agent picks the
                   answer that appears most often (majority vote, with a
                   deterministic tiebreak).
  3. HIERARCHICAL— a planner agent decomposes the task into a single
                   focused sub-question; an executor answers the sub-
                   question. The executor does NOT see the raw task.
  4. ROUTER      — a router agent picks a specialist by name from a
                   menu of {motif, hub, reachability} and only that
                   specialist's prompt reaches the LLM.

All four topologies are invoked via a single `Orchestrator.run(task)`
entry point that returns an `Answer` with a full provenance chain.
Nothing in this module calls an external LLM directly — the caller
injects the backend. That separation is what lets Gate 30 test the
orchestration logic exhaustively with zero tokens burned.

Provenance discipline
---------------------
`Answer.trace` records every backend call as a tuple
`(agent_role, system_prompt, user_prompt, response, latency_ms)`.
This is what makes the benchmark auditable: any single number in the
final report can be traced back to the exact prompt that produced it,
and Gate 30 verifies the trace discipline holds under all four
topologies.
"""

from __future__ import annotations

import json
import os
import random
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Protocol, Sequence


# ============================================================== backend

TraceCall = tuple[str, str, str, str, int]  # role, sys, user, resp, latency_ms


class LLMBackend(Protocol):
    def chat(self, system: str, user: str) -> str: ...


@dataclass
class Answer:
    text: str
    topology: str
    trace: list[TraceCall] = field(default_factory=list)
    latency_ms: int = 0
    agent_calls: int = 0


class StubLLM:
    """A scripted backend for unit tests and Gate 30.

    Given a mapping of prompt-substring → response, the stub returns the
    first matching response. Anything unmatched returns
    `default_response`. Latency is always 0 ms.
    """

    def __init__(
        self,
        script: dict[str, str] | list[tuple[str, str]],
        default_response: str = "unknown",
    ) -> None:
        if isinstance(script, dict):
            self.script: list[tuple[str, str]] = list(script.items())
        else:
            self.script = list(script)
        self.default_response = default_response
        self.calls: list[tuple[str, str]] = []

    def chat(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        combined = f"{system}\n===USER===\n{user}"
        for needle, response in self.script:
            if needle in combined:
                return response
        return self.default_response


class HTTPLLMBackend:
    """OpenAI-compatible HTTP backend.

    Deliberately stdlib-only (urllib) so the module has no runtime
    dependency beyond Python ≥3.10. The `key_pool` and `base_url` can
    be read from env vars as fallback.
    """

    DEFAULT_ENV_KEYS = (
        "FLYBRAIN_LLM_BASE_URL",
        "FLYBRAIN_LLM_MODEL",
        "FLYBRAIN_LLM_API_KEY",
        "FLYBRAIN_LLM_TIMEOUT",
        "FLYBRAIN_LLM_REASONING",
    )

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        timeout_s: float | None = None,
        reasoning_effort: str | None = None,
        max_retries: int = 2,
        max_tokens: int = 128,
        temperature: float = 0.0,
        seed: int | None = 42,
    ) -> None:
        self.base_url = (base_url or os.environ.get("FLYBRAIN_LLM_BASE_URL")
                         or "http://127.0.0.1:8788/v1").rstrip("/")
        if not self.base_url.endswith("/chat/completions"):
            if self.base_url.endswith("/v1"):
                self.base_url += "/chat/completions"
            elif not self.base_url.endswith("/chat/completions"):
                self.base_url += "/chat/completions"
        self.model = model or os.environ.get("FLYBRAIN_LLM_MODEL") or "deepseek-v4-flash"
        self.api_key = api_key or os.environ.get("FLYBRAIN_LLM_API_KEY") or "dummy"
        self.timeout = float(timeout_s or os.environ.get("FLYBRAIN_LLM_TIMEOUT", "30"))
        self.reasoning = reasoning_effort or os.environ.get("FLYBRAIN_LLM_REASONING") or "none"
        self.max_retries = int(max_retries)
        self.max_tokens = int(max_tokens)
        self.temperature = float(temperature)
        self.seed = seed
        self.calls: list[dict[str, Any]] = []
        self.failures: list[str] = []

    # ------------------------------------------------------------------ chat
    def chat(self, system: str, user: str) -> str:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "reasoning_effort": self.reasoning,
        }
        if self.seed is not None:
            body["seed"] = self.seed
        payload = json.dumps(body).encode("utf-8")

        last_err: str = ""
        for attempt in range(1 + self.max_retries):
            t0 = time.perf_counter()
            req = urllib.request.Request(
                self.base_url,
                data=payload,
                headers={"Content-Type": "application/json",
                         "Authorization": f"Bearer {self.api_key}"},
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read())
                ms = int((time.perf_counter() - t0) * 1000)
                content = (
                    data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )
                self.calls.append({
                    "model": self.model, "attempt": attempt,
                    "system": system, "user": user,
                    "content": content, "latency_ms": ms,
                    "usage": data.get("usage", {}),
                    "request_id": data.get("request_id", ""),
                })
                return content
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError,
                    KeyError, IndexError) as exc:
                ms = int((time.perf_counter() - t0) * 1000)
                last_err = f"{type(exc).__name__}: {exc}"
                self.failures.append(f"attempt={attempt} err={last_err}")
                # Retry on transient conditions, back off
                time.sleep(0.5 * (2 ** attempt))
        self.calls.append({
            "model": self.model, "attempt": self.max_retries + 1,
            "system": system, "user": user,
            "content": "", "latency_ms": 0,
            "error": last_err,
        })
        raise RuntimeError(f"LLM backend failed after {1 + self.max_retries} attempts: {last_err}")


# ============================================================== two-stage (cheap -> strong) pipeline

# Fusion B (OPEN_SOURCE_FUSION_2026-10-11.md §4): a TwoStageLLMBackend
# front-runs a cheap/open-source small model (Qwen / MiniCPM / Laya) and
# only escalates to a strong model when the cheap answer looks low-confidence
# or empty. This mirrors the two-tier pattern already proven on the JEV side
# (Laya 421M replaces ~60 % of JEV calls).

# Heuristics that decide whether the cheap answer is "good enough" to skip
# escalation. All are STRONGLY CONSERVATIVE — when in doubt, escalate. That is
# deliberate: the goal is cost reduction, not accuracy improvement, and a
# wrong escalation decision costs us one cheap call (not a wrong answer).
_HIGH_CONFIDENCE_MARKERS: tuple[str, ...] = (
    # answer that is NOT a refusal / hedge
    # we reject anything containing these tokens
)
_LOW_CONFIDENCE_MARKERS: tuple[str, ...] = (
    "unknown", "i don't know", "idk", "i'm not sure", "not sure",
    "cannot determine", "can't determine", "no answer", "unclear",
    "insufficient information", "i need more", "cannot determine",
)


def answer_confidence_score(text: str) -> float:
    """Return a 0..1 confidence estimate for a short LLM answer.

    Heuristic, deliberately simple and deterministic. This is a *routing*
    signal, not a judgement signal — see the "判据模型不是权威" caveat in
    OPEN_SOURCE_FUSION §4 Fusion A. The score is used only to decide whether
    to escalate to the strong backend; it is NEVER used as the answer itself.
    """
    if not text:
        return 0.0
    t = text.strip().lower()
    if not t:
        return 0.0
    # very short, clean token → high confidence
    if len(t) <= 40 and not any(m in t for m in _LOW_CONFIDENCE_MARKERS):
        return 1.0
    # long / vague / hedging → low confidence
    if any(m in t for m in _LOW_CONFIDENCE_MARKERS):
        return 0.0
    # medium-length answer with no hedging markers: moderate confidence
    return 0.5


class TwoStageLLMBackend:
    """Cheap-model-first backend with selective escalation to a strong model.

    Usage:
        cheap = HTTPLLMBackend(base_url=..., model="qwen-2.5-7b", max_tokens=64)
        strong = HTTPLLMBackend(base_url=..., model="deepseek-v4-flash", max_tokens=128)
        backend = TwoStageLLMBackend(cheap, strong, min_confidence=0.6)
        orchestrator = SequentialOrchestrator(backend)  # works unchanged

    The wrapper implements the LLMBackend protocol so any orchestrator can
    use it transparently. `stats` exposes call counts for benchmarking.

    Design notes (Fusion B discipline):
    - Never drops an answer to save cost: any low-confidence cheap answer is
      ESCALATED, not returned as-is. The strong model's answer always wins
      when escalation fires.
    - The two-stage routing is transparent to the caller: only `stats`
      exposes the internal path taken.
    - Fully deterministic: no randomness in the routing decision.
    """

    name = "two_stage"

    def __init__(
        self,
        cheap: LLMBackend,
        strong: LLMBackend,
        min_confidence: float = 0.6,
    ) -> None:
        if not (0.0 <= min_confidence <= 1.0):
            raise ValueError(f"min_confidence must be in [0,1]; got {min_confidence}")
        self.cheap = cheap
        self.strong = strong
        self.min_confidence = float(min_confidence)
        self.stats: dict[str, int] = {
            "cheap_calls": 0,
            "strong_calls": 0,
            "escalations": 0,
            "cheap_hits": 0,   # cheap answer accepted without escalation
            "total_calls": 0,
        }

    def chat(self, system: str, user: str) -> str:
        self.stats["cheap_calls"] += 1
        self.stats["total_calls"] += 1
        cheap_ans = self.cheap.chat(system, user)
        score = answer_confidence_score(cheap_ans)
        if score >= self.min_confidence:
            self.stats["cheap_hits"] += 1
            return cheap_ans
        # Low confidence → escalate to the strong backend with the same prompt
        self.stats["strong_calls"] += 1
        self.stats["escalations"] += 1
        strong_ans = self.strong.chat(system, user)
        return strong_ans

    # convenience: what fraction of calls ended at the cheap model
    @property
    def cheap_hit_rate(self) -> float:
        return self.stats["cheap_hits"] / max(1, self.stats["total_calls"])

    @property
    def escalation_rate(self) -> float:
        return self.stats["escalations"] / max(1, self.stats["total_calls"])


# ============================================================== evidence injection


def render_evidence_block(blueprint: Any, include: tuple[str, ...] = ()) -> str:
    """Render the blueprint's *structure evidence* for prompt injection.

    The whole point of the P1 experiment is to test whether the
    evidence-backed blueprint — as opposed to a random one of the same
    size — measurably improves LLM reasoning. This block is what the
    orchestrator injects around the raw task prompt.

    `include` lets you dial in exactly which fields are exposed
    (motif_family, capability_distribution, structure_signature_prefix,
    origin, sizes). By default all fields are included so the "evidence"
    arm sees the full signal.
    """
    if not include:
        include = (
            "motif_family", "capability_distribution",
            "structure_signature_prefix", "origin", "sizes",
        )
    lines: list[str] = ["[STRUCTURE EVIDENCE BLOCK]"]
    if "origin" in include:
        lines.append(f"origin: {blueprint.origin}")
    if "motif_family" in include:
        lines.append(f"motif_family: {blueprint.motif_family}")
    if "capability_distribution" in include and blueprint.capability_distribution:
        cap = ", ".join(f"{k}={v}" for k, v in blueprint.capability_distribution.items())
        lines.append(f"capability_distribution: {{{cap}}}")
    if "structure_signature_prefix" in include and blueprint.structure_signature_prefix:
        lines.append(f"structure_signature_prefix: {blueprint.structure_signature_prefix}")
    if "sizes" in include:
        lines.append(f"n_nodes: {len(blueprint.nodes)}")
        lines.append(f"n_edges: {len(blueprint.edges)}")
    lines.append("[/STRUCTURE EVIDENCE BLOCK]")
    return "\n".join(lines)


# ============================================================== answer extraction


def extract_answer(text: str) -> str:
    """Pull a short answer from an LLM response.

    Handles the three shapes we actually saw in the smoke test:
    bare token, JSON object, or a sentence containing the token.
    """
    if not text:
        return ""
    t = text.strip()
    # JSON object → try to find a common key
    if t.startswith("{") and t.endswith("}"):
        try:
            obj = json.loads(t)
            for key in ("answer", "hub", "motif", "family", "motif_family",
                        "value", "hop_count", "distance"):
                if key in obj and obj[key] is not None:
                    return str(obj[key])
        except json.JSONDecodeError:
            pass
    # First line, strip punctuation
    line = t.splitlines()[0].strip().rstrip(".:!?,")
    return line


# ============================================================== topologies


SYSTEM_GENERIC = (
    "You are a graph-reasoning assistant. Answer concisely: when a "
    "single token is requested, return ONLY the token and nothing else. "
    "Do not add explanation."
)


class SequentialOrchestrator:
    """1 → 2: agent 1 answers; agent 2 sees agent 1's answer and commits
    the final. Latency ~2x a single call; error surface: agent 1 may be
    wrong and agent 2 may trust it blindly (or override it).
    """

    name = "sequential"

    def __init__(self, backend: LLMBackend, evidence: str | None = None) -> None:
        self.backend = backend
        self.evidence = evidence

    def _wrap(self, prompt: str) -> str:
        return (
            (self.evidence + "\n\n" if self.evidence else "") + prompt
        )

    def run(self, prompt: str) -> Answer:
        t0 = time.perf_counter()
        trace: list[TraceCall] = []
        sys_1 = SYSTEM_GENERIC
        sys_2 = (SYSTEM_GENERIC + "\nA prior analyst produced an answer. "
                 "Verify against the graph and, if correct, echo it verbatim; "
                 "if wrong, correct it.")
        agent_1 = self.backend.chat(sys_1, self._wrap(prompt))
        trace.append((sys_1, "agent_1_reason", prompt, agent_1, 0))
        wrapped_2 = (
            (self.evidence + "\n\n" if self.evidence else "") +
            f"Original question:\n{prompt}\n\n"
            f"Prior analyst's answer: {extract_answer(agent_1)}"
        )
        agent_2 = self.backend.chat(sys_2, wrapped_2)
        trace.append((sys_2, "agent_2_verify", wrapped_2, agent_2, 0))
        return Answer(
            text=extract_answer(agent_2),
            topology=self.name,
            trace=trace,
            latency_ms=int((time.perf_counter() - t0) * 1000),
            agent_calls=2,
        )


class FanOutOrchestrator:
    """N agents answer independently, then a judge picks the majority
    answer. N is exposed via `n_agents`. Ties are broken by choosing
    the alphabetically-first candidate to keep the outcome deterministic
    given a fixed agent list.
    """

    name = "fan_out"

    def __init__(
        self,
        backend: LLMBackend,
        evidence: str | None = None,
        n_agents: int = 3,
    ) -> None:
        self.backend = backend
        self.evidence = evidence
        self.n_agents = max(1, int(n_agents))

    def _wrap(self, prompt: str, suffix: str = "") -> str:
        base = self.evidence + "\n\n" if self.evidence else ""
        return base + prompt + suffix

    def run(self, prompt: str) -> Answer:
        t0 = time.perf_counter()
        trace: list[TraceCall] = []
        calls: list[str] = []
        for i in range(self.n_agents):
            # Slight prompt variation so agents are not literally
            # identical; still the same graph question.
            suffix = f"\n\n(You are analyst #{i + 1} of {self.n_agents}.)"
            sys_i = SYSTEM_GENERIC + suffix
            wrapped_i = self._wrap(prompt, suffix=suffix)
            resp = self.backend.chat(sys_i, wrapped_i)
            calls.append(extract_answer(resp))
            trace.append((sys_i, "analyst", wrapped_i, resp, 0))
        # Judge: count occurrences and pick majority with alpha tiebreak
        counts: dict[str, int] = {}
        for a in calls:
            counts[a] = counts.get(a, 0) + 1
        majority = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        judge_sys = SYSTEM_GENERIC
        judge_user = (
            f"Candidates from {self.n_agents} analysts: {calls}\n"
            f"Return the candidate that appears most often, "
            f"breaking ties alphabetically. Token only."
        )
        judge_resp = self.backend.chat(judge_sys, judge_user)
        trace.append((judge_sys, "judge", judge_user, judge_resp, 0))
        return Answer(
            text=extract_answer(judge_resp) or majority,
            topology=self.name,
            trace=trace,
            latency_ms=int((time.perf_counter() - t0) * 1000),
            agent_calls=self.n_agents + 1,
        )


class HierarchicalOrchestrator:
    """Planner reduces the task to a single focused sub-question,
    executor answers only the sub-question. Compared with `sequential`,
    the executor is *blind* to the raw task.
    """

    name = "hierarchical"

    def __init__(self, backend: LLMBackend, evidence: str | None = None) -> None:
        self.backend = backend
        self.evidence = evidence

    def run(self, prompt: str) -> Answer:
        t0 = time.perf_counter()
        trace: list[TraceCall] = []
        sys_planner = (
            SYSTEM_GENERIC +
            "\nYou are a task planner. Given a graph-reasoning task, "
            "return EXACTLY ONE short, focused sub-question in the same "
            "answer format as the original task would require. No "
            "extra commentary."
        )
        sys_executor = SYSTEM_GENERIC
        plan = self.backend.chat(sys_planner, self._wrap(prompt))
        trace.append((sys_planner, "planner", self._wrap(prompt), plan, 0))
        sub_q = extract_answer(plan) or prompt
        exec_resp = self.backend.chat(sys_executor, self._wrap(sub_q))
        trace.append((sys_executor, "executor", self._wrap(sub_q), exec_resp, 0))
        return Answer(
            text=extract_answer(exec_resp),
            topology=self.name,
            trace=trace,
            latency_ms=int((time.perf_counter() - t0) * 1000),
            agent_calls=2,
        )

    def _wrap(self, prompt: str) -> str:
        return (self.evidence + "\n\n" if self.evidence else "") + prompt


SPECIALIST_MENU = (
    "motif (which motif family the graph belongs to)",
    "hub (which single node has the largest out-degree)",
    "reachability (shortest hop count between two named nodes)",
)


class RouterOrchestrator:
    """Router picks a specialist by NAME from a fixed menu; the
    specialist is the only one that ever sees the raw graph question.
    Compared with `hierarchical`, the specialist menu is closed-set
    (exactly the three task families we run in the benchmark), so the
    router's output is bounded.
    """

    name = "router"

    def __init__(self, backend: LLMBackend, evidence: str | None = None) -> None:
        self.backend = backend
        self.evidence = evidence

    def run(self, prompt: str) -> Answer:
        t0 = time.perf_counter()
        trace: list[TraceCall] = []
        menu_str = "\n".join(f"  - {s}" for s in SPECIALIST_MENU)
        sys_router = (
            SYSTEM_GENERIC +
            f"\nYou are a task router. Given a graph task, pick exactly ONE "
            f"specialist by name from this closed menu:\n{menu_str}\n"
            f"Return ONLY the specialist's first token (motif / hub / reachability)."
        )
        router_resp = self.backend.chat(sys_router, prompt)
        trace.append((sys_router, "router", prompt, router_resp, 0))
        route = extract_answer(router_resp).lower()
        if route not in {"motif", "hub", "reachability"}:
            route = "motif"  # deterministic fallback; NOT a guess at the answer
        sys_specialist = (
            SYSTEM_GENERIC +
            f"\nYou are the {route} specialist. Answer ONLY this question."
        )
        specialist_resp = self.backend.chat(sys_specialist, self._wrap(prompt))
        trace.append((sys_specialist, f"specialist:{route}", self._wrap(prompt), specialist_resp, 0))
        return Answer(
            text=extract_answer(specialist_resp),
            topology=self.name,
            trace=trace,
            latency_ms=int((time.perf_counter() - t0) * 1000),
            agent_calls=2,
        )

    def _wrap(self, prompt: str) -> str:
        return (self.evidence + "\n\n" if self.evidence else "") + prompt


# ============================================================== registry + driver


ORCHESTRATORS: dict[str, type] = {
    "sequential": SequentialOrchestrator,
    "fan_out": FanOutOrchestrator,
    "hierarchical": HierarchicalOrchestrator,
    "router": RouterOrchestrator,
}


def get_orchestrator(
    name: str,
    backend: LLMBackend,
    evidence: str | None = None,
    **kwargs: Any,
) -> Any:
    try:
        cls = ORCHESTRATORS[name]
    except KeyError:
        raise KeyError(f"unknown topology {name!r}; known: {list(ORCHESTRATORS)}")
    return cls(backend=backend, evidence=evidence, **kwargs)


def run_all_topologies(
    prompt: str,
    backend: LLMBackend,
    evidence: str | None = None,
    topologies: Sequence[str] = ("sequential", "fan_out", "hierarchical", "router"),
    fan_out_n: int = 3,
) -> dict[str, Answer]:
    out: dict[str, Answer] = {}
    for tname in topologies:
        cls = ORCHESTRATORS[tname]
        kwargs = {"n_agents": fan_out_n} if tname == "fan_out" else {}
        orch = cls(backend=backend, evidence=evidence, **kwargs)
        out[tname] = orch.run(prompt)
    return out


# ============================================================== self-test

def _self_test() -> int:
    """Prove all four topologies wire up correctly under a stub backend.

    The stub is scripted so that, given identical prompts, the
    orchestrator output is deterministic. This is exactly what Gate 30
    re-runs, but with defect injections (see check_llm_orchestrator.py).
    """
    # Script so that any prompt containing "inhibitory_hub" returns "inhibitory_hub"
    script = [
        ("You are a task planner", "Which motif family is the graph?"),
        ("Which motif family is the graph?", "inhibitory_hub"),
        ("Which motif family", "inhibitory_hub"),
        ("analyst #1", "inhibitory_hub"),
        ("analyst #2", "inhibitory_hub"),
        ("analyst #3", "inhibitory_hub"),
        ("Return the candidate that appears most often", "inhibitory_hub"),
        ("You are the motif specialist", "inhibitory_hub"),
        ("You are a task router", "motif"),
        ("Verify against", "inhibitory_hub"),
    ]
    backend = StubLLM(script=script, default_response="unknown")

    prompt = "Which motif family? (contains inhibitory_hub hint in the graph edges)"
    answers = run_all_topologies(prompt, backend, evidence="[STRUCTURE EVIDENCE BLOCK]\norigin: evidence\n[/STRUCTURE EVIDENCE BLOCK]")

    for tname, ans in answers.items():
        assert ans.text == "inhibitory_hub", (
            f"{tname}: got {ans.text!r} expected 'inhibitory_hub'; trace={ans.trace}"
        )
        assert ans.agent_calls >= 2, f"{tname}: only {ans.agent_calls} agent calls"
        assert all(len(t) == 5 for t in ans.trace), f"{tname}: malformed trace entries"

    # fan_out must make n_agents+1 backend calls (analysts + judge)
    fo_trace = answers["fan_out"].trace
    analyst_calls = sum(1 for t in fo_trace if t[1] == "analyst")
    assert analyst_calls == 3, f"fan_out should call 3 analysts, got {analyst_calls}"
    assert any(t[1] == "judge" for t in fo_trace), "fan_out must include a judge call"

    # deterministic re-run under a fresh backend with same script → same output
    backend2 = StubLLM(script=script, default_response="unknown")
    answers2 = run_all_topologies(prompt, backend2, evidence=None)
    for tname in answers2:
        assert answers2[tname].text == answers[tname].text, f"{tname} nondeterministic"

    # HTTP backend sanity (constructor wiring only, no network call)
    http = HTTPLLMBackend(
        base_url="http://127.0.0.1:8788/v1",
        model="deepseek-v4-flash",
        timeout_s=1.0,
        max_retries=0,
    )
    assert http.base_url == "http://127.0.0.1:8788/v1/chat/completions", http.base_url
    assert http.model == "deepseek-v4-flash"
    assert http.timeout == 1.0

    # evidence block wiring
    from llm_tasks import Blueprint
    bp = Blueprint(name="t", nodes=("a", "b"), edges=(("a", "b"),),
                   motif_family="inhibitory_hub",
                   capability_distribution={"perceive": 2})
    block = render_evidence_block(bp)
    assert "inhibitory_hub" in block
    assert "perceive=2" in block
    assert block.startswith("[STRUCTURE EVIDENCE BLOCK]")
    assert block.endswith("[/STRUCTURE EVIDENCE BLOCK]")

    print("llm_orchestrator self-test: all checks passed")
    print(f"  topologies: {list(ORCHESTRATORS)}")
    print(f"  agent_calls per topology: "
          f"{ {k: v.agent_calls for k, v in answers.items()} }")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test())
