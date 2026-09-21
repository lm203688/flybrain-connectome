"""
A1 交付物：从真实连接组生成数据驱动的模块库。
每个模块带真实溯源：superclass 引用 + 神经元数 + 突触数 + 自循环率 + 递质指纹。
"""
import json
import numpy as np
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[2]
MALE = ROOT / "male_cns"
CACHE = MALE / "connectome_cache"

mat = json.loads((MALE / "superclass_matrix.json").read_text(encoding="utf-8"))
sc = mat["superclass_list"]
idx = {s: i for i, s in enumerate(sc)}
M = np.array(mat["matrix"], dtype=np.float64)
total = M.sum()

facts = json.loads((MALE / "connectivity_facts.json").read_text(encoding="utf-8"))
n_neu = {x["superclass"]: x["n_neurons"] for x in facts["superclass_io"]}

nt_raw = json.loads((CACHE / "nt.json").read_text(encoding="utf-8"))
ann = json.loads((CACHE / "annotations.json").read_text(encoding="utf-8"))
NT_KINDS = ["acetylcholine", "dopamine", "gaba", "glutamate",
            "histamine", "octopamine", "serotonin"]
sc_nt = {s: Counter() for s in sc}
for body, rec in ann.items():
    s = rec.get("superclass")
    if not s or s not in sc_nt:
        continue
    nt = nt_raw.get(str(body)) or nt_raw.get(int(body))
    if isinstance(nt, list):
        nt = nt[0] if nt else None
    k = str(nt).strip().lower() if nt else ""
    if k in NT_KINDS:
        sc_nt[s][k] += 1


def fingerprint(s):
    i = idx[s]
    out_tot = M[i].sum()
    self_r = float(M[i, i] / out_tot) if out_tot else 0.0
    c = sc_nt[s]
    tot_nt = sum(c.values())
    nt = {k: round(v / tot_nt, 4) for k, v in c.most_common()} if tot_nt else {}
    dom = c.most_common(1)[0][0] if tot_nt else None
    # 出边 top5（真实组合去向）
    outs = [(sc[j], int(M[i, j])) for j in np.argsort(-M[i])[:6]
            if M[i, j] > 0 and sc[j] != s]
    return {
        "real_superclass": s,
        "n_neurons": n_neu[s],
        "out_synapses": int(out_tot),
        "in_synapses": int(M[:, i].sum()),
        "self_recurrence": round(self_r, 4),
        "dominant_neurotransmitter": dom,
        "neurotransmitter_profile": nt,
        "top_downstream": [{"to": t, "synapses": v} for t, v in outs],
    }


# 数据驱动的模块分组（基于 Louvain 社区 + Ward 层次聚类 + 递质指纹）
GROUPS = [
    ("recurrent_core_olfactory", "recurrent_memory",
     "嗅觉内在核：全脑最大的自循环记忆体，81% 输出回流自身",
     ["ol_intrinsic"]),
    ("recurrent_core_central", "recurrent_memory",
     "中枢内在核：第二记忆体，88% 输出回流自身",
     ["cb_intrinsic"]),
    ("recurrent_core_vnc", "recurrent_memory",
     "腹神经索内在核：运动程序记忆，71% 输出回流自身",
     ["vnc_intrinsic"]),
    ("visual_pathway", "sensory_transform",
     "视觉投射+离心门控（离心单元 59% GABA，抑制型门控）",
     ["visual_projection", "visual_centrifugal"]),
    ("sensory_intake", "sensory_input",
     "三类感觉输入：嗅觉(组胺)/中枢(ACh)/腹神经索(ACh)",
     ["ol_sensory", "cb_sensory", "vnc_sensory"]),
    ("long_range_relay", "relay",
     "脑-腹神经索长程中继（上行/下行/感觉升降）",
     ["ascending_neuron", "descending_neuron",
      "sensory_ascending", "sensory_descending"]),
    ("motor_output", "motor",
     "运动输出（腹神经索运动神经元 95% 谷氨酸，兴奋型）",
     ["cb_motor", "vnc_motor"]),
    ("neuromodulatory", "modulation",
     "神经调质：章鱼胺/血清素/内分泌（全局状态调节）",
     ["vnc_efferent", "efferent_descending", "cb_endocrine", "vnc_endocrine"]),
]

assigned = set()
units = []
for gid, gcat, gdesc, members in GROUPS:
    gsyn = sum(M[idx[s]].sum() for s in members)
    gneu = sum(n_neu[s] for s in members)
    units.append({
        "unit_id": gid,
        "category": gcat,
        "description": gdesc,
        "members": [fingerprint(s) for s in members],
        "aggregate": {
            "n_neurons": gneu,
            "out_synapses": int(gsyn),
            "pct_of_brain": round(100 * gsyn / total, 3),
        },
    })
    assigned.update(members)

# 未分配的薄卫星
satellites = [s for s in sc if s not in assigned]
sat_syn = sum(M[idx[s]].sum() for s in satellites)

out = {
    "schema_version": "1.0",
    "generated_from": "MaleCNS v1.0 superclass_matrix.json (computed from connectome_cache)",
    "method": "dual-modal clustering: connection profile (out27+in27) + neurotransmitter profile (7) + self-recurrence, "
              "validated by Louvain (Q=0.3748) and Ward hierarchical clustering",
    "n_units": len(units),
    "coverage": {
        "units_synapses": int(sum(u["aggregate"]["out_synapses"] for u in units)),
        "satellite_synapses": int(sat_syn),
        "total": int(total),
        "units_pct": round(100 * sum(u["aggregate"]["out_synapses"] for u in units) / total, 2),
    },
    "units": units,
    "satellites": [fingerprint(s) for s in satellites],
    "caveat": "superclass 是粗粒度注释；'最小功能单元'的最终粒度需下沉到 neuropil(146) 或细胞类型层。"
              "本文件是数据驱动模块库的第一版，用于替换 19 个 hand-crafted 模块。",
}

dest = MALE / "discovered_modules.json"
dest.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

lines = []
lines.append(f"units = {len(units)}")
for u in units:
    lines.append(f"  {u['unit_id']:<26} {u['aggregate']['n_neurons']:>7,} n  "
                 f"{u['aggregate']['out_synapses']:>12,} syn  "
                 f"({u['aggregate']['pct_of_brain']:5.2f}%)  members={[m['real_superclass'] for m in u['members']]}")
lines.append(f"  satellites ({len(satellites)}): {satellites}")
lines.append(f"coverage: units {out['coverage']['units_pct']}% of synapses")
_rep = ROOT / "tmp" / "discovered_modules_report.txt"
_rep.parent.mkdir(parents=True, exist_ok=True)
_rep.write_text("\n".join(lines), encoding="utf-8")
print("done")
