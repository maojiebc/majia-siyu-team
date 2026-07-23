#!/usr/bin/env python3
"""校验知识原子 JSONL 的 schema、枚举、唯一性与 skill 引用。"""
from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import re


REQUIRED = {"id", "knowledge", "original", "source", "date", "topics", "skills", "type", "confidence"}
TYPES = {"principle", "method", "case", "anti-pattern", "insight", "tool"}
CONFIDENCE = {"high", "medium", "low"}
TOPICS = {"社群运营", "内容运营", "用户增长", "转化", "留存", "复购", "合规", "活动", "话术", "数据"}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def known_skills(root: Path) -> set[str]:
    return {p.parent.name for p in (root / "plugins").rglob("SKILL.md")}


def validate_atom(atom: object, line: int, skills: set[str]) -> list[str]:
    prefix = f"第 {line} 行"
    if not isinstance(atom, dict):
        return [f"{prefix}: 必须是 JSON object"]
    errors = []
    missing = REQUIRED - atom.keys()
    if missing:
        errors.append(f"{prefix}: 缺字段 {sorted(missing)}")
        return errors
    for field in ("id", "knowledge", "original", "source", "date"):
        if not isinstance(atom[field], str) or not atom[field].strip():
            errors.append(f"{prefix}: {field} 必须是非空字符串")
    if isinstance(atom["id"], str) and not re.fullmatch(r"\d{4}Q[1-4]_\d{3,}", atom["id"]):
        errors.append(f"{prefix}: id 格式错误 {atom['id']!r}")
    if isinstance(atom["original"], str) and len(atom["original"]) > 200:
        errors.append(f"{prefix}: original 超过 200 字")
    if isinstance(atom["date"], str):
        try:
            date.fromisoformat(atom["date"])
        except ValueError:
            errors.append(f"{prefix}: date 必须是 YYYY-MM-DD")
    if not isinstance(atom["topics"], list) or not atom["topics"]:
        errors.append(f"{prefix}: topics 必须是非空数组")
    elif any(not isinstance(x, str) or x not in TOPICS for x in atom["topics"]):
        errors.append(f"{prefix}: topics 含未定义主题 {atom['topics']!r}")
    if not isinstance(atom["skills"], list) or not atom["skills"]:
        errors.append(f"{prefix}: skills 必须至少绑定一个 skill")
    elif any(not isinstance(x, str) or x not in skills for x in atom["skills"]):
        errors.append(f"{prefix}: skills 引用了不存在的目录 {atom['skills']!r}")
    if not isinstance(atom["type"], str) or atom["type"] not in TYPES:
        errors.append(f"{prefix}: type 枚举错误 {atom['type']!r}")
    if not isinstance(atom["confidence"], str) or atom["confidence"] not in CONFIDENCE:
        errors.append(f"{prefix}: confidence 枚举错误 {atom['confidence']!r}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="校验知识原子 JSONL")
    parser.add_argument("file", type=Path)
    parser.add_argument("--repo", type=Path, default=repo_root())
    args = parser.parse_args()
    if not args.file.is_file():
        parser.error(f"文件不存在：{args.file}")

    errors, seen, count = [], {}, 0
    skills = known_skills(args.repo.resolve())
    for line_no, raw in enumerate(args.file.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        count += 1
        try:
            atom = json.loads(raw)
        except json.JSONDecodeError as exc:
            errors.append(f"第 {line_no} 行: JSON 错误：{exc.msg}")
            continue
        errors.extend(validate_atom(atom, line_no, skills))
        if isinstance(atom, dict) and isinstance(atom.get("id"), str):
            if atom["id"] in seen:
                errors.append(f"第 {line_no} 行: id {atom['id']!r} 与第 {seen[atom['id']]} 行重复")
            seen[atom["id"]] = line_no

    if not count:
        errors.append("文件没有原子")
    if errors:
        for error in errors:
            print("❌", error)
        print(f"校验失败：{count} 条，{len(errors)} 个问题")
        return 1
    print(f"校验通过：{count} 条原子，{len(skills)} 个可引用 skill")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
