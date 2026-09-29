#!/usr/bin/env python3
"""qbnk —— 高考题库（gaokao-qbnk）命令行工具链。

常用流程：
    python -m tools.qbnk.cli validate --fix-hash     # 校验并补全内容哈希
    python -m tools.qbnk.cli stats                   # 统计概览
    python -m tools.qbnk.cli dedup                   # 查重
    python -m tools.qbnk.cli index                   # 生成 data/index/*.json
    python -m tools.qbnk.cli report                  # 生成 reports/*.md
    python -m tools.qbnk.cli verify-sources          # 复核来源链接（需网络）
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
import urllib.error
from collections import defaultdict
from datetime import date
from pathlib import Path

from .core import (
    DATA_DIR, PAPERS_DIR, QUESTIONS_DIR, QUARANTINE_DIR, REPO_ROOT, REGISTRY_PATH,
    SUBJECTS, by_verification, find_duplicates, hash_question, iter_jsonl, load_papers,
    load_questions, load_registry, make_id, registry_index, summarize,
    schema_validators, validate_papers, validate_questions,
)

INDEX_DIR = DATA_DIR / "index"
REPORTS_DIR = REPO_ROOT / "reports"


# ------------------------------------------------------------------- helpers
def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _load_all():
    qs = load_questions()
    ps = load_papers()
    reg = load_registry()
    return qs, ps, reg


# ------------------------------------------------------------------ commands
def cmd_validate(args) -> int:
    qs, ps, reg = _load_all()
    reg_idx = registry_index(reg)
    issues = validate_questions(qs, reg_idx) + validate_papers(ps, reg_idx)

    if args.fix_hash:
        fixed = 0
        for path in sorted({REPO_ROOT / q["__file__"] for q in qs if "__file__" in q}):
            lines = path.read_text(encoding="utf-8").splitlines()
            out = []
            for line in lines:
                if not line.strip() or line.strip().startswith("//"):
                    out.append(line)
                    continue
                rec = json.loads(line)
                h = hash_question(rec)
                if rec.get("content_hash") != h:
                    rec["content_hash"] = h
                    fixed += 1
                out.append(json.dumps(rec, ensure_ascii=False))
            path.write_text("\n".join(out) + "\n", encoding="utf-8")
        print(f"✔ 已更新 {fixed} 条记录的 content_hash")
        qs = load_questions()
        issues = validate_questions(qs, reg_idx) + validate_papers(ps, reg_idx)

    errors = [i for i in issues if i["level"] == "error"]
    warns = [i for i in issues if i["level"] == "warning"]
    for i in issues:
        print(i)
    print(f"\n合计：{len(issues)} 条问题（error {len(errors)} / warning {len(warns)}），"
          f"题目 {len([q for q in qs if '__parse_error__' not in q])} 条，试卷 {len(ps)} 份")
    if errors:
        return 1
    return 1 if (warns and args.strict) else 0


def cmd_stats(args) -> int:
    qs, ps, _ = _load_all()
    good = [q for q in qs if "__parse_error__" not in q]
    s = summarize(good, ps)
    s["by_verification"] = by_verification(good)
    if args.json:
        print(json.dumps(s, ensure_ascii=False, indent=2))
        return 0
    print("=== 题库概览 ===")
    print(f"题目：{s['questions']}    试卷：{s['papers']}   "
          f"有答案/解析：{s['with_answer']}/{s['with_analysis']}")
    for label, key in [("学科", "by_subject"), ("年份", "by_year"), ("卷别", "by_paper"),
                       ("题型", "by_type"), ("考试类型", "by_exam_type"),
                       ("来源等级", "by_source_tier"), ("校验状态", "by_verification")]:
        d = s[key]
        if not d:
            continue
        body = "  ".join(f"{k}:{v}" for k, v in list(d.items())[:18])
        print(f"{label:6} {body}{' …' if len(d) > 18 else ''}")
    return 0


def cmd_dedup(args) -> int:
    qs, _, _ = _load_all()
    dups = find_duplicates(qs, threshold=args.threshold)
    if not dups:
        print("✔ 未发现重复题目")
        return 0
    print(f"发现 {len(dups)} 组疑似重复：")
    for d in dups:
        extra = f"  ratio={d['ratio']}" if "ratio" in d else ""
        print(f"  [{d['kind']}] {d['id']} ≈ {d['dup_of']}{extra}")
    return 1 if any(d["kind"] == "exact" for d in dups) else 0


def cmd_index(args) -> int:
    qs, ps, _ = _load_all()
    good = [q for q in qs if "__parse_error__" not in q]

    def brief(q):
        stem = (q.get("stem") or "").replace("\n", " ")
        return {
            "id": q["id"], "subject": q.get("subject"), "year": q.get("year"),
            "region": q.get("region"), "paper": q.get("paper"), "type": q.get("type"),
            "exam_type": q.get("exam_type"), "question_no": q.get("question_no"),
            "status": (q.get("verification") or {}).get("status"),
            "tier": (q.get("source") or {}).get("tier"),
            "source_id": (q.get("source") or {}).get("source_id"),
            "preview": stem[:60] + ("…" if len(stem) > 60 else ""),
        }

    def group(keyfn):
        g = defaultdict(list)
        for q in good:
            g[str(keyfn(q))].append(brief(q))
        return {k: sorted(v, key=lambda x: x["id"]) for k, v in sorted(g.items())}

    _write_json(INDEX_DIR / "all.json", [brief(q) for q in sorted(good, key=lambda q: q["id"])])
    _write_json(INDEX_DIR / "by_subject.json", group(lambda q: q.get("subject")))
    _write_json(INDEX_DIR / "by_year.json", group(lambda q: q.get("year")))
    _write_json(INDEX_DIR / "by_paper.json", group(lambda q: f"{q.get('year')} {q.get('paper') or q.get('region')}"))
    _write_json(INDEX_DIR / "by_type.json", group(lambda q: q.get("type")))
    _write_json(INDEX_DIR / "manifest.json", {
        "generated_at": date.today().isoformat(),
        "schema_version": "1.0",
        "counts": {"questions": len(good), "papers": len(ps)},
        "stats": summarize(good, ps),
        "files": sorted(str(p.relative_to(REPO_ROOT)) for p in QUESTIONS_DIR.rglob("*.jsonl")),
    })
    print(f"✔ 索引已生成：{INDEX_DIR.relative_to(REPO_ROOT)}（题目 {len(good)}，试卷 {len(ps)}）")
    return 0


def _md_table(rows, header):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(out)


def cmd_report(args) -> int:
    qs, ps, reg = _load_all()
    good = [q for q in qs if "__parse_error__" not in q]
    s = summarize(good, ps)
    s["by_verification"] = by_verification(good)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    papers_with_q = sum(1 for p in ps if p.get("question_ids"))
    papers_archive_only = len(ps) - papers_with_q
    years = sorted({int(y) for y in s["by_year"]})
    y0, y1 = (min(years), max(years)) if years else (0, 0)

    # 覆盖矩阵：学科 × 年份
    mat: dict[tuple[str, int], int] = defaultdict(int)
    for q in good:
        mat[(q.get("subject", "?"), int(q.get("year", 0)))] += 1
    subj_present = sorted({k[0] for k in mat})
    header = ["学科"] + [str(y) for y in years] + ["合计"]
    rows = []
    for sub in subj_present:
        cells = [mat.get((sub, y), 0) or "" for y in years]
        rows.append([sub] + cells + [sum(mat.get((sub, y), 0) for y in years)])
    # 试卷层：学科 × 年代（含仅登记原卷档案的索引）
    dec: dict[tuple[str, str], int] = defaultdict(int)
    for p in ps:
        try:
            y = int(p.get("year", 0))
        except (TypeError, ValueError):
            continue
        dec[(p.get("subject", "?"), f"{y // 10 * 10}s" if y else "未知")] += 1
    decades = sorted({k[1] for k in dec})
    subs_paper = sorted({k[0] for k in dec})
    paper_rows = [[s] + [dec.get((s, d), 0) or "" for d in decades] +
                  [sum(dec.get((s, d), 0) for d in decades)] for s in subs_paper]

    coverage_md = [
        "# 覆盖度报告",
        "",
        f"> 自动生成（qbnk report）· {date.today().isoformat()} · 题目 {len(good)} 条 / 试卷 {len(ps)} 份",
        "",
        "## 总览",
        "",
        _md_table(
            [["题目总数", len(good)], ["试卷总数", len(ps)],
             ["已录入题目的试卷", papers_with_q], ["仅原卷档案索引（题目待录）", papers_archive_only],
             ["年份区间", f"{y0}-{y1}"],
             ["学科数", len(subj_present)], ["有答案", s["with_answer"]], ["有解析", s["with_analysis"]],
             [" verified", s["by_verification"].get("verified", 0)],
             [" single_source", s["by_verification"].get("single_source", 0)],
             [" conflict", s["by_verification"].get("conflict", 0)]],
            ["指标", "值"]),
        "",
        "## 题目：学科 × 年份（已录入题量）",
        "",
        _md_table(rows, header) if rows else "_暂无数据_",
        "",
        "## 试卷：学科 × 年代（含「仅登记原卷 PDF 档案、题目待录」的索引）",
        "",
        _md_table(paper_rows, ["学科"] + decades + ["合计"]) if paper_rows else "_暂无数据_",
        "",
        "## 来源等级分布",
        "",
        _md_table([[k, v] for k, v in s["by_source_tier"].items()], ["Tier", "题量"]) or "_暂无_",
        "",
        "## 缺口（TODO）",
        "",
        "- 数学/物理：试卷级档案索引已生成（1213 份，1952-2026），下一步是 OCR/人工录入题目正文并与官方答案核对；",
        "- 化学/生物/政治/历史/地理：尚未接入任何来源，需按 docs/sources.md 新增适配器；",
        "- 模拟题/联考/高一高二同步题：schema 已支持（exam_type/stage），来源未接入；",
        "- 1951-2021 历年作文题：仅 T4 站点有全量，须逐条与 T1-T3 核对后方可入库。",
        "",
    ]
    (REPORTS_DIR / "coverage.md").write_text("\n".join(coverage_md), encoding="utf-8")

    # 溯源报告
    per_src: dict[str, list[dict]] = defaultdict(list)
    for q in good + ps:  # 题目 + 试卷（含原卷档案索引）都算"已使用该来源"
        src = q.get("source") or {}
        per_src[src.get("source_id", "?")].append(q)
    reg_idx = registry_index(reg)
    prov_rows = []
    for sid, items in sorted(per_src.items(), key=lambda kv: -len(kv[1])):
        e = reg_idx.get(sid, {})
        prov_rows.append([sid, e.get("tier", "?"), len(items), e.get("name", "未登记"), e.get("url", "")])
    prov_md = [
        "# 溯源报告",
        "",
        f"> 自动生成（qbnk report）· {date.today().isoformat()}",
        "",
        "## 已使用来源",
        "",
        _md_table(prov_rows, ["source_id", "Tier", "题量", "来源名称", "主页"]),
        "",
        "## 未使用（登记待采集）",
        "",
        _md_table([[e["id"], e["tier"], e.get("status", ""), e.get("adapter") or "—", e.get("notes", "")[:60]]
                   for e in reg.get("sources", []) if e["id"] not in per_src],
                  ["source_id", "Tier", "状态", "适配器", "备注"]),
        "",
        "## 全部题目出处清单",
        "",
        _md_table([[q["id"], f"{q.get('year')} {q.get('paper') or ''}", q.get("type"),
                    (q.get("source") or {}).get("tier"), ((q.get("verification") or {}).get("status")),
                    (q.get("source") or {}).get("url", "")]
                   for q in sorted(good, key=lambda q: q["id"])],
                  ["id", "卷别", "题型", "Tier", "校验", "来源 URL"]),
        "",
    ]
    (REPORTS_DIR / "provenance.md").write_text("\n".join(prov_md), encoding="utf-8")
    print(f"✔ 报告已生成：{REPORTS_DIR / 'coverage.md'}、{REPORTS_DIR / 'provenance.md'}")
    return 0


def cmd_verify_sources(args) -> int:
    qs, ps, reg = _load_all()
    urls: dict[str, set[str]] = defaultdict(set)
    for q in qs:
        src = q.get("source") or {}
        if src.get("url"):
            urls[src["source_id"]].add(src["url"])
        for ev in src.get("evidence", []) or []:
            if ev.get("url"):
                urls[src["source_id"]].add(ev["url"])
    results = []
    checked = 0
    for sid, us in sorted(urls.items()):
        for u in sorted(us):
            if args.limit and checked >= args.limit:
                break
            status, note = "unknown", ""
            try:
                req = urllib.request.Request(u, method="HEAD", headers={"User-Agent": "qbnk-source-check/1.0"})
                with urllib.request.urlopen(req, timeout=args.timeout) as r:
                    status, note = "ok", str(r.status)
            except urllib.error.HTTPError as e:
                status, note = "http_error", str(e.code)
            except Exception as e:  # 网络受限/超时
                status, note = "unreachable", type(e).__name__
            checked += 1
            results.append({"source_id": sid, "url": u, "status": status, "note": note,
                            "checked_at": date.today().isoformat()})
            print(f"  {status:12} {sid}  {u}")
    _write_json(REPORTS_DIR / "sources_health.json", {"generated_at": date.today().isoformat(), "results": results})
    bad = [r for r in results if r["status"] not in ("ok",)]
    print(f"\n检查 {len(results)} 条链接：可达 {len(results) - len(bad)}，异常 {len(bad)}"
          f"（unreachable 可能是本地网络受限，非源站失效）")
    return 0


def cmd_check_staging(args) -> int:
    """检查 data/staging/ 下的适配器产出：结构与出处必须完整（等级与状态可以不合格）。"""
    d = Path(args.dir)
    files = sorted(d.rglob("*.jsonl"))
    if not files:
        print(f"（{d} 下没有 jsonl，无需检查）")
        return 0
    validators = schema_validators()
    if not validators:
        print("⚠ 未安装 jsonschema，只做基础字段检查（pip install -r requirements.txt 可得完整校验）")
    total = errs = 0
    rows = []
    for f in files:
        recs = [r for _p, _i, r in iter_jsonl([f]) if "__parse_error__" not in r]
        n_err = 0
        for r in recs:
            total += 1
            rid = r.get("id", "?")
            v = validators.get("question" if str(rid).startswith("q-") else "paper")
            if v is not None:
                clean = {k: v2 for k, v2 in r.items() if not k.startswith("__")}
                for e in list(v.iter_errors(clean))[:3]:
                    n_err += 1
                    errs += 1
                    print(f"  [schema] {rid} {f.name}: {'/'.join(map(str, e.path))}: {e.message}")
            src = r.get("source") or {}
            if not src.get("url"):
                n_err += 1
                errs += 1
                print(f"  [source] {rid} 缺少 source.url（野题，直接丢弃）")
            if not src.get("source_id"):
                n_err += 1
                errs += 1
                print(f"  [source] {rid} 缺少 source.source_id")
        rows.append([str(f.relative_to(REPO_ROOT)), len(recs), n_err])
    print(_md_table(rows, ["文件", "记录数", "问题数"]))
    print(f"\nstaging 合计 {total} 条记录，{errs} 处问题")
    print("说明：staging 允许存在 T4 / rejected 记录，但 JSON 结构与出处字段必须完整，"
          "否则人工无法复核，应在适配器里修好再重跑。")
    return 1 if errs else 0


def cmd_new_id(args) -> int:
    print(make_id(args.year, args.subject, args.paper, args.seq))
    return 0


def cmd_list_sources(args) -> int:
    reg = load_registry()
    rows = [[s["id"], s["tier"], s.get("status", ""), s.get("full_text_policy", ""),
             (s.get("adapter") or "—"), s.get("url", "")] for s in reg["sources"]]
    print(_md_table(rows, ["source_id", "Tier", "状态", "正文策略", "适配器", "主页"]))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="qbnk", description="高考题库工具链")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("validate", help="校验题目与试卷（schema + 溯源规则）")
    p.add_argument("--fix-hash", action="store_true", help="补全/修正 content_hash")
    p.add_argument("--strict", action="store_true", help="warning 也视为失败")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("stats", help="统计概览")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_stats)

    p = sub.add_parser("dedup", help="查重（精确 + 近似）")
    p.add_argument("--threshold", type=float, default=0.92)
    p.set_defaults(func=cmd_dedup)

    p = sub.add_parser("index", help="生成索引 data/index/*.json")
    p.set_defaults(func=cmd_index)

    p = sub.add_parser("report", help="生成 reports/coverage.md 与 reports/provenance.md")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("verify-sources", help="复核所有来源链接可达性（需网络）")
    p.add_argument("--timeout", type=float, default=10.0)
    p.add_argument("--limit", type=int, default=0)
    p.set_defaults(func=cmd_verify_sources)

    p = sub.add_parser("check-staging", help="检查 data/staging/ 下适配器产出的结构与出处完整性")
    p.add_argument("--dir", default=str(DATA_DIR / "staging"))
    p.set_defaults(func=cmd_check_staging)

    p = sub.add_parser("new-id", help="生成合规题目 id")
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--subject", required=True, choices=SUBJECTS)
    p.add_argument("--paper", default="")
    p.add_argument("--seq", default=1)
    p.set_defaults(func=cmd_new_id)

    p = sub.add_parser("list-sources", help="列出来源登记表")
    p.set_defaults(func=cmd_list_sources)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
