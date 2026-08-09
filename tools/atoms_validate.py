#!/usr/bin/env python3
"""校验知识原子 JSONL：v1 私有库走内置规则，v2 正式集走 KnowledgeAtomV2 契约。

两轨都做 id 唯一性与 skills 存在性校验；一份文件里允许混行（按行嗅探版本）。
"""
from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import re
import sys

TOOL_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = TOOL_ROOT.parent
# SkillHub 会把严格知识模型放到 tools/siyu_team；源码态则使用 src/。
# 两者都在 ``python -I`` 下显式注入，避免偷吃用户 site-packages。
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))
sys.path.insert(0, str(TOOL_ROOT))

try:
    from siyu_team.knowledge.models import (  # noqa: E402
        KnowledgeAtomV2,
        KnowledgeValidationError,
    )
except ImportError:  # SkillHub 分发态没有 src/：v2 校验降级为明确报错，v1 照常
    KnowledgeAtomV2 = None  # type: ignore[assignment, misc]
    KnowledgeValidationError = None  # type: ignore[assignment, misc]


REQUIRED = {"id", "knowledge", "original", "source", "date", "topics", "skills", "type", "confidence"}
TYPES = {"principle", "method", "case", "anti-pattern", "insight", "tool"}
CONFIDENCE = {"high", "medium", "low"}
TOPICS = {"社群运营", "内容运营", "用户增长", "转化", "留存", "复购", "合规", "活动", "话术", "数据"}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def known_skills(root: Path) -> set[str]:
    # 完整仓库扫 plugins/；SkillHub 单包布局扫 modules/。都没有则返回空集，
    # main 会给出警告并跳过 skills 存在性检查（其余校验照跑）。
    for base in ("plugins", "modules"):
        found = {p.parent.name for p in (root / base).rglob("SKILL.md")}
        if found:
            return found
    return set()


def is_v2(atom: dict) -> bool:
    return atom.get("schema_version") == "2.0" or "statement" in atom


def validate_atom_v2(atom: dict, line: int, skills: set[str]) -> list[str]:
    prefix = f"第 {line} 行"
    if KnowledgeAtomV2 is None:
        return [f"{prefix}: v2 校验需要完整仓库（src/siyu_team 不可导入）"]
    try:
        parsed = KnowledgeAtomV2.from_dict(atom)
    except KnowledgeValidationError as exc:
        return [f"{prefix}: v2 契约违规：{exc}"]
    unknown = [s for s in parsed.skills if s not in skills]
    if skills and unknown:
        return [f"{prefix}: skills 引用了不存在的目录 {unknown!r}"]
    if parsed.quality.review_status == "approved":
        applicability = parsed.applicability
        missing: list[str] = []
        if not applicability.preconditions:
            missing.append("precondition")
        if not applicability.recommended_action:
            missing.append("action")
        if not applicability.metrics and not any(
            "不适用" in item for item in applicability.preconditions
        ):
            missing.append("metric 或不适用说明")
        if not applicability.failure_modes and not applicability.counterexamples:
            missing.append("failure mode/counterexample")
        if missing:
            return [f"{prefix}: approved 原子缺少：{', '.join(missing)}"]
    return []


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
    elif skills and any(not isinstance(x, str) or x not in skills for x in atom["skills"]):
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
    v2_count = 0
    skills = known_skills(args.repo.resolve())
    if not skills:
        print("⚠️ 找不到 plugins/ 或 modules/ 下的 SKILL.md，跳过 skills 存在性检查", file=sys.stderr)
    for line_no, raw in enumerate(args.file.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        count += 1
        try:
            atom = json.loads(raw)
        except json.JSONDecodeError as exc:
            errors.append(f"第 {line_no} 行: JSON 错误：{exc.msg}")
            continue
        if isinstance(atom, dict) and is_v2(atom):
            v2_count += 1
            errors.extend(validate_atom_v2(atom, line_no, skills))
        else:
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
    print(
        f"校验通过：{count} 条原子（v1={count - v2_count}，v2={v2_count}），"
        f"{len(skills)} 个可引用 skill"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
