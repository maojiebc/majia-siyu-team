"""Independent Judge prompt, submission parser, and report construction.

This module never calls a model.  A host launches a clean Judge context, saves
the resulting rubric scores, and feeds them back here.  Only that completed
flow creates a :class:`JudgeReport` and therefore a quality badge.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Mapping

from .engine import badge, composite
from .models import JudgeReport
from .rubrics import ANCHORS, DIMENSION_WEIGHTS

JUDGE_PROMPT = """你是私域方案的独立严格评审。你只看本段待评方案，不接触生成过程、客户原始材料或其他评审结果。
只评一个维度：{dim}。
锚定标准（0.0–1.0）：
{anchor}

待评方案：
---
{plan}
---
只输出该维度的分数(0.0–1.0)和不超过两句理由，JSON：{{"score": x, "why": "..."}}
注意：质量分只用于交付复核，不能自动批准案例入库或知识原子。"""


def build_judge_prompt(dim: str, plan: str) -> str:
    """Build the anchored prompt for one independent rubric dimension."""

    return JUDGE_PROMPT.format(
        dim=dim,
        anchor=ANCHORS.get(dim, "（锚定待补，见 docs/blueprint.md §3d）"),
        plan=plan,
    )


def build_judge_batch(plan: str, dims: list[str] | None = None) -> dict[str, str]:
    """Build one isolated prompt per requested rubric dimension."""

    dims = dims or list(DIMENSION_WEIGHTS)
    unknown = [dim for dim in dims if dim not in DIMENSION_WEIGHTS]
    if unknown:
        raise ValueError(f"未知评分维度：{', '.join(unknown)}")
    return {dim: build_judge_prompt(dim, plan) for dim in dims}


def _decode_submission(raw: Any) -> Mapping[str, Any]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"judge 评分不是合法 JSON：{exc.msg}") from exc
    if not isinstance(raw, Mapping):
        raise ValueError("judge 评分必须是 {维度: 分数} 对象")
    return raw


def _score_payload(submission: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return scores from the v1.4.2 envelope or the legacy bare mapping."""

    if "scores" not in submission:
        return submission
    scores = submission["scores"]
    if not isinstance(scores, Mapping):
        raise ValueError("JudgeReport.scores 必须是 {维度: 分数} 对象")
    return scores


def parse_judge_scores(raw: Any) -> dict[str, float]:
    """Parse legacy scores or a v1.4.2 Judge submission envelope.

    A score value may be numeric or ``{"score": x, "why": ...}``.  Unknown
    dimensions and out-of-range values fail closed.  Partial mappings are
    accepted for API compatibility, but :func:`build_judge_report` marks them
    ``not_evaluated`` and never assigns a score or badge.
    """

    submission = _decode_submission(raw)
    score_payload = _score_payload(submission)
    scores: dict[str, float] = {}
    for dim, value in score_payload.items():
        if dim not in DIMENSION_WEIGHTS:
            raise ValueError(f"未知评分维度：{dim}")
        raw_score = value.get("score") if isinstance(value, Mapping) else value
        # bool is an int subclass and must not silently become 1.0/0.0.
        if isinstance(raw_score, bool) or not isinstance(
            raw_score, (int, float, str)
        ):
            raise ValueError(f"{dim} 分数不是数字：{raw_score!r}")
        try:
            score = float(raw_score)
        except ValueError as exc:
            raise ValueError(f"{dim} 分数不是数字：{raw_score!r}") from exc
        if not 0.0 <= score <= 1.0:
            raise ValueError(f"{dim} 分数越界（需 0.0–1.0）：{score}")
        scores[dim] = score
    return scores


def _judge_reasons(submission: Mapping[str, Any]) -> dict[str, str]:
    reasons: dict[str, str] = {}
    for dim, value in _score_payload(submission).items():
        if isinstance(value, Mapping) and value.get("why") is not None:
            reasons[dim] = str(value["why"])
    return reasons


def _judge_config(submission: Mapping[str, Any]) -> dict[str, Any]:
    raw_config = submission.get("config", {})
    if raw_config is None:
        raw_config = {}
    if not isinstance(raw_config, Mapping):
        raise ValueError("JudgeReport.config 必须是对象")
    config = dict(raw_config)
    metadata_complete = all(
        bool(submission.get(key))
        for key in ("model", "reviewed_at", "review_method")
    )
    config.setdefault("metadata_complete", metadata_complete)
    config.setdefault(
        "report_generated_at", datetime.now(timezone.utc).isoformat()
    )
    return config


def build_judge_report(
    raw: Any,
    *,
    source: str = "",
    threshold: int = 80,
    model: str | None = None,
    config: Mapping[str, Any] | None = None,
    reviewed_at: str | None = None,
    review_method: str | None = None,
) -> JudgeReport:
    """Build the machine-readable report for independently supplied scores.

    The v1.4.2 envelope accepts ``scores``, ``model``, ``config``,
    ``reviewed_at`` and ``review_method``.  Bare score mappings remain
    parseable for one compatibility release, but produce a ``not_evaluated``
    report without a score or badge because their provenance is incomplete.
    """

    submission = _decode_submission(raw)
    scores = parse_judge_scores(submission)
    reasons = _judge_reasons(submission)
    result = composite(scores)

    supplied_config = config if config is not None else submission.get("config")
    merged_config = _judge_config(submission)
    if config is not None:
        merged_config.update(dict(config))
    effective_model = str(model or submission.get("model") or "").strip()
    effective_reviewed_at = str(
        reviewed_at or submission.get("reviewed_at") or ""
    ).strip()
    effective_review_method = str(
        review_method or submission.get("review_method") or ""
    ).strip()

    incomplete_fields: list[str] = []
    if result["score"] is None:
        incomplete_fields.extend(
            f"scores.{dim}" for dim in result["missing_dims"]
        )
    if not source.strip():
        incomplete_fields.append("source")
    if not effective_model:
        incomplete_fields.append("model")
    if not isinstance(supplied_config, Mapping) or not supplied_config:
        incomplete_fields.append("config")
    if not effective_reviewed_at:
        incomplete_fields.append("reviewed_at")
    else:
        try:
            datetime.fromisoformat(effective_reviewed_at.replace("Z", "+00:00"))
        except ValueError:
            incomplete_fields.append("reviewed_at.iso8601")
    if not effective_review_method:
        incomplete_fields.append("review_method")
    elif "independent" not in effective_review_method.lower():
        incomplete_fields.append("review_method.independence")
    for dim in DIMENSION_WEIGHTS:
        if not reasons.get(dim, "").strip():
            incomplete_fields.append(f"reasons.{dim}")

    merged_config["metadata_complete"] = not incomplete_fields
    if incomplete_fields:
        merged_config["incomplete_fields"] = incomplete_fields
    merged_config["quality_threshold"] = threshold
    merged_config["automatic_case_or_knowledge_approval"] = False

    if incomplete_fields:
        score = None
        report_badge = None
        status = "not_evaluated"
    else:
        score = result["score"]
        assert score is not None  # narrowed by the complete-dimensions check
        report_badge = badge(score)
        status = "passed" if score >= threshold else "failed"

    return JudgeReport(
        status=status,
        source=source,
        model=effective_model,
        config=merged_config,
        reviewed_at=effective_reviewed_at,
        review_method=effective_review_method or "legacy_host_provided",
        scores=scores,
        reasons=reasons,
        score=score,
        badge=report_badge,
    )
