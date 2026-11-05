# ② 数据资产描述 — MICCAI 2026 技术材料基线

- 文档类型：技术基线（数据资产 + sha256 校验清单）
- 日期：2026-11-05
- 用途：申报材料中"数据资产"一节；含可复现校验（sha256 逐文件）。
- 诚实边界：仅列**项目内已校验**的数据资产；未校验/未持有完整文件集的数据源不列入"持有资产"，只在"引用数据"标注。

---

## 1. 核心数据资产（已持有 + 已校验）

### 1.1 MaleCNS v1.0（主数据源，真实连接组）

| 字段 | 值 |
|---|---|
| 数据集 | MaleCNS v1.0（雄性果蝇脑连接组，male Drosophila brain connectome） |
| 许可 | CC-BY（商用可用） |
| 神经元 | 167,565（VISION 叙事口径；实测锚定引用 107,558 真实细胞） |
| 突触 | 124,177,617（measured_synapses_neuron_subgraph） |
| 连接边（神经元子图） | 25,582,938（measured_edges_neuron_subgraph） |
| 文件数 | 211,604 |
| 总字节 | 37,418,478,413（37.4GB） |
| 生成时间 | 2026-09-20T04:36:51.591205+00:00 |
| 官方来源 | male-cns.janelia.org（2026-06-08 official；Cell 2026-09-03 发表） |
| DATA_MANIFEST.json sha256 | `9258e0f959ab1a0c3966b10275ac0103d0729bb5e4256b4b814049dd1a174bd3` |

**数据完整性校验**：DATA_MANIFEST.json 内含**逐文件 sha256**（files[] 数组，211,604 条），可全量复现校验；本基线文档提供的是**数据集级清单指纹** + 核心文件级 sha256（见 §2）。

### 1.2 功能单元模块库（派生资产，模块库本体）

| 资产 | 说明 | 规格 | sha256 |
|---|---|---|---|
| functional_units.json | 116 功能单元，83 端口类型，schema 1.0 | 1,228,193 B | `c427135f5f4e708793cceb71bb5fa44b1069f1f668ba469cab9d7b8089f148ba` |
| connection_types.json | 66 连接类型，schema 1.1 | 89,670 B | `a97430a2c9563f103e8ba4751b62247b5539b04c279e0be3c8d6d1a178b14770` |
| connection_costs.json | 66 成本轴，schema 1.1 | 97,986 B | `1847d1dcf5e0832a5e54a82cfc17302e7323ea67dec4e3e6f973a3007c7a71ac` |
| malecns_anchors.json | 真实锚定映射（58 锚定 profile / 107,558 细胞 / 5,413 类型） | 12,891,775 B | `6d3a2325ca310de4b3f70fddd1d009335138c635b125593c475e492cda1472c5` |

> ⚠️ **锚定校验一致性**：malecns_anchors.json 的实际 sha256（`6d3a2325...`）与 functional_units.json 中 `embodiment_source.sha256` **完全一致** ✅ —— 构建指纹可复现。

### 1.3 生成器/引擎（代码资产）

| 资产 | 说明 | sha256 |
|---|---|---|
| synthetic_bio_topology.py | C1 生成器（motif→agent 图+config+PROV；design/evolve/render/save） | `e9cff3b7f45d7cb940c7d1d5095f00551dea26d3b3778206dce8298d707fc0f1` |
| capability_quantification.py | 功能放大量化框架（functional_capacity/amplification/cross_domain） | `2a6fd9e7afb8235ac3f3c98fd2a6a71d18c290c77377b1a71c993ec7916baa2d` |
| combination_reaction.py | 组合反应引擎（12 规则+7 嵌套+4 乘数语义；"新能力判据=结构判据非功能判据"） | `80f69c957b152c227b95996e79e74e831716da82ea407afe61619fdfd5972fe8` |
| functional_unit_crud.py | 功能单元 CRUD（保存时重算派生字段，保留模型外字段） | `2ccc5c1b0561dd79162b4fd929dab656235d0a58e3d39bde610b33f952f5223f` |

## 2. 校验方法（申报可复现）

```bash
# 1) 逐文件校验（核心资产，本清单）
python -c "
import hashlib, json
files = ['flybrain-connectome-mcp/functional_units/functional_units.json', ...]
for f in files:
    h = hashlib.sha256(open(f,'rb').read()).hexdigest()
    print(f, h)
"

# 2) 全量数据校验（211,604 文件）
python -c "
import json
d = json.load(open('DATA_MANIFEST.json'))
print(d['dataset'], d['file_count'], d['total_bytes'])
# 逐文件校验可遍历 d['files'] 的 sha256
"
```

## 3. 引用数据（已核实许可，非本仓库持有完整文件集）

| 数据源 | 许可 | 商用 | 引用场景 |
|---|---|---|---|
| C. elegans (Witvliet 2020) | CC-BY-4.0 | ✅ | 跨物种锚定（模块库补充） |
| Drosophila larva (Winding 2023) | CC-BY | ✅ | 跨物种锚定（模块库补充） |
| zebrafish (Petkova 2025) | **CC-BY-NC-4.0** | ❌ 非商用 | 跨物种锚定（模块库补充） |
| mouse V1 (MICrONS) | CC-BY-4.0 | ✅ | 哺乳类锚定（模块库补充） |
| H01（人类，h01-release） | CC-BY-4.0 + 伦理门 | ✅（需伦理层） | 人类数据参考（**不混入模块库，需独立伦理审批**） |

> ⚠️ **Petkova 2025 非商用**：若申报产出涉及商业路径，该数据源不能用于商业衍生；申报材料应明确标注。
> ⚠️ **H01 人类数据**：独立伦理门（ethical_gate=true），仅作背景参考，不纳入模块库；申报若引用需单独伦理说明。

## 4. 诚实边界（数据资产口径）

- **"持有" vs "引用"**：本仓库**持有** MaleCNS v1.0 完整数据（DATA_MANIFEST 全量校验）+ 模块库派生资产；其余跨物种数据源为**引用**（已核实许可，未持完整文件集）。
- **锚定比例**：116 单元中 37 个真实锚定（31.9%）；40 motif 仅 3 个真实果蝇抽取（7.5%）——**申报材料若引用"果蝇连接组"必须如实表述**，不得暗示全部模块来自真实果蝇数据。
