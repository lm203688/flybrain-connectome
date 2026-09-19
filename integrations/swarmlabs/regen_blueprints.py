"""
批量重新生成所有 blueprint 的 .swarm.json 文件（schema v1.1.1 + motif_provenance）。

用法：
    python regen_blueprints.py
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

sys.path.insert(0, r"C:\Users\xing\Desktop\flybrain-connectome\flybrain-connectome-mcp")
import synthetic_bio_topology as c1

OUT_DIR = Path(r"C:\Users\xing\Desktop\flybrain-connectome\flybrain-connectome-mcp\generated_organisms\swarmlabs")

# 9 个单个蓝图 + 3 个组合蓝图
BLUEPRINTS = [
    "sequential",
    "deep_reasoning",
    "fast_reflex",
    "broad_explore",
    "orchestrated",
    "hierarchical",
    "lateral_inhibition",
    "predictive_coding",
    "competitive_selection",
    # 组合蓝图
    "deep_reasoning+competitive_selection",
    "deep_reasoning+fast_reflex",
    "lateral_inhibition+competitive_selection",
]


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # Resolve motifs (local snapshot, offline) — returns (doc, provenance)
    doc, prov = c1.resolve_motifs(source="local")
    print(f"Resolved motifs: {list(doc.get('motifs', {}).keys())}")

    for bp in BLUEPRINTS:
        spec = {
            "n_modules": 4,
            "agents_per_module": 4,
            "module_profiles": "cycled",
            "blueprint": bp,
        }
        org = c1.design_organism(spec, motifs=doc, seed=7)
        # build_swarmlabs_config takes provenance as separate arg
        cfg = c1.build_swarmlabs_config(org, name=f"bp_{bp.replace('+', '__')}", provenance=prov)
        # Write .swarm.json
        file_stem = bp.replace("+", "__")
        fp = OUT_DIR / f"bp_{file_stem}.swarm.json"
        fp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        mp = cfg.get("motif_provenance", {})
        print(f"  {fp.name:50s} schema={cfg.get('schema_version')} "
              f"agents={cfg['swarm']['validation']['n_agents']} "
              f"edges={cfg['swarm']['validation']['n_edges']} "
              f"bio={mp.get('is_bio_prior')}")

    print(f"\n生成完成：{len(BLUEPRINTS)} 个 .swarm.json 文件")


if __name__ == "__main__":
    main()
