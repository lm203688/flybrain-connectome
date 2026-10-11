"""One-off: render the scan & upgrade report to HTML."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_doc import main  # noqa: E402

sys.exit(main([
    "docs/SCAN_AND_UPGRADE_2026-10-11.md",
    "--sub", "v2.60.0 实测复核 · 核心目标对标 · 完成度判定 · 国际竞品与前沿对标 · 全板块提升建议",
    "--pill", "2026-10-11",
    "--pill", "基线 v2.60.0",
    "--pill", "门禁 26/29 PASS（3 项报红）",
    "--pill", "47 MCP 工具",
    "--pill", "综合 76.30 / 100",
    "--pill", "P1 结果经独立复核修正",
    "--foot", "评估文档 · 全部数字本次实测 · P1 结论已独立复核并提出修正 · 外部数据来源强度不一",
]))
