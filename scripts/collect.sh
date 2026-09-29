#!/usr/bin/env bash
# 跑需要联网的采集适配器，产出落到 data/staging/（待人工复核）。
# 主要在 GitHub Actions 里跑（见 .github/workflows/collect.yml），本地有网时也能跑。
#
# 用法：
#   bash scripts/collect.sh            # 跑全部（dxsbb + eol）
#   bash scripts/collect.sh dxsbb      # 只跑其中一个
#   EOL_LIMIT=50 bash scripts/collect.sh eol
set -uo pipefail

cd "$(dirname "$0")/.."

PY="${PY:-python3}"
ADAPTERS="${1:-all}"
EOL_LIMIT="${EOL_LIMIT:-30}"
EOL_LIST_URL="${EOL_LIST_URL:-https://gaokao.eol.cn/shiti/}"
mkdir -p data/staging

run() {
  echo "==> $*"
  if ! "$@"; then
    echo "    ⚠ 该适配器本轮未产出记录（详见上方日志）；"
    echo "      常见原因：源站改版/限流/robots 禁止，或该栏目当前没有新内容。"
  fi
}

case "$ADAPTERS" in
  all|dxsbb)
    run "$PY" sources/adapters/dxsbb_zuowen.py --out data/staging/zuowen_dxsbb.jsonl
    [ "$ADAPTERS" = "all" ] || exit 0
    ;&
  all|eol)
    run "$PY" sources/adapters/eol_zhenti.py --list-url "$EOL_LIST_URL" \
        --limit "$EOL_LIMIT" --out data/staging/eol_zhenti.jsonl
    ;;
  *)
    echo "未知适配器：$ADAPTERS（可选：all / dxsbb / eol）" >&2
    exit 2
    ;;
esac

echo "==> check-staging"
"$PY" -m tools.qbnk.cli check-staging
status=$?

echo "==> 产出"
git status --porcelain data/staging || true
exit $status
