#!/usr/bin/env python3
"""Build zebrafish_profiles.json from the bundled Petkova-2025 data.

Thin reproducibility wrapper around connectome_sources.zebrafish. Run by
GATE 20's prerequisite step (and in CI before the gate).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MCP = ROOT / "flybrain-connectome-mcp"
OUT = MCP / "functional_units" / "zebrafish_profiles.json"

sys.path.insert(0, str(MCP))


def main() -> int:
    from connectome_sources.zebrafish import ZebrafishSource
    z = ZebrafishSource()
    if not z.available():
        print("zebrafish data not found under zebrafish_data/paper_data/")
        return 1
    doc = z.build_profiles(OUT)
    print("wrote %s: %d neurons, %d synapses"
          % (OUT, doc["units"], doc["total_synapses"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
