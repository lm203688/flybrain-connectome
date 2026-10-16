"""One-off: render the foundation hardening audit (2026-10-16) to HTML."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_doc import main  # noqa: E402

BANNER = (
    "地基审计 · 只查底层不谈上层 · 每条结论附文件与行号 · "
    "定义性耦合地板为真实数据洗牌 ×2000 实测 · 版本/徽章数字为现场复测"
)

sys.exit(main([
    "docs/FOUNDATION_HARDENING_AUDIT_2026-10-16.md",
    "--sub", "地基七宗罪（静默吞异常 / 度量分裂 / 命名污染 / 测试缺失 / 版本漂移 / 种子自校准 / 可复现未验证）· 承重结构六项 · K1–K10 啃硬骨头清单 · 地基成熟度 F0–F5",
    "--pill", "2026-10-16",
    "--pill", "CHANGELOG v2.94.0",
    "--pill", "pyproject 仍 2.91.0（落后 3 版）",
    "--pill", "门禁 FAIL — gate2 漂移",
    "--pill", "13 处 except Exception: pass",
    "--pill", "2 处裸 except",
    "--pill", "AUC ×10 独立实现",
    "--pill", "真单测仅 3 文件 / 250 py",
    "--pill", "地基成熟度 F2",
    "--foot", BANNER,
]))
