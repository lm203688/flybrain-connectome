#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""v2.46.0 — extract circuit profiles from the Zebrafish larval connectome.

Source (待实施，本文件是骨架不下载数据)：
    Petkova MD, Januszewski M, et al.  "A connectomic resource for neural
    cataloguing and circuit dissection of the larval zebrafish brain."
    bioRxiv 10.1101/2025.06.10.658982 (2025).
    数据入口：https://fish1-release.storage.googleapis.com/index.html
    许可：CC-BY-NC 4.0（与本项目 MIT 主许可冲突，见
    docs/zebrafish_connectome_feasibility.md）

规模：>180,000 somas / >40,000 molecularly annotated / ~30M synapses /
    递质分类（excitatory / inhibitory / modulatory）。

本文件在数据授权与采样完成前只声明**期望的输入输出**，落地前必须：
    1. 用户确认 CC-BY-NC 授权边界（本项目 MIT 主体如何隔离）
    2. 用户明确授权拉采样数据（~600 MB，见可行性文档采样策略表）
    3. 决定抽取哪 3-5 个 circuit（示范：lateral line / hindbrain / tegmental）

跑起来时的行为（fail-closed）：
    ZEBRAFISH_DATA_DIR 未设 → 打印 SKIPPED，exit 0（门禁不误红）
    ZEBRAFISH_DATA_DIR 设了但目录空 → 打印 FAILED，exit 3
    ZEBRAFISH_DATA_DIR 设了且文件齐 → 跑解析，产出 zebrafish_profiles.json
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MCP = ROOT / "flybrain-connectome-mcp"
OUT = MCP / "functional_units" / "zebrafish_profiles.json"

# 期望的输入文件名（作者平台导出的最小采样集）
EXPECTED_INPUTS = (
    "somas.csv",        # soma_id, x, y, z, region, vglut2a_label, gad1b_label
    "edges.csv",        # source_soma_id, target_soma_id, synapse_count, drive_in, drive_out
    "circuits.json",    # {"lateral_line": [...soma_ids], "hindbrain": [...], ...}
)

# 期望的输出形状（对齐 larva_profiles.json / cel_profiles.json）
OUTPUT_SCHEMA = {
    "schema_version": "1.0",
    "source": "Petkova 2025, fish1-release, CC-BY-NC 4.0",
    "somas_total": 180000,
    "annotated_somas": 40000,
    "synapses_total": 30000000,
    "caveat": "采样集，不代表全脑 30M 突触；分子标签覆盖率取决于作者平台的分子注释密度",
    "profiles": {},  # name -> {somas, synapses, excitatory_fraction, connections, ...}
}


def skip_with_message() -> int:
    """ZEBRAFISH_DATA_DIR 未设：正常跳过，不 FAIL。

    与 extract_larva_profiles.py 不同——larva 是本地数据源（cel_data/ 已在库内），
    斑马鱼是远程 Google Cloud，需要显式授权才能拉。所以未设目录不算错误，
    而是明确的「尚未激活」状态。
    """
    print("SKIPPED: ZEBRAFISH_DATA_DIR not set")
    print("  下一步：与用户确认 CC-BY-NC 授权边界")
    print("  →  采样数据落 Tier-2 私有仓")
    print("  →  填本文件的 _load() 与 _emit() 实现")
    print("  详见：docs/zebrafish_connectome_feasibility.md")
    return 0


def fail_with_message(msg: str) -> int:
    print(f"FAILED: {msg}")
    return 3


def _load_inputs(data_dir: Path) -> tuple[dict, dict, dict]:
    """读三个输入文件。fail-closed：缺任何一个立即退出 3。"""
    for fname in EXPECTED_INPUTS:
        p = data_dir / fname
        if not p.exists():
            return {}, {}, {}  # 由调用方检测并 fail

    # 用 pandas 读 CSV（本项目 pyproject.toml [project.optional-dependencies].data 已装）
    import pandas as pd
    somas = pd.read_csv(data_dir / "somas.csv")
    edges = pd.read_csv(data_dir / "edges.csv")
    circuits = json.loads((data_dir / "circuits.json").read_text(encoding="utf-8"))

    # 分子标签解析：vgLut2a = excitatory, gad1b = inhibitory
    # 两者都有 → ambiguous（不声明极性）；两者都无 → unannotated
    def polarity(row) -> str:
        v = str(row.get("vglut2a_label", "")).strip().lower()
        g = str(row.get("gad1b_label", "")).strip().lower()
        if v in ("1", "true", "yes", "y") and not (g in ("1", "true", "yes", "y")):
            return "excitatory"
        if g in ("1", "true", "yes", "y") and not (v in ("1", "true", "yes", "y")):
            return "inhibitory"
        if v in ("1", "true", "yes", "y") and g in ("1", "true", "yes", "y"):
            return "ambiguous"
        return "unannotated"

    somas["polarity"] = somas.apply(polarity, axis=1)
    return {"somas": somas, "edges": edges}, {}, circuits


def _emit(data_dir: Path, out: Path) -> int:
    """抽 3-5 个 circuit，产出 zebrafish_profiles.json。"""
    somas_df, edges_df, circuits = _load_inputs(data_dir)
    if somas_df.empty:
        return fail_with_message(f"no somas loaded from {data_dir}")

    profiles = {}
    for name, soma_ids in circuits.items():
        soma_set = set(soma_ids)
        mask = somas_df["soma_id"].isin(soma_set)
        sub_somas = somas_df[mask]
        sub_edges = edges_df[
            edges_df["source_soma_id"].isin(soma_set)
            & edges_df["target_soma_id"].isin(soma_set)
        ]

        polarity_counts = sub_somas["polarity"].value_counts().to_dict()
        total = len(sub_somas) or 1
        profile = {
            "somas": int(total),
            "synapses": int(sub_edges["synapse_count"].sum()),
            "excitatory_fraction": round(polarity_counts.get("excitatory", 0) / total, 4),
            "inhibitory_fraction": round(polarity_counts.get("inhibitory", 0) / total, 4),
            "unannotated_fraction": round(polarity_counts.get("unannotated", 0) / total, 4),
            "polarity_counts": {k: int(v) for k, v in polarity_counts.items()},
            "edges_sample": sub_edges.head(20).to_dict(orient="records"),
            "caveat": (
                f"sampled from {len(somas_df)} somas in {data_dir.name}; "
                "not the full 180k soma brain-wide matrix"
            ),
        }
        profiles[name] = profile

    payload = dict(OUTPUT_SCHEMA)
    payload["profiles"] = profiles
    payload["generated_from"] = str(data_dir)
    payload["somas_in_sample"] = int(len(somas_df))
    payload["synapses_in_sample"] = int(edges_df["synapse_count"].sum())

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"emitted {out} — {len(profiles)} profiles from {len(somas_df)} somas")
    return 0


def main() -> int:
    env_dir = os.environ.get("ZEBRAFISH_DATA_DIR", "").strip()
    if not env_dir:
        return skip_with_message()

    data_dir = Path(env_dir).expanduser().resolve()
    if not data_dir.exists():
        return fail_with_message(f"ZEBRAFISH_DATA_DIR={data_dir} does not exist")
    if not data_dir.is_dir():
        return fail_with_message(f"ZEBRAFISH_DATA_DIR={data_dir} is not a directory")

    # 检查是否至少有一个期望文件
    present = [f for f in EXPECTED_INPUTS if (data_dir / f).exists()]
    if not present:
        return fail_with_message(
            f"{data_dir} has none of the expected input files "
            f"{list(EXPECTED_INPUTS)}"
        )
    missing = set(EXPECTED_INPUTS) - set(present)
    if missing:
        return fail_with_message(
            f"{data_dir} has {present} but is missing {sorted(missing)}"
        )

    return _emit(data_dir, OUT)


if __name__ == "__main__":
    sys.exit(main())
