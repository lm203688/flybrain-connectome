#!/usr/bin/env python3
"""issue_receipt.py — S2 verification receipt issuer.

Turns each preregistered protocol or claim into a third-party-verifiable receipt:

  receipt = {
    "claim_id": "...",
    "raw_sample_sha256": "sha256(raw artifact file)",
    "recompute_script_sha256": "sha256(recompute script that produced verdict)",
    "expected_verdict": "PASS|FAIL|WEAK_PASS|ACCEPT",
    "env_hash": "sha256(py_version + os + key modules)",
    "timestamp": "ISO 8601",
    "artifacts": [ {path, sha256}, ... ],
    "scripts":   [ {path, sha256}, ... ],
    "protocol_ref": "...",
    "notes": "..."
  }

Third party needs only raw artifact + recompute script + receipt, and can
independently verify without trusting the author's summary — this is the
"hash-commitment is enough" model (RISC-Zero-style, without ZK).

Usage:
    python scripts/issue_receipt.py --out receipts/

Writes receipts/<claim_id>.json for each configured claim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Claim -> (raw artifacts, recompute scripts, expected verdict, protocol ref)
# ---------------------------------------------------------------------------
CLAIM_SPECS: list[dict] = [
    {
        "claim_id": "R1",
        "statement": "模块化拓扑普遍提供故障隔离 (92.6%)；纯结构解释一小部分 (R²≈0.15)",
        "artifacts": [
            "_r1_mechanism_a/graded_isolation.json",
            "_r1_mechanism_a/mechanism_binary.json",
            "_r1_mechanism_prereg/f1_preregistered.json",
        ],
        "scripts": [
            "scripts/isolation_graded.py",
            "scripts/mechanism_binary.py",
            "scripts/f1_controllability_features.py",
        ],
        "expected_verdict": "WEAK",
        "protocol_ref": "PR1",
        "notes": "Preregistered forward prediction: AUC=0.788 ✅ / z=1.53 ❌ (WEAK_PASS).",
    },
    {
        "claim_id": "R2",
        "statement": "稀疏结构空间 (0.002-0.023) 无 GA 可搜索梯度；随机采样胜 GA",
        "artifacts": [
            "_gate31_r2/r2_density_scan.json",
        ],
        "scripts": [
            "scripts/f2_recovery_dynamics.py",
        ],
        "expected_verdict": "PASS",
        "protocol_ref": "None",
        "notes": "GA underperforms random sampling in the sparse regime — verified across density grid.",
    },
    {
        "claim_id": "R3",
        "statement": "结构-任务对齐度决定结构增益；对齐度<阈值时结构增益→0",
        "artifacts": [
            "_f3_generalization/f3_generalization.json",
        ],
        "scripts": [
            "scripts/f3_generalization_matrix.py",
        ],
        "expected_verdict": "FAIL",
        "protocol_ref": "PR3",
        "notes": "Cross-family AUC=0.5, n_positive=0 on 5 non-project-synthetic families. Boundary.",
    },
    {
        "claim_id": "R4",
        "statement": "确定性可复算结构指纹（sha256 over 归一化结构）",
        "artifacts": [
            "_gate32_r4/r4_sensitivity_scan.json",
        ],
        "scripts": [
            "scripts/check_topology_signature.py",
        ],
        "expected_verdict": "PASS",
        "protocol_ref": "None",
        "notes": "Structural signature reproducible across seeds; sensitive to non-trivial perturbations.",
    },
    {
        "claim_id": "R5",
        "statement": "确定性可复现的结构级生命闭环；出生签名同 seed 逐位一致",
        "artifacts": [],
        "scripts": [
            "lifecycle.py",
        ],
        "expected_verdict": "PASS",
        "protocol_ref": "None",
        "notes": "8-stage lifecycle: birth->survival->damage->repair->reproduction->selection->death, deterministic under seed.",
    },
    {
        "claim_id": "R6",
        "statement": "回路模式跨 4 进化支保守；家族特征可识别",
        "artifacts": [],
        "scripts": [
            "scripts/build_capability_matrix.py",
        ],
        "expected_verdict": "BOUNDARY",
        "protocol_ref": "None",
        "notes": "Anchored_validated; declarative extension (random_seed=null) declared boundary_anchor_gap.",
    },
    {
        "claim_id": "PR2",
        "statement": "删除桥边导致隔离度上升（干预因果）",
        "artifacts": [
            "_f4_intervention/f4_intervention.json",
        ],
        "scripts": [
            "scripts/f4_intervention_test.py",
        ],
        "expected_verdict": "FAIL",
        "protocol_ref": "PR2",
        "notes": "composite 38.9% (n=10) → 71.4% (n=50) → 59.1% (n=100); not monotone.",
    },
    {
        "claim_id": "PR4",
        "statement": "恢复动力学三补偿分量非退化；recovery_AUC 有真实方差",
        "artifacts": [
            "_f2_recovery/f2_recovery_dynamics.json",
        ],
        "scripts": [
            "scripts/f2_recovery_dynamics.py",
        ],
        "expected_verdict": "PASS",
        "protocol_ref": "PR4",
        "notes": "zero_ratio=0%, variance=0.0114; three compensation mechanisms R-a/R-b/R-c all non-degenerate.",
    },
    {
        "claim_id": "PR2b",
        "statement": "PR-2 替代度量（recovery_AUC）预执行拒绝：与干预变量解析耦合",
        "artifacts": [
            "_f4b_metric_substitution/f4b_metric_substitution.json",
        ],
        "scripts": [
            "scripts/f4b_metric_substitution_check.py",
        ],
        "expected_verdict": "ACCEPT",
        "protocol_ref": "PR2b",
        "notes": "|corr|=0.902 on merged sample; analytic proof of denominator artifact. Rule_underpowered=true.",
    },
]


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _env_hash() -> str:
    """Stable-enough environment fingerprint. Excludes volatile per-machine fields."""
    parts = [
        "python=" + platform.python_version(),
        "os=" + platform.system(),
        "arch=" + platform.machine(),
    ]
    for mod in ("numpy", "pandas", "networkx"):
        try:
            m = __import__(mod)
            parts.append(f"{mod}=" + getattr(m, "__version__", "n/a"))
        except ImportError:
            parts.append(f"{mod}=absent")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def issue_one(spec: dict, root: Path) -> dict:
    artifacts = []
    for rel in spec["artifacts"]:
        p = root / rel
        if p.exists() and p.is_file():
            artifacts.append({"path": rel, "sha256": _sha256_file(p), "size": p.stat().st_size})
        else:
            artifacts.append({"path": rel, "sha256": None, "size": None, "status": "missing"})

    scripts = []
    for rel in spec["scripts"]:
        p = root / rel
        if p.exists() and p.is_file():
            scripts.append({"path": rel, "sha256": _sha256_file(p), "size": p.stat().st_size})
        else:
            scripts.append({"path": rel, "sha256": None, "size": None, "status": "missing"})

    receipt = {
        "schema": "vro_receipt_v1",
        "claim_id": spec["claim_id"],
        "statement": spec["statement"],
        "protocol_ref": spec["protocol_ref"],
        "expected_verdict": spec["expected_verdict"],
        "raw_sample_sha256": (
            hashlib.sha256("|".join(a["sha256"] or "" for a in artifacts).encode()).hexdigest()
            if any(a.get("sha256") for a in artifacts) else None
        ),
        "recompute_script_sha256": (
            hashlib.sha256("|".join(s["sha256"] or "" for s in scripts).encode()).hexdigest()
            if any(s.get("sha256") for s in scripts) else None
        ),
        "artifacts": artifacts,
        "scripts": scripts,
        "env_hash": _env_hash(),
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "issued_by": "scripts/issue_receipt.py",
        "notes": spec["notes"],
    }
    return receipt


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="receipts/", help="output directory")
    ap.add_argument("--claim", help="issue only the receipt for this claim_id (repeatable)")
    args = ap.parse_args()

    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    specs = CLAIM_SPECS
    if args.claim:
        specs = [s for s in specs if s["claim_id"] == args.claim]
        if not specs:
            print(f"unknown claim_id: {args.claim}", file=sys.stderr)
            return 2

    written = []
    for spec in specs:
        receipt = issue_one(spec, ROOT)
        out_path = out_dir / f"{spec['claim_id']}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(receipt, f, ensure_ascii=False, indent=2)
        written.append(out_path)

    print("=" * 60)
    print(f"issued {len(written)} receipt(s) -> {out_dir}")
    for p in written:
        print(f"  {p.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
