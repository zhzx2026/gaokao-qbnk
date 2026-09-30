#!/usr/bin/env python3
"""把诊断文件以 GitHub annotation 形式打出来（沙箱里下不到 Actions 日志，只能读 annotation）。"""
import sys

for path in sys.argv[1:]:
    try:
        t = open(path, errors="replace").read()
    except OSError:
        continue
    t = t[-12000:]
    for i in range(0, len(t), 3000):
        c = t[i:i + 3000].replace("%", "%25").replace("\r", "").replace("\n", "%0A")
        print(f"::notice title={path.split('/')[-1]} #{i // 3000}::{c}")
