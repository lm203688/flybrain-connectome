#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""v2.28.0 — extract circuit profiles from the Drosophila larva connectome.

Source data
-----------
Winding M, Pedigo B, Barnes CL, ... Zlatic M, Cardona A, Vogelstein JT.
"The connectome of an insect brain."  Science 379(6636):eadd9330 (2023),
doi:10.1126/science.add9330

That paper reconstructed the synaptic connectome of a *Drosophila melanogaster
larva* at synapse resolution: 2,956 neurons and 116,922 directed synaptic
edges.  The network is distributed by networks.skewed.de under the handle
``fly_larva`` as three CSVs:

    nodes.csv : index, vids, hemisphere, homologue, cell_type, annotations,
                cluster, _pos
    edges.csv : source, target, count, etype
    gprops.csv: free-text provenance

Two properties of this source make it strictly more informative than the
C. elegans one added in v2.27.0:

* the edges carry a *polarity* annotation (``ad`` = axon->dendrite,
  ``aa`` = axon->axon, ``da`` = dendrite->axon, ``dd`` = dendrite->dendrite),
  so the unit's wiring can be emitted in the library's own connection
  vocabulary instead of being flattened onto the sign-neutral forms;
* the nodes carry an ``annotations`` field with subtype labels written by the
  original authors (``olfactory``, ``gustatory-external``,
  ``noci 2nd_order PN``, ``mechano-Ch 2nd_order PN``, ``proprio``, ...), so a
  profile can name the *modality* it traces rather than a bare cell class.

Honest limits of this source, kept rather than papered over
-----------------------------------------------------------
* no transmitter / excitation-inhibition annotation.  A few subtypes are named
  after their transmitter identity by the authors (``DAN-i1``, ``DAN-g1``
  dopaminergic; ``OAN-g1`` octopaminergic), but the *sign* of no synapse is
  annotated, so ``has_inhibition`` stays False and no inhibitory claim is
  made anywhere in the emitted unit.
* no electrical / gap-junction edge exists in the source at all -- it is a
  chemical-synapse connectome, so ``gap_junction_sync`` never appears here.
* the ``da`` (dendrite->axon) edges are NOT emitted: the library's 66-entry
  connection vocabulary has no ``dendro_axonic`` type (checked, not assumed),
  and inventing a type is worse than declaring the gap.  They are counted and
  reported in the artifact instead.
* nodes are single cells (``hemisphere`` / ``homologue`` are present), not
  cell classes.  Profiles therefore aggregate every cell whose
  ``(cell_type, annotations)`` matches a declared node into one member, which
  is what makes a ``count_ratio`` meaningful.  Left/right homologues collapse
  together the same way, but this is aggregation, not fabrication -- the cell
  count behind every member is recorded.

Usage
-----
    python scripts/extract_larva_profiles.py            # writes the artifact
    python scripts/extract_larva_profiles.py --report   # stdout summary only
"""
from __future__ import annotations

import argparse
import csv
import io
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LARVA_DIR = ROOT / "larva_data"
RAW = LARVA_DIR / "raw"
OUT = ROOT / "flybrain-connectome-mcp" / "functional_units" / "larva_profiles.json"

NODES_CSV = RAW / "nodes.csv"
EDGES_CSV = RAW / "edges.csv"

SOURCE = ("WormWiring / Winding et al. 2023, Science 379:eadd9330 "
          "(doi:10.1126/science.add9330), larva network `fly_larva`")

# etype -> library connection type.  ``da`` is deliberately absent: the
# library has no dendro-axonic type, so those edges are counted, not emitted.
ETYPE_FORM = {
    "ad": "axo_dendritic",
    "aa": "axo_axonic",
    "dd": "dendro_dendritic",
}

# The source's `annotations` field is a long tail of subtypes ("42a PN",
# "33a PN", "Thermo PN 3", "DAN-i1", ...).  Aggregating on it verbatim would
# give a "unit" ninety-odd members, which is not a function unit.  These rules
# fold the tail into modality buckets; they are a curated mapping, so they are
# written out here in plain sight rather than hidden in the aggregation code,
# and every edge that lands in a bucket is still counted out of the source.
_MODALITY_RULES = [
    ("dopaminergic", ("dan-",)),
    ("octopaminergic", ("oan-",)),
    ("olfactory", ("olfactory",)),
    ("gustatory", ("gustatory",)),
    ("gut", ("gut",)),
    ("mechano", ("mechano",)),
    ("noci", ("noci",)),
    ("proprio", ("proprio",)),
    ("thermo", ("thermo",)),
    ("visual", ("visual",)),
    ("respiratory", ("respiratory",)),
]


def bucket(annotations: str, cell_type: str) -> str:
    """Fold a long subtype label onto a modality bucket.

    The authors write several labels into one cell, in no fixed order
    (``Vision PN 1; vPN; visual 2nd_order PN``).  The head token is read
    first so a modality that leads the label keeps priority over one that
    merely appears later (``noci 2nd_order PN; mechano-Ch ...`` is a noci
    cell, not a mechano one); if the head makes no modality claim at all,
    the whole string is searched, which is what stops the visual and
    respiratory channels from being silently filed as "unannotated".
    """
    tokens = [t.strip().lower() for t in annotations.split(";")]
    head = tokens[0] if tokens else ""
    for src in (head, " ".join(tokens)):
        for name, keys in _MODALITY_RULES:
            if any(k in src for k in keys):
                return name
    return "unannotated"


def _slug(cell_type: str, modality: str) -> str:
    """The profile name for a (cell_type, modality) pair.

    One function, used by both the members and the neuron profiles: the two
    must agree or gate 9 breaks on a KeyError nobody can explain.
    """
    ct = cell_type.lower().replace("-", "_")
    if not modality:
        return ct
    return ct + "_" + modality.lower().replace(" ", "_").replace("-", "_")


# Declared shapes of the profiles.  A node is
#     (cell_type, modality_bucket, role)
# where an empty bucket matches every cell of that type whatever its modality.
PROFILES = [
    {
        "suffix": "olfactory_associative_learning",
        "display": "幼虫嗅觉关联学习单元",
        "function": "associative_learning",
        "system": "learning",
        "desc": ("嗅觉感受神经元经局部中间神经元 LN 交给投射神经元 PN，PN 再经"
                 "蕈状体 KC 汇到输出神经元 MBON；KC 之间以及 KC 到 MBIN 的"
                 "自反馈边是这条通路里权重最高的一部分，也是幼虫 scent-memory "
                 "回路在连接组里可直接量到的部分。"),
        "nodes": [("sensory", "olfactory", "receptor"),
                  ("LN", "", "local_int"),
                  ("PN", "", "projection"),
                  ("KC", "", "kenyon"),
                  ("MBON", "", "output")],
        "in_ports": [("odor", "sensory.olfactory", True)],
        "out_ports": [("valence", "memory.associative", True)],
        "nts": [],
        "hints": ["associative_learning", "sparse_expansion", "mushroom_body"],
        "lead": "associative_learning",
    },
    {
        "suffix": "somatosensory_escape",
        "display": "幼虫躯感逃逸反射单元",
        "function": "escape_reflex",
        "system": "motor",
        "desc": ("PN-somato 携带作者标注的 noci / mechano-Ch / proprio 三种二级"
                 "感受亚型，把这些躯感通道交给外侧角 LHN，再汇到 descending "
                 "pre-DN-VNC 送出脑外；这是连接组里唯一能按模态逐亚型追踪的"
                 "感觉-运动通路。"),
        "nodes": [("PN-somato", "noci", "noci_relay"),
                  ("PN-somato", "mechano", "mechano_relay"),
                  ("PN-somato", "proprio", "proprio_relay"),
                  ("LHN", "", "lateral_horn"),
                  ("pre-DN-VNC", "", "descending"),
                  ("CN", "", "central_int"),
                  ("ascending", "noci", "ascending_hub")],
        "in_ports": [("noxious", "sensory.nociceptive", True)],
        "out_ports": [("escape", "motor.escape", True)],
        "nts": [],
        "hints": ["sensory_motor", "reflex_arc", "escape"],
        "lead": "escape",
    },
    {
        "suffix": "gustatory_feeding_program",
        "display": "幼虫味觉摄食程序单元",
        "function": "feeding",
        "system": "motor",
        "desc": ("外部味觉、咽部味觉与肠内感受三类神经元都把输入送到 DN-SEZ"
                 "（口咽部下降神经元池）与 RGN（环腺神经元），共用一个摄食"
                 "输出级；这条通路把内脏信号和口部运动接到同一级，是连接组里"
                 "可逐边追踪的摄食汇聚点。"),
        "nodes": [("sensory", "gustatory", "taste"),
                  ("sensory", "gut", "enteric"),
                  ("DN-SEZ", "", "feed_output"),
                  ("RGN", "", "endocrine")],
        "in_ports": [("taste", "sensory.gustatory", True)],
        "out_ports": [("feeding", "motor.feeding", True)],
        "nts": [],
        "hints": ["feeding", "convergent_fanin", "motor_pool"],
        "lead": "feeding",
    },
    {
        "suffix": "descending_motor_command",
        "display": "幼虫下降运动指令单元",
        "function": "motor_command",
        "system": "motor",
        "desc": ("pre-DN-VNC 既接收 CN 与 PN-somato 的输入，也直接把运动指令"
                 "交给 DN-VNC 送往腹神经索；同类之间的耦合边在本连接组里权重"
                 "极高，说明下降池内部本身就是一个强耦合的指令层。"),
        "nodes": [("CN", "", "central_input"),
                  ("PN-somato", "", "somatosensory_input"),
                  ("pre-DN-VNC", "", "command"),
                  ("DN-VNC", "", "descending_out")],
        "in_ports": [("command_drive", "motor.command", True)],
        "out_ports": [("locomotion", "motor.posture", True)],
        "nts": [],
        "hints": ["command_drive", "motor_pool", "descending"],
        "lead": "command_drive",
    },
    {
        "suffix": "mushroom_body_feedback",
        "display": "幼虫蕈状体反馈调制单元",
        "function": "modulation",
        "system": "modulatory",
        "desc": ("MBIN 亚型里作者标注了 DAN-i1/DAN-g1（多巴胺能）与 OAN-g1"
                 "（章鱼胺能），它们回连 KC 形成蕈状体内部的调制环；LHN 与 "
                 "MB-FBN 再把这个环接到外侧角输入侧，构成可测量的反馈臂。"),
        "nodes": [("LHN", "", "lateral_horn"),
                  ("MB-FBN", "", "feedback"),
                  ("MBIN", "", "modulatory"),
                  ("KC", "", "kenyon"),
                  ("MBON", "", "output")],
        "in_ports": [("modulation", "modulatory.dopamine", True)],
        "out_ports": [("gate", "gating.attention", True)],
        "nts": ["dopamine", "octopamine"],
        "hints": ["modulation", "recurrent_feedback", "sparse_code"],
        "lead": "modulation",
    },
    {
        "suffix": "thermosensory_relay",
        "display": "幼虫温度感受中继单元",
        "function": "thermoreception",
        "system": "sensory",
        "desc": ("作者标注的 thermo-cold / thermo-warm 感受神经元只有 10 个，它们"
                 "把温度信号交给 8 个 thermo 投射神经元（tPN，实测 939 突触），"
                 "tPN 再分两路：外侧角 LHN（509 突触）与蕈状体 KC（222 突触）。"
                 "温度信息进到 KC 这一支是这条通路最值得记的一点——同一批 tPN "
                 "同时喂外侧角的运动侧与蕈状体的稀疏编码侧，而这条边在连接组里是"
                 "可直接数出来的。"),
        "nodes": [("sensory", "thermo", "receptor"),
                  ("PN", "thermo", "relay"),
                  ("LHN", "", "lateral"),
                  ("KC", "", "kenyon")],
        "in_ports": [("temperature", "thermal.vector", True)],
        "out_ports": [("drive", "motor.posture", True)],
        "nts": [],
        "hints": ["thermosensory", "relay", "sparse_code"],
        "lead": "relay",
    },
    {
        "suffix": "visual_relay",
        "display": "幼虫视觉信号中继单元",
        "function": "visual_relay",
        "system": "sensory",
        "desc": ("幼虫的外围光感受神经元（作者标注 visual，29 个）在这个重建里"
                 "把轴突送到两类细胞：局部中间神经元 LN（830 突触）与二级视觉"
                 "投射神经元 vPN（696 突触）；vPN 再汇到外侧角 LHN（1,142 突触）。"
                 "这条单元覆盖了库里此前唯一一个按视觉标注逐边追下来的通道。"),
        "nodes": [("sensory", "visual", "receptor"),
                  ("PN", "visual", "relay"),
                  ("LN", "", "local"),
                  ("LHN", "", "lateral")],
        "in_ports": [("light", "sensory.visual", True)],
        "out_ports": [("steer", "navigation.steering", True)],
        "nts": [],
        "hints": ["visual", "relay", "feedforward"],
        "lead": "relay",
    },
    {
        "suffix": "respiratory_relay",
        "display": "幼虫内部状态（呼吸）中继单元",
        "function": "respiratory_relay",
        "system": "respiratory",
        "desc": ("作者把 26 个感受神经元标注成 respiratory（气管/呼吸相关）。"
                 "连接组里它们指向三层：上行反馈神经元 ascending（151 突触）、"
                 "口咽部下降神经元池 DN-SEZ（51 突触）与内分泌级 RGN（31 突触）——"
                 "也就是把内部状态信号接到运动级与神经内分泌级。这条单元刻意不"
                 "声明任何行为：源只给了模态标签，没给行为，能追下来的就是这三跳。"),
        "nodes": [("sensory", "respiratory", "receptor"),
                  ("ascending", "", "feedback"),
                  ("DN-SEZ", "", "motor"),
                  ("RGN", "", "endocrine")],
        "in_ports": [("internal", "sensory.*", True)],
        "out_ports": [("ventilation", "motor.respiration", True)],
        "nts": [],
        "hints": ["internal_state", "relay", "feedback"],
        "lead": "relay",
    },
]


def _rows(path: Path):
    """The skewed.de CSVs prefix the real header with a '#' comment line, and
    every column name carries a leading space; both are stripped here."""
    with open(path, newline="", encoding="utf-8") as f:
        lines = f.readlines()
    header = lines[0].lstrip("#").strip()
    body = io.StringIO(header + "\n" + "".join(lines[1:]))
    for r in csv.DictReader(body):
        yield {k.strip(): v for k, v in r.items()}


def load():
    """Return ([(source, target, etype, count)], {idx: node record})."""
    if not NODES_CSV.exists() or not EDGES_CSV.exists():
        raise SystemExit(
            "missing larva source files under %s (run the download step)"
            % RAW)
    nodes = {}
    for i, r in enumerate(_rows(NODES_CSV)):
        nodes[i] = {
            "cell_type": (r.get("cell_type") or "").strip(),
            "annotations": (r.get("annotations") or "").strip(),
            "hemisphere": (r.get("hemisphere") or "").strip(),
            "homologue": (r.get("homologue") or "").strip(),
        }
    edges = []
    for r in _rows(EDGES_CSV):
        edges.append((int(r["source"]), int(r["target"]),
                      (r.get("etype") or "").strip(),
                      int(r["count"] or 0)))
    return edges, nodes


def _key(cell_type: str, annotations: str) -> tuple:
    return (cell_type, bucket(annotations, cell_type))


def _resolve(nodes: dict, cell_type: str, want: str) -> list:
    out = []
    for i, n in nodes.items():
        if n["cell_type"] != cell_type:
            continue
        if want and bucket(n["annotations"], cell_type) != want:
            continue
        out.append(i)
    return out


def neuron_profiles(edges, nodes, keys: set) -> dict:
    """Module-profile entries for every larva node a unit actually uses.

    Like the C. elegans branch, the two topology numbers are measured:
      reservoir_density = that node's synaptic output divided by the largest
                          output of any node in the reconstruction.
      recurrent_pct     = share of that node's own edges that stay inside its
                          own class, i.e. how self-coupled it is.
    has_inhibition stays False: sign is not annotated anywhere in the source.
    """
    out_t, in_t, self_t = {}, {}, {}
    for (a, b, _t, n) in edges:
        ka = _key(nodes[a]["cell_type"], nodes[a]["annotations"])
        kb = _key(nodes[b]["cell_type"], nodes[b]["annotations"])
        if ka in keys:
            out_t[ka] = out_t.get(ka, 0) + n
        if kb in keys:
            in_t[kb] = in_t.get(kb, 0) + n
        if ka == kb and ka in keys:
            self_t[ka] = self_t.get(ka, 0) + n
    mx = max(out_t.values()) or 1
    profiles = {}
    for k in sorted(keys):
        ct, ann = k
        tot = out_t.get(k, 0) + in_t.get(k, 0)
        profiles["larv." + _slug(ct, ann)] = {
            "reservoir_density": round(out_t.get(k, 0) / mx, 3),
            "recurrent_pct": round(self_t.get(k, 0) / tot, 3) if tot else 0.0,
            "has_inhibition": False,
            "description": "Drosophila larva cell class %s (%s) in the Winding "
                           "et al. 2023 connectome" % (ct, ann or "unannotated"),
            "capability": ["traced_connectome", "measure_synapses"],
            "task_hint_pool": ["larva_neuron"],
            "lead_task_hint": "larva_neuron",
            "neurotransmitter": "unannotated",
            "brain_region": "larval_central_nervous_system",
            "species_source": ["drosophila_melanogaster"],
            "allen_class": "",
            "biological_reference": SOURCE,
            "cell_class": ct,
            "annotations": ann,
        }
    return profiles


def build(p: dict, edges, nodes) -> dict:
    # The prefix in a profile declaration is a SELECTOR, not the key.  The key
    # has to come from the cell that was actually selected, because the source
    # fills `annotations` with the literal string "no official annotation" and
    # with the empty string in different cells of the same cell type.
    live, claimed = {}, {}
    for ct, prefix, role in p["nodes"]:
        for i in _resolve(nodes, ct, prefix):
            k = _key(nodes[i]["cell_type"], nodes[i]["annotations"])
            if k in claimed and claimed[k] != role:
                raise SystemExit(
                    "profile %s: cell class %s/%s matches two declared nodes "
                    "with different roles (%s vs %s)"
                    % (p["suffix"], k[0], k[1], claimed[k], role))
            claimed[k] = role
            live[k] = role
    if not live:
        raise SystemExit("profile %s resolves to no cells -- refusing to emit "
                         "an empty module" % p["suffix"])

    counts = Counter()
    for i, n in nodes.items():
        if _key(n["cell_type"], n["annotations"]) in live:
            counts[_key(n["cell_type"], n["annotations"])] += 1
    if not counts:
        raise SystemExit("profile %s has no cells behind its nodes" % p["suffix"])

    # A declared role can cover several modality buckets (all the PN subtypes
    # were one declared node "PN").  The library refuses a unit in which two
    # members share a role, so the largest population keeps the bare role and
    # the rest take a modality suffix -- which keeps the wiring readable about
    # which sensory channel each arm carries.
    roles, taken = {}, set()
    for k in sorted(live, key=lambda k: (-counts[k], k)):
        base, n = live[k], 0
        role = base
        while role in taken:
            n += 1
            role = "%s_%s" % (base, k[1] or n)
        taken.add(role)
        roles[k] = role
    live = roles

    # Several distinct cell pairs collapse onto the same (from, to, form) key
    # once cells are aggregated, so the weights are SUMMED, not overwritten:
    # the emitted synapse count is what the module really contains.
    acc, dropped = {}, 0
    for (a, b, et, n) in edges:
        ka = _key(nodes[a]["cell_type"], nodes[a]["annotations"])
        kb = _key(nodes[b]["cell_type"], nodes[b]["annotations"])
        if ka not in live or kb not in live:
            continue
        form = ETYPE_FORM.get(et)
        if form is None:
            dropped += n          # dendro-axonic: vocabulary gap, counted not emitted
            continue
        acc[(ka, kb, form)] = acc.get((ka, kb, form), 0) + n
    if not acc:
        raise SystemExit("profile %s produced no wiring after polarity mapping"
                         % p["suffix"])

    wiring, emitted_syn = [], Counter()
    for (ka, kb, form), total in acc.items():
        wiring.append({"from": live[ka], "to": live[kb], "type": form,
                       "synapses": total})
        emitted_syn[form] += total

    mx = max(w["synapses"] for w in wiring)
    for w in wiring:
        w["weight"] = round(w["synapses"] / mx, 3)

    total = sum(counts.values())
    return {
        "name": "larv_%s_unit" % p["suffix"],
        "display": p["display"],
        "function": p["function"],
        "system": p["system"],
        "description": p["desc"],
        "members": [{"role": live[k],
                     "neuron": "larv." + _slug(k[0], k[1]),
                     "count_ratio": round(counts[k] / total, 4)}
                    for k in sorted(live)],
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
        "species_source": ["drosophila_melanogaster"],
        "biological_reference": SOURCE,
        "composable_with": [],
        "provenance": {
            "class": "curated-drosophila-larva-connectome",
            "extracted_from_malecns": False,
            "source_connectome": ("Drosophila melanogaster larva "
                                  "(Winding et al. 2023)"),
            "basis": "serial-section EM reconstruction, single-cell nodes "
                     "aggregated to (cell_type, annotation) classes",
            "embodied_in_malecns": False,
            "embodiment_basis": "the MaleCNS anchor table is an adult "
                                "reconstruction; larva and adult are the same "
                                "species but different developmental stages, "
                                "so per-cell-type homology is an inference, "
                                "not a measurement, and is not claimed here",
            "unanchored_reason": "outside_male_cns_species_coverage",
            "evidence_weight": "connectome_derived",
            "connectome_traceable": True,
        },
        "larva_stats": {
            "n_cell_classes": len(live),
            "n_cells": total,
            "n_edges": len(wiring),
            "n_synapses": sum(w["synapses"] for w in wiring),
            "n_axo_dendritic": emitted_syn.get("axo_dendritic", 0),
            "n_axo_axonic": emitted_syn.get("axo_axonic", 0),
            "n_dendro_dendritic": emitted_syn.get("dendro_dendritic", 0),
            "n_dendro_axonic_dropped": dropped,
            "source": SOURCE,
        },
    }, set(live.keys())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true",
                    help="print the summary only; do not write the artifact")
    args = ap.parse_args()

    edges, nodes = load()
    print("loaded %d edges over %d neurons" % (len(edges), len(nodes)))

    units, used = [], set()
    for p in PROFILES:
        u, keys = build(p, edges, nodes)
        s = u["larva_stats"]
        print("  %-46s classes=%2d cells=%4d edges=%4d syn=%6d "
              "(a-d %6d / a-a %5d / d-d %5d / d-a dropped %5d)"
              % (u["name"], s["n_cell_classes"], s["n_cells"], s["n_edges"],
                 s["n_synapses"], s["n_axo_dendritic"], s["n_axo_axonic"],
                 s["n_dendro_dendritic"], s["n_dendro_axonic_dropped"]))
        units.append(u)
        used |= keys

    if args.report:
        return 0

    profiles = neuron_profiles(edges, nodes, used)
    # a member whose profile was never registered would blow up gate 9 far
    # away from here, so check it while the source files are still open
    missing = sorted({m["neuron"] for u in units for m in u["members"]}
                     - set(profiles))
    if missing:
        raise SystemExit("units reference neuron profiles that were not "
                         "registered: %s" % missing)

    doc = {
        "source": SOURCE,
        "note": ("Every edge below is copied from the larva connectome; "
                 "nothing is inferred from memory. The source annotates synapse "
                 "polarity (ad/aa/da/dd) but no transmitter and no sign, so no "
                 "inhibitory claim is made. dendro-axonic (da) edges are "
                 "counted, not emitted: the library's connection vocabulary "
                 "has no such type."),
        "emitted_forms": sorted(ETYPE_FORM.values()),
        "dropped_form": "da (no dendro_axonic type in the library)",
        "units": units,
        "neuron_profiles": profiles,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print("wrote %s (%d units, %d neuron profiles)"
          % (OUT, len(units), len(doc["neuron_profiles"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
