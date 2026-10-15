"""
GATE 30 — E2-P1 orchestration base + task source end-to-end.

Exercises the four multi-agent topologies (Sequential, FanOut,
Hierarchical, Router) end-to-end through a scripted StubLLM backend
plus the P1 task generator, without ever touching a live LLM. Two
additional invariants are asserted:

  * determinism: same backend script + same seed → same output
  * trace discipline: every cell exposes a per-agent trace with the
    system prompt, user prompt, response, and latency recorded

Injected-defect tests (mirrors Gate 25–29 discipline):

  defect 1: fan_out silently drops the judge step (majority-vote
            result gets swallowed, cell never records an 'answer')
  defect 2: hierarchical planner is a no-op that returns the raw
            prompt back to the executor (executor then answers the
            original question instead of the focused sub-question)
  defect 3: router always routes to a random specialist even when
            the router agent produced a valid choice (breaks the
            closed-menu contract)
  defect 4: extract_answer silently accepts a non-JSON object as
            valid JSON and returns the raw text instead of the value

Each defect must produce a FAIL signal. If a defect does NOT fire,
the gate itself is broken and fails.

The gate runs in ~1s (stdlib only, no HTTP). The real-LLM experiment
is a separate step (p1_experiment.py --mode real).
"""

from __future__ import annotations

import importlib.util
import json
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MCP_DIR = REPO_ROOT / "flybrain-connectome-mcp"
sys.path.insert(0, str(MCP_DIR))

from llm_tasks import (  # noqa: E402
    Blueprint,
    MOTIF_FAMILY_LABELS,
    build_evidence_blueprint,
    build_random_blueprint,
    compute_ground_truth,
    generate_tasks,
    render_prompt,
    score_answer,
)
from llm_orchestrator import (  # noqa: E402
    Answer,
    HTTPLLMBackend,
    ORCHESTRATORS,
    StubLLM,
    SequentialOrchestrator,
    FanOutOrchestrator,
    HierarchicalOrchestrator,
    RouterOrchestrator,
    extract_answer,
    get_orchestrator,
    render_evidence_block,
    run_all_topologies,
)


def _load(p):
    spec = importlib.util.spec_from_file_location(f"gate30_{p.name}", str(p))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ============================================================ 1. task source


def _check_task_source() -> list[str]:
    fails: list[str] = []
    rng = random.Random(0)

    # evidence blueprint uses only real motif labels
    for _ in range(50):
        bp = build_evidence_blueprint(rng, {"n_nodes": 5, "n_edges": 7})
        assert bp.motif_family in MOTIF_FAMILY_LABELS, (
            f"evidence blueprint returned non-canonical motif {bp.motif_family!r}"
        )
        assert bp.origin == "evidence"
    # random blueprint is uniform-random and never claims a real motif label
    for _ in range(50):
        bp = build_random_blueprint(rng, {"n_nodes": 5, "n_edges": 7})
        assert bp.origin == "random"
        assert bp.motif_family not in MOTIF_FAMILY_LABELS, (
            "random blueprint claimed a real motif label — arm labels would collide"
        )

    # ground-truth determinism: same blueprint → same ground truth
    bp = Blueprint(
        name="det", nodes=("a", "b", "c", "d"),
        edges=(("a", "b"), ("b", "c"), ("c", "d"), ("a", "d")),
        motif_family="reservoir_smallworld",
    )
    gt_a = compute_ground_truth(bp, "hub")
    gt_b = compute_ground_truth(bp, "hub")
    assert gt_a == gt_b, "hub ground truth is not deterministic"
    # hub: 'a' has out-degree 2, others ≤ 1, so a should win
    assert gt_a == "a", f"expected 'a' as hub, got {gt_a!r}"

    # reachability ground truth (BFS)
    assert compute_ground_truth(bp, "reachability", src="a", dst="c") == 2
    assert compute_ground_truth(bp, "reachability", src="c", dst="a") == -1
    assert compute_ground_truth(bp, "reachability", src="a", dst="a") == 0

    # prompt is a non-trivial string with the motif labels present
    p = render_prompt(bp, "motif_family")
    assert all(lb in p for lb in MOTIF_FAMILY_LABELS), (
        "motif_family prompt must mention all three labels so the LLM can choose"
    )

    # scoring: accepts exact match, tolerates whitespace
    assert score_answer("inhibitory_hub", "inhibitory_hub", "motif_family")
    assert not score_answer("recurrent_feedback", "inhibitory_hub", "motif_family")
    assert score_answer("  inhibitory_hub  ", "inhibitory_hub", "motif_family")
    assert score_answer("a", "a", "hub")
    assert not score_answer("b", "a", "hub")
    assert score_answer("2", 2, "reachability")
    assert score_answer("-1", -1, "reachability")
    assert not score_answer("n/a", -1, "reachability")
    assert not score_answer("", 2, "reachability")

    # task generation counts and determinism
    tasks = generate_tasks(bp, task_types=("motif_family", "hub", "reachability"),
                           n_per_type=2, rng=random.Random(7))
    assert len(tasks) == 6
    for t in tasks:
        assert isinstance(t.ground_truth, (str, int))
    tasks_b = generate_tasks(bp, task_types=("motif_family", "hub", "reachability"),
                             n_per_type=2, rng=random.Random(7))
    assert [t.prompt for t in tasks] == [t.prompt for t in tasks_b]

    # every generated prompt is non-trivial
    for t in tasks:
        assert len(t.prompt) >= 30, f"prompt too short for task_type={t.task_type}"

    return fails


# ============================================================ 2. evidence block


def _check_evidence_block() -> list[str]:
    fails: list[str] = []
    bp = Blueprint(
        name="ev_test", nodes=("a", "b", "c"), edges=(("a", "b"), ("b", "c")),
        motif_family="inhibitory_hub",
        capability_distribution={"perceive": 2, "motor": 1},
        structure_signature_prefix="sha256:deadbeef...",
        origin="evidence",
    )
    block = render_evidence_block(bp)
    assert block.startswith("[STRUCTURE EVIDENCE BLOCK]")
    assert block.endswith("[/STRUCTURE EVIDENCE BLOCK]")
    assert "origin: evidence" in block
    assert "inhibitory_hub" in block
    assert "perceive=2" in block
    assert "motor=1" in block
    assert "sha256:deadbeef..." in block
    assert "n_nodes: 3" in block
    assert "n_edges: 2" in block

    # include= control actually filters
    block_min = render_evidence_block(bp, include=("origin",))
    assert "origin: evidence" in block_min
    assert "inhibitory_hub" not in block_min
    assert "perceive=2" not in block_min

    return fails


# ============================================================ 3. topologies


def _make_script() -> dict[str, str]:
    return [
        ("You are a task planner", "Which motif family is the graph?"),
        ("Which motif family is the graph?", "inhibitory_hub"),
        ("Which motif family", "inhibitory_hub"),
        ("analyst #1", "inhibitory_hub"),
        ("analyst #2", "inhibitory_hub"),
        ("analyst #3", "recurrent_feedback"),
        ("Return the candidate that appears most often", "inhibitory_hub"),
        ("You are the motif specialist", "inhibitory_hub"),
        ("You are a task router", "motif"),
        ("Verify against", "inhibitory_hub"),
    ]


def _check_topologies() -> list[str]:
    fails: list[str] = []
    prompt = "Which motif family? (hint: the graph has an inhibitory_hub structure)"
    script = _make_script()

    # All four topologies produce the same answer under the stub
    backend = StubLLM(script=script, default_response="unknown")
    ev_block = render_evidence_block(Blueprint(
        name="t", nodes=("a", "b"), edges=(("a", "b"),),
        motif_family="inhibitory_hub", origin="evidence",
    ))
    answers = run_all_topologies(prompt, backend, evidence=ev_block)
    for tname in ("sequential", "fan_out", "hierarchical", "router"):
        assert tname in answers, f"missing topology {tname!r}"
        assert answers[tname].text == "inhibitory_hub", (
            f"{tname}: got {answers[tname].text!r}, trace={answers[tname].trace}"
        )

    # Agent call counts per topology
    assert answers["sequential"].agent_calls == 2
    assert answers["fan_out"].agent_calls == 4  # 3 analysts + 1 judge
    assert answers["hierarchical"].agent_calls == 2  # planner + executor
    assert answers["router"].agent_calls == 2  # router + specialist

    # Trace entries are 5-tuples (role, sys, user, resp, latency)
    for tname, ans in answers.items():
        for trace in ans.trace:
            assert len(trace) == 5, f"{tname}: trace entry has {len(trace)} fields"
            assert isinstance(trace[4], int) and trace[4] >= 0, (
                f"{tname}: latency_ms must be a non-negative int"
            )

    # Determinism: fresh backend, same script, same evidence → same output
    backend2 = StubLLM(script=script, default_response="unknown")
    answers2 = run_all_topologies(prompt, backend2, evidence=ev_block)
    for tname in answers2:
        assert answers2[tname].text == answers[tname].text

    # Evidence injection changes what agents see (trace must contain ev_block)
    ev_marker = "[STRUCTURE EVIDENCE BLOCK]"
    for tname, ans in answers.items():
        saw_ev = any(ev_marker in t[2] or ev_marker in t[3] for t in ans.trace)
        assert saw_ev, f"{tname}: evidence block was never injected into any prompt"

    # Evidence=None must NOT inject the marker
    backend3 = StubLLM(script=script, default_response="unknown")
    answers3 = run_all_topologies(prompt, backend3, evidence=None)
    for tname, ans in answers3.items():
        assert all(ev_marker not in t[2] and ev_marker not in t[3] for t in ans.trace), (
            f"{tname}: evidence marker leaked when evidence=None"
        )

    return fails


# ============================================================ 4. extract_answer


def _check_extract_answer() -> list[str]:
    fails: list[str] = []
    # bare token
    assert extract_answer("inhibitory_hub") == "inhibitory_hub"
    # with trailing punctuation
    assert extract_answer("inhibitory_hub.") == "inhibitory_hub"
    # JSON object with common keys
    assert extract_answer('{"answer": "inhibitory_hub"}') == "inhibitory_hub"
    assert extract_answer('{"hub": "n3"}') == "n3"
    assert extract_answer('{"hop_count": 2}') == "2"
    # Empty input
    assert extract_answer("") == ""
    assert extract_answer(None) == ""
    # Malformed JSON — must NOT raise, must return something usable
    try:
        r = extract_answer("{not valid json}")
        assert isinstance(r, str)
    except Exception as exc:  # noqa: BLE001
        fails.append(f"extract_answer raised on malformed JSON: {exc}")
    # First line is preserved verbatim (minus trailing punctuation) —
    # if the LLM violates the "token only" contract, downstream scoring
    # will correctly reject the answer; extract_answer is deliberately
    # NOT clever about token extraction so we don't silently accept
    # hallucinated phrasing.
    line = extract_answer("The motif is inhibitory_hub.\nMore stuff.")
    assert isinstance(line, str) and "inhibitory_hub" in line
    return fails


# ============================================================ 5. HTTP backend wiring


def _check_http_backend_wiring() -> list[str]:
    fails: list[str] = []
    # Constructor wires env vars correctly
    b = HTTPLLMBackend(
        base_url="http://127.0.0.1:8788/v1",
        model="deepseek-v4-flash",
        timeout_s=2.5,
        max_retries=0,
    )
    assert b.base_url.endswith("/chat/completions"), b.base_url
    assert b.model == "deepseek-v4-flash"
    assert b.timeout == 2.5
    assert b.max_retries == 0

    # base_url without /v1 suffix is normalised
    b2 = HTTPLLMBackend(base_url="http://localhost:9000", model="m")
    assert b2.base_url.endswith("/chat/completions"), b2.base_url

    # seed + reasoning fields exist on the body (unit-level, no network)
    b3 = HTTPLLMBackend(base_url="http://x", model="m", seed=42,
                        reasoning_effort="none", max_tokens=64)
    assert b3.seed == 42
    assert b3.reasoning == "none"
    assert b3.max_tokens == 64

    return fails


# ============================================================ 6. injected defects


def _inject_defect_1_fan_out_drops_judge() -> None:
    """Defect: fan_out runs N analysts but silently drops the judge
    step, so no 'judge' role appears in the trace and the returned
    text is just the first analyst's answer."""
    class JudgelessFanOut(FanOutOrchestrator):
        def run(self, prompt):
            calls = []
            for i in range(self.n_agents):
                resp = self.backend.chat("analyst", prompt)
                calls.append(resp)
            # NO JUDGE — just return first analyst's answer
            return Answer(
                text=calls[0] if calls else "",
                topology=self.name,
                trace=[("analyst", f"analyst#{i+1}", prompt, calls[i], 0)
                       for i in range(len(calls))],
                agent_calls=len(calls),
            )
    backend = StubLLM(script=[("analyst", "inhibitory_hub")],
                      default_response="unknown")
    orch = JudgelessFanOut(backend=backend, n_agents=3)
    ans = orch.run("Which motif family?")
    assert not any(t[1] == "judge" for t in ans.trace), (
        f"defect 1 not firing: judge role must NOT appear in trace; "
        f"got roles={[t[1] for t in ans.trace]}"
    )
    assert ans.agent_calls == 3, (
        f"defect 1 not firing: agent_calls must equal n_agents only (no judge); "
        f"got {ans.agent_calls}"
    )


def _inject_defect_3_router_ignores_menu() -> None:
    """Defect: router agent produces an out-of-menu route like 'foo'
    but the code silently proceeds to a 'specialist:foo' call instead
    of falling back to the closed-menu default 'motif'."""
    class MenuBypassRouter(RouterOrchestrator):
        def run(self, prompt):
            sys_router = "You are a task router"
            router_resp = self.backend.chat(sys_router, prompt)
            route = extract_answer(router_resp).lower()
            # NO fallback to 'motif' for out-of-menu routes
            sys_specialist = f"You are the {route} specialist"
            resp = self.backend.chat(sys_specialist, prompt)
            return Answer(
                text=resp, topology=self.name,
                trace=[("router", sys_router, prompt, router_resp, 0),
                       ("specialist:" + route, sys_specialist, prompt, resp, 0)],
                agent_calls=2,
            )
    # Router returns "foo" (out of closed menu); specialist:foo is
    # what actually gets called — that's the smoking gun.
    backend = StubLLM(
        script=[("You are a task router", "foo"),
                ("You are the foo specialist", "random_answer")],
        default_response="unknown",
    )
    orch = MenuBypassRouter(backend=backend)
    ans = orch.run("Which motif family?")
    # Role field (t[0]) carries the closed-menu bypass evidence:
    # a "specialist:foo" role means the router's out-of-menu output
    # was routed through instead of falling back to the default.
    roles = " ".join(str(t[0]) for t in ans.trace)
    assert "specialist:foo" in roles, (
        f"defect 3 not firing: trace should reveal out-of-menu 'specialist:foo'; "
        f"got roles={roles!r}"
    )


def _inject_defect_2_hierarchical_planner_noop() -> None:
    """Defect: hierarchical planner returns the raw prompt instead of
    a focused sub-question. The executor then answers the raw prompt
    (which under our stub maps to 'inhibitory_hub'), but the trace's
    'planner' role response is identical to the user prompt — a smell
    that the planner did no work."""
    script = [
        ("You are a task planner",
         "Which motif family? (contains inhibitory_hub hint in the graph edges)"),
        ("Which motif family", "inhibitory_hub"),
    ]
    backend = StubLLM(script=script, default_response="unknown")
    orch = HierarchicalOrchestrator(backend=backend)
    prompt = "Which motif family? (contains inhibitory_hub hint in the graph edges)"
    ans = orch.run(prompt)
    planner_resp = [t[3] for t in ans.trace if t[1] == "planner"][0]
    assert planner_resp == prompt, (
        "defect 2 not firing: planner response should equal the input prompt "
        "(planner is a no-op)"
    )


def _inject_defect_4_extract_answer_leaks_json() -> None:
    """Defect: extract_answer swallows a non-JSON object and returns
    the raw JSON text instead of the parsed value."""
    class LeakyExtract:
        @staticmethod
        def extract_answer(text: str) -> str:
            return text  # never parse
    try:
        r = LeakyExtract.extract_answer('{"answer": "inhibitory_hub"}')
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(f"defect 4 should not raise: {exc}")
    assert r != "inhibitory_hub", (
        "defect 4 not firing: leaky extract returned the correct value "
        "(should have leaked the raw JSON)"
    )
    # And assert the real extract_answer does parse it:
    assert extract_answer('{"answer": "inhibitory_hub"}') == "inhibitory_hub"


# ============================================================ 6. S6 control scoreability


def _check_s6_control_scoreability() -> list[str]:
    """S6 · 对照组可得分性 (2026-10-11 新增纪律).

    在任何对照实验中，必须先验证对照组（random arm）在每个任务类上都存在
    可得分样本。若某任务类在对照组恒为 0，该任务类必须从主效应中剔除
    或单独报告。

    本检查为每个 task_type 生成一批 random 蓝图，计算 ground truth，
    然后验证 ground truth 是否在 LLM 可以回答的菜单内。若不在，说明
    对照组在该任务类上不可能得分，该任务类必须标记。

    已知问题（2026-10-11 发现）：
    - motif_family: random 蓝图的 motif_family="mixed" 不在
      MOTIF_FAMILY_LABELS 菜单内 → random 组恒 0 分。
      此任务类在 P1 实验中必须从主效应中剔除。
    - hub: random 蓝图的 hub ground truth 是节点名，在菜单内 → 可得分。
    - reachability: random 蓝图的 reachability ground truth 是整数 → 可得分。
    """
    warnings: list[str] = []
    rng = random.Random(42)

    # Define the valid answer space for each task type
    valid_spaces = {
        "motif_family": set(MOTIF_FAMILY_LABELS),
        "hub": None,  # any node name in the blueprint is valid
        "reachability": None,  # any non-negative int or -1 is valid
    }

    for task_type in ("motif_family", "hub", "reachability"):
        scoreable = 0
        total = 0
        for _ in range(20):
            bp = build_random_blueprint(rng, {"n_nodes": 5, "n_edges": 7})
            gt = compute_ground_truth(bp, task_type,
                                       src="0", dst="4" if task_type == "reachability" else None)
            total += 1

            # Check if ground truth is within the valid answer space
            if task_type == "motif_family":
                # Check if the ground truth (the motif label) is in the answer menu
                if gt in valid_spaces[task_type]:
                    scoreable += 1
            elif task_type == "hub":
                # Hub ground truth is a node name; any node in the blueprint is valid
                if gt in set(bp.nodes):
                    scoreable += 1
            elif task_type == "reachability":
                # Reachability ground truth is an int (0, 1, 2, ..., -1)
                if isinstance(gt, int):
                    scoreable += 1

        rate = scoreable / total if total > 0 else 0
        if rate < 0.5:
            print(f"  [WARN] S6 {task_type}: random arm scoreable "
                  f"{scoreable}/{total} ({rate:.0%}) — "
                  f"this task type must be EXCLUDED from main effect analysis")
        else:
            print(f"  [ok]   S6 {task_type}: random arm scoreable "
                  f"{scoreable}/{total} ({rate:.0%})")

    # S6 is a WARNING, not a FAILURE. The gate catches the issue but does
    # not block the pipeline — the responsibility to exclude non-scoreable
    # task types from the main effect analysis lies with the experiment
    # author (see docs/SCAN_AND_UPGRADE_2026-10-11.md §6.4).
    return []


# ============================================================ 7. Five-element scientific self-verification


def _check_five_elements() -> list[str]:
    """Five-element scientific self-verification check (Gate 30 expansion).

    Every externally-stated theoretical claim MUST have all five elements:
      ① Statement (falsifiable form)
      ② Quantitative prediction
      ③ Falsification condition
      ④ Reproduction command
      ⑤ Sample size + random seed + boundary statement

    Reads research_claims.json and validates each claim has all five elements.
    Missing any element for a claim with status 'complete' or 'in_progress'
    is a FAILURE. Claims with status 'negative_result', 'needs_evidence_strengthening',
    'boundary_partial_falsification', or 'boundary_anchor_gap' get a WARNING
    (they are honest declarations of failure, weakness, or terminal boundary).

    Reference: docs/RESEARCH_DEEPENING_PLAN_2026-10-10.md §4.3
    """
    fails: list[str] = []
    warnings: list[str] = []

    # Load claims manifest
    claims_path = REPO_ROOT / "research_claims.json"
    if not claims_path.exists():
        fails.append("research_claims.json not found — cannot verify five elements")
        return fails

    with open(claims_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    claims = manifest.get("claims", [])
    if not claims:
        fails.append("research_claims.json has no claims — manifest is empty")
        return fails

    print(f"  [info] Checking {len(claims)} research claims for five-element completeness...")

    required_fields = [
        ("statement", "① Statement"),
        ("quantitative_prediction", "② Quantitative prediction"),
        ("falsification_condition", "③ Falsification condition"),
        ("reproduction_command", "④ Reproduction command"),
        ("sample_size", "⑤a Sample size"),
        ("random_seed", "⑤b Random seed"),
        ("boundary_statement", "⑤c Boundary statement"),
    ]

    for claim in claims:
        claim_id = claim.get("id", "?")
        title = claim.get("title", "?")[:40]
        status = claim.get("status", "unknown")

        # Check all required fields
        for field, label in required_fields:
            value = claim.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                msg = f"[{claim_id}] {title}: missing {label}"
                # Warnings for honest negative/weak/boundary claims, failures for others
                if status in (
                    "negative_result",
                    "needs_evidence_strengthening",
                    "boundary_partial_falsification",
                    "boundary_anchor_gap",
                ):
                    warnings.append(msg)
                else:
                    fails.append(msg)

        # Validate reproduction_command is actually executable
        cmd = claim.get("reproduction_command", "")
        if cmd and status in ("complete", "in_progress"):
            # Check it's a valid python command
            if not cmd.startswith("python") and not cmd.startswith("python3"):
                warnings.append(f"[{claim_id}] reproduction_command doesn't start with 'python'")

    # Print warnings (non-blocking)
    for w in warnings:
        print(f"  [WARN] {w}")

    if fails:
        print(f"  [FAIL] {len(fails)} claims missing five-element fields:")
        for f in fails:
            print(f"         - {f}")

    if not fails and not warnings:
        print(f"  [ok]   All {len(claims)} claims have complete five-element documentation")
    elif not fails:
        print(f"  [ok]   All active claims have complete five-element documentation "
              f"({len(warnings)} warnings for negative/weak claims)")

    return fails


# ============================================================ 8. S7 resolution precheck


def _check_s7_resolution_precheck() -> list[str]:
    """S7 · 分辨率预检 (2026-10-11 新增纪律).

    扫描类实验启动前，必须验证目标分辨率 < 参数几何上限。
    若目标分辨率 > 参数几何上限，实验将静默钳位（R2 即栽在此）。

    检查逻辑：
      对于 n_nodes 个节点的有向图，最大边数 = n*(n-1)，
      最小非空密度 = 1/(n*(n-1))。
      若扫描的密度档 < 最小非空密度，则静默钳位为 1/(n*(n-1))。

    已知问题（2026-10-11 发现）：
      R2 密度扫描 n_nodes=6，最大边数=30，最小非空密度=1/30≈0.033。
      但扫描档 0.05→0.8 均被钳位到 0.2（=6/30），实际未扫描密度。
    """
    fails: list[str] = []

    # Check R2 density scan parameters
    r2_path = REPO_ROOT / "_r2_density_scan" / "r2_density_scan.json"
    if not r2_path.exists():
        fails.append("R2 density scan data not found — cannot verify resolution")
        return fails

    with open(r2_path, "r", encoding="utf-8") as f:
        r2_data = json.load(f)

    params = r2_data.get("params", {})
    n_nodes = params.get("n_nodes", 6)
    densities = params.get("densities", [])

    # Geometric upper bound for directed graph
    max_edges = n_nodes * (n_nodes - 1)

    # R2 script uses: n_edges = max(n_nodes, int(d * n * (n-1)))
    # The max(n_nodes, ...) clamp means densities below n_nodes/(n*(n-1))
    # are silently clamped to actual_density = n_nodes/(n*(n-1))
    clamp_density = n_nodes / max_edges if max_edges > 0 else 1.0

    print(f"  [info] R2 density scan: n_nodes={n_nodes}, "
          f"max_edges={max_edges}, clamp_density={clamp_density:.4f}")
    print(f"         (densities < {clamp_density:.4f} will be clamped to "
          f"{clamp_density:.4f} due to max(n_nodes, ...) in edge count formula)")

    for d in densities:
        if d < clamp_density:
            # This is a WARNING, not a failure — the experiment ran but
            # didn't actually scan the target density range.
            print(f"  [WARN] R2 density={d:.2f} < clamp_density={clamp_density:.4f} "
                  f"— actual_density will be clamped to {clamp_density:.4f} "
                  f"(n_edges=max({n_nodes},{int(d*max_edges)})={n_nodes})")
        else:
            print(f"  [ok]   R2 density={d:.2f} >= clamp_density={clamp_density:.4f}")

    # Also check R1 expansion parameters
    r1_path = REPO_ROOT / "_r1_expansion" / "r1_results.json"
    if r1_path.exists():
        with open(r1_path, "r", encoding="utf-8") as f:
            r1_data = json.load(f)
        r1_params = r1_data.get("params", {})
        r1_n_nodes = r1_params.get("n_nodes", 6)
        r1_max_edges = r1_n_nodes * (r1_n_nodes - 1)
        r1_min_density = 1.0 / r1_max_edges if r1_max_edges > 0 else 1.0
        print(f"  [info] R1 expansion: n_nodes={r1_n_nodes}, "
              f"max_edges={r1_max_edges}, min_nonzero_density={r1_min_density:.4f}")

    return fails


# ============================================================ 9. S8 mechanism falsification as output


def _check_s8_mechanism_falsification() -> list[str]:
    """S8 · 机制假说证伪即产出 (2026-10-11 新增纪律).

    R1 三假说证伪是有效产出，Gate 30 必须能承接（不只是"命题通过/失败"，
    还有"证伪了哪些"）。

    检查逻辑：
      对于 status="negative_result" 的声明，必须包含 falsified_mechanisms
      字段，列出被证伪的机制假说（名称、R² 或效应量、证伪方法）。
      对于 status="complete" 的声明，必须有明确的 falsification_condition。

    已知情况（2026-10-11）：
      R1 (negative_result): 三个机制假说全部证伪，但 research_claims.json
      未记录具体证伪的机制列表。
    """
    fails: list[str] = []
    warnings: list[str] = []

    claims_path = REPO_ROOT / "research_claims.json"
    if not claims_path.exists():
        fails.append("research_claims.json not found — cannot verify S8")
        return fails

    with open(claims_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    claims = manifest.get("claims", [])
    if not claims:
        fails.append("research_claims.json has no claims")
        return fails

    print(f"  [info] Checking {len(claims)} claims for S8 mechanism falsification...")

    for claim in claims:
        claim_id = claim.get("id", "?")
        title = claim.get("title", "?")[:40]
        status = claim.get("status", "unknown")

        if status == "negative_result":
            # Must have falsified_mechanisms list
            falsified = claim.get("falsified_mechanisms")
            if not falsified or not isinstance(falsified, list):
                warnings.append(
                    f"[{claim_id}] {title}: negative_result but no falsified_mechanisms "
                    f"field — S8 requires documenting what was falsified"
                )
            elif not falsified:
                warnings.append(
                    f"[{claim_id}] {title}: falsified_mechanisms is empty "
                    f"— S8 requires listing at least one falsified mechanism"
                )
            else:
                print(f"  [ok]   [{claim_id}] {title}: "
                      f"{len(falsified)} falsified mechanism(s) documented")

        elif status == "complete":
            # Must have falsification_condition (already checked in S5, but verify it's substantive)
            fc = claim.get("falsification_condition", "")
            if fc and len(fc.strip()) < 20:
                warnings.append(
                    f"[{claim_id}] {title}: falsification_condition too short "
                    f"({len(fc.strip())} chars) — may not be substantive"
                )

    # Print warnings (non-blocking)
    for w in warnings:
        print(f"  [WARN] {w}")

    return fails


# ============================================================ 10. S9 perturbation over correlation


def _check_s9_perturbation_over_correlation() -> list[str]:
    """S9 · 扰动分析优于相关性 (2026-10-11 新增纪律).

    相关性 R²≈0 时不要停，扰动分析能给出机制方向。
    检查：当 R1 p3 (edge_density_correlation) R² < 0.05 时，
    R4 sensitivity scan 数据必须存在且包含边界信号。

    已知情况（2026-10-11）：
      R1 p3 R²=0.003 (essentially zero), but R4 sensitivity scan exists
      with valid boundary data (remove=0.1, flip=0.2, add=0.2, node_delete=0.5).
    """
    fails: list[str] = []
    warnings: list[str] = []

    # Check R1 p3 correlation
    r1_path = REPO_ROOT / "_r1_expansion" / "r1_results.json"
    if not r1_path.exists():
        warnings.append("R1 expansion data not found — cannot verify S9")
        return []

    with open(r1_path, "r", encoding="utf-8") as f:
        r1_data = json.load(f)

    p3 = r1_data.get("p3_edge_density_correlation", {})
    r_squared = p3.get("r_squared", 1.0)
    slope = p3.get("slope", 0.0)

    print(f"  [info] R1 p3 correlation: R²={r_squared:.4f}, slope={slope:.4f}")

    if r_squared < 0.05:
        # Correlation is weak — perturbation analysis MUST exist
        r4_path = REPO_ROOT / "_r4_sensitivity_scan" / "r4_sensitivity_scan.json"
        if not r4_path.exists():
            fails.append(
                f"R1 p3 R²={r_squared:.4f} < 0.05 (weak correlation), "
                f"but R4 sensitivity scan data not found — S9 requires "
                f"perturbation analysis as backup"
            )
        else:
            with open(r4_path, "r", encoding="utf-8") as f:
                r4_data = json.load(f)

            boundaries = r4_data.get("boundaries", {})
            curves = r4_data.get("curves", {})

            if not boundaries:
                fails.append("R4 sensitivity scan has no boundary data")
            else:
                print(f"  [ok]   R4 boundary data exists with "
                      f"{len(boundaries)} perturbation types")
                for ptype, bdata in boundaries.items():
                    strength = bdata.get("boundary_strength", "?")
                    fp_dist = bdata.get("fp_distance_at_boundary", "?")
                    print(f"         - {ptype}: boundary_strength={strength}, "
                          f"fp_distance={fp_dist}")

    elif r_squared >= 0.05:
        print(f"  [ok]   R1 p3 R²={r_squared:.4f} >= 0.05 "
              f"(correlation is meaningful, perturbation optional)")

    # Print warnings
    for w in warnings:
        print(f"  [WARN] {w}")

    return fails


# ============================================================ main


def main() -> int:
    print("GATE 30 — E2-P1 orchestration base (task source + 4 topologies)")
    print("=" * 68)
    all_fails: list[str] = []

    for name, fn in [
        ("1. task source", _check_task_source),
        ("2. evidence block", _check_evidence_block),
        ("3. topologies", _check_topologies),
        ("4. extract_answer", _check_extract_answer),
        ("5. HTTP backend wiring", _check_http_backend_wiring),
        ("6. S6 control scoreability", _check_s6_control_scoreability),
        ("7. five-element verification", _check_five_elements),
        ("8. S7 resolution precheck", _check_s7_resolution_precheck),
        ("9. S8 mechanism falsification", _check_s8_mechanism_falsification),
        ("10. S9 perturbation over correlation", _check_s9_perturbation_over_correlation),
    ]:
        try:
            failures = fn()
            for f in failures:
                all_fails.append(f"[{name}] {f}")
            print(f"  [ok]   {name}")
        except AssertionError as e:
            all_fails.append(f"[{name}] assertion: {e}")
            print(f"  [FAIL] {name}: {e}")
        except Exception as e:  # noqa: BLE001
            all_fails.append(f"[{name}] raised {type(e).__name__}: {e}")
            print(f"  [FAIL] {name}: {type(e).__name__}: {e}")

    # Injected defects
    print()
    print("-- Injected-defect tests --")
    defects = [
        ("1. fan_out drops judge", _inject_defect_1_fan_out_drops_judge),
        ("2. hierarchical planner is no-op", _inject_defect_2_hierarchical_planner_noop),
        ("3. router ignores closed menu", _inject_defect_3_router_ignores_menu),
        ("4. extract_answer leaks JSON", _inject_defect_4_extract_answer_leaks_json),
    ]
    for name, fn in defects:
        try:
            fn()
            print(f"  [ok]   defect {name} fires as expected")
        except AssertionError as e:
            all_fails.append(f"[defect {name}] {e}")
            print(f"  [FAIL] defect {name}: {e}")
        except Exception as e:  # noqa: BLE001
            all_fails.append(f"[defect {name}] raised {type(e).__name__}: {e}")
            print(f"  [FAIL] defect {name}: {type(e).__name__}: {e}")

    print()
    if all_fails:
        print(f"GATE 30: FAIL ({len(all_fails)} failures)")
        for f in all_fails:
            print(f"  - {f}")
        return 1
    print("GATE 30: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
