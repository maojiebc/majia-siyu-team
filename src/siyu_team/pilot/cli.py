"""``siyu-pilot`` 离线验证命令。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence

from siyu_team.knowledge import KnowledgeValidationError

from .blind import create_blind_pairs
from .editorial import render_editorial_report, summarize_editorial
from .models import PilotValidationError
from .packets import (
    REPOSITORY_ROOT,
    load_atoms,
    load_mapping,
    load_tasks,
    prepare_run,
    validate_atoms,
    validate_mapping,
    validate_tasks,
)
from .scoring import score_run, write_score_report


FIXTURE_ROOT = REPOSITORY_ROOT / "tests" / "fixtures" / "pilot"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="siyu-pilot",
        description="离线知识共建验证工具（不调用模型或飞书 API）",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate", help="校验 Golden Tasks、Atom 和映射")
    validate.add_argument("--fixtures", action="store_true", help="校验仓库内合成数据")
    validate.add_argument("--tasks", type=Path)
    validate.add_argument("--atoms", type=Path)
    validate.add_argument("--mapping", type=Path)
    validate.add_argument(
        "--allow-public-atoms",
        action="store_true",
        help="允许校验仓库内公开 approved 原子（跳过 0600 权限要求）",
    )

    prepare = commands.add_parser("prepare", help="生成私有双版 Prompt 试验包")
    prepare.add_argument("--tasks", required=True, type=Path)
    prepare.add_argument("--atoms", required=True, type=Path)
    prepare.add_argument("--mapping", required=True, type=Path)
    prepare.add_argument("--output", required=True, type=Path)
    prepare.add_argument("--seed", required=True, type=int)
    prepare.add_argument("--model-name", default="")
    prepare.add_argument("--host", default="")
    prepare.add_argument("--generated-at", default="")
    prepare.add_argument("--temperature", default="")
    prepare.add_argument("--max-output", default=0, type=int)
    prepare.add_argument("--limit", type=int)
    prepare.add_argument(
        "--fixture-atoms", action="store_true", help="仅开发 Dry Run 时允许仓库合成 Atom"
    )

    blind = commands.add_parser("blind", help="将已生成的左右答案稳定随机化")
    blind.add_argument("--run", required=True, type=Path)

    score = commands.add_parser("score", help="汇总盲测评分并判定 H1")
    score.add_argument("--run", required=True, type=Path)
    score.add_argument("--ratings", required=True, nargs="+", type=Path)
    score.add_argument("--output", required=True, type=Path)

    editorial = commands.add_parser("editorial-report", help="汇总 Phase 0 审核日志")
    editorial.add_argument("--input", required=True, type=Path)
    editorial.add_argument("--output", required=True, type=Path)
    return parser


def _paths(args: argparse.Namespace) -> tuple[Path, Path, Path, bool]:
    if args.fixtures:
        return (
            FIXTURE_ROOT / "golden-tasks.jsonl",
            FIXTURE_ROOT / "synthetic-approved-atoms.jsonl",
            FIXTURE_ROOT / "task-atom-map.json",
            True,
        )
    missing = [name for name in ("tasks", "atoms", "mapping") if getattr(args, name) is None]
    if missing:
        raise PilotValidationError(
            "未使用 --fixtures 时必须提供：" + ", ".join(f"--{name}" for name in missing)
        )
    allow_public = bool(getattr(args, "allow_public_atoms", False))
    return args.tasks, args.atoms, args.mapping, allow_public


def _validate_inputs(
    tasks_path: Path, atoms_path: Path, mapping_path: Path, *, fixture_mode: bool
) -> tuple[Any, Any, Any]:
    tasks = load_tasks(tasks_path)
    atoms = load_atoms(atoms_path)
    mapping = load_mapping(mapping_path)
    validate_tasks(tasks)
    validate_atoms(atoms, atoms_path=atoms_path, fixture_mode=fixture_mode)
    validate_mapping(tasks, atoms, mapping)
    return tasks, atoms, mapping


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "validate":
            tasks_path, atoms_path, mapping_path, fixtures = _paths(args)
            tasks, atoms, _ = _validate_inputs(
                tasks_path, atoms_path, mapping_path, fixture_mode=fixtures
            )
            print(
                json.dumps(
                    {"status": "ok", "tasks": len(tasks), "atoms": len(atoms)},
                    ensure_ascii=False,
                )
            )
        elif args.command == "prepare":
            tasks, atoms, mapping = _validate_inputs(
                args.tasks,
                args.atoms,
                args.mapping,
                fixture_mode=args.fixture_atoms,
            )
            output = prepare_run(
                tasks=tasks,
                atoms=atoms,
                mapping=mapping,
                output=args.output,
                seed=args.seed,
                model_name=args.model_name,
                host=args.host,
                generated_at=args.generated_at,
                temperature=args.temperature,
                max_output=args.max_output,
                limit=args.limit,
            )
            print(output)
        elif args.command == "blind":
            print(create_blind_pairs(args.run))
        elif args.command == "score":
            result = score_run(args.run, args.ratings)
            print(write_score_report(args.run, result, args.output))
        elif args.command == "editorial-report":
            result = summarize_editorial(args.input)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(render_editorial_report(result), encoding="utf-8")
            print(args.output)
        return 0
    except (PilotValidationError, KnowledgeValidationError, OSError) as exc:
        print(f"siyu-pilot: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
