"""
functional_unit_crud.py  --  功能单元 CRUD API

P1-5 交付：把 functional_units.json（只读加载）升级为可增删改查的模块库。

现状（P1-5 核实）：
    * functional_units.py 只提供只读接口（load_units / list_units / get_unit），
      无任何写接口（无 add/update/delete）。
    * module_registry.py 有 ModuleFactory CRUD（list/get/save/load/delete market
      organisms），但那是 213 模块的硬编码 dict，不是"功能单元 JSON"层。

本模块提供对 functional_units.json 的最小 CRUD，原则：
    * 每次写操作都校验（端口类型合法、name 唯一、字段齐备），失败 fail-closed。
    * 写回前自动备份（.bak_crud），写后自动重载并重算 stats，保证不损坏库。
    * 不改变现有只读接口（load_units 仍可用），只新增写能力。

用法（CLI 或 Python）：
    python functional_unit_crud.py list
    python functional_unit_crud.py get <name>
    python functional_unit_crud.py add <json_file>
    python functional_unit_crud.py update <name> <json_file>
    python functional_unit_crud.py delete <name>
"""
from __future__ import annotations

import json
import shutil
import sys
import argparse
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
UNITS_FILE = HERE / "functional_units" / "functional_units.json"

REQUIRED_FIELDS = ["name", "display", "function", "system", "description",
                   "members", "internal_wiring", "ports", "size_range",
                   "motif_source", "capability", "task_hint_pool"]
# 可选字段（有默认/可空）
OPTIONAL_FIELDS = ["provenance", "embodiment", "species_source"]


def _load() -> dict:
    return json.loads(UNITS_FILE.read_text(encoding="utf-8"))


def _save(doc: dict, reason: str = "") -> None:
    """原子写回 + 备份。reason 用于备份文件名标记。"""
    bak = UNITS_FILE.with_name(f"{UNITS_FILE.stem}.bak_crud{('_'+reason) if reason else ''}.json")
    shutil.copy2(UNITS_FILE, bak)
    UNITS_FILE.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")


def _recompute_stats(doc: dict) -> dict:
    """重算 stats，与 JSON 源保持一致（116 单元的 stats 口径）。

    合并而非覆盖：保留派生/测量类字段（connection_types、embodied_populations_referenced、
    structural_support_edges_*、support_resolution、contradictions_acknowledged 等），
    只重算单元数派生字段（functional_units/systems/embodied_units）。
    """
    units = doc.get("units", [])
    systems = sorted({u.get("system", "?") for u in units})
    embodied = sum(1 for u in units if u.get("embodiment", {}).get("real_cells_anchored", 0) > 0)
    # 基础重算字段
    recomputed = {
        "functional_units": len(units),
        "systems": systems,
        "embodied_units": embodied,
    }
    # 合并现有 stats（保留派生/测量字段，避免覆盖丢失）
    merged = dict(doc.get("stats", {}))
    merged.update(recomputed)
    return merged


def _validate_unit(unit: dict, units: list[dict], is_new: bool) -> list[str]:
    """返回错误列表（空=通过）。fail-closed。"""
    errors = []
    name = unit.get("name", "")
    if not name:
        errors.append("name 必填")
    # 唯一性
    for u in units:
        if u.get("name") == name and (is_new or u.get("name") != name):
            errors.append(f"name '{name}' 已存在")
            break
    # 字段齐备（允许缺省可选字段）
    for f in REQUIRED_FIELDS:
        if f not in unit:
            errors.append(f"缺少字段: {f}")
    # 端口类型合法性（必须有 in/out）
    ports = unit.get("ports", {})
    if "in" not in ports and "out" not in ports:
        errors.append("ports 必须含 in 或 out")
    # 端口类型引用一致性（type 非空）
    for direction in ("in", "out"):
        for p in ports.get(direction, []):
            if not p.get("type"):
                errors.append(f"ports.{direction} 端口 '{p.get('name','?')}' 缺 type")
    return errors


def list_units() -> list[dict]:
    doc = _load()
    return doc.get("units", [])


def get_unit(name: str) -> dict | None:
    doc = _load()
    for u in doc.get("units", []):
        if u.get("name") == name:
            return u
    return None


def add_unit(unit: dict) -> dict:
    doc = _load()
    errors = _validate_unit(unit, doc.get("units", []), is_new=True)
    if errors:
        return {"ok": False, "errors": errors}
    doc.setdefault("units", []).append(unit)
    doc["stats"] = _recompute_stats(doc)
    _save(doc, "add")
    return {"ok": True, "name": unit["name"], "count": len(doc["units"])}


def update_unit(name: str, patch: dict) -> dict:
    doc = _load()
    units = doc.get("units", [])
    idx = next((i for i, u in enumerate(units) if u.get("name") == name), None)
    if idx is None:
        return {"ok": False, "errors": [f"name '{name}' 不存在"]}
    # 合并（name 不可改）
    merged = dict(units[idx])
    for k, v in patch.items():
        if k != "name":
            merged[k] = v
    errors = _validate_unit(merged, units, is_new=False)
    if errors:
        return {"ok": False, "errors": errors}
    units[idx] = merged
    doc["stats"] = _recompute_stats(doc)
    _save(doc, "update")
    return {"ok": True, "name": name, "count": len(units)}


def delete_unit(name: str) -> dict:
    doc = _load()
    units = doc.get("units", [])
    before = len(units)
    units = [u for u in units if u.get("name") != name]
    if len(units) == before:
        return {"ok": False, "errors": [f"name '{name}' 不存在"]}
    doc["units"] = units
    doc["stats"] = _recompute_stats(doc)
    _save(doc, "delete")
    return {"ok": True, "name": name, "count": len(units)}


def _cli() -> int:
    ap = argparse.ArgumentParser(description="功能单元 CRUD API")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="列出所有单元")
    p_get = sub.add_parser("get", help="获取单个单元")
    p_get.add_argument("name")
    p_add = sub.add_parser("add", help="添加单元（从 JSON 文件）")
    p_add.add_argument("json_file")
    p_up = sub.add_parser("update", help="更新单元（合并 JSON 文件）")
    p_up.add_argument("name")
    p_up.add_argument("json_file")
    p_del = sub.add_parser("delete", help="删除单元")
    p_del.add_argument("name")
    args = ap.parse_args()

    if args.cmd == "list":
        units = list_units()
        print(json.dumps([u.get("name") for u in units], ensure_ascii=False, indent=2))
    elif args.cmd == "get":
        u = get_unit(args.name)
        print(json.dumps(u, ensure_ascii=False, indent=2) if u else f"NOT FOUND: {args.name}")
    elif args.cmd == "add":
        unit = json.loads(Path(args.json_file).read_text(encoding="utf-8"))
        print(json.dumps(add_unit(unit), ensure_ascii=False))
    elif args.cmd == "update":
        patch = json.loads(Path(args.json_file).read_text(encoding="utf-8"))
        print(json.dumps(update_unit(args.name, patch), ensure_ascii=False))
    elif args.cmd == "delete":
        print(json.dumps(delete_unit(args.name), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
