#!/usr/bin/env python3
"""Cross-check Python routes, published skills, industry packs and knowledge refs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE = ROOT / "skillhub/majia-siyu"
ALLOWED_INDUSTRY_STATUS = {"supported_with_industry_pack", "generic_only"}


def normalize_skill_slug(value: str) -> str:
    return value.strip().lstrip("/")


def published_repo_skills(root: Path) -> set[str]:
    skills = {
        path.parent.name
        for path in (root / "plugins").glob("**/skills/*/SKILL.md")
    }
    skills.update(
        path.stem
        for path in (root / "plugins/_orchestrator/commands").glob("*.md")
    )
    skills.add("majia-siyu")
    return skills


def published_bundle_skills(bundle: Path) -> set[str]:
    index_file = bundle / "modules/index.json"
    if not index_file.is_file():
        return set()
    data = json.loads(index_file.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return set()
    return {normalize_skill_slug(str(key)) for key in data} | {"majia-siyu"}


def _bundle_knowledge_path(bundle: Path, reference: str) -> Path:
    if reference.startswith("knowledge/"):
        reference = "modules/_knowledge/" + reference.removeprefix("knowledge/")
    return bundle / reference


def _load_runtime(root: Path) -> tuple[Any, Any, Any, Any, Any]:
    source = str(root / "src")
    if source not in sys.path:
        sys.path.insert(0, source)
    from siyu_team.routing import (  # noqa: PLC0415
        INDUSTRY_BOOKS,
        INDUSTRY_CAPABILITIES,
        TASK_ROUTES,
        route_task,
    )
    from siyu_team.task import Task, TaskKind  # noqa: PLC0415

    return TASK_ROUTES, route_task, Task, TaskKind, (
        INDUSTRY_CAPABILITIES,
        INDUSTRY_BOOKS,
    )


def check_contracts(root: Path = ROOT, bundle: Path = DEFAULT_BUNDLE) -> list[str]:
    root = root.resolve(strict=False)
    bundle = bundle.resolve(strict=False)
    task_routes, route_task, task_type, task_kind, industry_data = _load_runtime(root)
    industry_capabilities, industry_books = industry_data
    repo_skills = published_repo_skills(root)
    bundle_skills = published_bundle_skills(bundle)
    errors: list[str] = []

    for kind, (raw_skill, _reason) in task_routes.items():
        skill = normalize_skill_slug(raw_skill)
        if skill not in repo_skills:
            errors.append(f"{kind.value}: 路由目标未发布：{raw_skill}")
        if skill not in bundle_skills:
            errors.append(f"{kind.value}: SkillHub 缺少路由目标：{raw_skill}")

    for industry, status in industry_capabilities.items():
        if status not in ALLOWED_INDUSTRY_STATUS:
            errors.append(f"{industry}: 未知行业能力状态：{status}")
            continue
        book = industry_books.get(industry)
        if status == "generic_only" and book is not None:
            errors.append(f"{industry}: generic_only 不得声明行业册：{book}")
        if status == "supported_with_industry_pack":
            if not book:
                errors.append(f"{industry}: 声明有行业包但未给路径")
            elif not (root / book).is_dir():
                errors.append(f"{industry}: 行业包不存在：{book}")

    seen_refs: set[str] = set()
    for kind in task_kind:
        for industry in ("", "catering", "retail", "edu"):
            for stage in ("", "cold", "growth", "mature"):
                task = task_type(
                    kind=kind,
                    source_text=kind.value,
                    industry=industry,
                    stage=stage,
                )
                decision = route_task(task)
                for reference in decision.knowledge_refs:
                    if reference in seen_refs:
                        continue
                    seen_refs.add(reference)
                    if not (root / reference).exists():
                        errors.append(f"RouteDecision 知识引用不存在：{reference}")
                    if not _bundle_knowledge_path(bundle, reference).exists():
                        errors.append(f"SkillHub 知识引用不存在：{reference}")

    atoms_file = root / "knowledge/04-atoms/growth-layers.approved.jsonl"
    if atoms_file.is_file():
        for line_no, line in enumerate(
            atoms_file.read_text(encoding="utf-8").splitlines(), 1
        ):
            if not line.strip():
                continue
            row = json.loads(line)
            for raw_skill in row.get("skills", []):
                skill = normalize_skill_slug(str(raw_skill))
                if skill not in repo_skills:
                    errors.append(
                        f"{atoms_file.relative_to(root)}:{line_no}: "
                        f"绑定未发布 skill：{raw_skill}"
                    )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="检查路由与分发契约")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    args = parser.parse_args()
    errors = check_contracts(args.root, args.bundle)
    if errors:
        print(f"路由契约检查失败：{len(errors)} 个问题")
        for error in errors:
            print(f"- {error}")
        return 1
    print("路由契约检查通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
