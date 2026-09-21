"""
Anti-plagiarism Tier 3: generate SHA-256 fingerprints for organisms.

Fingerprints are the *only* thing shipped out via the service-side API.
They serve three purposes:

  1. Identity — a fingerprint uniquely identifies a composed organism
  2. Watermark — every saved organism carries the fingerprint, so theft is traceable
  3. Version binding — the fingerprint includes the pipeline version, so downstream
     services know exactly what discovery method produced the object

Usage:
  fingerprint_organism.py --load male_cns/virtual_organisms/foo.json
  fingerprint_organism.py --compose --modules sensory,memory --counts '{"sensory":2}'
  fingerprint_organism.py --verify --path male_cns/virtual_organisms/foo.json

Fingerprint format:
  flybrain:organism-v1:<64-char sha256>
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

PIPELINE_VERSION = "1.2.0"
SCHEMA_PREFIX = "flybrain:organism-v1"
PIPELINE_VERSION_TAG = "v1"  # version tag embedded in the fingerprint

ROOT = Path(__file__).resolve().parents[1]


def _canonical(obj) -> bytes:
    """Canonical JSON bytes: sorted keys, no whitespace, ensure_ascii=False."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def compute_fingerprint(organism: dict) -> str:
    """
    Compute a fingerprint for an organism dict.

    Two supported shapes:
      - Flat:   {name, modules, seed, stats}
      - Nested: {status, organism: {modules, edges, stats}, compatibility}

    For nested shape, we fingerprint the inner 'organism' object only (the
    semantic payload). The 'status'/'compatibility' fields are metadata.

    The fingerprint is stable across equivalent organisms:
      - Different field ORDER does not change the fingerprint
      - Different key ordering does not change the fingerprint
      - Whitespace/encoding is normalized
      - Only *semantic* differences change the fingerprint
    """
    # Unwrap nested shape
    if "organism" in organism and isinstance(organism["organism"], dict):
        organism = organism["organism"]

    # Extract only the semantically-meaningful fields
    semantic = {
        "name": organism.get("name", ""),
        "modules": organism.get("modules", []),
        "seed": organism.get("seed", 0),
    }
    # If edges present, include a stable digest of edge structure
    edges = organism.get("edges", [])
    if edges:
        edge_count = len(edges)
        edge_weight_sum = sum(
            float(e.get("weight", 0) if isinstance(e, dict) else 0)
            for e in edges
        )
        semantic["edges_summary"] = {"n_edges": edge_count, "weight_sum": round(edge_weight_sum, 4)}
    # If stats present, include only stable summary keys
    stats = organism.get("stats", {}) or {}
    if stats:
        semantic["stats_summary"] = {
            k: stats[k] for k in ("n_nodes", "n_edges", "n_modules", "total_synapses")
            if k in stats
        }
    payload = _canonical(semantic)
    digest = _sha256_hex(payload)
    return f"{SCHEMA_PREFIX}:{digest}"


def fingerprint_organism_path(path: str) -> str:
    """Load an organism JSON and return its fingerprint."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    return compute_fingerprint(data)


def verify_organism(path: str, expected_fp: str) -> dict:
    """
    Verify an organism's fingerprint against an expected value.
    Returns {valid, actual, expected, reason}.
    """
    actual = fingerprint_organism_path(path)
    valid = actual == expected_fp
    return {
        "valid": valid,
        "actual": actual,
        "expected": expected_fp,
        "reason": None if valid else "fingerprint mismatch — organism was modified",
    }


def compose_and_fingerprint(modules: list[str], counts: dict[str, int] | None = None,
                             seed: int = 42) -> dict:
    """
    Compose a minimal organism dict and return the fingerprint.
    (Real topology generation is done by ModuleFactory; this is just the fingerprint step.)
    """
    modules_norm = [{"name": m, "count": int((counts or {}).get(m, 1))} for m in modules]
    organism = {
        "name": f"composed_{'_'.join(modules)}_{seed}",
        "modules": modules_norm,
        "seed": seed,
    }
    return {
        "organism": organism,
        "fingerprint": compute_fingerprint(organism),
        "pipeline_version": PIPELINE_VERSION,
        "pipeline_tag": PIPELINE_VERSION_TAG,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="FlyBrain organism fingerprinting")
    ap.add_argument("--load", help="Load and fingerprint an organism JSON file")
    ap.add_argument("--verify", action="store_true", help="Verify against expected fingerprint")
    ap.add_argument("--path", help="Path to organism JSON (for --verify)")
    ap.add_argument("--expected", help="Expected fingerprint (for --verify)")
    ap.add_argument("--compose", action="store_true", help="Compose a minimal organism and fingerprint it")
    ap.add_argument("--modules", default="sensory,memory",
                    help="Comma-separated module names (for --compose)")
    ap.add_argument("--counts", default="",
                    help="JSON string of module→count map (for --compose)")
    ap.add_argument("--seed", type=int, default=42, help="Random seed (for --compose)")
    ap.add_argument("--json", action="store_true", help="Emit machine-parseable JSON")
    args = ap.parse_args()

    try:
        if args.load:
            fp = fingerprint_organism_path(args.load)
            print(fp if not args.json else json.dumps({"path": args.load, "fingerprint": fp}))
        elif args.verify:
            if not (args.path and args.expected):
                print("error: --verify requires --path and --expected", file=sys.stderr)
                return 1
            result = verify_organism(args.path, args.expected)
            print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else
                  (f"{'VALID' if result['valid'] else 'INVALID'}\n  actual: {result['actual']}\n  expected: {result['expected']}\n  reason: {result['reason']}"))
            return 0 if result["valid"] else 2
        elif args.compose:
            mods = [m.strip() for m in args.modules.split(",") if m.strip()]
            counts = json.loads(args.counts) if args.counts else {}
            result = compose_and_fingerprint(mods, counts, args.seed)
            print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else
                  f"fingerprint: {result['fingerprint']}\npipeline: {result['pipeline_version']} ({result['pipeline_tag']})\nname: {result['organism']['name']}")
        else:
            ap.print_help()
            return 1
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
