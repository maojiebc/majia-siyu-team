"""Deterministic, auditable knowledge selection for Runtime and Pilot.

The loader owns corpus safety (approval, privacy, lifecycle and manifest gates).
This module starts from that safe corpus and selects only atoms that apply to the
current task, route target and declared industry.  Selection never depends on
JSONL file order.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable, Mapping

from ..routing import RouteDecision, normalize_skill_slug
from ..task import Goal, Task, TaskKind
from .corpus import Corpus, CorpusLoader
from .models import KnowledgeAtomV2


DEFAULT_SELECTION_LIMIT = 12
L0_TOPIC = "growth_l0"
L1_CATERING_TOPIC = "growth_l1_catering"
L1_RETAIL_TOPIC = "growth_l1_retail"

# These routes either obtain evidence elsewhere or do not have enough task
# information to select public growth knowledge safely.
NO_PUBLIC_KNOWLEDGE_KINDS = frozenset(
    {
        TaskKind.MARKET_RESEARCH,
        TaskKind.MEMBERSHIP_DATA,
        TaskKind.UPDATE,
        TaskKind.UNKNOWN,
    }
)

_GOAL_THEMES: Mapping[Goal, tuple[str, ...]] = {
    Goal.ACQUISITION: ("add_wechat",),
    Goal.CONVERSION: ("activity_increment",),
    Goal.ENGAGEMENT: ("activity_increment",),
    Goal.RETENTION: ("repurchase_recall",),
}

_KIND_THEMES: Mapping[TaskKind, tuple[str, ...]] = {
    TaskKind.MOMENTS_COPY: ("activity_increment",),
    TaskKind.GROUP_CAMPAIGN: ("activity_increment", "repurchase_recall"),
    TaskKind.CONVERSATION_SCRIPT: ("add_wechat",),
}

_THEME_ALIASES: Mapping[str, tuple[str, ...]] = {
    "add_wechat": (
        "add_wechat",
        "加微",
        "加好友",
        "添加好友",
        "扫码",
        "好友通过",
        "拉新",
        "获客",
        "引流",
        "新增",
    ),
    "activity_increment": (
        "activity_increment",
        "活动增量",
        "活动",
        "转化",
        "成交",
        "gmv",
        "打开率",
        "点击率",
        "核销",
        "群发",
        "推送",
        "活跃",
    ),
    "repurchase_recall": (
        "repurchase_recall",
        "复购",
        "留存",
        "召回",
        "流失",
        "休眠",
        "沉默",
        "再来",
    ),
}

_CONFIDENCE_RANK = {"high": 3, "medium": 2, "low": 1}
_EVIDENCE_RANK = {
    "A": 7,
    "A1": 7,
    "A2": 6,
    "B": 5,
    "B1": 5,
    "B2": 4,
    "C": 3,
    "C1": 3,
    "C2": 2,
    "D": 1,
}


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return tuple(result)


def _normalized_text(value: object) -> str:
    return re.sub(r"\s+", "", str(value).casefold())


def _flatten_text(value: object) -> tuple[str, ...]:
    """Extract stable textual context without depending on mapping order."""
    if isinstance(value, Mapping):
        parts: list[str] = []
        for key in sorted(value, key=lambda item: str(item)):
            parts.extend(_flatten_text(key))
            parts.extend(_flatten_text(value[key]))
        return tuple(parts)
    if isinstance(value, (list, tuple, set, frozenset)):
        parts = []
        for item in value:
            parts.extend(_flatten_text(item))
        return tuple(parts)
    if value is None:
        return ()
    text = str(value).strip()
    return (text,) if text else ()


def _task_text(task: Task) -> str:
    parts = [task.source_text, task.audience, *task.constraints]
    parts.extend(_flatten_text(task.context))
    return " ".join(part for part in parts if part)


def _requested_themes(task: Task, text: str) -> tuple[str, ...]:
    wanted: list[str] = list(_GOAL_THEMES.get(task.goal, ()))
    wanted.extend(_KIND_THEMES.get(task.kind, ()))
    normalized = _normalized_text(text)
    for theme, aliases in _THEME_ALIASES.items():
        if any(_normalized_text(alias) in normalized for alias in aliases):
            wanted.append(theme)
    return _unique(wanted)


def _layer_of(atom: KnowledgeAtomV2) -> str:
    topics = {topic.casefold() for topic in atom.topics}
    if L1_RETAIL_TOPIC in topics:
        return "l1_retail"
    if L1_CATERING_TOPIC in topics:
        return "l1_catering"
    if L0_TOPIC in topics:
        return "l0"
    return "general"


def _runtime_safe(atom: KnowledgeAtomV2, *, public_runtime: bool) -> bool:
    """Defence in depth for in-memory corpora used by Runtime and Pilot.

    Production distribution additionally requires ``exportable``.  Pilot may
    opt into non-exportable, already approved public fixtures, but can never
    relax visibility, PII or client-secret boundaries.
    """
    return (
        atom.quality.review_status == "approved"
        and atom.scope.visibility == "public"
        and (atom.privacy.exportable or not public_runtime)
        and not atom.privacy.contains_pii
        and not atom.privacy.contains_client_secret
    )


def _industry_reason(atom: KnowledgeAtomV2, industry: str) -> str | None:
    """Return an audit reason when the atom is allowed, otherwise ``None``."""
    declared = industry.strip().casefold()
    atom_industry = atom.scope.industry.strip().casefold()
    layer = _layer_of(atom)

    if layer == "l1_retail":
        if declared != "retail":
            return None
        return "industry:retail:l1_retail"

    # Shared L1 currently published is the catering/retail layer.
    if layer == "l1_catering":
        if declared not in {"catering", "retail"}:
            return None
        return f"industry:{declared}:shared_l1"

    # edu and every undeclared/generic industry stay on L0 until a real L1 is
    # published.  Explicitly scoped atoms must not leak across industries.
    if atom_industry:
        if not declared or atom_industry != declared:
            return None
        return f"industry:{declared}"
    if layer == "l0":
        return "industry:generic:l0"
    return "industry:generic"


def _skill_match(
    atom: KnowledgeAtomV2,
    route_skill: str,
) -> tuple[int, tuple[str, ...]] | None:
    bound = tuple(sorted({normalize_skill_slug(value).casefold() for value in atom.skills}))
    if route_skill in bound:
        return 100, (f"skill:{route_skill}",)

    # siyu-onboard is a composition entry.  It may consume growth atoms bound
    # to its downstream capabilities, but unrelated public atoms do not get a
    # blanket pass merely because the route is broad.
    if route_skill == "siyu-onboard" and (
        L0_TOPIC in {topic.casefold() for topic in atom.topics}
        or L1_CATERING_TOPIC in {topic.casefold() for topic in atom.topics}
        or L1_RETAIL_TOPIC in {topic.casefold() for topic in atom.topics}
    ) and bound:
        return 35, (
            "skill:siyu-onboard",
            "composite_binding:" + ",".join(bound),
        )
    return None


def _applicability_haystack(atom: KnowledgeAtomV2) -> str:
    applicability = atom.applicability
    metrics = " ".join(
        f"{metric.name} {metric.definition} {metric.time_window}"
        for metric in applicability.metrics
    )
    return " ".join(
        (
            *applicability.preconditions,
            *applicability.recommended_action,
            metrics,
            *applicability.failure_modes,
            *applicability.counterexamples,
        )
    ).casefold()


def _relevance(
    atom: KnowledgeAtomV2,
    task: Task,
    task_text: str,
    themes: tuple[str, ...],
) -> tuple[int, tuple[str, ...]]:
    score = 0
    reasons: list[str] = []
    topics = {topic.casefold() for topic in atom.topics}
    scenarios = {scenario.casefold() for scenario in atom.scope.scenarios}
    applicability = _applicability_haystack(atom)
    normalized_task = _normalized_text(task_text)

    for theme in themes:
        if theme in topics:
            score += 30
            reasons.append(f"topic:{theme}")
        if theme in scenarios:
            score += 20
            reasons.append(f"scenario:{theme}")

    goal_themes = set(_GOAL_THEMES.get(task.goal, ()))
    if goal_themes.intersection(topics | scenarios):
        score += 12
        reasons.append(f"goal:{task.goal.value}")

    for theme in themes:
        if theme not in topics and theme not in scenarios:
            continue
        matching_aliases = sorted(
            {
                alias.casefold()
                for alias in _THEME_ALIASES.get(theme, ())
                if _normalized_text(alias) in normalized_task
            },
            key=lambda value: (-len(value), value),
        )
        if matching_aliases:
            # One textual reason per theme is enough for an audit trail; the
            # topic/scenario reasons above explain the actual atom match.
            alias = matching_aliases[0]
            score += 10
            reasons.append(f"text:{alias}")
            if alias in applicability:
                score += 4
                reasons.append(f"applicability:{alias}")

    if task.stage and task.stage.casefold() in {
        value.casefold() for value in atom.scope.lifecycle_stages
    }:
        score += 5
        reasons.append(f"stage:{task.stage.casefold()}")

    return score, _unique(reasons)


def _community_grade_tag(atom: KnowledgeAtomV2) -> str:
    grade = atom.quality.evidence_grade
    if grade.startswith("A"):
        letter = "A"
    elif grade.startswith("B"):
        letter = "B"
    elif grade.startswith("C"):
        letter = "C"
    else:
        letter = "D"
    return f"社区·评审通过·{letter}级"


def _applicability_summary(atom: KnowledgeAtomV2) -> dict[str, Any]:
    """Return the complete bounded context needed to use an atom safely."""
    return atom.applicability.to_dict()


@dataclass(frozen=True)
class SelectedKnowledge:
    atom: KnowledgeAtomV2
    score: int
    why_selected: tuple[str, ...]
    layer: str

    def to_dict(self) -> dict[str, Any]:
        row = self.atom.to_dict()
        row.update(
            {
                "source_id": self.atom.source.source_id,
                "locator": self.atom.source.locator,
                "why_selected": list(self.why_selected),
                "applicability_summary": _applicability_summary(self.atom),
                "layer": self.layer,
            }
        )
        return row


@dataclass(frozen=True)
class KnowledgeSelection:
    corpus_version: str
    corpus_hash: str
    atoms: tuple[SelectedKnowledge, ...]
    warnings: tuple[str, ...] = ()

    @property
    def selection_count(self) -> int:
        return len(self.atoms)

    @property
    def raw_atoms(self) -> tuple[KnowledgeAtomV2, ...]:
        return tuple(item.atom for item in self.atoms)

    def to_dict(self) -> dict[str, Any]:
        """Return the ``ExecutionPlan.knowledge`` payload."""
        return {
            "corpus_version": self.corpus_version,
            "corpus_hash": self.corpus_hash,
            "selection_count": self.selection_count,
            "atoms": [item.to_dict() for item in self.atoms],
        }

    def context_rows(self) -> tuple[dict[str, Any], ...]:
        """Return rows compatible with the legacy ``growth_atoms`` context."""
        return tuple(item.to_dict() for item in self.atoms)


class KnowledgeAssembler:
    """Select a small relevant slice from one strictly loaded public corpus."""

    def __init__(
        self,
        corpus: Corpus | None = None,
        loader: CorpusLoader | None = None,
        limit: int = DEFAULT_SELECTION_LIMIT,
        *,
        public_runtime: bool = True,
        community_atoms: tuple[KnowledgeAtomV2, ...] | None = None,
    ) -> None:
        if limit < 0:
            raise ValueError("limit 不能为负数")
        self._corpus = corpus
        self._loader = loader or CorpusLoader()
        self.limit = limit
        self.public_runtime = public_runtime
        self._community_atoms = community_atoms
        self._auto_community = community_atoms is None and corpus is None

    @property
    def corpus(self) -> Corpus:
        if self._corpus is None:
            self._corpus = self._loader.load()
        return self._corpus

    @property
    def community_atoms(self) -> tuple[KnowledgeAtomV2, ...]:
        if self._community_atoms is None:
            if not self._auto_community:
                return ()
            self._community_atoms = self._loader.load_community()
        return self._community_atoms

    def assemble(
        self,
        task: Task,
        decision: RouteDecision,
        *,
        limit: int | None = None,
    ) -> KnowledgeSelection:
        selected_limit = self.limit if limit is None else limit
        if selected_limit < 0:
            raise ValueError("limit 不能为负数")

        corpus = self.corpus
        if task.kind in NO_PUBLIC_KNOWLEDGE_KINDS or selected_limit == 0:
            return KnowledgeSelection(
                corpus_version=corpus.corpus_version,
                corpus_hash=corpus.corpus_hash,
                atoms=(),
                warnings=corpus.warnings,
            )

        route_skill = normalize_skill_slug(decision.skill).casefold()
        text = _task_text(task)
        themes = _requested_themes(task, text)
        strict = self._match_atoms(corpus.atoms, task, route_skill, text, themes)
        chosen = list(strict[:selected_limit])
        seen = {item.atom.id for item in chosen}
        remaining = selected_limit - len(chosen)
        extra_warnings = ()
        if remaining > 0:
            community = self._match_atoms(
                self.community_atoms, task, route_skill, text, themes
            )
            tagged: list[SelectedKnowledge] = []
            for item in community:
                if item.atom.id in seen:
                    continue
                tagged.append(
                    SelectedKnowledge(
                        atom=item.atom,
                        score=item.score,
                        why_selected=_unique(
                            (*item.why_selected, _community_grade_tag(item.atom))
                        ),
                        layer=item.layer,
                    )
                )
                seen.add(item.atom.id)
                if len(tagged) >= remaining:
                    break
            chosen.extend(tagged)
            extra_warnings = getattr(self._loader, "community_warnings", ())
        return KnowledgeSelection(
            corpus_version=corpus.corpus_version,
            corpus_hash=corpus.corpus_hash,
            atoms=tuple(chosen),
            warnings=corpus.warnings + tuple(extra_warnings or ()),
        )

    def _match_atoms(
        self,
        atoms: Iterable[KnowledgeAtomV2],
        task: Task,
        route_skill: str,
        text: str,
        themes: tuple[str, ...],
    ) -> list[SelectedKnowledge]:
        candidates: list[SelectedKnowledge] = []
        for atom in atoms:
            if not _runtime_safe(atom, public_runtime=self.public_runtime):
                continue
            industry_reason = _industry_reason(atom, task.industry)
            if industry_reason is None:
                continue
            skill_match = _skill_match(atom, route_skill)
            if skill_match is None:
                continue
            skill_score, skill_reasons = skill_match
            atom_themes = {
                value.casefold()
                for value in (*atom.topics, *atom.scope.scenarios)
            }
            if themes and not set(themes).intersection(atom_themes):
                continue
            relevance_score, relevance_reasons = _relevance(
                atom,
                task,
                text,
                themes,
            )
            why = _unique((*skill_reasons, industry_reason, *relevance_reasons))
            candidates.append(
                SelectedKnowledge(
                    atom=atom,
                    score=skill_score + relevance_score,
                    why_selected=why,
                    layer=_layer_of(atom),
                )
            )
        candidates.sort(
            key=lambda item: (
                -item.score,
                -_CONFIDENCE_RANK.get(item.atom.quality.confidence, 0),
                -_EVIDENCE_RANK.get(item.atom.quality.evidence_grade, 0),
                item.atom.id,
            )
        )
        return candidates


def assemble_knowledge(
    task: Task,
    decision: RouteDecision,
    *,
    corpus: Corpus | None = None,
    loader: CorpusLoader | None = None,
    limit: int = DEFAULT_SELECTION_LIMIT,
    public_runtime: bool = True,
) -> KnowledgeSelection:
    """Convenience wrapper for callers that do not keep an assembler cache."""
    return KnowledgeAssembler(
        corpus=corpus,
        loader=loader,
        limit=limit,
        public_runtime=public_runtime,
    ).assemble(
        task,
        decision,
    )
