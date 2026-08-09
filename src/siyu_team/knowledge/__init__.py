"""Knowledge Runtime 的稳定数据契约与路径解析。"""

from .models import (
    Applicability,
    KnowledgeAtomV2,
    KnowledgeValidationError,
    Lifecycle,
    Metric,
    Privacy,
    Quality,
    Scope,
    SourceRef,
    generate_atom_id,
    generate_source_id,
    migrate_v1_atom,
)
from .paths import KnowledgePathResolver
from .corpus import Corpus, CorpusLoader, CorpusMetadata
from .assembler import (
    KnowledgeAssembler,
    KnowledgeSelection,
    SelectedKnowledge,
    assemble_knowledge,
)
from .query import KnowledgeQuery, QueryResult, query_atoms, query_knowledge

__all__ = [
    "Applicability",
    "Corpus",
    "CorpusLoader",
    "CorpusMetadata",
    "KnowledgeAssembler",
    "KnowledgeAtomV2",
    "KnowledgePathResolver",
    "KnowledgeQuery",
    "KnowledgeSelection",
    "KnowledgeValidationError",
    "Lifecycle",
    "Metric",
    "Privacy",
    "Quality",
    "QueryResult",
    "SelectedKnowledge",
    "Scope",
    "SourceRef",
    "assemble_knowledge",
    "generate_atom_id",
    "generate_source_id",
    "migrate_v1_atom",
    "query_atoms",
    "query_knowledge",
]

from .growth_layers import (
    L0_DOC,
    L1_CATERING_DOC,
    describe_growth_load,
    filter_atoms_by_growth_layer,
    growth_atom_id,
    load_growth_draft_atoms,
    load_growth_atoms,
    select_growth_doc_refs,
    select_growth_topics,
    format_growth_atoms_for_context,
)

__all__ += [
    "L0_DOC",
    "L1_CATERING_DOC",
    "describe_growth_load",
    "filter_atoms_by_growth_layer",
    "growth_atom_id",
    "load_growth_draft_atoms",
    "load_growth_atoms",
    "select_growth_doc_refs",
    "select_growth_topics",
    "format_growth_atoms_for_context",
]
