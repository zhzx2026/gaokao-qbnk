"""qbnk core：加载、规范化、校验、去重、统计。

纯标准库实现（jsonschema 可选，装了就做 schema 级校验，没装就只跑业务规则）。
设计目标：让"野题"在 validate 阶段就进不去正式库。
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
QUESTIONS_DIR = DATA_DIR / "questions"
PAPERS_DIR = DATA_DIR / "papers"
QUARANTINE_DIR = DATA_DIR / "quarantine"
REGISTRY_PATH = REPO_ROOT / "sources" / "registry.json"
SCHEMA_DIR = REPO_ROOT / "schema"

SUBJECTS = ["语文", "数学", "英语", "物理", "化学", "生物", "政治", "历史", "地理", "技术", "综合", "其他"]
OBJECTIVE_TYPES = {"单选", "多选", "判断", "填空"}
SUBJECT_CODE = {
    "语文": "yw", "数学": "sx", "英语": "yy", "物理": "wl", "化学": "hx",
    "生物": "sw", "政治": "zz", "历史": "ls", "地理": "dl", "技术": "js",
    "综合": "zh", "其他": "qt",
}

_WS = re.compile(r"\s+")
_PUNCT = re.compile(r"[，。、；：？！“”‘’（）《》〈〉·\-—…,.;:?!\"'()<>\u3000]+")


# --------------------------------------------------------------------------- IO
def iter_jsonl(paths: Iterable[Path]) -> Iterable[tuple[Path, int, dict]]:
    for p in sorted(paths):
        if not p.exists():
            continue
        with p.open(encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith("//"):
                    continue
                try:
                    yield p, i, json.loads(line)
                except json.JSONDecodeError as e:
                    yield p, i, {"__parse_error__": f"{e} @ {p.name}:{i}"}


def load_questions(root: Path | None = None) -> list[dict]:
    root = root or QUESTIONS_DIR
    out: list[dict] = []
    for p, i, rec in iter_jsonl(sorted(root.rglob("*.jsonl"))):
        if "__parse_error__" in rec:
            out.append({"__parse_error__": rec["__parse_error__"], "__file__": str(p), "__line__": i})
            continue
        rec["__file__"] = str(p.relative_to(REPO_ROOT))
        rec["__line__"] = i
        out.append(rec)
    return out


def load_papers(root: Path | None = None) -> list[dict]:
    root = root or PAPERS_DIR
    return [
        {**rec, "__file__": str(p.relative_to(REPO_ROOT)), "__line__": i}
        for p, i, rec in iter_jsonl(sorted(root.rglob("*.jsonl")))
        if "__parse_error__" not in rec
    ]


def load_registry() -> dict:
    with REGISTRY_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def registry_index(reg: dict | None = None) -> dict[str, dict]:
    reg = reg or load_registry()
    return {s["id"]: s for s in reg.get("sources", [])}


# ------------------------------------------------------------------- normalize
def norm_text(s: str) -> str:
    """题干归一化：全半角统一 + 去空白 + 去常见标点，用于去重与哈希。"""
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = _WS.sub("", s)
    s = _PUNCT.sub("", s)
    return s


def hash_question(q: dict) -> str:
    opts = "|".join(f"{o.get('key','')}={norm_text(o.get('text',''))}" for o in (q.get("options") or []))
    ans = q.get("answer")
    ans = "|".join(ans) if isinstance(ans, list) else (ans or "")
    payload = f"{norm_text(q.get('stem',''))}|{opts}|{norm_text(ans)}|{norm_text(q.get('answer_text') or '')}"
    return "sha1:" + hashlib.sha1(payload.encode("utf-8")).hexdigest()


def make_id(year: int, subject: str, paper: str, seq: int | str, slug: str = "") -> str:
    """生成题目 id。卷别为中文时请显式传 slug（如 quanguo1 / beijing / xinkebiao2）。"""
    code = SUBJECT_CODE.get(subject, "qt")
    if not slug:
        slug = re.sub(r"[^a-z0-9]+", "", (paper or "").lower())
        slug = re.sub(r"[^a-z0-9]+", "", slug or "x") or "x"
    return f"q-{year}-{code}-{slug}-{int(seq):03d}"


# ------------------------------------------------------------------- validate
class Issue(dict):
    def __init__(self, level: str, code: str, msg: str, qid: str = "", where: str = ""):
        super().__init__(level=level, code=code, msg=msg, id=qid, where=where)

    def __str__(self) -> str:  # pragma: no cover
        return f"[{self['level'].upper():7}] {self['code']:16} {self['id'] or '-'} {self['where']} {self['msg']}"


def schema_validators() -> dict[str, Any]:
    try:
        import jsonschema  # type: ignore
    except Exception:
        return {}
    out = {}
    for name in ("question", "paper"):
        p = SCHEMA_DIR / f"{name}.schema.json"
        if p.exists():
            with p.open(encoding="utf-8") as f:
                out[name] = jsonschema.Draft202012Validator(json.load(f))
    return out


def _host(url: str) -> str:
    m = re.match(r"https?://([^/]+)", url or "")
    return (m.group(1).lower() if m else "").split(":")[0]


def validate_questions(questions: list[dict], reg_idx: dict[str, dict] | None = None,
                       validators: dict[str, Any] | None = None) -> list[Issue]:
    reg_idx = reg_idx if reg_idx is not None else registry_index()
    validators = validators if validators is not None else schema_validators()
    issues: list[Issue] = []
    seen_ids: dict[str, str] = {}
    seen_keys: dict[tuple, str] = {}

    for q in questions:
        qid = q.get("id", "<missing-id>")
        where = f"{q.get('__file__','?')}:{q.get('__line__','?')}"

        if "__parse_error__" in q:
            issues.append(Issue("error", "E-PARSE", q["__parse_error__"], qid, where))
            continue

        v = validators.get("question")
        if v is not None:
            clean = {k: v2 for k, v2 in q.items() if not k.startswith("__")}
            for err in sorted(v.iter_errors(clean), key=lambda e: list(e.path)):
                path = "/".join(str(x) for x in err.path)
                issues.append(Issue("error", "E-SCHEMA", f"{path}: {err.message}", qid, where))

        # R1 id 唯一
        if qid in seen_ids:
            issues.append(Issue("error", "E-DUP-ID", f"id 重复，首次出现于 {seen_ids[qid]}", qid, where))
        else:
            seen_ids[qid] = where

        # R2 来源必须登记
        src = q.get("source") or {}
        sid = src.get("source_id", "")
        if sid not in reg_idx:
            issues.append(Issue("error", "E-SRC-UNKNOWN",
                                f"source_id 未在 sources/registry.json 登记：{sid!r}", qid, where))
        else:
            entry = reg_idx[sid]
            # R3 tier 必须与登记表一致
            if src.get("tier") != entry["tier"]:
                issues.append(Issue("error", "E-SRC-TIER",
                                    f"tier {src.get('tier')!r} 与登记表 {entry['tier']!r} 不一致", qid, where))
            # R4 域名必须与登记表吻合（防伪造 URL）
            if _host(src.get("url", "")) not in {_host(entry["url"]), *{_host(x) for x in entry.get("allowed_hosts", [])}}:
                issues.append(Issue("error", "E-SRC-HOST",
                                    f"url 主机 {_host(src.get('url',''))!r} 与登记来源主机不一致", qid, where))
            # R5 T4 不得直接入正式库
            if entry["tier"] == "T4":
                issues.append(Issue("error", "E-SRC-T4",
                                    "T4（社区/UGC）来源不得直接进入 data/questions，应先放 data/quarantine", qid, where))
            # R6 登记表禁用正文抓取的来源
            if entry.get("full_text_policy") == "index_only" and q.get("stem"):
                issues.append(Issue("warning", "W-SRC-INDEXONLY",
                                    f"来源 {sid} 的入库策略为 index_only，请确认正文授权", qid, where))

        # R7 野题：无 URL
        if not src.get("url"):
            issues.append(Issue("error", "E-SRC-NOURL", "缺少可核验的 source.url（野题）", qid, where))

        # R8 校验状态
        ver = q.get("verification") or {}
        status = ver.get("status")
        if status == "rejected":
            issues.append(Issue("error", "E-REJECTED", "rejected 记录必须移至 data/quarantine/", qid, where))
        if status not in {"verified", "single_source", "conflict", "rejected"}:
            issues.append(Issue("error", "E-VERIFY-STATUS", f"非法的 verification.status：{status!r}", qid, where))
        if status == "verified" and src.get("tier") != "T1" and not src.get("evidence"):
            issues.append(Issue("error", "E-VERIFY-EVIDENCE",
                                "verified 需要至少一条 evidence（或来源为 T1）", qid, where))
        if status == "conflict":
            issues.append(Issue("warning", "W-CONFLICT", "来源冲突，需人工裁决", qid, where))

        # R9 客观题必须有答案
        if q.get("type") in OBJECTIVE_TYPES and q.get("answer") in (None, "", []):
            issues.append(Issue("error", "E-NO-ANSWER", f"{q.get('type')} 题缺少标准答案", qid, where))

        # R10 内容哈希
        expected = hash_question(q)
        if not q.get("content_hash"):
            issues.append(Issue("warning", "W-NO-HASH", f"content_hash 缺失（应为 {expected}）", qid, where))
        elif q["content_hash"] != expected:
            issues.append(Issue("warning", "W-HASH-MISMATCH",
                                f"content_hash 与正文不符，应为 {expected}", qid, where))

        # R11 年份一致性
        year = q.get("year")
        if isinstance(qid, str) and qid.startswith("q-") and isinstance(year, int) and not qid.startswith(f"q-{year}-"):
            issues.append(Issue("warning", "W-ID-YEAR", f"id 中的年份与 year 字段({year})不一致", qid, where))

        # R12 同一卷内题号唯一（题号缺失时不参与比对）
        if q.get("question_no"):
            key = (q.get("year"), q.get("region"), q.get("paper"), q.get("question_no"))
            if key in seen_keys:
                issues.append(Issue("error", "E-DUP-NO",
                                    f"同一试卷题号重复，冲突记录 {seen_keys[key]}", qid, where))
            else:
                seen_keys[key] = where

        if q.get("difficulty") is not None and not (1 <= int(q["difficulty"]) <= 5):
            issues.append(Issue("error", "E-DIFF", "difficulty 需为 1-5 或 null", qid, where))

    return issues


def validate_papers(papers: list[dict], reg_idx: dict[str, dict] | None = None,
                    validators: dict[str, Any] | None = None) -> list[Issue]:
    reg_idx = reg_idx if reg_idx is not None else registry_index()
    validators = validators if validators is not None else schema_validators()
    issues: list[Issue] = []
    seen: set[str] = set()
    for p in papers:
        pid = p.get("id", "<missing-id>")
        where = f"{p.get('__file__','?')}:{p.get('__line__','?')}"
        v = validators.get("paper")
        if v is not None:
            clean = {k: v2 for k, v2 in p.items() if not k.startswith("__")}
            for err in sorted(v.iter_errors(clean), key=lambda e: list(e.path)):
                issues.append(Issue("error", "E-SCHEMA", "/".join(map(str, err.path)) + ": " + err.message, pid, where))
        if pid in seen:
            issues.append(Issue("error", "E-DUP-ID", "试卷 id 重复", pid, where))
        seen.add(pid)
        src = p.get("source") or {}
        if src.get("source_id") not in reg_idx:
            issues.append(Issue("error", "E-SRC-UNKNOWN", f"source_id 未登记：{src.get('source_id')!r}", pid, where))
        if not src.get("url"):
            issues.append(Issue("error", "E-SRC-NOURL", "缺少 source.url", pid, where))
    return issues


# ---------------------------------------------------------------------- dedup
def find_duplicates(questions: list[dict], threshold: float = 0.92) -> list[dict]:
    """精确重复 + 近似重复（同年份同学科内做 difflib 比对）。"""
    buckets: dict[tuple, list[dict]] = {}
    for q in questions:
        if "__parse_error__" in q:
            continue
        buckets.setdefault((q.get("year"), q.get("subject")), []).append(q)

    dups: list[dict] = []
    exact: dict[str, str] = {}
    for q in questions:
        if "__parse_error__" in q:
            continue
        h = norm_text(q.get("stem", ""))[:400]
        if not h:
            continue
        k = hashlib.sha1(h.encode()).hexdigest()
        if k in exact:
            dups.append({"kind": "exact", "id": q.get("id"), "dup_of": exact[k]})
        else:
            exact[k] = q.get("id", "?")

    import difflib
    for (_y, _s), group in buckets.items():
        if len(group) > 400:  # 大分组跳过近邻比对，避免 O(n^2) 爆炸
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = norm_text(group[i].get("stem", "")), norm_text(group[j].get("stem", ""))
                if not a or not b:
                    continue
                if abs(len(a) - len(b)) / max(len(a), len(b)) > 0.3:
                    continue
                if difflib.SequenceMatcher(None, a, b).ratio() >= threshold:
                    dups.append({"kind": "near", "id": group[j].get("id"), "dup_of": group[i].get("id"),
                                 "ratio": round(difflib.SequenceMatcher(None, a, b).ratio(), 3)})
    return dups


# ---------------------------------------------------------------------- stats
def summarize(questions: list[dict], papers: list[dict]) -> dict:
    def tally(items, key):
        out: dict[str, int] = {}
        for it in items:
            k = it.get(key)
            out[str(k)] = out.get(str(k), 0) + 1
        return dict(sorted(out.items(), key=lambda kv: (-kv[1], kv[0])))

    good = [q for q in questions if "__parse_error__" not in q]
    tiers: dict[str, int] = {}
    for q in good:
        t = (q.get("source") or {}).get("tier", "?")
        tiers[t] = tiers.get(t, 0) + 1
    return {
        "questions": len(good),
        "papers": len(papers),
        "by_subject": tally(good, "subject"),
        "by_year": tally(good, "year"),
        "by_region": tally(good, "region"),
        "by_paper": tally(good, "paper"),
        "by_type": tally(good, "type"),
        "by_exam_type": tally(good, "exam_type"),
        "by_source_tier": dict(sorted(tiers.items())),
        "by_verification": by_verification(good),
        "with_answer": sum(1 for q in good if q.get("answer") not in (None, "", []) or q.get("answer_text")),
        "with_analysis": sum(1 for q in good if q.get("analysis")),
    }


def by_verification(questions: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for q in questions:
        if "__parse_error__" in q:
            continue
        s = ((q.get("verification") or {}).get("status")) or "?"
        out[s] = out.get(s, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: (-kv[1], kv[0])))
