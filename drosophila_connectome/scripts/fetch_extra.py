"""MaleCNS 「扩展产物」下载器（形态学 / 突触空间数据）。

背景：
    fetch_fast.py 已经下载了「flat-connectome」4 张核心表（annotations / NT /
    body-stats / connectome-weights），共 5.63 GB，覆盖「神经元 + 突触 + 递质 +
    神经元级统计」。这是项目的核心连接组。

    MaleCNS v1.0 官方发布物还包括形态学与突触空间数据：
      - syn-partners-male-cns-v1.0-minconf-0.5.feather       (6.78 GB)  突触伙伴对 + 3D 坐标 + neuropil
      - syn-points-male-cns-v1.0-minconf-0.5.feather         (13.06 GB) 突触点 3D 坐标（与上重复）
      - tbar-neurotransmitters-male-cns-v1.0.feather         (2.65 GB)  每突触递质概率
      - skeletons-malecns/skeletons-swc/                      (~2-4 GB)  166,700 个神经元 3D 骨架 SWC
      - segmentation / EM volumes                              (数十 TB)  不做

    本脚本默认下 3 个 feather 全量（syn-partners / syn-points / tbar-nt），
    skeletons SWC 是目录结构，用 fetch_skeletons.py 单独处理。

复用：
    直接调用 fetch_fast.py 的分块多线程下载器（8MB 分块 × 8 workers + 断点续传
    + feather magic 校验 + 深度校验）。同一目录前缀 v1.0/connectome-data/flat-connectome/。

用法：
    python fetch_extra.py                                # 下默认清单（3 个 feather）
    python fetch_extra.py --only syn-points              # 只下 syn-points（子串匹配）
    python fetch_extra.py --only tbar                    # 只下 tbar-neurotransmitters
    python fetch_extra.py --only syn-partners            # 只下 syn-partners
    python fetch_extra.py --status                       # 只看进度
    python fetch_extra.py --verify                       # 深度校验（pyarrow 真解析）
    python fetch_extra.py --force                        # 强制重下（修复损坏文件）

约束（继承自 fetch_fast.py）：
    - 同一目标文件永远只允许一个进程在下载（并发写会 LZ4 损坏）
    - 启动前确认无残留：
        Get-CimInstance Win32_Process | ? {$_.CommandLine -like '*fetch_extra*'}
"""
import os
import sys

# 复用 fetch_fast.py 的下载基础设施
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import fetch_fast as ff  # noqa: E402

# ─── 扩展清单 ─────────────────────────────────────────────────────────────
# 全部在 v1.0/connectome-data/flat-connectome/ 同一 prefix 下
# fetch_fast.py 里 PREFIX 已定义好，直接指定文件名即可
EXTRA = [
    'syn-partners-male-cns-v1.0-minconf-0.5.feather',          # 6.78 GB  突触对 + neuropil
    'tbar-neurotransmitters-male-cns-v1.0.feather',             # 2.65 GB  突触级递质概率
    'syn-points-male-cns-v1.0-minconf-0.5.feather',             # 13.06 GB 突触点 3D 坐标
]

# 注：skeletons-malecns/skeletons-swc/ 是目录结构，不是单文件 feather，
#     由 drosophila_connectome/scripts/fetch_skeletons.py 单独处理。


def main():
    # 把 EXTRA 挂到 fetch_fast 的 KNOWLEDGE 上，其余逻辑全部复用
    ff.KNOWLEDGE = EXTRA
    ff.main()


if __name__ == '__main__':
    main()
