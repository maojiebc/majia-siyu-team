#!/usr/bin/env python3
"""Query the same strictly loaded public corpus used by Siyu Runtime."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src"
TOOL_ROOT = Path(__file__).resolve().parent
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))
if SOURCE.is_dir() and str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))

from siyu_team.errors import KnowledgeLoadError  # noqa: E402
from siyu_team.knowledge.corpus import CorpusLoader  # noqa: E402
from siyu_team.knowledge.paths import KnowledgePathResolver  # noqa: E402
from siyu_team.knowledge.query import KnowledgeQuery  # noqa: E402


def split_values(values: list[str] | None) -> tuple[str, ...]:
    return tuple(
        item.strip()
        for value in values or []
        for item in value.split(",")
        if item.strip()
    )


def _legacy_haystack(atom: dict[str, Any]) -> str:
    parts = [str(atom.get("knowledge", "")), str(atom.get("original", ""))]
    parts.extend(str(value) for value in atom.get("topics", []) if isinstance(value, str))
    parts.extend(str(value) for value in atom.get("skills", []) if isinstance(value, str))
    return " ".join(parts).casefold()


def _query_legacy(
    path: Path,
    *,
    skills: tuple[str, ...],
    topics: tuple[str, ...],
    types: tuple[str, ...],
    keywords: tuple[str, ...],
    limit: int,
    lenient: bool,
) -> int:
    """Keep explicit v1 `--file` queries working for one compatibility patch."""
    if limit == 0:
        print("命中 0 条（legacy explicit file）", file=sys.stderr)
        return 0
    matched = 0
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            atom = json.loads(raw)
        except json.JSONDecodeError as exc:
            if not lenient:
                raise KnowledgeLoadError(
                    f"{path}:{line_no} JSON 非法：{exc.msg}"
                ) from exc
            print(f"警告：跳过 {path}:{line_no}（{exc.msg}）", file=sys.stderr)
            continue
        if not isinstance(atom, dict):
            if not lenient:
                raise KnowledgeLoadError(f"{path}:{line_no} 必须是对象")
            continue
        atom_skills = {str(value).strip().lstrip("/") for value in atom.get("skills", [])}
        if skills and not {value.lstrip("/") for value in skills}.intersection(atom_skills):
            continue
        if topics and not set(topics).intersection(atom.get("topics", [])):
            continue
        if types and atom.get("type") not in types:
            continue
        haystack = _legacy_haystack(atom)
        if any(value.casefold() not in haystack for value in keywords):
            continue
        print(json.dumps(atom, ensure_ascii=False, separators=(",", ":")))
        matched += 1
        if matched >= limit:
            break
    print(f"命中 {matched} 条（legacy explicit file）", file=sys.stderr)
    return 0


def _looks_legacy(path: Path, *, lenient: bool) -> bool:
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            if lenient:
                continue
            raise KnowledgeLoadError(
                f"{path}:{line_no} JSON 非法：{exc.msg}"
            ) from exc
        return isinstance(value, dict) and value.get("schema_version") != "2.0"
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="按 skill、主题、类型和关键词查询知识原子")
    parser.add_argument("keywords", nargs="*", help="关键词；全部命中才返回")
    parser.add_argument("--file", type=Path, help="显式 approved JSONL；优先于自动发现")
    parser.add_argument("--manifest", type=Path, help="与 --file 联用的 manifest")
    parser.add_argument("--skills", action="append", help="skill 名，可重复或逗号分隔")
    parser.add_argument("--topics", action="append", help="主题，可重复或逗号分隔")
    parser.add_argument("--type", dest="types", action="append", help="原子类型，可重复或逗号分隔")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument(
        "--lenient",
        action="store_true",
        help="仅开发排查时跳过 malformed 行；默认 fail-closed",
    )
    args = parser.parse_args()
    if args.limit < 0:
        parser.error("--limit 不能为负数")
    if args.manifest is not None and args.file is None:
        parser.error("--manifest 必须与 --file 联用")

    skills = split_values(args.skills)
    topics = split_values(args.topics)
    types = split_values(args.types)
    keywords = tuple(str(value) for value in args.keywords)
    try:
        if args.file is not None:
            path = args.file.expanduser().resolve(strict=False)
            if not path.is_file():
                raise KnowledgeLoadError(f"原子库不存在：{path}")
            if _looks_legacy(path, lenient=args.lenient):
                return _query_legacy(
                    path,
                    skills=skills,
                    topics=topics,
                    types=types,
                    keywords=keywords,
                    limit=args.limit,
                    lenient=args.lenient,
                )

        resolver = KnowledgePathResolver(repository_root=ROOT, bundle_root=ROOT)
        loader = CorpusLoader(resolver=resolver, lenient=args.lenient)
        corpus = loader.load(args.file, manifest_path=args.manifest)
        if not corpus.atoms:
            print("当前没有可用知识库", file=sys.stderr)
            return 0
        result = KnowledgeQuery(corpus=corpus).search(
            skills=skills,
            topics=topics,
            types=types,
            keywords=keywords,
            limit=args.limit,
        )
        for atom in result.atoms:
            print(json.dumps(atom.to_dict(), ensure_ascii=False, separators=(",", ":")))
        for warning in result.warnings:
            print(f"警告：{warning}", file=sys.stderr)
        print(
            f"命中 {result.count} 条；corpus={result.corpus_version} "
            f"hash={result.corpus_hash}",
            file=sys.stderr,
        )
        return 0
    except (KnowledgeLoadError, OSError, ValueError) as exc:
        print(f"知识查询失败：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
