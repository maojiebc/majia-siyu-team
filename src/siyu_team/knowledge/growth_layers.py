"""用户增长 L0/L1 分层：路径、路由选择与原子 ID 约定。

规则（产品约定）：
- 未声明业态 → 只加载 L0
- industry=catering|retail → L0 + L1 餐饮零售包（retail 暂共用门店壳）
- 其他已声明业态（如 edu）→ 只加载 L0，直到有对应 L1
- 市场调研任务不加载增长层（避免内部方法冒充外部事实）

原子 ID：
- source_id = generate_source_id(稳定文档路径)
- locator = L0-01 / L1-C01 / L1-01 等章节锚点
- atom_id = generate_atom_id(source_id, locator, 0)
- 逻辑 id 写在 source.locator，便于人对齐文档
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .models import KnowledgeAtomV2, generate_atom_id, generate_source_id
from .paths import KnowledgePathResolver

L0_DOC = "knowledge/00-methodology/L0-通用用户增长原则.md"
L1_CATERING_DOC = "knowledge/02-industry/catering/L1-餐饮零售用增Know-how.md"
GROWTH_INDEX_DOC = "knowledge/00-methodology/用户增长分层索引.md"
GROWTH_ATOMS_DRAFT = "04-atoms/growth-layers.draft.jsonl"

L0_TOPIC = "growth_l0"
L1_CATERING_TOPIC = "growth_l1_catering"
LAYER_TOPICS = frozenset({L0_TOPIC, L1_CATERING_TOPIC})

L1_INDUSTRIES = frozenset({"catering", "retail"})


def growth_source_id(doc_path: str) -> str:
    return generate_source_id(doc_path)


def growth_atom_id(doc_path: str, locator: str, local_index: int = 0) -> str:
    return generate_atom_id(growth_source_id(doc_path), locator, local_index)


def select_growth_doc_refs(
    industry: str = "",
    *,
    include_index: bool = False,
) -> tuple[str, ...]:
    """按业态返回应注入的增长文档路径（相对仓库根）。"""
    refs: list[str] = [L0_DOC]
    normalized = (industry or "").strip().lower()
    if normalized in L1_INDUSTRIES:
        refs.append(L1_CATERING_DOC)
    if include_index:
        refs.append(GROWTH_INDEX_DOC)
    return tuple(refs)


def select_growth_topics(industry: str = "") -> tuple[str, ...]:
    """按业态返回应加载的增长原子主题标签。"""
    topics = [L0_TOPIC]
    if (industry or "").strip().lower() in L1_INDUSTRIES:
        topics.append(L1_CATERING_TOPIC)
    return tuple(topics)


def filter_atoms_by_growth_layer(
    atoms: Iterable[KnowledgeAtomV2],
    industry: str = "",
) -> tuple[KnowledgeAtomV2, ...]:
    """只保留当前业态允许的增长层原子。"""
    allowed = set(select_growth_topics(industry))
    out: list[KnowledgeAtomV2] = []
    for atom in atoms:
        layer_tags = set(atom.topics).intersection(LAYER_TOPICS)
        if layer_tags & allowed:
            out.append(atom)
    return tuple(out)


def _find_draft_file(resolver: KnowledgePathResolver) -> Path | None:
    for root in resolver.candidates():
        candidate = root / GROWTH_ATOMS_DRAFT
        if candidate.is_file():
            return candidate
    return None


def load_growth_draft_atoms(
    industry: str = "",
    *,
    resolver: KnowledgePathResolver | None = None,
) -> tuple[KnowledgeAtomV2, ...]:
    """读取 draft 增长原子并按业态过滤。文件不存在则返回空。"""
    resolver = resolver or KnowledgePathResolver()
    path = _find_draft_file(resolver)
    if path is None:
        return ()
    atoms: list[KnowledgeAtomV2] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        atoms.append(KnowledgeAtomV2.from_json(line))
    return filter_atoms_by_growth_layer(atoms, industry)


def describe_growth_load(industry: str = "") -> str:
    """给人看的加载说明（说人话）。"""
    normalized = (industry or "").strip().lower()
    if not normalized:
        return "未声明业态：只加载通用用户增长原则（L0），不加载餐饮门店专包（L1）。"
    if normalized in L1_INDUSTRIES:
        return f"业态={normalized}：加载通用原则（L0）+ 餐饮零售门店专包（L1）。"
    return f"业态={normalized}：尚无专属 L1，只加载通用用户增长原则（L0）。"
