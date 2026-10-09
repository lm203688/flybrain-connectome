"""One-off: render the digital-organism design doc to HTML."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_doc import main  # noqa: E402

sys.exit(main([
    "docs/DIGITAL_ORGANISM_DESIGN_2026-10-10.md",
    "--sub", "让虚拟生物具备自我修复 / 演化 / 组合创新 / 进化四条数字生命特征，并接入 2026 前沿技术",
    "--pill", "2026-10-10",
    "--pill", "基线 v2.52.0",
    "--pill", "门禁 quick 20/20 · full 23/23",
    "--pill", "116 单元 · 66 连接 · 83 端口",
    "--pill", "T3 已解锁 12+7+4",
    "--pill", "故障隔离 92.6%",
    "--foot", "设计方案 · 非实测报告 · 外部技术来源见 §五，具体数值对外引用前须核对原文",
]))
