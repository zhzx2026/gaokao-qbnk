#!/usr/bin/env python3
"""批量编译高考试卷 PDF（XeLaTeX，统一版式）。

三类试卷，全部用同一套排版样式（上游 styles.tex 的字体/页面/题号/选项/答案框样式）：

  typeset   数学：上游 LaTeX 源码整卷重排（试题版 + 含答案解析版），2000 年以后全部
  excerpt   其它学科：题库中已有的题目按同一样式排成"节选卷"（明确标注不是完整试卷）
  archive   物理：上游原卷 PDF 套统一封面/页眉页脚（pdfpages），题目正文尚未转写

用法（CI 里跑，见 .github/workflows/papers-pdf.yml）：
  build_pdfs.py prepare --work W [--only-year 2024] [--limit N]
  build_pdfs.py compile --work W --shard 0/8
  build_pdfs.py merge   --work W --results DIR --out pdf/
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MIN_YEAR = 2000
SUBJECT_CODE = {"语文": "yw", "数学": "sx", "英语": "yy", "物理": "wl", "化学": "hx",
                "生物": "sw", "政治": "zz", "历史": "ls", "地理": "dl"}

# 上游 styles.tex 用的是 Windows 字体，Linux 上按下表替换（CI 里 apt 装了对应字体）
FONT_MAP = [
    ("{SimSun}", "{Noto Serif CJK SC}"),
    ("SimHei", "Noto Sans CJK SC"),
    ("KaiTi", "AR PL KaitiM GB"),
    ("{Times New Roman}", "{TeX Gyre Termes}"),
    ("{TeX Gyre Termes Math}", "{STIXTwoMath-Regular.otf}"),
    ("{STIX}", "{STIXTwoMath-Regular.otf}"),
    ("{Asana Math}", "{STIXTwoMath-Regular.otf}"),
]

SOURCES = {
    "dx": {
        "name": "DxAThing/Gaokao-Math-Problems-Compilation（LaTeX 重排）",
        "url": "https://github.com/DxAThing/Gaokao-Math-Problems-Compilation",
        "license": "CC BY-SA 4.0",
        "upstream": "题源 deekur/gaokaomath（CC BY 4.0）",
    },
    "gaokaophysics": {
        "name": "deekur/gaokaophysics（历年高考物理真题原卷）",
        "url": "https://github.com/deekur/gaokaophysics",
        "license": "CC BY 4.0",
        "upstream": "试题著作权归命题机构",
    },
    "gaokao-bench": {
        "name": "OpenLMLab/GAOKAO-Bench 及 GAOKAO-Bench-Updates（结构化高考题）",
        "url": "https://github.com/OpenLMLab/GAOKAO-Bench",
        "license": "Apache-2.0（数据整理）",
        "upstream": "试题著作权归命题机构",
    },
    "qbnk": {
        "name": "gaokao-qbnk 题库（作文题，来源见 reports/provenance.md）",
        "url": "https://github.com/zhzx2026/gaokao-qbnk",
        "license": "见 DATA-LICENSE.md",
        "upstream": "试题著作权归命题机构",
    },
}


# --------------------------------------------------------------------- utils
def slug(s: str) -> str:
    return re.sub(r"[^0-9A-Za-z_.-]+", "_", s).strip("_")


_SLUG = [("未标注卷别", "unk"), ("全国", "qg"), ("新课标", "xkb"), ("新高考", "xgk"), ("甲", "jia"), ("乙", "yi"),
         ("上海", "sh"), ("北京", "bj"), ("天津", "tj"), ("浙江", "zj"), ("理科", "-li"), ("文科", "-wen"),
         ("卷", ""), ("（", "-"), ("）", "")]


def paper_slug(name: str) -> str:
    t = name
    for a, b in _SLUG:
        t = t.replace(a, b)
    leftover = bool(re.search(r"[^\x00-\x7f]", t))
    t = re.sub(r"[^0-9A-Za-z-]+", "", t).strip("-")
    if leftover or not t:
        t = (t + "-" if t else "") + hashlib.sha1(name.encode()).hexdigest()[:5]
    return t


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def git_rev(d: Path) -> str:
    try:
        return subprocess.check_output(["git", "-C", str(d), "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


_SPECIAL = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "#": r"\#", "_": r"\_",
            "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}", "$": r"\$"}
_MATH = re.compile(r"\$\$(.+?)\$\$|\$(.+?)\$|\\\((.+?)\\\)|\\\[(.+?)\\\]", re.S)


def _table(lines: list[str]) -> str:
    rows = []
    for l in lines:
        cells = [c.strip() for c in l.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) or not c for c in cells) and any(cells):
            continue
        rows.append(cells)
    n = max(len(r) for r in rows)
    body = "".join(" & ".join(tex_text(c) for c in r + [""] * (n - len(r))) + " \\\\ \\hline\n" for r in rows)
    return ("\n\n\\begin{center}\\small\\renewcommand{\\baselinestretch}{1.15}"
            f"\\begin{{tabular}}{{|*{{{n}}}{{p{{\\dimexpr0.86\\linewidth/{n}\\relax}}|}}}}\\hline\n{body}"
            "\\end{tabular}\\end{center}\n\n")


def tex_text(s: str) -> str:
    """普通文本转义；$...$ 数学原样保留（统一转成 \\( \\)）；Markdown 表格转 tabular。"""
    s = re.sub(r"<br\s*/?>", " ", (s or "").replace("\r", ""))
    if re.search(r"(?m)^\s*\|", s):
        out, buf = [], []
        for l in s.split("\n"):
            if l.strip().startswith("|"):
                buf.append(l)
                continue
            if buf:
                out.append(("\x01", buf)); buf = []
            out.append(("t", l))
        if buf:
            out.append(("\x01", buf))
        text_lines, res = [], []
        for kind, v in out:
            if kind == "t":
                text_lines.append(v)
            else:
                if text_lines:
                    res.append(tex_text("\n".join(text_lines))); text_lines = []
                res.append(_table(v))
        if text_lines:
            res.append(tex_text("\n".join(text_lines)))
        return "".join(res)
    out, pos = [], 0
    for m in _MATH.finditer(s):
        out.append(_plain(s[pos:m.start()]))
        body = next(g for g in m.groups() if g is not None).strip()
        display = m.group(1) is not None or m.group(4) is not None
        out.append(("\\[" + body + "\\]") if display else ("\\(" + body + "\\)"))
        pos = m.end()
    out.append(_plain(s[pos:]))
    return "".join(out)


def _plain(t: str) -> str:
    t = re.sub(r"[_＿]{2,}|_\s_\s_[_\s]*", "\x00", t)          # 填空线
    t = "".join(_SPECIAL.get(c, c) for c in t)
    t = t.replace("\x00", r"\fillinblank{}")
    t = re.sub(r"\n{2,}", "\n\n", t)
    t = re.sub(r"(?<!\n)\n(?!\n)", "\n\n", t)                   # 每个换行都是一个段落
    return t


# ------------------------------------------------------------------ math (dx)
def colophon(kind: str, src: dict, extra: str, rev: str) -> str:
    kind_txt = {"typeset": "整卷 LaTeX 重排", "excerpt": "题库节选卷（非完整试卷）",
                "archive": "原卷影印页 + 统一版式（题目正文尚未转写）"}[kind]
    return (
        "\\par\\vspace{1.5em}\\begingroup\\footnotesize\\renewcommand{\\baselinestretch}{1.25}"
        "\\setlength{\\parindent}{0pt}\\noindent\\rule{\\linewidth}{0.4pt}\\par\\vspace{0.3em}"
        f"\\textbf{{文件类型}}：{kind_txt}\\par"
        f"\\textbf{{来源}}：{tex_text(src['name'])}（{tex_text(src['url'])}，版本 {rev}）\\par"
        f"\\textbf{{许可}}：{tex_text(src['license'])}；{tex_text(src['upstream'])}\\par"
        f"{extra}"
        "\\textbf{编译}：gaokao-qbnk 项目（github.com/zhzx2026/gaokao-qbnk）用 XeLaTeX 统一编译；"
        "如发现错漏请以原卷为准并提 issue。\\par\\endgroup\n"
    )


def prep_math(work: Path, args) -> list[dict]:
    dx = work / "dx"
    if not dx.exists():
        return []
    rev = git_rev(dx)
    styles = (dx / "styles.tex").read_text(encoding="utf-8")
    for a, b in FONT_MAP:
        styles = styles.replace(a, b)
    (dx / "styles_qbnk.tex").write_text(styles, encoding="utf-8")
    (dx / "_qbnk").mkdir(exist_ok=True)
    jobs = []
    for f in sorted((dx / "content").glob("*/*.tex")):
        year = int(f.parent.name)
        if year < MIN_YEAR or (args.only_year and year != args.only_year):
            continue
        text = f.read_text(encoding="utf-8")
        m = re.search(r"\\chapter\{(.*?)\}", text)
        title = m.group(1) if m else f"{year}年 {f.stem}"
        for edition, showans in (("试题", False), ("解析", True)):
            jid = f"sx-{year}-{f.stem}-{'q' if not showans else 'a'}"
            tex = (
                "\\documentclass[12pt, oneside, UTF8]{ctexbook}\n\\input{styles_qbnk.tex}\n"
                f"\\show{'answertrue' if showans else 'answerfalse'}\n\\tallpagefalse\n"
                "\\begin{document}\n\\mainmatter\n"
                f"\\examyear{{{year}年}}%\n\\input{{content/{year}/{f.name}}}\n"
                + colophon("typeset", SOURCES["dx"], "", rev)
                + "\\end{document}\n"
            )
            (dx / "_qbnk" / f"{jid}.tex").write_text(tex, encoding="utf-8")
            jobs.append({"id": jid, "kind": "typeset", "subject": "数学", "year": year,
                         "title": title, "edition": edition, "cwd": "dx", "tex": f"_qbnk/{jid}.tex",
                         "source": "dx", "source_rev": rev, "source_path": f"content/{year}/{f.name}"})
    return jobs


# ------------------------------------------------------------ physics archive
def prep_physics(work: Path, args) -> list[dict]:
    ph = work / "gaokaophysics"
    dx = work / "dx"
    if not ph.exists() or not dx.exists():
        return []
    rev = git_rev(ph)
    (dx / "_qbnk" / "src").mkdir(parents=True, exist_ok=True)
    jobs = []
    for line in (REPO / "data/papers/archive_physics.jsonl").read_text(encoding="utf-8").splitlines():
        p = json.loads(line)
        year = p["year"]
        if year < MIN_YEAR or (args.only_year and year != args.only_year):
            continue
        src = ph / p["artifact"]["local_path"]
        if not src.exists():
            print(f"skip（找不到原卷）{p['id']}", file=sys.stderr)
            continue
        jid = f"wl-{year}-{slug(p['id'])}"
        shutil.copyfile(src, dx / "_qbnk" / "src" / f"{jid}.pdf")
        title = f"{year}年 {p['paper']} 物理"
        info = (f"\\begin{{center}}\\begin{{tabular}}{{rl}}\\textbf{{学科}} & 物理\\\\ \\textbf{{年份}} & {year}\\\\ "
                f"\\textbf{{卷别}} & {tex_text(p['paper'])}\\\\ \\textbf{{地区}} & {tex_text(p.get('region') or '')}\\\\ "
                f"\\textbf{{原卷 SHA-256}} & \\texttt{{\\scriptsize {p['artifact'].get('sha256', '')[:32]}…}}\\end{{tabular}}\\end{{center}}\n")
        tex = (
            "\\documentclass[12pt, oneside, UTF8]{ctexbook}\n\\input{styles_qbnk.tex}\n\\tallpagefalse\n\\usepackage{pdfpages}\n"
            "\\begin{document}\n\\mainmatter\n"
            f"\\examyear{{{year}年}}%\n\\chapter{{{tex_text(title)}（原卷）}}\n{info}"
            + colophon("archive", SOURCES["gaokaophysics"], "", rev)
            + "\\includepdf[pages=-,scale=0.92,pagecommand={\\thispagestyle{headings}}]"
              f"{{_qbnk/src/{jid}.pdf}}\n\\end{{document}}\n"
        )
        (dx / "_qbnk" / f"{jid}.tex").write_text(tex, encoding="utf-8")
        jobs.append({"id": jid, "kind": "archive", "subject": "物理", "year": year, "title": title,
                     "edition": "原卷", "cwd": "dx", "tex": f"_qbnk/{jid}.tex", "source": "gaokaophysics",
                     "source_rev": rev, "source_path": p["artifact"]["local_path"]})
    return jobs


# ------------------------------------------------------- excerpt (GAOKAO-Bench)
SUBJ_FILE = [
    ("Chinese", "语文"), ("English", "英语"), ("Math", "数学"), ("Physics", "物理"), ("Chemistry", "化学"),
    ("Biology", "生物"), ("Political", "政治"), ("History", "历史"), ("Geography", "地理"),
]
_ROMAN = {"ⅰ": "I", "ⅱ": "II", "ⅲ": "III", "Ⅰ": "I", "Ⅱ": "II", "Ⅲ": "III"}
_OPT = re.compile(r"(?:^|\n|\s)([A-D])\s*[．.、:：]\s*")


def norm_paper(cat: str, track: str = "") -> str | None:
    """把 GAOKAO-Bench 里五花八门的 category 归一成卷别；认不出来（数据里混进了题干）返回 None。"""
    c = re.sub(r"[（()）\s]", "", str(cat or ""))
    if not c:
        return None
    if len(c) > 14:
        return None
    for a, b in _ROMAN.items():
        c = c.replace(a, b)
    c = re.sub(r"(?<![A-Za-z])(iii|ii|i)(?![A-Za-z])", lambda m: m.group(1).upper(), c)
    m = re.search(r"(III|II|I)", c)
    rom = m.group(1) if m else ""
    if "新高考" in c:
        name = f"新高考{rom}卷" if rom else "新高考卷"
    elif "新课标" in c:
        name = f"新课标{rom}卷" if rom else "新课标卷"
    elif "全国甲" in c or c in ("甲卷", "高考甲卷"):
        name = "全国甲卷"
    elif "全国乙" in c or c in ("乙卷", "高考乙卷"):
        name = "全国乙卷"
    elif "全国" in c:
        name = f"全国{rom}卷" if rom else "全国卷"
    elif "解析版" in c:
        name = "未标注卷别"
    else:
        return None
    if track:
        name += f"（{track}）"
    elif "理科" in c:
        name += "（理科）"
    elif "文科" in c:
        name += "（文科）"
    return name


def split_options(q: str):
    """把 'stem A．x B．y C．z D．w' 拆成 (stem, [4 项])；拆不干净返回 None。"""
    ms = list(_OPT.finditer(q))
    if len(ms) < 4:
        return None
    for i in range(len(ms) - 3):
        seq = ms[i:i + 4]
        if [m.group(1) for m in seq] == list("ABCD"):
            stem = q[:seq[0].start()].rstrip()
            opts = [q[seq[k].end(): seq[k + 1].start() if k < 3 else len(q)].strip() for k in range(4)]
            if all(opts):
                return stem, opts
    return None


def load_gaokao_bench(work: Path) -> list[dict]:
    recs = []
    for repo, sub in (("gkb", "Data"), ("gku", "Data")):
        base = work / repo / sub
        if not base.exists():
            continue
        for f in sorted(base.rglob("*.json")):
            name = f.name
            subj = next((zh for en, zh in SUBJ_FILE if en in name), None)
            if not subj or subj in ("数学", "物理"):   # 数学/物理已有完整来源
                continue
            kind = "选择题" if ("MCQs" in name or "Reading_Comp" in name or "Fill_in_Blanks" in name or "Cloze" in name
                                or "Modern_Lit" in name) else "非选择题"
            if "Fill-in-the-Blank" in name:
                kind = "填空题"
            for e in json.loads(f.read_text(encoding="utf-8"))["example"]:
                try:
                    year = int(e["year"])
                except Exception:
                    continue
                paper = norm_paper(e.get("category", ""))
                if paper is None:
                    continue
                recs.append({"subject": subj, "year": year, "paper": paper,
                             "kind": kind, "file": name, "index": e.get("index", 0), "score": e.get("score"),
                             "question": e.get("question") or "", "answer": e.get("answer"),
                             "analysis": e.get("analysis") or "", "repo": repo})
    return recs


def render_problem(r: dict) -> str:
    q = re.sub(r"^\s*\d+\s*[.．、]\s*(?:[（(]\s*\d+(?:\.\d+)?\s*分\s*[)）]\s*)?", "", r["question"].strip())
    ans = r["answer"]
    ans_txt = "、".join(ans) if isinstance(ans, list) else (str(ans) if ans not in (None, "") else "")
    sp = None   # 选项保持原文（每行一个段落），\\choices 对长文字选项排版不稳
    if sp:
        stem, opts = sp
        body = tex_text(stem) + "\n\n\\choices\n" + "".join("  {" + re.sub(r"\s*\n\s*", " ", tex_text(o)).strip() + "}\n" for o in opts)
    else:
        body = tex_text(q)
    out = f"\\begin{{problem}}\n{body}\n\\end{{problem}}\n\n"
    if ans_txt:
        out += f"\\begin{{answer}}\n{tex_text(ans_txt)}\n\\end{{answer}}\n\n"
    if r["analysis"].strip():
        out += f"\\begin{{solution}}\n{tex_text(r['analysis'].strip())}\n\\end{{solution}}\n\n"
    return out


def prep_excerpt(work: Path, args) -> list[dict]:
    dx = work / "dx"
    if not dx.exists():
        return []
    (dx / "_qbnk").mkdir(exist_ok=True)
    groups = defaultdict(list)
    for r in load_gaokao_bench(work):
        if r["year"] < MIN_YEAR or (args.only_year and r["year"] != args.only_year):
            continue
        groups[(r["subject"], r["year"], r["paper"])].append(r)
    # 作文题（本库自己的记录）
    for line in (REPO / "data/questions/zuowen.jsonl").read_text(encoding="utf-8").splitlines():
        q = json.loads(line)
        if q["year"] < MIN_YEAR or (args.only_year and q["year"] != args.only_year):
            continue
        pname = q.get("paper") or q.get("region") or ""
        groups[("语文", q["year"], pname)].append(
            {"subject": "语文", "year": q["year"], "paper": pname,
             "kind": "作文", "file": "zuowen", "index": int(re.sub(r"\D", "", q.get("question_no") or "") or 99),
             "score": q.get("score"), "question": q["stem"], "answer": None, "analysis": q.get("analysis") or "",
             "repo": "qbnk"})
    jobs = []
    order = {"选择题": 0, "填空题": 1, "非选择题": 2, "作文": 3}
    for (subj, year, paper), rs in sorted(groups.items()):
        rs.sort(key=lambda r: (order[r["kind"]], r["file"], r["index"]))
        for edition, showans in (("试题", False), ("解析", True)):
            if showans and not any(r["answer"] or r["analysis"].strip() for r in rs):
                continue
            jid = f"{SUBJECT_CODE[subj]}-{year}-{paper_slug(paper)}-x{'a' if showans else 'q'}"
            title = f"{year}年 {paper} {subj}（节选）"
            parts = [f"\\chapter{{{tex_text(title)}}}\n"]
            total = sum(float(r["score"] or 0) for r in rs)
            parts.append(
                f"\\begin{{center}}\\small 本卷为题库\\textbf{{节选卷}}，仅含已收录的 {len(rs)} 道题"
                f"{'，共 %g 分' % total if total else ''}；不是完整试卷，题号为本卷序号。\\end{{center}}\n")
            cur = None
            for r in rs:
                if r["kind"] != cur:
                    cur = r["kind"]
                    parts.append(f"\\section{{{cur}}}\n\n")
                parts.append(render_problem(r))
            src_key = "qbnk" if all(r["repo"] == "qbnk" for r in rs) else "gaokao-bench"
            body = "".join(parts)
            tex = (
                "\\documentclass[12pt, oneside, UTF8]{ctexbook}\n\\input{styles_qbnk.tex}\n"
                f"\\show{'answertrue' if showans else 'answerfalse'}\n\\tallpagefalse\n"
                "\\begin{document}\n\\mainmatter\n"
                f"\\examyear{{{year}年}}%\n{body}"
                + colophon("excerpt", SOURCES[src_key],
                           "\\textbf{校对状态}：来源为 OCR 整理的结构化数据，尚未逐题二次校对，公式/选项可能有误，请以原卷为准。\\par"
                           if src_key == "gaokao-bench" else "", "main")
                + "\\end{document}\n"
            )
            (dx / "_qbnk" / f"{jid}.tex").write_text(tex, encoding="utf-8")
            jobs.append({"id": jid, "kind": "excerpt", "subject": subj, "year": year, "title": title,
                         "edition": "解析" if showans else "试题", "cwd": "dx", "tex": f"_qbnk/{jid}.tex",
                         "source": src_key, "source_rev": "main", "n_questions": len(rs)})
    return jobs


# -------------------------------------------------------------------- commands
def cmd_prepare(args) -> int:
    work = Path(args.work).resolve()
    jobs = prep_math(work, args) + prep_physics(work, args) + prep_excerpt(work, args)
    if args.limit:
        jobs = jobs[: args.limit]
    (work / "jobs.json").write_text(json.dumps(jobs, ensure_ascii=False, indent=1), encoding="utf-8")
    from collections import Counter
    print(f"jobs: {len(jobs)}", dict(Counter(j["kind"] for j in jobs)))
    return 0


def pdf_pages(p: Path) -> int | None:
    try:
        out = subprocess.check_output(["pdfinfo", str(p)], text=True, stderr=subprocess.DEVNULL)
        return int(re.search(r"Pages:\s+(\d+)", out).group(1))
    except Exception:
        return None


def cmd_compile(args) -> int:
    work = Path(args.work).resolve()
    jobs = json.loads((work / "jobs.json").read_text(encoding="utf-8"))
    i, n = (int(x) for x in args.shard.split("/"))
    mine = [j for k, j in enumerate(jobs) if k % n == i]
    res_dir = Path(args.results).resolve()
    (res_dir / "pdf").mkdir(parents=True, exist_ok=True)
    (res_dir / "fail").mkdir(parents=True, exist_ok=True)
    results = []
    for j in mine:
        cwd = work / j["cwd"]
        t0 = time.time()
        outdir = cwd / "_out" / j["id"]
        outdir.mkdir(parents=True, exist_ok=True)
        cmd = ["latexmk", "-xelatex", "-interaction=nonstopmode", "-halt-on-error", "-file-line-error",
               f"-outdir={outdir}", "-e", '$xelatex = "xelatex -cnf-line=extra_mem_bot=10000000 %O %S"', j["tex"]]
        try:
            r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=args.timeout)
            ok = r.returncode == 0
        except subprocess.TimeoutExpired:
            ok = False
        pdf = outdir / (Path(j["tex"]).stem + ".pdf")
        rec = dict(j, seconds=round(time.time() - t0, 1), ok=ok and pdf.exists())
        if rec["ok"]:
            dest = res_dir / "pdf" / SUBJECT_CODE[j["subject"]] / str(j["year"]) / f"{j['id']}.pdf"
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(pdf, dest)
            rec.update(path=f"{SUBJECT_CODE[j['subject']]}/{j['year']}/{j['id']}.pdf", size=dest.stat().st_size,
                       pages=pdf_pages(dest), sha256=sha256(dest))
        else:
            logf = outdir / (Path(j["tex"]).stem + ".log")
            tail = ""
            if logf.exists():
                lines = logf.read_text(errors="replace").splitlines()
                pat = re.compile(r"^(!|\S+\.(tex|sty|cls|def|cfg|fd|xdv):\d+:)")
                errs = [k for k, l in enumerate(lines) if pat.match(l)]
                k = errs[0] if errs else max(0, len(lines) - 40)
                tail = "\n".join(lines[max(0, k - 2): k + 16])
            rec["error"] = tail
            (res_dir / "fail" / f"{j['id']}.txt").write_text(tail, encoding="utf-8")
        results.append(rec)
        print(("OK  " if rec["ok"] else "FAIL"), j["id"], rec["seconds"], flush=True)
        shutil.rmtree(outdir, ignore_errors=True)
    (res_dir / f"results-{i}.json").write_text(json.dumps(results, ensure_ascii=False), encoding="utf-8")
    return 0


def cmd_merge(args) -> int:
    """全量 PDF 打成 dist/*.zip（发 Release）；仓库里只留 >= repo_min_year 的整卷/节选卷 + 完整清单。"""
    import zipfile
    res_dir, out, dist = Path(args.results), Path(args.out), Path(args.dist)
    allr = []
    for f in sorted(res_dir.rglob("results-*.json")):
        allr += json.loads(f.read_text(encoding="utf-8"))
    repo_kinds = set(args.repo_kinds.split(","))
    dist.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    zips: dict[str, zipfile.ZipFile] = {}
    for r in allr:
        if not r["ok"]:
            continue
        src = next(res_dir.rglob(f"pdf/{r['path']}"), None)
        if src is None:
            r["ok"] = False
            r["error"] = "artifact missing"
            continue
        zname = f"gaokao-pdf-{r['kind']}-{SUBJECT_CODE[r['subject']]}.zip"
        z = zips.get(zname) or zips.setdefault(zname, zipfile.ZipFile(dist / zname, "w", zipfile.ZIP_STORED))
        z.write(src, r["path"])
        r["zip"] = zname
        r["in_repo"] = r["year"] >= args.repo_min_year and r["kind"] in repo_kinds
        if r["in_repo"]:
            dest = out / r["path"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest)
    for z in zips.values():
        z.close()
    keep = ["id", "kind", "subject", "year", "title", "edition", "ok", "path", "size", "pages", "sha256", "in_repo", "zip",
            "source", "source_rev", "source_path", "n_questions", "seconds"]
    man = [{k: r[k] for k in keep if k in r} for r in sorted(allr, key=lambda r: (r["subject"], r["year"], r["id"]))]
    (out / "manifest.json").write_text(json.dumps(
        {"sources": SOURCES, "release_tag": args.release_tag, "papers": man}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    bad = [r for r in allr if not r["ok"]]
    (out / "failed.txt").write_text("\n".join(f"{r['id']}\n{r.get('error', '')}\n" for r in bad), encoding="utf-8")
    print(f"total {len(allr)}  ok {len(allr) - len(bad)}  failed {len(bad)}  in_repo {sum(1 for r in allr if r.get('in_repo'))}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare"); p.add_argument("--work", required=True)
    p.add_argument("--only-year", type=int); p.add_argument("--limit", type=int); p.set_defaults(fn=cmd_prepare)
    p = sub.add_parser("compile"); p.add_argument("--work", required=True); p.add_argument("--shard", default="0/1")
    p.add_argument("--results", required=True); p.add_argument("--timeout", type=int, default=600); p.set_defaults(fn=cmd_compile)
    p = sub.add_parser("merge"); p.add_argument("--results", required=True); p.add_argument("--out", required=True)
    p.add_argument("--dist", default="dist"); p.add_argument("--repo-min-year", type=int, default=2024)
    p.add_argument("--repo-kinds", default="typeset,excerpt"); p.add_argument("--release-tag", default="pdf-latest")
    p.set_defaults(fn=cmd_merge)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
