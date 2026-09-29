#!/usr/bin/env python3
"""把 deekur/gaokaophysics（历年高考物理真题原卷 PDF 档案）转成试卷级清单。

原卷是 PDF/图片，仓库不复制二进制文件，只登记：年份、卷别、适用地区、文件路径、sha256。
这样既拿到了 1952-2026 的完整试卷骨架（用于覆盖度统计与后续 OCR/录入），又不搬运大文件。

用法：
    git clone --depth 1 https://github.com/deekur/gaokaophysics.git /tmp/gaokaophysics
    python3 sources/adapters/gaokaophysics_papers.py --repo /tmp/gaokaophysics \
        --out data/papers/archive_physics.jsonl
    python3 -m tools.qbnk.cli validate     # 新记录必须能通过校验
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from urllib.parse import quote

from _common import REPO_ROOT, build_paper_record, parse_paper_filename, sha256_file, write_jsonl

SOURCE_ID = "gh-gaokaophysics"
SOURCE_NAME = "GitHub deekur/gaokaophysics：历年高考物理真题原卷（1952-2026）"
SOURCE_URL = "https://github.com/deekur/gaokaophysics"
SUBJECT = "物理"


def collect(repo: Path, with_hash: bool = True) -> list[dict]:
    out: list[dict] = []
    files = sorted(p for p in repo.rglob("*.pdf") if ".git" not in p.parts)
    for i, f in enumerate(files, 1):
        info = parse_paper_filename(f.stem)
        if not info["year"]:
            continue
        rel = f.relative_to(repo).as_posix()
        suspicious = bool(info["notes"])
        artifact = {
            "kind": "pdf",
            "url": f"{SOURCE_URL}/blob/main/{quote(rel)}",
            "local_path": rel,
            "sha256": sha256_file(f) if with_hash else "",
            "note": "原卷 PDF 存放于外部仓库，本库不复制",
        }
        out.append(build_paper_record(
            year=info["year"], subject=SUBJECT, label=info["label"], regions=info["regions"],
            seq=i, source_id=SOURCE_ID, source_name=SOURCE_NAME, source_url=artifact["url"],
            tier="T3", artifact=artifact, notes=info["notes"], suspicious=suspicious,
            exam_type="真题" if "春季" not in rel else "真题",
        ))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", required=True, help="gaokaophysics 本地克隆目录")
    ap.add_argument("--out", default=str(REPO_ROOT / "data/papers/archive_physics.jsonl"))
    ap.add_argument("--no-hash", action="store_true", help="跳过 sha256（大仓库提速）")
    args = ap.parse_args()

    repo = Path(args.repo).expanduser().resolve()
    if not repo.exists():
        print(f"✗ 找不到仓库目录：{repo}\n  先执行：git clone --depth 1 https://github.com/deekur/gaokaophysics.git {repo}")
        return 1
    recs = collect(repo, with_hash=not args.no_hash)
    n = write_jsonl(Path(args.out), recs)
    flagged = sum(1 for r in recs if r["verification"]["status"] == "conflict")
    print(f"✔ 生成 {n} 条试卷档案索引 → {args.out}（其中 {flagged} 条因文件名自述存疑被标为 conflict）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
