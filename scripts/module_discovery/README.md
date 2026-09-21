# module_discovery — 从真实连接组发现功能模块

把 166,700 个神经元**降维成可复用的最小功能单元**，产出的模块库带真实溯源
（追溯到具体 superclass、真实突触数、真实递质指纹），不掺任何合成数据。

## 三步管线

```bash
# 需要 FLYBRAIN_DATA_DIR 指向 male_cns（含 connectome_cache/*.npy）
python scripts/module_discovery/step1_build_matrix.py   # 27x27 加权有向矩阵
python scripts/module_discovery/step2_cluster.py        # 双模态聚类 + 对照
python scripts/module_discovery/step3_build_library.py  # 数据驱动模块库
```

## 各步做什么

| 步 | 输入 | 输出 | 耗时 |
|---|---|---|---|
| step1 | `connectome_cache/*.npy`（1.5 亿边） | `male_cns/superclass_matrix.json` | ~1–2 min |
| step2 | 上述矩阵 + `nt.json` | `tmp/module_discovery_result.txt` | <5 s |
| step3 | 上述矩阵 + 分组定义 | `male_cns/discovered_modules.json` | <5 s |

## step1 的自校验

脚本内置两条硬校验，任何一条不过就说明数据或映射错了：

```
SELF-CHECK ol_intrinsic->ol_intrinsic = 35,691,182  (expect 35,691,182)  PASS
SELF-CHECK matrix total               = 124,177,617 (expect 124,177,617) PASS
```

## 方法

**双模态特征**（step2）：
- 结构指纹：出/入分布各 27 维（行/列归一化）
- 功能指纹：该 superclass 内 7 类递质分布
- 记忆指纹：自循环率（自环突触 / 自身输出突触）

**两种聚类互相印证**：
- Louvain 社区发现（网络视角）→ modularity Q = 0.3748，3 社区
- Ward 层次聚类（特征视角）→ 三大内在核各自独立成簇

## 结论要点

1. 三个内在核 `ol_intrinsic` / `cb_intrinsic` / `vnc_intrinsic` 的**自循环率分别为
   81.1% / 87.8% / 70.8%**（占自身输出）——它们是自治递归记忆体，不是处理器。
2. 递质指纹可直接做功能标注：`ol_sensory` 组胺 1.00（光感受器）、
   `visual_centrifugal` GABA 0.59（抑制门控）、`vnc_motor` 谷氨酸 0.95（兴奋输出）。
3. 8 个数据驱动单元覆盖 **99.97%** 的突触；与现有 19 个人工模块**无对应关系**。

## 边界

- `superclass` 是**粗粒度**注释（27 类）。要到"极限最小单位"，需下沉到
  neuropil（146）或细胞类型层——这是下一步。
- 只有果蝇一个物种。跨生物通用性需要用线虫（302 神经元）等下界验证。
