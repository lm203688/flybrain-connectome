# 斑马鱼全脑 EM 连接组：可行性核实（v2.46.0 待实施）

**目的**：判断「加入第四个连接组 = 斑马鱼全脑 EM」是否可行，与已有三个连接组的分工，以及拉数据之前必须先确认的事。

**结论先行**：
- ✅ **数据可访问**：两个 2025 年公开 EM 源，Google Cloud / 中科院开放平台，CC-BY-NC 4.0
- ⚠️ **数据量级不适合本地全量**：30M synapses / 180k soma，需要采样策略
- ✅ **补齐的维度真实**：三个已有连接组都没有分子级 E/I 标注，斑马鱼是**脊椎动物首次 EM 级证据**
- ⚠️ **不能替代 MaleCNS 主力锚定**：116 单元的锚定 37 条全部来自 MaleCNS，斑马鱼是**独立证据源**，用来跨物种验证 circuit 是否守恒

---

## 数据源核实

### 源 A：Petkova et al. 2025（Janelia / ZFIN 联盟）

- **DOI**：10.1101/2025.06.10.658982
- **入口**：`https://fish1-release.storage.googleapis.com/index.html`（Google Cloud 公开桶）
- **平台**：open-access platform（Janelia Fish Connectome）
- **许可**：CC-BY-NC 4.0（禁止商业使用，与本项目 MIT 主许可冲突，需要单独处理）

**规模**：
| 维度 | 数值 |
|---|---|
| 分节 soma | >180,000 |
| 分子注释神经元 | >40,000（vglut2a 兴奋 / gad1b 抑制） |
| 突触 | ~30,000,000 |
| 递质分类 | 兴奋 / 抑制 / 调节 |
| 覆盖 | 全脑 + 前脊髓 |
| 方法 | CLEM（共聚焦 + 逐层 EM） |

**独有的三个维度**（三个已有连接组都没有）：
1. **每个 soma 带分子标签**：`vglut2a`（谷氨酸能，兴奋）/ `gad1b`（GABA 能，抑制）——本项目第一次可以声明**兴奋 vs 抑制**级别的 circuit
2. **递质三分类**：兴奋 / 抑制 / 调节——本项目的 `CONNECTION_TYPES` 里没有直接对应，需要新增 `excitatory_synapse` / `inhibitory_synapse`
3. **input / output drive index**：作者在单细胞分辨率算好了输入/输出驱动度，可以直接映射成 `PORT_TYPES` 里的强度信息

**作者示范的三个 circuit**（可直接抽成 unit 模板）：
- **侧线水流方向编码**（lateral line water flow）——本项目没有侧线单元，是新功能类别
- **后脑运动整合器**（hindbrain motion integrator）——recurrent excitation + contralateral inhibition，可对比本项目已有的视觉通路
- **被盖兴奋核远距离投射**（tegmental excitatory nucleus）——功能相关的长距离 projection，可对比本项目已有的 association cortex 单元

### 源 B：Zhang / Li et al. 2025（上海交大 / 中科院）

- **DOI**：10.1101/2025.06.12.659365
- **许可**：bioRxiv preprint，数据源未在摘要中给出（需二次核实）

**规模**：
| 维度 | 数值 |
|---|---|
| 分节神经元 | >170,000 |
| 突触 | ~25,000,000 |
| 神经调节亚型 | NA / DA / 5HT / orexin / glycinergic 五种 |
| 全脑 | 脊椎动物全脑 EM + 分子注释 |

**独有**：五种神经调节分子的亚型标注（NA 去甲肾上腺素、DA 多巴胺、5HT 5-羟色胺、orexin 食欲素、glycine 甘氨酸）——本项目的 `neuromodulation` domain 目前只有 4 个单元（dopaminergic_value / octopamine_arousal / locus_coeruleus_arousal 等），斑马鱼可以补齐 **5-HT / orexin** 两个跨物种证据。

**风险**：数据入口未在摘要披露，需要作者主页二次核实；如果只挂在 bioRxiv 没有独立平台，落地路径不明。

---

## 与三个已有连接组的分工

| 连接组 | 物种 | 神经元 | 突触 | 阶段 | 分子标签 | 用途 |
|---|---|---|---|---|---|---|
| MaleCNS | Drosophila 成虫 | 166,700 | 124M | 成虫雄性 | 无 E/I | **主力锚定**（37/115 单元） |
| Witvliet 2020 | C. elegans | 302 | 1,980 | 成虫×2 + L1×4 + L2/L3 | 无 | 发育阶段轴 |
| Winding 2023 | Drosophila 幼虫 | 2,956 | 352,611 | 幼虫 | 有 polarity（ad/aa/da/dd） | 幼虫阶段 + polarity |
| **Petkova 2025** | **Zebrafish 幼虫** | **180,000** | **30M** | **7-day larva** | **有 E/I + 递质分类** | **脊椎动物首证** |

**斑马鱼加入后新增的三个维度**：
1. **脊椎动物 EM 级证据**——现有三个都是 invertebrate；斑马鱼是唯一 vertebrate
2. **E/I 极性**——MaleCNS/C. elegans/larva 都没有，只有 zebrafish 有
3. **神经调节分子亚型**——现有 `neuromodulatory` domain 只有泛化标签，斑马鱼给具体分子

**不替代任何已有证据**：斑马鱼是**独立第四源**，不合并进 MaleCNS 锚定。116 单元的 37 条锚定仍然全部来自 MaleCNS；斑马鱼只提供跨物种一致性检查（同 circuit 在脊椎动物里是否存在）。

---

## 数据量级估算与采样策略

**全量下载估算**：
- Petkova：30M synapses × ~200 bytes/synapse = **6 GB**（保守）
- 加上 180k soma 形态 + 分子标签 = **再加 2 GB**
- **总计 ~8 GB**——不适合放 Tier-2 私有仓（当前 MaleCNS 5.63 GB 是单一大文件）

**采样策略**（本项目实际用的量级）：

| 阶段 | 数据 | 大小 | 用途 |
|---|---|---|---|
| 元数据 | fish1-release 目录清单 + 分片索引 | ~10 MB | 判断需要拉哪些 slice |
| 分子标签表 | 40k annotated somas 的 `vgLut2a/gad1b` 分类 | ~50 MB | 建分子注释索引 |
| 局部 edge 子集 | 每个示范 circuit 的邻域（3 个 circuit） | ~500 MB | 抽 3-5 个单元 |
| Drive index 表 | 输入/输出驱动度 per-soma | ~5 MB | 映射到 PORT_TYPES |
| 全量突触矩阵 | 30M synapses | 6 GB | **不落地**，只在作者平台查询 |

**实际策略**：不下载全量矩阵，只用作者平台的**查询接口**（如果开放）+ 元数据 + 分子标签 + 3 个示范 circuit 邻域。总本地数据 ~600 MB，符合项目当前体量。

---

## 必须先与用户确认的三个问题

1. **数据授权**：CC-BY-NC 4.0 与本项目 MIT 冲突。项目 MIT 承诺允许任意使用，但 Petkova 数据**只允许非商业**。选项：
   - (a) 单元声明里标注数据源为 CC-BY-NC，单元本身走 MIT
   - (b) 斑马鱼单元放入独立的 `data_cc_by_nc/` 目录，与 MIT 主体分离
   - (c) 只用 Zhang/Li 的数据（许可待核实）

2. **拉多少数据**：全量 8 GB 落 Tier-2 私有仓需要用户确认（现有 MaleCNS 5.63 GB 已经占了大部分空间）。建议先只拉 600 MB 采样集，验证可行后再决定是否扩到全量。

3. **抽取器实现范围**：
   - (a) 只写骨架（`extract_zebrafish_profiles.py` 带 TODO + 输入接口 + 空返回），等数据授权后再填实现——**推荐**
   - (b) 完整实现（含下载 + 解析 + 分子标签映射）——需要用户明确授权拉数据
   - (c) 只做可行性文档，不写抽取器——最保守

---

## 抽取器骨架（v2.46.0 建议）

`scripts/extract_zebrafish_profiles.py` 骨架设计：

```python
"""v2.46.0 — extract circuit profiles from the zebrafish connectome.

Source (待实施)：Petkova et al. 2025, Janelia Fish Connectome
（180k soma / 40k annotated / 30M synapses，CC-BY-NC 4.0）

本文件是骨架，不下载数据。落地前必须：
1. 与用户确认 CC-BY-NC 授权边界（本项目 MIT 主体如何隔离）
2. 用户明确授权拉数据（采样集 ~600 MB）
3. 决定抽取哪 3-5 个 circuit（示范：lateral line / hindbrain / tegmental）

骨架只做两件事：
- 声明期望的输入格式（避免以后重构）
- 声明期望的输出（对齐 zebrafish_profiles.json 结构，与 larva/cel 一致）

跑起来时：如果 ZEBRAFISH_DATA_DIR 未设，输出 SKIPPED 并说明下一步；
如果设了但目录为空，输出 FAILED 并说明缺哪个文件。
"""
import os, sys, json
from pathlib import Path

ZEBRAFISH_DATA_DIR = os.environ.get("ZEBRAFISH_DATA_DIR")
if not ZEBRAFISH_DATA_DIR:
    print("SKIPPED: ZEBRAFISH_DATA_DIR not set")
    print("下一步：与用户确认授权 → 采样数据 → 落 Tier-2")
    sys.exit(0)

# 期望的输入格式（作者平台导出的 CSV 或 JSON）：
#   somas.csv: soma_id, x, y, z, region, vglut2a_label, gad1b_label
#   edges.csv: source_soma_id, target_soma_id, synapse_count, drive_in, drive_out
#   circuits.json: {"lateral_line": [...soma_ids], "hindbrain": [...], "tegmental": [...]}

# 期望的输出（对齐 larva_profiles.json / cel_profiles.json）：
#   zebrafish_profiles.json:
#     {"schema_version": "1.0", "source": "Petkova 2025",
#      "somas_total": 180000, "annotated": 40000, "synapses": 30000000,
#      "profiles": {
#         "lateral_line_water_flow": {
#            "somas": 350, "synapses": 12000,
#            "excitatory_fraction": 0.72, "inhibitory_fraction": 0.28,
#            "connections": [...], "caveat": "sampled from 180k somas"
#         }, ...
#      }}
```

---

## 结论

- **技术可行**：数据可访问，规模可控（采样集 600 MB）
- **科学价值真实**：补脊椎动物 + E/I 极性 + 神经调节分子三轴
- **许可需注意**：CC-BY-NC 与 MIT 冲突，需要用户在三个选项里拍板
- **不替代现有证据**：独立第四源，只用作跨物种一致性检查
- **下一步需要用户确认**：授权边界 + 数据量 + 抽取范围

**在用户明确授权前不拉数据、不落 Tier-2、不新增单元**。骨架可以先建（v2.46.0），把决策点写在文件里而不是散在对话里。
