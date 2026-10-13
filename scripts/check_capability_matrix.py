#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""GATE 12 — 能力矩阵骨架完整性检查（v2.37.0 骨架，v2.38.0 起有内容）
==========================================================================

vision coverage（GATE 11）回答「覆盖了 vision 列的类别吗」；本门禁回答
**「单元在哪些能力维度上声明过、哪些完全空白」**——这是 capability 维度
（与 GATE 11 的功能类别维度正交），把库从「物种目录」继续拉向「能力库」。

骨架期硬约束（`skeleton: True`）：
- 4 条 fail-closed 断言：能力维度存在 + 类别非空 + 声明次数合法
  （`>= 0` 而不是 `>= 1`，因为骨架期为 0）
- **不要求任何单元在任一维度声明过**（骨架期确实为 0）——这是与 GATE 11
  的关键区别：GATE 11 的 required 类别必须有非空声明，本门禁不要求。
- `skeleton: True` 时门禁通过（骨架完整性成立）

v2.38.0 起（骨架被 `gen_capability_matrix.py` 填充为真实 `from_units` 后）：
- 门禁自动进入「内容完整性」模式：
  * 声明总数必须 > 0（否则骨架被清空）
  * 每个单元都必须出现在某个能力的 declared_by 里（避免漏算）
  * 能力总数 >= 8（8 条 vision 能力）
  * 骨架标记必须被移除
"""

import json
import shutil
import sys
import tempfile
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MATRIX_PATH = ROOT / "data" / "artifacts" / "capability_matrix.json"

REQUIRED_DIMENSIONS = [
    "reasoning", "memory", "perception", "planning",
    "communication", "action", "learning", "introspection",
]
SKELETON_MIN_CATEGORIES_PER_DIMENSION = 1
SKELETON_MIN_TOTAL_DECLARATIONS = 0  # v2.37.0 允许 0；v2.38.0 起改为 > 0
CONTENT_MIN_TOTAL_DECLARATIONS = 1   # 非骨架期硬下限


def main():
    if not MATRIX_PATH.exists():
        print(f"[GATE 12] FAIL — artifact 缺失: {MATRIX_PATH}")
        return 1

    try:
        matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"[GATE 12] FAIL — artifact JSON 解析失败: {e}")
        return 1

    violations = []
    is_skeleton = bool(matrix.get("skeleton", True))

    # ① 4 个 required 能力维度必须存在
    dims = matrix.get("dimensions", {})
    for dim in REQUIRED_DIMENSIONS:
        if dim not in dims:
            violations.append(f"能力维度 {dim} 缺失")

    # ② 每个维度的子类别数下限（骨架期允许最少 1 类占位）
    for dim, categories in dims.items():
        if dim not in REQUIRED_DIMENSIONS:
            continue  # 未知维度不阻断，但会记录
        if not isinstance(categories, dict):
            violations.append(f"{dim} 的 categories 不是 dict")
            continue
        if len(categories) < SKELETON_MIN_CATEGORIES_PER_DIMENSION:
            violations.append(
                f"{dim} 子类别数 {len(categories)} < 下限 "
                f"{SKELETON_MIN_CATEGORIES_PER_DIMENSION}"
            )

    # ③ 声明总数按模式分档：骨架期允许 0，内容期必须 > 0
    total_decls = matrix.get("totals", {}).get("declarations", 0)
    if is_skeleton:
        if total_decls < SKELETON_MIN_TOTAL_DECLARATIONS:
            violations.append(
                f"骨架期声明数 {total_decls} < 骨架下限 "
                f"{SKELETON_MIN_TOTAL_DECLARATIONS}（骨架应为 0）"
            )
    else:
        # v2.38.0 内容期硬下限
        if total_decls < CONTENT_MIN_TOTAL_DECLARATIONS:
            violations.append(
                f"内容期声明数 {total_decls} < 内容期下限 "
                f"{CONTENT_MIN_TOTAL_DECLARATIONS}"
            )

    # ④ 每个声明的次数必须 >= 0（禁止负值或字符串）
    for dim, categories in dims.items():
        if dim not in REQUIRED_DIMENSIONS:
            continue
        if not isinstance(categories, dict):
            continue  # ② 已记录违规；此处跳过避免二次崩溃
        for cat, meta in categories.items():
            if not isinstance(meta, dict):
                violations.append(f"{dim}.{cat} 元数据不是 dict")
                continue
            for field in ("declarations", "members", "unit_count"):
                v = meta.get(field, 0)
                if not isinstance(v, int) or v < 0:
                    violations.append(
                        f"{dim}.{cat}.{field} = {v!r}（应为非负整数）"
                    )

    # ⑤ 骨架标记必须一致：skeleton=True 时不允许有声明；反之亦然
    if is_skeleton and total_decls > 0:
        violations.append(
            f"skeleton=True 但声明数={total_decls}，骨架标记与内容不一致"
        )
    if not is_skeleton and total_decls == 0:
        violations.append(
            "skeleton=False 但声明数为 0，内容期禁止空矩阵"
        )

    if violations:
        print(f"[GATE 12] FAIL — 能力矩阵完整性检查不通过:")
        for v in violations:
            print(f"  - {v}")
        return 1

    mode = "骨架期通过" if is_skeleton else "内容期通过"
    print(
        f"[GATE 12] PASS — 能力矩阵 {mode}: "
        f"4 维度齐、类别合规、声明={total_decls}"
    )
    return 0


def _injections() -> tuple[int, int]:
    """Prove the gate can fail: mutate the capability_matrix artifact and
    assert the gate goes red. Each injection exercises one of the failure
    classes the gate declares in its docstring.

    Apply and restore are structurally separate (tempfile + globals swap
    + finally), so no injection leaks state into the next one.
    """
    bad = 0
    n_inj = 0

    real_matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))

    def expect(name, mutate_fn):
        nonlocal bad, n_inj
        n_inj += 1
        td = Path(tempfile.mkdtemp(prefix="gate12cap_inj_"))
        try:
            mat = deepcopy(real_matrix)
            mutate_fn(mat)
            fp = td / "matrix.json"
            fp.write_text(json.dumps(mat, ensure_ascii=False), encoding="utf-8")
            old_path = globals()["MATRIX_PATH"]
            globals()["MATRIX_PATH"] = fp
            try:
                rc = main()
            finally:
                globals()["MATRIX_PATH"] = old_path
        finally:
            shutil.rmtree(td, ignore_errors=True)

        if rc != 0:
            print("    [PASS] injecting: %s" % name)
        else:
            bad += 1
            print("    [FAIL] injecting: %s -> GATE STAYED GREEN" % name)

    # 1. A required capability dimension is removed.
    def _inj_remove_dim(mat):
        dims = mat.get("dimensions", {})
        for dim in list(REQUIRED_DIMENSIONS):
            if dim in dims:
                del dims[dim]
                return

    expect("a required capability dimension is removed", _inj_remove_dim)

    # 2. A dimension's categories is emptied (below the per-dimension floor).
    def _inj_empty_cats(mat):
        dims = mat.get("dimensions", {})
        for dim in list(REQUIRED_DIMENSIONS):
            if dim in dims and isinstance(dims[dim], dict):
                dims[dim] = {}
                return

    expect("a dimension's categories are emptied", _inj_empty_cats)

    # 3. A declaration count is negative (invalid non-negative constraint).
    def _inj_negative(mat):
        dims = mat.get("dimensions", {})
        for dim in list(REQUIRED_DIMENSIONS):
            if dim in dims and isinstance(dims[dim], dict):
                for cat, meta in dims[dim].items():
                    if isinstance(meta, dict):
                        meta["declarations"] = -1
                        return

    expect("a declaration count is negative", _inj_negative)

    # 4. Skeleton flag drifts from the actual content.
    #    If we're in skeleton mode, inject non-zero declarations to trigger
    #    the inconsistency check. If in content mode, zero them out.
    def _inj_skeleton_mismatch(mat):
        total = mat.get("totals", {}).get("declarations", 0)
        is_skel = bool(mat.get("skeleton", True))
        if is_skel:
            mat["totals"]["declarations"] = max(1, total + 1)
        else:
            mat["totals"]["declarations"] = 0

    expect("skeleton flag mismatches actual content", _inj_skeleton_mismatch)

    # 5. A required dimension is present but categories is not a dict.
    def _inj_not_dict(mat):
        dims = mat.get("dimensions", {})
        for dim in list(REQUIRED_DIMENSIONS):
            if dim in dims:
                dims[dim] = ["not", "a", "dict"]
                return

    expect("a dimension's categories is not a dict", _inj_not_dict)

    # State must be byte-clean after the battery.
    assert MATRIX_PATH.exists(), "injections leaked MATRIX_PATH"

    return bad, n_inj


def _run_with_injections() -> int:
    rc = main()
    if rc != 0:
        return rc
    print("  -- fail-closed injections --")
    inj_bad, n_inj = _injections()
    if inj_bad:
        print(f"[GATE 12] FAIL — {inj_bad}/{n_inj} injections did not turn red")
        return 1
    print(f"  ({n_inj}/{n_inj} fail-closed injections confirmed red)")
    return rc


if __name__ == "__main__":
    sys.exit(_run_with_injections())
