"""One-off: render the digital-life positioning report to HTML."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_doc import main  # noqa: E402

sys.exit(main([
    "docs/DIGITAL_LIFE_POSITIONING_2026-10-09.md",
    "--sub", "结合谷歌「计算生命」实验（arXiv:2406.19108，随机程序原始汤中自发涌现自我复制器）",
    "--pill", "2026-10-10 · 第三版",
    "--pill", "基线 v2.52.0",
    "--pill", "门禁 quick 20/20 · full 23/23",
    "--pill", "116 单元 · 66 连接类型 · 83 端口",
    "--pill", "T3 已解锁 12+7+4 规则",
    "--pill", "故障隔离 92.6%",
    "--foot", "定位文档 · 非实测报告 · 谷歌数字来自 arXiv:2406.19108，非本项目实测，对外引用前须核对原文",
]))
