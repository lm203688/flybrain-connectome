"""
计算完整 27x27 superclass 连接矩阵（加权有向）—— A1 阶段的原料。
用已知事实做自校验：ol_intrinsic->ol_intrinsic 应 == 35,691,182 (28.74%)
"""
import json
import numpy as np
from pathlib import Path

MALE = Path(__file__).resolve().parents[2] / "male_cns"
CACHE = MALE / "connectome_cache"
OUTDIR = MALE

facts = json.loads((MALE / "connectivity_facts.json").read_text(encoding="utf-8"))
sc_list = facts["superclass_list"]
sc_idx = {s: i for i, s in enumerate(sc_list)}
N = len(sc_list)
total_syn = facts["total_synapses"]

ann = json.loads((CACHE / "annotations.json").read_text(encoding="utf-8"))
pre = np.load(CACHE / "pre_s.npy")
post = np.load(CACHE / "post_s.npy")
w = np.load(CACHE / "w_s.npy")

rep = []
rep.append(f"superclasses = {N}")
rep.append(f"ann entries  = {len(ann):,}")
rep.append(f"edges        = {len(pre):,}  dtypes pre={pre.dtype} w={w.dtype}")
max_id = int(max(pre.max(), post.max()))
rep.append(f"max body id  = {max_id:,}")

# --- body -> superclass mapping (searchsorted, no giant LUT) ---
# Body ids go up to ~1.57e9, so a dense LUT would need ~3 GB. Only ~1.7e5 bodies
# are annotated, so map via binary search on the sorted annotated id list.
ann_pairs = sorted((int(b), r["superclass"]) for b, r in ann.items()
                   if r.get("superclass") in sc_idx)
ann_ids = np.array([b for b, _ in ann_pairs], dtype=np.int64)
ann_sc = np.array([sc_idx[s] for _, s in ann_pairs], dtype=np.int16)
n_mapped = len(ann_ids)
rep.append(f"mapped bodies= {n_mapped:,}")

def map_sc(ids: np.ndarray) -> np.ndarray:
    pos = np.clip(np.searchsorted(ann_ids, ids), 0, len(ann_ids) - 1)
    hit = ann_ids[pos] == ids
    return np.where(hit, ann_sc[pos], -1).astype(np.int16)

a = map_sc(pre)
b = map_sc(post)
mask = (a >= 0) & (b >= 0)
a = a[mask].astype(np.int64)
b = b[mask].astype(np.int64)
ww = w[mask].astype(np.float64)
rep.append(f"annotated edges = {len(a):,}")
rep.append(f"annotated syn   = {ww.sum():,.0f}  (expected {total_syn:,})")

# --- full weighted matrix ---
comb = a * N + b
M = np.bincount(comb, weights=ww, minlength=N * N).reshape(N, N)

# --- self check ---
i_ol = sc_idx["ol_intrinsic"]
expect = 35691182
got = M[i_ol, i_ol]
rep.append("")
rep.append(f"SELF-CHECK ol_intrinsic->ol_intrinsic = {got:,.0f} (expect {expect:,}) "
           f"{'PASS' if abs(got-expect) < 1 else 'MISMATCH'}")
rep.append(f"SELF-CHECK matrix total = {M.sum():,.0f} (expect {total_syn:,}) "
           f"{'PASS' if abs(M.sum()-total_syn) < 1 else 'MISMATCH'}")

# --- export ---
pct = M / total_syn * 100.0
mat = {
    "source": "MaleCNS v1.0 neuron subgraph, computed from connectome_cache .npy",
    "superclass_list": sc_list,
    "total_synapses": int(total_syn),
    "matrix_synapses": int(M.sum()),
    "matrix": [[int(M[i, j]) for j in range(N)] for i in range(N)],
    "matrix_pct": [[round(float(pct[i, j]), 6) for j in range(N)] for i in range(N)],
    "self_check": {
        "ol_intrinsic_self": int(M[i_ol, i_ol]),
        "expected": expect,
        "total_ok": bool(abs(M.sum() - total_syn) < 1),
    },
}
(OUTDIR / "superclass_matrix.json").write_text(
    json.dumps(mat, ensure_ascii=False, indent=1), encoding="utf-8")
rep.append("")
rep.append("wrote male_cns/superclass_matrix.json")

# --- 稀疏度 ---
nz = int((M > 0).sum())
rep.append(f"non-zero cells = {nz} / {N*N} = {100*nz/(N*N):.1f}%  (denseness)")
strong = int((pct > 0.1).sum())
rep.append(f"cells > 0.1%   = {strong}")

# --- 每个 superclass 的主导出边 ---
rep.append("")
rep.append("-- 每个 superclass 的主导去向 (出边 top1) --")
for i, s in enumerate(sc_list):
    row = M[i]
    if row.sum() == 0:
        continue
    j = int(np.argmax(row))
    rep.append(f"  {s:<24} -> {sc_list[j]:<24} {row[j]:>12,.0f} ({pct[i,j]:.2f}%) "
               f"| out_total={row.sum():>12,.0f}")

rep_path = Path(__file__).resolve().parents[2] / "tmp" / "matrix_report.txt"
rep_path.parent.mkdir(parents=True, exist_ok=True)
rep_path.write_text("\n".join(rep), encoding="utf-8")
print("done")
