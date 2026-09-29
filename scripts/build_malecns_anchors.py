#!/usr/bin/env python3
"""Build the MaleCNS *embodiment* layer for the functional-unit library.

WHY THIS EXISTS
---------------
Every one of the 82 functional units in `functional_units.json` is curated from
comparative-neuroscience literature. The library therefore carries a permanent
hole: nothing in it has ever been checked against the real connectome it was
named after. A reader cannot tell a unit describing *Drosophila* circuitry from
a unit describing mouse cortex, because both look identical in the JSON.

This script closes that hole for the subset where it is honest to do so. It does
NOT try to prove that a literature circuit is the circuit the fly uses. It does
two weaker, checkable things:

  1. **Presence** — for each neuron population used by the library, find the real
     annotated cell types it corresponds to in MaleCNS v1.0, and how many real
     cells carry them. A population either has evidence or it does not; there is
     no "probably".
  2. **Measured structural backbone** — one pass over the real synapse table
     yields the full 27x27 superclass-to-superclass matrix (synapses + edges).
     That lets any declared connection be *falsified*: if a unit declares
     A -> B and the real connectome contains zero synapses from A's superclass to
     B's superclass, the unit is contradicted at the coarsest possible
     resolution. Zero contradictions is a real result; support at this
     resolution is weak and is reported as weak.

WHAT IT IS NOT
--------------
`extracted_from_malecns` stays **false** for every unit. Anchoring proves the
parts exist and that the declared pathway is not contradicted; it does not prove
the declared microcircuit or its connection FORM. Superclass-level support is a
falsification net, not a confirmation machine.

THE RULE TABLE IS DATA, AND IT PRINTS ITS OWN EVIDENCE
------------------------------------------------------
`TYPE_RULES` maps a MODULE_PROFILES name to an explicit regex over the real
`type` column. Rules are deliberately narrow and every match is written into the
artifact, so any over-reach is auditable by reading the JSON rather than by
trusting this file. Profiles whose identity is a mammalian cell class (e.g.
`interneuron_pv`, `hippocampal_ca1`) are *never* anchored to fly cells even when
their `species_source` list happens to contain "drosophila" -- that list means
"this cell class also exists in flies", not "this profile is the fly cell".

Usage:
    python scripts/build_malecns_anchors.py            # build + write artifact
    python scripts/build_malecns_anchors.py --check    # recompute, compare, no write

Needs numpy + pyarrow and a local MaleCNS v1.0 copy under FLYBRAIN_DATA_DIR.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "flybrain-connectome-mcp"
OUT = PKG / "functional_units" / "malecns_anchors.json"
ANCHOR_SCHEMA = "1.0"

DATA_DIR = Path(os.environ.get("FLYBRAIN_DATA_DIR",
                               str(ROOT / "male_cns")))
ANN_FEATHER = DATA_DIR / "flat-connectome" / "body-annotations-male-cns-v1.0-minconf-0.5.feather"
CACHE = DATA_DIR / "connectome_cache"
CONN_STATS = DATA_DIR / "connectivity_stats.json"
NEUROPIL_STATS = DATA_DIR / "neuropil_stats.json"

# The authoritative neuron subgraph, cross-checked after the matrix pass.
EXPECTED_SYNAPSES = 124_177_617
EXPECTED_EDGES = 25_582_938
EXPECTED_NEURONS = 166_700

CHUNK = 4_000_000


# ---------------------------------------------------------------------------
# Rule table: MODULE_PROFILES name -> real MaleCNS `type` regex.
#
# Only profiles whose identity IS a Drosophila/insect cell class appear here.
# `note` states the anatomical claim so a reviewer can reject it on sight.
# ---------------------------------------------------------------------------
# A rule fires only when the regex matches AND the dataset's own `superclass`
# agrees (when `superclass` is given). The superclass filter is what keeps a
# name-based rule from swallowing look-alikes: `^DN` alone also catches the
# clock neurons DN1a/DN1pA (cb_intrinsic) and the endocrine DNES cells, which
# are not descending neurons at all.
CB = ["cb_intrinsic"]
CB_OL = ["cb_intrinsic", "ol_intrinsic"]
DESC = ["descending_neuron", "efferent_descending", "sensory_descending"]

TYPE_RULES: list[dict] = [
    {"profile": "kenyon_cell", "type_re": r"^KC", "superclass": CB,
     "note": "Kenyon cells: the KCg / KCab / KCa'b' clans, the intrinsic MB cells."},
    {"profile": "mushroom_body_dan", "type_re": r"^(PAM|PPL|PPM)",
     "superclass": CB,
     "note": "Dopaminergic neurons of the MB: the PAM / PPL / PPM clans."},
    {"profile": "mushroom_body_output", "type_re": r"^MBON", "superclass": CB,
     "note": "MB output neurons (MBONs)."},
    {"profile": "mushroom_body_apl", "type_re": r"^APL", "superclass": CB,
     "note": "The single giant GABAergic MB feedback neuron (APL)."},
    {"profile": "antennal_lobe_pn", "type_re": r"(adPN|lPN|uPN|vPN|lvPN|MPN|mPN)",
     "superclass": CB_OL,
     "note": "Antennal-lobe projection neurons: adPN / lPN / lvPN / uPN classes."},
    {"profile": "antennal_lobe_ln", "type_re": r"^(LN[0-9]|LNO|GLNO)",
     "superclass": CB,
     "known_narrow": True,
     "note": "Antennal-lobe local neurons, narrowly matched on the unambiguous LNO / GLNO / "
             "LN-number classes. Deliberately excludes LNd (a clock group, not an AL LN), so "
             "this is a LOWER BOUND on the AL local-neuron population, not the whole class."},
    {"profile": "central_complex_eb", "type_re": r"^(EPG|EL[0-9]?$|EL$|E-PG|PEG)",
     "superclass": CB, "note": "Ellipsoid-body columnar cells (EPG) plus the EL/PEG tangential set."},
    {"profile": "central_complex_pb", "type_re": r"^(PEN|IB[0-9])", "superclass": CB,
     "note": "Protocerebral-bridge columnar cells: PEN_a/PEN_b and the IB* columnar types."},
    {"profile": "central_complex_fb", "type_re": r"^(PFN|PFNa|PFNd|FS[0-9]|FC[0-9])",
     "superclass": CB,
     "note": "Fan-shaped-body columnar cells: PFN/PFNa/PFNd and the FS/FC sets."},
    {"profile": "central_complex_noduli", "type_re": r"^Nod[0-9]",
     "superclass": CB + ["visual_projection"],
     "caveat": "The dataset files Nod1-5 under `visual_projection`, not cb_intrinsic, "
               "which is unexpected for CX noduli cells. The match is therefore a NAME "
               "match with a possibly wrong dataset label; treat as low confidence.",
     "note": "Noduli cells (Nod1-5) -- the smallest CX neuropil."},
    {"profile": "central_complex_ring", "type_re": r"^(vDelta|hDelta|Delta[0-9]|ER[0-9])",
     "superclass": CB,
     "note": "Ring neurons of the ellipsoid body: Delta / vDelta / hDelta and the ER series."},
    {"profile": "clock_neuron_ln", "type_re": r"^(l-LNv|s-LNv|LNd_[a-z]|LNd[0-9]|LN60|5thsLNv)",
     "superclass": CB_OL + ["visual_projection", "sensory_descending"],
     "note": "Lateral clock neurons (the LN groups)."},
    {"profile": "clock_neuron_slnv", "type_re": r"^(s-LNv|5thsLNv)",
     "superclass": CB_OL + ["visual_projection"],
     "note": "Small ventral lateral clock neurons -- the master pacemaker subset."},
    {"profile": "descending_neuron", "type_re": r"^DN", "superclass": DESC,
     "note": "Descending neurons (DNg / DNp / DNge / DNpe / DNx) carrying brain output to "
             "the VNC. The superclass filter excludes the clock DN1/DN2/DN3 cells and the "
             "DNES endocrine cells that share the name prefix."},
    # ---------------- v1.8.0: Drosophila-shaped unit expansion -------------
    # Same discipline as above: a name regex AND the dataset's own superclass
    # must both agree. Optic-lobe names are systematic (T4a-d, TmY18, L1-L5,
    # LC12...) but look-alikes exist in other superclasses, so the filter stays
    # load-bearing everywhere.
    {"profile": "ol_photoreceptor_r1r6", "type_re": r"^R1-R6$",
     "superclass": ["ol_sensory"],
     "note": "Outer photoreceptors R1-R6: the dataset types the whole outer channel "
             "as one class. The exact-match regex plus ol_sensory excludes any other "
             "R-prefixed type."},
    {"profile": "ol_photoreceptor_r7r8", "type_re": r"^R[78]", "superclass": ["ol_sensory"],
     "note": "Inner photoreceptors R7/R8 (R7y/R7p/R8y/R8_unclear and friends): the "
             "colour channel that bypasses the lamina and targets the medulla."},
    {"profile": "ol_lamina_monopolar", "type_re": r"^L[1-5]$", "superclass": ["ol_intrinsic"],
     "note": "Lamina monopolar cells L1-L5, exact matches only so that LC12/LT51/LAL094 "
             "style names can never be swallowed."},
    {"profile": "ol_medulla_intrinsic", "type_re": r"^(Tm[0-9]|TmY[0-9]|Mi[0-9])",
     "superclass": ["ol_intrinsic"],
     "note": "Medulla columnar cells: Tm1-20, TmY series and the Mi series - the "
             "early-vision compute layer."},
    {"profile": "ol_motion_detector_t45", "type_re": r"^T[45][a-d]$",
     "superclass": ["ol_intrinsic"],
     "note": "T4a-d / T5a-d: the eight direction-selective elementary motion detector "
             "classes, one per lobula-plate layer and direction."},
    {"profile": "ol_lptc", "type_re": r"^(HS|VS|CH|FD)", "superclass": ["visual_projection"],
     "note": "Lobula-plate tangential cells (HSN/HSE/HSS/HST, VS/VST, CH, FD): the "
             "wide-field optic-flow integrators. Few but famous."},
    {"profile": "ol_lpi", "type_re": r"^LPi[0-9]", "superclass": ["ol_intrinsic"],
     "note": "Lobula-plate intrinsic cells LPi: GABAergic inter-columnar links behind "
             "directional opponency."},
    {"profile": "ol_visual_lc", "type_re": r"^LC[0-9]", "superclass": ["visual_projection"],
     "note": "Lobula columnar (LC) visual projection neurons: feature- and target-"
             "selective detectors with named glomerular targets."},
    {"profile": "escape_giant_fiber", "type_re": r"^DNp01$", "superclass": DESC,
     "note": "The giant fiber: MaleCNS type DNp01, the descending jump-escape command "
             "neuron (instances carry the (GF) annotation)."},
    {"profile": "escape_vnc_gfc", "type_re": r"^GFC[0-9]", "superclass": ["vnc_intrinsic"],
     "note": "Giant-fiber-connected interneurons GFC1-4 in the ventral nerve cord."},
    {"profile": "escape_psi", "type_re": r"^PSI$", "superclass": ["vnc_efferent"],
     "note": "The peripheral synapsing interneuron (PSI), relay of the DLM escape branch."},
    {"profile": "escape_jump_motor", "type_re": r"^(TTMn|DLMn|STTMm)",
     "superclass": ["vnc_motor"],
     "note": "Jump/flight-power motor neurons: TTMn (tergotrochanteral jump), DLMn and "
             "STTMm (dorsal longitudinal / steering flight power)."},
    {"profile": "courtship_pc1", "type_re": r"^pC1", "superclass": ["cb_intrinsic"],
     "note": "The pC1/P1 courtship decision cluster: 49 MaleCNS types. The superclass "
             "filter keeps the match inside the brain."},
    {"profile": "courtship_asp", "type_re": r"^aSP", "superclass": ["cb_intrinsic"],
     "note": "Male-specific aggression neurons: the aSP10 subtypes."},
    {"profile": "courtship_pip", "type_re": r"^pIP[0-9]", "superclass": DESC,
     "note": "pIP1/pIP10: courtship descending neurons carrying the decision to the VNC."},
    {"profile": "song_vnc_int", "type_re": r"^(vMS|vPR)", "superclass": ["vnc_intrinsic"],
     "note": "VNC song-network interneurons: the vMS11/vMS12 and vPR song pattern "
             "generator classes."},
    {"profile": "song_vpo", "type_re": r"^vpo", "superclass": ["cb_intrinsic"],
     "note": "Ventral protocerebrum song-pathway cells vpoEN/vpoIN: recurrent partners "
             "of pC1. Note they are BRAIN cells - do not retag them as VNC."},
    {"profile": "auditory_ammc", "type_re": r"^AMMC", "superclass": ["cb_intrinsic"],
     "note": "Antennal mechanosensory and motor centre (AMMC) neurons: the first brain "
             "relay of near-field sound, i.e. the courtship song."},
    {"profile": "lateral_horn_ln", "type_re": r"^LH", "superclass": ["cb_intrinsic"],
     "note": "Lateral horn neuron families (LHPV/LHLN/...): the innate-odour centre. "
             "Broad by design - the LH is typed by hundreds of families, all of them "
             "lateral horn cells."},
    {"profile": "antennal_orn", "type_re": r"^ORN_", "superclass": ["cb_sensory"],
     "note": "Olfactory receptor neurons typed per glomerular class (ORN_DA1, ORN_VA1d, "
             "...). This resolves what the generic `olfactory_receptor` profile could "
             "not: the fly ORN classes ARE published in this release."},
    # ---------------- v1.9.0: remaining cleanly-anchorable fly circuits ----
    {"profile": "octopamine_vum", "type_re": r"^OA-VU|^OA-VP",
     "superclass": ["cb_intrinsic"],
     "note": "Octopaminergic ventral unpaired median neurons (OA-VUMa / OA-VPM): "
             "the invertebrate arousal / effort system."},
    {"profile": "looming_lplc", "type_re": r"^LPLC",
     "superclass": ["visual_projection"],
     "note": "Lobula plate lobula columnar (LPLC1 / LPLC2 / LPLC4): expanding-loom "
             "/ collision detectors feeding the visual escape pathway."},
    {"profile": "pharyngeal_gustatory", "type_re": r"^PhG",
     "superclass": ["cb_sensory"],
     "note": "Pharyngeal (PhG) sensory neurons: taste / feeding input from the "
             "proboscis / cibarial region."},
    # ---------------- v1.10.0: VNC + peripheral neuron-profile densification ----
    # 20 neuron populations newly anchored to real MaleCNS v1.0 superclasses.
    {"profile": "vnc_leg_motor_pool", "type_re": r"^MN(a[dg]|n[mnl]|m[lh]|w|m)|^Fe |^Acc\.|^Ster",
     "superclass": ["vnc_motor"],
     "note": "VNC leg/abdominal motor neurons (MNad* leg, MNhl/MNml/MNnm body-wall, "
             "Fe reductor, Acc. tibiae, Ster sternal): motor output of leg and "
             "abdomen behaviour."},
    {"profile": "haltere_muscle_pool", "type_re": r"^hg[1-4]",
     "superclass": ["vnc_motor"],
     "note": "Haltere muscle motor neurons hg1-4: drive the gyroscopic halteres, "
             "a dedicated flight-stabilization channel."},
    {"profile": "wing_depressor_pool", "type_re": r"^b[12]",
     "superclass": ["vnc_motor"],
     "note": "Wing depressor motor neurons b1/b2: paired with the wing flexor for "
             "the ~200 Hz wing-beat depression."},
    {"profile": "pleural_promotor_pool", "type_re": r"^Tergop|^Pleu",
     "superclass": ["vnc_motor"],
     "note": "Tergopleural / pleural promotor motor neurons: thoracic axial "
             "posturing and wing-steering base."},
    {"profile": "vnc_flight_power_pool", "type_re": r"^DLMn|^DVMn|^STTMm",
     "superclass": ["vnc_motor"],
     "note": "Flight power motor neurons DLMn/DVMn/STTMm: dorsal longitudinal and "
             "dorsal ventral muscles powering the wing stroke."},
    {"profile": "vnc_efferent_pool", "type_re": r"^E[AN]",
     "superclass": ["vnc_efferent"],
     "note": "VNC efferent / intermediate-motor neurons (EN*, EA*): sensory-to-"
             "motor gating interneurons of the ventral nerve cord."},
    {"profile": "vnc_sensory_pool", "type_re": r".+",
     "superclass": ["vnc_sensory"],
     "note": "All VNC-resident sensory neurons (mechanoreceptors, chordotonal "
             "organs, stretch receptors of abdomen / thorax): segmental input."},
    {"profile": "oa_visual_centrifugal_pool", "type_re": r"^OA-",
     "superclass": ["visual_centrifugal"],
     "note": "Octopaminergic centrifugal neurons (OA-AL2i*, OA-ASM*) projecting "
             "back to the optic lobe: the visual arousal / attention channel."},
    {"profile": "johnston_organ_mechano", "type_re": r"^JO-",
     "superclass": ["cb_sensory"],
     "note": "Johnston organ mechanoreceptors on the flagellum (JO-A..F, JO-E): "
             "wind detection and antenna position sense."},
    {"profile": "proboscis_mechano_pool", "type_re": r"^a?PhM|^Mn_|^Lab",
     "superclass": ["cb_sensory"],
     "note": "Proboscis / labellar mechanosensory neurons (aPhM, Mn_, Lab): "
             "mouthpart touch and feeding tactile input."},
    {"profile": "vnc_interneuron_pool", "type_re": r".+",
     "superclass": ["vnc_intrinsic"],
     "note": "VNC intrinsic interneurons (the bulk of the ventral nerve cord): "
             "local pattern generators and sensory-motor integration."},
    {"profile": "cb_motor_pool", "type_re": r".+",
     "superclass": ["cb_motor"],
     "note": "Central-brain motor neurons (cb_motor superclass): brain-internal "
             "effector output."},
    {"profile": "cb_endocrine_pool", "type_re": r".+",
     "superclass": ["cb_endocrine"],
     "note": "Central-brain endocrine neurons (corpus cardiacum / allatum inputs): "
             "neurohormone release into the haemolymph."},
    {"profile": "vnc_endocrine_pool", "type_re": r".+",
     "superclass": ["vnc_endocrine"],
     "note": "Ventral nerve cord endocrine neurons: segmental neurohormone release."},
    {"profile": "sensory_ascending_pool", "type_re": r".+",
     "superclass": ["sensory_ascending"],
     "note": "Sensory ascending neurons: carry segmental / peripheral sensory "
             "information up to brain centres."},
    {"profile": "efferent_ascending_pool", "type_re": r".+",
     "superclass": ["efferent_ascending"],
     "note": "Efferent ascending neurons: brain-to-VNC motor copies / corollary "
             "discharge."},
    {"profile": "cb_efferent_pool", "type_re": r".+",
     "superclass": ["cb_efferent"],
     "note": "Central-brain efferent neurons: a small brain output class."},
    {"profile": "visual_projection_tbc_pool", "type_re": r".+",
     "superclass": ["visual_projection_tbc"],
     "note": "Visual projection neurons still to be classified (visual_projection_"
             "tbc): the residual optic-flow projection channel."},
    {"profile": "efferent_descending_pool", "type_re": r".+",
     "superclass": ["efferent_descending"],
     "note": "Efferent descending neurons: motor commands from brain to VNC."},
    {"profile": "sensory_descending_pool", "type_re": r".+",
     "superclass": ["sensory_descending"],
     "note": "Sensory descending neurons: descending neurons carrying sensory-"
             "state information back down the cord."},
    # ---------------- v1.22.0: ascending_neuron superclass densification ----
    # The dataset's `ascending_neuron` superclass (1,846 bodies, 567 types)
    # is DISJOINT from `sensory_ascending` (537) and `efferent_ascending` (8) --
    # each neuron body sits in exactly one superclass, so this pool is the
    # remaining "ascending" channel that neither sensory- nor efferent-
    # ascending captures. Its type names (AN01-AN23 A/B, IN/vMS/dMS variants)
    # are a distinct numbering system, not a sub-class of the other two.
    {"profile": "ascending_neuron_pool", "type_re": r".+",
     "superclass": ["ascending_neuron"],
     "note": "Ascending neurons (AN01-AN23 A/B families plus IN / vMS / dMS "
             "variants): the general ascending channel from VNC / peripheral "
             "segments up to brain centres. A separate superclass from "
             "sensory_ascending (which this pool does NOT duplicate) and "
             "efferent_ascending; the dataset's own type prefix AN is the "
             "distinctive marker."},
]

# Profiles that ARE a fly cell class but whose real counterpart could not be
# resolved narrowly enough to anchor. Recorded, never silently dropped.
UNRESOLVED: dict[str, str] = {
    "interneuron_npf": "only ITP-NPFL1-I matched; not a defensible NPF-cell anchor",
    "interneuron_nph": "no NPH-named type in MaleCNS v1.0",
    "interneuron_kcn": "no KCN-named type in MaleCNS v1.0",
    "interneuron_lamp": "no LAMP-named type in MaleCNS v1.0",
    "olfactory_receptor": "the profile is a receptor, not a neuron; ORNs sit in ol_sensory "
                          "but no per-receptor-class typing is published in this release",
}

# Which real ROIs each library `system` corresponds to. Kept explicit and short:
# a system is mapped only when the ROI set is unambiguous.
SYSTEM_REGIONS: dict[str, list[str]] = {
    "antennal_lobe": ["AL(L)", "AL(R)"],
    "central_complex": ["EB", "PB", "FB", "NO"],
    "mushroom_body": ["CA(L)", "CA(R)", "PED(L)", "PED(R)", "aL(L)", "aL(R)",
                      "a'L(L)", "a'L(R)", "bL(L)", "bL(R)", "b'L(L)", "b'L(R)",
                      "gL(L)", "gL(R)"],
    "optic_lobe": ["AME(L)", "AME(R)", "LA(L)", "LA(R)", "ME(L)", "ME(R)",
                   "LO(L)", "LO(R)", "LOP(L)", "LOP(R)"],
    "lateral_horn": ["LH(L)", "LH(R)"],
}

# Profiles whose `species_source` mentions Drosophila but whose IDENTITY is a
# vertebrate cell class. Anchoring these to fly cells would be a category error.
MAMMAL_SHAPED = [
    "cerebellar_granule", "cerebellar_purkinje", "cholinergic_mt", "dopaminergic_vta",
    "interneuron_pv", "retinal_amacrine", "retinal_bipolar", "retinal_gc",
    "retinal_horizontal", "serotonergic_raphe", "spinal_motor_alpha",
    "spinal_motor_gamma", "thalamic_relay",
]

FLY_HINTS = ("drosophila", "insect", "locust", "monarch", "honeybee", "moth", "mosquito")


# ---------------------------------------------------------------------------
def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def load_neurons() -> tuple[dict[int, str], dict[int, str]]:
    """Return (bodyId -> type, bodyId -> superclass) for the authoritative 166,700.

    Rows without a `superclass` are not neurons in this release; duplicate
    bodyIds keep their first annotated row.
    """
    import pyarrow.feather as feather
    t = feather.read_table(str(ANN_FEATHER),
                           columns=["bodyId", "type", "superclass"],
                           memory_map=True)
    ty: dict[int, str] = {}
    sc: dict[int, str] = {}
    for r in t.to_pylist():
        s = r["superclass"]
        if s is None:
            continue
        b = int(r["bodyId"])
        if b in sc:
            continue
        sc[b] = s
        ty[b] = r["type"] or ""
    return ty, sc


def build_profile_anchors(ty: dict[int, str], sc: dict[int, str]) -> dict:
    by_type: dict[str, list[int]] = {}
    for b, name in ty.items():
        if not name:
            continue
        by_type.setdefault(name, []).append(b)

    anchors: dict[str, dict] = {}
    for rule in TYPE_RULES:
        rx = re.compile(rule["type_re"])
        allowed = set(rule.get("superclass") or ())
        hits: list[dict] = []
        for name, bodies in by_type.items():
            if not rx.search(name):
                continue
            if allowed:
                bodies = [b for b in bodies if sc[b] in allowed]
                if not bodies:
                    continue
            superclasses = sorted({sc[b] for b in bodies})
            hits.append({"type": name, "n_bodies": len(bodies),
                         "superclasses": superclasses})
        hits.sort(key=lambda h: (-h["n_bodies"], h["type"]))
        n_bodies = sum(h["n_bodies"] for h in hits)
        entry = {
            "rule": "type_re:%s" % rule["type_re"],
            "superclass_filter": sorted(allowed) if allowed else None,
            "note": rule["note"],
            "n_types": len(hits),
            "n_bodies": n_bodies,
            "superclasses": sorted({s for h in hits for s in h["superclasses"]}),
            "types": hits,
        }
        if rule.get("known_narrow"):
            entry["coverage"] = "lower_bound"
        if rule.get("caveat"):
            entry["caveat"] = rule["caveat"]
        anchors[rule["profile"]] = entry
    return anchors


def classify_profiles(profiles: dict, anchors: dict) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {"anchored": [], "identity_not_drosophila": [],
                                "identity_not_resolved_in_malecns": [],
                                "abstract_cognitive_module": []}
    for name, p in sorted(profiles.items()):
        if name in anchors:
            out["anchored"].append(name)
            continue
        if name in UNRESOLVED:
            out["identity_not_resolved_in_malecns"].append(name)
            continue
        ss = " ".join(str(x) for x in (p.get("species_source") or [])).lower()
        if name in MAMMAL_SHAPED:
            out["identity_not_drosophila"].append(name)
            continue
        if any(h in ss for h in FLY_HINTS):
            # Mentions the fly but is a mammalian-shaped class we did not whitelist.
            out["identity_not_drosophila"].append(name)
            continue
        if not ss.strip():
            out["abstract_cognitive_module"].append(name)
        else:
            out["identity_not_drosophila"].append(name)
    return out


def superclass_matrix(ty, sc, anchored_types: set[str]):
    """One pass over the real synapse table -> 27x27 matrices.

    Returns (names, synapses, edges, type_names, type_syn, type_edges, stats).
    `synapses`/`edges` are indexed [pre][post] over superclasses.
    """
    ids = np.fromiter(sorted(sc), dtype=np.int64, count=len(sc))
    sc_names = sorted(set(sc.values()))
    sc_of = np.array([sc_names.index(sc[int(i)]) for i in ids], dtype=np.int32)
    K = len(sc_names)

    tnames = sorted(anchored_types)
    t_index = {n: i for i, n in enumerate(tnames)}
    T = len(tnames)
    # type index per neuron; -1 when the neuron's type is not an anchored one
    ti_of = np.full(len(ids), -1, dtype=np.int32)
    for k, b in enumerate(ids):
        t = ty.get(int(b), "")
        j = t_index.get(t)
        if j is not None:
            ti_of[k] = j

    M = np.zeros(K * K, dtype=np.int64)
    E = np.zeros(K * K, dtype=np.int64)
    TM = np.zeros(max(T * T, 1), dtype=np.int64)
    TE = np.zeros(max(T * T, 1), dtype=np.int64)

    t0 = time.time()
    arrs = {}
    for name in ("pre_s", "post_s", "w_s"):
        arrs[name] = np.load(str(CACHE / (name + ".npy")), mmap_mode="r")
    n = len(arrs["pre_s"])
    for a in range(0, n, CHUNK):
        b = min(a + CHUNK, n)
        pre = np.asarray(arrs["pre_s"][a:b], dtype=np.int64)
        post = np.asarray(arrs["post_s"][a:b], dtype=np.int64)
        w = np.asarray(arrs["w_s"][a:b], dtype=np.int64)
        ip = np.searchsorted(ids, pre)
        np.clip(ip, 0, len(ids) - 1, out=ip)
        iq = np.searchsorted(ids, post)
        np.clip(iq, 0, len(ids) - 1, out=iq)
        keep = (ids[ip] == pre) & (ids[iq] == post)
        if not keep.any():
            continue
        ip = ip[keep]
        iq = iq[keep]
        wk = w[keep]
        key = sc_of[ip].astype(np.int64) * K + sc_of[iq]
        M += np.bincount(key, weights=wk, minlength=K * K).astype(np.int64)
        E += np.bincount(key, minlength=K * K)
        if T:
            tp = ti_of[ip]
            tq = ti_of[iq]
            tk = (tp >= 0) & (tq >= 0)
            if tk.any():
                tkey = tp[tk].astype(np.int64) * T + tq[tk]
                TM += np.bincount(tkey, weights=wk[tk],
                                  minlength=max(T * T, 1)).astype(np.int64)
                TE += np.bincount(tkey, minlength=max(T * T, 1))
        del pre, post, w, ip, iq, wk, key
    elapsed = time.time() - t0

    stats = {"rows_scanned": int(n), "seconds": round(elapsed, 1),
             "measured_synapses_neuron_subgraph": int(M.sum()),
             "measured_edges_neuron_subgraph": int(E.sum())}
    return (sc_names, M.reshape(K, K), E.reshape(K, K),
            tnames, TM.reshape(T, T) if T else TM.reshape(1, 1),
            TE.reshape(T, T) if T else TE.reshape(1, 1), stats)


def type_matrix_sparse(names, M, E) -> dict:
    """One line per row type: `col:synapses:edges,col:synapses:edges,...`.

    The matrix has ~57 k nonzero pairs. Emitting one JSON object per pair costs
    ~350 k pretty-printed lines and makes the artifact unreviewable; a dense array
    is worse still. One compact string per row keeps the FULL matrix (so the gate
    can re-derive the profile matrix from it rather than trusting it) in one line
    per cell type, which is short enough to read in a diff.
    """
    rows = []
    for i in range(M.shape[0]):
        cols = np.nonzero(M[i])[0]
        rows.append(",".join("%d:%d:%d" % (j, M[i][j], E[i][j]) for j in cols))
    return {
        "n_types": len(names),
        "format": "rows[i] = `<col>:<synapses>:<edges>` entries for row type index i, "
                  "columns ascending; empty string = no measured outgoing synapses",
        "rows": rows,
    }


def region_layer() -> dict:
    raw = json.loads(NEUROPIL_STATS.read_text(encoding="utf-8"))
    regions = raw["neuropils"]
    total = sum(v.get("synapses", 0) for v in regions.values())
    out = {}
    for system, codes in SYSTEM_REGIONS.items():
        rows = []
        for c in codes:
            v = regions.get(c)
            if v is None:
                continue
            rows.append({"roi": c, "synapses": v.get("synapses"),
                         "tbar_synapses": v.get("tbar_synapses")})
        out[system] = {"rois": rows,
                       "total_synapses": sum(r["synapses"] or 0 for r in rows)}
    return {"n_roi_categories": raw.get("n_neuropil_categories"),
            "roi_synapse_total": total,
            "source_total_synapse_pairs": raw.get("total_synapse_pairs"),
            "systems": out}


def profile_matrix(anchors: dict, tnames, TM, TE) -> dict:
    """Anchored-profile x anchored-profile measured matrix.

    Superclass resolution is useless here: 11 of the 14 anchored profiles live in
    `cb_intrinsic`, so every declared edge would score the same 34 M synapses and
    the number would be indistinguishable from noise. Aggregating the type-level
    matrix over each profile's real cell-type set gives a number that can actually
    differ between edges -- and therefore can be zero, which is the whole point.
    """
    names = sorted(anchors)
    t_index = {n: i for i, n in enumerate(tnames)}
    K = len(names)
    PM = np.zeros((K, K), dtype=np.int64)
    PE = np.zeros((K, K), dtype=np.int64)
    for i, pi in enumerate(names):
        ti = [t_index[h["type"]] for h in anchors[pi]["types"] if h["type"] in t_index]
        if not ti:
            continue
        for j, pj in enumerate(names):
            tj = [t_index[h["type"]] for h in anchors[pj]["types"] if h["type"] in t_index]
            if not tj:
                continue
            PM[i, j] = int(TM[np.ix_(ti, tj)].sum())
            PE[i, j] = int(TE[np.ix_(ti, tj)].sum())
    return {"index": {n: i for i, n in enumerate(names)}, "names": names,
            "n_types_per_profile": {n: anchors[n]["n_types"] for n in names},
            "synapses": PM.tolist(), "edges": PE.tolist()}


def build() -> dict:
    profiles = _load_module(PKG / "synthetic_bio_topology.py", "_sbt").MODULE_PROFILES
    ty, sc = load_neurons()
    if len(sc) != EXPECTED_NEURONS:
        raise SystemExit("REFUSING TO BUILD: %d annotated neurons, expected %d"
                         % (len(sc), EXPECTED_NEURONS))

    anchors = build_profile_anchors(ty, sc)
    empty = sorted(k for k, a in anchors.items() if a["n_types"] == 0)
    if empty:
        raise SystemExit(
            "REFUSING TO BUILD: rule(s) matched zero real cells: %s\n"
            "A rule that anchors nothing is a broken rule -- fix the regex or the "
            "superclass filter rather than shipping an empty anchor." % ", ".join(empty))
    classification = classify_profiles(profiles, anchors)
    anchored_types = {h["type"] for a in anchors.values() for h in a["types"]}
    (sc_names, M, E, tnames, TM, TE, stats) = superclass_matrix(ty, sc, anchored_types)

    if stats["measured_synapses_neuron_subgraph"] != EXPECTED_SYNAPSES or \
       stats["measured_edges_neuron_subgraph"] != EXPECTED_EDGES:
        raise SystemExit(
            "REFUSING TO BUILD: recomputed neuron subgraph = %s synapses / %s edges, "
            "expected %s / %s -- the cache and connectivity_stats.json disagree"
            % (stats["measured_synapses_neuron_subgraph"],
               stats["measured_edges_neuron_subgraph"],
               EXPECTED_SYNAPSES, EXPECTED_EDGES))

    doc = {
        "schema_version": ANCHOR_SCHEMA,
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "purpose": "Map library neuron populations onto real MaleCNS v1.0 cells and "
                   "measure the real superclass connectivity backbone, so a declared "
                   "pathway can be falsified. Presence and non-contradiction only; the "
                   "declared microcircuit and connection FORM remain literature-derived.",
        "source": {
            "annotations": {"file": ANN_FEATHER.name,
                            "sha256": sha256_file(ANN_FEATHER),
                            "rows": None, "unique_neurons": len(sc),
                            "type_column": "type"},
            "synapse_cache": {"dir": "male_cns/connectome_cache",
                              "arrays": ["pre_s.npy", "post_s.npy", "w_s.npy"]},
            "connectivity_stats": CONN_STATS.name,
            "neuropil_stats": NEUROPIL_STATS.name,
        },
        "validation": {
            "expected_synapses": EXPECTED_SYNAPSES,
            "expected_edges": EXPECTED_EDGES,
            "measured_synapses_neuron_subgraph": stats["measured_synapses_neuron_subgraph"],
            "measured_edges_neuron_subgraph": stats["measured_edges_neuron_subgraph"],
            "matches_connectivity_stats": True,
            "rows_scanned": stats["rows_scanned"],
            "seconds": stats["seconds"],
        },
        "superclasses": sc_names,
        "superclass_matrix": {
            "index": {n: i for i, n in enumerate(sc_names)},
            "synapses": M.tolist(),
            "edges": E.tolist(),
        },
        "anchored_type_matrix": type_matrix_sparse(tnames, TM, TE),
        "profile_matrix": profile_matrix(anchors, tnames, TM, TE),
        "profile_anchors": anchors,
        "profile_classification": classification,
        "regions": region_layer(),
        "summary": {
            "anchored_profiles": len(anchors),
            "anchored_real_cells": sum(a["n_bodies"] for a in anchors.values()),
            "anchored_types": len(anchored_types),
            "lower_bound_profiles": sorted(k for k, a in anchors.items()
                                           if a.get("coverage") == "lower_bound"),
            "profiles_total": len(profiles),
            "unanchored_profiles": len(profiles) - len(anchors),
        },
    }
    return doc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="recompute and compare against the committed artifact")
    args = ap.parse_args()

    doc = build()
    if args.check:
        if not OUT.exists():
            print("MISSING artifact %s" % OUT)
            return 1
        old = json.loads(OUT.read_text(encoding="utf-8"))
        same = (old["superclass_matrix"] == doc["superclass_matrix"]
                and old["anchored_type_matrix"] == doc["anchored_type_matrix"]
                and old["profile_matrix"] == doc["profile_matrix"]
                and old["profile_anchors"] == doc["profile_anchors"]
                and old["profile_classification"] == doc["profile_classification"]
                and old["regions"] == doc["regions"])
        print("anchors match artifact: %s" % same)
        return 0 if same else 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n",
                   encoding="utf-8")

    a = doc["profile_anchors"]
    print("wrote %s (%.1f KB)" % (OUT.name, OUT.stat().st_size / 1024))
    print("  neurons           %d" % doc["source"]["annotations"]["unique_neurons"])
    print("  synapses/edges    %d / %d  (matches connectivity_stats: %s)"
          % (doc["validation"]["measured_synapses_neuron_subgraph"],
             doc["validation"]["measured_edges_neuron_subgraph"],
             doc["validation"]["matches_connectivity_stats"]))
    print("  anchored profiles %d" % len(a))
    for k in sorted(a, key=lambda x: -a[x]["n_bodies"]):
        print("    %-26s %5d cells / %4d types  %s"
              % (k, a[k]["n_bodies"], a[k]["n_types"], ",".join(a[k]["superclasses"])))
    print("  anchored types    %d" % doc["anchored_type_matrix"]["n_types"])
    cls = doc["profile_classification"]
    for k, v in cls.items():
        print("  %-32s %d" % (k, len(v)))
    print("  ROI regions       %s systems, %d roi categories"
          % (len(doc["regions"]["systems"]), doc["regions"]["n_roi_categories"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
