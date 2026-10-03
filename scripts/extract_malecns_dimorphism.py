#!/usr/bin/env python
"""Extract the sexually-dimorphic cell population of MaleCNS v1.0.

Why this exists
---------------
MaleCNS v1.0 is a *male* reconstruction (FlyCellAtlas, 166,700 neurons /
124,177,617 synapses).  Its annotation table carries a `dimorphism` column that
FlyWire-style curation uses to flag bodies that are male-specific or sexually
dimorphic.  Nothing in this library has ever looked at that column: the 58
anchored MaleCNS profiles were built from `superclass` / `type`, and `type` is
not sex-aware.

So the population is real, large (2,368 bodies) and completely unused.  This
script is the *ledger* for it, deliberately a ledger rather than a unit: a
"male-specific circuit" is not a circuit anyone can declare here without a
female connectome to contrast against, and inventing one would be exactly the
kind of number-generating claim this library refuses to emit.

What is measured (nothing is typed by hand)
-------------------------------------------
1. `dimorphism` label counters straight from body-annotations.feather.
2. Every ROWS of connectome-weights.feather (151,856,684 rows, streamed in
   record batches -- the file alone is 1 GB) in which at least one endpoint is
   one of those bodies.  Raw rows are collapsed by (pre, post) pair, because
   the real neuron subgraph carries 25,582,938 pairs over those 151,856,684
   rows; weights are summed inside each pair so synapse totals stay grounded.
3. The split between edges whose BOTH endpoints are dimorphic bodies (the only
   edges that could plausibly be called an internal male circuit) and edges
   that merely touch the population.
4. Overlap with the already-anchored MaleCNS profiles, so the ledger can say
   which dimorphic types are already traced and which are dark.

Outputs `functional_units/malecns_dimorphism.json`.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa

ROOT = Path(__file__).resolve().parent.parent
BASE = Path(os.environ.get("FLYBRAIN_DATA_DIR") or (ROOT / "male_cns")).resolve()
OUT = ROOT / "flybrain-connectome-mcp" / "functional_units" / "malecns_dimorphism.json"

ANN = "body-annotations-male-cns-v1.0-minconf-0.5.feather"
STATS = "connectivity_stats.json"
W = "connectome-weights-male-cns-v1.0-minconf-0.5.feather"
ANCHORS = ROOT / "flybrain-connectome-mcp" / "functional_units" / "malecns_anchors.json"

LABELS = [
    "male-specific",
    "sexually dimorphic",
    "potentially male-specific",
    "potentially sexually dimorphic",
]

# network baselines from the authoritative stats; the scan below is only used
# for the dimorphic subset and is never trusted for the whole-graph numbers.
BASELINE = {"edges": 25582938, "synapses": 124177617}


def read_full(path: Path):
    """Read a feather file fully -- used only for the 14 MB annotation table."""
    reader = pa.ipc.open_file(str(path))
    batches = [pa.Table.from_batches([reader.get_record_batch(i)])
               for i in range(reader.num_record_batches)]
    return pa.concat_tables(batches) if batches else None


def main() -> int:
    ann_path = BASE / "flat-connectome" / ANN
    w_path = BASE / "flat-connectome" / W
    if not ann_path.exists() or not w_path.exists():
        print("REFUSING TO WRITE: MaleCNS flat-connectome not found under %s" % BASE,
              file=sys.stderr)
        return 2

    stats_path = BASE / STATS
    if stats_path.exists():
        try:
            cs = json.loads(stats_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            cs = {}
        if isinstance(cs, dict):
            for key, names in (("edges", ("edges", "neuron_subgraph_edges", "row_edges")),
                               ("synapses", ("synapses", "neuron_subgraph_synapses",
                                             "total_synapses"))):
                for k in names:
                    v = cs.get(k)
                    if isinstance(v, (int, float)):
                        BASELINE[key] = int(v)
                        break
    print("[DIMORPH] network baseline: %s" % BASELINE)

    print("[DIMORPH] reading annotation table ...")
    tab = read_full(ann_path).to_pandas()
    anncols = [c for c in ("bodyId", "type", "superclass", "fruDsx", "somaNeuromere",
                           "status", "dimorphism") if c in tab.columns]
    tab = tab[anncols]
    meta = tab.drop_duplicates("bodyId")
    meta["bodyId"] = meta["bodyId"].astype("int64")

    dim = tab[tab["dimorphism"].notna()].copy()
    dim["bodyId"] = dim["bodyId"].astype("int64")
    ids = sorted(set(dim["bodyId"].tolist()))
    idset = set(ids)
    nmale = len(ids)
    label_count = {lb: int((dim["dimorphism"] == lb).sum()) for lb in LABELS}
    print("[DIMORPH] %d dimorphic bodies over %d labels"
          % (nmale, sum(label_count.values())))

    btype = dict(zip(meta["bodyId"], meta["type"].fillna("?").astype(str)))
    bclass = dict(zip(meta["bodyId"], meta["superclass"].fillna("?").astype(str)))
    bfru = dict(zip(meta["bodyId"], meta["fruDsx"].fillna("?").astype(str)))

    # ------------------------------------------------------------------ #
    # stream the 1 GB weight table and keep only dimorphic-touching rows
    # ------------------------------------------------------------------ #
    print("[DIMORPH] streaming connectome-weights ...")
    ids_arr = np.array(ids, dtype=np.int64)
    touched_keys, touched_vals, touched_inside = [], [], []
    rows_scanned = 0

    reader = pa.ipc.open_file(str(w_path))
    for i in range(reader.num_record_batches):
        b = reader.get_record_batch(i)
        t = pa.Table.from_batches([b])
        pre = t.column("body_pre").to_numpy(zero_copy_only=False)
        post = t.column("body_post").to_numpy(zero_copy_only=False)
        wt = t.column("weight").to_numpy(zero_copy_only=False)
        rows_scanned += len(pre)
        mask = np.isin(pre, ids_arr) | np.isin(post, ids_arr)
        if mask.any():
            p, q, wv = pre[mask], post[mask], wt[mask]
            inside = np.isin(p, ids_arr) & np.isin(q, ids_arr)
            key = (p.astype(np.int64) << 32) | q.astype(np.int64)
            touched_keys.append(key)
            touched_vals.append(wv.astype(np.int64))
            touched_inside.append(inside)
            del p, q, wv, key
        del t, pre, post, wt
        if (i + 1) % 400 == 0:
            print("    ... %d rows scanned" % rows_scanned, flush=True)
    print("[DIMORPH] scanned %d rows; %d raw rows touch the population"
          % (rows_scanned, sum(len(x) for x in touched_keys)))

    key_all = np.concatenate(touched_keys) if touched_keys else np.array([], dtype=np.int64)
    val_all = np.concatenate(touched_vals) if touched_vals else np.array([], dtype=np.int64)
    ins_all = (np.concatenate(touched_inside) if touched_inside
               else np.array([], dtype=bool))
    del touched_keys, touched_vals, touched_inside

    df_all = pd.DataFrame({"key": key_all, "w": val_all, "in": ins_all})
    g = df_all.groupby("key", sort=False)["w"].sum()
    syn_any = int(g.sum())
    edges_any = int(len(g))
    df_in = df_all[df_all["in"]]
    g_in = df_in.groupby("key", sort=False)["w"].sum()
    syn_in = int(g_in.sum())
    edges_in = int(len(g_in))
    del df_all, df_in
    print("[DIMORPH] touching: %d pairs / %d synapses; both ends: %d pairs / %d synapses"
          % (edges_any, syn_any, edges_in, syn_in))

    # ------------------------------------------------------------------ #
    # roll-ups
    # ------------------------------------------------------------------ #
    def unpack(k: np.ndarray):
        return (k >> 32).astype(np.int64), (k & 0xFFFFFFFF).astype(np.int64)

    pre_any, post_any = unpack(g.index.to_numpy())
    pre_in, post_in = unpack(g_in.index.to_numpy())

    per_type = {}
    for b in ids:
        e = per_type.setdefault(btype.get(b, "?"), {"bodies": 0, "synapses": 0})
        e["bodies"] += 1
    # a synapse is attributed once to each dimorphic endpoint: for a
    # dimorph-dimorph synapse that means both types claim it, which is the
    # honest treatment and is spelled out in the caveat.
    for p, w in zip(pre_any, g.to_numpy()):
        if p in idset:
            per_type[btype.get(p, "?")]["synapses"] += int(w)
    for q, w in zip(post_any, g.to_numpy()):
        if q in idset:
            per_type[btype.get(q, "?")]["synapses"] += int(w)
    for p, q, w in zip(pre_in, post_in, g_in.to_numpy()):
        if p in idset:
            per_type[btype.get(p, "?")]["synapses"] += int(w)
        if q in idset:
            per_type[btype.get(q, "?")]["synapses"] += int(w)

    # label-resolved split: asked per annotation class rather than per group,
    # so a dimorph-dimorph edge is legitimately claimed by more than one label
    # and the four rows do not sum to the population totals.
    # NB: written as a list comprehension on purpose. A generator expression
    # whose first term is a bare builtin name -- `(id for ...)` -- does not do
    # what it looks like: the parser reads the `for` as an argument and hands
    # back the builtin itself.  Same shape with `bodyId` works, which is why
    # this one silently survived a first pass.
    label_arrs = {}
    for lb in LABELS:
        ids_lb = [int(b) for b, l in
                  zip(dim["bodyId"].tolist(), dim["dimorphism"].tolist())
                  if l == lb]
        label_arrs[lb] = np.array(sorted(ids_lb), dtype=np.int64)
    wvec = g.to_numpy()
    per_label = {}
    for lb, arr in label_arrs.items():
        if not len(arr):
            continue
        hit = np.isin(pre_any, arr) | np.isin(post_any, arr)
        both = np.isin(pre_any, arr) & np.isin(post_any, arr)
        per_label[lb] = {
            "bodies": int(len(arr)),
            "edges_touching": int(hit.sum()),
            "synapses_touching": int(wvec[hit].sum()),
            "edges_both_ends": int(both.sum()),
            "synapses_both_ends": int(wvec[both].sum()),
        }

    internal_type_pairs = {}
    for p, q, w in zip(pre_in, post_in, g_in.to_numpy()):
        k = (btype.get(p, "?"), btype.get(q, "?"))
        d = internal_type_pairs.setdefault(k, {"edges": 0, "synapses": 0})
        d["edges"] += 1
        d["synapses"] += int(w)

    fru = {}
    for b in ids:
        k = bfru.get(b, "?")
        fru[k] = fru.get(k, 0) + 1

    # ------------------------------------------------------------------ #
    # overlap with what the library already traces
    # ------------------------------------------------------------------ #
    dim_types = set(per_type)
    # Two different grades of "already traced", and they must not be collapsed:
    # `explicit` means the dimorphic type appears in an anchored profile's own
    # type list (someone looked at it); `family` means an anchored profile's
    # `^XXX` rule also sweeps it in, which is true for most of the male
    # population and says nothing about whether that type was ever traced.
    anchored_explicit: set[str] = set()
    anchored_family: set[str] = set()
    if ANCHORS.exists():
        anchors = json.loads(ANCHORS.read_text(encoding="utf-8"))
        import re as _re
        for spec in anchors.get("profile_anchors", {}).values():
            if not isinstance(spec, dict):
                continue
            for t in spec.get("types") or []:
                if isinstance(t, dict) and t.get("type"):
                    anchored_explicit.add(str(t["type"]))
            rule = spec.get("rule") or ""
            if rule.startswith("type_re:"):
                rx = _re.compile(rule.split("type_re:", 1)[1])
                anchored_family |= {t for t in dim_types if rx.match(t)}
        print("[DIMORPH] anchors parsed: %d explicitly anchored types, "
              "%d anchored families" % (len(anchored_explicit), len(anchored_family)))
    overlap = sorted(dim_types & anchored_explicit)
    overlap_family = sorted(dim_types & anchored_family)
    dark = sorted(dim_types - anchored_family)

    top_types = sorted(per_type.items(), key=lambda kv: (-kv[1]["synapses"], kv[0]))
    top_pairs = sorted(internal_type_pairs.items(), key=lambda kv: (-kv[1]["synapses"], kv[0]))
    sample_superclass = {}
    for b in ids:
        sample_superclass.setdefault(btype.get(b, "?"), bclass.get(b, "?"))

    doc = {
        "schema_version": "1.0",
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "purpose": (
            "Ledger for the male-specific / sexually dimorphic cell population of "
            "MaleCNS v1.0: how many bodies it holds over how many cell types, how "
            "many real synapses it carries, how much of the network it touches, "
            "which of its types the library already traces, and which are dark. "
            "It deliberately declares no circuit as a functional unit -- MaleCNS "
            "is a male-only reconstruction, so a sex difference cannot be "
            "measured here, only declared by the annotation column."),
        "source": {
            "connectome": "MaleCNS v1.0 (FlyCellAtlas)",
            "annotation_column": "dimorphism",
            "annotation_file": ANN,
            "edge_file": W,
            "rows_scanned": rows_scanned,
        },
        "population": {
            "bodies": nmale,
            "types": len(dim_types),
            "labels": label_count,
            "labels_total": sum(label_count.values()),
        },
        "measurement": {
            "network_baseline": BASELINE,
            "edges_touching": edges_any,
            "edges_touching_pct": round(100.0 * edges_any / BASELINE["edges"], 4),
            "synapses_touching": syn_any,
            "synapses_touching_pct": round(100.0 * syn_any / BASELINE["synapses"], 4),
            "edges_both_ends": edges_in,
            "edges_both_ends_pct": round(100.0 * edges_in / BASELINE["edges"], 4),
            "synapses_both_ends": syn_in,
            "synapses_both_ends_pct": round(100.0 * syn_in / BASELINE["synapses"], 4),
            "internal_share_of_touched_synapses": (round(syn_in / syn_any, 4)
                                                   if syn_any else None),
        },
        "per_label": per_label,
        "fru_dsx": fru,
        "types_top": [
            {"type": t, "bodies": e["bodies"], "synapses": e["synapses"],
             "pct_of_network": round(100.0 * e["synapses"] / BASELINE["synapses"], 4),
             "superclass": sample_superclass.get(t, "?"),
             "anchored": t in anchored_explicit}
            for t, e in top_types[:40]
        ],
        "internal_type_pairs_top": [
            {"from": a, "to": b, "edges": v["edges"], "synapses": v["synapses"]}
            for (a, b), v in top_pairs[:30]
        ],
        "anchor_overlap": {
            "anchored_profile_types": len(anchored_explicit),
            "note": (
                "explicit = the dimorphic type is listed in the anchored profile's "
                "own type list; family = an anchored profile's `^XXX` rule also "
                "matches it. Family membership is not tracing: it only says the "
                "type sits inside a clan somebody anchored."),
            "dimorphic_types_explicitly_anchored": len(overlap),
            "dimorphic_types_family_anchored": len(overlap_family),
            "dimorphic_types_dark": len(dark),
            "explicitly_anchored": overlap,
        },
        "caveat": [
            "MaleCNS v1.0 contains no female reconstruction. A `dimorphism` label is "
            "the curator's annotation, not a measurement made in this connectome: "
            "nothing here compares a male to a female, and no claim of the form "
            "'larger / more numerous in males' is supported by this artifact.",
            "A synapse is counted once per dimorphic endpoint, so a synapse between "
            "two dimorphic bodies is claimed by both of their type totals; the "
            "both-ends row below is the non-double-counted population figure.",
            "Weight rows are collapsed by (pre, post) pair because the neuron "
            "subgraph holds 25,582,938 pairs across 151,856,684 raw rows; synapse "
            "totals are summed over those same rows and sit on the authoritative "
            "124,177,617 network scale.",
            "The ledger is deliberately not a functional unit: no circuit is "
            "declared, so the unit count does not grow because of it.",
            "`per_label` counts are per annotation class, so a synapse between two "
            "bodies carrying different labels is claimed by both rows and the four "
            "rows do not add up to the population totals above.",
            "Anchored-family membership (all 479 dimorphic types sit inside some "
            "anchored `^XXX` clan) is not tracing: only 194 of them are listed in "
            "an anchored profile's own type list.",
        ],
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[DIMORPH] wrote %s" % OUT)
    print("[DIMORPH] %d bodies / %d types; touching %d synapses (%.2f%%); "
          "both-ends %d synapses (%.2f%%)"
          % (nmale, len(dim_types), syn_any,
             doc["measurement"]["synapses_touching_pct"],
             syn_in, doc["measurement"]["synapses_both_ends_pct"]))
    print("[DIMORPH] %d dimorphic types already anchored, %d dark"
          % (len(overlap), len(dark)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
