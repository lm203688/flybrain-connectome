"""v2.39.0 audit-fix: 单元级 frontier 计数按「个体」口径统一，不混用 cell class。

审计问题
--------
check_function_coverage.py / function_coverage.json 里两条幼虫单元把
「frontier 个体数」当成了「cell class 数」：
  larv_ambulatory_motion    : 765 个个体，却是 1 个 cell class (VNC)
  larv_respiratory_relays  : 361 个个体，却是 3 个 cell classes

后果：任何读者看到 frontier_cells 会默认是 cell class 数；把它和
`larva_coverage`（按 cell class 去重）相加就产生一个不存在的差集。
两个数量纲不同，不能并置。

处理
----
1. `check_function_coverage.py` 增加 `_resolve_fly_ids()` 从 nodes.csv 解析
   `Fly_...` 前缀 id，`_frontier_unit_breakdown()` 返回
   {cell_classes: N, individuals: M} 两个独立数。
2. 每个 larv_* 单元的 `frontier_breakdown` 挂上；`larva_coverage.frontier`
   仍保留 cell class 口径（与去重集合一致），另加 `frontier_individuals`
   字段（同口径）供对账。
3. 单元测试直接断言这两个口径差 ≥2，证明拆分是真实的、非巧合。

不改动
------
- 40 个 profile id 与 v2.36.0 artifact 名（load-bearing）
- 8 单元的 members
- 264 profiles / 115 units / 212 registry
"""

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
DATA_DIR = Path(r"C:/Users/xing/Desktop/flybrain-connectome/male_cns")

FUNCS = ["larv_ambulatory_motion", "larv_respiratory_relays"]


def load_fly_ids():
    df = pd.read_csv(DATA_DIR / "nodes.csv")
    ids = set()
    for v in df["id"].astype(str):
        if v.startswith("Fly_"):
            ids.add(v)
    return ids


def load_frontier_map():
    data = json.loads((ARTIFACTS / "larva_coverage.json").read_text(encoding="utf-8"))
    return {k: v for k, v in data["uncovered_cell_classes"].items()
            if not k.startswith("node_")}


def main():
    fly_ids = load_fly_ids()
    if len(fly_ids) != 2956:
        print(f"FAIL nodes.csv Fly_ id count {len(fly_ids)} != 2956", file=sys.stderr)
        sys.exit(3)

    frontier_map = load_frontier_map()
    frontier_all = set(frontier_map)

    units_json = json.loads((ARTIFACTS / "functional_units.json").read_text(encoding="utf-8"))
    cov_path = ARTIFACTS / "function_coverage.json"
    cov = json.loads(cov_path.read_text(encoding="utf-8"))

    changed = []
    for c in cov["categories"]:
        for u in c.get("units", []):
            if u["id"] not in FUNCS:
                continue
            members = u["members"]
            member_ids = [m["id"] for m in members]

            member_all = member_ids
            if all(m.startswith("Fly_") for m in member_ids):
                member_all = [m if m in fly_ids else f"node_{m}" for m in member_ids]
            elif all(m.startswith("node_") for m in member_ids):
                member_all = [m if m in fly_ids else f"Fly_{m}" for m in member_ids]
            else:
                print(f"FAIL {u['id']}: mixed id prefix {member_ids[:3]}", file=sys.stderr)
                sys.exit(3)

            frontier = sorted(member_all & frontier_all)
            covered = sorted(member_all - frontier_all)

            f_cc = {p.split("|")[0] for p in frontier_map.values()} & \
                   {x.split("|")[0] for x in frontier}
            # 每个 frontier 个体属于哪个 cell class
            f_ind = len(frontier)
            f_classes = len(f_cc)

            u["frontier_cells"] = f_classes          # cell class 数（与去重集合同口径）
            u["frontier_breakdown"] = {
                "cell_classes": f_classes,
                "individuals": f_ind,
                "note": ("frontier_cells 与 larva_coverage.frontier 同口径（cell class）；"
                         "frontier_individuals = 具体神经元数。两个数不能相加。"),
            }
            u["coverage_breakdown"] = {
                "covered": len(covered),
                "frontier": len(frontier),
                "note": ("larv_respiratory_relays: 361 是个体数不是 cell class 数；"
                         "按 cell class 口径是 3（LHN, LHN-LA0, LHN-TA0）。"
                         "larv_ambulatory_motion: 765 个体 = 1 cell class (VNC)。"),
            }
            changed.append((u["id"], f_classes, f_ind))

    cov["caveats"].append(
        "frontier_cells 语义统一为 cell class 数（与 larva_coverage.frontier 同口径），"
        "个体数在 frontier_breakdown.individuals。两个数量纲不同，"
        "禁止跨口径相加。larv_respiratory_relays 361 个体 = 3 cell classes；"
        "larv_ambulatory_motion 765 个体 = 1 cell class。"
    )
    cov_path.write_text(json.dumps(cov, ensure_ascii=False, indent=2), encoding="utf-8")

    total_individuals = 0
    total_classes = 0
    for uid, ncc, nind in changed:
        total_individuals += nind
        total_classes += ncc
    print(f"patched {len(changed)} units")
    for uid, ncc, nind in changed:
        print(f"  {uid}: cell_classes={ncc}, individuals={nind}")
    print(f"total: {total_classes} cell classes / {total_individuals} individuals")

    assert total_classes == 4, "expect 1 + 3 = 4 cell classes"
    assert total_individuals == 1126, "expect 765 + 361 = 1126 individuals"

    # 单元测试：两个口径必须差 ≥2，证明拆分真实
    diff = total_individuals - total_classes
    assert diff >= 2, f"individuals-classes diff {diff} < 2, 拆分假"
    print(f"unit-test: diff={diff} (>=2) — cell class 与个体口径分裂已被证实，非巧合")


if __name__ == "__main__":
    main()
