#!/usr/bin/env python3
"""从中国教育在线「高考真题及答案」栏目抽取试题，输出到 data/staging/ 待人工复核。

用法：
    python3 sources/adapters/eol_zhenti.py --list-url https://gaokao.eol.cn/shiti/
    python3 sources/adapters/eol_zhenti.py --article <某篇真题页> --out data/staging/eol.jsonl

说明：
- 本适配器只做"粗抽"：按题号切分段落，产出候选记录，verification.status = single_source；
- 数学/理化公式、语文阅读材料、英语听力材料等都可能出现切分错误，**必须人工复核后**才能
  移入 data/questions/（移入后同样要通过 qbnk validate）；
- 遵守 robots.txt 与 ≥1s 限速；遇到 403/429 直接停止，不做任何绕过。
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import REPO_ROOT, polite_get, robots_allows, write_jsonl

SOURCE_ID = "eol-gaokao"
TIER = "T2"
SUBJECT_BY_KEYWORD = [("语文", "语文"), ("数学", "数学"), ("英语", "英语"), ("物理", "物理"),
                      ("化学", "化学"), ("生物", "生物"), ("政治", "政治"), ("历史", "历史"),
                      ("地理", "地理")]
PAPER_PATTERNS = [
    (r"全国\s*[IⅠ1一]\s*卷", "全国I卷"), (r"全国\s*[IⅠ]{2}\s*卷|全国\s*[IⅠ][IⅠ]\s*卷", "全国II卷"),
    (r"全国\s*甲\s*卷", "全国甲卷"), (r"全国\s*乙\s*卷", "全国乙卷"),
    (r"新课标\s*[IⅠ1]\s*卷|新高考\s*[IⅠ1]\s*卷", "新课标I卷"),
    (r"新课标\s*II\s*卷|新高考\s*II\s*卷", "新课标II卷"),
    (r"北京卷?", "北京卷"), (r"上海卷?", "上海卷"), (r"天津卷?", "天津卷"),
    (r"浙江卷?", "浙江卷"), (r"江苏卷?", "江苏卷"), (r"山东卷?", "山东卷"),
]
QUESTION_SPLIT = re.compile(r"(?m)^\s*(\d{1,2})\s*[．.、]\s*")
LINK_RE = re.compile(r'href="(https?://[^"]*?/(?:shiti|gaokao)/[^"]*?\.s?html)"')
TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S)


def text_of(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", "", raw)
    raw = re.sub(r"(?i)<br\s*/?>|</p>|</div>", "\n", raw)
    raw = re.sub(r"<[^>]+>", "", raw)
    import html as _h
    raw = _h.unescape(raw)
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t\u00a0]+", " ", raw))


def guess_meta(title: str) -> dict:
    year = None
    m = re.search(r"(20\d{2})", title)
    if m:
        year = int(m.group(1))
    subject = "其他"
    for kw, sub in SUBJECT_BY_KEYWORD:
        if kw in title:
            subject = sub
            break
    paper = "未知"
    for pat, name in PAPER_PATTERNS:
        if re.search(pat, title):
            paper = name
            break
    return {"year": year, "subject": subject, "paper": paper}


def split_questions(body: str) -> list[tuple[str, str]]:
    marks = list(QUESTION_SPLIT.finditer(body))
    if not marks:
        return []
    out = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
        out.append((m.group(1), body[m.end():end].strip()))
    return [(no, txt) for no, txt in out if len(txt) > 20]


def build_records(url: str, title: str, body: str) -> list[dict]:
    meta = guess_meta(title)
    if not meta["year"]:
        return []
    today = date.today().isoformat()
    recs = []
    for no, txt in split_questions(body):
        slug = {"全国I卷": "quanguo1", "全国II卷": "quanguo2", "全国甲卷": "quanguojia",
                "全国乙卷": "quanguoyi", "新课标I卷": "xinkebiao1", "新课标II卷": "xinkebiao2",
                "北京卷": "beijing", "上海卷": "shanghai", "天津卷": "tianjin",
                "浙江卷": "zhejiang", "江苏卷": "jiangsu", "山东卷": "shandong"}.get(meta["paper"], "eol")
        subj_code = {"语文": "yw", "数学": "sx", "英语": "yy", "物理": "wl", "化学": "hx",
                     "生物": "sw", "政治": "zz", "历史": "ls", "地理": "dl"}.get(meta["subject"], "qt")
        recs.append({
            "id": f"q-{meta['year']}-{subj_code}-{slug}-{int(no):03d}",
            "schema_version": "1.0",
            "subject": meta["subject"],
            "stage": "高考",
            "exam_type": "真题",
            "year": meta["year"],
            "region": "全国" if meta["paper"].startswith(("全国", "新课标")) else meta["paper"].replace("卷", ""),
            "paper": meta["paper"],
            "question_no": no,
            "type": "其他",
            "stem": txt,
            "answer": None,
            "answer_text": None,
            "analysis": None,
            "score": None,
            "difficulty": None,
            "knowledge_points": [],
            "tags": ["待人工复核", "eol-auto"],
            "source": {
                "source_id": SOURCE_ID,
                "name": f"中国教育在线：{title[:40]}",
                "publisher": "中国教育在线",
                "url": url,
                "tier": TIER,
                "published_at": "",
                "fetched_at": today,
                "license": "网站声明可转载，须注明出处",
                "evidence": [],
            },
            "verification": {
                "status": "single_source",
                "method": "adapter:auto-extract（未人工复核，题型/答案待补）",
                "checked_at": today,
                "notes": "自动切分结果，题型与标准答案需人工补全后才能入库",
            },
            "notes": f"页面标题：{title[:60]}",
            "created_at": today,
            "updated_at": today,
        })
    return recs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list-url", help="栏目页 URL，自动发现文章链接")
    ap.add_argument("--article", action="append", default=[], help="直接指定真题页 URL，可重复")
    ap.add_argument("--limit", type=int, default=10, help="最多抓取的文章数")
    ap.add_argument("--out", default=str(REPO_ROOT / "data/staging/eol_zhenti.jsonl"))
    args = ap.parse_args()

    articles = list(args.article)
    if args.list_url:
        if not robots_allows(args.list_url):
            print(f"✗ robots.txt 禁止抓取：{args.list_url}")
            return 1
        try:
            raw = polite_get(args.list_url)
        except Exception as e:
            print(f"✗ 抓取栏目页失败：{type(e).__name__}: {e}（本适配器需联网环境运行）")
            return 1
        seen = set()
        for u in LINK_RE.findall(raw):
            if u not in seen and u.endswith((".shtml", ".html")):
                seen.add(u)
                articles.append(u)
            if len(seen) >= args.limit:
                break

    all_recs: list[dict] = []
    for url in articles[: args.limit]:
        try:
            raw = polite_get(url)
        except Exception as e:
            print(f"  ✗ {url} → {type(e).__name__}")
            continue
        m = TITLE_RE.search(raw)
        title = (m.group(1).strip() if m else url).split("_")[0].strip()
        recs = build_records(url, title, text_of(raw))
        print(f"  {len(recs):3d} 条  {title[:50]}")
        all_recs.extend(recs)

    if not all_recs:
        print("未产出记录")
        return 1
    n = write_jsonl(Path(args.out), all_recs)
    print(f"✔ 输出 {n} 条到 {args.out}（staging，需人工复核）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
