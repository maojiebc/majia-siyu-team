#!/usr/bin/env python3
"""把 md/txt 语料按段落切成待人工提炼的 JSONL 草稿。"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import sys


def current_quarter() -> str:
    now = datetime.now().astimezone()
    return f"{now.year}Q{(now.month - 1) // 3 + 1}"


def clean_block(block: str) -> str:
    lines = [line.strip() for line in block.splitlines()]
    lines = [line for line in lines if line and not line.startswith("```")]
    text = " ".join(lines)
    return re.sub(r"\s+", " ", text).strip()


def iter_candidates(root: Path, min_chars: int):
    files = [root] if root.is_file() else sorted(
        p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in {".md", ".txt"}
    )
    for path in files:
        if path.suffix.lower() not in {".md", ".txt"}:
            continue
        text = path.read_text(encoding="utf-8")
        if text.startswith("---\n"):
            parts = text.split("\n---\n", 1)
            if len(parts) == 2:
                text = parts[1]
        source = path.name if root.is_file() else path.relative_to(root).as_posix()
        date = datetime.fromtimestamp(path.stat().st_mtime).astimezone().date().isoformat()
        for block in re.split(r"\n\s*\n", text):
            cleaned = clean_block(block)
            if len(cleaned) < min_chars or re.fullmatch(r"#{1,6}\s+.*", cleaned):
                continue
            yield source, date, cleaned[:200]


def main() -> int:
    parser = argparse.ArgumentParser(description="按段落切分候选知识原子；knowledge 留空待人工填写")
    parser.add_argument("source", type=Path, help="md/txt 文件或语料目录")
    parser.add_argument("--output", type=Path, help="输出 JSONL；省略时写到 stdout")
    parser.add_argument("--quarter", default=current_quarter(), help="ID 季度前缀，如 2026Q3")
    parser.add_argument("--min-chars", type=int, default=20, help="最短候选段落字符数")
    parser.add_argument("--force", action="store_true", help="允许覆盖已有输出文件")
    args = parser.parse_args()

    if not args.source.exists():
        parser.error(f"语料不存在：{args.source}")
    if not re.fullmatch(r"\d{4}Q[1-4]", args.quarter):
        parser.error("--quarter 必须形如 2026Q3")
    if args.output and args.output.exists() and not args.force:
        parser.error(f"输出已存在：{args.output}；如需覆盖请加 --force")

    rows = []
    for index, (source, date, original) in enumerate(iter_candidates(args.source, args.min_chars), 1):
        rows.append({
            "id": f"{args.quarter}_{index:03d}",
            "knowledge": "",
            "original": original,
            "source": source,
            "date": date,
            "topics": [],
            "skills": [],
            "type": "insight",
            "confidence": "low",
        })

    payload = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
        print(f"已切分 {len(rows)} 条候选：{args.output}")
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
