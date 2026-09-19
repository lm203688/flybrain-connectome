"""
extract_motifs.py
-----------------
Extract reusable multi-agent topology MOTIFS from the real MaleCNS v1.0
connectome, so SwarmLabs (or any other project) can consume them as a
lightweight derived artifact WITHOUT embedding the 166,700-neuron raw data.

Output (single self-contained JSON):
    motifs/swarm_agent_topology_motifs.json

All numbers come from core.py query layer (which reads connectivity_facts.json
+ the indexed .npy cache). Nothing is synthesized.

Run:
    FLYBRAIN_DATA_DIR=<.../data/male_cns> python extract_motifs.py
"""
from __future__ import annotations
import os
import sys
import json
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "mcp_connectome"))
import core
import numpy as np

LOG = HERE.parent / "motif_extract.log"

def log(msg: str):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")
    print(msg, file=sys.stderr, flush=True)

def main():
    t0 = time.time()
    log("[extract] ensure_cache...")
    core.ensure_cache(False)
    f = core._STATE["facts"]
    ann_ids = core._STATE["ann_ids"]            # bodies with superclass (neuron subgraph)
    ann_set = set(int(b) for b in ann_ids)
    pre_s, w_s = core._STATE["pre_s"], core._STATE["w_s"]
    post_s2, w_s2 = core._STATE["post_s2"], core._STATE["w_s2"]

    out = {
        "schema_version": "1.0",
        "source": "MaleCNS v1.0 (male Drosophila brain connectome), license CC-BY",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "caveat": "Motifs are TOPOLOGY PATTERNS derived from real wiring; they are "
                  "descriptions, not the raw neuron data. The authoritative 166,700 "
                  "neurons live in flybrain-connectome-mcp (queried via MCP/HTTP API).",
    }

    # ---- dataset stats (real) ----
    ov = core.connectome_overview()
    out["dataset_stats"] = {
        "total_synapses": ov["total_synapses"],
        "annotated_neurons": ov["annotated_neurons"],
        "mean_fanout": round(ov["mean_fanout"], 2),
        "mean_fanin": round(ov["mean_fanin"], 2),
        "top_hubs": ov["top_hubs"],
    }
    log("[extract] dataset: synapses=%d neurons=%d" % (
        ov["total_synapses"], ov["annotated_neurons"]))

    # ---- degree distribution over neuron subgraph (real, computed) ----
    max_id = int(max(pre_s.max(), post_s2.max()))
    fo = np.bincount(pre_s.astype(np.int64), weights=w_s.astype(np.float64),
                     minlength=max_id + 1)
    fi = np.bincount(post_s2.astype(np.int64), weights=w_s2.astype(np.float64),
                     minlength=max_id + 1)
    fo_ann = fo[ann_ids]
    fi_ann = fi[ann_ids]
    buckets = [("1-10", 1, 10), ("11-100", 11, 100), ("101-1000", 101, 1000),
               ("1001-10000", 1001, 10000), ("10000+", 10001, 10**12)]
    fanout_dist, fanin_dist = {}, {}
    for name, lo, hi in buckets:
        fanout_dist[name] = int(((fo_ann >= lo) & (fo_ann <= hi)).sum())
        fanin_dist[name] = int(((fi_ann >= lo) & (fi_ann <= hi)).sum())
    n = len(ann_ids)
    fanout_pct = {k: round(100.0 * v / n, 2) for k, v in fanout_dist.items()}
    log("[extract] fanout 101-1000 share = %.2f%% (n=%d)" % (
        fanout_pct.get("101-1000", 0), n))

    # ---- MOTIF 1: inhibitory hub (APL broadcast) ----
    apl = None
    for h in f.get("top_hubs_with_targets", []):
        if "APL" in str(h.get("hub_type", "")).upper():
            apl = h
            break
    inhibitory = None
    if apl:
        apl_body = int(apl["hub_body"])
        afo, afi = core.degree(apl_body)
        info = core.neuron_info(apl_body) or {}
        outs = core.neuron_outputs(apl_body, top=15)
        targets = [{"body": b, "type": (core._STATE["ann"].get(b, {}).get("type") or ""),
                    "superclass": (core._STATE["ann"].get(b, {}).get("superclass") or ""),
                    "synapses": s} for b, s in outs]
        # DPM is the canonical APL target (mushroom-body feedback neuron)
        dpm_body = 12569
        apl_dpm = core.pair_synapses(apl_body, dpm_body)
        inhibitory = {
            "pattern": "inhibitory_hub",
            "biological_role": "Single GABAergic hub broadcasts inhibition to many "
                               "targets; acts as a global 'brake'/coordinator.",
            "hub_body": apl_body,
            "hub_type": apl.get("hub_type"),
            "hub_superclass": info.get("superclass", ""),
            "neurotransmitter": info.get("neurotransmitter", ""),
            "fan_out_synapses": afo,
            "fan_in_synapses": afi,
            "broadcast_targets": targets,
            "canonical_target": {"body": dpm_body,
                                 "type": (core._STATE["ann"].get(dpm_body, {}).get("type") or ""),
                                 "synapses": apl_dpm},
            "agent_mapping": {
                "role": "coordinator / guardrail agent",
                "rule": "One coordinator agent sends inhibitory (negative-weight) "
                        "edges to its top-K workers, weighted by synapses/normalized. "
                        "Prevents runaway/over-commit in the swarm.",
                "edge_weight_hint": "normalize each target's synapses by max target "
                                    "synapses -> inhibition strength in [0,1]."
            },
        }
        log("[extract] inhibitory hub APL body=%d fo=%d DPM_syn=%d" % (
            apl_body, afo, apl_dpm))
    else:
        log("[extract] WARNING: APL hub not found in facts; skipping inhibitory motif")

    # ---- MOTIF 2: reservoir / small-world (echo-state substrate) ----
    reservoir = {
        "pattern": "reservoir_smallworld",
        "biological_role": "Loosely-connected, small-world wiring gives a useful "
                           "memory spectrum and built-in regularization (thebuzz "
                           "finding: intact fly wiring > shuffled wiring as a reservoir).",
        "mean_fanout": round(ov["mean_fanout"], 2),
        "mean_fanin": round(ov["mean_fanin"], 2),
        "fanout_distribution_neurons": fanout_dist,
        "fanout_distribution_pct": fanout_pct,
        "dominant_bucket": max(fanout_pct, key=fanout_pct.get),
        "agent_mapping": {
            "role": "collective short-term memory / context buffer",
            "rule": "Instantiate a reservoir of K loosely-connected 'reservoir agents' "
                    "whose sparse connections are drawn from the observed fanout "
                    "distribution. A readout agent observes the reservoir state to "
                    "encode recent task context (echo-state / reservoir computing).",
            "build": "Sample each reservoir agent's out-degree from fanout_distribution; "
                     "wire targets uniformly at random among the K agents."
        },
    }

    # ---- MOTIF 3: recurrent feedback (self-loops per subsystem) ----
    self_loops = [c for c in f.get("cross_superclass_top", [])
                   if c.get("from") == c.get("to")]
    self_loops.sort(key=lambda c: c.get("pct_of_total", 0), reverse=True)
    recurrent = {
        "pattern": "recurrent_feedback",
        "biological_role": "Subsystems feed a fraction of their output back as input "
                           "(working-memory / stabilization loop).",
        "self_recurrence_top": [
            {"superclass": c["from"], "synapses": c["synapses"],
             "pct_of_total": round(c.get("pct_of_total", 0), 2)}
            for c in self_loops[:8]
        ],
        "agent_mapping": {
            "role": "module internal memory / stabilization",
            "rule": "For any functional module, connect its output back to its input "
                    "with recurrent weight = self_recurrence pct (normalized). Keeps "
                    "the module's prior state alive across steps without external storage."
        },
    }
    log("[extract] recurrent top: %s" % [c["from"] for c in self_loops[:3]])

    out["motifs"] = {}
    if inhibitory:
        out["motifs"]["inhibitory_hub"] = inhibitory
    out["motifs"]["reservoir_smallworld"] = reservoir
    out["motifs"]["recurrent_feedback"] = recurrent

    out["how_to_consume"] = {
        "keep_independence": "SwarmLabs stores ONLY this JSON; the 166,700 neurons stay "
                             "in flybrain-connectome-mcp. To refresh, call the MCP tool "
                             "hub_targets / neuron_outputs or re-run this script.",
        "refresh_command": "FLYBRAIN_DATA_DIR=<male_cns> python extract_motifs.py",
    }

    dest = HERE / "motifs" / "swarm_agent_topology_motifs.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    log("[extract] wrote %s in %.1fs" % (dest, time.time() - t0))
    log("[extract] DONE")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        log("[extract] ERROR: %r" % e)
        import traceback
        log(traceback.format_exc())
        sys.exit(2)
