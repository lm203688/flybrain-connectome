#!/usr/bin/env python3
"""export_boundary_atlas.py — E4 边界图册产品化（durable negative knowledge）.

Why this exists
---------------
`compute_epistemic_progress.py` exports `boundary_atlas.json` — a list of every
documented non-confirmation (FAIL / WEAK / ACCEPT / BOUNDARY).  But a bare JSON
list is not *citable knowledge*: it has no checksums, no reproduction command,
and no record of which paths were *not* taken.

E4 upgrades the atlas into a **durable, machine-readable negative-knowledge
asset** — the "Negative Knowledge" frontier: a failure should become a
persistent, shareable knowledge object, not a log line.

Each atlas entry gains:
  - `evidence_file` + `evidence_sha256`   — the artifact that produced the verdict
  - `recompute_command`                   — how to reproduce it
  - `unexplored_alternatives`             — which paths were NOT taken
  - `citation_doi` / `@id`                — a stable identifier for citing

Outputs
-------
  boundary_atlas_products.json   enhanced, citable boundary knowledge
  boundary_crate.json            RO-Crate 1.1 package (JSON-LD, machine-readable)
  boundary_nanopub.json          nanopublication (assertion + provenance + pubinfo)

Usage
-----
  python scripts/export_boundary_atlas.py
  python scripts/export_boundary_atlas.py --atlas boundary_atlas.json \\
      --out boundary_atlas_products.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Per-boundary enrichment table.
# Each entry maps a boundary (protocol or claim) to:
#   evidence_file    — the artifact that produced the verdict
#   recompute        — reproduction command (script name, run from repo root)
#   unexplored       — paths that were NOT taken (the negative knowledge itself)
# ---------------------------------------------------------------------------
ENRICH = {
    "PR1": {
        "evidence_file": "_r1_mechanism_prereg/f1_preregistered.json",
        "recompute": "python scripts/f1_mechanism_preregistered.py",
        "unexplored": [
            "前瞻性 z 阈值重估（更大样本量）",
            "独立外部数据集前瞻复验",
        ],
    },
    "PR2": {
        "evidence_file": "_f4_intervention/f4_intervention.json",
        "recompute": "python scripts/f4_intervention_test.py",
        "unexplored": [
            "因果级 L4 基底上限——当前数据不可达（非样本量不足）",
            "跨物种干预实验",
        ],
    },
    "PR3": {
        "evidence_file": "_f3_generalization/f3_generalization.json",
        "recompute": "python scripts/f3_generalization_matrix.py",
        "unexplored": [
            "跨族绝对阈值重标定（N8 E2 的 top 推荐）",
            "更大节点规模跨族验证",
        ],
    },
    "PR2b": {
        "evidence_file": "_f4b_metric_substitution/f4b_metric_substitution.json",
        "recompute": "python scripts/f4b_metric_substitution_check.py",
        "unexplored": [
            "解析解耦替代度量（重新设计 outcome 变量）",
        ],
    },
    "PR5": {
        "evidence_file": "_c1_cell_densification/c1_results.json",
        "recompute": "python scripts/c1_cell_densification.py",
        "unexplored": [
            "恢复动力学跨 n 阈值重标定（N8 推荐）",
            "非度量依赖的恢复信号",
        ],
    },
    # claim-level boundaries (no preregistered protocol)
    "R3": {
        "evidence_file": "_s1_external_validation/results.json",
        "recompute": "python scripts/s1_external_validation.py",
        "unexplored": [
            "外部数据集扩展（跨物种 PARTIAL 边界细化）",
        ],
    },
    "R6": {
        "evidence_file": "research_claims.json",
        "recompute": "python scripts/compute_epistemic_progress.py",
        "unexplored": [
            "跨物种 role 绑定扩展（T5#4 已 141 组，余下族未覆盖）",
        ],
    },
}


def _sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _load(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _enrich(entry: dict, root: Path) -> dict:
    """Add evidence checksum, recompute command, and unexplored alternatives."""
    key = entry.get("protocol") or entry.get("claim")
    meta = ENRICH.get(str(key), {})
    evidence = meta.get("evidence_file")
    e_path = root / evidence if evidence else None
    enriched = dict(entry)
    enriched["evidence_file"] = evidence
    enriched["evidence_sha256"] = _sha256_file(e_path) if e_path else None
    enriched["recompute_command"] = meta.get("recompute")
    enriched["unexplored_alternatives"] = meta.get("unexplored", [])
    enriched["@id"] = f"boundary:{key}"
    return enriched


def _build_crate(products: list[dict], root: Path) -> dict:
    """RO-Crate 1.1 package: boundary atlas as a citable negative-knowledge set."""
    entries = [{
        "@context": {
            "@vocab": "https://schema.org/",
            "ro": "https://w3id.org/ro/",
            "prov": "http://www.w3.org/ns/prov#",
            "sha256": "https://w3id.org/ro/crate-1.1#sha256",
        }
    }]
    entries.append({
        "@id": "boundary_atlas.json",
        "@type": "Dataset",
        "name": "Flybrain boundary atlas — durable negative knowledge",
        "description": (
            "Every documented non-confirmation (FAIL/WEAK/ACCEPT/BOUNDARY) as a "
            "citable, machine-readable negative-knowledge record with evidence "
            "checksum and reproduction command."
        ),
        "dateModified": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "hasPart": [f"boundary:{p['@id'].split(':')[1]}" for p in products],
    })
    for p in products:
        entries.append({
            "@id": p["@id"],
            "@type": "CreativeWork",
            "name": f"Boundary {p['@id'].split(':')[1]} — {p.get('verdict')}",
            "about": p.get("claim"),
            "identifier": p.get("protocol"),
            "description": (
                f"verdict={p.get('verdict')} category={p.get('category')} "
                f"tier={p.get('tier')}"
            ),
            "sha256": p.get("evidence_sha256"),
            "url": f"https://github.com/lm203688/flybrain-connectome/blob/main/{p.get('evidence_file')}",
            "unexploredAlternatives": p.get("unexplored_alternatives", []),
            "recomputeCommand": p.get("recompute_command"),
        })
    return {"@context": entries[0]["@context"], "@graph": entries[1:]}


def _build_nanopub(products: list[dict]) -> dict:
    """Nanopublication: assertion + provenance + publication info."""
    assertions = [{
        "@id": f"boundary:{p['@id'].split(':')[1]}",
        "verdict": p.get("verdict"),
        "category": p.get("category"),
        "claim": p.get("claim"),
        "protocol": p.get("protocol"),
        "tier": p.get("tier"),
    } for p in products]
    return {
        "@context": {"@vocab": "https://schema.org/"},
        "@id": "boundary_atlas_nanopub",
        "@type": "Nanopublication",
        "assertion": {
            "@id": "boundary_atlas_assertion",
            "@type": "Assertion",
            "hasSubject": assertions,
        },
        "provenance": {
            "@id": "boundary_atlas_provenance",
            "wasGeneratedBy": {
                "@type": "CreateAction",
                "agent": "flybrain-connectome E4 exporter",
                "startTime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        },
        "publicationInfo": {
            "@id": "boundary_atlas_pubinfo",
            "type": "NegativeKnowledge",
            "source": "https://github.com/lm203688/flybrain-connectome",
        },
    }


def _validate(products: list[dict], crate: dict) -> list[str]:
    """E4 acceptance: each entry reproducible + crate passes RO-Crate shape check."""
    issues: list[str] = []
    for p in products:
        if p.get("evidence_sha256") is None:
            issues.append(f"{p['@id']}: evidence file missing sha256")
        if not p.get("recompute_command"):
            issues.append(f"{p['@id']}: no recompute command")
    if "@graph" not in crate:
        issues.append("crate: missing @graph")
    if not crate.get("@graph"):
        issues.append("crate: empty @graph")
    return issues


def main() -> int:
    ap = argparse.ArgumentParser(description="E4 boundary atlas productization")
    ap.add_argument("--atlas", default=str(ROOT / "boundary_atlas.json"))
    ap.add_argument("--out", default=str(ROOT / "boundary_atlas_products.json"))
    args = ap.parse_args()

    atlas_path = Path(args.atlas)
    out_path = Path(args.out)
    if not atlas_path.exists():
        print(f"[FAIL] boundary_atlas.json not found: {atlas_path}", file=sys.stderr)
        return 1

    atlas = _load(atlas_path)
    entries = atlas.get("entries", [])
    if not entries:
        print("[FAIL] atlas has no entries", file=sys.stderr)
        return 1

    products = [_enrich(e, ROOT) for e in entries]
    crate = _build_crate(products, ROOT)
    nanopub = _build_nanopub(products)

    issues = _validate(products, crate)
    if issues:
        for i in issues:
            print(f"[WARN] {i}", file=sys.stderr)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "schema": "boundary_atlas_products_v1",
            "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "n_entries": len(products),
            "validation_issues": issues,
            "entries": products,
        }, f, ensure_ascii=False, indent=2)

    with open(ROOT / "boundary_crate.json", "w", encoding="utf-8") as f:
        json.dump(crate, f, ensure_ascii=False, indent=2)

    with open(ROOT / "boundary_nanopub.json", "w", encoding="utf-8") as f:
        json.dump(nanopub, f, ensure_ascii=False, indent=2)

    print(f"[ok] wrote {out_path} ({len(products)} entries)")
    print(f"[ok] wrote boundary_crate.json (RO-Crate, {len(crate.get('@graph', []))} graph nodes)")
    print(f"[ok] wrote boundary_nanopub.json (nanopublication)")
    if issues:
        print(f"[warn] {len(issues)} validation issue(s) — see 'validation_issues'")
        return 2
    print("[ok] E4 acceptance: all entries citable + crate valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
