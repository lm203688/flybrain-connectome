"""One-off: render the next-stage vision & plan (EPE) to HTML."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_doc import main  # noqa: E402

BANNER = (
    "下一阶段愿景 · 认知进度引擎（EPE）· 双轴进度为实测值（progress.json）· "
    "预注册判定见 receipts/ 与各 _f*/_r*_ 结果文件 · 外部文献引用前须核对原始出处"
)

sys.exit(main([
    "docs/NEXT_STAGE_VISION_EPE_2026-10-16.md",
    "--sub", "上一阶段完成度 · 三个改变判断的新事实（C3 正结果 / C1 关闭 / 装置≠证据）· 2026-10 前沿坐标 · EPE 愿景与 E/S/M 执行方案 · 本轮落地的双轴进度原型",
    "--pill", "2026-10-16",
    "--pill", "基线 v2.91.0",
    "--pill", "门禁 47/47 PASS",
    "--pill", "C3 跨 5 族 AUC 0.73–1.00",
    "--pill", "C1 cell 级密化 FAIL",
    "--pill", "R1 装置 V5 / 证据 E3（分歧）",
    "--pill", "愿景：认知进度引擎（EPE）",
    "--pill", "本轮落地：双轴进度 + 边界图册",
    "--foot", BANNER,
]))
