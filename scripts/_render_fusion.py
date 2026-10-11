"""One-off: render the open-source fusion report to HTML."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_doc import main  # noqa: E402

sys.exit(main([
    "docs/OPEN_SOURCE_FUSION_2026-10-11.md",
    "--sub", "判据模型 · 图基础模型 · 自进化框架 · 小模型降本 —— 围绕核心目标的开源技术融合梳理",
    "--pill", "2026-10-11",
    "--pill", "基线 v2.60.0",
    "--pill", "6 类可融合技术",
    "--pill", "ROI 最高：小模型降本 5.0",
    "--pill", "已用 JEV / Laya 421M",
    "--foot", "技术融合评估 · 外部技术落地前须核对原始仓库与许可证 · 任何提升须由实验给出",
]))
