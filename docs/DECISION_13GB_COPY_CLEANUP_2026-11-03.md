# 13GB 副本清理决策记录（2026-11-03）

> **任务**：任务书 P2-8（13GB 副本清理）。
> **目标路径**：`drosophila_connectome/data/male_cns/`（2 个文件，合计约 13GB）。
> **授权状态**：用户已批准任务书四项（含 13GB 副本清理，Chief m00027 转达）；本次执行前做删除前验证并留痕。

---

## 1. 目标内容（已核实）

| 文件 | 大小 | 路径 |
|---|---|---|
| `syn-points-male-cns-v1.0-minconf-0.5.feather` | 13,061,489,098 B（≈12.2 GiB / 13 GB） | `drosophila_connectome/data/male_cns/flat-connectome/` |
| `syn-points-male-cns-v1.0-minconf-0.5.feather.progress.json` | 8,248 B | 同上 |

## 2. 冗余性证明（删除前验证）

**同一数据在原始位置**：`male_cns/flat-connectome/syn-points-male-cns-v1.0-minconf-0.5.feather`（顶层原始数据目录，`DATA_MANIFEST.json` root 指向）。

- **大小一致**：两者均为 13,061,489,098 B。
- **内容一致（抽样哈希）**：5 点采样（头/1/4/1/2/3/4/尾，各 1MB）SHA-256 前缀均为 `dd0886c5225f98dc`。
- **佐证**：`CONSOLIDATION_REPORT.md` 已记录"与顶层 male_cns 逐字节相同的副本（抽样 3 件 sha256 全同）"。

## 3. 无运行引用证明

| 检查项 | 结果 | 证据 |
|---|---|---|
| MCP `config.json` `data_dir` | 指向顶层 `male_cns`，非副本 | `"data_dir": "C:/Users/xing/Desktop/flybrain-connectome/male_cns"` |
| MCP `core.py` 默认 `DATA_DIR` | 解析为 `flybrain-connectome-mcp/data/male_cns`（无 flat-connectome，非副本） | `os.environ.get("FLYBRAIN_DATA_DIR", ...)` 默认值 |
| `DATA_MANIFEST.json` | root=顶层 `male_cns`；files 中 0 个引用 drosophila | root 字段 + files 检索 |
| `CONSOLIDATION_REPORT.md:98` | 明确"遗留：项目还在旧工作区时的老位置，现无代码引用" | 原文 |
| `drosophila_connectome/scripts/*.py` | `data/male_cns` 为取数脚本默认输出/注释，非 MCP 运行时依赖 | `fetch_malecns.py` 默认 `../data/male_cns/flat-connectome` |

**结论**：该副本为**历史遗留下载副本**，原始数据在顶层 `male_cns/` 完整可用，MCP 服务不读取此副本。删除安全。

## 4. 风险与处置

- **不可逆**：删除后不可恢复（除非重新下载 13GB，耗时/带宽成本）。
- **处置**：按任务书批准执行删除；保留 `fetch_malecns.py` 取数脚本（如需可重新下载）。
- **诚实边界**：删除仅回收磁盘空间，不影响任何功能/数据资产（原始 `male_cns/` 保留）。

## 5. 执行记录（2026-11-03 05:46）

- **删除时间**：2026-11-03 05:46:58（Asia/Shanghai）
- **删除方式**：`rm -rf drosophila_connectome/data/male_cns/`（退出码 0）
- **完整 SHA-256（删除前计算）**：`c16b1b63186c4d4f28939decea7444451f0f5f6f7ef1bb5dab5b2a7058f8f284`
- **文件大小**：13,061,489,098 B（≈12.2 GiB）
- **删除后验证**：`drosophila_connectome/data/male_cns/` 目录不存在（已删除）；`drosophila_connectome/data/` 现为空
- **授权**：用户确认删除（ask_user 卡片，2026-11-03）；任务书已批准（Chief m00027 转达用户已批四项）
- **原始数据保留**：顶层 `male_cns/flat-connectome/syn-points-male-cns-v1.0-minconf-0.5.feather`（13,061,489,098 B）在原始位置完整可用

---

*记录人：FlyBrain（DEV）· 2026-11-03*
