"""
check_swarmlabs_sync.py — 校验基地(flybrain-connectome) 与 SwarmLabs 两侧的一致性

为什么需要它：两边故意**不共享代码**（保持项目独立），所以最容易出的问题不是崩溃，
而是「悄悄漂移」——某天有人只更新了一侧，另一侧还在用旧客户端 / 旧 motif 快照，
结果两边算出来的拓扑不一样却都"跑得通"。

本脚本只读、不改，做四件事：
  1. 客户端文件 sha256 是否一致
  2. motif 快照 sha256 是否一致（漂移即代表有人重抽了 motif 却没同步）
  3. C1 产出的 swarm config 是否能被 SwarmLabs 侧 loader 加载 + 通过独立复算校验
  4. motif 里的关键真实数字是否仍是预期的锚点（防止静默换数据）

用法：
    python check_swarmlabs_sync.py
    python check_swarmlabs_sync.py --swarmlabs C:\\path\\to\\swarmlabs
退出码：0 = 全绿；1 = 有漂移/校验失败
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

BASE = Path(os.environ.get("FLYBRAIN_BASE", r"C:\Users\xing\Desktop\flybrain-connectome"))
DEFAULT_SWARMLABS = Path(os.environ.get("SWARMLABS_ROOT", r"C:\Users\xing\Desktop\swarmlabs"))

# 期望锚点：来自真实 MaleCNS v1.0，若变了说明数据/motif 被换过，必须人工确认
EXPECTED_ANCHORS = {
    "dataset_stats.total_synapses": 124177617,
    "support_motifs.inhibitory_hub.hub_body": 10540,
    "support_motifs.inhibitory_hub.canonical_target.synapses": 711,
    "support_motifs.reservoir_smallworld.fanout_distribution_pct.101-1000": 49.36,
}


def sha256_file(p: Path) -> str | None:
    if not p.exists():
        return None
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _dig(doc: dict, dotted: str):
    cur = doc
    for part in dotted.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def load_swarmlabs_loader(swarmlabs: Path):
    p = swarmlabs / "agent_topology" / "load_organism_config.py"
    if not p.exists():
        return None
    spec = importlib.util.spec_from_file_location("_swarmlabs_loader", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)          # type: ignore[union-attr]
    return mod


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", default=str(BASE))
    ap.add_argument("--swarmlabs", default=str(DEFAULT_SWARMLABS))
    args = ap.parse_args(argv)

    base = Path(args.base)
    sl = Path(args.swarmlabs)
    ok = True
    rows: list[tuple[str, str, str]] = []

    # ---- 1/2: 文件一致性 ------------------------------------------- #
    pairs = [
        ("客户端 client.py",
         base / "flybrain-connectome-mcp" / "motifs" / "flybrain_connectome_client.py",
         sl / "agent_topology" / "flybrain_connectome_client.py"),
        ("motif 快照 motifs.json",
         base / "flybrain-connectome-mcp" / "motifs" / "swarm_agent_topology_motifs.json",
         sl / "agent_topology" / "swarm_agent_topology_motifs.json"),
    ]
    for label, a, b in pairs:
        ha, hb = sha256_file(a), sha256_file(b)
        if ha is None or hb is None:
            rows.append((label, "MISSING", "base=%s swarmlabs=%s" % (
                "有" if ha else "缺", "有" if hb else "缺")))
            ok = False
        elif ha == hb:
            rows.append((label, "OK", ha[:16]))
        else:
            rows.append((label, "DRIFT", "base=%s swarmlabs=%s" % (ha[:16], hb[:16])))
            ok = False

    # ---- 3: motif 锚点 --------------------------------------------- #
    motif_doc = None
    mp = base / "flybrain-connectome-mcp" / "motifs" / "swarm_agent_topology_motifs.json"
    if mp.exists():
        motif_doc = json.loads(mp.read_text(encoding="utf-8"))
        flat = {"dataset_stats": motif_doc.get("dataset_stats", {}),
                "support_motifs": motif_doc.get("motifs", {})}
        for dotted, want in EXPECTED_ANCHORS.items():
            got = _dig(flat, dotted)
            if got == want:
                rows.append(("锚点 " + dotted, "OK", str(got)))
            else:
                rows.append(("锚点 " + dotted, "CHANGED", "期望 %s 实得 %s" % (want, got)))
                ok = False
    else:
        rows.append(("motif 快照", "MISSING", str(mp)))
        ok = False

    # ---- 4: C1 产物可加载性 ---------------------------------------- #
    loader = load_swarmlabs_loader(sl)
    gen = base / "flybrain-connectome-mcp" / "generated_organisms" / "swarmlabs"
    if loader is None:
        rows.append(("SwarmLabs loader", "MISSING",
                     str(sl / "agent_topology" / "load_organism_config.py")))
        ok = False
    elif not gen.exists():
        rows.append(("C1 swarm configs", "MISSING", str(gen)))
    else:
        cfgs = sorted(gen.glob("*.swarm.json"))
        for c in cfgs:
            try:
                cfg = loader.load_organism_config(c)
                rep = loader.validate_swarm_config(cfg)
                if rep["ok"]:
                    rows.append(("加载+校验 " + c.name, "OK",
                                 "%d agents / %d edges" % (rep["n_agents"], rep["n_edges"])))
                else:
                    bad = {k: v for k, v in rep.items()
                           if k not in ("ok", "n_agents", "n_edges") and v}
                    rows.append(("加载+校验 " + c.name, "FAIL", str(bad)[:80]))
                    ok = False
            except Exception as e:  # noqa: BLE001
                rows.append(("加载+校验 " + c.name, "ERROR", str(e)[:80]))
                ok = False

    # ---- 报表 ------------------------------------------------------ #
    w = max(len(r[0]) for r in rows)
    print("\nflybrain-connectome ⇄ SwarmLabs 同步体检")
    print("  base      : %s" % base)
    print("  swarmlabs : %s\n" % sl)
    for label, status, extra in rows:
        print("  %-*s  %-8s  %s" % (w, label, status, extra))
    print("\n结论: %s" % ("全部一致 ✓" if ok else "存在漂移/失败 ✗（见上表）"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
