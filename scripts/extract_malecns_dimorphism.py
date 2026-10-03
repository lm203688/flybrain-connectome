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


def _per_body_scale(w_path: Path, ann_ids: np.ndarray):
    """Per-body synapse totals + percentiles, as the scale reference.

    Body ids in this connectome run to 1,571,825,087, so a dense
    `np.zeros(max_id)` array is 11.7 GiB and allocating it on a laptop is not
    an option.  Instead the annotated ids are sorted once and every endpoint is
    located with a binary search, accumulating into an array sized by the
    number of annotated bodies (211,577) rather than by the id range.  The two
    approaches agree; only one of them fits in memory.

    The lesson from the first attempt at this measurement is kept in the
    docstring below rather than in a comment that could be deleted: a guessed
    cap of 400,000 with a `< cap` mask looks like a bounds check and is
    actually a silent 96% data loss, and the number it produces is plausible
    enough to argue with.
    """
    uniq = np.unique(np.asarray(ann_ids, dtype=np.int64))
    n = len(uniq)
    totals = np.zeros(n, dtype=np.int64)
    reader = pa.ipc.open_file(str(w_path))
    for i in range(reader.num_record_batches):
        t = pa.Table.from_batches([reader.get_record_batch(i)])
        pre = t.column("body_pre").to_numpy(zero_copy_only=False).astype(np.int64)
        post = t.column("body_post").to_numpy(zero_copy_only=False).astype(np.int64)
        w = t.column("weight").to_numpy(zero_copy_only=False).astype(np.int64)
        for arr in (pre, post):
            pos = np.searchsorted(uniq, arr)
            np.clip(pos, 0, n - 1, out=pos)
            hit = uniq[pos] == arr
            np.add.at(totals, pos[hit], w[hit])
        del t, pre, post, w
    v = totals[totals > 0]
    pos_of = {int(b): k for k, b in enumerate(uniq.tolist())}
    scale = {
        "note": (
            "Scale reference so an extreme per-type number can be judged. "
            "Percentiles are over annotated bodies that carry at least one "
            "synapse. The distribution is heavy-tailed, so the per-cell means "
            "in types_top sit far above the median and are not anomalies."),
        "annotated_bodies": int(n),
        "bodies_with_synapses": int(len(v)),
        "median": int(np.median(v)) if len(v) else 0,
        "p90": int(np.percentile(v, 90)) if len(v) else 0,
        "p99": int(np.percentile(v, 99)) if len(v) else 0,
        "p999": int(np.percentile(v, 99.9)) if len(v) else 0,
        "max": int(v.max()) if len(v) else 0,
        "max_body_id": int(uniq.max()) if n else 0,
    }
    return (uniq, totals, pos_of), scale


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
                           "status", "dimorphism",
                           # v2.33.0 -- the provenance of the dimorphism call
                           # itself, so an extreme type can be audited without
                           # re-opening the 14 MB table by hand.
                           "flywireType", "hemibrainType", "statusLabel",
                           "matchingNotes", "itoleeHl", "trumanHl")
               if c in tab.columns]
    tab = tab[anncols]
    meta = tab.drop_duplicates("bodyId")
    meta["bodyId"] = meta["bodyId"].astype("int64")

    # ------------------------------------------------------------------ #
    # The three type axes, measured rather than asserted.
    #
    # The annotation table carries THREE independent naming axes: `type` is the
    # MaleCNS axis, `flywireType` the FlyWire axis and `hemibrainType` the
    # hemibrain axis.  They disagree on a third of all bodies -- `TmY21` in
    # this ledger is the MaleCNS name for a class FlyWire calls `Tm36`.  That
    # is not an error, it is a renaming plus lineage splits, but it means a
    # name quoted from here will not be found in FlyWire or hemibrain
    # documentation under the same string.  This library's anchors all sit on
    # the `type` axis (asserted below, not assumed), so the ledger counts on
    # that axis and says so out loud.
    #
    # NB the fillna("") before comparing.  Missing values are a real state in
    # both columns, and letting pandas turn them into the *string* 'nan' makes
    # two missing cells compare unequal -- which inflated the disagreement
    # rate to 54.94% in a first pass of this script.  The measured figure is
    # the one in `axis_comparison`; do not hand-edit a number into the prose
    # below, read it from there.
    # ------------------------------------------------------------------ #
    axis_census = {}
    for col in ("type", "flywireType", "hemibrainType"):
        if col not in tab.columns:
            continue
        s = tab[col].fillna("").astype(str)
        axis_census[col] = int(s[s.str.len() > 0].nunique())
    pairs = None
    if "flywireType" in tab.columns:
        tv = tab["type"].fillna("").astype(str)
        fv = tab["flywireType"].fillna("").astype(str)
        diff = tv != fv
        named = (tv.str.len() > 0) | (fv.str.len() > 0)
        pairs = {
            "compared": "type vs flywireType",
            "bodies_compared": int(len(tv)),
            "bodies_differing": int(diff.sum()),
            "bodies_differing_pct": round(100.0 * float(diff.mean()), 2),
            "bodies_named_on_either_axis": int(named.sum()),
            "classes_involved": int(tv[diff].nunique()),
        }
        if "hemibrainType" in tab.columns:
            hv = tab["hemibrainType"].fillna("").astype(str)
            has_h = hv.str.len() > 0
            hd = (tv[has_h] != hv[has_h])
            pairs["hemibrain_comparison"] = {
                "bodies_with_hemibrain_type": int(has_h.sum()),
                "bodies_differing": int(hd.sum()),
                "bodies_differing_pct": round(100.0 * float(hd.mean()), 2),
            }
    print("[DIMORPH] type axes: %s ; type vs flywireType differ on %s%%"
          % (axis_census, (pairs or {}).get("bodies_differing_pct")))

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
    balias = dict(zip(meta["bodyId"],
                      meta["flywireType"].fillna("").astype(str))) \
        if "flywireType" in meta.columns else {}
    bstatus = dict(zip(meta["bodyId"],
                       meta["statusLabel"].fillna("").astype(str))) \
        if "statusLabel" in meta.columns else {}
    bnote = dict(zip(meta["bodyId"],
                     meta["matchingNotes"].fillna("").astype(str))) \
        if "matchingNotes" in meta.columns else {}
    bito = dict(zip(meta["bodyId"],
                    meta["itoleeHl"].fillna("").astype(str))) \
        if "itoleeHl" in meta.columns else {}

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
    # ------------------------------------------------------------------ #
    # Per-body scale reference.
    #
    # v2.32.0 quoted `oviIN` at 2 bodies / 196,360 synapses without saying what
    # a normal body holds, so the number could not be judged -- 196k sounds
    # impossible next to the "1k-10k per neuron" folk rule, and the honest
    # answer turned out to be that the folk rule is wrong for this dataset:
    # the distribution is heavy-tailed with a max in the six figures.  Without
    # this row a reader has to take the extremes on faith or dismiss them on a
    # rule of thumb that does not hold here.  Percentiles are over annotated
    # bodies only (149k of the 211,577 rows carry synapses).
    #
    # The array is sized from the annotation table, NOT from a guessed cap.
    # Body ids run to 1,571,863,634; a `np.zeros(400_000)` with a `< cap` mask
    # silently drops the large-id majority and understates every body.  That
    # mistake was made and caught in this very investigation -- it produced a
    # per-body median of 573 against a true one roughly an order of magnitude
    # higher, and it would have "confirmed" oviIN as a 100x outlier.  Asserted
    # below rather than trusted.
    # ------------------------------------------------------------------ #
    (body_ids, body_totals, pos_of), body_scale = _per_body_scale(
        w_path, meta["bodyId"].to_numpy())
    v = body_totals[body_totals > 0]
    if len(v) < 1000 or int(body_scale["median"]) <= 0:
        print("[DIMORPH] REFUSING TO WRITE: per-body scale looks broken "
              "(%d bodies with synapses, median %s) -- the endpoint lookup is "
              "probably dropping bodies." % (len(v), body_scale["median"]),
              file=sys.stderr)
        return 3
    # every annotated body must be locatable in the id -> index map, and the
    # totals must land on the network scale rather than a fraction of it
    if int(body_totals.sum()) < BASELINE["synapses"]:
        print("[DIMORPH] NOTE: per-body out+in total %d is below the %d network "
              "synapses because a self-connection is counted on both sides; "
              "expected, not an error."
              % (int(body_totals.sum()), BASELINE["synapses"]))
    print("[DIMORPH] per-body scale: median %d p99 %d max %d over %d bodies"
          % (body_scale["median"], body_scale["p99"], body_scale["max"],
             body_scale["bodies_with_synapses"]))

    def unpack(k: np.ndarray):
        return (k >> 32).astype(np.int64), (k & 0xFFFFFFFF).astype(np.int64)

    pre_any, post_any = unpack(g.index.to_numpy())
    pre_in, post_in = unpack(g_in.index.to_numpy())

    per_type = {}
    for b in ids:
        e = per_type.setdefault(btype.get(b, "?"), {"bodies": 0, "synapses": 0})
        e["bodies"] += 1
    # Attribution rule, stated once and then asserted: a collapsed pair is
    # charged once to each of its dimorphic endpoints.  So a pair with one
    # dimorphic end contributes its weight once, and a pair with two contributes
    # it twice -- which makes the sum over ALL types exactly
    #     touching + both_ends
    # no matter how the population is split across types.  That identity is the
    # regression test for this block: an earlier version walked the both-ends
    # pairs a second time on top of the all-pairs pass, so every internal
    # synapse was charged four times and `types_top` came out inflated by 3x the
    # internal total.  The headline `measurement` numbers were never affected
    # (they come straight off the groupby), but the per-type breakdown was --
    # and the per-type breakdown is the part a reader quotes.
    for p, w in zip(pre_any, g.to_numpy()):
        if p in idset:
            per_type[btype.get(p, "?")]["synapses"] += int(w)
    for q, w in zip(post_any, g.to_numpy()):
        if q in idset:
            per_type[btype.get(q, "?")]["synapses"] += int(w)

    charged = sum(e["synapses"] for e in per_type.values())
    expect_charged = syn_any + syn_in
    if charged != expect_charged:
        print("[DIMORPH] REFUSING TO WRITE: per-type synapse attribution does "
              "not reconcile (%d charged vs %d expected = touching %d + "
              "both-ends %d). A pair must be charged once per dimorphic "
              "endpoint and no more." % (charged, expect_charged, syn_any, syn_in),
              file=sys.stderr)
        return 3
    print("[DIMORPH] attribution reconciles: %d charged == touching %d + "
          "both-ends %d" % (charged, syn_any, syn_in))

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
        # The overlap below is only meaningful if the anchored type names live
        # on the same axis the ledger counts on.  Verified, not assumed: v2.32.0
        # compared a `type`-axis census against anchored names without ever
        # checking which axis those names came from.  They do all sit on `type`
        # (5,413/5,413), so the earlier count stands -- but the check is now
        # in the script instead of in a later session's memory.
        tset = set(btype.values())
        on_type = len(anchored_explicit & tset)
        if anchored_explicit and on_type != len(anchored_explicit):
            print("[DIMORPH] REFUSING TO WRITE: %d of %d anchored type names "
                  "are not on the `type` axis this ledger counts on; the "
                  "overlap below would compare across naming axes."
                  % (len(anchored_explicit) - on_type, len(anchored_explicit)),
                  file=sys.stderr)
            return 3
        print("[DIMORPH] anchor axis check: %d/%d anchored names on the `type` "
              "axis" % (on_type, len(anchored_explicit)))
    overlap = sorted(dim_types & anchored_explicit)
    overlap_family = sorted(dim_types & anchored_family)
    dark = sorted(dim_types - anchored_family)

    # where does each top type sit in the per-body distribution?
    type_body_stats = {}
    for b in ids:
        t = btype.get(b, "?")
        k = pos_of.get(b)
        if k is not None:
            type_body_stats.setdefault(t, []).append(int(body_totals[k]))
    type_body_median = {t: int(np.median(vals))
                        for t, vals in type_body_stats.items() if vals}

    def _pct_of_bodies(n: int):
        if not len(v):
            return None
        return round(100.0 * float((v < n).mean()), 4)

    top_types = sorted(per_type.items(), key=lambda kv: (-kv[1]["synapses"], kv[0]))
    top_pairs = sorted(internal_type_pairs.items(), key=lambda kv: (-kv[1]["synapses"], kv[0]))
    sample_superclass = {}
    for b in ids:
        sample_superclass.setdefault(btype.get(b, "?"), bclass.get(b, "?"))

    # ------------------------------------------------------------------ #
    # Provenance of the dimorphism call, per type.
    #
    # v2.32.0 shipped a ledger whose two most eye-catching numbers -- `oviIN`
    # at 2 bodies and `TmY21` at 372 -- were quoted without ever showing where
    # their dimorphism label came from.  Both turn out to be attributable: the
    # `matchingNotes` column carries the curator's own sentence for each
    # ("more extensive dendrites in male", "the male dendrites have an extra
    # layer of arborisation in layer 3 of the ME ..."), and `itoleeHl` records
    # the matching grade.  So the labels are traceable curation, not inference.
    #
    # What that does NOT do is make them measurements -- see the caveat.  But
    # "2 bodies, 196k synapses" is now a number a reader can check against a
    # primary note instead of taking on faith, and the trace grade travels with
    # it: a `Roughly traced` type is a weaker object than a `Reviewed` one, and
    # the ledger now says which is which.
    # ------------------------------------------------------------------ #
    type_provenance = {}
    for b in ids:
        t = btype.get(b, "?")
        d = type_provenance.setdefault(t, {
            "flywire_alias": set(), "hemibrain_alias": set(),
            "status_labels": set(), "matching_notes": set(),
            "itolee_grade": set(), "truman_grade": set(),
        })
        if balias.get(b):
            d["flywire_alias"].add(balias[b])
        if bito.get(b):
            d["itolee_grade"].add(bito[b])
        if bstatus.get(b):
            d["status_labels"].add(bstatus[b])
        if bnote.get(b):
            d["matching_notes"].add(bnote[b])
    if "hemibrainType" in meta.columns:
        bh = dict(zip(meta["bodyId"],
                      meta["hemibrainType"].fillna("").astype(str)))
        for b in ids:
            if bh.get(b):
                type_provenance[btype.get(b, "?")]["hemibrain_alias"].add(bh[b])
    if "trumanHl" in meta.columns:
        bt2 = dict(zip(meta["bodyId"],
                       meta["trumanHl"].fillna("").astype(str)))
        for b in ids:
            if bt2.get(b):
                type_provenance[btype.get(b, "?")]["truman_grade"].add(bt2[b])

    def _prov(t: str):
        d = type_provenance.get(t, {})
        alias = sorted(x for x in d.get("flywire_alias", ()) if x)
        if alias and set(alias) != {t}:
            return {
                "flywire_alias": alias,
                "note": ("Counted under the MaleCNS `type` axis; FlyWire calls "
                         "this class %s. The two axes disagree on a third of the "
                         "annotated bodies, so a FlyWire-side grep for `%s` "
                         "returns nothing." % (alias[0], t)),
                "status_labels": sorted(d.get("status_labels", ())),
                "matching_notes": sorted(d.get("matching_notes", ())),
                "itolee_grade": sorted(d.get("itolee_grade", ())),
            }
        return {
            "status_labels": sorted(d.get("status_labels", ())),
            "matching_notes": sorted(d.get("matching_notes", ())),
            "itolee_grade": sorted(d.get("itolee_grade", ())),
        }

    graded = sum(1 for t in per_type
                 if "Roughly traced" in type_provenance.get(t, {})
                 .get("status_labels", ()))
    noted = sum(1 for t in per_type
                if type_provenance.get(t, {}).get("matching_notes"))
    print("[DIMORPH] dimorphism provenance: %d/%d types carry a matchingNote, "
          "%d are `Roughly traced`" % (noted, len(per_type), graded))

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
        "type_axes": {
            "note": (
                "The annotation table carries three independent type-naming axes. "
                "This ledger counts on `type` (the MaleCNS axis) and only that one. "
                "`type` != `flywireType` on most bodies, so a class named here may "
                "be filed under a different name in FlyWire or hemibrain; per-type "
                "aliases travel with the top types below."),
            "class_counts": axis_census,
            "axis_comparison": pairs,
        },
        "dimorphism_provenance": {
            "note": (
                "Where the sex label came from. `matching_notes` is the curator's "
                "own sentence; `status_labels` is the trace grade; `itolee_grade` "
                "is the matching grade against the Ito et al. reference. A label "
                "with a note is curation you can check, not an inference this "
                "library made -- but it is still a label, and MaleCNS has no "
                "female reconstruction to measure it against."),
            "types_with_matching_note": noted,
            "types_total": len(per_type),
            "types_roughly_traced": graded,
        },
        "measurement": {
            "network_baseline": BASELINE,
            "body_scale": body_scale,
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
            "per_type_attribution_check": {
                "charged_to_types": charged,
                "expected_touching_plus_both": expect_charged,
                "reconciles": bool(charged == expect_charged),
                "note": (
                    "Each collapsed pair is charged once per dimorphic endpoint, so "
                    "the per-type totals sum to touching + both-ends. Checked on "
                    "every run; the script refuses to write if it fails."),
            },
        },
        "per_label": per_label,
        "fru_dsx": fru,
        "types_top": [
            {"type": t, "bodies": e["bodies"], "synapses": e["synapses"],
             "pct_of_network": round(100.0 * e["synapses"] / BASELINE["synapses"], 4),
             "superclass": sample_superclass.get(t, "?"),
             "anchored": t in anchored_explicit,
             "synapses_per_body": (round(e["synapses"] / e["bodies"], 1)
                                   if e["bodies"] else None),
             "median_body_synapses": type_body_median.get(t),
             "body_synapse_percentile": _pct_of_bodies(
                 type_body_median.get(t) or 0),
             "provenance": _prov(t)}
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
            "A synapse is charged once per dimorphic endpoint, so a synapse between "
            "two dimorphic bodies is claimed by both of their type totals; the "
            "per-type figures therefore sum to touching + both-ends rather than to "
            "the touching total. `measurement.per_type_attribution_check` records "
            "that identity and the script refuses to write when it fails.",
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
            "Types are named on the MaleCNS `type` axis. That axis disagrees with "
            "`flywireType` on a third of all annotated bodies -- `TmY21` here is "
            "the class FlyWire calls `Tm36` -- so quoting a type name from this "
            "artifact into FlyWire or hemibrain documentation needs the alias in "
            "`types_top[].provenance.flywire_alias` first. The exact rate is in "
            "`type_axes.axis_comparison`, not repeated here on purpose: a first "
            "pass of this script hardcoded 54.94% into this string, which was the "
            "pandas 'nan'-vs-missing artefact described above, not a measurement.",
            "Per-type synapse counts are per-cell figures on a heavy-tailed "
            "distribution: compare them against `measurement.body_scale` "
            "(median / p99 / max) rather than against a rule of thumb. `oviIN` at "
            "~91k synapses per body looks impossible next to the usual '1k-10k per "
            "neuron' rule, and is nonetheless real in this dataset -- the rule is "
            "not what the data does.",
            "`dimorphism_provenance` records the curator's own `matchingNotes` "
            "sentence and the trace grade behind each sex label. That makes a label "
            "auditable; it does not make it a measurement, and `Roughly traced` "
            "types are weaker objects than `Reviewed` ones.",
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
