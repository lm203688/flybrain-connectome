"""快速重跑 profile 对比 + 抓 routing 函数"""
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = r"C:\Users\xing\Desktop\flybrain-connectome\integrations\swarmlabs\profile_compare.py"
PYTHON = r"C:\Users\xing\.workbuddy\binaries\python\envs\minimind\Scripts\python.exe"

r = subprocess.run([PYTHON, SCRIPT], capture_output=True, text=True, timeout=300)
out = r.stdout
# 只提取 routing 相关段落
lines = out.split("\n")
print("\n".join(lines[-40:]))
