"""
profile_health.py — Structural health check for connectome-anchored profiles.

This is the C1 deliverable from the project's positioning strategy:
"structure health check" as an MCP tool, zero external dependencies.

The core insight (from the project's comprehensive assessment): the international
landscape (AdaptOrch / DGM / TMLR 2026 survey / SkillOpt-Lite) validates agents
by *task metrics* only. Nobody measures *structural degradation*. This module
fills that gap — it quantifies how structurally healthy a profile is, using
metrics derived from the real connectome evidence base.

Metrics (all stdlib-only, no numpy):
  1. connectivity     — is the module graph connected? (# components / # nodes)
  2. evidence_ratio   — fraction of units with ≥1 real connectome anchor
  3. port_satisfaction— fraction of declared ports that match a compatible counterpart
  4. orphan_rate      — fraction of units with 0 declared connections
  5. cycle_count      — number of directed cycles (feedback loops, desirable in reservoirs)
  6. hub_concentration— top-1 / top-5 out-degree ratio (measure of hub dependency)
  7. degradation_score— composite 0.0–1.0 (1.0 = perfectly healthy)

Usage:
    from profile_health import profile_health, health_summary
    result = profile_health("perceive")
    print(result["degradation_score"])

As MCP tool (wired in server.py):
    profile_health({ "profile": "perceive" })
    → { "profile": "...", "health": {...}, "degradation_score": 0.87, ... }
"""

from __future__ import annotations
import os, sys, json, math

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..")))


# ---------------------------------------------------------------------------
# helpers — pure stdlib graph ops (no numpy, no networkx)
# ---------------------------------------------------------------------------

def _build_adjacency(edges: list[tuple[str, str]]) -> dict[str, list[str]]:
    """Return {node: [neighbors]} from edge list."""
    adj: dict[str, list[str]] = {}
    for u, v in edges:
        adj.setdefault(u, [])
        adj.setdefault(v, [])
        adj[u].append(v)
    return adj


def _connected_components(nodes: list[str], adj: dict[str, list[str]]) -> list[set[str]]:
    """BFS connected components (undirected)."""
    visited: set[str] = set()
    components: list[set[str]] = []
    for start in nodes:
        if start in visited:
            continue
        comp: set[str] = set()
        stack = [start]
        while stack:
            node = stack.pop()
            if node in visited:
                continue
            visited.add(node)
            comp.add(node)
            for nb in adj.get(node, []):
                if nb not in visited:
                    stack.append(nb)
        components.append(comp)
    return components


def _find_cycles(nodes: list[str], adj: dict[str, list[str]],
                  max_depth: int = 8) -> list[list[str]]:
    """DFS cycle detection (returns list of cycles, truncated at max_depth)."""
    cycles: list[list[str]] = []
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {n: WHITE for n in nodes}
    parent: dict[str, str | None] = {n: None for n in nodes}

    def _dfs(start: str, path: list[str]):
        nonlocal cycles
        stack = [(start, iter(adj.get(start, [])))]
        color[start] = GRAY
        path = [start]

        while stack:
            node, it = stack[-1]
            found_next = False
            for neighbor in it:
                if color.get(neighbor) == GRAY:
                    # cycle found
                    idx = path.index(neighbor) if neighbor in path else -1
                    if idx >= 0:
                        cycle = path[idx:] + [neighbor]
                        if len(cycle) <= max_depth:
                            cycles.append(cycle)
                    found_next = True
                    break
                elif color.get(neighbor) == WHITE:
                    color[neighbor] = GRAY
                    parent[neighbor] = node
                    stack.append((neighbor, iter(adj.get(neighbor, []))))
                    path.append(neighbor)
                    found_next = True
                    break
            if not found_next:
                color[node] = BLACK
                stack.pop()
                if path and path[-1] == node:
                    path.pop()
        return

    for node in nodes:
        if color.get(node) == WHITE:
            _dfs(node, [])

    # deduplicate
    seen = set()
    unique = []
    for c in cycles:
        key = tuple(c)
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique[:20]  # cap at 20 cycles


def _out_degrees(adj: dict[str, list[str]]) -> dict[str, int]:
    return {n: len(nbrs) for n, nbrs in adj.items()}


# ---------------------------------------------------------------------------
# profile loading — reuse the project's module_registry
# ---------------------------------------------------------------------------

def _load_profile(profile_name: str) -> dict:
    """Load a profile's full spec from module_registry.

    The MODULE_REGISTRY stores ModuleSpec dataclass instances keyed by
    module name (e.g. "sensory", "memory", "motor"). We convert the spec
    to a dict and extract the fields needed for health analysis.
    """
    try:
        from module_registry import MODULE_REGISTRY, ModuleFactory
        if profile_name not in MODULE_REGISTRY:
            # fallback: try ModuleFactory which may have more lookup paths
            try:
                return ModuleFactory.get_module(profile_name)
            except Exception:
                raise ValueError(
                    f"profile '{profile_name}' not found. "
                    f"Available: {', '.join(list(MODULE_REGISTRY.keys())[:10])} "
                    f"... ({len(MODULE_REGISTRY)} total)"
                )
        spec = MODULE_REGISTRY[profile_name]
        # convert dataclass to dict
        from dataclasses import asdict
        return asdict(spec)
    except ImportError:
        pass
    # fallback: direct JSON lookup
    data_dir = os.path.join(os.path.dirname(HERE), "data")
    profile_path = os.path.join(data_dir, "profiles", f"{profile_name}.json")
    if os.path.exists(profile_path):
        with open(profile_path, encoding="utf-8") as fh:
            return json.load(fh)
    raise ValueError(f"profile '{profile_name}' not found")


def _get_units(profile: dict) -> list[dict]:
    """Extract unit list from profile.

    Handles two schemas:
      1. Organism-level: has "units"/"modules"/"nodes" list
      2. Single-module spec (ModuleSpec from MODULE_REGISTRY): wrap in a list
    """
    for key in ("units", "modules", "nodes", "components"):
        if key in profile and isinstance(profile[key], list):
            return profile[key]
    # Single-module spec (ModuleSpec dataclass asdict) — wrap in list
    if "name" in profile and "connection_pattern" in profile:
        return [profile]
    return []


def _get_edges(profile: dict) -> list[tuple[str, str]]:
    """Extract edges from profile.

    Handles two schemas:
      1. Organism-level: explicit "edges"/"connections" list
      2. Single-module spec: derive from connection_pattern {inputs, outputs}
         — each input/output reference becomes a virtual edge from the
         module name.
    """
    edges_raw = profile.get("edges") or profile.get("connections") or []
    edges: list[tuple[str, str]] = []
    for e in edges_raw:
        if isinstance(e, dict):
            u = e.get("from") or e.get("source") or e.get("u") or ""
            v = e.get("to") or e.get("target") or e.get("v") or ""
            if u and v:
                edges.append((str(u), str(v)))
        elif isinstance(e, (list, tuple)) and len(e) >= 2:
            edges.append((str(e[0]), str(e[1])))

    # Single-module spec: derive edges from connection_pattern
    conn = profile.get("connection_pattern")
    if conn and isinstance(conn, dict) and not edges:
        mod_name = profile.get("name", "self")
        for inp in conn.get("inputs", []):
            if inp and inp != "external":
                edges.append((str(inp), str(mod_name)))
        for outp in conn.get("outputs", []):
            if outp:
                edges.append((str(mod_name), str(outp)))

    return edges


# ---------------------------------------------------------------------------
# core health metrics
# ---------------------------------------------------------------------------

def _compute_connectivity(nodes: list[str], edges: list[tuple[str, str]]) -> dict:
    """Metric 1: connectivity — # components, # nodes, fraction connected."""
    adj = _build_adjacency(edges)
    # ensure all nodes are in adj
    for n in nodes:
        adj.setdefault(n, [])
    components = _connected_components(nodes, adj)
    n_comp = len(components)
    largest = max(len(c) for c in components) if components else 0
    n_total = len(nodes)
    return {
        "n_nodes": n_total,
        "n_components": n_comp,
        "largest_component": largest,
        "fraction_connected": largest / n_total if n_total > 0 else 1.0,
    }


def _compute_evidence_ratio(units: list[dict]) -> dict:
    """Metric 2: evidence_ratio — fraction of units with real connectome anchor."""
    if not units:
        return {"evidence_ratio": 1.0, "n_evidence_anchored": 0, "n_total": 0}
    anchored = 0
    for u in units:
        provenance = u.get("provenance") or {}
        emb = u.get("embodiment") or u.get("embodiment_anchor") or {}
        # ModuleSpec fields that indicate evidence anchoring:
        #   motif_source  — trace to a real MaleCNS motif
        #   provenance    — explicit provenance block
        #   embodiment    — explicit embodiment anchor
        #   evidence_weight — explicit evidence weight
        has_anchor = bool(
            provenance.get("evidence_weight")
            or provenance.get("source")
            or emb.get("anchor")
            or emb.get("measured")
            or u.get("evidence_weight")
            or u.get("anchored")
            or u.get("motif_source")   # ModuleSpec: trace to MaleCNS motif
        )
        if has_anchor:
            anchored += 1
    ratio = anchored / len(units)
    return {
        "evidence_ratio": round(ratio, 4),
        "n_evidence_anchored": anchored,
        "n_total": len(units),
    }


def _compute_port_satisfaction(units: list[dict], edges: list[tuple[str, str]]) -> dict:
    """Metric 3: port_satisfaction — declared ports vs actual connections."""
    total_ports = 0
    satisfied_ports = 0
    for u in units:
        ports = u.get("ports") or []
        for p in ports:
            total_ports += 1
            # a port is "satisfied" if there's an edge referencing this unit
            unit_name = u.get("name") or u.get("id") or u.get("unit_id") or ""
            involved = any(unit_name in edge for edge in edges)
            if involved:
                satisfied_ports += 1
    ratio = satisfied_ports / total_ports if total_ports > 0 else 1.0
    return {
        "port_satisfaction": round(ratio, 4),
        "total_ports": total_ports,
        "satisfied_ports": satisfied_ports,
    }


def _compute_orphan_rate(units: list[dict], edges: list[tuple[str, str]]) -> dict:
    """Metric 4: orphan_rate — fraction of units with 0 connections."""
    if not units:
        return {"orphan_rate": 0.0, "n_orphans": 0, "n_total": 0}
    connected_names = set()
    for u, v in edges:
        connected_names.add(u)
        connected_names.add(v)
    orphans = 0
    for u in units:
        name = u.get("name") or u.get("id") or u.get("unit_id") or ""
        if name and name not in connected_names:
            orphans += 1
    rate = orphans / len(units)
    return {
        "orphan_rate": round(rate, 4),
        "n_orphans": orphans,
        "n_total": len(units),
    }


def _compute_cycle_count(nodes: list[str], edges: list[tuple[str, str]]) -> dict:
    """Metric 5: cycle_count — number of directed cycles (feedback loops)."""
    adj = _build_adjacency(edges)
    for n in nodes:
        adj.setdefault(n, [])
    cycles = _find_cycles(nodes, adj, max_depth=6)
    return {
        "n_cycles": len(cycles),
        "has_feedback": len(cycles) > 0,
    }


def _compute_hub_concentration(nodes: list[str], edges: list[tuple[str, str]]) -> dict:
    """Metric 6: hub_concentration — top-1 / top-5 out-degree ratio."""
    adj = _build_adjacency(edges)
    for n in nodes:
        adj.setdefault(n, [])
    degrees = _out_degrees(adj)
    sorted_degrees = sorted(degrees.values(), reverse=True)
    if not sorted_degrees or sum(sorted_degrees) == 0:
        return {"hub_concentration_top1": 0.0, "hub_concentration_top5": 0.0,
                "n_hubs": 0}
    total_deg = sum(sorted_degrees)
    top1 = sorted_degrees[0] / total_deg if total_deg > 0 else 0.0
    top5 = sum(sorted_degrees[:5]) / total_deg if total_deg > 0 else 0.0
    n_hubs = sum(1 for d in sorted_degrees if d > total_deg / len(sorted_degrees) * 2)
    return {
        "hub_concentration_top1": round(top1, 4),
        "hub_concentration_top5": round(top5, 4),
        "n_hubs": n_hubs,
    }


# ---------------------------------------------------------------------------
# composite degradation score
# ---------------------------------------------------------------------------

# Weights — evidence_ratio and connectivity are most important
# (they directly measure whether the profile is backed by real data and structurally coherent)
_WEIGHTS = {
    "evidence_ratio": 0.30,
    "fraction_connected": 0.25,
    "port_satisfaction": 0.15,
    "inverse_orphan_rate": 0.15,
    "inverse_hub_top1": 0.10,
    "cycle_presence": 0.05,
}


def _compute_degradation_score(metrics: dict) -> float:
    """Compute composite degradation score (0.0 = fully degraded, 1.0 = perfect)."""
    score = 0.0
    # evidence_ratio: higher is better
    score += _WEIGHTS["evidence_ratio"] * min(1.0, metrics.get("evidence_ratio", 0.0))
    # connectivity: higher fraction_connected is better
    score += _WEIGHTS["fraction_connected"] * min(1.0, metrics.get("fraction_connected", 0.0))
    # port_satisfaction: higher is better
    score += _WEIGHTS["port_satisfaction"] * min(1.0, metrics.get("port_satisfaction", 0.0))
    # inverse_orphan_rate: (1 - orphan_rate) is better
    orphan_rate = metrics.get("orphan_rate", 0.0)
    score += _WEIGHTS["inverse_orphan_rate"] * (1.0 - min(1.0, orphan_rate))
    # inverse_hub_top1: lower hub concentration is healthier
    # (for single-node profiles, hub concentration is meaningless — use 0.0)
    hub_top1 = metrics.get("hub_concentration_top1", 0.0)
    score += _WEIGHTS["inverse_hub_top1"] * (1.0 - min(1.0, hub_top1))
    # cycle_presence: having feedback is a small bonus (reservoir behavior)
    score += _WEIGHTS["cycle_presence"] * (1.0 if metrics.get("has_feedback") else 0.0)
    return round(min(1.0, max(0.0, score)), 4)


# ---------------------------------------------------------------------------
# main API
# ---------------------------------------------------------------------------

def profile_health(profile_name: str) -> dict:
    """
    Compute structural health metrics for a given profile.

    Args:
        profile_name: Name of the profile/unit to check (e.g. "perceive", "plan")

    Returns:
        {
            "profile": str,
            "health": {
                "connectivity": {...},
                "evidence": {...},
                "ports": {...},
                "orphans": {...},
                "cycles": {...},
                "hubs": {...},
            },
            "degradation_score": float,
            "status": "healthy" | "degraded" | "critical",
            "notes": [str, ...],
        }
    """
    try:
        profile = _load_profile(profile_name)
    except Exception as exc:
        return {
            "profile": profile_name,
            "error": str(exc),
            "degradation_score": 0.0,
            "status": "unknown",
            "notes": [f"failed to load profile: {exc}"],
        }

    units = _get_units(profile)
    edges = _get_edges(profile)
    node_names = []
    for u in units:
        name = u.get("name") or u.get("id") or u.get("unit_id")
        if name:
            node_names.append(str(name))

    # compute all metrics
    connectivity = _compute_connectivity(node_names, edges)
    evidence = _compute_evidence_ratio(units)
    ports = _compute_port_satisfaction(units, edges)
    orphans = _compute_orphan_rate(units, edges)
    cycles = _compute_cycle_count(node_names, edges)
    hubs = _compute_hub_concentration(node_names, edges)

    # composite score
    score = _compute_degradation_score({
        "evidence_ratio": evidence["evidence_ratio"],
        "fraction_connected": connectivity["fraction_connected"],
        "port_satisfaction": ports["port_satisfaction"],
        "orphan_rate": orphans["orphan_rate"],
        "hub_concentration_top1": hubs["hub_concentration_top1"],
        "has_feedback": cycles["has_feedback"],
    })

    # status classification
    if score >= 0.70:
        status = "healthy"
    elif score >= 0.40:
        status = "degraded"
    else:
        status = "critical"

    # diagnostic notes
    notes: list[str] = []
    if evidence["evidence_ratio"] < 0.5:
        notes.append(f"low evidence anchoring: {evidence['evidence_ratio']:.0%}")
    if connectivity["fraction_connected"] < 0.8:
        notes.append(f"poor connectivity: {connectivity['fraction_connected']:.0%} nodes in largest component")
    if orphans["orphan_rate"] > 0.3:
        notes.append(f"high orphan rate: {orphans['orphan_rate']:.0%} units disconnected")
    if hubs["hub_concentration_top1"] > 0.4:
        notes.append(f"hub-dependent: top-1 out-degree is {hubs['hub_concentration_top1']:.0%} of total")
    if not cycles["has_feedback"]:
        notes.append("no feedback loops detected (may lack reservoir dynamics)")

    return {
        "profile": profile_name,
        "health": {
            "connectivity": connectivity,
            "evidence": evidence,
            "ports": ports,
            "orphans": orphans,
            "cycles": cycles,
            "hubs": hubs,
        },
        "degradation_score": score,
        "status": status,
        "notes": notes,
    }


def health_summary(profiles: list[str]) -> dict:
    """
    Batch health check for multiple profiles.

    Returns:
        {
            "n_profiles": int,
            "mean_degradation_score": float,
            "by_status": {"healthy": N, "degraded": N, "critical": N},
            "results": [profile_health(...), ...],
        }
    """
    results = [profile_health(p) for p in profiles]
    scores = [r["degradation_score"] for r in results if "degradation_score" in r]
    by_status: dict[str, int] = {}
    for r in results:
        st = r.get("status", "unknown")
        by_status[st] = by_status.get(st, 0) + 1
    return {
        "n_profiles": len(profiles),
        "mean_degradation_score": round(sum(scores) / len(scores), 4) if scores else 0.0,
        "by_status": by_status,
        "results": results,
    }


def list_healthy_profiles(min_score: float = 0.5) -> list[dict]:
    """
    Scan all known profiles and return those above a health threshold.

    Returns list of {profile, degradation_score, status} sorted by score desc.
    """
    # try to enumerate profiles from module_registry
    profile_names: list[str] = []
    try:
        from module_registry import ModuleFactory
        # try common registry methods
        for attr in ("list_profiles", "all_profiles", "profile_names"):
            fn = getattr(ModuleFactory, attr, None)
            if callable(fn):
                result = fn()
                if isinstance(result, list):
                    for item in result:
                        if isinstance(item, str):
                            profile_names.append(item)
                        elif isinstance(item, dict):
                            name = item.get("name") or item.get("id") or ""
                            if name:
                                profile_names.append(name)
                    break
    except Exception:
        pass

    # fallback: scan profiles directory
    data_dir = os.path.join(os.path.dirname(HERE), "data", "profiles")
    if os.path.isdir(data_dir):
        for fname in os.listdir(data_dir):
            if fname.endswith(".json"):
                profile_names.append(fname.replace(".json", ""))

    # deduplicate
    seen = set()
    unique_names = []
    for n in profile_names:
        if n not in seen:
            seen.add(n)
            unique_names.append(n)

    results = []
    for name in unique_names:
        r = profile_health(name)
        if r.get("degradation_score", 0.0) >= min_score:
            results.append({
                "profile": name,
                "degradation_score": r["degradation_score"],
                "status": r["status"],
            })
    results.sort(key=lambda x: x["degradation_score"], reverse=True)
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Profile health checker")
    parser.add_argument("profile", nargs="?", help="Profile name to check")
    parser.add_argument("--batch", nargs="*", help="Batch check multiple profiles")
    parser.add_argument("--list-healthy", action="store_true",
                        help="List all profiles above health threshold")
    parser.add_argument("--min-score", type=float, default=0.5,
                        help="Minimum health score for --list-healthy")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    if args.batch:
        result = health_summary(args.batch)
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            _print_summary(result)
    elif args.list_healthy:
        results = list_healthy_profiles(min_score=args.min_score)
        if args.json:
            print(json.dumps(results, indent=2, default=str))
        else:
            print(f"{'Profile':<30} {'Score':<8} {'Status'}")
            print("-" * 50)
            for r in results:
                print(f"{r['profile']:<30} {r['degradation_score']:<8.4f} {r['status']}")
    elif args.profile:
        result = profile_health(args.profile)
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            _print_health(result)
    else:
        parser.print_help()


def _print_health(r: dict):
    print(f"\n=== Profile Health: {r['profile']} ===")
    print(f"Status: {r['status'].upper()}  |  Degradation Score: {r['degradation_score']:.4f}")
    h = r.get("health", {})
    conn = h.get("connectivity", {})
    ev = h.get("evidence", {})
    ports = h.get("ports", {})
    orph = h.get("orphans", {})
    cyc = h.get("cycles", {})
    hubs = h.get("hubs", {})
    print(f"\nConnectivity:  {conn.get('n_components', 0)} components, "
          f"{conn.get('fraction_connected', 0):.0%} in largest")
    print(f"Evidence:      {ev.get('evidence_ratio', 0):.0%} anchored "
          f"({ev.get('n_evidence_anchored', 0)}/{ev.get('n_total', 0)})")
    print(f"Ports:         {ports.get('satisfied_ports', 0)}/{ports.get('total_ports', 0)} satisfied")
    print(f"Orphans:       {orph.get('orphan_rate', 0):.0%} "
          f"({orph.get('n_orphans', 0)}/{orph.get('n_total', 0)})")
    print(f"Cycles:        {cyc.get('n_cycles', 0)} feedback loops")
    print(f"Hub dep:       top-1 = {hubs.get('hub_concentration_top1', 0):.0%}, "
          f"top-5 = {hubs.get('hub_concentration_top5', 0):.0%}")
    if r.get("notes"):
        print(f"\nNotes:")
        for n in r["notes"]:
            print(f"  • {n}")


def _print_summary(r: dict):
    print(f"\n=== Batch Health Summary ({r['n_profiles']} profiles) ===")
    print(f"Mean degradation score: {r['mean_degradation_score']:.4f}")
    print(f"By status: {r['by_status']}")
    print()
    for res in r["results"]:
        _print_health(res)


if __name__ == "__main__":
    main()
