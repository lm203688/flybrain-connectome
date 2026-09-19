"""
drosophila_connectome / core.py
--------------------------------
In-memory indexed query layer over the MaleCNS v1.0 connectome.

Design
------
* The 1.8 GB connectome-weights feather (151,856,684 directed edges) is converted
  ONCE into six memory-mapped-friendly .npy arrays, sorted two ways:
    - by presynaptic body  (pre_s, post_s, w_s)
    - by postsynaptic body (pre_s2, post_s2, w_s2)
  This lets any single-neuron query (outputs / inputs / degree / pair) resolve in
  O(log n) via np.searchsorted + a small slice aggregation.
* Annotations + neurotransmitter predictions are flattened into two JSON dicts
  (bodyId -> metadata / bodyId -> consensus neurotransmitter).
* Aggregate facts (superclass projections, hub targets, degree distribution) are
  read from the precomputed connectivity_facts.json so they never need a full scan.

All numbers are real and traceable to the published MaleCNS v1.0 dataset
(Schlegel et al., 2026, CC-BY). No values are synthesized.
"""

from __future__ import annotations
import os
import sys
import json
import time
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
# Data location is configurable so this package can live in its own project
# while the (large) connectome data stays wherever it was downloaded.
# Set FLYBRAIN_DATA_DIR to the `.../data/male_cns` directory to relocate data.
DATA_DIR = Path(os.environ.get(
    "FLYBRAIN_DATA_DIR", str(HERE.parent / "data" / "male_cns"))).resolve()
FLAT = DATA_DIR / "flat-connectome"
CACHE = DATA_DIR / "connectome_cache"

CW_FEATHER = FLAT / "connectome-weights-male-cns-v1.0-minconf-0.5.feather"
ANN_FEATHER = FLAT / "body-annotations-male-cns-v1.0-minconf-0.5.feather"
NT_FEATHER = FLAT / "body-neurotransmitters-male-cns-v1.0.feather"
FACTS = DATA_DIR / "connectivity_facts.json"

_ANN_COLS = [
    "bodyId", "type", "superclass", "supertype", "subclass",
    "statusLabel", "somaSide", "somaNeuromere", "instance", "vfbId",
    "status", "flywireType",
]

_STATE: dict = {}


# --------------------------------------------------------------------------- #
# Cache build / load
# --------------------------------------------------------------------------- #
def _np_path(name: str) -> Path:
    return CACHE / (name + ".npy")


def ensure_cache(verbose: bool = True) -> None:
    """Build .npy cache if missing, then load everything into _STATE."""
    if _STATE.get("loaded"):
        return
    CACHE.mkdir(parents=True, exist_ok=True)

    need = ["pre_s", "post_s", "w_s", "pre_s2", "post_s2", "w_s2"]
    if any(not _np_path(n).exists() for n in need):
        _build_arrays(verbose)

    if verbose:
        print("[core] loading indexed arrays...", file=sys.stderr, flush=True)
    _STATE["pre_s"] = np.load(_np_path("pre_s"))
    _STATE["post_s"] = np.load(_np_path("post_s"))
    _STATE["w_s"] = np.load(_np_path("w_s"))
    _STATE["pre_s2"] = np.load(_np_path("pre_s2"))
    _STATE["post_s2"] = np.load(_np_path("post_s2"))
    _STATE["w_s2"] = np.load(_np_path("w_s2"))
    _STATE["ann"] = _load_ann(CACHE)
    _STATE["nt"] = _load_nt(CACHE)
    # "Neuron subgraph" = bodies with a non-null superclass annotation, matching
    # the scope used when connectivity_facts.json was precomputed.
    neuron_ids = [b for b, r in _STATE["ann"].items() if r.get("superclass")]
    _STATE["ann_ids"] = np.array(sorted(neuron_ids), dtype=np.int32)
    _STATE["facts"] = json.load(open(FACTS, encoding="utf-8"))
    _STATE["loaded"] = True
    if verbose:
        print("[core] ready. neurons≈%d edges=%d" % (
            len(_STATE["ann"]), len(_STATE["pre_s"])), file=sys.stderr, flush=True)


def _build_arrays(verbose: bool = True) -> None:
    import pyarrow.feather as feather
    if verbose:
        print("[cache] reading connectome-weights feather...", file=sys.stderr, flush=True)
    t0 = time.time()
    t = feather.read_table(str(CW_FEATHER), columns=["body_pre", "body_post", "weight"])
    pre = t.column("body_pre").to_numpy().astype(np.int64)
    post = t.column("body_post").to_numpy().astype(np.int64)
    w = t.column("weight").to_numpy().astype(np.int64)
    if verbose:
        print("[cache] rows=%d  sorting by presynaptic body..." % len(pre),
              file=sys.stderr, flush=True)
    op = np.argsort(pre, kind="stable")
    pre_s = pre[op].astype(np.int32)
    post_s = post[op].astype(np.int32)
    w_s = w[op].astype(np.int32)
    if verbose:
        print("[cache] sorting by postsynaptic body...", file=sys.stderr, flush=True)
    op2 = np.argsort(post, kind="stable")
    pre_s2 = pre[op2].astype(np.int32)
    post_s2 = post[op2].astype(np.int32)
    w_s2 = w[op2].astype(np.int32)
    del pre, post, w, op, op2
    for name, arr in [
        ("pre_s", pre_s), ("post_s", post_s), ("w_s", w_s),
        ("pre_s2", pre_s2), ("post_s2", post_s2), ("w_s2", w_s2),
    ]:
        np.save(_np_path(name), arr)
    if verbose:
        print("[cache] arrays saved in %.1fs" % (time.time() - t0),
              file=sys.stderr, flush=True)


def _load_ann(cache: Path) -> dict:
    p = cache / "annotations.json"
    if p.exists():
        # JSON serializes int keys as strings; coerce back to int.
        return {int(k): v for k, v in json.load(open(p, encoding="utf-8")).items()}
    import pyarrow.feather as feather
    t = feather.read_table(str(ANN_FEATHER))
    cols = [c for c in _ANN_COLS if c in t.schema.names]
    rows = t.select(cols).to_pylist()
    d: dict = {}
    for r in rows:
        bid = r.get("bodyId")
        if bid is None:
            continue
        d[int(bid)] = {
            k: (r.get(k) if r.get(k) is not None else "")
            for k in cols if k != "bodyId"
        }
    json.dump(d, open(p, "w", encoding="utf-8"))
    return d


def _load_nt(cache: Path) -> dict:
    p = cache / "nt.json"
    if p.exists():
        return json.load(open(p, encoding="utf-8"))
    import pyarrow.feather as feather
    t = feather.read_table(str(NT_FEATHER), columns=["body", "consensus_nt"])
    d = {int(r["body"]): (r.get("consensus_nt") or "") for r in t.to_pylist()}
    json.dump(d, open(p, "w", encoding="utf-8"))
    return d


# --------------------------------------------------------------------------- #
# Low-level helpers
# --------------------------------------------------------------------------- #
def _label(body: int) -> str:
    rec = _STATE["ann"].get(int(body))
    if not rec:
        return "body %d" % body
    t = rec.get("type") or rec.get("superclass") or ""
    return "%s (body %d)" % (t, body)


# --------------------------------------------------------------------------- #
# Public query API
# --------------------------------------------------------------------------- #
def pair_synapses(pre: int, post: int) -> int:
    """Number of synapses from presynaptic `pre` to postsynaptic `post`."""
    ensure_cache()
    pre_s = _STATE["pre_s"]
    post_s = _STATE["post_s"]
    w_s = _STATE["w_s"]
    lo = int(np.searchsorted(pre_s, pre, side="left"))
    hi = int(np.searchsorted(pre_s, pre, side="right"))
    if lo >= hi:
        return 0
    seg_post = post_s[lo:hi]
    seg_w = w_s[lo:hi]
    mask = seg_post == post
    return int(seg_w[mask].sum()) if mask.any() else 0


def neuron_outputs(body: int, top: int = 20, neuron_only: bool = True):
    """Top-N postsynaptic targets of `body`: list of (target_body, synapses).

    By default only counts synapses onto *annotated neurons* (neuron subgraph),
    matching the biologically meaningful scope used in connectivity_facts.json.
    Set neuron_only=False to include fragment/non-annotated targets.
    """
    ensure_cache()
    pre_s = _STATE["pre_s"]
    post_s = _STATE["post_s"]
    w_s = _STATE["w_s"]
    lo = int(np.searchsorted(pre_s, body, side="left"))
    hi = int(np.searchsorted(pre_s, body, side="right"))
    if lo >= hi:
        return []
    seg_post = post_s[lo:hi]
    seg_w = w_s[lo:hi]
    if neuron_only:
        m = np.isin(seg_post, _STATE["ann_ids"])
        seg_post = seg_post[m]
        seg_w = seg_w[m]
        if seg_post.size == 0:
            return []
    uniq, inv = np.unique(seg_post, return_inverse=True)
    sums = np.zeros(len(uniq), dtype=np.int64)
    np.add.at(sums, inv, seg_w)
    order = np.argsort(-sums)[:top]
    return [(int(uniq[i]), int(sums[i])) for i in order]


def neuron_inputs(body: int, top: int = 20, neuron_only: bool = True):
    """Top-N presynaptic sources of `body`: list of (source_body, synapses).

    neuron_only defaults True (see neuron_outputs).
    """
    ensure_cache()
    post_s2 = _STATE["post_s2"]
    pre_s2 = _STATE["pre_s2"]
    w_s2 = _STATE["w_s2"]
    lo = int(np.searchsorted(post_s2, body, side="left"))
    hi = int(np.searchsorted(post_s2, body, side="right"))
    if lo >= hi:
        return []
    seg_pre = pre_s2[lo:hi]
    seg_w = w_s2[lo:hi]
    if neuron_only:
        m = np.isin(seg_pre, _STATE["ann_ids"])
        seg_pre = seg_pre[m]
        seg_w = seg_w[m]
        if seg_pre.size == 0:
            return []
    uniq, inv = np.unique(seg_pre, return_inverse=True)
    sums = np.zeros(len(uniq), dtype=np.int64)
    np.add.at(sums, inv, seg_w)
    order = np.argsort(-sums)[:top]
    return [(int(uniq[i]), int(sums[i])) for i in order]


def degree(body: int, neuron_only: bool = True):
    """Return (fan_out_synapses, fan_in_synapses) for `body`.

    neuron_only defaults True: counts only synapses between annotated neurons.
    """
    ensure_cache()
    pre_s = _STATE["pre_s"]
    w_s = _STATE["w_s"]
    lo = int(np.searchsorted(pre_s, body, side="left"))
    hi = int(np.searchsorted(pre_s, body, side="right"))
    if hi > lo:
        seg_post = _STATE["post_s"][lo:hi]
        seg_w = w_s[lo:hi]
        if neuron_only:
            seg_w = seg_w[np.isin(seg_post, _STATE["ann_ids"])]
        fanout = int(seg_w.sum())
    else:
        fanout = 0
    post_s2 = _STATE["post_s2"]
    w_s2 = _STATE["w_s2"]
    lo2 = int(np.searchsorted(post_s2, body, side="left"))
    hi2 = int(np.searchsorted(post_s2, body, side="right"))
    if hi2 > lo2:
        seg_pre = _STATE["pre_s2"][lo2:hi2]
        seg_w2 = w_s2[lo2:hi2]
        if neuron_only:
            seg_w2 = seg_w2[np.isin(seg_pre, _STATE["ann_ids"])]
        fanin = int(seg_w2.sum())
    else:
        fanin = 0
    return fanout, fanin


def neuron_info(body: int) -> dict | None:
    """Full metadata for a body id: type, superclass, NT prediction, degree."""
    ensure_cache()
    rec = _STATE["ann"].get(int(body))
    if not rec:
        return None
    out = {"bodyId": int(body)}
    out.update(rec)
    out["neurotransmitter"] = _STATE["nt"].get(int(body), "")
    fo, fi = degree(int(body))
    out["fan_out"] = fo
    out["fan_in"] = fi
    return out


def search_neurons(query: str, field: str = "type", limit: int = 20):
    """Find neurons whose `field` contains `query` (case-insensitive)."""
    ensure_cache()
    ann = _STATE["ann"]
    q = str(query).lower()
    out = []
    for bid, rec in ann.items():
        val = str(rec.get(field, "")).lower()
        if q and q in val:
            out.append((bid, rec))
            if len(out) >= limit:
                break
    return out


# Intuitive brain-area aliases -> real superclass token (multiple tokens share a prefix)
_SUPERCLASS_ALIASES = {
    "olfactory": "ol_intrinsic", "olf": "ol_intrinsic",
    "antenna": "ol_sensory", "antennal": "ol_sensory",
    "central_complex": "cb_intrinsic", "cx": "cb_intrinsic", "central": "cb_intrinsic",
    "visual": "visual_projection", "optic": "visual_projection", "eye": "visual_projection",
    "descending": "descending_neuron", "dn": "descending_neuron",
    "ascending": "ascending_neuron", "an": "ascending_neuron",
    "ventral": "vnc_intrinsic", "vnc": "vnc_intrinsic",
    "motor": "cb_motor", "sensory": "cb_sensory",
}


def superclass_projection(superclass: str) -> dict:
    """Top downstream/upstream projections for a superclass (from precomputed facts).

    Accepts an exact superclass token, a intuitive alias (e.g. 'olfactory' ->
    'ol_intrinsic', 'central_complex' -> 'cb_intrinsic'), or a substring.
    Returns candidates if nothing matches.
    """
    ensure_cache()
    facts = _STATE["facts"]
    q = superclass.strip().lower()
    q = _SUPERCLASS_ALIASES.get(q, q)
    io = next((x for x in facts.get("superclass_io", [])
               if x["superclass"].lower() == q), None)
    matched = io["superclass"] if io else None
    if matched is None:
        cand = [x["superclass"] for x in facts.get("superclass_io", [])
                if q in x["superclass"].lower()]
        if cand:
            matched = cand[0]
            io = next((x for x in facts.get("superclass_io", [])
                       if x["superclass"] == matched), None)
    outs = [c for c in facts.get("cross_superclass_top", [])
            if c.get("from") == matched][:15]
    ins = [c for c in facts.get("cross_superclass_top", [])
           if c.get("to") == matched][:15]
    return {"superclass": matched, "io": io, "top_downstream": outs,
            "top_upstream": ins, "candidates": (
                [x["superclass"] for x in facts.get("superclass_io", [])]
                if matched is None else None)}


def list_superclasses() -> list:
    """All superclass tokens available for superclass_projection / search."""
    ensure_cache()
    return sorted({x["superclass"] for x in _STATE["facts"].get("superclass_io", [])})


def hub_targets(name: str) -> dict | None:
    """Top targets of a named hub neuron (CT1, APL, ...) from precomputed facts."""
    ensure_cache()
    facts = _STATE["facts"]
    for h in facts.get("top_hubs_with_targets", []):
        if name.lower() in str(h.get("hub_type", "")).lower() or \
           name.lower() in str(h.get("hub_body", "")).lower():
            return h
    return None


def pathway(source: int, target: int, max_via: int = 1) -> dict:
    """Is `source` connected to `target`? Returns hops + a sample route."""
    d = pair_synapses(source, target)
    if d > 0:
        return {"connected": True, "hops": 1, "synapses": d,
                "route": [source, target]}
    if max_via < 1:
        return {"connected": False}
    outs = [b for b, _ in neuron_outputs(source, top=300)]
    ins = {b for b, _ in neuron_inputs(target, top=300)}
    via = [v for v in outs if v in ins]
    if via:
        return {"connected": True, "hops": 2, "via": via[:10],
                "route": [source, via[0], target]}
    return {"connected": False}


def connectome_overview() -> dict:
    """High-level real numbers for the dataset."""
    ensure_cache()
    f = _STATE["facts"]
    return {
        "dataset": "MaleCNS v1.0 (male Drosophila brain connectome)",
        "license": "CC-BY",
        "total_synapses": f["total_synapses"],
        "mean_fanout": f["mean_fanout"],
        "mean_fanin": f["mean_fanin"],
        "annotated_neurons": len(_STATE["ann"]),
        "top_hubs": [
            {"hub_type": h["hub_type"], "hub_body": h["hub_body"],
             "total_synapses": h["hub_total_synapses"]}
            for h in f.get("top_hubs_with_targets", [])[:5]
        ],
    }


# --------------------------------------------------------------------------- #
# CLI entry for manual cache build
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    t0 = time.time()
    ensure_cache(verbose=True)
    print("cache ready in %.1fs" % (time.time() - t0))
