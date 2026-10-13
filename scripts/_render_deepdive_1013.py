"""One-off: render the second-round deep-dive report to HTML."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_doc import main  # noqa: E402

sys.exit(main([
    "docs/PROJECT_DEEP_DIVE_AND_ENHANCEMENT_2026-10-13.md",
    "--sub", "完整性 · 科学先进性 · 国际化定位 · 国际竞品 · 技术壁垒与技术深度 · 最新科技融合",
    "--pill", "2026-10-13",
    "--pill", "基线 v2.66.0",
    "--pill", "门禁实测 33/33 PASS",
    "--pill", "200 文件 · 78.3k 行 · 116 单元 · 47 工具",
    "--pill", "新发现：隔离效应是阶跃函数",
    "--pill", "SCI 判定：仍未达标（素材约 85%）",
    "--foot", "评估文档 · 评分为判断值非测量值（方法见附录 A）· 外部数据来源强度不一，引用前须核对原始出处",
]))
