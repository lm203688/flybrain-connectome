# flybrain-connectome 项目史记

> 记录果蝇神经元方向的完整来龙去脉：为什么做、走了哪几条路、踩了什么坑、
> 哪些数字是真实的。原始工作记忆留档在 `ops/2026-08-31-workspace/memory-archive/`。
>
> 时间线：2026-09-15 起，共 7 轮。

---

## 第 0 轮 · 起点问题

用户问：「果蝇神经元开源模型能不能用来训练小模型？」→ 很快转成
「帮我下载果蝇神经元开源项目，以后可以用」。

**决定性澄清（决定了后面所有路线）**：

- **连接组 ≠ 训练好的权重。** MaleCNS v1.0（2026-09-03 Cell，166,700 神经元 /
  1.25 亿突触 / 11,691 细胞类型，CC-BY）与 FlyWire（2024 Nature 雌性脑，139,255
  神经元 / 5,450 万突触）都是**接线图**，不是模型权重。
- **「果蝇玩游戏」的真实机制**：连接组只提供 ①拓扑 ②权重(突触数) ③符号(递质定兴奋/抑制)；
  使用者自己补 ④LIF 神经元动力学 ⑤感官编码器 ⑥运动解码器 ⑦身体+物理环境。
  **无反向传播**——网络是「读」出来的，被调的是输入/输出接口。
- **与 minimind 不可对接**：LLM(文本 token/Transformer/反传) vs SNN(脉冲/LIF/连接组直给权重)，
  喂突触做反传无物理意义。
- **各自的水分**（诚实记录）：NeuroCraft Fly 动作程序是人写的；Flyhard 学转方向盘为真但
  指令是脚本、未接视觉；Beat Saber 是复现录像；Doom 版自报三道门全失败；
  Eon「多行为大脑上传」底层是 FlyWire + NeuroMechFly v2 身体，属营销发布。

---

## 第 1 轮 · 取数与下载（2026-09-15）

- `scripts/fetch_connectome.py` —— GCS JSON API 匿名批量下载器，纯标准库，免 gsutil/gcloud。
- `download_windows.bat` / `download_linux.sh` —— 一键下载。
- 明确「下载 vs 连接」：neuPrint API = 数据库查询接口（需 token，取子集）；
  GCS 桶 = 对象存储文件堆（匿名可下，适合自建库全量统计）。
  **桶不是活服务；所有流程都是「取数 → 落本地 → 转矩阵 → 跑」。**
- 分级下载（避免下 29.2 GB）：做知识语料只需 4 个文件 / 1.8 GB
  （body-annotations 13.8MB、body-neurotransmitters 41.3MB、body-stats 742MB、
  connectome-weights 1002MB）。

---

## 第 2 轮 · 零 GPU 零成本路线（2026-09-15）

- 官方权重免费可得：ModelScope `gongjy/minimind-3-pytorch` 的 `pretrain_768.pth`
  无缺失键 → **预训练可整个跳过**；模型实际 **63.91M 参数**（不是文档说的 26M）。
- CPU 基准（本机 AMD Ryzen AI MAX+ 395 / 32 线程）：单步 1.99s（batch4×seq768）
  → **1544 tokens/秒**；2000 条语料 × 3 epoch ≈ **26 分钟**；全量预训练 ≈ 72h（不划算）。
- **CPU 真实领域 SFT 已跑通**：官方权重 + 果蝇脑科学种子语料，loss **4.65→3.81**，
  全程无 GPU。
- 免费算力实测情报：腾讯云 Cloud Studio 10000 分钟/月 T4 首选；
  Kaggle 30h/周；魔搭 36h/月；天池 60h；**飞桨 AI Studio 仅限 PaddlePaddle，
  跑 PyTorch 会被 kill → MiniMind 不可用**。
- 产出：`minimind/FREE_PATH.md`、`bench_cpu.py`、`run_domain_sft_cpu.bat`。

---

## 第 3 轮 · 下载提速 + 真实统计（2026-09-15）

三个真实 bug（都已修复，值得跨项目复用）：

1. **`os.pwrite` 在 Windows 不存在** → 改每线程独立句柄 `seek`+`write`
   （文件指针 per-handle，并发写不同偏移安全）。
2. **只比 size 不足以判完整** → 遇到两种坏法：「字节数对但内容坏」与
   「字节数偏大且首部 magic 正常」（残留进程用 `ab` 追加，多出 25MB = 3 个 8MB 块）。
   解法：`feather_ok()` 同时查**首尾 magic**（Feather v1 `FEA1`；v2/Arrow IPC 首尾 `ARROW1`，
   尾部必须落在最后 6 字节）。
3. **提速关键**：单连接 GCS 被限速 ~23 KB/s；改 12 并发分块（8MB/块）+ Range 后
   实测 **2.2–5.7 MB/s（约 100–240 倍）**，1.8GB 从「几小时到一天」降到约 10 分钟。

真实统计（落 `data/male_cns/stats.json`）：标注表 211,577 行 × 36 列；
神经元 **166,700**；细胞类型 11,751 种；超类 27 个；递质表 1,835,518 行但只有
**187,016** 条能映射到已标注神经元。
递质分布：ACh 55.7% / Glu 15.7% / unclear 12.1% / GABA 11.9% / 组胺 4.3% / DA 0.2%。
超类 Top5：ol_intrinsic 89,403 (53.6%)、cb_intrinsic 32,164、vnc_intrinsic 13,161、
visual_projection 9,201、vnc_sensory 6,370。左右对称 L 75,215 : R 75,119 : M 392。

---

## 第 4 轮 · 口径收敛（关键，2026-09-15）

**连接表口径必须收敛，否则数字全错**——这是全项目最重要的技术结论。

- 连接表全表 pre 有 183 万 body、post 有 **8,758 万** body（大量未注释碎片）。
- 全表口径：151,856,684 边 / 311,833,243 突触 ← **无物理意义，不能引用**
- **真神经元子图口径：25,582,938 边 / 124,177,617 突触**
  （上游 165,480 / 下游 166,330）
- **124,177,617 ≈ 1.24 亿，与论文 ~1.25 亿对上 → 口径收敛正确、数据可靠**

其他实测：平均每神经元输出 750.4 / 输入 746.6 突触；连接强度极长尾
（一对神经元间突触数中位数仅 **2**，p90=10、p99=46、p99.9=139）。

枢纽 Top4（输出突触）：10009 CT1 140,897｜10157 CT1 112,796｜**10977 APL 107,649**｜
**10540 APL 102,263**。**完美左右成对**；**APL 被纯数据驱动顶到第 3/4 名**
——它是蘑菇体那对著名巨型 GABA 能反馈神经元，构成极强的数据可靠性交叉验证。

---

## 第 5 轮 · 语料工程（2026-09-15）

- `scripts/build_connectivity_facts.py`：全向量化流式扫 1GB 连接表（两次，33GB 内存安全）
  → `connectivity_facts.json`（37–39KB，27×27 跨超类投射矩阵 + 顶级枢纽靶点）。
  **总突触重算 = 124,177,617，与两者完全一致 → 数据自洽校验通过。**
- `scripts/build_corpus_v2.py` → `dataset/flybrain_sft_generated.jsonl` **604 条**
  （中文 404 / 英文 200），0 坏行，全部事实可溯源、抽验零编造。
- 关键事实：跨脑区投射以同脑区内回路为主（ol→ol 28.7%、cb→cb 27.7%）；
  CT1 最强下游 LT33（288 突触），**APL 最强下游 DPM（711 突触，符合文献）**。

踩坑：Windows 版 Python 不认 `/c/...` POSIX 路径（Git Bash 认但 `.exe` 不认）
→ 一律用 `C:/...`；pyarrow 25 无 `feather.FeatherReader` → 用
`pa.ipc.open_file().get_batch(i)` 流式；`np.add.at` 对 2D 用 1D 扁平索引越界
→ 先 `.ravel()`。

**当时状态：「怎么玩」尚未定方向**（五候选：领域 Agent / MCP 工具 / 可视化 / 科普内容 / 仿真）。

---

## 第 6 轮 · 定位收敛：连接组即服务 + SwarmLabs 集成 + 基地化（2026-09-16）

用户四项指令定了项目的形态：

1. SwarmLabs 改动文件放桌面 → 后来收进基地；
2. **连接组即服务（API）不并入 SwarmLabs**——保持独立项目，**apikey 跨项目支援**；
3. 整个项目迁到桌面基础文件夹；
4. 实施 HTTP API 开机自启 + `export_motifs` 实时拉取工具。

### 交付

- `mcp_connectome/server.py`：MCP stdio 服务（零第三方 SDK，12 工具），新增
  **`export_swarm_motifs`**（`refresh=true` 可先重跑抽取）。
- `mcp_connectome/api_server.py` + `run_api.py` + `start_api_autostart.bat`：
  HTTP API（127.0.0.1:8799，Bearer 鉴权）。
  **沙箱坑**：`schtasks.exe` 被黑名单拦截、`Register-ScheduledTask` 需管理员、
  `WScript.Shell` COM 被拦 → 改走 **HKCU Run 注册表项**登录自启。
- `extract_motifs.py` → `motifs/swarm_agent_topology_motifs.json`：三个 motif
  - `inhibitory_hub`：APL body 10540，fan_out 102,263，APL→DPM 711
  - `reservoir_smallworld`：fanout 101–1000 实测 **49.36%**，均值 744.9
  - `recurrent_feedback`：ol_intrinsic 自循环 28.74%、cb_intrinsic 27.67%
- `motifs/flybrain_connectome_client.py`：drop-in 客户端 +
  `build_agent_topology(motif, K)`；把硬编码 dev key 改成 `FLYBRAIN_API_KEY` 环境变量
  （守「密钥不进 git」）。
- **C1 `synthetic_bio_topology.py`**：用 motif 组合出「虚拟生物形态」
  （`design_organism(spec)` / `evolve_organism(target)` / `render_html(...)`），
  零依赖力导向 SVG 预览。实测：样例 29 节点/16 边；进化到 39 节点（目标 40，err=1）。

### 数据独立化 + 基地化

- 数据稳定副本 + `DATA_MANIFEST.json`（逐文件 size+sha256）；
  robocopy `/COPYALL` 因需管理员审计权限失败 → 改 `/COPY:DAT`。
- 迁移到 `C:\Users\xing\Desktop\flybrain-connectome\`（含 `male_cns`、`DATA_MANIFEST.json`、
  `drosophila_connectome`、`flybrain-connectome-mcp`）；旧 `C:\Users\xing\data\flybrain-connectome`
  已清空删除；`~/.workbuddy/mcp.json` 的 `drosophila-connectome` 条目改指桌面新路径。

### 诚实校正（本轮的自我纠错）

- 早期记忆里「fanout 101–1000 约占 75%」是估算；**实算 49.36%**，以实算为准。
- APL 的 `neurotransmitter` 字段在数据集里为空，"GABAergic" 来自文献非文件标注。
- 「蜂群科研反馈说数据目录缺失」→ 实为**配置仍指向已删旧路径**，数据一直在桌面；
  已修正文档与配置对齐。

### 环境坑（本项目高频踩）

- Bash shim 坏（`dirname: command not found`、`cd: null directory`）→ 必须先
  `export PATH="/c/.../PortableGit/.../usr/bin:...:$PATH"`。
- 工具报 `Parameter expected string, but received undefined` 时**先自查参数名**
  （曾把 `command` 写成 `arguments`，却误判为「环境全线瘫痪」）。
- 后台任务在 shell 被中断时会被杀 → 用「可续传脚本 + 一次性兜底 automation」组合。

---

## 第 7 轮 · A/B 链路落地（2026-09-17，本轮）

把「生成器」和「服务」真正接上，并让产物直接能被 SwarmLabs 吃掉。

### A —— C1 运行时调 API 的 `export_swarm_motifs`，快照仅作离线兜底

- `--motif-source api|auto|local`：
  `api` 硬门禁（拉不到即非 0 退出，不静默降级）；`auto` 服务 → API 热缓存 → 快照逐级回退；
  `local` 完全离线。
- 产物带 `motif_provenance`：`mode` / `served_from` / `doc_sha256` /
  `motif_generated_utc` / `fallback_reason` → **任何拓扑都能追溯到「实时还是冻结」**。
- 客户端补齐 `export_swarm_motifs()` + `FlybrainUnavailable` 语义化异常；
  typed helper 改为返回**解包后的 result**（`711` 而不是信封）。

实测结论：
| 场景 | 结果 |
|---|---|
| `api` + 服务在线 | `mode=api`，sha256 与快照一致 → **两路同源** |
| `auto` + 服务在线、不设环境变量 | `mode=api` ✓（key 自动取自同机 config → 默认即走实时） |
| `api` + `--refresh` | 服务真的重跑抽取（40.2s），返回 `generated_utc` 更新的新文档 |
| `api` + 服务未起 | `MotifSourceError`，退出码 1（不静默降级） |
| key 错误 | 401 → **硬失败退出码 1**（配置错误不当故障处理） |
| `auto` + 服务未起（有/无缓存） | 分别 `api_cache` / `local_snapshot` + 记录回退原因 |

**一个设计决定**：`auto` 最初对 401 也回退，实测发现**默认跑会静默用旧缓存**——
key 没配就永远连不上服务，A 等于没接上。改成：401/403 判定为**配置错误**，
即使在 `auto` 下也直接抛错；并补上「同机 `config.json` 取 key」的兜底，
使默认 `auto` 在本机**开箱即走实时**（下游拿到的是客户端副本、无该文件，仍必须显式给 key）。

### B —— C1 拓扑直接吐出 SwarmLabs 可实例化 config

- C1 新增 `emit_swarmlabs_config()` → `swarmlabs/<name>.swarm.json` + `.yaml`
  （对齐 `agentteams/config/team.yaml`：leader / role_map / thresholds）。
- config 含：`agents[]`（organism role + swarm_role）、`modules[]`、
  全量带权 `edges[]`、`guardrails[]`（拓扑不变式）、`validation`、`motif_provenance`。
- SwarmLabs 侧新增 `agent_topology/load_organism_config.py`：加载 + **独立复算校验**
  + 合并 team 形状；**fail-closed**（悬空边 / 权重越界 / 正权 inhibitory /
  非自环 recurrent / leader 掉进模块内 → 抛 `SwarmConfigError` 拒绝产出）。
- 新增自研 YAML 发射器（stdlib，全字符串双引号），PyYAML round-trip 验证
  `yaml == json` 为 True。

### 归集（本轮）

把散在桌面与旧工作区的果蝇资料全部收进基地：
`ops/2026-08-31-workspace/`（25 个历史日志 + 当时工作记忆原始档）、
`archive/desktop-loose/`（硬编码 key 的老客户端、旧快照、旧集成文档）、
`integrations/swarmlabs/`（两侧一致性校验器）。
修正陈旧路径（`config.json` 的 `data_dir`、`start_api.bat`、`DATA_MANIFEST` 的 root）。

**发现并待处理**：基地内存在**两份逐字节相同的 5.63 GB 数据**
（顶层 `male_cns/` 与 `drosophila_connectome/data/male_cns/`），见
`CONSOLIDATION_REPORT.md`。
