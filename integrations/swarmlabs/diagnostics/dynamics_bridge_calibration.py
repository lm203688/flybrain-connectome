"""结构 × 动力学桥接 —— 标定查表（T4.2 #1）。

路线图要的是「把 ρ、反馈边比例与 ESN 记忆容量/收敛速度的实测关系固化成查表」。
本脚本只做能被测的那一半，并把不能做的那一半显式写死，理由如下。

可测的一半 —— ρ → 记忆容量
  固定 N 的教科书储备池，谱半径 ρ 是唯一的关键动力学参数（见
  dyn_calibration_probe.py 复核 A：原实现的列归一化把 ρ 抹掉了，这是当年
  「dyn_score 无判别力」初判的根因之一）。Bernoulli 延迟线任务给出
  R²(ρ, delay)，跨 ρ 从 0.000 平滑升到 0.856，是真实动态范围不是悬崖。
  这个关系值得固化：它是一张**仪器标定曲线**，告诉后续工作 ρ「应该」带来什么。

不可测的一半 —— 反馈边比例 / 拓扑形状 → 动力学
  复核 C（匹配非零元素总数 K 的决定性对照）：0/7 拓扑显著优于随机，
  差值 0.018 内，全在噪声里。也就是说在本库**实际产出的模块代表层**
  （密度 0.002–0.023）拓扑形状不预测动力学。给反馈边比例建一张查表
  等于把一条已证伪的关系固化成看似有用的产物 —— 不做。
  真正可用的杠杆是**密度**，不是形状。

所以本查表的定位是「标尺」而非「预言机」：拿 cell 级密化版本来对表，
看它落在标定曲线的哪一段，而不是用它预测模块代表层的收益。

用法：
  python dynamics_bridge_calibration.py            # 重算并写 DYNAMICS_BRIDGE_LOOKUP.json
  python dynamics_bridge_calibration.py --check    # 只读表校验结构，不落盘
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from dyn_calibration_probe import r2_score, random_W  # noqa: E402

# r2_score 末尾的 max(0.0, ...) 截断让 R² 在 0 附近只差数值噪声，
# 那不是动力学测量。低于此值的相邻对不参与单调性断言。
FLOOR_R2 = 0.005

OUT = HERE / "DYNAMICS_BRIDGE_LOOKUP.json"

# 网格取值刻意贴着复核 A 已验证有动态范围的区间，不外推到未见过的地方。
N = 150
SEEDS = 20
SEED_BASE = 20261009
RHO_GRID = [0.50, 0.60, 0.70, 0.80, 0.90, 0.95, 1.00]
DELAY_GRID = [1, 3, 5, 8, 12]


def mean_capacity(W, delay, rho, n_seeds=SEEDS, seed_base=SEED_BASE):
    """多种子均值 + 标准差。单种子 std 可达 0.19–0.23（复核 B），
    必须平均才把拓扑效应和输入序列运气分开。"""
    scores = [r2_score(W, delay, rho, seed=seed_base + s) for s in range(n_seeds)]
    a = np.array(scores, dtype=float)
    return float(a.mean()), float(a.std())


def build(n_seeds=SEEDS):
    W = random_W(N, seed=SEED_BASE)
    grid = {}
    for rho in RHO_GRID:
        for d in DELAY_GRID:
            m, s = mean_capacity(W, d, rho, n_seeds=n_seeds)
            grid["rho=%.2f|delay=%d" % (rho, d)] = {"mean_r2": m, "std_r2": s}

    # 单调性判据用**配对标准误**，不用全局 std 中位数。后者会把拐点处的大噪声
    # （0.19-0.23）摊薄到平坦段，使平坦段容忍带过窄而假红；反过来在拐点段又太宽。
    # 两个相邻 ρ 各自独立取种子，均值差的标准误 = hypot(se_a, se_b)，
    # se = std/sqrt(n_seeds)。
    #
    # 另外，r2_score 末尾的 max(0.0, ...) 截断让 R² 在 0 附近产生数值伪影差值，
    # 那不是动力学测量。低于 FLOOR_R2 的相邻对不参与单调性断言，但必须登记
    # 出来 —— 静默跳过等于隐藏了曲线在哪一段不可测。
    se = lambda s: s / np.sqrt(n_seeds)
    monotone = {}
    for d in DELAY_GRID:
        cells = [(r, grid["rho=%.2f|delay=%d" % (r, d)]) for r in RHO_GRID]
        means = [c[1]["mean_r2"] for c in cells]
        drops, tols, skipped = [], [], []
        for i in range(len(cells) - 1):
            (ra, ga), (rb, gb) = cells[i], cells[i + 1]
            if max(ga["mean_r2"], gb["mean_r2"]) < FLOOR_R2:
                skipped.append("rho %.2f->%.2f (below R2 floor %.3f)"
                               % (ra, rb, FLOOR_R2))
                continue
            drops.append(means[i] - means[i + 1])
            tols.append(float(2.0 * np.hypot(se(ga["std_r2"]), se(gb["std_r2"]))))
        tol = max(tols) if tols else None
        monotone["delay=%d" % d] = {
            "means": means,
            "measured_drops": drops,
            "max_drop": max(drops) if drops else None,
            "tolerance": round(tol, 6) if tol is not None else None,
            "pairs_below_floor": skipped,
            "assertable": bool(drops),
            # 没有可测段时不判定（None），区别于 True/False —— 不可判定不是通过
            "monotone_within_tolerance": (bool(drops) and max(drops) <= tol) if drops else None,
        }

    # 单比特线性读出要预测 delay 步前，需要区分 2^d 级状态；过了某条 delay
    # R² 直接塌到 0（能力悬崖）。实测 cliff 比 dyn_calibration_probe.py 文档写的
    # 「delay=20-40 才过悬崖」靠前得多 —— 本任务的悬崖在 delay=5 与 8 之间。
    # 塌零列不是「不可判定的空段」，是一条实测量级为零的结论，必须单独登记，
    # 否则单调性断言会静默跳过整列、读者以为那里还没测。
    assertable_delays = sorted(int(d.split("=")[1])
                               for d, m in monotone.items()
                               if m["monotone_within_tolerance"] is not None)
    measurable_delays = [d for d in DELAY_GRID if d in assertable_delays]
    collapsed_delays = [d for d in DELAY_GRID if d not in assertable_delays]
    last_measurable = max(measurable_delays) if measurable_delays else None
    cliff = {"status": "none within grid", "from_delay": None, "to_delay": None}
    if last_measurable is not None and collapsed_delays:
        cliff = {"status": "measured",
                 "from_delay": last_measurable,
                 "to_delay": min(collapsed_delays),
                 "note": ("Capacity collapses to ~0 between delay=%d and delay=%d for a "
                          "single-bit linear readout at N=%d. Longer delays need ~2^d "
                          "distinguishable states, so this is a readout/task limit, not a "
                          "reservoir-size limit." % (last_measurable, min(collapsed_delays), N))}

    knee = [{"rho": r, "delay": d, "mean_r2": grid["rho=%.2f|delay=%d" % (r, d)]["mean_r2"]}
            for r in RHO_GRID for d in DELAY_GRID
            if 0.1 <= grid["rho=%.2f|delay=%d" % (r, d)]["mean_r2"] <= 0.9]

    return {
        "artifact": "dynamics_bridge_lookup",
        "version": 1,
        "purpose": ("Instrument calibration curve for reservoir spectral radius, NOT a "
                    "prediction of dynamics for the module-representative topologies "
                    "this library emits."),
        "reservoir": {"kind": "textbook random-Gaussian", "n_units": N,
                      "task": "Bernoulli delay line (single +-1 bit)",
                      "seeds": n_seeds, "seed_base": SEED_BASE,
                      "w_seed": SEED_BASE},
        "grid": {"rho": RHO_GRID, "delay": DELAY_GRID},
        "rho_calibration": grid,
        "monotonicity": monotone,
        "capacity_cliff": cliff,
        "measurable_delays": measurable_delays,
        "collapsed_delays": collapsed_delays,
        "r2_floor": FLOOR_R2,
        "per_cell_seed_std": {
            "median": round(float(np.median([g["std_r2"] for g in grid.values()])), 4),
            "max": round(float(np.max([g["std_r2"] for g in grid.values()])), 4),
            "note": ("std across seeds within one (rho,delay) cell: large near the knee "
                     "(~0.2), ~0 where the clamp pins R2 at 0. Monotonicity tolerance is "
                     "derived per adjacent pair from the cell stds, NOT from this median "
                     "-- a single global band is too tight on the flat part and too loose "
                     "on the knee."),
        },
        "knee_region": knee,
        "topology_shape_axis": {
            "status": "REFUTED, not tabulated",
            "claim": "feedback edge fraction / motif shape predicts dynamics",
            "evidence": ("Matched-K control in dyn_calibration_probe.py: after matching "
                         "total non-zero elements, 0/7 topologies significantly beat "
                         "random; differences 0.001-0.018, inside seed noise."),
            "why_no_table": ("Tabulating a relationship that has been measured to be "
                             "null would freeze a refuted claim into a lookup that "
                             "looks useful. The table exists only for the axis that "
                             "is actually measured."),
            "source": "integrations/swarmlabs/diagnostics/dyn_calibration_probe.py (probe C)",
        },
        "density_boundary": {
            "module_representative_layer": {"density_range": [0.002, 0.023],
                                            "finding": "structurally insufficient to carry temporal dynamics"},
            "real_lever": "density, not shape",
        },
        "not_predicted_by": [
            "feedback_edge_frac", "motif_counts", "reciprocity",
            "modularity_q", "topology_signature",
        ],
        "how_to_use": ("Compare a densified (cell-level) build's measured R² against "
                       "this curve to locate it on the known rho->capacity axis. Do not "
                       "use it to rank module-representative topologies: that ranking is "
                       "the null result recorded above."),
        "not_measured": ["energy", "task_performance", "biological_validity"],
    }


def check(data):
    """结构性断言（值本身带随机性，断言形状与定性不变量，不断言精确数值）。"""
    errs = []
    g = data.get("rho_calibration", {})
    if len(g) != len(RHO_GRID) * len(DELAY_GRID):
        errs.append("grid has %d cells, expected %d" % (len(g), len(RHO_GRID) * len(DELAY_GRID)))
    for k, v in g.items():
        if not (0.0 <= v.get("mean_r2", -1) <= 1.0):
            errs.append("%s mean_r2 out of [0,1]: %r" % (k, v.get("mean_r2")))
        if not (0.0 <= v.get("std_r2", -1)):
            errs.append("%s std_r2 negative: %r" % (k, v.get("std_r2")))
    for d, m in data.get("monotonicity", {}).items():
        ok = m.get("monotone_within_tolerance")
        if ok is False:
            errs.append("%s not monotone in rho: drop %s > tol %s"
                        % (d, m.get("max_drop"), m.get("tolerance")))
        if ok is None and not m.get("pairs_below_floor"):
            errs.append("%s not assertable yet reports no floor exclusion" % d)
    cd = data.get("collapsed_delays") or []
    if cd and data.get("capacity_cliff", {}).get("status") != "measured":
        errs.append("collapsed delay columns %r exist but capacity_cliff status=%r"
                    % (cd, data.get("capacity_cliff", {}).get("status")))
    if not data.get("measurable_delays"):
        errs.append("no measurable delay column -- lookup would calibrate nothing")
    if data.get("r2_floor") is None:
        errs.append("r2_floor missing (clamp-excluded pairs must be declared)")
    if not data.get("per_cell_seed_std", {}).get("note"):
        errs.append("per_cell_seed_std note missing (tolerance provenance)")
    tsa = data.get("topology_shape_axis", {})
    if tsa.get("status") != "REFUTED, not tabulated":
        errs.append("topology_shape_axis must stay REFUTED (no silent upgrade to a table)")
    if tsa.get("evidence"):
        if "0/7" not in tsa["evidence"]:
            errs.append("topology_shape_axis evidence lost the 0/7 decisive figure")
    if not data.get("not_predicted_by"):
        errs.append("not_predicted_by empty (silence would read as 'nothing tested')")
    if data.get("reservoir", {}).get("seeds", 0) < 5:
        errs.append("seeds=%r too few to separate topology from input luck"
                    % data.get("reservoir", {}).get("seeds"))
    return errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="read the table and validate structure only; do not rewrite")
    ap.add_argument("--seeds", type=int, default=SEEDS)
    args = ap.parse_args()

    if args.check:
        if not OUT.exists():
            print("GATE: FAIL -- %s missing" % OUT.name)
            return 2
        data = json.loads(OUT.read_text(encoding="utf-8"))
        errs = check(data)
        if errs:
            print("GATE: FAIL")
            for e in errs:
                print("  - " + e)
            return 1
        g = data["rho_calibration"]
        print("GATE: PASS -- %d grid cells, %d seeds, N=%d"
              % (len(g), data["reservoir"]["seeds"], data["reservoir"]["n_units"]))
        print("  topology_shape_axis: %s" % data["topology_shape_axis"]["status"])
        print("  knee_region: %d cell(s) in 0.1-0.9" % len(data["knee_region"]))
        return 0

    t0 = time.time()
    data = build(n_seeds=args.seeds)
    errs = check(data)
    if errs:
        print("FAIL (self-check) -- not written:")
        for e in errs:
            print("  - " + e)
        return 1
    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote %s in %.1fs" % (OUT.name, time.time() - t0))
    for d in DELAY_GRID:
        seq = data["monotonicity"]["delay=%d" % d]["means"]
        print("  delay=%2d  rho .50->1.00: %s"
              % (d, " ".join("%.3f" % x for x in seq)))
    print("  topology_shape_axis: %s" % data["topology_shape_axis"]["status"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
