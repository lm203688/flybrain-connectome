"""Annotate worm modules with neurotransmitter profiles.

Cross-references worm_modules.json (Cook 2019) with the WormAtlas
neurotransmitter mapping (Loer & Rand 2022) to add NT profiles to each module.

Input:
  - data/worm/worm_modules.json (from Tier-2 backup)
  - data/worm/neuron_nt_mapping.json (from parse_worm_nt.py)

Output:
  - data/worm/worm_modules_nt_annotated.json

Each module gets a 'neurotransmitter_profile' field with:
  - distribution: {NT: count, ...}
  - dominant_nt: most common NT in the module
  - n_annotated: number of neurons with NT data
  - n_unknown: number of neurons without NT data
"""
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

# Paths
MODULES_PATHS = [
    ROOT / "data" / "worm" / "worm_modules.json",
    Path("C:/Users/xing/Desktop/flybrain-tier2-backup-2026-09-22/data/worm/worm_modules.json"),
]
NT_PATH = ROOT / "data" / "worm" / "neuron_nt_mapping.json"
OUT_PATH = ROOT / "data" / "worm" / "worm_modules_nt_annotated.json"


def load_json(paths):
    """Load JSON from first existing path."""
    for p in paths:
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8")), p
    return None, None


def annotate_module(module, nt_mapping):
    """Add neurotransmitter profile to a module."""
    neurons = module.get("neurons", [])
    if not neurons:
        module["neurotransmitter_profile"] = {
            "distribution": {},
            "dominant_nt": None,
            "n_annotated": 0,
            "n_unknown": 0,
            "n_total": 0,
        }
        return module

    nt_counter = Counter()
    n_annotated = 0
    n_unknown = 0

    for n in neurons:
        data = nt_mapping.get(n)
        if data and data.get("neurotransmitters"):
            for nt in data["neurotransmitters"]:
                nt_counter[nt] += 1
            n_annotated += 1
        else:
            n_unknown += 1

    # Determine dominant NT
    dominant_nt = nt_counter.most_common(1)[0][0] if nt_counter else None

    module["neurotransmitter_profile"] = {
        "distribution": dict(nt_counter.most_common()),
        "dominant_nt": dominant_nt,
        "n_annotated": n_annotated,
        "n_unknown": n_unknown,
        "n_total": len(neurons),
    }
    return module


def main():
    print("Loading worm modules...")
    modules_data, modules_path = load_json(MODULES_PATHS)
    if not modules_data:
        print("ERROR: worm_modules.json not found", file=sys.stderr)
        sys.exit(1)
    print(f"  Loaded from {modules_path}")
    print(f"  {modules_data.get('n_units', 0)} modules")

    print("Loading neurotransmitter mapping...")
    nt_data = json.loads(NT_PATH.read_text(encoding="utf-8"))
    nt_mapping = nt_data["neurons"]
    print(f"  {len(nt_mapping)} neurons mapped")

    print("Annotating modules...")
    annotated_units = []
    for unit in modules_data["units"]:
        annotated = annotate_module(unit, nt_mapping)
        annotated_units.append(annotated)
        profile = annotated["neurotransmitter_profile"]
        print(f"  {unit['unit_id']}: dominant={profile['dominant_nt']}, "
              f"annotated={profile['n_annotated']}/{profile['n_total']}")

    # Save
    output = dict(modules_data)
    output["units"] = annotated_units
    output["nt_annotation_source"] = "WormAtlas Loer & Rand 2022"
    output["nt_annotation_date"] = "2026-09-22"
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"\nSaved annotated modules to {OUT_PATH}")


if __name__ == "__main__":
    import sys
    main()
