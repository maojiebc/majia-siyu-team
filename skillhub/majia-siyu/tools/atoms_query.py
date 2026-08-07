#!/usr/bin/env python3
"""对本地 JSONL 原子库做轻量过滤与关键词检索（v1 私有库与 v2 正式集双轨兼容）。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


DEFAULT_FILE = Path(__file__).resolve().parents[1] / "knowledge/03-majia-sop/atoms.jsonl"


def split_values(values: list[str] | None) -> set[str]:
    return {item.strip() for value in values or [] for item in value.split(",") if item.strip()}


def _join(items: object) -> str:
    if isinstance(items, list):
        return " ".join(str(item) for item in items)
    return ""


def haystack_of(atom: dict) -> str:
    """按 schema 版本拼关键词检索文本：v1 搜 knowledge/original，v2 搜 statement 与适用性。"""
    parts: list[str] = []
    if atom.get("schema_version") == "2.0" or "statement" in atom:
        parts.append(str(atom.get("statement", "")))
        applicability = atom.get("applicability") or {}
        if isinstance(applicability, dict):
            for field in ("preconditions", "recommended_action", "failure_modes", "counterexamples"):
                parts.append(_join(applicability.get(field)))
            for metric in applicability.get("metrics") or []:
                if isinstance(metric, dict):
                    parts.append(f"{metric.get('name', '')} {metric.get('definition', '')}")
        source = atom.get("source") or {}
        if isinstance(source, dict):
            parts.append(f"{source.get('label', '')} {source.get('locator', '')}")
    else:
        parts.append(str(atom.get("knowledge", "")))
        parts.append(str(atom.get("original", "")))
    parts.append(_join(atom.get("topics")))
    parts.append(_join(atom.get("skills")))
    return " ".join(parts).casefold()


def main() -> int:
    parser = argparse.ArgumentParser(description="按 skill、主题、类型和关键词查询知识原子")
    parser.add_argument("keywords", nargs="*", help="关键词；全部命中才返回")
    parser.add_argument("--file", type=Path, default=DEFAULT_FILE)
    parser.add_argument("--skills", action="append", help="skill 名，可重复或逗号分隔")
    parser.add_argument("--topics", action="append", help="主题，可重复或逗号分隔")
    parser.add_argument("--type", dest="types", action="append", help="原子类型，可重复或逗号分隔")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()
    if not args.file.is_file():
        parser.error(f"原子库不存在：{args.file}；真实语料待灌注时可用 --file 指向 example")

    wanted_skills = split_values(args.skills)
    wanted_topics = split_values(args.topics)
    wanted_types = split_values(args.types)
    keywords = [x.casefold() for x in args.keywords]
    matched = 0
    for line_no, raw in enumerate(args.file.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            atom = json.loads(raw)
        except json.JSONDecodeError as exc:
            print(f"跳过第 {line_no} 行：JSON 错误 {exc.msg}", file=sys.stderr)
            continue
        if wanted_skills and not wanted_skills.intersection(atom.get("skills", [])):
            continue
        if wanted_topics and not wanted_topics.intersection(atom.get("topics", [])):
            continue
        if wanted_types and atom.get("type") not in wanted_types:
            continue
        haystack = haystack_of(atom)
        if any(keyword not in haystack for keyword in keywords):
            continue
        print(json.dumps(atom, ensure_ascii=False))
        matched += 1
        if matched >= args.limit:
            break
    print(f"命中 {matched} 条", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
