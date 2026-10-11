"""One-off: render the research deepening plan to HTML."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_doc import main  # noqa: E402

sys.exit(main([
    "docs/RESEARCH_DEEPENING_PLAN_2026-10-10.md",
    "--sub", "聚焦项目本身的科研技术研发 · 论文后压（触发条件 1.5/5，阈值 4/5 且必须含 T1+T5）",
    "--pill", "2026-10-10 修订版",
    "--pill", "基线 v2.58.0",
    "--pill", "门禁 28/28 PASS",
    "--pill", "6 条科研命题",
    "--pill", "L3 理论层 = 分水岭",
    "--pill", "论文触发条件 1.5/5",
    "--foot", "科研路线方案 · 论文与竞赛已移出路线，改为触发条件（§七）· 六条命题均为待验",
]))
