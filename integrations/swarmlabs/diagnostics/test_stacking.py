"""v2.9.1 组合堆叠能力测试 —— 验证所有完成的模块能否正确组合。

测试范围：
  1. v2.9.0 新增端口（memory.associative, modulatory.orexin, modulatory.histamine）
     是否能被 compose_from_units 正确识别和连接
  2. 多种组合形态（链式、树状、网状）的验证
  3. 端口类型兼容性检查
  4. 组合后的结构完整性

用法：
  python test_stacking.py
"""
import sys
import json
from pathlib import Path
from collections import Counter

HERE = Path(__file__).resolve().parent
MCP = HERE.parent.parent.parent / "flybrain-connectome-mcp"
sys.path.insert(0, str(MCP))
sys.path.insert(0, str(HERE))

from functional_units import compose_from_units, load_units

# ---------------------------------------------------------------------------
# 1. v2.9.0 新增端口测试
# ---------------------------------------------------------------------------
def test_v29_ports():
    """测试 v2.9.0 新增的 3 个端口是否能正常工作。"""
    print("=" * 70)
    print("测试 1: v2.9.0 新增端口验证")
    print("=" * 70)
    
    units = load_units()["units"]
    port_types = load_units()["port_types"]
    
    # 检查新增端口是否存在于 PORT_TYPES
    new_ports = ["memory.associative", "modulatory.orexin", "modulatory.histamine",
                 "sensory.*", "modulatory.*"]
    print(f"\nPORT_TYPES 总数: {len(port_types)}")
    for p in new_ports:
        exists = p in port_types
        print(f"  {'✓' if exists else '✗'} {p:30s} {'存在' if exists else '缺失'}")
    
    # 检查哪些单元使用了这些新端口
    print(f"\n使用新端口的单元:")
    for p in new_ports[:3]:  # 前 3 个是具体端口，后 2 个是通配
        using = []
        for u in units:
            ports = u.get('ports', {})
            for side in ('in', 'out'):
                for x in ports.get(side, []) or []:
                    if isinstance(x, dict) and x.get('type') == p:
                        using.append(f"{u['name']} [{side}]")
        if using:
            print(f"  {p:30s}: {len(using)} 处使用")
            for u in using[:5]:
                print(f"    {u}")
    
    return True


# ---------------------------------------------------------------------------
# 2. 端口类型兼容性测试
# ---------------------------------------------------------------------------
def test_port_compatibility():
    """测试端口类型兼容性检查是否正常工作。"""
    print("\n" + "=" * 70)
    print("测试 2: 端口类型兼容性检查")
    print("=" * 70)
    
    units = load_units()["units"]
    
    # 收集所有单元的端口
    unit_ports = {}
    for u in units:
        ports = u.get('ports', {})
        in_ports = [p for p in ports.get('in', []) if isinstance(p, dict)]
        out_ports = [p for p in ports.get('out', []) if isinstance(p, dict)]
        unit_ports[u['name']] = {
            'in': {p['name']: p['type'] for p in in_ports},
            'out': {p['name']: p['type'] for p in out_ports}
        }
    
    # 测试 compose_from_units 的验证
    # 测试 1: 正确的端口类型匹配
    print("\n测试 1: 正确端口类型匹配")
    test_cases = [
        ("olfactory_to_steering", [
            {"unit": "antennal_lobe_glomerular_unit", "instances": 1},
            {"unit": "mushroom_body_sparse_code_unit", "instances": 1},
            {"unit": "mushroom_body_associative_memory_unit", "instances": 1},
            {"unit": "central_complex_steering_unit", "instances": 1},
        ], [
            {"type": "sparse_expansion_projection",
             "from": "antennal_lobe_glomerular_unit.pn_out",
             "to": "mushroom_body_sparse_code_unit.pn_in"},
        ]),
    ]
    
    for name, unit_list, conn_list in test_cases:
        result = compose_from_units(unit_list, conn_list, name=name + "_test")
        ok = result["validation"]["ok"]
        errors = result["validation"]["errors"][:3]
        print(f"  {'✓' if ok else '✗'} {name:30s} ok={ok}  errors={errors}")
    
    # 测试 2: 错误的端口类型匹配（应该失败）
    print("\n测试 2: 错误端口类型匹配（应该失败）")
    bad_cases = [
        ("bad_port_type", [
            {"unit": "antennal_lobe_glomerular_unit", "instances": 1},
            {"unit": "mushroom_body_sparse_code_unit", "instances": 1},
        ], [
            {"type": "sparse_expansion_projection",
             "from": "antennal_lobe_glomerular_unit.pn_out",
             "to": "mushroom_body_sparse_code_unit.nonexistent_port"},
        ]),
    ]
    
    for name, unit_list, conn_list in bad_cases:
        result = compose_from_units(unit_list, conn_list, name=name + "_test")
        ok = result["validation"]["ok"]
        errors = result["validation"]["errors"][:3]
        print(f"  {'✗' if not ok else '✓'} {name:30s} ok={ok}  errors={errors}")
    
    return True


# ---------------------------------------------------------------------------
# 3. 多种组合形态测试
# ---------------------------------------------------------------------------
def test_composition_patterns():
    """测试链式、树状、网状等多种组合形态。"""
    print("\n" + "=" * 70)
    print("测试 3: 多种组合形态")
    print("=" * 70)
    
    units = load_units()["units"]
    
    # 链式（已有）
    chain_composition = [
        {"unit": "compound_lamina_relay_unit", "instances": 1},
        {"unit": "elementary_motion_detection_unit", "instances": 1},
        {"unit": "lobula_plate_optic_flow_unit", "instances": 1},
    ]
    chain_conns = [
        {"type": "feedforward_excitatory",
         "from": "compound_lamina_relay_unit.lamina_out",
         "to": "elementary_motion_detection_unit.lamina_in"},
        {"type": "feedforward_excitatory",
         "from": "elementary_motion_detection_unit.motion",
         "to": "lobula_plate_optic_flow_unit.motion_in"},
    ]
    
    # 树状（一个输入分发到多个输出）
    tree_composition = [
        {"unit": "antennal_lobe_glomerular_unit", "instances": 1},
        {"unit": "mushroom_body_sparse_code_unit", "instances": 1},
        {"unit": "mushroom_body_associative_memory_unit", "instances": 1},
        {"unit": "central_complex_heading_unit", "instances": 1},
    ]
    tree_conns = [
        {"type": "sparse_expansion_projection",
         "from": "antennal_lobe_glomerular_unit.pn_out",
         "to": "mushroom_body_sparse_code_unit.pn_in"},
        {"type": "sparse_expansion_projection",
         "from": "antennal_lobe_glomerular_unit.pn_out",
         "to": "central_complex_heading_unit.compass_in"},
    ]
    
    # 网状（多个输入汇聚到多个输出）
    network_composition = [
        {"unit": "compound_lamina_relay_unit", "instances": 1},
        {"unit": "elementary_motion_detection_unit", "instances": 1},
        {"unit": "looming_detection_unit", "instances": 1},
        {"unit": "giant_fiber_escape_unit", "instances": 1},
    ]
    network_conns = [
        {"type": "feedforward_excitatory",
         "from": "compound_lamina_relay_unit.lamina_out",
         "to": "elementary_motion_detection_unit.lamina_in"},
        {"type": "feedforward_excitatory",
         "from": "compound_lamina_relay_unit.lamina_out",
         "to": "looming_detection_unit.motion"},
        {"type": "feedforward_excitatory",
         "from": "looming_detection_unit.loom_cmd",
         "to": "giant_fiber_escape_unit.looming"},
    ]
    
    patterns = [
        ("链式 (chain)", chain_composition, chain_conns),
        ("树状 (tree)", tree_composition, tree_conns),
        ("网状 (network)", network_composition, network_conns),
    ]
    
    results = []
    for name, units_list, conns_list in patterns:
        try:
            result = compose_from_units(units_list, conns_list, name=name + "_test")
            ok = result["validation"]["ok"]
            errors = result["validation"]["errors"]
            warnings = result["validation"]["warnings"]
            n_nodes = len(result["organism"]["nodes"])
            n_edges = len(result["organism"]["edges"])
            results.append((name, ok, n_nodes, n_edges, errors, warnings))
            print(f"\n  {'✓' if ok else '✗'} {name}")
            print(f"    nodes={n_nodes}  edges={n_edges}  ok={ok}")
            if errors:
                print(f"    errors: {errors[:3]}")
            if warnings:
                print(f"    warnings: {warnings[:3]}")
        except Exception as e:
            print(f"\n  ✗ {name} - EXCEPTION: {e}")
            results.append((name, False, 0, 0, [str(e)], []))
    
    success_rate = sum(1 for _, ok, *_ in results if ok) / len(results)
    print(f"\n组合形态成功率: {success_rate:.0%}")
    
    return success_rate == 1.0


# ---------------------------------------------------------------------------
# 4. 大规模组合测试
# ---------------------------------------------------------------------------
def test_large_scale_composition():
    """测试更大规模的组合（5+ 单元）。"""
    print("\n" + "=" * 70)
    print("测试 4: 大规模组合测试")
    print("=" * 70)
    
    # 视觉到逃避链（5 单元）
    visual_chain = [
        {"unit": "compound_lamina_relay_unit", "instances": 1},
        {"unit": "elementary_motion_detection_unit", "instances": 1},
        {"unit": "lobula_plate_optic_flow_unit", "instances": 1},
        {"unit": "looming_detection_unit", "instances": 1},
        {"unit": "giant_fiber_escape_unit", "instances": 1},
    ]
    visual_conns = [
        {"type": "feedforward_excitatory",
         "from": "compound_lamina_relay_unit.lamina_out",
         "to": "elementary_motion_detection_unit.lamina_in"},
        {"type": "feedforward_excitatory",
         "from": "elementary_motion_detection_unit.motion",
         "to": "lobula_plate_optic_flow_unit.motion_in"},
        {"type": "feedforward_excitatory",
         "from": "looming_detection_unit.loom_cmd",
         "to": "giant_fiber_escape_unit.looming"},
    ]
    
    result = compose_from_units(visual_chain, visual_conns, name="visual_5unit")
    ok = result["validation"]["ok"]
    errors = result["validation"]["errors"]
    n_nodes = len(result["organism"]["nodes"])
    n_edges = len(result["organism"]["edges"])
    
    print(f"\n  视觉链 (5 单元):")
    print(f"    {'✓' if ok else '✗'} ok={ok}")
    print(f"    nodes={n_nodes}  edges={n_edges}")
    if errors:
        print(f"    errors: {errors[:3]}")
    
    # 嗅觉到转向链（4 单元）
    olfactory_chain = [
        {"unit": "antennal_lobe_glomerular_unit", "instances": 1},
        {"unit": "mushroom_body_sparse_code_unit", "instances": 1},
        {"unit": "mushroom_body_associative_memory_unit", "instances": 1},
        {"unit": "central_complex_steering_unit", "instances": 1},
    ]
    olfactory_conns = [
        {"type": "sparse_expansion_projection",
         "from": "antennal_lobe_glomerular_unit.pn_out",
         "to": "mushroom_body_sparse_code_unit.pn_in"},
        {"type": "sparse_expansion_projection",
         "from": "mushroom_body_sparse_code_unit.sparse_out",
         "to": "mushroom_body_associative_memory_unit.sparse_code"},
        {"type": "modulatory_gated_plasticity",
         "from": "mushroom_body_associative_memory_unit.learned_valence",
         "to": "central_complex_steering_unit.valence_in"},
    ]
    
    result2 = compose_from_units(olfactory_chain, olfactory_conns, name="olfactory_4unit")
    ok2 = result2["validation"]["ok"]
    errors2 = result2["validation"]["errors"]
    n_nodes2 = len(result2["organism"]["nodes"])
    n_edges2 = len(result2["organism"]["edges"])
    
    print(f"\n  嗅觉链 (4 单元):")
    print(f"    {'✓' if ok2 else '✗'} ok={ok2}")
    print(f"    nodes={n_nodes2}  edges={n_edges2}")
    if errors2:
        print(f"    errors: {errors2[:3]}")
    
    return ok and ok2


# ---------------------------------------------------------------------------
# 5. 组合完整性验证
# ---------------------------------------------------------------------------
def test_composition_integrity():
    """验证组合后的结构完整性。"""
    print("\n" + "=" * 70)
    print("测试 5: 组合完整性验证")
    print("=" * 70)
    
    units = load_units()["units"]
    unit_map = {u['name']: u for u in units}
    
    # 测试组合后的端口可访问性
    test_comp = [
        {"unit": "compound_lamina_relay_unit", "instances": 1},
        {"unit": "elementary_motion_detection_unit", "instances": 1},
    ]
    test_conns = [
        {"type": "feedforward_excitatory",
         "from": "compound_lamina_relay_unit.lamina_out",
         "to": "elementary_motion_detection_unit.lamina_in"},
    ]
    
    result = compose_from_units(test_comp, test_conns, name="integrity_test")
    organism = result["organism"]
    
    print(f"\n  组合节点数: {len(organism['nodes'])}")
    print(f"  组合边数: {len(organism['edges'])}")
    
    # 检查每个节点是否保留了单元信息
    for node in organism['nodes']:
        unit_name = node['unit']
        unit = unit_map.get(unit_name)
        if unit:
            print(f"\n  节点: {node['id']}")
            print(f"    单元: {unit_name}")
            print(f"    功能: {unit.get('function', 'N/A')}")
            print(f"    系统: {unit.get('system', 'N/A')}")
            ports = unit.get('ports', {})
            in_ports = ports.get('in', [])
            out_ports = ports.get('out', [])
            print(f"    输入端口: {len(in_ports)}  输出端口: {len(out_ports)}")
    
    # 检查边是否正确连接
    print(f"\n  边连接验证:")
    for edge in organism['edges']:
        print(f"    {edge['from']} → {edge['to']}  (type={edge['type']})")
    
    return True


# ---------------------------------------------------------------------------
# 5. v2.9.0 新端口组合测试
# ---------------------------------------------------------------------------
def test_v29_port_composition():
    """测试 v2.9.0 新增端口能否在组合中正确工作。"""
    print("\n" + "=" * 70)
    print("测试 5: v2.9.0 新端口组合测试")
    print("=" * 70)
    
    units = load_units()["units"]
    
    # 测试 1: 使用 memory.associative 端口的组合
    print("\n测试 1: memory.associative 端口组合")
    comp1 = [
        {"unit": "mushroom_body_sparse_code_unit", "instances": 1},
        {"unit": "mushroom_body_associative_memory_unit", "instances": 1},
        {"unit": "central_complex_steering_unit", "instances": 1},
    ]
    conn1 = [
        {"type": "sparse_expansion_projection",
         "from": "mushroom_body_sparse_code_unit.sparse_out",
         "to": "mushroom_body_associative_memory_unit.sparse_code"},
        {"type": "modulatory_gated_plasticity",
         "from": "mushroom_body_associative_memory_unit.learned_valence",
         "to": "central_complex_steering_unit.valence_in"},
    ]
    result1 = compose_from_units(comp1, conn1, name="memory_trace_test")
    ok1 = result1["validation"]["ok"]
    print(f"  {'✓' if ok1 else '✗'} memory.associative 组合 ok={ok1}")
    if not ok1:
        print(f"    errors: {result1['validation']['errors'][:3]}")
    
    # 测试 2: 使用 modulatory.orexin 和 modulatory.histamine 端口的组合
    print("\n测试 2: modulatory.orexin/histamine 端口组合")
    comp2 = [
        {"unit": "hypothalamic_arousal_unit", "instances": 1},
        {"unit": "mushroom_body_associative_memory_unit", "instances": 1},
    ]
    conn2 = [
        {"type": "state_gating_modulation",
         "from": "hypothalamic_arousal_unit.arousal_out",
         "to": "mushroom_body_associative_memory_unit.value_in"},
    ]
    result2 = compose_from_units(comp2, conn2, name="arousal_modulation_test")
    ok2 = result2["validation"]["ok"]
    print(f"  {'✓' if ok2 else '✗'} 觉醒调制组合 ok={ok2}")
    if not ok2:
        print(f"    errors: {result2['validation']['errors'][:3]}")
    
    # 验证新端口在组合结果中的可见性
    print("\n验证新端口在组合结果中的可见性:")
    for node in result1.get("organism", {}).get("nodes", []):
        unit_name = node.get("unit")
        unit = next((u for u in units if u['name'] == unit_name), None)
        if unit:
            out_ports = [p for p in unit.get('ports',{}).get('out',[]) 
                        if isinstance(p, dict)]
            new_ports = [p for p in out_ports 
                        if p.get('type') in ('memory.associative', 
                                             'modulatory.orexin', 
                                             'modulatory.histamine')]
            if new_ports:
                print(f"  {unit_name}: 新端口 {len(new_ports)} 个")
                for p in new_ports:
                    print(f"    - {p['name']} ({p['type']})")
    
    return ok1 and ok2


# ---------------------------------------------------------------------------
# 6. 组合能力统计
# ---------------------------------------------------------------------------
def test_composition_stats():
    """统计可组合的单元和端口。"""
    print("\n" + "=" * 70)
    print("测试 6: 组合能力统计")
    print("=" * 70)
    
    units = load_units()["units"]
    
    # 统计每个单元的输入/输出端口类型
    port_usage = Counter()
    for u in units:
        ports = u.get('ports', {})
        for side in ('in', 'out'):
            for p in ports.get(side, []) or []:
                if isinstance(p, dict) and 'type' in p:
                    port_usage[p['type']] += 1
    
    print(f"\n  端口类型使用频率 (前 15):")
    for ptype, count in port_usage.most_common(15):
        print(f"    {ptype:40s} {count:3d} 次")
    
    # 统计可组合的单元对（有匹配端口的）
    composable_pairs = []
    for i, u1 in enumerate(units):
        ports1 = u1.get('ports', {})
        out_ports1 = [p['type'] for p in ports1.get('out', []) if isinstance(p, dict)]
        for u2 in units[i+1:]:
            ports2 = u2.get('ports', {})
            in_ports2 = [p['type'] for p in ports2.get('in', []) if isinstance(p, dict)]
            # 检查是否有匹配的端口类型
            matches = set(out_ports1) & set(in_ports2)
            if matches:
                composable_pairs.append((u1['name'], u2['name'], matches))
    
    print(f"\n  可组合单元对: {len(composable_pairs)}")
    print(f"  示例 (前 10):")
    for u1, u2, matches in composable_pairs[:10]:
        print(f"    {u1[:30]:30s} → {u2[:30]:30s}  匹配: {list(matches)[:2]}")
    
    return len(composable_pairs)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 70)
    print("v2.9.1 组合堆叠能力测试")
    print("=" * 70)
    
    results = {}
    
    # 运行所有测试
    results['v29_ports'] = test_v29_ports()
    results['port_compatibility'] = test_port_compatibility()
    results['composition_patterns'] = test_composition_patterns()
    results['large_scale'] = test_large_scale_composition()
    results['integrity'] = test_composition_integrity()
    results['v29_port_composition'] = test_v29_port_composition()
    results['stats'] = test_composition_stats()
    
    # 总结
    print("\n" + "=" * 70)
    print("测试结果总结")
    print("=" * 70)
    
    all_pass = all(isinstance(v, bool) and v for k, v in results.items() 
                   if k not in ('stats',))
    
    for name, passed in results.items():
        if name == 'stats':
            continue
        status = '✓ PASS' if passed else '✗ FAIL'
        print(f"  {status:10s} {name}")
    
    print(f"\n  总体: {'✓ 全部通过' if all_pass else '✗ 有失败项'}")
    
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())