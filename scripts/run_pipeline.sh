#!/usr/bin/env bash
# 一条龙：校验 → 统计 → 查重 → 索引 → 报告
# 用法：bash scripts/run_pipeline.sh [--fix-hash]
set -euo pipefail

cd "$(dirname "$0")/.."

PY="${PY:-python3}"
QBNK=("$PY" -m tools.qbnk.cli)

echo "==> validate"
"${QBNK[@]}" validate "$@"

echo "==> stats"
"${QBNK[@]}" stats

echo "==> dedup"
"${QBNK[@]}" dedup || echo "    （存在疑似重复，请检查上方输出；正式库不应有精确重复）"

echo "==> index"
"${QBNK[@]}" index

echo "==> report"
"${QBNK[@]}" report

echo "==> done. 报告见 reports/coverage.md、reports/provenance.md"
