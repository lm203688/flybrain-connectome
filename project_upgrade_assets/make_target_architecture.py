from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT = Path(__file__).resolve().parent / "target_architecture.png"
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

fig, ax = plt.subplots(figsize=(16, 10), dpi=180)
fig.patch.set_facecolor("#F5F7FB")
ax.set_facecolor("#F5F7FB")
ax.set_xlim(0, 16)
ax.set_ylim(0, 10)
ax.axis("off")

ax.text(0.6, 9.55, "FlyBrain 目标架构：连接组约束的可验证结构实验平台", fontsize=23, weight="bold", color="#14213D")
ax.text(0.6, 9.13, "一个证据底座、一个可执行结构 IR、两条应用线；AI 提议，确定性验证，受保护数据裁决", fontsize=12.5, color="#526078")

layers = [
    (7.45, "体验层｜从问题到证据", "研究工作台   实验向导   实时轨迹   拓扑 Diff   干预控制   对比报告   一键复跑", "#E8F0FE", "#2864DC"),
    (5.85, "实验操作系统｜可信优化控制面", "预注册冻结   对照与随机化   多保真调度   Pareto 选择   Holdout 裁决   晋级 / 回滚", "#E9F7EF", "#21855C"),
    (4.25, "可执行结构 IR｜跨运行时的单一真源", "类型化节点 / 边 / 端口   状态与动力学   干预算子   度量版本   证据引用   内容哈希", "#FFF3E2", "#C66A11"),
    (2.65, "证据与运行层｜静态谱系 + 动态事实", "W3C PROV   RO-Crate / Workflow Run   OpenTelemetry   Receipt   数据与代码版本   许可策略", "#F2EAFE", "#7851A9"),
    (1.05, "数据与计算层｜版本化、可扩展", "MaleCNS / FlyWire / Worm / Larva / Zebrafish   Arrow-CSR   GNN / SNN / Agent Runtime   FlyGym", "#E8F6F8", "#167C8C"),
]
for y, title, body, face, edge in layers:
    box = FancyBboxPatch((2.15, y), 11.7, 1.08, boxstyle="round,pad=0.025,rounding_size=0.08", linewidth=1.5, edgecolor=edge, facecolor=face)
    ax.add_patch(box)
    ax.text(2.5, y + 0.72, title, fontsize=14, weight="bold", color=edge, va="center")
    ax.text(2.5, y + 0.30, body, fontsize=11.2, color="#26344D", va="center")

for y in [2.13, 3.73, 5.33, 6.93, 8.53]:
    ax.add_patch(FancyArrowPatch((8, y), (8, y + 0.48), arrowstyle="-|>", mutation_scale=16, color="#7C879D", linewidth=1.4))

# Side rails
ax.add_patch(FancyBboxPatch((0.35, 2.65), 1.35, 5.88, boxstyle="round,pad=0.03,rounding_size=0.08", facecolor="#14213D", edgecolor="#14213D"))
ax.text(1.025, 7.85, "生物数字孪生", color="white", fontsize=13, weight="bold", ha="center")
ax.text(1.025, 6.95, "神经元\n突触\n区室\n可塑性\n身体与环境", color="#D8E5FF", fontsize=11.5, ha="center", va="top", linespacing=1.7)
ax.text(1.025, 4.40, "禁止把结构\n直接等同于\n功能或智能", color="#FFD166", fontsize=11.2, weight="bold", ha="center", va="top", linespacing=1.6)

ax.add_patch(FancyBboxPatch((14.3, 2.65), 1.35, 5.88, boxstyle="round,pad=0.03,rounding_size=0.08", facecolor="#243B53", edgecolor="#243B53"))
ax.text(14.975, 7.85, "Agent 拓扑", color="white", fontsize=13, weight="bold", ha="center")
ax.text(14.975, 6.95, "角色\n消息\n状态\n工具\n恢复与审批", color="#D8E5FF", fontsize=11.5, ha="center", va="top", linespacing=1.7)
ax.text(14.975, 4.40, "通过显式映射\n验证 motif 是否\n带来任务收益", color="#FFD166", fontsize=11.2, weight="bold", ha="center", va="top", linespacing=1.6)

ax.text(0.6, 0.25, "核心边界：生物证据 ≠ Agent 任务证据；PROV 谱系 ≠ 运行日志；结构门禁通过 ≠ 科学主张成立。", fontsize=12, weight="bold", color="#A23B3B")
fig.tight_layout(pad=0.6)
fig.savefig(OUT, bbox_inches="tight", facecolor=fig.get_facecolor())
print(OUT)
