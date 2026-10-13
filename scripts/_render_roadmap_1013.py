"""One-off: render the inner-strength roadmap (and re-render the deep-dive report) to HTML."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_doc import main  # noqa: E402

rc = main([
    "docs/INNER_STRENGTH_ROADMAP_V2_2026-10-13.md",
    "--sub", "私仓优先 · 自验证为主 · 技术硬能力 · 技术壁垒 · 公开门槛",
    "--pill", "2026-10-13",
    "--pill", "基线 v2.66.0",
    "--pill", "门禁实测 33/33 PASS",
    "--pill", "自验证成熟度 V0–V5",
    "--pill", "本阶段目标：V2 → V3",
    "--pill", "公开门槛 G1–G8",
    "--foot", "路线图活文档 · 每条交付须有脚本+数字+门禁三重证据 · 战略前提由用户 2026-10-13 拍板",
])
if rc != 0:
    sys.exit(rc)

sys.exit(main([
    "docs/PROJECT_DEEP_DIVE_AND_ENHANCEMENT_2026-10-13.md",
    "--sub", "完整性 · 科学先进性 · 国际化定位 · 国际竞品 · 技术壁垒与技术深度 · 最新科技融合",
    "--pill", "2026-10-13",
    "--pill", "基线 v2.66.0",
    "--pill", "门禁实测 33/33 PASS",
    "--pill", "200 文件 · 78.3k 行 · 116 单元 · 47 工具",
    "--pill", "新发现：隔离效应是阶跃函数",
    "--pill", "战略：私仓优先 · 公开仓后置",
    "--foot", "评估文档 · 评分为判断值非测量值（方法见附录 A）· 外部数据来源强度不一，引用前须核对原始出处",
]))
