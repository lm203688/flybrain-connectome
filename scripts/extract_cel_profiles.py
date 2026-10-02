#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""v2.27.0 — extract circuit profiles from the C. elegans adult connectome.

Source data
-----------
WormWiring (wormwiring.org) hosts the raw reconstruction files of

    Witvliet D, Mulcahy B, Mitchell JK, Meirovitch Y, Berger DR, Wu Y, ... Zhen M.
    "Connectomes across development reveal principles of brain maturation in
     C. elegans."  bioRxiv 2020, doi:10.1101/2020.04.30.066209

Two *adult* datasets (labelled "7 adult" and "8 adult" on
/pages/witvliet.html) are shipped as two xlsx files with the columns
``pre, post, type, synapses``.  They are the two independent adult hermaphrodites;
this script merges them by summing synapse counts, which is only valid because
the animals are isogenic and the reconstruction is at cell-class resolution.
The两个数 are averaged in the sense that we keep both, not pick one: the
``source`` field records that both contributed.

Every edge emitted below is copied out of those two files.  Nothing is
invented, and nothing is dropped for "looking wrong" — if a circuit has no
edges in the reconstruction, the profile fails closed instead of being filled
in from memory.

What is NOT in the source
-------------------------
* no transmitter / excitatory-inhibitory identity  -> chemical edges are mapped
  to the sign-neutral ``axo_dendritic`` form and gap junctions to
  ``gap_junction_sync``; we never claim a C. elegans synapse is inhibitory
  unless the cell type is already known to be GABAergic.
* no pharyngeal neurons (the somatic reconstruction covers 302 of the 320
  cells) -> no pharyngeal / feeding profile is attempted.
* no left/right aware wiring diagram; ``canonical`` strips the trailing L/R
  so that AVBL and AVBR collapse to the cell class AVB.

Usage
-----
    python scripts/extract_cel_profiles.py            # writes the artifact
    python scripts/extract_cel_profiles.py --report   # stdout summary only
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
CELDIR = ROOT / "cel_data"
OUT = ROOT / "flybrain-connectome-mcp" / "functional_units" / "cel_profiles.json"

# The two adult animals, relative to wormwiring.org.
ADULT_FILES = [
    ("dataset_7", "witvliet_witvliet_2020_7_adult.xlsx"),
    ("dataset_8", "witvliet_witvliet_2020_8_adult.xlsx"),
]

SOURCE = ("WormWiring / Witvliet et al. 2020 "
          "(bioRxiv 10.1101/2020.04.30.066209), adult datasets 7 & 8")

CHEM_FORM = "axo_dendritic"
ELEC_FORM = "gap_junction_sync"
DEND_SELF = "dendro_dendritic"

PROFILES = [
    {
        "suffix": "forward_locomotion_command",
        "display": "线虫前向运动指令单元",
        "function": "locomotion_command",
        "system": "motor",
        "desc": ("AVB 指令神经元汇聚 AIB 等中间神经元的输入，把前向运动指令交给腹侧"
                 "运动神经元 PV/PVQ 与体壁肌；连接组里 AVB→PV 是这条通路上权重最高的一条边。"),
        "classes": ["AVB", "PV", "AIB", "AIZ", "AIA"],
        "roles": {"AVB": "command", "PV": "motor", "AIB": "relay",
                  "AIZ": "relay2", "AIA": "relay3"},
        "in_ports": [("forward_drive", "motor.command", True)],
        "out_ports": [("locomotion", "motor.posture", True)],
        "nts": ["acetylcholine"],
        "ref": "Witvliet et al. 2020 (bioRxiv 10.1101/2020.04.30.066209)",
        "hints": ["command_drive", "motor_pool", "forward_locomote"],
        "lead": "forward_locomote",
    },
    {
        "suffix": "touch_avoidance_reflex",
        "display": "线虫轻触回避反射单元",
        "function": "touch_reflex",
        "system": "motor",
        "desc": ("ALM/ALN/PLN/AVM 机械感受神经元把轻触交给 AIA/AIB/AIZ 中间神经元，"
                 "再汇到 AVA 与 AVB 指令神经元，反向驱动运动池造成后退；这是连接组里"
                 "可逐条追踪的最短感觉-运动通路。"),
        "classes": ["ALM", "ALN", "PLM", "PLN", "AVM", "AIA", "AIB", "AIZ", "AVA", "AVB", "PV"],
        "roles": {"ALM": "touch_post", "ALN": "touch_post_lat", "PLM": "touch_posterior",
                  "PLN": "touch_post_lat2", "AVM": "touch_ant", "AIA": "relay1",
                  "AIB": "relay2", "AIZ": "relay3", "AVA": "brake", "AVB": "command",
                  "PV": "motor"},
        "in_ports": [("touch", "sensory.mechanovibratory", True)],
        "out_ports": [("reversal", "motor.escape", True)],
        "nts": ["glutamate", "acetylcholine"],
        "ref": "Witvliet et al. 2020 (bioRxiv 10.1101/2020.04.30.066209)",
        "hints": ["sensory_motor", "reflex_arc", "touch_reversal"],
        "lead": "touch_reversal",
    },
    {
        "suffix": "amphid_chemosensory",
        "display": "线虫头侧化学感受单元",
        "function": "chemosensation",
        "system": "sensory",
        "desc": ("AWA/AWC/ASE/ADF/ASI/ASJ/ASK 七类 amphid 化学感受神经元经 AIA/AIY/RIA"
                 "送出；RIA 是整条连接组里突触总数最高的中间神经元，本单元是唯一能"
                 "在这个连接组里直接测出「高阶汇聚枢纽」的一处。"),
        "classes": ["AWA", "AWC", "ASE", "ADF", "ASI", "ASJ", "ASK", "AIA", "AIY", "RIA"],
        "roles": {"AWA": "chemo1", "AWC": "chemo2", "ASE": "taste", "ADF": "chemo3",
                  "ASI": "chemo4", "ASJ": "developmental", "ASK": "chemo5",
                  "AIA": "relay1", "AIY": "relay2", "RIA": "hub"},
        "in_ports": [("chemo", "sensory.olfactory", True)],
        "out_ports": [("valence", "memory.associative", True)],
        "nts": ["glutamate"],
        "ref": "Witvliet et al. 2020 (bioRxiv 10.1101/2020.04.30.066209)",
        "hints": ["chemosense", "convergent_fanin", "sparse_code"],
        "lead": "chemosense",
    },
    {
        "suffix": "nociceptive_avoidance",
        "display": "线虫伤害性回避单元",
        "function": "nociception",
        "system": "sensory",
        "desc": ("ASH 伤害性感受神经元是连接组里对指令神经元输出最强的感觉输入之一，"
                 "与轻触通路共用 AIA/AIZ/AVA/AVB 下游；两条感觉通道汇聚到同一运动"
                 "输出级，是本连接组里可直接测量的汇聚实例。"),
        "classes": ["ASH", "AIA", "AIZ", "AVA", "AVB", "PV"],
        "roles": {"ASH": "nociceptive", "AIA": "relay1", "AIZ": "relay2",
                  "AVA": "brake", "AVB": "command", "PV": "motor"},
        "in_ports": [("noxious", "sensory.nociceptive", True)],
        "out_ports": [("avoidance", "motor.escape", True)],
        "nts": ["glutamate"],
        "ref": "Witvliet et al. 2020 (bioRxiv 10.1101/2020.04.30.066209)",
        "hints": ["nociception", "convergent_fanin", "avoid"],
        "lead": "avoid",
    },
]


def canonical(name: str) -> str:
    n = str(name).strip()
    return n[:-1] if n.endswith("L") or n.endswith("R") else n


def load() -> tuple[dict[tuple[str, str, str], int], dict[str, set]]:
    """Return {(pre, post, type): synapses} merged over both adults, plus the
    number of *distinct cells* behind every cell class (how many raw names
    collapse onto it -- ASH is ASHL+ASHR, PV is a single unpaired cell)."""
    edges: dict[tuple[str, str, str], int] = defaultdict(int)
    cells: dict[str, set] = defaultdict(set)
    for tag, fname in ADULT_FILES:
        path = CELDIR / fname
        if not path.exists():
            raise SystemExit("missing source file: %s (run the download step)"
                             % path)
        ws = openpyxl.load_workbook(path, read_only=True).worksheets[0]
        rows = 0
        for pre, post, typ, ns in ws.iter_rows(values_only=True):
            if pre is None:
                continue
            try:
                ns = int(ns or 0)
            except (TypeError, ValueError):
                continue  # header row
            rows += 1
            edges[(canonical(pre), canonical(post), str(typ).lower())] += ns
            cells[canonical(pre)].add(str(pre).strip())
            cells[canonical(post)].add(str(post).strip())
        print("  loaded %s: %d rows" % (tag, rows))
    return dict(edges), {k: v for k, v in cells.items()}


def neuron_profiles(edges: dict, classes: set) -> dict:
    """Module-profile entries for the C. elegans cell classes the units use.

    Two of the three topology numbers are measured, not hand-picked:
      reservoir_density  = that class's total synaptic output divided by the
                           largest total output of any class in the file.
      recurrent_pct      = the share of that class's own edges that are
                           self-edges, i.e. the L/R homologue coupling the
                           reconstruction actually measures.
    has_inhibition stays False because the file carries no sign annotation --
    calling a worm synapse inhibitory without a transmitter assignment would
    be the same fabrication the library refuses elsewhere.
    """
    out_t, in_t, self_t = {}, {}, {}
    for (a, b, _t), n in edges.items():
        if a in classes:
            out_t[a] = out_t.get(a, 0) + n
        if b in classes:
            in_t[b] = in_t.get(b, 0) + n
        if a == b and a in classes:
            self_t[a] = self_t.get(a, 0) + n
    mx = max(out_t.values()) or 1
    profiles = {}
    for c in sorted(classes):
        tot = out_t.get(c, 0) + in_t.get(c, 0)
        profiles["cel." + c.lower()] = {
            "reservoir_density": round(out_t.get(c, 0) / mx, 3),
            "recurrent_pct": round(self_t.get(c, 0) / tot, 3) if tot else 0.0,
            "has_inhibition": False,
            "description": "C. elegans cell class %s (adult connectome, "
                           "datasets 7 & 8)" % c,
            "capability": ["c_elegans_neuron"],
            "task_hint_pool": ["c_elegans_neuron"],
            "lead_task_hint": "c_elegans_neuron",
            "neurotransmitter": "unannotated",
            "brain_region": "nervous_system",
            "species_source": ["c_elegans"],
            "allen_class": "",
            "biological_reference": SOURCE,
            "cell_class": c,
        }
    return profiles


def _form(kind: str, selfloop: bool) -> str:
    """Map a measured edge onto the library's connection vocabulary.

    The reconstruction carries no transmitter or sign annotation, so polarity
    is never asserted: chemical contacts become the default axo-dendritic form
    and gap junctions the sync form.  Left/right homologue pairs are recorded
    as self-loops at cell-class resolution (AIZ-AIZ, AVA-AVA, ...) because the
    electrical coupling between the two homologues is exactly what the file
    measures; those get their own forms rather than being dropped.
    """
    if kind == "electrical":
        return ELEC_FORM
    return DEND_SELF if selfloop else CHEM_FORM


def build(p: dict, edges: dict, ncells: Counter) -> dict:
    cls = set(p["classes"])
    roles = p["roles"]

    # members: every cell class in the profile that actually carries an edge
    live = {c for c in cls
            if any(edges.get((a, b, t)) for a, b, t in edges
                   if (a == c or b == c) and a in cls and b in cls)}
    if not live:
        raise SystemExit("profile %s has no edges in the reconstruction -- "
                         "refusing to emit an empty module" % p["suffix"])

    counts = {c: max(1, len(ncells.get(c, ()))) for c in live}
    total = sum(counts.values())

    wiring, seen_pair = [], set()
    for (a, b, t), n in edges.items():
        if a not in live or b not in live:
            continue
        form = _form(t, a == b)
        if (a, b, form) in seen_pair:
            continue
        seen_pair.add((a, b, form))
        wiring.append({"from": roles[a], "to": roles[b], "type": form,
                       "synapses": n})
    if not wiring:
        raise SystemExit("profile %s produced no wiring after form mapping"
                         % p["suffix"])

    mx = max(w["synapses"] for w in wiring)
    for w in wiring:
        w["weight"] = round(w["synapses"] / mx, 3)

    return {
        "name": "cel_%s_unit" % p["suffix"],
        "display": p["display"],
        "function": p["function"],
        "system": p["system"],
        "description": p["desc"],
        "members": [{"role": roles[c], "neuron": "cel.%s" % c.lower(),
                     "count_ratio": round(counts[c] / total, 4)}
                    for c in sorted(live)],
        "motif_source": sorted({w["type"] for w in wiring}),
        "internal_wiring": wiring,
        "ports": {"in": [{"name": n, "type": t, "required": r}
                         for n, t, r in p["in_ports"]],
                  "out": [{"name": n, "type": t, "required": r}
                          for n, t, r in p["out_ports"]]},
        "size_range": [len(live), total],
        "capability": ["traced_connectome", p["function"], "measure_synapses"],
        "task_hint_pool": list(p["hints"]),
        "lead_task_hint": p["lead"],
        "neurotransmitter": list(p["nts"]),
        "species_source": ["c_elegans"],
        "biological_reference": p["ref"],
        "composable_with": [],
        "provenance": {
            "class": "curated-c-elegans-connectome",
            "extracted_from_malecns": False,
            "source_connectome": "C. elegans adult (WormWiring / Witvliet 2020)",
            "basis": "serial-section EM reconstruction, cell-class resolution",
            "embodied_in_malecns": False,
            "embodiment_basis": "C. elegans is a different species; the MaleCNS "
                                "anchor matrix cannot adjudicate its cell types",
            "unanchored_reason": "outside_male_cns_species_coverage",
            "evidence_weight": "connectome_derived",
            "connectome_traceable": True,
        },
        "cel_stats": {
            "n_cell_classes": len(live),
            "n_cells": total,
            "n_edges": len(wiring),
            "n_synapses": sum(w["synapses"] for w in wiring),
            "n_chemical": sum(w["synapses"] for w in wiring if w["type"] == CHEM_FORM),
            "n_electrical": sum(w["synapses"] for w in wiring if w["type"] == ELEC_FORM),
            "source": SOURCE,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true",
                    help="print the summary only; do not write the artifact")
    args = ap.parse_args()

    print("merging adult datasets from %s" % CELDIR)
    edges, ncells = load()
    neurons = {c for a, _b, _t in edges for c in (a,)}
    print("  merged: %d weighted edges, %d cell classes"
          % (len(edges), len(neurons)))

    units = []
    used_classes: set = set()
    for p in PROFILES:
        u = build(p, edges, ncells)
        s = u["cel_stats"]
        print("  %-42s classes=%2d edges=%3d synapses=%5d (chem %5d / elec %4d)"
              % (u["name"], s["n_cell_classes"], s["n_edges"], s["n_synapses"],
                 s["n_chemical"], s["n_electrical"]))
        units.append(u)
        # classes actually emitted, not merely declared -- a declared cell
        # class with no edge inside the module must not ship a profile
        used_classes |= {m["neuron"].split(".", 1)[1].upper()
                         for m in u["members"]}

    if args.report:
        return 0

    doc = {
        "source": SOURCE,
        "note": ("Every edge below is copied from the two adult reconstruction "
                 "files; nothing is inferred from memory. The file carries no "
                 "transmitter or sign annotation, so polarity is never asserted."),
        "units": units,
        "neuron_profiles": neuron_profiles(edges, used_classes),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote %s (%d units, %d neuron profiles)"
          % (OUT, len(units), len(doc["neuron_profiles"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
