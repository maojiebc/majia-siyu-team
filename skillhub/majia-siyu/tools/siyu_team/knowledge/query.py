"""Public knowledge queries backed by the same strict Corpus as Runtime."""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Iterable, Iterator

from .corpus import Corpus, CorpusLoader, CorpusMetadata
from .models import KnowledgeAtomV2


def _normalize_skill_slug(value: str) -> str:
    """Mirror the route contract's canonical slug without importing Runtime."""
    return value.strip().lstrip("/")


def _values(values: str | Iterable[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    source = (values,) if isinstance(values, str) else values
    result: list[str] = []
    seen: set[str] = set()
    for raw in source:
        # CLI callers commonly pass repeatable comma-separated flags.
        for item in str(raw).split(","):
            cleaned = item.strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                result.append(cleaned)
    return tuple(result)


def _haystack(atom: KnowledgeAtomV2) -> str:
    # Canonical JSON covers statement, topics, source metadata and every
    # applicability field without maintaining a second hand-written schema.
    return json.dumps(
        atom.to_dict(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).casefold()


@dataclass(frozen=True)
class QueryResult:
    metadata: CorpusMetadata
    atoms: tuple[KnowledgeAtomV2, ...]
    warnings: tuple[str, ...] = ()

    @property
    def corpus_version(self) -> str:
        return self.metadata.corpus_version

    @property
    def corpus_hash(self) -> str:
        return self.metadata.corpus_hash

    @property
    def count(self) -> int:
        return len(self.atoms)

    def __iter__(self) -> Iterator[KnowledgeAtomV2]:
        return iter(self.atoms)

    def __len__(self) -> int:
        return len(self.atoms)

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.metadata.to_dict(),
            "count": self.count,
            "atoms": [atom.to_dict() for atom in self.atoms],
            "warnings": list(self.warnings),
        }


class KnowledgeQuery:
    """Filter approved public atoms without bypassing CorpusLoader semantics."""

    def __init__(
        self,
        corpus: Corpus | None = None,
        loader: CorpusLoader | None = None,
    ) -> None:
        self._corpus = corpus
        self._loader = loader or CorpusLoader()

    @property
    def corpus(self) -> Corpus:
        if self._corpus is None:
            self._corpus = self._loader.load()
        return self._corpus

    def search(
        self,
        *,
        skills: str | Iterable[str] | None = None,
        topics: str | Iterable[str] | None = None,
        types: str | Iterable[str] | None = None,
        keywords: str | Iterable[str] | None = None,
        limit: int = 50,
    ) -> QueryResult:
        if limit < 0:
            raise ValueError("limit 不能为负数")

        corpus = self.corpus
        wanted_skills = {
            _normalize_skill_slug(value).casefold() for value in _values(skills)
        }
        wanted_topics = {value.casefold() for value in _values(topics)}
        wanted_types = {value.casefold() for value in _values(types)}
        wanted_keywords = tuple(value.casefold() for value in _values(keywords))

        matches: list[KnowledgeAtomV2] = []
        for atom in corpus.atoms:
            atom_skills = {
                _normalize_skill_slug(value).casefold() for value in atom.skills
            }
            if wanted_skills and not wanted_skills.intersection(atom_skills):
                continue
            atom_topics = {value.casefold() for value in atom.topics}
            if wanted_topics and not wanted_topics.intersection(atom_topics):
                continue
            if wanted_types and atom.type.casefold() not in wanted_types:
                continue
            haystack = _haystack(atom)
            if any(keyword not in haystack for keyword in wanted_keywords):
                continue
            matches.append(atom)

        # Query output, like Runtime selection, must not change when JSONL lines
        # are regrouped or regenerated in a different order.
        matches.sort(key=lambda atom: atom.id)
        return QueryResult(
            metadata=corpus.metadata,
            atoms=tuple(matches[:limit]),
            warnings=corpus.warnings,
        )


def query_atoms(
    *,
    skills: str | Iterable[str] | None = None,
    topics: str | Iterable[str] | None = None,
    types: str | Iterable[str] | None = None,
    keywords: str | Iterable[str] | None = None,
    limit: int = 50,
    corpus: Corpus | None = None,
    loader: CorpusLoader | None = None,
) -> tuple[KnowledgeAtomV2, ...]:
    """Compatibility-friendly convenience function returning only atoms."""
    return KnowledgeQuery(corpus=corpus, loader=loader).search(
        skills=skills,
        topics=topics,
        types=types,
        keywords=keywords,
        limit=limit,
    ).atoms


def query_knowledge(
    *,
    skills: str | Iterable[str] | None = None,
    topics: str | Iterable[str] | None = None,
    types: str | Iterable[str] | None = None,
    keywords: str | Iterable[str] | None = None,
    limit: int = 50,
    corpus: Corpus | None = None,
    loader: CorpusLoader | None = None,
) -> QueryResult:
    """Convenience function retaining corpus metadata and warnings."""
    return KnowledgeQuery(corpus=corpus, loader=loader).search(
        skills=skills,
        topics=topics,
        types=types,
        keywords=keywords,
        limit=limit,
    )
