"""Zebrafish larva connectome adapter (Petkova 2025, TEN + HMI, CAVE).

This is the one source we actually bundle data for, so its adapter produces a
real ``zebrafish_profiles.json`` aligned with ``larva_profiles.json`` /
``cel_profiles.json``:

  * TEN_analysis/*.csv  -> per-neuron in/out synapse degree (connectivity)
  * HMI_analysis/*.xlsx -> cell class, neurotransmitter (E/I), network level

License is CC-BY-NC (non-commercial) per the foundation roadmap; that is stamped
into every profile's provenance so it is never silently mixed with the MIT /
CC-BY anchors.
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from .base import ConnectomeSource, SourceMeta, data_dir

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "zebrafish_data" / "paper_data"
TEN = DATA / "TEN_analysis"
HMI = DATA / "HMI_analysis"

_ID_RE = re.compile(r"\d+")


class ZebrafishSource(ConnectomeSource):
    meta = SourceMeta(
        id="zebrafish",
        species="zebrafish_larva",
        license="CC-BY-NC",
        modality="EM (CAVE) connectivity",
        data_dir_env="",
        default_data_dir=str(DATA),
    )

    def available(self) -> bool:
        return TEN.exists() and HMI.exists()

    # -- parsing helpers ----------------------------------------------------
    @staticmethod
    def _syn_ids(cell: str) -> list[str]:
        """The synapse id column is a numpy-array-style string '[a b c]'."""
        if not cell:
            return []
        return _ID_RE.findall(cell)

    def _ten_degrees(self) -> tuple[dict[str, int], dict[str, int], int]:
        indeg: dict[str, int] = {}
        outdeg: dict[str, int] = {}
        total = 0
        inc = TEN / "incoming_synapses.csv"
        out = TEN / "outgoing_synapses.csv"
        if inc.exists():
            with inc.open(encoding="utf-8", errors="replace") as fh:
                for row in csv.DictReader(fh):
                    nid = (row.get("query_neuron") or "").strip()
                    ids = self._syn_ids(row.get("incoming_synapses", ""))
                    indeg[nid] = len(ids)
                    total += len(ids)
        if out.exists():
            with out.open(encoding="utf-8", errors="replace") as fh:
                for row in csv.DictReader(fh):
                    nid = (row.get("query_neuron") or "").strip()
                    outdeg[nid] = len(self._syn_ids(row.get("outgoing_synapses", "")))
        return indeg, outdeg, total

    def _hmi_cells(self) -> dict[str, dict]:
        """Cell class + neurotransmitter (E/I) + network level from the xlsx.

        openpyxl is imported lazily so the package still imports without it.
        """
        cells: dict[str, dict] = {}
        xlsx = HMI / "data" / "em_zfish1_dataframe.xlsx"
        if not xlsx.exists():
            return cells
        try:
            import openpyxl  # lazy
        except Exception:
            return cells
        wb = openpyxl.load_workbook(str(xlsx), read_only=True)
        ws = wb.active
        rows = ws.iter_rows(values_only=True)
        header = [str(h).strip() if h is not None else "" for h in next(rows)]
        idx = {h: i for i, h in enumerate(header)}
        for r in rows:
            name = r[idx.get("name", 0)] if idx.get("name") is not None else None
            if not name:
                continue
            nt = str(r[idx.get("final_neurotransmitter_ID", 0)] or "")
            cls = str(r[idx.get("classifier", 0)] or "")
            net = str(r[idx.get("network_level", 0)] or "")
            inh = "Gad" in nt or "VGAT" in nt or "GlyT" in nt
            exc = "VGluT" in nt or "vGluT" in nt
            cells[str(name)] = {
                "cell_class": cls,
                "neurotransmitter": nt,
                "has_inhibition": bool(inh),
                "neurotype": "inhibitory" if inh else ("excitatory" if exc else "unknown"),
                "network_level": net,
            }
        return cells

    # -- public API ---------------------------------------------------------
    def load(self) -> dict:
        indeg, outdeg, total = self._ten_degrees()
        cells = self._hmi_cells()
        return {"indeg": indeg, "outdeg": outdeg,
                "total_synapses": total, "cells": cells}

    def build_profiles(self, out: Path) -> dict:
        raw = self.load()
        indeg, outdeg, total = raw["indeg"], raw["outdeg"], raw["total_synapses"]
        cells = raw["cells"]
        neurons = sorted(set(indeg) | set(outdeg) | set(cells))
        profiles: dict[str, dict] = {}
        for nid in neurons:
            c = cells.get(nid, {})
            ind = indeg.get(nid, 0)
            oud = outdeg.get(nid, 0)
            rec = 0.0
            if (ind + oud) > 0:
                rec = round(min(ind, oud) / (ind + oud), 3)
            profiles[nid] = {
                "brain_region": "zebrafish_larva",
                "species_source": "petkova_2025_zebrafish",
                "neurotransmitter": c.get("neurotransmitter", ""),
                "neurotype": c.get("neurotype", "unknown"),
                "has_inhibition": c.get("has_inhibition", False),
                "cell_class": c.get("cell_class", ""),
                "network_level": c.get("network_level", ""),
                "in_degree": ind,
                "out_degree": oud,
                "recurrent_pct": rec,
                "reservoir_density": None,
                "capability": ["traced_connectome"],
                "lead_task_hint": "zebrafish larva connectivity (TEN+HMI)",
                "task_hint_pool": ["connectivity", "cross_species_consistency"],
                "biological_reference": "Petkova et al. 2025, zebrafish larva (TEN+HMI, CAVE)",
                "provenance": {
                    "source_connectome": "petkova_2025_zebrafish",
                    "source_license": "CC-BY-NC",
                    "modality": "EM connectivity",
                },
            }
        doc = {
            "source": "Petkova et al. 2025 (zebrafish larva, TEN + HMI, CAVE)",
            "note": (
                "Independent cross-species evidence line. License CC-BY-NC: "
                "do NOT mix with MIT/CC-BY anchors in commercial contexts.\n"
                "MODALITY COVERAGE (what the bundled TEN+HMI subset actually "
                "carries): E/I molecular polarity is resolved per neuron from the "
                "HMI neurotransmitter column (Gad1B -> inhibitory, VGluT2 -> "
                "excitatory; 668/999 cells unresolved -> 'unknown'); network "
                "hierarchy is carried in 'network_level' (output_one / output_two "
                "/ input_one / seed / dt_* ...); a spinal-locomotor subpopulation "
                "is recoverable from the 'spn_*' classifier values.\n"
                "MODALITY GAPS (NOT in the bundled TEN+HMI subset -> "
                "data-acquisition pending, same blocker class as H01/MICrONS): "
                "the lateral-line (mechanosensory) system and the named "
                "neuromodulatory modulators (dopamine / serotonin / "
                "acetylcholine / noradrenaline / histamine) are absent from this "
                "derived extract. Do not fabricate them; they require the full "
                "Petkova 2025 release, not the connectivity-only TEN+HMI slice."),
            "license": "CC-BY-NC",
            "units": len(profiles),
            "total_synapses": total,
            "neuron_profiles": profiles,
        }
        out = Path(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
        return doc


if __name__ == "__main__":
    z = ZebrafishSource()
    import sys
    sys.path.insert(0, str(ROOT))
    p = z.build_profiles(ROOT / "flybrain-connectome-mcp" / "functional_units" / "zebrafish_profiles.json")
    print("zebrafish profiles: %d neurons, %d synapses" % (p["units"], p["total_synapses"]))
