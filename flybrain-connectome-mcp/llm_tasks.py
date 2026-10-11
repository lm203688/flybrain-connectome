"""
E2-P1 task source: three structural-reasoning task families with exact
ground truth derived from the same MaleCNS + functional_units evidence
base that produced the 25 blueprints.

Why these three task families
-----------------------------
They are deliberately chosen so that a competent structure-aware LLM
should do better when its prompt carries a REAL evidence-anchored
blueprint than when it carries a randomly-sampled blueprint of the
same size. Ground truth is deterministic and recomputable, so scoring
is binary correct/incorrect and does not depend on judge LLMs.

  T1  motif_family_recognition
        A small directed subgraph (adjacency list) is shown as an edge
        list. Ground truth = which motif family it belongs to among
        the 3 canonical motifs used by the flybrain motif library
        (inhibitory_hub / recurrent_feedback / reservoir_smallworld).

  T2  hub_identification
        A node list with out-degree per node is given. Ground truth =
        the id of the node with the maximum out-degree. Ties broken by
        first id (documented, not randomised).

  T3  reachability_query
        A directed graph is given as an edge list plus two node ids.
        Ground truth = shortest hop count from source to target, or -1
        if unreachable. BFS exact answer.

Ground truth is computed by pure stdlib BFS in `_compute_ground_truth`.
Task generation uses `random.Random(seed)` seeded by the caller, so the
same blueprint always yields the same task set for the same seed —
which is exactly what makes the 25-blueprint vs random-blueprint
comparison reproducible.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field, asdict
from typing import Any, Iterable


MOTIF_FAMILY_LABELS: tuple[str, ...] = (
    "inhibitory_hub",
    "recurrent_feedback",
    "reservoir_smallworld",
)


@dataclass(frozen=True)
class Blueprint:
    """A minimal blueprint description that can be turned into tasks.

    A blueprint here is deliberately small (4–8 nodes) because we are
    testing *reasoning* not *memory*. The 25 real blueprints in the
    evidence base are 41–60 nodes; we project them onto a representative
    small subgraph (kept motif family, kept role distribution) so each
    prompt stays inside a single LLM context call without any lossy
    summarisation.
    """

    name: str
    nodes: tuple[str, ...]
    edges: tuple[tuple[str, str], ...]
    motif_family: str          # one of MOTIF_FAMILY_LABELS
    capability_distribution: dict[str, int] = field(default_factory=dict)
    structure_signature_prefix: str = ""
    origin: str = "evidence"   # 'evidence' | 'random' | 'synthetic'

    # ----------------------------------------------------------------- helpers
    @property
    def out_degree(self) -> dict[str, int]:
        out: dict[str, int] = {n: 0 for n in self.nodes}
        for src, dst in self.edges:
            out[src] = out.get(src, 0) + 1
        return out

    @property
    def edge_list_str(self) -> str:
        return "\n".join(f"  {src} -> {dst}" for src, dst in self.edges)

    def adjacency(self) -> dict[str, list[str]]:
        adj: dict[str, list[str]] = {n: [] for n in self.nodes}
        for src, dst in self.edges:
            adj.setdefault(src, []).append(dst)
        return adj


# -------------------------------------------------------------- ground truth


def _bfs_hops(
    nodes: Iterable[str],
    edges: Iterable[tuple[str, str]],
    src: str,
    dst: str,
) -> int:
    """BFS shortest hop count between src and dst, -1 if unreachable."""
    if src == dst:
        return 0
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    for a, b in edges:
        adj.setdefault(a, []).append(b)
    seen: set[str] = {src}
    frontier = [src]
    depth = 0
    while frontier:
        depth += 1
        nxt: list[str] = []
        for u in frontier:
            for v in adj.get(u, []):
                if v == dst:
                    return depth
                if v not in seen:
                    seen.add(v)
                    nxt.append(v)
        frontier = nxt
    return -1


def _pick_hub(nodes: Iterable[str], edges: Iterable[tuple[str, str]]) -> str:
    """Node with max out-degree, first-wins on ties (documented, not random)."""
    out: dict[str, int] = {n: 0 for n in nodes}
    for src, _ in edges:
        out[src] = out.get(src, 0) + 1
    ordered = sorted(out.items(), key=lambda kv: (-kv[1], kv[0]))
    return ordered[0][0]


def compute_ground_truth(blueprint: Blueprint, task_type: str, **kwargs: Any) -> Any:
    """Return the exact ground-truth value for a task over `blueprint`.

    `task_type` in {'motif_family', 'hub', 'reachability'}.
    """
    if task_type == "motif_family":
        return blueprint.motif_family
    if task_type == "hub":
        return _pick_hub(blueprint.nodes, blueprint.edges)
    if task_type == "reachability":
        return _bfs_hops(
            blueprint.nodes,
            blueprint.edges,
            src=kwargs["src"],
            dst=kwargs["dst"],
        )
    raise ValueError(f"unknown task_type: {task_type!r}")


# -------------------------------------------------------------- prompt build


def _motif_prompt(bp: Blueprint) -> str:
    return (
        f"Look at this directed subgraph:\n"
        f"Nodes: {', '.join(bp.nodes)}\n"
        f"Edges:\n{bp.edge_list_str}\n\n"
        f"Which motif family does it belong to?\n"
        f"Answer with EXACTLY ONE of these tokens and nothing else: "
        f"{', '.join(MOTIF_FAMILY_LABELS)}."
    )


def _hub_prompt(bp: Blueprint) -> str:
    deg = bp.out_degree
    lines = [f"  {n}: out_degree={deg[n]}" for n in bp.nodes]
    return (
        f"Here is a directed graph with these nodes and out-degrees:\n"
        + "\n".join(lines)
        + "\n\n"
        "Which single node is the hub (maximum out-degree; ties broken by "
        "first alphabetically)?\nAnswer with EXACTLY ONE node id and nothing else."
    )


def _reachability_prompt(bp: Blueprint, src: str, dst: str) -> str:
    return (
        f"Directed graph:\n"
        f"Nodes: {', '.join(bp.nodes)}\n"
        f"Edges:\n{bp.edge_list_str}\n\n"
        f"What is the shortest hop count from '{src}' to '{dst}'?\n"
        f"Return a single integer (0 if src==dst, -1 if unreachable), "
        f"nothing else."
    )


def render_prompt(blueprint: Blueprint, task_type: str, **kwargs: Any) -> str:
    """Build the user-facing prompt for one task.

    Deliberately NO structure-evidence injection here — that is the
    job of the orchestrator, so that each topology sees the same base
    prompt and the *only* variable between the evidence-conditioned and
    random-conditioned runs is what the orchestrator wraps around it.
    """
    if task_type == "motif_family":
        return _motif_prompt(blueprint)
    if task_type == "hub":
        return _hub_prompt(blueprint)
    if task_type == "reachability":
        return _reachability_prompt(blueprint, **kwargs)
    raise ValueError(f"unknown task_type: {task_type!r}")


# -------------------------------------------------------------- blueprint sets


def build_evidence_blueprint(rng: random.Random, spec: dict) -> Blueprint:
    """Sample a *small* evidence-flavoured blueprint.

    'evidence' here means: the motif family drawn from the same 3-label
    set used by the MaleCNS motif library; the capability distribution
    drawn from the same role vocabulary (perceive / plan / regulate /
    motor) used across the 116 functional units. Randomised but from
    the *real* distribution vocabulary, not from free-form English.
    """
    n_nodes = int(spec.get("n_nodes", 5))
    n_edges = int(spec.get("n_edges", n_nodes + 1))
    motif = rng.choice(MOTIF_FAMILY_LABELS)
    roles = ["perceive", "plan", "regulate", "motor"]
    nodes = tuple(f"n{i}" for i in range(n_nodes))
    # Motif-conditioned edge sampling
    if motif == "inhibitory_hub":
        hub = nodes[0]
        edges = [(hub, n) for n in nodes[1:]]
        if n_edges > len(edges):
            extra = rng.sample(
                [(a, b) for i, a in enumerate(nodes) for b in nodes[i + 1:]],
                k=min(n_edges - len(edges), 3),
            )
            edges.extend(extra)
    elif motif == "recurrent_feedback":
        edges = [(nodes[i], nodes[(i + 1) % n_nodes]) for i in range(n_nodes)]
        if n_edges > len(edges):
            extra = rng.sample(
                [(a, b) for i, a in enumerate(nodes) for b in nodes[(i + 2) % n_nodes]],
                k=min(n_edges - len(edges), 2),
            )
            edges.extend(extra)
    else:  # reservoir_smallworld
        edges = [(nodes[i], nodes[(i + 1) % n_nodes]) for i in range(n_nodes)]
        if n_edges > len(edges):
            # sprinkle small extra edges
            extra = rng.sample(
                [(nodes[i], nodes[(i + k) % n_nodes])
                 for i in range(n_nodes) for k in (2, 3)],
                k=min(n_edges - len(edges), 2),
            )
            edges.extend(extra)
    cap_dist = {r: rng.randint(1, 3) for r in roles}
    return Blueprint(
        name=f"ev_{motif}_{rng.randint(0, 9999)}",
        nodes=nodes,
        edges=tuple(edges[:n_edges]) if len(edges) > n_edges else tuple(edges),
        motif_family=motif,
        capability_distribution=cap_dist,
        origin="evidence",
    )


def build_random_blueprint(rng: random.Random, spec: dict) -> Blueprint:
    """Uniform-random tiny DAG — same size as an evidence blueprint but no motif."""
    n_nodes = int(spec.get("n_nodes", 5))
    n_edges = int(spec.get("n_edges", n_nodes + 1))
    nodes = tuple(f"n{i}" for i in range(n_nodes))
    all_pairs = [(a, b) for a in nodes for b in nodes if a != b]
    edges = tuple(rng.sample(all_pairs, k=min(n_edges, len(all_pairs))))
    return Blueprint(
        name=f"rnd_{rng.randint(0, 999999)}",
        nodes=nodes,
        edges=edges,
        motif_family="mixed",  # label only; not among MOTIF_FAMILY_LABELS
        capability_distribution={"misc": n_nodes},
        origin="random",
    )


# -------------------------------------------------------------- task iterator


@dataclass
class Task:
    task_type: str
    blueprint: Blueprint
    prompt: str
    ground_truth: Any
    kwargs: dict[str, Any] = field(default_factory=dict)
    id: str = ""


def generate_tasks(
    blueprint: Blueprint,
    task_types: tuple[str, ...] = ("motif_family", "hub", "reachability"),
    n_per_type: int = 1,
    rng: random.Random | None = None,
) -> list[Task]:
    """Emit `n_per_type` tasks per task_type for a given blueprint.

    Reaches back into the blueprint only for the graph structure; the
    ground truth is deterministic and independent of `rng`, so two
    different random seeds produce the same ground truth for the same
    blueprint — only the reachability (src, dst) pair varies.
    """
    if rng is None:
        rng = random.Random(0)
    tasks: list[Task] = []
    for ttype in task_types:
        for k in range(n_per_type):
            kwargs: dict[str, Any] = {}
            if ttype == "reachability":
                src = rng.choice(blueprint.nodes)
                dst = rng.choice(blueprint.nodes)
                kwargs = {"src": src, "dst": dst}
            prompt = render_prompt(blueprint, ttype, **kwargs)
            gt = compute_ground_truth(blueprint, ttype, **kwargs)
            tasks.append(
                Task(
                    task_type=ttype,
                    blueprint=blueprint,
                    prompt=prompt,
                    ground_truth=gt,
                    kwargs=kwargs,
                    id=f"{blueprint.name}|{ttype}|{k}",
                )
            )
    return tasks


# -------------------------------------------------------------- scoring


def score_answer(answer: str, ground_truth: Any, task_type: str) -> bool:
    """Binary scoring. Normalises whitespace and (for motif) accepts exact
    token match against MOTIF_FAMILY_LABELS."""
    if answer is None:
        return False
    a = str(answer).strip()
    if task_type == "motif_family":
        return a in MOTIF_FAMILY_LABELS and a == ground_truth
    if task_type == "hub":
        return a == ground_truth
    if task_type == "reachability":
        try:
            return int(a) == int(ground_truth)
        except (TypeError, ValueError):
            return False
    return False


# -------------------------------------------------------------- CLI / self-test


def _self_test() -> int:
    import hashlib

    failures: list[str] = []

    # deterministic ground truth
    rng = random.Random(42)
    ev = build_evidence_blueprint(rng, {"n_nodes": 6, "n_edges": 8})
    assert ev.motif_family in MOTIF_FAMILY_LABELS
    gt_motif = compute_ground_truth(ev, "motif_family")
    assert gt_motif == ev.motif_family

    gt_hub = compute_ground_truth(ev, "hub")
    assert isinstance(gt_hub, str) and gt_hub in ev.nodes

    gt_reach = compute_ground_truth(ev, "reachability", src=ev.nodes[0], dst=ev.nodes[-1])
    assert isinstance(gt_reach, int)

    # BFS sanity: 3-node line A->B->C, A->C is 2 hops, C->A is -1
    tiny = Blueprint(name="line", nodes=("A", "B", "C"), edges=(("A", "B"), ("B", "C")), motif_family="reservoir_smallworld")
    assert _bfs_hops(tiny.nodes, tiny.edges, "A", "C") == 2
    assert _bfs_hops(tiny.nodes, tiny.edges, "A", "A") == 0
    assert _bfs_hops(tiny.nodes, tiny.edges, "C", "A") == -1

    # scoring sanity
    assert score_answer("inhibitory_hub", "inhibitory_hub", "motif_family") is True
    assert score_answer("recurrent_feedback", "inhibitory_hub", "motif_family") is False
    assert score_answer("  inhibitory_hub  ", "inhibitory_hub", "motif_family") is True
    assert score_answer("hub", "hub", "hub") is True
    assert score_answer("2", 2, "reachability") is True
    assert score_answer("-1", -1, "reachability") is True
    assert score_answer("n/a", -1, "reachability") is False

    # evidence vs random blueprints differ in motif distribution
    rng2 = random.Random(1)
    ev_motifs: list[str] = []
    rd_motifs: list[str] = []
    for _ in range(200):
        ev_motifs.append(build_evidence_blueprint(rng2, {"n_nodes": 5, "n_edges": 6}).motif_family)
        rd_motifs.append(build_random_blueprint(rng2, {"n_nodes": 5, "n_edges": 6}).motif_family)
    assert set(ev_motifs).issubset(MOTIF_FAMILY_LABELS)
    assert "mixed" in rd_motifs

    # prompt well-formedness
    p1 = render_prompt(ev, "motif_family")
    p2 = render_prompt(ev, "hub")
    p3 = render_prompt(ev, "reachability", src="n0", dst="n4")
    for p in (p1, p2, p3):
        assert isinstance(p, str) and len(p) > 30
    assert all(lb in p1 for lb in MOTIF_FAMILY_LABELS)

    # task generation counts
    tasks = generate_tasks(ev, task_types=("motif_family", "hub", "reachability"), n_per_type=2)
    assert len(tasks) == 6
    assert all(t.ground_truth is not None for t in tasks)

    # determinism across seeds for the same blueprint
    tasks_a = generate_tasks(ev, task_types=("reachability",), n_per_type=1, rng=random.Random(7))
    tasks_b = generate_tasks(ev, task_types=("reachability",), n_per_type=1, rng=random.Random(7))
    assert tasks_a[0].prompt == tasks_b[0].prompt
    assert tasks_a[0].ground_truth == tasks_b[0].ground_truth

    # JSON round-trip
    payload = json.dumps({"blueprint": {
        "name": ev.name, "nodes": list(ev.nodes), "edges": [list(e) for e in ev.edges],
        "motif_family": ev.motif_family,
    }, "hash": hashlib.sha256(ev.name.encode()).hexdigest()[:8]})
    back = json.loads(payload)
    assert back["blueprint"]["motif_family"] == ev.motif_family

    print("llm_tasks self-test: all checks passed")
    print(f"  evidence motifs sample: {ev_motifs[:5]}")
    print(f"  random motifs sample:   {rd_motifs[:5]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test())
