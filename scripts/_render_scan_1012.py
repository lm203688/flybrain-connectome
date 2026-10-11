"""One-off: render the SCI-readiness & enhancement report to HTML."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_doc import main  # noqa: E402

sys.exit(main([
    "docs/SCI_READINESS_AND_ENHANCEMENT_2026-10-12.md",
    "--sub", "完整性 · 科学先进性 · 国际化定位 · 国际竞品 · 技术壁垒 · 技术融合 · SCI 阶段判定",
    "--pill", "2026-10-12",
    "--pill", "基线 v2.65.0",
    "--pill", "门禁实测 32/32 PASS",
    "--pill", "116 单元 · 47 工具 · 77.6k 行",
    "--pill", "故障隔离 92.6%",
    "--pill", "SCI 判定：未达标（素材约 80%）",
    "--foot", "评估文档 · 评分为判断值非测量值（方法见附录 A）· 外部数据来源强度不一，引用前须核对原始出处",
]))
