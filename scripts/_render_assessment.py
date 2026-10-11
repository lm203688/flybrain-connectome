"""One-off: render the comprehensive assessment to HTML."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_doc import main  # noqa: E402

sys.exit(main([
    "docs/COMPREHENSIVE_ASSESSMENT_2026-10-10.md",
    "--sub", "完整性 · 可行性 · 前瞻性 · 技术壁垒 —— 结合虚拟生物生态市场、开源进展与专家视角",
    "--pill", "2026-10-10",
    "--pill", "基线 v2.58.0",
    "--pill", "门禁实测 28/28 PASS",
    "--pill", "116 单元 · 66 连接 · 83 端口",
    "--pill", "综合 75.65 / 100",
    "--pill", "故障隔离 92.6%",
    "--foot", "评估文档 · 评分为判断值非测量值（方法见附录）· 外部数据来源强度不一，引用前须核对原始出处",
]))
