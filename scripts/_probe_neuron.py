# -*- coding: utf-8 -*-
"""
Probe a real MaleCNS neuron.

Inputs are hard-coded below. Change NEURON_ID and NEURON_TYPE at the top to
re-probe a different cell.

The probe walks the same four-layer library + real connectome that the shipped
function units use, and prints every step so a reader can see where each
sentence of the final "this cell does what" answer came from.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# --- change these to probe a different neuron --------------------------------
NEURON_ID = 888878106          # example: an annotated TmY21 body
NEURON_TYPE = "TmY21"
# -----------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(r"C:\Users\xing\Desktop\flybrain-connectome\male_cns")
sys.path.insert(0, str(ROOT))
from engine.core.data_load import _load_csv


def header(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def main() -> None:
    header(f"Step 1/7  Look up {NEURON_ID} in the raw connectome")

    edges = _load_csv(DATA / "MaleCNS_neurons_edges.csv")
    annot = _load_csv(DATA / "MaleCNS_annotations.csv")
    annot = annot.rename(columns={
        "Neuron Type": "neuron_type",
        "Matching Notes": "matching_notes",
        "Body Type": "body_type",
    })

    ann = annot[annot["Neuron ID"] == NEURON_ID]
    if ann.empty:
        print(f"!! {NEURON_ID} is not in the annotation table (frontier cell)")
        return
    a = ann.iloc[0]
    print(f"Neuron ID      : {NEURON_ID}")
    print(f"neuron_type    : {a['neuron_type']}")
    print(f"body_type      : {a.get('body_type', '?')}")
    print(f"dimorphism     : {a.get('dimorphism', '')}")
    print(f"matchingNotes  : {str(a.get('matching_notes', ''))[:200]}")

    eid = np.int64(NEURON_ID)
    sub = edges[(edges["pre"] == eid) | (edges["post"] == eid)].copy()
    if sub.empty:
        print("!! this body has zero synapses in the reconstructed layer")
        return

    def side(row):
        if int(row["pre"]) == int(NEURON_ID):
            other, pol = row["post"], "out"
        else:
            other, pol = row["pre"], "in"
        return int(other), pol, int(row["weight"])

    pairs = {o for o, _, _ in sub.apply(side, axis=1)}
    n_syn = int(sub["weight"].sum())
    n_out_syn = int(sub[sub["pre"] == eid]["weight"].sum())
    n_in_syn = int(sub[sub["post"] == eid]["weight"].sum())
    n_out_post = len({int(r["post"]) for _, r in sub.iterrows() if int(r["pre"]) == int(NEURON_ID)})
    n_in_pre = len({int(r["pre"]) for _, r in sub.iterrows() if int(r["post"]) == int(NEURON_ID)})

    header("Step 2/7  Direct connectome neighbourhood")
    print(f"distinct partners : {len(pairs):,}")
    print(f"synapses (total)  : {n_syn:,}")
    print(f"  outgoing (pre)  : {n_out_syn:,}   -> {n_out_post} distinct targets")
    print(f"  incoming  (post): {n_in_syn:,}   <- {n_in_pre} distinct sources")

    # --- functional units that claim this type -------------------------------
    header("Step 3/7  Which functional units declare this neuron type")
    units = json.loads((ROOT / "artifacts" / "functional_units.json").read_text(encoding="utf-8"))
    claiming = []
    for u in units:
        if NEURON_TYPE in u.get("members", []):
            claiming.append(u)
    if not claiming:
        print(f"no functional unit in the library declares `{NEURON_TYPE}`")
    for u in claiming:
        st = u.get("embodiment", {}).get("status", "?")
        print(f"- {u['unit_id']:48s} {u['name'][:34]:34s} {st}")

    # --- which module profile the library assigned this cell ----------------
    header("Step 4/7  Which library module profile claims this cell type")
    profiles = json.loads((ROOT / "artifacts" / "neuron_profiles.json").read_text(encoding="utf-8"))
    module_hits = []
    for mid, prof in profiles.items():
        for t in prof.get("types", []):
            if t == NEURON_TYPE:
                module_hits.append((mid, prof))
    if not module_hits:
        print(f"no module profile in neuron_profiles.json claims `{NEURON_TYPE}`")
    else:
        mid, prof = module_hits[0]
        print(f"module_id       : {mid}")
        print(f"module_name     : {prof.get('name')}")
        print(f"function        : {prof.get('function')}")
        print(f"category        : {prof.get('category')}")
        print(f"motif_pattern   : {prof.get('motif_pattern')}")
        print(f"n_members       : {prof.get('n_members')}")
        print(f"total_synapses  : {prof.get('total_synapses')}")

    # --- the male-neuron ledger, if this type is dimorphic ------------------
    header("Step 5/7  Male-cell classification (male_dimorphism.json)")
    ledger = json.loads((ROOT / "artifacts" / "male_dimorphism.json").read_text(encoding="utf-8"))
    by_type = {r["type"]: r for r in ledger.get("per_type", [])}
    if NEURON_TYPE in by_type:
        r = by_type[NEURON_TYPE]
        print(f"neuron_types_total  : {r.get('neuron_types_total')}")
        print(f"total_synapses      : {r.get('total_synapses'):,}")
        print(f"pct_of_male_syn     : {r.get('pct_of_male_syn')}")
        print(f"touch_pct_of_own    : {r.get('touch_pct_of_own')}")
        print(f"both_ends_male_pct  : {r.get('both_ends_male_pct')}")
        print(f"median_syn_per_cell : {r.get('median_syn_per_cell')}")
        print(f"p90_syn_per_cell    : {r.get('p90_syn_per_cell')}")
        print(f"matching_notes_share: {r.get('matching_notes_share')}")
    else:
        print(f"`{NEURON_TYPE}` is not in the dimorphic list -> treated as a general-purpose cell")

    # --- compare this single cell against its type's distribution -----------
    header("Step 6/7  Is THIS cell representative of its type?")
    type_cells = annot[(annot["neuron_type"] == NEURON_TYPE)]["Neuron ID"].to_numpy()
    weights = np.asarray([int(w) for _, w in zip(sub["pre"], sub["weight"])] if False else sub["weight"], dtype=np.int64)
    # per-cell total synapses for the whole type
    per_cell = edges.groupby("pre", sort=False)["weight"].sum()
    type_sums = per_cell.reindex(type_cells.astype(np.int64)).dropna().astype(np.int64)
    print(f"cells of type {NEURON_TYPE}               : {len(type_sums):,}")
    print(f"type total synapses (sum over cells)      : {int(type_sums.sum()):,}")
    print(f"median synapses per cell of this type     : {int(np.median(type_sums))}")
    print(f"p90 / p99                                 : {int(np.percentile(type_sums,90))} / {int(np.percentile(type_sums,99))}")
    this_cell = int(per_cell.loc[eid])
    pctile = float((type_sums < this_cell).mean()) * 100
    print(f"THIS cell (id {NEURON_ID}): {this_cell:,} synapses  ->  {pctile:.1f}th percentile within its type")

    header("Step 7/7  What you can honestly say about this cell")
    print(f"1. Anatomical identity: {NEURON_ID} is annotated as `{NEURON_TYPE}` "
          f"({a.get('body_type','?')}), curator note: "
          f"{(str(a.get('matching_notes',''))[:120] or '(none)').strip()}")
    print(f"2. Wiring role in the connectome: "
          f"{n_out_post} downstream targets, {n_in_pre} upstream sources, "
          f"{len(pairs):,} distinct partners, {n_syn:,} synapses total.")
    print(f"3. Within-type scale: {pctile:.0f}th percentile — "
          f"{'a typical example of this type' if 33 <= pctile <= 67 else 'NOT a typical example'}")
    if claiming:
        names = ", ".join(u["name"] for u in claiming[:3])
        print(f"4. Library function attached: appears in {len(claiming)} unit(s): {names}")
    else:
        print("4. Library function attached: no unit claims this type — the library has no "
              "function sentence for this cell.")
    print("5. Male-specific? "
          + ("this type IS in the dimorphic list (Step 5)"
             if NEURON_TYPE in by_type else
             "this type is NOT flagged dimorphic -> no male-specific claim"))
    print(f"6. Embodiment gap: of 115 library units, 37 have male CNS wiring verified; "
          f"the {len(claiming)} unit(s) above say `{NEURON_TYPE}` is a member, "
          f"but membership is a *declaration* — the connectome only proves the wiring.")
    print("\nThe connectome says what is WIED. The library says what is CLAIMED. "
          "The gap between the two is the honest boundary of the answer.")


if __name__ == "__main__":
    main()
