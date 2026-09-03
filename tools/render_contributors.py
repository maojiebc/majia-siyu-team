#!/usr/bin/env python3
"""把社区原子聚合成公开贡献者墙。不输出公司名或哈希。"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from siyu_team.contribution.intake import ANON_LABEL  # noqa: E402
from siyu_team.knowledge.models import KnowledgeAtomV2, KnowledgeValidationError  # noqa: E402

SKIP_FILES = frozenset({"seeds.retail.jsonl", "revoked.jsonl"})
TITLE = "贡献者"
INTRO = "每条经验背后都是一个真的踩过坑或验过招的同行，按提交条数排序，不显示公司名"
EMPTY = "目前还没有公开署名的社区投稿。"


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


def _community_atoms(knowledge_root: Path) -> list[KnowledgeAtomV2]:
    community = knowledge_root / "05-community"
    if not community.is_dir():
        return []
    atoms: list[KnowledgeAtomV2] = []
    for path in sorted(community.glob("*.jsonl")):
        if path.name in SKIP_FILES:
            continue
        atoms.extend(_read_jsonl(path))
    return [atom for atom in atoms if atom.source.source_type != "seed"]


def _grade_bucket(grade: str) -> str:
    if grade.startswith("A") or grade.startswith("B"):
        return "A"
    if grade.startswith("C"):
        return "C"
    return "D"


def _author_hash(atom: KnowledgeAtomV2) -> str:
    if atom.quality.confirmations:
        return atom.quality.confirmations[0].contributor_hash
    return atom.id


def _atom_dates(atom: KnowledgeAtomV2) -> list[str]:
    dates = [atom.source.observed_at]
    extras = atom.quality.confirmations[1:] if atom.quality.confirmations else ()
    dates.extend(item.confirmed_at for item in extras if item.confirmed_at)
    return [item for item in dates if item]


def render_markdown(atoms: list[KnowledgeAtomV2]) -> str:
    named: dict[str, dict[str, object]] = {}
    anon_hashes: set[str] = set()
    anon_atoms = 0
    for atom in atoms:
        name = atom.source.contributor_display_name.strip()
        extras = atom.quality.confirmations[1:] if atom.quality.confirmations else ()
        bucket = _grade_bucket(atom.quality.evidence_grade)
        latest_candidates = _atom_dates(atom)
        if not name:
            anon_hashes.add(_author_hash(atom))
            anon_atoms += 1
            continue
        row = named.setdefault(
            name,
            {"count": 0, "A": 0, "C": 0, "D": 0, "confirms": 0, "latest": ""},
        )
        row["count"] = int(row["count"]) + 1
        row[bucket] = int(row[bucket]) + 1
        row["confirms"] = int(row["confirms"]) + len(extras)
        latest = max(latest_candidates) if latest_candidates else ""
        if latest and (not row["latest"] or latest > str(row["latest"])):
            row["latest"] = latest

    lines = [f"# {TITLE}", "", INTRO, ""]
    if not named and not anon_atoms:
        lines.append(EMPTY)
        lines.append("")
        return "\n".join(lines)

    named_items = sorted(
        named.items(),
        key=lambda item: (-int(item[1]["count"]), item[0]),
    )
    for name, row in named_items:
        lines.append(
            f"{name} · {row['count']} 条（A {row['A']} / C {row['C']} / D {row['D']}）"
            f"· 印证 {row['confirms']} 次 · 最近 {row['latest']}"
        )
    if anon_atoms:
        lines.append(f"{ANON_LABEL} · {len(anon_hashes)} 位 · {anon_atoms} 条")
    lines.append("")
    return "\n".join(lines)


def render_contributors(knowledge_root: Path | None = None) -> Path:
    root = knowledge_root or (ROOT / "knowledge")
    target = root / "05-community/contributors.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    text = render_markdown(_community_atoms(root))
    if not target.is_file() or target.read_text(encoding="utf-8") != text:
        target.write_text(text, encoding="utf-8")
    return target


def main() -> int:
    path = render_contributors(ROOT / "knowledge")
    print(f"已写入 {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
