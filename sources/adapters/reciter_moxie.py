#!/usr/bin/env python3
"""把 GitHub Binkic/Reciter 的古诗文默写题库转成"隔离区"候选记录。

为什么进 data/quarantine/ 而不是 data/questions/：
- Reciter 自述资料来源为"QQ群群友搜集、百度百科、维基百科、维基文库"，属 T4（社区/UGC）；
- 每条记录没有对应到具体年份与卷别的真题出处，按 docs/sources.md 的规则不能直接入库；
- 因此统一标记 verification.status = rejected（待人工核对真题原卷后才可提升等级并移入正式库）。

用法：
    git clone --depth 1 https://github.com/Binkic/Reciter.git /tmp/Reciter
    python3 sources/adapters/reciter_moxie.py --repo /tmp/Reciter \
        --out data/quarantine/reciter_moxie.jsonl
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import REPO_ROOT, write_jsonl

SOURCE_ID = "gh-reciter"
TIER = "T4"
SOURCE_URL = "https://github.com/Binkic/Reciter"
BLANK = re.compile(r"\$(\d+)")


def convert(repo: Path) -> list[dict]:
    src = repo / "comprehensions" / "comprehensions.json"
    if not src.exists():
        raise SystemExit(f"✗ 找不到 {src}")
    data = json.loads(src.read_text(encoding="utf-8"))
    items = data.get("comprehensions", [])
    today = date.today().isoformat()
    out: list[dict] = []
    for i, it in enumerate(items, 1):
        content = it.get("content", "")
        answers = it.get("answer", []) or []
        stem = BLANK.sub(lambda m: "____", content)
        out.append({
            "id": f"q-0000-yw-reciter-{i:04d}",
            "schema_version": "1.0",
            "subject": "语文",
            "stage": "高考",
            "exam_type": "其他",
            "year": 0,  # 0 = 年份/出处未知
            "region": "未知",
            "paper": "未知",
            "type": "古诗文默写",
            "stem": stem,
            "answer": answers,
            "answer_text": "；".join(answers),
            "analysis": None,
            "score": None,
            "difficulty": None,
            "knowledge_points": ["理解性默写", it.get("title", "")],
            "tags": ["隔离区", "T4", "待核验真题出处"],
            "source": {
                "source_id": SOURCE_ID,
                "name": "GitHub Binkic/Reciter：古诗文默写结构化题库（理解性默写）",
                "publisher": "Binkic 等（MIT）",
                "url": f"{SOURCE_URL}/blob/main/comprehensions/comprehensions.json",
                "tier": TIER,
                "published_at": "",
                "fetched_at": today,
                "license": "MIT（数据组织）；内容源自社区收集与百科",
                "evidence": [],
            },
            "verification": {
                "status": "rejected",
                "method": "T4-source-pending-review",
                "checked_at": today,
                "notes": "出处为社区整理，未核对到具体年份/卷别的真题原卷；核对通过前禁止使用",
            },
            "notes": f"篇目：{it.get('title','')}｜作者：{it.get('author','')}｜出处：{it.get('source','')}",
            "created_at": today,
            "updated_at": today,
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--out", default=str(REPO_ROOT / "data/quarantine/reciter_moxie.jsonl"))
    args = ap.parse_args()
    recs = convert(Path(args.repo).expanduser().resolve())
    n = write_jsonl(Path(args.out), recs)
    print(f"✔ 输出 {n} 条隔离区记录 → {args.out}")
    print("  这些记录 verification.status=rejected，不会也不允许进入 data/questions/；")
    print("  逐条核对真题原卷、补足年份/卷别并把状态改为 single_source/verified 后方可移入正式库。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
