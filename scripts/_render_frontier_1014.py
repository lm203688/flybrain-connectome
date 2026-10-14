"""One-off: render the frontier-value enhancement plan (V2) and pre-registration protocol to HTML."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_doc import main  # noqa: E402

BANNER = (
    "前沿对接 · 技术提升落地 · 价值证实途径 · 评估为判断值非测量值 · "
    "外部文献引用前须核对原始出处"
)

rc = main([
    "docs/FRONTIER_VALUE_ENHANCEMENT_2026-10-14.md",
    "--sub", "仿生学 / 神经网络 / 人工智能 三轴前沿坐标 · F1–F8 技术提升清单 · 阶段 A/B/C 落地 · 五级证实阶梯",
    "--pill", "2026-10-14 (V2)",
    "--pill", "基线 v2.69.0",
    "--pill", "门禁实测 37/37 PASS",
    "--pill", "R1 机制救回 AUC=0.7754",
    "--pill", "本轮新发现：恢复分量 64% 为 0",
    "--pill", "配套预注册协议 v1",
    "--foot", BANNER,
])

if rc:
    sys.exit(rc)

sys.exit(main([
    "docs/PREREGISTRATION_PROTOCOL_v1.md",
    "--sub", "PR-1 前瞻性预测 · PR-2 干预/因果 · PR-3 跨图族泛化 · PR-4 恢复动力学 · 冻结规则 R-0.1–R-0.4",
    "--pill", "2026-10-14",
    "--pill", "协议 v1",
    "--pill", "框架 arXiv:2608.14894",
    "--pill", "四协议 × 四门禁",
    "--pill", "失败即发表",
    "--foot", BANNER,
]))
