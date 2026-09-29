#!/usr/bin/env python3
"""从「大学生必备网」历年高考作文汇总页抽取作文题，输出到 data/staging/ 待人工复核。

设计要点（对应 docs/sources.md 的采信流程）：
1. 该站为 T3（教育类整理稿），因此产出的记录 verification.status = single_source；
2. 输出落在 data/staging/，**不会**自动进入 data/questions/，必须人工比对后再入库；
3. 该站 2025 年北京卷存在转录错误（大作文被误填为微写作），
   因此解析器对"微写作/作文"分节失败时会直接标记 conflict 并写进 notes，提醒人工处理。

用法：
    python3 sources/adapters/dxsbb_zuowen.py                       # 抓默认四个汇总页
    python3 sources/adapters/dxsbb_zuowen.py --url <某汇总页> --out data/staging/x.jsonl
"""
from __future__ import annotations

import argparse
import html
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import REPO_ROOT, polite_get, robots_allows, write_jsonl

SOURCE_ID = "dxsbb-zuowen"
TIER = "T3"
DEFAULT_URLS = [
    ("全国卷", "https://www.dxsbb.com/news/136500.html"),
    ("北京卷", "https://www.dxsbb.com/news/116375.html"),
    ("上海卷", "https://www.dxsbb.com/news/99991.html"),
    ("天津卷", "https://www.dxsbb.com/news/116376.html"),
]

HEADING = re.compile(r"(\d{4})\s*年.{0,12}?(?:高考)?(?:作文题目|高考作文|作文)")
SUBHEAD = re.compile(r"^\s*(微写作|作文)（?(\d+分)?）?\s*$")


def html_to_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", "", raw)
    raw = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>", "\n", raw)
    raw = re.sub(r"<[^>]+>", "", raw)
    raw = html.unescape(raw)
    raw = re.sub(r"[ \t\u00a0]+", " ", raw)
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    return raw


def extract_sections(text: str) -> list[dict]:
    """按「N、YYYY年XX高考作文题目」切块，块内再按 微写作/作文 分节。"""
    marks = [(m.start(), int(m.group(1)), m.group(0)) for m in HEADING.finditer(text)]
    blocks: list[dict] = []
    for idx, (pos, year, title) in enumerate(marks):
        end = marks[idx + 1][0] if idx + 1 < len(marks) else len(text)
        body = text[pos:end].strip()
        lines = [ln.strip() for ln in body.split("\n") if ln.strip()]
        sections: list[tuple[str, str]] = []
        cur_name, cur_buf = "作文", []
        for ln in lines[1:]:
            m = SUBHEAD.match(ln)
            if m:
                if cur_buf:
                    sections.append((cur_name, "\n".join(cur_buf).strip()))
                cur_name, cur_buf = m.group(1), []
            else:
                cur_buf.append(ln)
        if cur_buf:
            sections.append((cur_name, "\n".join(cur_buf).strip()))
        if not sections:
            continue
        blocks.append({"year": year, "heading": title.strip(), "sections": sections})
    return blocks


def to_records(paper_label: str, url: str, blocks: list[dict]) -> list[dict]:
    out: list[dict] = []
    today = date.today().isoformat()
    for b in blocks:
        for i, (name, text) in enumerate(b["sections"], 1):
            if len(text) < 30:  # 太短多半是导航残留
                continue
            qtype = "微写作" if name == "微写作" else "写作"
            seq = 1 if qtype == "写作" else 2
            slug = {"全国卷": "quanguo", "北京卷": "beijing", "上海卷": "shanghai",
                    "天津卷": "tianjin"}.get(paper_label, "x")
            conflict = "两个分节内容完全相同" if (len(b["sections"]) > 1 and
                        b["sections"][0][1][:60] == b["sections"][1][1][:60]) else ""
            out.append({
                "id": f"q-{b['year']}-yw-{slug}-{seq:03d}",
                "schema_version": "1.0",
                "subject": "语文",
                "stage": "高考",
                "exam_type": "真题",
                "year": b["year"],
                "region": "全国" if paper_label == "全国卷" else paper_label.replace("卷", ""),
                "paper": paper_label,
                "type": qtype,
                "stem": text,
                "answer": None,
                "answer_text": None,
                "analysis": None,
                "score": None,
                "difficulty": None,
                "knowledge_points": ["材料作文" if qtype == "写作" else "微写作"],
                "tags": ["待人工复核", "dxsbb"],
                "source": {
                    "source_id": SOURCE_ID,
                    "name": f"历年{paper_label}高考作文题目汇总（大学生必备网）",
                    "publisher": "大学生必备网",
                    "url": url,
                    "tier": TIER,
                    "published_at": "",
                    "fetched_at": today,
                    "license": "教育类站点整理稿，转载需署名",
                    "evidence": [],
                },
                "verification": {
                    "status": "conflict" if conflict else "single_source",
                    "method": "adapter:auto-extract（未人工复核）",
                    "checked_at": today,
                    "notes": f"{conflict}；本条由适配器自动抽取，入库前须与第二个来源比对",
                },
                "notes": f"来源小标题：{b['heading'][:40]}",
                "created_at": today,
                "updated_at": today,
            })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", action="append", default=[], help="汇总页 URL，可重复；默认抓取四个已知页面")
    ap.add_argument("--out", default=str(REPO_ROOT / "data/staging/zuowen_dxsbb.jsonl"))
    args = ap.parse_args()

    targets = [(paper_label, u) for paper_label, u in DEFAULT_URLS] if not args.url else [("全国卷", u) for u in args.url]
    all_recs: list[dict] = []
    for label, url in targets:
        if not robots_allows(url):
            print(f"✗ robots.txt 禁止抓取：{url}")
            continue
        try:
            raw = polite_get(url)
        except Exception as e:
            print(f"✗ 抓取失败 {url}：{type(e).__name__}: {e}（本适配器需联网环境运行）")
            continue
        text = html_to_text(raw)
        blocks = extract_sections(text)
        recs = to_records(label, url, blocks)
        print(f"  {label} {url} → {len(recs)} 条（{len(blocks)} 个年份块）")
        all_recs.extend(recs)

    if not all_recs:
        print("未产出任何记录")
        return 1
    n = write_jsonl(Path(args.out), all_recs)
    print(f"✔ 输出 {n} 条到 {args.out}（staging，需人工复核后再移入 data/questions/）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
