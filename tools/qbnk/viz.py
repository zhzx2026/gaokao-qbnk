"""qbnk viz：把题库数据打包成一个**自包含**的可视化页面（site/index.html）。

不依赖 CDN / 构建工具，双击即可打开（file://），也可以 `python3 -m http.server -d site` 预览。
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import date
from pathlib import Path

from .core import (
    QUARANTINE_DIR, REPO_ROOT, iter_jsonl, load_papers, load_questions, load_registry, summarize,
)

TEMPLATE = Path(__file__).with_name("viz_template.html")
SITE_DIR = REPO_ROOT / "site"
PLACEHOLDER = "/*__QBNK_DATA__*/null"


def build_payload() -> dict:
    qs = [q for q in load_questions() if "__parse_error__" not in q]
    ps = load_papers()
    reg = load_registry()

    def src(o):
        return o.get("source") or {}

    questions = []
    for q in sorted(qs, key=lambda x: (-int(x.get("year") or 0), x["id"])):
        s, v = src(q), q.get("verification") or {}
        questions.append({
            "id": q["id"], "year": q.get("year"), "subject": q.get("subject"),
            "region": q.get("region"), "paper": q.get("paper"), "no": q.get("question_no"),
            "type": q.get("type"), "score": q.get("score"), "stem": q.get("stem"),
            "analysis": q.get("analysis"), "kp": q.get("knowledge_points") or [],
            "status": v.get("status"), "method": v.get("method"),
            "tier": s.get("tier"), "source_id": s.get("source_id"),
            "source_name": s.get("name"), "url": s.get("url"),
            "evidence": [
                {"name": e.get("name"), "url": e.get("url"), "tier": e.get("tier")}
                for e in (s.get("evidence") or [])
            ],
        })

    papers = []
    for p in ps:
        s, v = src(p), p.get("verification") or {}
        a = p.get("artifact") or {}
        papers.append({
            "id": p["id"], "year": p.get("year"), "subject": p.get("subject"),
            "region": p.get("region"), "paper": p.get("paper"),
            "system": p.get("exam_system"), "status": v.get("status"),
            "tier": s.get("tier"), "source_id": s.get("source_id"),
            "nq": len(p.get("question_ids") or []),
            "url": a.get("url") or s.get("url"),
        })

    quarantine = [r for _, _, r in iter_jsonl(QUARANTINE_DIR.rglob("*.jsonl"))]
    used = Counter(src(x).get("source_id") for x in [*qs, *ps])
    sources = [{
        "id": s["id"], "name": s["name"], "tier": s["tier"], "status": s.get("status"),
        "url": s.get("url"), "policy": s.get("full_text_policy"), "adapter": s.get("adapter"),
        "records": used.get(s["id"], 0),
    } for s in reg.get("sources", [])]

    pdf_manifest = REPO_ROOT / "pdf" / "manifest.json"
    pdfs = {"papers": [], "release_tag": None, "sources": {}}
    if pdf_manifest.exists():
        pdfs = json.loads(pdf_manifest.read_text(encoding="utf-8"))
    pdf_rows = [{
        "id": x["id"], "kind": x["kind"], "subject": x["subject"], "year": x["year"], "title": x["title"],
        "edition": x["edition"], "path": x.get("path"), "size": x.get("size"), "pages": x.get("pages"),
        "in_repo": bool(x.get("in_repo")), "zip": x.get("zip"), "ok": x["ok"], "nq": x.get("n_questions"),
    } for x in pdfs.get("papers", [])]

    return {
        "pdfs": pdf_rows, "pdf_release_tag": pdfs.get("release_tag"),
        "generated_at": date.today().isoformat(),
        "stats": summarize(qs, ps),
        "questions": questions,
        "papers": papers,
        "quarantine": {
            "total": len(quarantine),
            "by_status": dict(Counter((r.get("verification") or {}).get("status") for r in quarantine)),
            "by_type": dict(Counter(r.get("type") for r in quarantine)),
        },
        "sources": sources,
        "tier_definitions": reg.get("tier_definitions", {}),
    }


def build_site(out_dir: Path = SITE_DIR) -> Path:
    tpl = TEMPLATE.read_text(encoding="utf-8")
    if PLACEHOLDER not in tpl:
        raise RuntimeError("viz_template.html 缺少数据占位符")
    data = json.dumps(build_payload(), ensure_ascii=False, separators=(",", ":"))
    data = data.replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "index.html"
    out.write_text(tpl.replace(PLACEHOLDER, data), encoding="utf-8")
    return out
