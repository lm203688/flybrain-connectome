"""
topology_visualizer.py — v2.32.0

Generates zero-dependency SVG visualizations for the 12 composed
topologies produced across v2.7-v2.15, and aggregates them into a
single-file HTML dashboard (topology_overview.html).

Layout algorithm classifies each composition by its graph structure
(chain / tree_fanout / funnel / hierarchical / reciprocal / wide_fanout)
and picks a canonical layout per class — no matplotlib/graphviz, just
networkx + hand-written SVG.

Usage:
    python topology_visualizer.py                  # writes SVGs + HTML
    python topology_visualizer.py --out <dir>      # custom output dir

Zero external deps beyond stdlib + networkx (already required by the
compositions modules).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

# --- paths / imports ------------------------------------------------------

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))

import networkx as nx  # noqa: E402

from topology_capacity_experiment import ALL_COMPOSITIONS  # noqa: E402
from tree_fanout_variants_experiment import VARIANT_COMPOSITIONS  # noqa: E402


# =========================================================================== #
# Topology classification & layout
# =========================================================================== #

def _classify(name: str, G: nx.DiGraph) -> str:
    """Pick a layout class from the graph structure (structure-first,
    name-fallback for edge cases)."""
    n = G.number_of_nodes()
    e = G.number_of_edges()
    if n == 0:
        return "chain"

    has_cycle = not nx.is_directed_acyclic_graph(G)

    # Wide fanout: at least one node with out_degree >= 3, and total
    # out-edge-count from hub exceeds the number of distinct target nodes
    # (i.e. hub's OUT port is reused across multiple downstream).
    out_deg = dict(G.out_degree())
    max_out = max(out_deg.values()) if out_deg else 0
    if max_out >= 4:
        return "wide_fanout"

    # Funnel: single sink with in_degree >= 3
    in_deg = dict(G.in_degree())
    max_in = max(in_deg.values()) if in_deg else 0
    if max_in >= 3 and n >= 4:
        # Only funnel if NOT a pure chain
        sinks = [v for v, d in in_deg.items() if d == max_in]
        sources = [v for v, d in in_deg.items() if d == 0]
        if max_in >= 3 and len(sources) >= 3:
            return "funnel"

    # Tree fanout: single root with out_degree >= 3 (and no cycle)
    if max_out >= 3 and not has_cycle and n >= 4:
        roots = [v for v, d in out_deg.items() if d == max_out]
        if len(roots) == 1:
            return "tree_fanout"

    # Reciprocal: has a strongly-connected cycle involving >= 2 nodes
    if has_cycle and len(list(nx.simple_cycles(G))) > 0:
        return "reciprocal"

    # Hierarchical: DAG whose longest simple path has >= 4 nodes
    if not has_cycle and e >= 3:
        try:
            topo = list(nx.topological_sort(G))
            sources = [v for v, d in G.in_degree() if d == 0]
            sinks = [v for v, d in G.out_degree() if d == 0]
            longest_len = 0
            for s in sources:
                for t in sinks:
                    for p in nx.all_simple_paths(G, s, t, cutoff=n):
                        if len(p) > longest_len:
                            longest_len = len(p)
            if longest_len >= 4 and max(in_deg.values()) >= 1 and max(out_deg.values()) >= 1:
                return "hierarchical"
        except Exception:
            pass

    # Default: chain
    return "chain"


def _layout(name: str, topo_type: str, G: nx.DiGraph,
            W: int = 480, H: int = 320) -> dict[str, tuple[float, float]]:
    """Return {node_id: (x, y)} for each layout class.

    Coordinate system: origin top-left; SVG y grows downward.
    """
    nodes = list(G.nodes())
    n = len(nodes)
    if n == 0:
        return {}

    # --- chain: horizontal left->right -----------------------------------
    if topo_type == "chain":
        # Follow longest simple path
        try:
            longest = max(nx.all_simple_paths(G), key=len)
        except Exception:
            longest = nodes
        pad = 60
        xs = {v: pad + i * (W - 2 * pad) / max(1, len(longest) - 1)
              for i, v in enumerate(longest)}
        # Stragglers (not on the longest path) go below
        rest = [v for v in nodes if v not in xs]
        for j, v in enumerate(rest):
            xs[v] = (pad + j * 80, H - 60)
        return {v: (xs[v], H / 2) if isinstance(xs[v], (int, float))
                else (xs[v][0], H / 2) for v in nodes}

    # --- tree_fanout: root top, leaves bottom ---------------------------
    if topo_type == "tree_fanout":
        root = max(nodes, key=lambda v: G.out_degree(v))
        leaves = [v for v in nodes if v != root]
        pos = {root: (W / 2, 60)}
        n_leaves = max(1, len(leaves))
        pad = 70
        for i, v in enumerate(leaves):
            x = pad + i * (W - 2 * pad) / max(1, n_leaves - 1) if n_leaves > 1 else W / 2
            pos[v] = (x, H - 70)
        return pos

    # --- funnel: sources top, sink bottom -------------------------------
    if topo_type == "funnel":
        sink = max(nodes, key=lambda v: G.in_degree(v))
        sources = [v for v in nodes if v != sink]
        pos = {sink: (W / 2, H - 60)}
        pad = 70
        n_src = max(1, len(sources))
        for i, v in enumerate(sources):
            x = pad + i * (W - 2 * pad) / max(1, n_src - 1) if n_src > 1 else W / 2
            pos[v] = (x, 60)
        return pos

    # --- hierarchical: topological layers -------------------------------
    if topo_type == "hierarchical":
        try:
            ranks = dict(nx.topological_generations(G))
            layers = list(nx.topological_generations(G))
        except Exception:
            layers = [[v] for v in nodes]
        n_layers = max(1, len(layers))
        pos = {}
        for li, layer in enumerate(layers):
            y = 60 + li * (H - 120) / max(1, n_layers - 1)
            pad = 70
            n_in = len(layer)
            for i, v in enumerate(layer):
                x = pad + i * (W - 2 * pad) / max(1, n_in - 1) if n_in > 1 else W / 2
                pos[v] = (x, y)
        return pos

    # --- wide_fanout: hub center-top, many downstream ------------------
    if topo_type == "wide_fanout":
        hub = max(nodes, key=lambda v: G.out_degree(v))
        downstream = [v for v in nodes if v != hub]
        pos = {hub: (W / 2, 50)}
        pad = 60
        n_d = max(1, len(downstream))
        for i, v in enumerate(downstream):
            x = pad + i * (W - 2 * pad) / max(1, n_d - 1)
            pos[v] = (x, H - 60)
        return pos

    # --- reciprocal: ring layout ---------------------------------------
    if topo_type == "reciprocal":
        # Follow the longest cycle if one exists
        cycles = list(nx.simple_cycles(G))
        if cycles:
            longest = max(cycles, key=len)
        else:
            longest = nodes
        n_c = max(1, len(longest))
        cx, cy, r = W / 2, H / 2, min(W, H) / 2 - 70
        pos = {}
        for i, v in enumerate(longest):
            theta = -math.pi / 2 + i * 2 * math.pi / n_c
            pos[v] = (cx + r * math.cos(theta), cy + r * math.sin(theta))
        # Extra nodes outside the ring
        rest = [v for v in nodes if v not in pos]
        for j, v in enumerate(rest):
            pos[v] = (60 + j * 80, H - 40)
        return pos

    # Fallback: grid
    return {v: (60 + i * 60, 60 + (i // 4) * 60) for i, v in enumerate(nodes)}


# =========================================================================== #
# SVG rendering
# =========================================================================== #

UNIT_LABELS = {
    "hypothalamic_arousal_unit": "HY (hypothalamus)",
    "cortical_l23_association_unit": "L2/3 (cortex assoc.)",
    "cortical_highorder_integration_unit": "HO (cortex hi.)",
    "cortical_inhibitory_gain_unit": "INH (cortex inh.)",
    "central_complex_steering_unit": "CC-Steer (drosophila)",
    "antennal_lobe_glomerular_unit": "AL-GLM (drosophila)",
    "mushroom_body_associative_memory_unit": "MB-AM (drosophila)",
    "mushroom_body_sparse_code_unit": "MB-SC (drosophila)",
    "compound_lamina_relay_unit": "Lam (drosophila)",
    "elementary_motion_detection_unit": "EMD (drosophila)",
    "visual_target_detection_unit": "VTD",
    "looming_detection_unit": "LPI (drosophila)",
    "winner_take_all_unit": "WTA",
    "spinal_reflex_arc_unit": "SpReflex",
    "spinal_cpg_unit": "SpCPG",
    "pharyngeal_gustatory_unit": "PhGus",
    "cholinergic_arousal_unit": "Chol-Arouse",
}


def _short_label(unit_name: str) -> str:
    """Truncate the long unit id to a display label."""
    if unit_name in UNIT_LABELS:
        return UNIT_LABELS[unit_name]
    # Fallback: take first two underscore-separated tokens
    parts = unit_name.replace("_unit", "").split("_")
    abbr = "".join(p[:2].upper() for p in parts[:3])
    return abbr


SYSTEM_COLORS = {
    "drosophila": "#7aa6d9",  # blue
    "mammalian":  "#d97a7a",  # red
    "invertebrate": "#7ad97a",  # green
    "abstract":   "#c9c9c9",  # gray
}


def _system_of(unit_name: str) -> str:
    """Very cheap system heuristic — drosophila units all carry
    '_unit' with drosophila-only names (antennal_lobe, mushroom_body,
    lamina, looming, etc.); others are mammalian/invertebrate/abstract."""
    drosophila_markers = [
        "antennal_lobe", "mushroom_body", "lamina", "looming",
        "compound_lamina", "central_complex", "pharyngeal_gustatory",
        "elementary_motion",
    ]
    for m in drosophila_markers:
        if m in unit_name:
            return "drosophila"
    if "spinal" in unit_name or "cpg" in unit_name:
        return "invertebrate"
    if "cortical" in unit_name or "hypothalamic" in unit_name or "wta" in unit_name:
        return "mammalian"
    return "abstract"


def render_svg(name: str, nodes: list[dict], edges: list[dict],
               pos: dict[str, tuple[float, float]],
               W: int = 480, H: int = 320) -> str:
    """Emit a self-contained SVG string for one composition.

    - nodes: [{'id': ..., 'unit': ...}, ...]
    - edges: [{'from': ..., 'to': ...}, ...]
    - pos: {node_id: (x, y)}
    """
    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'width="100%" height="100%" style="font-family: system-ui, -apple-system, sans-serif;">'
    )
    # Arrowhead marker
    parts.append(
        '<defs>'
        '<marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="8" markerHeight="8" orient="auto-start-reverse">'
        '<path d="M0,0 L10,5 L0,10 z" fill="#334155"/></marker>'
        '</defs>'
    )
    # Background
    parts.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="#f8fafc"/>')

    # Edges (draw before nodes so nodes sit on top)
    r = 26  # node radius
    for e in edges:
        src, dst = e["from"], e["to"]
        if src not in pos or dst not in pos:
            continue
        x1, y1 = pos[src]
        x2, y2 = pos[dst]
        # Shorten endpoints to node circle boundary
        dx, dy = x2 - x1, y2 - y1
        dist = (dx * dx + dy * dy) ** 0.5
        if dist == 0:
            continue
        ux, uy = dx / dist, dy / dist
        sx, sy = x1 + ux * r, y1 + uy * r
        ex, ey = x2 - ux * r, y2 - uy * r
        parts.append(
            f'<line x1="{sx:.1f}" y1="{sy:.1f}" x2="{ex:.1f}" y2="{ey:.1f}" '
            f'stroke="#334155" stroke-width="1.6" marker-end="url(#ah)"/>'
        )

    # Nodes
    for n in nodes:
        nid = n["id"]
        if nid not in pos:
            continue
        x, y = pos[nid]
        sys = _system_of(n.get("unit", nid))
        color = SYSTEM_COLORS.get(sys, SYSTEM_COLORS["abstract"])
        # circle + border
        parts.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{color}" '
            f'stroke="#0f172a" stroke-width="1.5" opacity="0.85"/>'
        )
        # label — up to 2 lines
        short = _short_label(n.get("unit", nid))
        lines = []
        # Split into <=9 chars per line, max 2 lines
        if len(short) <= 9:
            lines = [short]
        elif " " in short:
            head, tail = short.split(" ", 1)
            if len(tail) > 9:
                tail = tail[:9]
            lines = [head, tail]
        else:
            lines = [short[:9], short[9:18] if len(short) > 9 else ""]
        for i, line in enumerate(lines):
            dy = -3 if i == 0 else 10
            if len(lines) == 1:
                dy = 4
            parts.append(
                f'<text x="{x:.1f}" y="{y + dy:.1f}" text-anchor="middle" '
                f'font-size="10" fill="#0f172a" font-weight="600">'
                f'{line}</text>'
            )

    # Title
    parts.append(
        f'<text x="12" y="20" font-size="13" fill="#0f172a" font-weight="700">{name}</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts)


# =========================================================================== #
# Data aggregation: pull MSE/conv/bonferroni per composition
# =========================================================================== #

def _load_performance() -> dict[str, dict]:
    """Load MSE + conv90 + Bonferroni verdict per composition from
    topology_capacity_results.json, tree_fanout_variants_results.json,
    tree_fanout_variants_n50_results.json (prefer n=50 data where
    available)."""
    perf: dict[str, dict] = {}

    # v2.12.0 topology capacity: 7 compositions × 2 sizes
    tc_path = HERE / "topology_capacity_results.json"
    if tc_path.exists():
        tc = json.loads(tc_path.read_text(encoding="utf-8"))
        for m in tc.get("compositions_measured", []):
            key = m["composition"]
            N = m["N"]
            entry = perf.setdefault(key, {})
            entry[f"narma10_mse@N{N}"] = m.get("narma10_mse")
            entry[f"conv90@N{N}"] = m.get("convergence_90")
            entry[f"memory@N{N}"] = m.get("memory_eff_depth")
            entry["n_seeds_v212"] = tc.get("n_seeds_per_metric") or tc.get("n_seeds_narma10")

    # v2.13.0 variants (n=10)
    tf_path = HERE / "tree_fanout_variants_results.json"
    if tf_path.exists():
        tf = json.loads(tf_path.read_text(encoding="utf-8"))
        for m in tf.get("variants_measured", []):
            key = m["variant"]
            N = m["N"]
            entry = perf.setdefault(key, {})
            entry[f"narma10_mse@N{N}_n10"] = m.get("narma10_mse")
            entry[f"conv90@N{N}_n10"] = m.get("convergence_90")
            entry["n_seeds_v213"] = tf.get("n_seeds")

    # v2.15.0 variants (n=50, authoritative)
    tf50_path = HERE / "tree_fanout_variants_n50_results.json"
    if tf50_path.exists():
        tf50 = json.loads(tf50_path.read_text(encoding="utf-8"))
        for m in tf50.get("variants_measured", []):
            key = m["variant"]
            N = m["N"]
            entry = perf.setdefault(key, {})
            entry[f"narma10_mse@N{N}"] = m.get("narma10_mse")
            entry[f"conv90@N{N}"] = m.get("convergence_90")
            entry["n_seeds_v215"] = tf50.get("n_seeds")

    # Bonferroni verdicts from claims_audit.json (prefer latest)
    ca_path = HERE / "claims_audit.json"
    if ca_path.exists():
        ca = json.loads(ca_path.read_text(encoding="utf-8"))
        # index surviving verdicts by composition name (as "a")
        for row in ca.get("rows", []):
            a = row.get("a") or ""
            if row.get("survives_bonferroni"):
                entry = perf.setdefault(a, {})
                metric = row.get("metric") or "narma10"
                entry.setdefault("bonferroni_survived", []).append({
                    "metric": metric,
                    "p": row.get("welch_p"),
                    "d": row.get("cohens_d"),
                    "n": row.get("n_seeds"),
                    "version": row.get("version"),
                })
    return perf


# =========================================================================== #
# HTML dashboard assembly
# =========================================================================== #

DASHBOARD_CSS = """
* { box-sizing: border-box; }
body {
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  margin: 0; padding: 24px;
  background: #f1f5f9;
  color: #0f172a;
  line-height: 1.5;
}
header {
  max-width: 1280px;
  margin: 0 auto 24px;
  padding: 24px;
  background: #ffffff;
  border-left: 6px solid #3b82f6;
  box-shadow: 0 1px 3px rgba(15,23,42,0.08);
}
header h1 {
  margin: 0 0 8px;
  font-size: 22px;
  font-weight: 700;
}
header p {
  margin: 4px 0;
  color: #475569;
  font-size: 14px;
}
header .badges {
  margin-top: 12px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
header .badge {
  padding: 4px 10px;
  font-size: 12px;
  border-radius: 12px;
  background: #dbeafe;
  color: #1e40af;
  font-weight: 600;
}
header .badge.warn { background: #fef3c7; color: #92400e; }
header .badge.ok { background: #dcfce7; color: #166534; }

.legend {
  max-width: 1280px;
  margin: 0 auto 20px;
  padding: 12px 16px;
  background: #ffffff;
  border-radius: 6px;
  font-size: 13px;
  display: flex;
  gap: 20px;
  align-items: center;
  flex-wrap: wrap;
}
.legend-item { display: flex; align-items: center; gap: 6px; }
.legend-dot {
  width: 12px; height: 12px; border-radius: 50%;
  border: 1.5px solid #0f172a;
}

.grid {
  max-width: 1280px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(500px, 1fr));
  gap: 16px;
}
.card {
  background: #ffffff;
  border-radius: 8px;
  padding: 12px;
  box-shadow: 0 1px 3px rgba(15,23,42,0.08);
  display: flex;
  flex-direction: column;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 8px;
}
.card-title {
  font-size: 14px;
  font-weight: 700;
}
.card-type {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  background: #e0e7ff;
  color: #3730a3;
  font-weight: 600;
}
.card-type.bad { background: #fee2e2; color: #991b1b; }
.card-type.ok { background: #dcfce7; color: #166534; }
.card-type.warn { background: #fef3c7; color: #92400e; }

.card-svg {
  background: #f8fafc;
  border-radius: 4px;
  overflow: hidden;
}
.card-stats {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #e2e8f0;
  font-size: 12px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px 12px;
}
.stat { display: flex; justify-content: space-between; }
.stat-k { color: #64748b; }
.stat-v { font-weight: 600; font-variant-numeric: tabular-nums; }
.stat-v.good { color: #166534; }
.stat-v.bad { color: #991b1b; }
.card-note {
  margin-top: 6px;
  font-size: 11px;
  color: #475569;
  font-style: italic;
}

footer {
  max-width: 1280px;
  margin: 24px auto 0;
  padding: 12px 20px;
  background: #ffffff;
  border-radius: 6px;
  font-size: 12px;
  color: #475569;
}
"""


TYPE_BADGES = {
    "chain":          ("linear chain",       "warn"),
    "tree_fanout":    ("tree fanout",        "ok"),
    "funnel":         ("converging funnel",  "warn"),
    "hierarchical":   ("hierarchical",       "warn"),
    "reciprocal":     ("reciprocal feedback","warn"),
    "wide_fanout":    ("wide fanout",        "bad"),
}


def build_dashboard(cards: list[dict], meta: dict) -> str:
    """Assemble the full HTML dashboard from a list of SVG cards."""
    html_parts: list[str] = []
    html_parts.append("<!DOCTYPE html>")
    html_parts.append('<html lang="en">')
    html_parts.append('<head>')
    html_parts.append('<meta charset="utf-8"/>')
    html_parts.append('<meta name="viewport" content="width=device-width, initial-scale=1"/>')
    html_parts.append(f"<title>{meta['title']}</title>")
    html_parts.append(f"<style>{DASHBOARD_CSS}</style>")
    html_parts.append("</head>")
    html_parts.append("<body>")

    # Header
    html_parts.append("<header>")
    html_parts.append(f"<h1>{meta['title']}</h1>")
    html_parts.append(f"<p>{meta['subtitle']}</p>")
    html_parts.append("<div class='badges'>")
    for b in meta.get("badges", []):
        cls = f"badge {b['kind']}" if b["kind"] != "default" else "badge"
        html_parts.append(f"<span class='{cls}'>{b['text']}</span>")
    html_parts.append("</div>")
    html_parts.append("</header>")

    # Legend
    html_parts.append("<div class='legend'>")
    for label, color in [
        ("drosophila", "#7aa6d9"),
        ("mammalian",  "#d97a7a"),
        ("invertebrate", "#7ad97a"),
        ("abstract",   "#c9c9c9"),
    ]:
        html_parts.append(
            f"<div class='legend-item'>"
            f"<span class='legend-dot' style='background:{color}'></span>"
            f"<span>{label}</span></div>"
        )
    html_parts.append("</div>")

    # Grid
    html_parts.append("<div class='grid'>")
    for c in cards:
        topo_type = c["topo_type"]
        badge_label, badge_class = TYPE_BADGES.get(topo_type, ("graph", "warn"))
        html_parts.append("<div class='card'>")
        html_parts.append("<div class='card-header'>")
        html_parts.append(f"<span class='card-title'>{c['name']}</span>")
        html_parts.append(f"<span class='card-type {badge_class}'>{badge_label}</span>")
        html_parts.append("</div>")
        html_parts.append("<div class='card-svg'>")
        html_parts.append(c["svg"])
        html_parts.append("</div>")
        html_parts.append("<div class='card-stats'>")
        # Stats rows
        n_nodes = c.get("n_nodes") or "?"
        n_edges = c.get("n_edges") or "?"
        html_parts.append(f"<div class='stat'><span class='stat-k'>nodes</span><span class='stat-v'>{n_nodes}</span></div>")
        html_parts.append(f"<div class='stat'><span class='stat-k'>edges</span><span class='stat-v'>{n_edges}</span></div>")
        for key, label in [
            ("narma10_mse@N60",   "MSE@N60"),
            ("narma10_mse@N200",  "MSE@N200"),
            ("conv90@N60",        "conv@N60"),
            ("conv90@N200",       "conv@N200"),
        ]:
            v = c["stats"].get(key)
            if v is None:
                continue
            html_parts.append(
                f"<div class='stat'><span class='stat-k'>{label}</span>"
                f"<span class='stat-v'>{v:.4f}</span></div>"
            )
        html_parts.append("</div>")
        # Verdict / note
        verdicts = c["stats"].get("bonferroni_survived", [])
        if verdicts:
            v0 = verdicts[-1]
            note = (
                f"✅ Bonferroni survivor on {v0['metric']} "
                f"(p={v0['p']}, d={v0['d']:+.3f}, n={v0['n']}, v{v0['version']})"
            )
            html_parts.append(f"<div class='card-note'>{note}</div>")
        elif c.get("verdict_note"):
            html_parts.append(f"<div class='card-note'>{c['verdict_note']}</div>")
        html_parts.append("</div>")

    html_parts.append("</div>")  # grid

    # Footer
    html_parts.append("<footer>")
    html_parts.append(f"Generated by <code>topology_visualizer.py</code> · flybrain-connectome v2.32.0 · {meta['generated_at']}")
    html_parts.append("</footer>")

    html_parts.append("</body>")
    html_parts.append("</html>")
    return "\n".join(html_parts)


# =========================================================================== #
# Main entry
# =========================================================================== #

def _all_compositions() -> list[tuple[str, callable]]:
    """Yield (name, builder_fn) for every distinct composition we have."""
    seen: dict[str, callable] = {}
    for name, fn in ALL_COMPOSITIONS.items():
        seen[name] = fn
    for name, fn in VARIANT_COMPOSITIONS.items():
        # Skip if identical to an existing entry by identity
        if name not in seen:
            seen[name] = fn
    return list(seen.items())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None,
                    help="Output directory (default: alongside this script)")
    args = ap.parse_args()
    out_dir = Path(args.out) if args.out else HERE
    out_dir.mkdir(parents=True, exist_ok=True)

    import time
    t0 = time.time()

    perf = _load_performance()

    cards: list[dict] = []
    total = 0
    for name, fn in _all_compositions():
        comp = fn()
        organism = comp["organism"]
        nodes = organism["nodes"]
        edges = organism["edges"]

        G = nx.DiGraph()
        G.add_nodes_from(n["id"] for n in nodes)
        G.add_edges_from((e["from"], e["to"]) for e in edges)

        topo_type = _classify(name, G)
        pos = _layout(name, topo_type, G)
        svg = render_svg(name, nodes, edges, pos)

        stats = perf.get(name, {})
        # Add verdict note for common cases
        verdict_note = ""
        if name == "tree_fanout" and "bonferroni_survived" not in stats:
            verdict_note = "v2.12.0 local optimum of composed topologies; adding edges never improves NARMA-10."
        elif name == "tree_fanout_ref" and "bonferroni_survived" not in stats:
            verdict_note = "v2.13.0 reference variant (identical topology to tree_fanout). Baseline for 4 variant comparisons."
        elif name == "tree_fanout_extended_chain" and "bonferroni_survived" in stats:
            verdict_note = "v2.15.0 P0: n_seeds=50 confirms WORSE scaling under Bonferroni."

        cards.append({
            "name": name,
            "topo_type": topo_type,
            "svg": svg,
            "n_nodes": len(nodes),
            "n_edges": len(edges),
            "stats": stats,
            "verdict_note": verdict_note,
        })
        total += 1

    # Also emit individual SVG files
    for c in cards:
        safe = c["name"].replace("/", "_")
        svg_path = out_dir / f"svg_{safe}.svg"
        svg_path.write_text(c["svg"], encoding="utf-8")

    # Dashboard metadata
    import datetime
    meta = {
        "title": "Composed Topology Atlas · flybrain-connectome v2.32.0",
        "subtitle": "12 composed topologies produced across v2.7–v2.15, classified by graph structure, "
                    "annotated with NARMA-10 MSE, convergence_90 steps, and Bonferroni-surviving verdicts. "
                    "Generated with zero external deps (networkx + hand-written SVG).",
        "badges": [
            {"text": f"{total} compositions", "kind": "default"},
            {"text": "119 meta-analyzed comparisons", "kind": "default"},
            {"text": "7 Bonferroni survivors", "kind": "ok"},
            {"text": "5 sample-bias retractions", "kind": "warn"},
        ],
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }

    html = build_dashboard(cards, meta)
    out_html = out_dir / "topology_overview.html"
    out_html.write_text(html, encoding="utf-8")

    print(f"Wrote: {out_html}  ({out_html.stat().st_size:,} bytes)")
    print(f"Wrote {total} SVG files to {out_dir}/")
    print(f"Elapsed: {time.time()-t0:.2f}s")
    print()
    print("Layout classification:")
    counts: dict[str, int] = {}
    for c in cards:
        counts[c["topo_type"]] = counts.get(c["topo_type"], 0) + 1
    for k, v in sorted(counts.items()):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
