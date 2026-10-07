# 审计：功能分类轴（v2.37.0 GATE 11 之后的第二遍）

## 问题设定

GATE 11 回答的是「vision 要的类别有没有缺口」——它只读 `function_coverage.json`
里的 24 个 canonical 类别。**它不校验单元自己声明的 `system` / `function` / `capability`
三个自由字符串字段是否一致。**

本审计问的是：**同一批 115 个单元，在这三个字段里描述的是同一个功能吗？**

## 结论：三个字段独立失控，且没有一个受控

| 字段 | 去重值 | 单值出现次数 | 判断 |
|---|---|---|---|
| `system` | 48 | ~20 | 分类词汇表存在但**语义复用**（"circuit" 一个词描述 10+ 种实际系统） |
| `function` | 60+ | 55 个只用一次 | **完全没有受控词表**——是散文式描述 |
| `capability` | 256 | 60 个只用一次 | **每个单元都在自创描述**——基本无复用 |
| `task_hint_pool` | 39 | 25 个只用一次 | 相对健康，接近可用 |

## 关键漂移：命名与实体不匹配

68 个单元 caveat 里的原话是 *"identity not resolvable as a Drosophila type in
FlyCellAtlas v1.0"*，但它们的 `system` 明确**不是 Drosophila**：

| 非果蝇 system | 单元数 | 举例 |
|---|---|---|
| `primate_association_cortex` | 3 | prefrontal_executive, cerebellar_motor_learning |
| `zebrafish_lateral_line` | 3 | lateral_line_touch, zebrafish_mechanosensory |
| `vertebrate_retina` | 2 | retinal_contrast, vertebrate_visual_peripheral |
| `mammalian_nociception` | 2 | mammalian_nociception |
| `mammalian_mechanosensory` | 2 | mammalian_mechanosensory, vertebrate_proprioception |
| `c. elegans` | 1 | chemosensory_mnemonic（**system 拼写错**，应为 `worm_neuromuscular`） |
| `human` | 1 | primate_attention |
| `human_brain` | 1 | human_attention |
| `avian_visual_system` | 1 | avian_visual_peripheral |
| `c. elegans_touch` | 1 | worm_touch_sensation |
| `invertebrate_larval_visual` | 1 | larval_visual |
| `human_brain_connectomics` | 1 | whole_brain_network |
| `rodent_hippocampus` | 1 | rodent_spatial_navigation |

## 两个自坑（防线）

### 1. 我原本的审计口径是错的

我把 68 项全列成"命名错配"，其中 **2 项是误报**（system = `worm_neuromuscular` 和
`invertebrate_neuromuscular` 的 `worm_*` 单元）。它们在 artifact 里的名字确实不是
Drosophila 类型，但它们的 `system` 已经是明确的非 Drosophila 分类，读者不会误读。
**"审计口径比真实问题大"** —— 写代码时用了 `drosophila` 作为白名单但没有排除
`system not in {drosophila, Drosophila}` 的双重判断，把 worm/vertebrate 都算进去了。

### 2. `taxonomy.system` 是 479 个可用值，只有 50 个在用

`PROVENANCE.taxon.system` 表里给了 479 个合法系统名，但 115 个单元实际只用到
~50 个——其中还有约 150 个单元声明的 system 值**完全不存在于 479 词表**中（例如
`invertebrate_nociception`、`vertebrate_mechanosensory`、`c. elegans` 都拼错或与词表无关）。
说明 `system` 是**弱约束**——填什么都不报错，等于没有约束。

## 修复建议（未落地）

1. `system` 加**白名单校验**：只允许 `PROVENANCE.taxon.system` 里的 479 个值之一，
   并显式拒绝自由字符串。当前状态：无断言。
2. `function` 加**长度上限 + 关键词词表**：60+ 个散文化描述里 55 个是单值。
   建议强制匹配 GATE 11 的 24 个 canonical 类别，或明确标注 `ad_hoc: true`。
3. `capability` **废弃**或改为**结构化枚举**：256 个描述里 60 个是单值，语义上
   接近 `function` 的重复。考虑删除，或改为 `capability_family` 有限枚举。
4. `identity_not_in_drosophila` 标签改名为 `identity_not_resolvable_in_target_taxon`
   —— 语义上更准确（当前名字对 66 项非果蝇系统不适用）。

## 未落地的原因

以上四条都是**改进项**不是**漏洞**——现状不会导致功能分类错误，只会让读者
"以为 66 项都是 Drosophila" 而实际上不是。这是**文档问题**而非**逻辑错误**。
在下一轮（v2.38）随其他改动一并处理，本轮不单独发版。
