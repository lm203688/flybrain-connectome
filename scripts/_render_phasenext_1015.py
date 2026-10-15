"""One-off: render the phase-next execution plan to HTML."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_doc import main  # noqa: E402

BANNER = (
    "下一阶段执行方案 · 科技含金量重判 · 估分为判断值非测量值 · "
    "预注册实测见各 _f*/_r*_ 结果文件 · 外部文献引用前须核对原始出处"
)

sys.exit(main([
    "docs/PHASE_NEXT_EXECUTION_PLAN_2026-10-15.md",
    "--sub", "上一阶段完成度判定 · 预注册实测复盘 · 科技含金量重判 · 竞品重定位 · N1–N5 具体执行方案",
    "--pill", "2026-10-15",
    "--pill", "基线 v2.81.0",
    "--pill", "门禁复测 42/42 PASS",
    "--pill", "上一阶段任务：执行 100% / 科学目标收敛为负/弱",
    "--pill", "重判：方法学硬科技平台（非发现型）",
    "--pill", "N1 产品化 selfverify 包",
    "--foot", BANNER,
]))
