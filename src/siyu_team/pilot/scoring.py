"""盲测评分聚合与 H1 判定。"""
from __future__ import annotations

from collections import Counter, defaultdict
import csv
import json
import math
from pathlib import Path
import re
from statistics import mean
from typing import Any, Mapping, Sequence

from .models import BlindRating, PilotValidationError, SCORE_DIMENSIONS, THEMES
from .packets import write_private_text


KEY_DIMENSIONS = (
    "industry_realism",
    "organization_constraints",
    "boundary_awareness",
    "actionability",
)
_GENERIC_REASONS = {
    "更好",
    "更专业",
    "更全面",
    "更实用",
    "比较好",
    "左边更好",
    "右边更好",
}


def _load_blind_map(run: Path) -> tuple[Mapping[str, Mapping[str, str]], Mapping[str, str]]:
    path = run / "blind" / "blind-map.json"
    if not path.is_file():
        raise PilotValidationError(f"找不到盲测真值映射：{path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PilotValidationError(f"blind-map JSON 非法：{exc.msg}") from exc
    if not isinstance(data, Mapping):
        raise PilotValidationError("blind-map 必须是对象")
    pairs = data.get("pairs")
    themes = data.get("task_themes")
    if not isinstance(pairs, Mapping) or not isinstance(themes, Mapping):
        raise PilotValidationError("blind-map 缺少 pairs 或 task_themes")
    clean_pairs: dict[str, Mapping[str, str]] = {}
    clean_themes: dict[str, str] = {}
    for task_id, raw_pair in pairs.items():
        if not isinstance(raw_pair, Mapping):
            raise PilotValidationError(f"blind-map pair 非法：{task_id}")
        left, right = raw_pair.get("left"), raw_pair.get("right")
        if {left, right} != {"baseline", "knowledge"}:
            raise PilotValidationError(f"blind-map 左右真值非法：{task_id}")
        theme = themes.get(task_id)
        if theme not in THEMES:
            raise PilotValidationError(f"blind-map 主题非法：{task_id}")
        clean_pairs[str(task_id)] = {"left": str(left), "right": str(right)}
        clean_themes[str(task_id)] = str(theme)
    if set(clean_pairs) != set(clean_themes):
        raise PilotValidationError("blind-map 的 pair 与主题任务集不一致")
    return clean_pairs, clean_themes


def _score(row: Mapping[str, str], field: str) -> int:
    raw = (row.get(field) or "").strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise PilotValidationError(f"{field} 必须是 1—5 整数") from exc
    if not 1 <= value <= 5:
        raise PilotValidationError(f"{field} 必须是 1—5 整数")
    return value


def load_ratings(
    paths: Sequence[Path], expected_task_ids: set[str]
) -> tuple[BlindRating, ...]:
    if not paths:
        raise PilotValidationError("至少需要一份评分 CSV")
    ratings: list[BlindRating] = []
    seen: set[tuple[str, str]] = set()
    reviewers: dict[str, set[str]] = defaultdict(set)
    for path in paths:
        if not path.is_file():
            raise PilotValidationError(f"找不到评分 CSV：{path}")
        with path.open(encoding="utf-8-sig", newline="") as handle:
            for line_number, row in enumerate(csv.DictReader(handle), 2):
                reviewer_id = (row.get("reviewer_id") or "").strip()
                task_id = (row.get("task_id") or "").strip()
                if task_id not in expected_task_ids:
                    raise PilotValidationError(f"{path}:{line_number} 未知 Task：{task_id}")
                left = {dim: _score(row, f"left_{dim}") for dim in SCORE_DIMENSIONS}
                right = {dim: _score(row, f"right_{dim}") for dim in SCORE_DIMENSIONS}
                rating = BlindRating(
                    reviewer_id=reviewer_id,
                    task_id=task_id,
                    left_scores=left,
                    right_scores=right,
                    preference=(row.get("preference") or "").strip().casefold(),
                    reason=(row.get("reason") or "").strip(),
                )
                key = (rating.reviewer_id, rating.task_id)
                if key in seen:
                    raise PilotValidationError(
                        f"评审 {rating.reviewer_id} 重复评分 {rating.task_id}"
                    )
                seen.add(key)
                reviewers[rating.reviewer_id].add(rating.task_id)
                ratings.append(rating)
    if not ratings:
        raise PilotValidationError("评分 CSV 没有数据行")
    for reviewer, task_ids in reviewers.items():
        if task_ids != expected_task_ids:
            missing = ", ".join(sorted(expected_task_ids - task_ids))
            raise PilotValidationError(f"评审 {reviewer} 未覆盖全部任务：{missing}")
    return tuple(ratings)


def _wilson_interval(wins: int, total: int) -> tuple[float | None, float | None]:
    if total == 0:
        return None, None
    z = 1.959963984540054
    proportion = wins / total
    denominator = 1 + z * z / total
    centre = (proportion + z * z / (2 * total)) / denominator
    margin = (
        z
        * math.sqrt(proportion * (1 - proportion) / total + z * z / (4 * total**2))
        / denominator
    )
    return centre - margin, centre + margin


def _specific_reason(reason: str) -> bool:
    compact = re.sub(r"[\s，。！？、,.;:!?]", "", reason).casefold()
    return len(compact) >= 12 and compact not in _GENERIC_REASONS


def score_run(run: Path, rating_paths: Sequence[Path]) -> dict[str, Any]:
    pairs, themes = _load_blind_map(run)
    ratings = load_ratings(rating_paths, set(pairs))
    reviewer_ids = sorted({rating.reviewer_id for rating in ratings})
    wins = losses = ties = 0
    theme_counts: dict[str, Counter[str]] = {theme: Counter() for theme in THEMES}
    dimension_deltas: dict[str, list[int]] = defaultdict(list)
    preferences_by_task: dict[str, list[str]] = defaultdict(list)
    specific_win_reasons = 0
    for rating in ratings:
        pair = pairs[rating.task_id]
        knowledge_side = "left" if pair["left"] == "knowledge" else "right"
        baseline_scores = rating.right_scores if knowledge_side == "left" else rating.left_scores
        knowledge_scores = rating.left_scores if knowledge_side == "left" else rating.right_scores
        for dimension in SCORE_DIMENSIONS:
            dimension_deltas[dimension].append(
                knowledge_scores[dimension] - baseline_scores[dimension]
            )
        if rating.preference == "tie":
            outcome = "tie"
            ties += 1
        elif rating.preference == knowledge_side:
            outcome = "win"
            wins += 1
            specific_win_reasons += int(_specific_reason(rating.reason))
        else:
            outcome = "loss"
            losses += 1
        theme_counts[themes[rating.task_id]][outcome] += 1
        preferences_by_task[rating.task_id].append(outcome)

    non_ties = wins + losses
    win_rate = wins / non_ties if non_ties else None
    wilson_low, wilson_high = _wilson_interval(wins, non_ties)
    theme_rates = {
        theme: (
            counts["win"] / (counts["win"] + counts["loss"])
            if counts["win"] + counts["loss"]
            else None
        )
        for theme, counts in theme_counts.items()
    }
    deltas = {dimension: mean(values) for dimension, values in dimension_deltas.items()}
    agreements = []
    for outcomes in preferences_by_task.values():
        agreements.append(max(Counter(outcomes).values()) / len(outcomes))
    specific_rate = specific_win_reasons / wins if wins else None
    eligible = len(pairs) == 30 and len(reviewer_ids) >= 3
    criteria = {
        "overall_win_rate_gte_0_65": win_rate is not None and win_rate >= 0.65,
        "wilson_lower_gt_0_50": wilson_low is not None and wilson_low > 0.50,
        "every_theme_gte_0_55": all(
            rate is not None and rate >= 0.55 for rate in theme_rates.values()
        ),
        "key_dimension_delta_gte_0_40": all(deltas[dim] >= 0.40 for dim in KEY_DIMENSIONS),
        "unsupported_claim_control_non_negative": deltas[
            "unsupported_claim_control"
        ]
        >= 0,
        "specific_win_reason_rate_gte_0_70": specific_rate is not None
        and specific_rate >= 0.70,
    }
    status = "pass" if eligible and all(criteria.values()) else "fail" if eligible else "not_evaluated"
    return {
        "scope": {
            "task_count": len(pairs),
            "reviewer_count": len(reviewer_ids),
            "rating_count": len(ratings),
            "eligible_for_h1": eligible,
        },
        "outcomes": {
            "knowledge_wins": wins,
            "baseline_wins": losses,
            "ties": ties,
            "knowledge_win_rate_excluding_ties": win_rate,
            "wilson_95": {"lower": wilson_low, "upper": wilson_high},
            "tie_rate": ties / len(ratings),
            "theme_win_rates": theme_rates,
            "mean_dimension_deltas": deltas,
            "mean_reviewer_agreement": mean(agreements),
            "specific_reason_rate_for_knowledge_wins": specific_rate,
        },
        "h1": {
            "status": status,
            "criteria": criteria,
            "note": (
                "仅验证工具链；少于 30 题或 3 名评审，不得解读为 H1 结论。"
                if not eligible
                else "按预注册门槛判定。"
            ),
        },
    }


def render_score_report(result: Mapping[str, Any]) -> str:
    return "# H1 知识价值盲测报告\n\n```json\n" + json.dumps(
        result, ensure_ascii=False, indent=2, sort_keys=True
    ) + "\n```\n"


def write_score_report(run: Path, result: Mapping[str, Any], output: Path) -> Path:
    content = render_score_report(result)
    if output.resolve().is_relative_to(run.resolve()):
        write_private_text(output, content)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
    return output
