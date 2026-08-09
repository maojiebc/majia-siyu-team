"""Typed contracts shared by compliance scanning and independent judging.

The public CLI still exposes dictionaries for backwards compatibility.  These
models give the scanner and judge a stable, serialisable contract underneath
that compatibility layer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from .rubrics import DIMENSION_WEIGHTS


class ScanMode(str, Enum):
    """Context in which the same compliance rules are interpreted."""

    CUSTOMER_COPY = "customer_copy"
    INTERNAL_REPORT = "internal_report"
    KNOWLEDGE = "knowledge"
    QUOTED_EVIDENCE = "quoted_evidence"


@dataclass(frozen=True)
class ScanHit:
    """One explainable rule hit.

    ``offset`` and ``end`` use Python string offsets.  A document-level rule
    without a concrete token (for example ``NO_METRIC``) uses ``-1`` for both.
    ``flag`` is retained for callers of the v1 static scanner; ``rule`` is the
    stable, more specific rule identifier for new integrations.
    """

    flag: str
    description: str
    offset: int
    end: int
    snippet: str
    rule: str
    mode: ScanMode
    severity: float
    hard: bool
    soft: bool

    def __post_init__(self) -> None:
        if self.hard == self.soft:
            raise ValueError("ScanHit 必须且只能标记为 hard 或 soft")
        if not 0.0 <= self.severity <= 1.0:
            raise ValueError("ScanHit.severity 必须在 0 到 1 之间")

    def to_dict(self) -> dict[str, Any]:
        """Return the compatibility shape plus the v1.4.2 context fields."""

        return {
            "flag": self.flag,
            "desc": self.description,
            "description": self.description,
            "offset": self.offset,
            "end": self.end,
            "snippet": self.snippet,
            "rule": self.rule,
            "mode": self.mode.value,
            "severity": self.severity,
            "hard": self.hard,
            "soft": self.soft,
        }


@dataclass(frozen=True)
class ScanResult:
    """Structured scanner result with a v1-compatible dictionary adapter."""

    mode: ScanMode
    text_length: int
    hits: tuple[ScanHit, ...] = ()
    penalty: float = 1.0

    @property
    def flags(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(hit.flag for hit in self.hits))

    @property
    def details(self) -> tuple[dict[str, Any], ...]:
        return tuple(hit.to_dict() for hit in self.hits)

    @property
    def hard_fail(self) -> bool:
        return any(hit.hard for hit in self.hits)

    def to_dict(self) -> dict[str, Any]:
        return {
            "flags": list(self.flags),
            "details": [dict(detail) for detail in self.details],
            "penalty": self.penalty,
            "hard_fail": self.hard_fail,
            "mode": self.mode.value,
            "text_length": self.text_length,
        }


@dataclass(frozen=True)
class JudgeReport:
    """Machine-readable record of an independent host/Judge assessment.

    A static compliance scan is not a Judge report.  ``score`` and ``badge``
    therefore remain optional until complete independent scores are supplied.
    """

    schema_version: str = "1.0"
    status: str = "not_evaluated"
    source: str = ""
    model: str = ""
    config: Mapping[str, Any] = field(default_factory=dict)
    reviewed_at: str = ""
    review_method: str = "independent_host_judge"
    scores: Mapping[str, float] = field(default_factory=dict)
    reasons: Mapping[str, str] = field(default_factory=dict)
    score: float | None = None
    badge: str | None = None

    def __post_init__(self) -> None:
        complete_statuses = {"complete", "passed", "failed"}
        has_complete_status = self.status in complete_statuses

        if self.score is None:
            if self.badge is not None:
                raise ValueError("没有完整 Judge score 时不得生成 badge")
            if has_complete_status:
                raise ValueError("完成态 JudgeReport 必须包含 score 与 badge")
            return

        if not 0.0 <= self.score <= 100.0:
            raise ValueError("JudgeReport.score 必须在 0 到 100 之间")
        if not has_complete_status or not self.badge:
            raise ValueError("有 score 的 JudgeReport 必须是完成态且包含 badge")

        expected_dimensions = set(DIMENSION_WEIGHTS)
        if set(self.scores) != expected_dimensions:
            missing = sorted(expected_dimensions - set(self.scores))
            extra = sorted(set(self.scores) - expected_dimensions)
            raise ValueError(
                f"完成态 JudgeReport 维度不完整：missing={missing}, extra={extra}"
            )
        if any(not 0.0 <= float(value) <= 1.0 for value in self.scores.values()):
            raise ValueError("JudgeReport.scores 各维分必须在 0 到 1 之间")
        if set(self.reasons) != expected_dimensions or any(
            not str(reason).strip() for reason in self.reasons.values()
        ):
            raise ValueError("完成态 JudgeReport 必须包含每个维度的非空理由")

        required_metadata = {
            "source": self.source,
            "model": self.model,
            "config": self.config,
            "reviewed_at": self.reviewed_at,
            "review_method": self.review_method,
        }
        missing_metadata = [
            key for key, value in required_metadata.items() if not value
        ]
        if missing_metadata:
            raise ValueError(
                "完成态 JudgeReport 缺少独立评审元数据："
                + ", ".join(missing_metadata)
            )
        if "independent" not in self.review_method.lower():
            raise ValueError("完成态 JudgeReport.review_method 必须确认独立评审")
        if self.config.get("metadata_complete") is not True:
            raise ValueError("完成态 JudgeReport.config 必须确认 metadata_complete=true")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "source": self.source,
            "model": self.model,
            "config": dict(self.config),
            "reviewed_at": self.reviewed_at,
            "review_method": self.review_method,
            "scores": dict(self.scores),
            "reasons": dict(self.reasons),
            "score": self.score,
            "badge": self.badge,
        }
