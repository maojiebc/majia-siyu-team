#!/usr/bin/env python3
"""把社区原子聚合成公开贡献者墙。不输出公司名或哈希。"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from siyu_team.contribution.intake import ANON_LABEL  # noqa: E402
from siyu_team.knowledge.models import KnowledgeAtomV2, KnowledgeValidationError  # noqa: E402

SKIP_FILES = frozenset({"seeds.retail.jsonl", "revoked.jsonl", "rejected.jsonl"})
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


def _grade_letter(grade: str) -> str:
    if grade.startswith("A"):
        return "A"
    if grade.startswith("B"):
        return "B"
    if grade.startswith("C"):
        return "C"
    return "D"


def _author_hash(atom: KnowledgeAtomV2) -> str:
    if atom.quality.confirmations:
        return atom.quality.confirmations[0].contributor_hash
    return atom.id


def _empty_row() -> dict[str, object]:
    return {"approved": 0, "pending": 0, "A": 0, "B": 0, "C": 0, "D": 0, "confirms": 0}


def render_markdown(atoms: list[KnowledgeAtomV2]) -> str:
    named: dict[str, dict[str, object]] = {}
    anon_hashes: set[str] = set()
    anon_approved = 0
    anon_pending = 0
    for atom in atoms:
        extras = atom.quality.confirmations[1:] if atom.quality.confirmations else ()
        approved = atom.quality.review_status == "approved"
        name = atom.source.contributor_display_name.strip()
        if not name:
            anon_hashes.add(_author_hash(atom))
            if approved:
                anon_approved += 1
            else:
                anon_pending += 1
            continue
        row = named.setdefault(name, _empty_row())
        if approved:
            row["approved"] = int(row["approved"]) + 1
            letter = _grade_letter(atom.quality.evidence_grade)
            row[letter] = int(row[letter]) + 1
        else:
            row["pending"] = int(row["pending"]) + 1
        row["confirms"] = int(row["confirms"]) + len(extras)

    lines = [f"# {TITLE}", "", INTRO, ""]
    if not named and not anon_hashes:
        lines.append(EMPTY)
        lines.append("")
        return "\n".join(lines)

    named_items = sorted(
        named.items(),
        key=lambda item: (-int(item[1]["approved"]), -int(item[1]["pending"]), item[0]),
    )
    for name, row in named_items:
        lines.append(
            f"{name} · 通过 {row['approved']}（A {row['A']} / B {row['B']} / "
            f"C {row['C']} / D {row['D']}）· 待审 {row['pending']} · 印证 {row['confirms']}"
        )
    if anon_hashes:
        lines.append(
            f"{ANON_LABEL} · {len(anon_hashes)} 位 · 通过 {anon_approved} · 待审 {anon_pending}"
        )
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
