"""适配器公共工具：文件解析、记录构造、抓取礼仪。

所有适配器都遵循同一条铁律：产出的每条记录都必须带 source_id + 可点击的 url，
source_id 必须已在 sources/registry.json 登记，否则 qbnk validate 会直接报错。
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import date
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
USER_AGENT = "qbnk-collector/1.0 (+https://github.com/zhzx2026/gaokao-qbnk)"

PROVINCES = ["北京", "天津", "上海", "重庆", "河北", "山西", "辽宁", "吉林", "黑龙江", "江苏",
             "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南", "广东", "海南",
             "四川", "贵州", "云南", "陕西", "甘肃", "青海", "台湾", "内蒙古", "广西", "西藏",
             "宁夏", "新疆", "香港", "澳门"]

SLUG_MAP = {
    "北京": "beijing", "天津": "tianjin", "上海": "shanghai", "重庆": "chongqing",
    "河北": "hebei", "山西": "shanxi", "辽宁": "liaoning", "吉林": "jilin",
    "黑龙江": "heilongjiang", "江苏": "jiangsu", "浙江": "zhejiang", "安徽": "anhui",
    "福建": "fujian", "江西": "jiangxi", "山东": "shandong", "河南": "henan",
    "湖北": "hubei", "湖南": "hunan", "广东": "guangdong", "海南": "hainan",
    "四川": "sichuan", "贵州": "guizhou", "云南": "yunnan", "陕西": "shaanxi",
    "甘肃": "gansu", "青海": "qinghai", "内蒙古": "neimenggu", "广西": "guangxi",
    "西藏": "xizang", "宁夏": "ningxia", "新疆": "xinjiang",
    "全国": "quanguo", "全国卷": "quanguo", "全国甲卷": "quanguojia", "全国乙卷": "quanguoyi",
    "新高考I卷": "xingaokao1", "新高考II卷": "xingaokao2",
    "新课标I卷": "xinkebiao1", "新课标II卷": "xinkebiao2",
    "春季高考": "chunji", "未知": "unknown",
}

SUSPICIOUS = ("不明", "不确定", "存疑", "待考", "来源网络")


# --------------------------------------------------------------------- 抓取
def polite_get(url: str, timeout: float = 20.0, referer: str | None = None) -> str:
    """带限速与 UA 的 GET。仅用于公开发布页；遇到 403/429 直接抛错，不做绕过。"""
    headers = {"User-Agent": USER_AGENT}
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        enc = r.headers.get_content_charset() or "utf-8"
    time.sleep(1.0)  # 单域名限速：≥1s
    return raw.decode(enc, errors="replace")


def robots_allows(url: str, timeout: float = 10.0) -> bool:
    """极简 robots.txt 检查：只判断本 UA 是否被整体禁止。抓不到 robots 视为允许。"""
    parts = urllib.parse.urlparse(url)
    robots = f"{parts.scheme}://{parts.netloc}/robots.txt"
    try:
        txt = polite_get(robots, timeout=timeout)
    except Exception:
        return True
    agent_block = False
    for line in txt.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        low = line.lower()
        if low.startswith("user-agent:"):
            agent = low.split(":", 1)[1].strip()
            agent_block = agent in ("*", "qbnk-collector")
        elif agent_block and low.startswith("disallow:"):
            path = line.split(":", 1)[1].strip()
            if path == "/":
                return False
    return True


# --------------------------------------------------------------------- IO
def write_jsonl(path: Path, records: Iterable[dict], sort_key: str = "id") -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    recs = sorted(records, key=lambda r: r.get(sort_key, ""))
    with path.open("w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(recs)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ----------------------------------------------------------------- 文件名解析
PAREN = re.compile(r"[（(]([^）)]*)[）)]")


def parse_paper_filename(stem: str) -> dict:
    """从 `2024新高考1(山东,广东,…).pdf` 之类的文件名里解析年份、卷别、适用地区。"""
    year = None
    m = re.match(r"^(\d{4})", stem)
    if m:
        year = int(m.group(1))
        rest = stem[m.end():]
    else:
        rest = stem
    parens = PAREN.findall(rest)
    label = PAREN.sub("", rest).strip()
    notes = "；".join(p for p in parens if any(k in p for k in ("不明", "不确定", "存疑", "来源网络", "待考")))
    regions = [p for p in parens if p not in (notes,) and p]
    label = (label.replace("新高考1", "新高考I卷").replace("新高考2", "新高考II卷")
                  .replace("新高考Ⅰ", "新高考I").replace("新高考Ⅱ", "新高考II"))
    if not label:
        label = "全国卷"
    return {"year": year, "label": label, "regions": regions, "notes": notes}


def slug_for(label: str, fallback: str) -> str:
    if label in SLUG_MAP:
        return SLUG_MAP[label]
    for k, v in SLUG_MAP.items():
        if k in label:
            return v
    return fallback


def build_paper_record(*, year: int, subject: str, label: str, regions: list[str], seq: int,
                       source_id: str, source_name: str, source_url: str, tier: str,
                       artifact: dict | None, notes: str = "", exam_type: str = "真题",
                       suspicious: bool = False, slug_hint: str = "") -> dict:
    """构造一份"试卷级"记录（原卷未录入题目时，仅登记档案位置）。"""
    subj_code = {"语文": "yw", "数学": "sx", "英语": "yy", "物理": "wl", "化学": "hx",
                 "生物": "sw", "政治": "zz", "历史": "ls", "地理": "dl"}.get(subject, "qt")
    slug = slug_for(label, slug_hint or f"z{seq:03d}")
    region = "全国"
    paper = label
    if label in SLUG_MAP and label in ("北京", "天津", "上海", "重庆", "浙江", "江苏", "山东", "广东"):
        region = label
        paper = f"{label}卷"
    elif any(p in label for p in PROVINCES) or (regions and len(regions) == 1 and "," not in regions[0]):
        region = "多省" if "," in label else label
        paper = label
    today = date.today().isoformat()
    return {
        "id": f"p-{year}-{subj_code}-{slug}-{seq:03d}",
        "schema_version": "1.0",
        "title": f"{year}年普通高等学校招生全国统一考试 {subject}（{label}）",
        "subject": subject,
        "stage": "高考",
        "exam_type": exam_type,
        "year": year,
        "region": region,
        "paper": paper,
        "exam_system": "新高考" if "新高考" in label else ("未知" if year < 2014 else "老高考"),
        "duration_minutes": None,
        "total_score": None,
        "question_ids": [],
        "source": {
            "source_id": source_id,
            "name": source_name,
            "publisher": source_name,
            "url": source_url,
            "tier": tier,
            "published_at": "",
            "fetched_at": today,
            "license": "外部仓库自带许可，导入前须复核；原卷版权归命题机构",
            "evidence": [],
        },
        "verification": {
            "status": "conflict" if suspicious else "single_source",
            "method": "filename-derived（文件名自述存疑）" if suspicious else "filename-derived（外部档案索引）",
            "checked_at": today,
            "notes": "仅登记原卷档案位置，题目正文尚未录入" + (f"；{notes}" if notes else ""),
        },
        "artifact": artifact,
        "notes": f"适用地区：{'、'.join(regions)}" if regions else "",
        "created_at": today,
        "updated_at": today,
    }
