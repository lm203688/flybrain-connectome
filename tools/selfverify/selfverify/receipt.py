"""selfverify.receipt — S2 验证收据（Verification Receipt）核心逻辑。

为每条 claim 生成可第三方验证的收据：
  receipt = {
    claim_id, raw_sample_sha256, recompute_script_sha256,
    expected_verdict, env_hash, timestamp,
    artifacts, scripts, protocol_ref, notes
  }

第三方只需原始样本 + 脚本即可独立重算并比对，无需信任作者摘要。
这是 RISC-Zero 风格的 self-certifying receipt（不需要 ZK，hash 承诺已足够）。

参考：RISC Zero self-certifying receipt model.
"""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    """计算文件的 SHA-256 哈希。"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def env_hash() -> str:
    """稳定的环境指纹。排除易变字段。"""
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


def issue_one(spec: dict[str, Any], root: Path) -> dict[str, Any]:
    """为单个 claim 生成验证收据。
    
    Args:
        spec: claim 规格字典，含 claim_id, artifacts, scripts, expected_verdict, 等
        root: 项目根目录路径
    
    Returns:
        收据字典
    """
    artifacts = []
    for rel in spec.get("artifacts", []):
        p = root / rel
        if p.exists() and p.is_file():
            artifacts.append({"path": rel, "sha256": sha256_file(p), "size": p.stat().st_size})
        else:
            artifacts.append({"path": rel, "sha256": None, "size": None, "status": "missing"})

    scripts = []
    for rel in spec.get("scripts", []):
        p = root / rel
        if p.exists() and p.is_file():
            scripts.append({"path": rel, "sha256": sha256_file(p), "size": p.stat().st_size})
        else:
            scripts.append({"path": rel, "sha256": None, "size": None, "status": "missing"})

    receipt = {
        "schema": "vro_receipt_v1",
        "claim_id": spec["claim_id"],
        "statement": spec.get("statement", ""),
        "protocol_ref": spec.get("protocol_ref", "None"),
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
        "env_hash": env_hash(),
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "issued_by": "selfverify.receipt",
        "notes": spec.get("notes", ""),
    }
    return receipt


def issue_many(specs: list[dict[str, Any]], root: Path, out_dir: Path) -> list[Path]:
    """批量生成验证收据。
    
    Args:
        specs: claim 规格列表
        root: 项目根目录路径
        out_dir: 输出目录
    
    Returns:
        写入的文件路径列表
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for spec in specs:
        receipt = issue_one(spec, root)
        out_path = out_dir / f"{spec['claim_id']}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(receipt, f, ensure_ascii=False, indent=2)
        written.append(out_path)
    return written


def verify_one(receipt: dict[str, Any], raw_sample: bytes, recompute_fn=None) -> dict[str, Any]:
    """验证单个收据。
    
    Args:
        receipt: 收据字典
        raw_sample: 原始样本字节
        recompute_fn: 重算函数（可选）
    
    Returns:
        验证结果字典
    """
    result = {
        "claim_id": receipt.get("claim_id"),
        "status": "VERIFIED",
        "checks": {},
        "errors": [],
    }
    
    # 1. 检查 raw_sample_sha256
    if receipt.get("raw_sample_sha256"):
        computed = hashlib.sha256(raw_sample).hexdigest()
        expected = receipt["raw_sample_sha256"]
        if computed == expected:
            result["checks"]["raw_sample_sha256"] = "OK"
        else:
            result["checks"]["raw_sample_sha256"] = "MISMATCH"
            result["errors"].append(f"raw_sample_sha256: expected {expected}, got {computed}")
            result["status"] = "FAILED"
    
    # 2. 检查 recompute_script_sha256（如果提供重算函数）
    if recompute_fn and receipt.get("recompute_script_sha256"):
        try:
            recomputed = recompute_fn(receipt)
            if recomputed == receipt.get("expected_verdict"):
                result["checks"]["recompute_verdict"] = "OK"
            else:
                result["checks"]["recompute_verdict"] = "MISMATCH"
                result["errors"].append(
                    f"recompute_verdict: expected {receipt['expected_verdict']}, got {recomputed}"
                )
                result["status"] = "FAILED"
        except Exception as e:
            result["checks"]["recompute_verdict"] = f"ERROR: {e}"
            result["errors"].append(f"recompute_fn raised: {e}")
            result["status"] = "FAILED"
    
    return result


def verify_many(receipts_dir: Path, root: Path) -> list[dict[str, Any]]:
    """批量验证收据目录中的所有收据。
    
    Args:
        receipts_dir: 收据目录路径
        root: 项目根目录路径
    
    Returns:
        验证结果列表
    """
    results = []
    for receipt_path in sorted(receipts_dir.glob("*.json")):
        with open(receipt_path, encoding="utf-8") as f:
            receipt = json.load(f)
        
        # 检查工件是否存在
        artifacts_ok = all(
            (root / a["path"]).exists()
            for a in receipt.get("artifacts", [])
            if a.get("sha256")
        )
        scripts_ok = all(
            (root / s["path"]).exists()
            for s in receipt.get("scripts", [])
            if s.get("sha256")
        )
        
        result = {
            "claim_id": receipt.get("claim_id"),
            "status": "VERIFIED" if artifacts_ok and scripts_ok else "FAILED",
            "checks": {
                "artifacts_present": artifacts_ok,
                "scripts_present": scripts_ok,
            },
            "errors": [],
        }
        
        if not artifacts_ok:
            missing = [a["path"] for a in receipt.get("artifacts", []) 
                      if a.get("sha256") and not (root / a["path"]).exists()]
            result["errors"].append(f"missing artifacts: {missing}")
        
        if not scripts_ok:
            missing = [s["path"] for s in receipt.get("scripts", [])
                      if s.get("sha256") and not (root / s["path"]).exists()]
            result["errors"].append(f"missing scripts: {missing}")
        
        results.append(result)
    
    return results
