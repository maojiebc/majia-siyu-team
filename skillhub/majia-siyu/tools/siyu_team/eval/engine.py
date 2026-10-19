"""Deterministic composition for scores supplied by an independent Judge.

Compliance scanning and Judge scoring are deliberately separate.  The legacy
``static_penalty`` argument remains for one compatibility release, but the CLI
does not feed scanner penalties into the quality score.
"""
from __future__ import annotations

from typing import Any

from .rubrics import DIMENSION_WEIGHTS


# A badge is only a quality grade.  It never approves a case-library entry or a
# knowledge atom; both remain separate human-governed workflows.
BADGES = [
    (90, "Platinum 独立评审优秀"),
    (80, "Gold 独立评审通过"),
    (70, "Silver 需内部复核"),
    (60, "Bronze 需返工"),
    (0, "未达交付线"),
]


def badge(score: float) -> str:
    """Return the quality grade for a completed independent Judge score."""

    for threshold, label in BADGES:
        if score >= threshold:
            return label
    return "未达交付线"


def composite(
    dim_scores: dict[str, float], static_penalty: float = 1.0
) -> dict[str, Any]:
    """Compose complete rubric scores into a 0–100 quality score.

    ``dim_scores`` maps every rubric dimension to a value in ``[0.0, 1.0]``.
    Missing dimensions produce an incomplete result with no score and no
    badge.  Even a complete dimension mapping only produces a numeric
    intermediate here; ``build_judge_report`` assigns the badge after it has
    validated independent-review metadata.

    ``static_penalty`` is retained only for callers of the v1.4.1 Python API.
    New integrations must keep compliance/roughness separate and leave it at
    ``1.0``.  Values are clamped so the compatibility adjustment cannot raise
    a score.
    """

    missing = [dim for dim in DIMENSION_WEIGHTS if dim not in dim_scores]
    if missing:
        return {
            "status": "incomplete",
            "score": None,
            "badge": None,
            "missing_dims": missing,
            "static_penalty": None,
        }

    compatibility_penalty = min(1.0, max(0.0, static_penalty))
    weighted = sum(
        weight * dim_scores[dim]
        for dim, (weight, _description) in DIMENSION_WEIGHTS.items()
    )
    score = round(weighted * 100 * compatibility_penalty, 1)
    return {
        "status": "scored",
        "score": score,
        "badge": None,
        "missing_dims": [],
        "static_penalty": compatibility_penalty,
    }
