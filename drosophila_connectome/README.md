# 果蝇神经元开源资产 · 下载与使用说明

> 建立：2026-09-15
> 目的：囤下果蝇连接组公开资产，供后续「brain-science 领域 Agent」使用
> 许可：CC-BY 4.0（MaleCNS / FlyWire 均为开放许可，可商用，需署名）

---

## 〇、下载状态（2026-09-15 实测）

存储桶匿名访问已验证可用，无需账号、无需 gcloud/gsutil。

**已验证可下载**（`scripts/fetch_malecns.py` 实测成功）：

| 文件 | 体积 | 状态 |
|---|---|---|
| `body-annotations-...minconf-0.5.feather` | 14.5 MB | ✅ 已下，实测 **211,577 行 × 36 列** |
| `body-neurotransmitters-...feather` | 43.3 MB | ✅ 已下 |
| `body-stats-...minconf-0.5.feather` | 742 MB | ⏳ 下载中 |
| `connectome-weights-...minconf-0.5.feather` | 1002 MB | ⏳ 下载中 |

**不要下全量**。`flat-connectome` 目录共 11 个文件、**29.2 GB**，但其中 24 GB 是突触级原始数据（`syn-points` 13 GB、`syn-partners` 6.8 GB 等），**只有做无身仿真才需要**。做知识问答语料只需要上面 4 个文件（1.8 GB）。

**分级下载命令**：

```bash
python scripts/fetch_malecns.py --tier knowledge   # 1.8 GB，默认，知识 Agent 够用
python scripts/fetch_malecns.py --tier simulation  # 8.8 GB，加仿真必需
python scripts/fetch_malecns.py --tier full        # 29.2 GB，全量
python scripts/fetch_malecns.py --list             # 只列清单
```

脚本特性：纯标准库（免 gcloud）、自动翻页列举、**断点续传**（用 Range 头）、失败重试、先下小文件。

---

## 一、资产清单（你要的"开源果蝇神经元"）

| 资产 | 发布 | 规模 | 获取入口 |
|---|---|---|---|
| **MaleCNS v1.0** | 2026-09-03, Cell | 166,700 神经元 / 1.25 亿突触 / 11,691 细胞类型 | `male-cns.janelia.org/download`；存储桶 `gs://flyem-male-cns/v1.0/`；neuPrint 数据集 `male-cns:v1.0` |
| **FlyWire**（雌性脑） | 2024, Nature | 139,255 神经元 / 5,450 万突触 | `flywire.ai`；neuPrint 数据集 `flywire` |
| **FlyEM hemibrain** | 2020 | 2.5 万神经元 / 2,100 万突触 | neuPrint 数据集 `hemibrain` |

上游单位：HHMI Janelia FlyEM ＋ 剑桥大学动物学系 ＋ MRC 分子生物学实验室 ＋ Google Research。

### 衍生项目（Demo / 代码，小体积，可 git clone）
| 项目 | 说明 | 仓库 |
|---|---|---|
| NeuroCraft Fly | 果蝇神经元接 Minecraft | `github.com/evnsnclr/neurocraft-fly-public` |
| Flyhard | 果蝇神经元学开车（转方向盘） | `github.com/MarkUnthank/flyhard` |
| MaleCNS 论文 / Blog | 一手资料 | `male-cns.janelia.org`、Google Research Blog |

---

## 二、它们是"怎么用"这些神经元的（机制）

**核心认知：连接组是一张接线图，不是训练好的权重，更不是语言模型。**

把连接组跑成一个"会玩游戏的果蝇"，需要七样东西：

| # | 谁提供 | 内容 |
|---|---|---|
| ① | 连接组 | 拓扑：哪个神经元连哪个 |
| ② | 连接组 | 权重：两点之间有几条突触 |
| ③ | 连接组 | 符号：兴奋 / 抑制（来自神经递质预测） |
| ④ | 你自己 | 神经元动力学模型（主流用 **LIF**，leaky integrate-and-fire） |
| ⑤ | 你自己 | 感官编码器：环境状态 → 脉冲序列 → 注入感觉神经元 |
| ⑥ | 你自己 | 运动解码器：运动神经元发放率 → 动作指令 |
| ⑦ | 你自己 | 身体 + 物理环境（MuJoCo / 游戏引擎） |

流水线：`连接组 → 建 LIF 网络 → 感官编码 → 时间步仿真(GPU, dt≈0.1–1ms) → 运动解码 → 具身闭环`

**三个反直觉点**：
1. **没有反向传播。** 突触权重直接来自连接组的突触计数，网络是"读"出来的不是"训"出来的。
2. **被调的是接口，不是脑。** 项目里"学会"的多半是感官编码 + 运动解码 + 少量阈值/读出层，不是 5000 万条连接本身。
3. **不接身体就动不起来。** 孤立跑脑只是放电图，必须闭环到环境。

**已知的"水分"（传播时被抹掉的部分）**：
- NeuroCraft Fly：动作程序是人手写的，神经活动只负责"选哪个"；**打乱连接权重后部分反应仍然存在**。
- Flyhard：保留测试 0/100 → 100/100 学转方向盘是真的，但车速与转弯指令是脚本给的，未接视觉。
- Beat Saber 版：作者承认是复现录好的动作。
- Doom 版：开发者自报视觉 / 条件反射 / 存活三道门全失败。
- Eon「首个多行为大脑上传」：底层是 **FlyWire**（不是 MaleCNS），接 NeuroMechFly v2 身体；属公司营销发布，技术细节披露不足。

---

## 二·补、数据是"连"着用，还是"下"下来用？

**结论：两条路用途不同，而且仿真必须落到本地。**

| 取数方式 | 性质 | 需要什么 | 适合 |
|---|---|---|---|
| **neuPrint API** | 数据库查询接口，按需取子集 | 注册账号 + API token | 探索、取特定细胞/回路 |
| **GCS 存储桶 `gs://`** | 对象存储（文件堆），批量下载 | 公开桶可匿名，无需鉴权 | 仿真、自建库、全量统计 |

**关键认知：存储桶不是"活的服务"，没法"连"上去跑仿真。** 没有任何项目是"实时连着"跑的，
流程一律是：取数 → 落本地 → 转矩阵 → 跑。

按数据类型细分：

| 数据类型 | 能否不下载 |
|---|---|
| EM 电镜图像体 | ✅ 可流式按需读（`cloud-volume` / Neuroglancer 按 chunk 拉） |
| 连接表（flat-connectome） | ❌ 得下成文件，或用 API 取子集后落盘 |
| 跑仿真 | ❌ 必须全量本地，转稀疏矩阵（CSR/COO）进显存 |

**为什么仿真必须本地**：LIF 步长 dt≈0.1ms，仿真 1 秒＝1 万步；每步 16.6 万神经元各自积分输入电流，
涉及约 1.25 亿条突触 → 每仿真 1 秒约 10¹² 量级乘加运算，全部要在 GPU 显存里零延迟完成。
**内循环里不可能发网络请求。**

neuPrint 取子集示例（需先注册 `neuprint.janelia.org` 拿 token）：

```python
pip install neuprint-python
from neuprint import Client, fetch_neurons, fetch_adjacencies
client = Client("https://neuprint.janelia.org", dataset="male-cns:v1.0", token=token)
neurons, syndist = fetch_neurons("DNge104")     # 取特定细胞
out_edges, _ = fetch_adjacencies("DNge104")     # 取它的下游连接
```

FlyWire 把 `dataset` 换成 `"flywire"` 即可。

---

## 三、本目录脚本会下载什么

| 目录 | 内容 | 体积量级 |
|---|---|---|
| `data/male_cns/annotations/` | 细胞类型、神经毡支配等注释表 | 小（数十 MB～百 MB） |
| `data/male_cns/connectivity/` | flat-connectome 连接表（神经元对 / 突触） | 中～大（数 GB 起） |
| `data/papers/` | 一手论文与 Blog 页面 | 小 |
| `data/demos/` | NeuroCraft Fly、Flyhard 源码 | 小 |

**明确不下载**：EM 电镜体数据（`gs://flyem-male-cns/v1.0/segmentation`、`em/` 等），PB 级，且是图像而非文本/结构化知识，对 LLM 无用途。

---

## 四、怎么跑

```bat
:: Windows
download_windows.bat
```

```bash
# Linux / macOS
bash download_linux.sh
```

脚本走 **Google Cloud Storage JSON API 匿名拉取**（`scripts/fetch_connectome.py`，纯 Python 标准库），
**不需要装 gsutil / gcloud**。公开桶可匿名下载；若报 403 说明桶策略变更，需改用 gsutil + 凭据。

先评估体积再决定是否全量下：
```bash
python scripts/fetch_connectome.py flyem-male-cns "v1.0/connectome-data/flat-connectome/" ./tmp --ext csv --dry
```

---

## 五、具体操作步骤

先分清两条**完全不同**的目标，别混：

### 路径 A：果蝇神经科学知识 Agent（推荐 —— 复用已验证链路）

目标产物：一个能回答果蝇 / 脑科学问题的**专职 Agent**（不是"会玩的果蝇"）。

| 步骤 | 做什么 | 用什么 |
|---|---|---|
| 1 取数 | 论文文档 + 细胞类型目录 + 连接统计 + Demo README | 本目录脚本 + neuPrint API |
| 2 装配料 | 转 `{"conversations":[...]}`，中英混合 | 模板见 `minimind/dataset/smoke_sft.jsonl` |
| 3 SFT | 全参微调 | `minimind/trainer/train_full_sft.py` |
| 4 导出 | HF → GGUF | `convert_to_hf.py` → `run_gguf.bat` |
| 5 接入 | 建 Ollama 模型 | `Modelfile` → `ollama create` |

**第 3–5 步的工具已全部跑通验证，真正要新做的是第 1–2 步（语料工程）。**

**第 1 步取数三条线**：
1. **论文与文档**：MaleCNS 的 Cell 论文 + 同期 3 篇论文 + bioRxiv 预印本 v2 + Google Research Blog + Janelia/neuPrint 文档 + Demo 仓库 README。
2. **结构化统计**：neuPrint API 拉 11,691 个细胞类型清单、神经毡支配、代表性回路；再自己算度数分布、rich-club 系数、蘑菇体 KC 稀疏编码率等，转成自然语言。
3. **（可选）flat-connectome 全量**，用于自己算统计。

**第 2 步装配料要点**：论文切段生成 QA 对；结构化数据用模板转自然语言；先做 500–2000 条高质量种子，别一上来堆量。

**第 3 步命令**（在 GPU 主机、且已跑完 pretrain 之后）：

```bat
cd minimind\trainer
python train_full_sft.py --data_path ../dataset/fly_brain_sft.jsonl --from_weight pretrain ^
  --epochs 3 --batch_size 16 --learning_rate 1e-5 --device cuda --dtype bfloat16
```

### 路径 B：真跑一只脉冲果蝇（另一套技术栈）

| 步骤 | 做什么 |
|---|---|
| 1 | 连表落地：neuPrint API 或 flat-connectome → 本地稀疏矩阵（CSR/COO） |
| 2 | 选 SNN 仿真器：Brian2 / NEST / GeNN，或自写 CUDA 核 |
| 3 | 建 LIF 网络：拓扑 + 权重（突触数）+ 符号（递质类型定兴奋/抑制） |
| 4 | 设计感官编码器 + 运动解码器（手写部分，也是行为成败关键） |
| 5 | 接身体：NeuroMechFly v2（MuJoCo）或游戏引擎 |
| 6 | 跑闭环并调接口 |

**路径 B 产出"行为演示"，路径 A 产出"知识问答"。** 按你的业务（brain-science 站 + 内容变现），
A 的 ROI 明显更高；B 更像研究性项目，建议 A 跑通后再评估。

---

## 五·补、为什么不能把连接组当训练权重喂给 minimind

训练范式不同：minimind 是**文本 token → Transformer → 反向传播**；果蝇仿真是**脉冲 → LIF → 连接组直给权重**。
把 1.25 亿条突触当训练数据喂进去做梯度下降，没有物理意义，也不会产出有用结果。

---

## 六、如果想真的"跑"一只脉冲果蝇

那是**另一套技术栈**（SNN 仿真，非 PyTorch Transformer），需要：
- SNN 仿真器（Brian2 / NEST / GeNN，或自写 CUDA 核）
- LIF 网络构建（由连接组拓扑 + 权重 + 递质符号）
- 身体模型（NeuroMechFly v2 / MuJoCo）或游戏引擎接口
- GPU（本机 AMD 无 NVIDIA；需在 3090/4090 主机跑）

这是独立课题，与本目录的"知识语料"用途不冲突，可并存。

---

## 七、文件清单

| 文件 | 作用 |
|---|---|
| `README.md` | 本说明 |
| `scripts/fetch_connectome.py` | GCS 匿名批量下载器（纯标准库） |
| `download_windows.bat` | Windows 一键下载 |
| `download_linux.sh` | Linux 一键下载 |
