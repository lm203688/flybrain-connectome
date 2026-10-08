"""MICrONS mouse visual-cortex adapter (EM + functional, CAVE, CC-BY).

Same contract as H01: real adapter, multi-GB data not bundled, offline-safe.
Point ``MICRONS_DATA_DIR`` at a local sample (CAVE-exported neuron/edge tables
that also carry functional responses) and it parses it.  MICrONS is the only
source that adds a *functional* axis (responses to visual stimuli) on top of
structure -- the roadmap's "structure -> function" gap.

Source: "Functional connectomics spans precision and generality" (MICrONS,
Benson et al., 2025), public CAVE release, CC-BY.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from .base import ConnectomeSource, SourceMeta, build_unavailable, data_dir

ROOT = Path(__file__).resolve().parents[2]


class MicronsSource(ConnectomeSource):
    meta = SourceMeta(
        id="microns",
        species="mouse",
        license="CC-BY",
        modality="EM connectivity + functional responses",
        data_dir_env="MICRONS_DATA_DIR",
        default_data_dir="",
    )

    def available(self) -> bool:
        d = data_dir(self.meta)
        if d is None:
            return False
        return any(d.glob("*.csv")) or any(d.glob("*.json"))

    def load(self) -> dict:
        d = data_dir(self.meta)
        if d is None:
            return {}
        neurons, edges = {}, []
        for f in d.glob("*.csv"):
            with f.open(encoding="utf-8", errors="replace") as fh:
                rdr = csv.DictReader(fh)
                for row in rdr:
                    if "neuron" in f.name or "cell" in f.name:
                        neurons[row.get("id") or row.get("neuron_id")] = row
                    else:
                        edges.append(row)
        return {"neurons": neurons, "edges": edges}

    def build_profiles(self, out: Path) -> dict:
        d = data_dir(self.meta)
        if d is None or not self.available():
            return build_unavailable(
                self.meta,
                "MICrONS sample not present locally (set MICRONS_DATA_DIR to a "
                "CAVE-exported sample with functional responses)")
        raw = self.load()
        profiles = {}
        for nid, row in raw.get("neurons", {}).items():
            profiles[nid] = {
                "brain_region": "mouse_visual_cortex",
                "species_source": "microns_mouse_2025",
                # MICrONS adds the functional axis the others lack:
                "functional_response": row.get("functional_response", ""),
                "neurotransmitter": row.get("neurotransmitter", ""),
                "neurotype": row.get("neurotype", "unknown"),
                "has_inhibition": str(row.get("neurotype", "")).lower() == "inhibitory",
                "in_degree": int(row.get("in_degree", 0) or 0),
                "out_degree": int(row.get("out_degree", 0) or 0),
                "recurrent_pct": None,
                "reservoir_density": None,
                "capability": ["traced_connectome", "functional_response"],
                "lead_task_hint": "mouse V1 connectivity + visual responses (MICrONS)",
                "task_hint_pool": ["connectivity", "structure_to_function"],
                "biological_reference": "Benson et al. 2025, MICrONS mouse V1",
                "provenance": {
                    "source_connectome": "microns_mouse_2025",
                    "source_license": "CC-BY",
                    "modality": "EM connectivity + function",
                },
            }
        doc = {
            "source": "Benson et al. 2025 (MICrONS, mouse visual cortex, EM+function)",
            "note": "Adds the structure->function axis. CC-BY: mixable with the MIT anchor.",
            "license": "CC-BY",
            "units": len(profiles),
            "neuron_profiles": profiles,
        }
        out = Path(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
        return doc


if __name__ == "__main__":
    print(json.dumps(MicronsSource().status(), indent=2))
