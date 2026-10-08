"""D2 / D3 / D4 -- the north-star experiment (fast local decision).

North-star, as stated: a decision made in very few steps by a local circuit,
without global routing -- "subconscious / dreaming" judgement. D1 (the
definition) lives in ``flybrain-connectome-mcp/fast_decision.py``; this file is
the measurement.

WHY THE TASK IS WHAT IT IS
--------------------------
The first version of this file used a delay-line reservoir task. It came back
at chance level (0.45-0.65) for every topology, while a random Gaussian
reservoir of the same size scored 0.73 -- i.e. the generated motif wiring is a
bad reservoir, and "everything is 0.5" is a measurement of substrate quality,
not of the north-star question. So the primary measurement below is a
**propagation** measurement, which the wiring actually determines:

    a bit `u` enters the afferent module at step 1; each hop applies the
    wiring then corrupts the signal with channel noise `p`; a linear readout
    over a candidate set R must classify `u`.

    * the afferent module's own readout starts at step 1 (no routing needed)
    * a remote module's readout can only start once the signal has travelled
      the wiring distance from the afferent module to it
    * the global readout contains the afferent module, so it starts at step 1

`steps_to_quality` is then a genuine step budget, and the headline number is
the **routing tax**: how many steps a remote module needs before a local
afferent module can already decide. That is the north-star claim made
falsifiable -- and it can come back negative, which is printed as such.

A secondary reservoir sweep is kept because it answers a different question
("does the generated wiring support recurrent computation at all?") and the
answer to that one is already visible: it mostly does not.

Run:
    python fast_decision_experiment.py --quick     # 3 topologies, few trials
    python fast_decision_experiment.py             # full sweep
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
MCP = HERE.parent.parent.parent / "flybrain-connectome-mcp"
ORG_DIR = MCP / "generated_organisms" / "swarmlabs"
OUT = HERE / "fast_decision_results.json"
REPORT = HERE / "FAST_DECISION_REPORT.md"

sys.path.insert(0, str(MCP))
sys.path.insert(0, str(HERE))

import importlib.util as _ilu
_cd_spec = _ilu.spec_from_file_location("_cd", HERE / "cell_densify_experiment.py")
_cd = _ilu.module_from_spec(_cd_spec)
sys.modules["_cd"] = _cd
_cd_spec.loader.exec_module(_cd)

from fast_decision import (  # noqa: E402
    ARM_AFFERENT, ARM_GLOBAL, ARM_REMOTE, DecisionSpec, fast_decision_record,
    local_fingerprint, steps_to_quality, time_quality_curve,
)
from topology_profile import profile as _topo_profile  # noqa: E402

# --- propagation regime ------------------------------------------------- #
NODE_CAP = 40
TARGET_DENSITY = 0.20
FILL_MODE = "intra_ring"
LEAK = 0.90            # state retention per step
NOISE_P = 0.12         # per-neuron bit-flip probability per step
N_TRIALS = 48          # classification trials per step
K_STEPS = 8            # step budget scanned
HORIZON = 4            # "fast" = within this many steps
THRESHOLD = 0.80       # fixed quality bar

# --- reservoir regime (secondary) --------------------------------------- #
RHO = 1.0
RES_N_TRIALS = 12
RES_N_SEEDS = 8
RES_K = 6
RES_DELAY = 1


# --------------------------------------------------------------------------- #
def _load_targets(quick: bool) -> list[tuple[Path, str]]:
    names = ["bp_predictive_coding.swarm.json", "modular_isolation.swarm.json",
             "robust_redundant.swarm.json"]
    if not quick:
        names += ["bp_hierarchical.swarm.json", "decoupled_hierarchical.swarm.json",
                  "bench_attention_working_combo.swarm.json",
                  "sample_10module.swarm.json"]
    out = []
    for n in names:
        p = ORG_DIR / n
        if p.exists():
            out.append((p, n.replace(".swarm.json", "")))
    return out


def _build(path: Path) -> tuple[np.ndarray, np.ndarray, int]:
    """(W, module_of_node, n_modules). Substrate reused from cell_densify."""
    agents, edges, _label = _cd.load_org(path)
    nodes, _ = _cd.pick_nodes(agents, cap=NODE_CAP)
    if len(nodes) < 6:
        raise ValueError("too few nodes: %d" % len(nodes))
    mods, reps, sizes = _cd.node_meta(nodes)
    n_modules = len(sizes)
    W = _cd.motif_layer(nodes, edges)
    d_max = _cd.max_intra_density(len(nodes), sizes, n_modules)
    frac = min(1.0, TARGET_DENSITY / max(d_max, 1e-9))
    W, _K, _added, _ = _cd.densify(nodes, edges, frac, FILL_MODE, seed=7,
                                   keep_motif=True)
    return W, mods.astype(int), n_modules


def _local_spectral(W: np.ndarray, mods: np.ndarray) -> dict[int, float]:
    """Spectral radius of each module's induced subgraph (|weight|)."""
    out = {}
    for m in np.unique(mods):
        idx = np.where(mods == m)[0]
        if len(idx) < 2:
            out[int(m)] = 0.0
            continue
        s = np.linalg.svd(np.abs(W[np.ix_(idx, idx)]), compute_uv=False)
        out[int(m)] = float(s[0]) if len(s) else 0.0
    return out


def _wire_distance(W: np.ndarray, src: np.ndarray, dst: np.ndarray) -> int | None:
    """Shortest wiring distance (in hops) from any src node to any dst node."""
    n = W.shape[0]
    nbrs = {i: set(np.nonzero(W[:, i])[0].tolist()) for i in range(n)}
    seen = set(src.tolist())
    for _ in range(n):
        if seen & set(dst.tolist()):
            return 0
        nxt = set()
        for i in seen:
            nxt |= nbrs[i]
        nxt -= seen
        if not nxt:
            return None
        seen |= nxt
    return None


# --------------------------------------------------------------------------- #
# D3 primary -- propagation: steps to decide, per candidate readout set
# --------------------------------------------------------------------------- #
def _propagate(W: np.ndarray, aff: np.ndarray, u: float, k: int, rng) -> np.ndarray:
    """x[t] for t = 1..k. The bit `u` enters the afferent module at step 1."""
    n = W.shape[0]
    X = []
    x = np.zeros(n)
    for t in range(k):
        received = W @ x
        if t == 0:
            received[aff] += u
        # channel noise: flip the sign of a neuron's received signal
        flip = rng.random(n) < NOISE_P
        received = np.where(flip, -received, received)
        x = LEAK * np.tanh(received)
        X.append(x.copy())
    return np.array(X)


def _curve_propagate(W: np.ndarray, neurons: np.ndarray, aff: np.ndarray,
                     k: int, n_trials: int) -> dict[int, float]:
    """Accuracy of a learned linear readout over `neurons`, per step."""
    acc: dict[int, float] = {}
    n = W.shape[0]
    n_train = n_trials // 2
    n_eval = n_trials - n_train
    for s in range(1, k + 1):
        tr_X, tr_y, te = [], [], []
        rng = np.random.default_rng(2024)
        for _trial in range(n_trials):
            u = 1.0 if (_trial % 2 == 0) else -1.0
            X = _propagate(W, aff, u, k, rng)
            v = X[s - 1][neurons]
            if _trial < n_train:
                tr_X.append(v)
                tr_y.append(int(u > 0))
            else:
                te.append((v, int(u > 0)))
        if not tr_X or not te:
            continue
        Xa = np.array(tr_X)
        y = np.array(tr_y)
        if len(np.unique(y)) < 2:
            continue
        Xc = np.concatenate([Xa, np.ones((len(Xa), 1))], axis=1)
        w, *_ = np.linalg.lstsq(Xc, y, rcond=None)
        correct = 0
        for v, ytrue in te:
            pred = float(np.dot(v, w[:-1]) + w[-1])
            if (pred >= 0.5) == bool(ytrue):
                correct += 1
        acc[s] = correct / len(te)
    return acc


# --------------------------------------------------------------------------- #
# D3 secondary -- reservoir sweep (delay-line task)
# --------------------------------------------------------------------------- #
def _normalize_rho(W: np.ndarray, rho: float) -> np.ndarray:
    s = np.linalg.svd(W, compute_uv=False)
    if len(s) == 0 or s[0] < 1e-12:
        return W
    return W / s[0] * min(rho, 1.0)


def _curve_reservoir(W: np.ndarray, neurons: np.ndarray, aff: np.ndarray,
                     delay: int, n_seeds: int, k: int, n_trials: int
                     ) -> dict[int, float]:
    acc: dict[int, float] = {}
    n = W.shape[0]
    n_train = n_trials // 2
    for s in range(1, k + 1):
        if s <= delay:
            continue
        tr_X, tr_y, te = [], [], []
        for seed in range(n_seeds):
            rng = np.random.default_rng(1000 + 17 * seed)
            Win = np.zeros((n, 1))
            Win[aff, 0] = rng.normal(0.0, 1.0, size=len(aff))
            bias = rng.normal(0.0, 0.3, size=n)
            for _trial in range(n_trials):
                seq = (rng.random(size=s) > 0.5) * 2 - 1
                x = np.zeros(n)
                for t in range(s):
                    x = 0.95 * np.tanh(W @ x + Win[:, 0] * seq[t] + bias)
                y = int(seq[s - 1 - delay] > 0)
                v = x[neurons]
                if _trial < n_train:
                    tr_X.append(v)
                    tr_y.append(y)
                else:
                    te.append((v, y))
        if not tr_X or not te:
            continue
        Xa = np.array(tr_X)
        y = np.array(tr_y)
        if len(np.unique(y)) < 2:
            continue
        Xc = np.concatenate([Xa, np.ones((len(Xa), 1))], axis=1)
        w, *_ = np.linalg.lstsq(Xc, y, rcond=None)
        correct = sum(1 for v, yt in te
                      if (float(np.dot(v, w[:-1]) + w[-1]) >= 0.5) == bool(yt))
        acc[s] = correct / len(te)
    return acc


# --------------------------------------------------------------------------- #
def _spearman(xs, ys) -> float | None:
    if len(xs) < 3 or len(set(xs)) < 2:
        return None
    def rank(v):
        order = np.argsort(np.argsort(np.asarray(v, dtype=float)))
        return (order + 1.0) / len(v)
    rx, ry = rank(xs), rank(ys)
    return float(np.corrcoef(rx, ry)[0, 1])


def run_experiment(quick: bool) -> dict:
    targets = _load_targets(quick)
    k_steps = 4 if quick else K_STEPS
    n_trials = 12 if quick else N_TRIALS
    horizon = 2 if quick else HORIZON
    records, fingerprints, rows = [], [], []
    for path, label in targets:
        try:
            W, mods, n_modules = _build(path)
        except Exception as exc:  # noqa: BLE001
            print("  [skip] %s: %r" % (label, exc))
            continue
        aff_m = int(np.unique(mods)[0])
        rem_m = int([m for m in np.unique(mods) if m != aff_m][0]) \
            if n_modules > 1 else aff_m
        aff = np.where(mods == aff_m)[0]
        rem = np.where(mods == rem_m)[0]
        alln = np.arange(W.shape[0])
        fps = _local_spectral(W, mods)
        dist = _wire_distance(W, aff, rem)

        fp = local_fingerprint(_topo_profile({"nodes":
            [{"id": "n%d" % i, "module": int(mods[i])} for i in range(W.shape[0])],
            "edges": [{"from": "n%d" % i, "to": "n%d" % j, "weight": float(W[i, j])}
                      for i in range(W.shape[0]) for j in range(W.shape[0])
                      if W[i, j] != 0.0]}))
        fp["local_spectral_by_module"] = {str(k): round(v, 4)
                                          for k, v in fps.items()}
        fp["afferent_module"] = aff_m
        fp["remote_module"] = rem_m
        fp["wire_distance_afferent_to_remote"] = dist
        fingerprints.append({"topology": label, "fingerprint": fp})

        sp_aff = DecisionSpec(arm=ARM_AFFERENT, horizon=horizon,
                              quality_threshold=THRESHOLD,
                              require_local_readout=True, neurons=aff.tolist())
        sp_rem = DecisionSpec(arm=ARM_REMOTE, horizon=horizon,
                              quality_threshold=THRESHOLD,
                              require_local_readout=True, neurons=rem.tolist())
        sp_glob = DecisionSpec(arm=ARM_GLOBAL, horizon=horizon,
                               quality_threshold=THRESHOLD,
                               require_local_readout=False)

        ca = _curve_propagate(W, aff, aff, k_steps, n_trials)
        cr = _curve_propagate(W, rem, aff, k_steps, n_trials)
        cg = _curve_propagate(W, alln, aff, k_steps, n_trials)
        s_a, s_r, s_g = (steps_to_quality(ca, THRESHOLD),
                         steps_to_quality(cr, THRESHOLD),
                         steps_to_quality(cg, THRESHOLD))

        # D4: an offline ("sleep") phase shifts the starting state. Same wiring,
        # same input, same noise -- only the pre-integration differs.
        cs = _curve_propagate_sleep(W, aff, aff, k_steps, n_trials)
        s_sl = steps_to_quality(cs, THRESHOLD)

        rec = fast_decision_record(
            sp_aff, ca, fp, cr,
            extra={
                "topology": label,
                "regime": "propagation",
                "n_nodes": int(W.shape[0]),
                "n_modules": int(n_modules),
                "afferent_module_size": int(len(aff)),
                "remote_module_size": int(len(rem)),
                "wire_distance_afferent_to_remote": dist,
                "channel_noise_p": NOISE_P,
                "leak": LEAK,
                "n_trials": n_trials,
                "global_reference": time_quality_curve(sp_glob, cg),
                "routing_tax_steps": (None if s_a is None or s_r is None
                                      else s_r - s_a),
                "sleep_control": {
                    "sleep_steps": SLEEP_STEPS,
                    "curve": {str(kk): round(vv, 4) for kk, vv in sorted(cs.items())},
                    "steps_to_quality": s_sl,
                    "wake_steps_to_quality": s_a,
                    "delta_steps": (None if s_sl is None or s_a is None
                                    else s_sl - s_a),
                },
                "reservoir_sweep": {
                    "regime": "delay_line_reservoir",
                    "delay": RES_DELAY,
                    "rho": RHO,
                    "afferent": _curve_reservoir(_normalize_rho(W, RHO), aff, aff,
                                                 RES_DELAY, RES_N_SEEDS, RES_K,
                                                 RES_N_TRIALS),
                    "global": _curve_reservoir(_normalize_rho(W, RHO), alln, aff,
                                               RES_DELAY, RES_N_SEEDS, RES_K,
                                               RES_N_TRIALS),
                },
            })
        records.append(rec)
        for arm, curve, st in (("local_afferent", ca, s_a),
                               ("local_remote", cr, s_r), ("global", cg, s_g)):
            row = {"topology": label, "arm": arm, "steps_to_quality": st,
                   "afferent_spectral": round(fps.get(aff_m, 0.0), 4),
                   "remote_spectral": round(fps.get(rem_m, 0.0), 4),
                   "wire_distance": dist}
            for s, v in sorted(curve.items()):
                row["acc_s%d" % s] = round(v, 4)
            rows.append(row)
    return {"targets": len(targets), "records": records, "fingerprints": fingerprints,
            "per_step_rows": rows, "k_steps": k_steps, "n_trials": n_trials,
            "horizon": horizon, "threshold": THRESHOLD,
            "channel_noise_p": NOISE_P, "leak": LEAK}


SLEEP_STEPS = 24


def _curve_propagate_sleep(W, neurons, aff, k, n_trials):
    """Propagation variant with an offline pre-integration phase first."""
    acc: dict[int, float] = {}
    n = W.shape[0]
    n_train = n_trials // 2
    for s in range(1, k + 1):
        tr_X, tr_y, te = [], [], []
        rng = np.random.default_rng(2024)
        for _trial in range(n_trials):
            u = 1.0 if (_trial % 2 == 0) else -1.0
            x = np.zeros(n)
            for _ in range(SLEEP_STEPS):          # offline: integrate with no input
                x = LEAK * np.tanh(rng.normal(0.0, 0.05, size=n))
            X = []
            for t in range(k):
                received = W @ x
                if t == 0:
                    received[aff] += u
                flip = rng.random(n) < NOISE_P
                received = np.where(flip, -received, received)
                x = LEAK * np.tanh(received)
                X.append(x.copy())
            v = X[s - 1][neurons]
            if _trial < n_train:
                tr_X.append(v)
                tr_y.append(int(u > 0))
            else:
                te.append((v, int(u > 0)))
        if not tr_X or not te:
            continue
        Xa = np.array(tr_X)
        y = np.array(tr_y)
        if len(np.unique(y)) < 2:
            continue
        Xc = np.concatenate([Xa, np.ones((len(Xa), 1))], axis=1)
        w, *_ = np.linalg.lstsq(Xc, y, rcond=None)
        correct = sum(1 for v, yt in te
                      if (float(np.dot(v, w[:-1]) + w[-1]) >= 0.5) == bool(yt))
        acc[s] = correct / len(te)
    return acc


def _summarise(exp: dict) -> dict:
    recs = exp["records"]
    out = {"n_records": len(recs)}
    if not recs:
        return out
    aff_ok = [r for r in recs if r["result"]["steps_to_quality"] is not None]
    out["local_afferent_reaches_threshold"] = len(aff_ok)
    out["local_afferent_within_horizon"] = sum(
        1 for r in recs if r["result"]["decides_within_horizon"])
    out["local_afferent_1_step"] = sum(
        1 for r in recs if r["result"]["steps_to_quality"] == 1)
    rem = [r for r in recs if r["result"]["baseline_steps_to_quality"] is not None]
    out["local_remote_reaches_threshold"] = len(rem)
    out["local_remote_within_horizon"] = sum(
        1 for r in rem if r["result"]["advantage_steps"] is not None)
    tax = [r["routing_tax_steps"] for r in recs if r["routing_tax_steps"] is not None]
    out["routing_tax_measured"] = len(tax)
    out["routing_tax_mean_steps"] = round(float(np.mean(tax)), 3) if tax else None
    out["routing_tax_min_steps"] = int(min(tax)) if tax else None
    out["routing_tax_max_steps"] = int(max(tax)) if tax else None
    glob = [r["global_reference"] for r in recs]
    out["global_never_reaches"] = sum(
        1 for g in glob if g["steps_to_quality"] is None)
    sl = [r["sleep_control"] for r in recs]
    d = [x["delta_steps"] for x in sl if x["delta_steps"] is not None]
    out["sleep_measured_pairs"] = len(d)
    out["sleep_shortened_budget"] = sum(1 for x in d if x < 0)
    out["sleep_lengthened_budget"] = sum(1 for x in d if x > 0)
    out["sleep_no_change"] = sum(1 for x in d if x == 0)
    out["sleep_mean_delta_steps"] = round(float(np.mean(d)), 3) if d else None
    # D2: does the afferent module's local spectral radius predict the budget?
    xs, ys = [], []
    for r in recs:
        st = r["result"].get("steps_to_quality")
        fp = r.get("structural_fingerprint") or {}
        loc = fp.get("local_spectral_by_module") or {}
        am = fp.get("afferent_module")
        if st is not None and am is not None and str(am) in loc:
            xs.append(loc[str(am)])
            ys.append(st)
    out["d2_pairs"] = len(xs)
    sp = _spearman(xs, ys)
    out["d2_afferent_spectral_vs_steps_spearman"] = round(sp, 3) if sp else None
    # D2b: does wiring distance predict the remote module's budget?
    xs2, ys2 = [], []
    for r in recs:
        rr = r["result"].get("baseline_steps_to_quality")
        dd = r.get("wire_distance_afferent_to_remote")
        if rr is not None and dd is not None:
            xs2.append(dd)
            ys2.append(rr)
    out["d2b_pairs"] = len(xs2)
    sp2 = _spearman(xs2, ys2)
    out["d2b_distance_vs_remote_steps_spearman"] = round(sp2, 3) if sp2 else None
    return out


def _write_report(exp: dict, s: dict, t0: float) -> None:
    L = []
    A = L.append
    A("# 快速局部判断实验（北极星 D2 / D3 / D4）")
    A("")
    A("运行：%d 拓扑 × %d 试验 / 步，步预算 k=%d，质量阈值 %.2f，信道噪声 %.2f，"
      "泄漏 %.2f。耗时 %.1fs。"
      % (exp["targets"], exp["n_trials"], exp["k_steps"], exp["threshold"],
         exp["channel_noise_p"], exp["leak"], time.time() - t0))
    A("")
    A("## 定义（D1 · `flybrain-connectome-mcp/fast_decision.py`）")
    A("")
    A("比特 `u` 在第 1 步进入 afferent 模块；每步先按接线传播、再按噪声翻转；")
    A("`steps_to_quality` = 让某个读出集合上的线性分类器达到 %.2f 准确率所需的"
      "**最少步数**。比较的是**固定质量下的时间**，这是此前所有被撤回的结论")
    A("（计算力 0/7、能耗 0/24、涌现撤回）都没测过的轴——它们比的都是固定时间预算下的质量。")
    A("")
    A("## D3 结果")
    A("")
    A("| 指标 | 值 |")
    A("|---|---|")
    for k in ("n_records", "local_afferent_reaches_threshold",
              "local_afferent_1_step", "local_afferent_within_horizon",
              "local_remote_reaches_threshold", "global_never_reaches",
              "routing_tax_measured", "routing_tax_mean_steps",
              "routing_tax_min_steps", "routing_tax_max_steps"):
        A("| %s | %s |" % (k, s.get(k)))
    A("")
    A("## D2 结构预测")
    A("")
    A("- afferent 模块局部谱半径 vs 决策步数（Spearman）：**%s**（n=%s）"
      % (s.get("d2_afferent_spectral_vs_steps_spearman"), s.get("d2_pairs")))
    A("- afferent→remote 接线距离 vs remote 决策步数（Spearman）：**%s**（n=%s）"
      % (s.get("d2b_distance_vs_remote_steps_spearman"), s.get("d2b_pairs")))
    A("")
    A("## D4 离线整合（「做梦」代理）")
    A("")
    A("| 指标 | 值 |")
    A("|---|---|")
    for k in ("sleep_measured_pairs", "sleep_shortened_budget",
              "sleep_lengthened_budget", "sleep_no_change",
              "sleep_mean_delta_steps"):
        A("| %s | %s |" % (k, s.get(k)))
    A("")
    A("## 诚实边界")
    A("")
    A("1. **步 = 积分步，不是毫秒**。本框架没有时钟，也没有频率标定。")
    A("2. 读出是**在线**的（只用 1..s 步的状态），无未来回看。")
    A("3. 噪声是**信道翻转**，不是生物学噪声模型；LEAK/tanh 是工程折衷不是神经生理。")
    A("4. 该集合未达阈值 → `steps_to_quality = null`，显式打印，不静默丢弃。")
    A("5. 离线整合是「预积分」，不是记忆巩固；无帮助是**结果**，不是缺陷。")
    A("6. 本实验测的是**接线决定的路由代价**，不是认知主张。")
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args(argv)
    t0 = time.time()
    if not ORG_DIR.exists():
        print("FATAL: no topology dir %s" % ORG_DIR)
        return 1
    exp = run_experiment(args.quick)
    exp["summary"] = _summarise(exp)
    exp["elapsed_sec"] = round(time.time() - t0, 1)
    exp["not_measured"] = ["energy", "biological_validity"]
    exp["caveat"] = ("steps are recurrent integration steps, not time; the readout "
                     "is online (no future look-ahead); channel noise is a bit-flip "
                     "proxy, not a biological noise model; the offline phase is "
                     "pre-integration, not memory consolidation.")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(exp, indent=2, ensure_ascii=False, default=str),
                   encoding="utf-8")
    s = exp["summary"]
    print("fast-decision: %d topology, %d trials/step, k=%d, thr=%.2f (%.1fs)"
          % (exp["targets"], exp["n_trials"], exp["k_steps"],
             exp["threshold"], exp["elapsed_sec"]))
    print("  afferent reaches threshold  %s" % s.get("local_afferent_reaches_threshold"))
    print("  afferent decides in 1 step  %s" % s.get("local_afferent_1_step"))
    print("  afferent within horizon     %s" % s.get("local_afferent_within_horizon"))
    print("  remote reaches threshold    %s" % s.get("local_remote_reaches_threshold"))
    print("  global never reaches        %s" % s.get("global_never_reaches"))
    print("  routing tax steps: mean %s (min %s, max %s, n=%s)"
          % (s.get("routing_tax_mean_steps"), s.get("routing_tax_min_steps"),
             s.get("routing_tax_max_steps"), s.get("routing_tax_measured")))
    print("  D2  aff_spectral vs steps   %s (n=%s)"
          % (s.get("d2_afferent_spectral_vs_steps_spearman"), s.get("d2_pairs")))
    print("  D2b distance vs remote step %s (n=%s)"
          % (s.get("d2b_distance_vs_remote_steps_spearman"), s.get("d2b_pairs")))
    print("  D4 sleep: shortened %s / lengthened %s / flat %s / mean %+s"
          % (s.get("sleep_shortened_budget"), s.get("sleep_lengthened_budget"),
             s.get("sleep_no_change"), s.get("sleep_mean_delta_steps")))
    _write_report(exp, s, t0)
    print("  wrote %s, %s" % (OUT.name, REPORT.name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
