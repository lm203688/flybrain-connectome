"""H01 human cortex (1 mm^3) connectome adapter (Google Cloud, public, CC-BY).

This is a REAL adapter with a real parse path, but the dataset is ~8 GB and is
NOT bundled.  Offline it reports ``available() == False`` and
``build_profiles()`` returns a structured ``unavailable`` envelope.  Point
``H01_DATA_DIR`` at a local sample (e.g. a downloaded neuron/edge CSV from the
public bucket) and it parses it into ``h01_profiles.json``.

Source: "A petascale connectomic portrait of the human cerebral cortex"
        (Shapson-Coe et al., 2025), MICrONS / AI2 public release, CC-BY.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from .base import ConnectomeSource, SourceMeta, build_unavailable, data_dir

ROOT = Path(__file__).resolve().parents[2]


class H01Source(ConnectomeSource):
    meta = SourceMeta(
        id="h01",
        species="human",
        license="CC-BY",
        modality="EM connectivity (1 mm^3 human cortex)",
        data_dir_env="H01_DATA_DIR",
        default_data_dir="",
    )

    def available(self) -> bool:
        d = data_dir(self.meta)
        if d is None:
            return False
        # A sample directory should contain neuron and/or edge tables.
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
                "H01 sample not present locally (set H01_DATA_DIR to a "
                "downloaded sample from the public bucket)")
        raw = self.load()
        profiles = {}
        for nid, row in raw.get("neurons", {}).items():
            profiles[nid] = {
                "brain_region": "human_cortex",
                "species_source": "h01_human_2025",
                "neurotransmitter": row.get("neurotransmitter", ""),
                "neurotype": row.get("neurotype", "unknown"),
                "has_inhibition": str(row.get("neurotype", "")).lower() == "inhibitory",
                "in_degree": int(row.get("in_degree", 0) or 0),
                "out_degree": int(row.get("out_degree", 0) or 0),
                "recurrent_pct": None,
                "reservoir_density": None,
                "capability": ["traced_connectome"],
                "lead_task_hint": "human cortex connectivity (H01)",
                "task_hint_pool": ["connectivity", "cross_species_consistency"],
                "biological_reference": "Shapson-Coe et al. 2025, H01 human cortex",
                "provenance": {
                    "source_connectome": "h01_human_2025",
                    "source_license": "CC-BY",
                    "modality": "EM connectivity",
                },
            }
        doc = {
            "source": "Shapson-Coe et al. 2025 (H01, 1 mm^3 human cortex)",
            "note": "Human evidence line. CC-BY: may be mixed with the MIT anchor.",
            "license": "CC-BY",
            "units": len(profiles),
            "neuron_profiles": profiles,
        }
        out = Path(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
        return doc


if __name__ == "__main__":
    print(json.dumps(H01Source().status(), indent=2))
