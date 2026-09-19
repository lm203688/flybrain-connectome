"""
Phase 4 一键验证脚本：串起 4 个验证工具
- check_swarmlabs_sync.py（一致性体检）
- e2e_cross_domain.py（跨域任务对比）
- e2e_batch_scenarios.py（批量场景验证）
- profile_compare.py（cProfile 剖析）

用法：
  python run_phase4_checks.py                      # 跑全部
  python run_phase4_checks.py --quick              # 只跑 sync + profile
  python run_phase4_checks.py --ci                 # CI 模式：失败即退出
  python run_phase4_checks.py --mode ci            # 同 --ci
  python run_phase4_checks.py --mode full --blueprint deep_reasoning  # 完整+统计
  python run_phase4_checks.py --only sync          # 只跑 sync

期望（Phase 4 收官）：
- sync：26 organism 全 OK
- cross_domain：3 任务 × 4 配置全通过
- batch：10 场景 × 2 配置，score 100% 一致
- profile：CPU 差异 < 5%
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
PYTHON = r"C:\Users\xing\.workbuddy\binaries\python\envs\minimind\Scripts\python.exe"

SCRIPTS = {
    "sync": ("check_swarmlabs_sync.py", "SwarmLabs 一致性体检"),
    "cross_domain": ("e2e_cross_domain.py", "跨域任务对比（3 任务 × 4 配置）"),
    "batch": ("e2e_batch_scenarios.py", "批量场景验证（10 场景 × 2 配置）"),
    "batch_stats": ("e2e_batch_stats.py", "批量统计显著性（5 场景 × 3 轮）"),
    "profile": ("profile_compare.py", "cProfile 剖析（CPU 差异）"),
}


def run_script(name, desc, blueprint=None):
    """执行一个脚本，返回 (returncode, elapsed, output_tail)"""
    path = HERE / name
    if not path.exists():
        return 999, 0.0, f"NOT FOUND: {name}"
    print(f"\n{'='*70}")
    print(f"[{name}] {desc}")
    print(f"{'='*70}")
    t0 = time.time()

    cmd = [PYTHON, str(path)]
    # batch 类脚本支持 --blueprint 参数
    if blueprint and name in ("e2e_batch_scenarios.py", "e2e_batch_stats.py"):
        cmd.append(f"--blueprint")
        cmd.append(blueprint)

    r = subprocess.run(
        cmd,
        capture_output=True, text=True,
        cwd=str(HERE.parent.parent),
        timeout=900,
    )
    elapsed = time.time() - t0
    # 保留最后 20 行输出
    out = r.stdout.splitlines()
    err = r.stderr.splitlines()
    tail = "\n".join(out[-20:] + err[-10:])
    return r.returncode, elapsed, tail


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true",
                    help="只跑 sync + profile")
    ap.add_argument("--ci", action="store_true",
                    help="CI 模式：失败即退出")
    ap.add_argument("--mode", choices=["quick", "ci", "full"],
                    help="验证模式（等同 --quick / --ci / 全量）")
    ap.add_argument("--only", choices=list(SCRIPTS.keys()),
                    help="只跑指定脚本")
    ap.add_argument("--blueprint", default=None,
                    help="batch 验证使用的蓝图名称（默认 deep_reasoning）")
    args = ap.parse_args()

    # --mode 映射
    if args.mode == "quick":
        args.quick = True
    elif args.mode == "ci":
        args.ci = True

    blueprint = args.blueprint or "deep_reasoning"

    if args.only:
        to_run = [args.only]
    elif args.quick:
        to_run = ["sync", "profile"]
    elif args.ci:
        to_run = ["sync", "cross_domain", "batch", "profile"]
    else:
        to_run = list(SCRIPTS.keys())  # full 模式：全部

    results = []
    for name in to_run:
        script, desc = SCRIPTS[name]
        rc, elapsed, tail = run_script(script, desc, blueprint)
        results.append((name, rc, elapsed, tail))
        print(f"\n[{name}] rc={rc}  elapsed={elapsed:.1f}s")
        print(tail[-500:])
        if args.ci and rc != 0:
            print(f"\n❌ CI 失败：{name} rc={rc}")
            sys.exit(rc)

    # 汇总
    print(f"\n{'='*70}")
    print("汇总")
    print(f"{'='*70}")
    all_ok = True
    for name, rc, elapsed, _ in results:
        status = "✅" if rc == 0 else "❌"
        print(f"  {status} {name}: rc={rc} ({elapsed:.1f}s)")
        if rc != 0:
            all_ok = False

    if all_ok:
        print(f"\n✅ 全部通过（{len(results)} 项）")
        sys.exit(0)
    else:
        print(f"\n❌ 有失败项")
        sys.exit(1)


if __name__ == "__main__":
    main()
