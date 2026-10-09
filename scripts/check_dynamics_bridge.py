#!/usr/bin/env python3
"""Gate 22 — 结构 × 动力学桥接查表：可复算性 + 诚实性。

stdlib-only（可直接读 JSON 做结构断言，不需要 numpy），因此在 --quick 下也跑。

查表本体见 integrations/swarmlabs/diagnostics/DYNAMICS_BRIDGE_LOOKUP.json，
由 dynamics_bridge_calibration.py 生成。本门禁不信任生成器的自检，独立断言：

  A. 形状完整 —— 网格满、数值在界内、噪声量已登记
  B. 定性不变量 —— 可测区间的 ρ 单调性不被谎报为通过
  C. 已证伪的轴不许偷偷变回来 —— topology_shape_axis 必须保持 REFUTED，
     0/7 决定性数字不能丢；空数组也不能静默清空

每条断言都配一个 fail-closed 注入：在深拷贝上改坏它、确认本门禁真的报红。
注入与还原是**两个独立动作**（原始 dict 从未被改过，注入只发生在副本上）——
不要写"同一个闭包调两次"式的 apply/restore，那在 pop/append 上会叠加而不是还原。
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "integrations" / "swarmlabs" / "diagnostics" / "DYNAMICS_BRIDGE_LOOKUP.json"

REFUTED = "REFUTED, not tabulated"


def audit(t: dict) -> list[str]:
    """返回错误列表；空 = 通过。"""
    errs: list[str] = []

    # ---- A. 形状完整 -------------------------------------------------
    grid_spec = t.get("grid") or {}
    rho = grid_spec.get("rho") or []
    delay = grid_spec.get("delay") or []
    if not rho or not delay:
        return ["grid.rho / grid.delay missing or empty"]

    cal = t.get("rho_calibration") or {}
    want = len(rho) * len(delay)
    if len(cal) != want:
        errs.append("rho_calibration has %d cells, expected %d (%d x %d)"
                    % (len(cal), want, len(rho), len(delay)))
    for k, v in cal.items():
        if not isinstance(v, dict):
            errs.append("%s is not an object" % k)
            continue
        m, s = v.get("mean_r2"), v.get("std_r2")
        if not isinstance(m, (int, float)) or not 0.0 <= m <= 1.0:
            errs.append("%s mean_r2 out of [0,1]: %r" % (k, m))
        if not isinstance(s, (int, float)) or s < 0:
            errs.append("%s std_r2 negative or missing: %r" % (k, s))

    res = t.get("reservoir") or {}
    if (res.get("seeds") or 0) < 5:
        errs.append("reservoir.seeds=%r too few to separate structure from input luck"
                    % res.get("seeds"))
    if not isinstance(res.get("n_units"), int) or res.get("n_units", 0) < 4:
        errs.append("reservoir.n_units=%r implausible" % res.get("n_units"))

    if t.get("r2_floor") is None:
        errs.append("r2_floor missing (clamp-excluded pairs must be declared)")
    if not (t.get("per_cell_seed_std") or {}).get("note"):
        errs.append("per_cell_seed_std.note missing -- tolerance provenance is unreadable")

    # ---- B. 定性不变量：单调性不许把「不可判定」读成「通过」----------
    mon = t.get("monotonicity") or {}
    assertable = 0
    for d, m in mon.items():
        verdict = m.get("monotone_within_tolerance")
        if verdict is True:
            assertable += 1
        elif verdict is False:
            errs.append("%s measured non-monotone in rho (drop %s > tol %s)"
                        % (d, m.get("max_drop"), m.get("tolerance")))
        elif verdict is None:
            if not m.get("pairs_below_floor"):
                errs.append("%s not assertable yet reports no floor exclusion" % d)
        else:
            errs.append("%s has no verdict (missing / malformed)" % d)

    if not t.get("measurable_delays"):
        errs.append("measurable_delays empty -- the lookup calibrates nothing")
    collapsed = t.get("collapsed_delays") or []
    if collapsed and (t.get("capacity_cliff") or {}).get("status") != "measured":
        errs.append("collapsed delay columns %r exist but capacity_cliff.status=%r"
                    % (collapsed, (t.get("capacity_cliff") or {}).get("status")))

    # ---- C. 已证伪的轴不许偷偷翻案 -----------------------------------
    tsa = t.get("topology_shape_axis") or {}
    if tsa.get("status") != REFUTED:
        errs.append("topology_shape_axis.status=%r -- must stay %r "
                    "(a null result may not be quietly promoted to a table)"
                    % (tsa.get("status"), REFUTED))
    if "0/7" not in (tsa.get("evidence") or ""):
        errs.append("topology_shape_axis.evidence lost the 0/7 matched-K figure")
    if not t.get("not_predicted_by"):
        errs.append("not_predicted_by empty -- silence would read as 'nothing tested'")
    if not (t.get("density_boundary") or {}).get("real_lever"):
        errs.append("density_boundary.real_lever missing")
    if not t.get("not_measured"):
        errs.append("not_measured empty -- must not imply full coverage")
    return errs


INJECTIONS = [
    ("empty grid drops a calibration cell",
     lambda t: t["rho_calibration"].pop(next(iter(t["rho_calibration"])))),
    ("a cell mean is pushed outside [0,1]",
     lambda t: t["rho_calibration"].__setitem__(next(iter(t["rho_calibration"])),
                                                {"mean_r2": 1.4, "std_r2": 0.0})),
    ("a cell std is made negative",
     lambda t: t["rho_calibration"].__setitem__(next(iter(t["rho_calibration"])),
                                                {"mean_r2": 0.5, "std_r2": -1.0})),
    ("a non-monotone curve is reported",
     lambda t: t["monotonicity"].__setitem__(
         next(iter(t["monotonicity"])),
         {"monotone_within_tolerance": False, "max_drop": 0.5,
          "tolerance": 0.01, "pairs_below_floor": []})),
    ("an unassertable curve is left silent",
     lambda t: t["monotonicity"].__setitem__(
         next(k for k, v in t["monotonicity"].items() if v.get("pairs_below_floor")),
         {"monotone_within_tolerance": None, "pairs_below_floor": []})),
    ("all delay columns become unmeasurable",
     lambda t: t.__setitem__("measurable_delays", [])),
    ("a collapsed column loses its cliff record",
     lambda t: t.__setitem__("capacity_cliff", {"status": "none within grid"})),
    ("the refuted axis is quietly promoted to a table",
     lambda t: t["topology_shape_axis"].__setitem__("status", "MEASURED, tabulated")),
    ("the 0/7 decisive figure is dropped",
     lambda t: t["topology_shape_axis"].__setitem__("evidence", "matched-K control: null")),
    ("the not_predicted_by list is emptied",
     lambda t: t.__setitem__("not_predicted_by", [])),
    ("seed count is cut below the averaging floor",
     lambda t: t["reservoir"].__setitem__("seeds", 1)),
    ("the clamp floor is removed",
     lambda t: t.__setitem__("r2_floor", None)),
]


def main() -> int:
    print("=" * 72)
    print("GATE 22 — structure x dynamics bridge lookup")
    print("=" * 72)

    if not TABLE.exists():
        print("GATE 22: FAIL -- %s not found; run dynamics_bridge_calibration.py"
              % TABLE.name)
        return 1
    base = json.loads(TABLE.read_text(encoding="utf-8"))

    errs = audit(base)
    if errs:
        for e in errs:
            print("  [FAIL] " + e)
        print("GATE 22: FAIL -- %d assertion(s) violated" % len(errs))
        return 1
    print("  [ok] %d grid cells, %d seeds, N=%s, r2_floor=%s"
          % (len(base["rho_calibration"]), base["reservoir"]["seeds"],
             base["reservoir"]["n_units"], base["r2_floor"]))
    print("  [ok] measurable delays %s; collapsed %s"
          % (base["measurable_delays"], base["collapsed_delays"]))
    print("  [ok] topology_shape_axis stays %s" % REFUTED)

    # ---- fail-closed injections --------------------------------------
    # 每次都在深拷贝上动手，原始 base 全程不被修改，因此还原就是"丢掉副本"，
    # 不存在 apply/restore 叠加的风险。
    print("  -- fail-closed injections --")
    broken = []
    for label, mutate in INJECTIONS:
        t = copy.deepcopy(base)
        try:
            mutate(t)
        except (KeyError, ValueError, StopIteration) as e:
            broken.append((label, "injection itself failed: %r" % e))
            continue
        got = audit(t)
        if not got:
            broken.append((label, "mutation passed undetected"))
            print("  [FAIL] injecting: %s -> NOT caught" % label)
        else:
            print("  [ok]   injecting: %s -> caught (%s)" % (label, got[0][:78]))

    if broken:
        print("GATE 22: FAIL -- %d injection(s) not caught" % len(broken))
        for label, why in broken:
            print("         - %s: %s" % (label, why))
        return 1

    cal = base["rho_calibration"]
    print("GATE 22: PASS -- %d cells audited, %d assertions, %d injections caught"
          % (len(cal), len(errs) + len(INJECTIONS), len(INJECTIONS)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
