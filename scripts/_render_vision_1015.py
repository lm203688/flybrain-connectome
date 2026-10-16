"""One-off: render the next-stage vision & plan (VRO) to HTML."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_doc import main  # noqa: E402

BANNER = (
    "下一阶段愿景 · 可验证研究对象（VRO）协议 · 估分为判断值非测量值 · "
    "预注册实测见各 _f*/_r*_ 结果文件 · 外部文献引用前须核对原始出处"
)

sys.exit(main([
    "docs/NEXT_STAGE_VISION_AND_PLAN_2026-10-15.md",
    "--sub", "上一阶段完成度 · 三条 2026 前沿轴对标 · 远超市场的 VRO 愿景 · S/C/F 三阶段执行方案 · 本轮落地的命题图与 Gate 48",
    "--pill", "2026-10-15",
    "--pill", "基线 v2.85.0",
    "--pill", "门禁 42/42 PASS",
    "--pill", "A 面：方法学基础设施（国际前列）",
    "--pill", "B 面：发现已被预注册证伪",
    "--pill", "愿景：可执行认识论 / VRO 协议",
    "--pill", "本轮落地：命题图 + Gate 48",
    "--foot", BANNER,
]))
