"""One-off: render the comprehensive assessment & enhancement report (2026-10-16) to HTML."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_doc import main  # noqa: E402

BANNER = (
    "本报告全部数字为现场实测（门禁 47/47 PASS）· metrics_fork 三命令实测失败见 §三 · "
    "外部文献与竞品引用前须核对原始出处 · 上一轮报告见 docs/NEXT_STAGE_VISION_EPE_2026-10-16.md"
)

sys.exit(main([
    "docs/PROJECT_ASSESSMENT_AND_ENHANCEMENT_2026-10-16.md",
    "--sub", "全量扫描 · 完整性/先进性评估 · 国际化定位与国际竞品 · 技术壁垒深挖 · 前沿融合跟踪 · 提升方案 · SCI 阶段判定",
    "--pill", "2026-10-16",
    "--pill", "基线 v2.92.0",
    "--pill", "门禁 47/47 PASS",
    "--pill", "新发现：metrics_fork 不可复现",
    "--pill", "可复现层 35/100（新降）",
    "--pill", "C3 跨族 AUC 0.73–1.00",
    "--pill", "C1 cell 密化 FAIL",
    "--pill", "同期竞品 RAGWarrant（2026-09）",
    "--pill", "SCI：差一条门禁",
    "--foot", BANNER,
]))
