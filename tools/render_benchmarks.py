#!/usr/bin/env python3
"""把 type=benchmark 的原子按业态×规模带聚合成社区基线说明。"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import re
import statistics
import sys
from typing import Mapping

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from siyu_team.knowledge.models import KnowledgeAtomV2, KnowledgeValidationError  # noqa: E402

NUMBER = re.compile(r"(\d+(?:\.\d+)?)\s*%?")
INDUSTRY_ZH = {"catering": "餐饮", "retail": "零售", "other": "其他"}
BAND_ORDER = (
    "1",
    "2-10",
    "11-50",
    "51-300",
    "301-1000",
    "1001-5000",
    "5000+",
    "any",
)


def _read_jsonl(path: Path) -> list[KnowledgeAtomV2]:
    if not path.is_file():
        return []
    atoms: list[KnowledgeAtomV2] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        try:
            atoms.append(KnowledgeAtomV2.from_json(raw))
        except (KnowledgeValidationError, ValueError, TypeError):
            continue
    return atoms


def _all_atoms(knowledge_root: Path) -> list[KnowledgeAtomV2]:
    atoms: list[KnowledgeAtomV2] = []
    approved = knowledge_root / "04-atoms/growth-layers.approved.jsonl"
    atoms.extend(_read_jsonl(approved))
    community = knowledge_root / "05-community"
    if community.is_dir():
        for path in sorted(community.glob("*.jsonl")):
            if path.name in {"pending.jsonl", "rejected.jsonl", "revoked.jsonl"}:
                continue
            atoms.extend(_read_jsonl(path))
    return atoms


def _numbers(atom: KnowledgeAtomV2) -> list[float]:
    texts = [atom.statement, *(metric.definition for metric in atom.applicability.metrics)]
    found: list[float] = []
    for text in texts:
        for match in NUMBER.finditer(text):
            found.append(float(match.group(1)))
    return found


def _group_key(atom: KnowledgeAtomV2) -> list[tuple[str, str]]:
    industry = atom.scope.industry or "any"
    bands = atom.scope.scale_band or ("any",)
    return [(industry, band) for band in bands]


def _band_rank(band: str) -> tuple[int, str]:
    try:
        return (BAND_ORDER.index(band), band)
    except ValueError:
        return (len(BAND_ORDER), band)


def _group_sort_key(item: tuple[str, str]) -> tuple[str, int, str]:
    industry, band = item
    rank, name = _band_rank(band)
    return (industry, rank, name)


def load_benchmark_index(knowledge_root: Path) -> dict[tuple[str, str], str]:
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for atom in _all_atoms(knowledge_root):
        if atom.type != "benchmark":
            continue
        values = _numbers(atom)
        for key in _group_key(atom):
            counts[key] += 1
            grouped[key].extend(values)
    index: dict[tuple[str, str], str] = {}
    for key, values in grouped.items():
        industry, band = key
        label = f"{INDUSTRY_ZH.get(industry, industry)} × {band}"
        n = counts[key]
        if not values:
            index[key] = f"{label}：n={n}，投稿未带可解析数字"
            continue
        mid = statistics.median(values)
        index[key] = (
            f"{label}：n={n}，中位数 {mid:g}，区间 {min(values):g}–{max(values):g}"
        )
    return index


def render_markdown(index: Mapping[tuple[str, str], str]) -> str:
    lines = [
        "# 社区数字基线",
        "",
        "由 `type=benchmark` 的社区原子按业态 × 门店规模带汇总。数字来自投稿原文，未做因果解释。",
        "规模带：`1` / `2-10` / `11-50` / `51-300` / `301-1000` / `1001-5000` / `5000+` / `any`。",
        "没有投稿的格子不出现。维护者可用这些行做同规模对照，不能当成官方 KPI。",
        "",
    ]
    if not index:
        lines.append("目前还没有可汇总的社区数字基线。")
        lines.append("")
        return "\n".join(lines)
    for key in sorted(index, key=_group_sort_key):
        lines.append(f"- {index[key]}")
    lines.append("")
    return "\n".join(lines)


def render_benchmarks(knowledge_root: Path | None = None) -> Path:
    root = knowledge_root or (ROOT / "knowledge")
    index = load_benchmark_index(root)
    target = root / "02-industry/benchmarks.community.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    text = render_markdown(index)
    if not target.is_file() or target.read_text(encoding="utf-8") != text:
        target.write_text(text, encoding="utf-8")
    return target


def main() -> int:
    parser_root = ROOT / "knowledge"
    path = render_benchmarks(parser_root)
    print(f"已写入 {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
