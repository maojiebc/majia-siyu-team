"""盲测评分聚合与 H1 判定。

主分析先在每个任务内聚合评审，再把任务作为独立样本。
``reviewer × task`` 级别的结果只作次要分析，不进入 H1 门槛。
"""
from __future__ import annotations

from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import random
import re
from statistics import mean
from typing import Any, Mapping, Sequence

from .models import (
    BlindRating,
    GenerationManifest,
    PilotValidationError,
    SCORE_DIMENSIONS,
    THEMES,
    canonical_json,
)
from .packets import write_private_text


# 与稳定化文档的正式门槛一致：三个业务质量维度。
KEY_DIMENSIONS = (
    "industry_realism",
    "action_priority",
    "organization_constraints",
)
BOOTSTRAP_ITERATIONS = 2_000
_GENERIC_REASONS = {
    "更好",
    "更专业",
    "更全面",
    "更实用",
    "比较好",
    "左边更好",
    "右边更好",
}


def _load_blind_map(
    run: Path,
) -> tuple[
    Mapping[str, Mapping[str, str]],
    Mapping[str, str],
    int,
    Mapping[str, Mapping[str, str]],
    Mapping[str, str],
]:
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
    seed = data.get("seed")
    if not isinstance(pairs, Mapping) or not isinstance(themes, Mapping):
        raise PilotValidationError("blind-map 缺少 pairs 或 task_themes")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise PilotValidationError("blind-map.seed 必须是整数")
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

    if data.get("hash_algorithm") != "sha256":
        raise PilotValidationError(
            "blind-map 缺少 v1.4.2 SHA-256 完整性记录；请重新运行 blind"
        )
    raw_answer_hashes = data.get("generation_answer_hashes")
    raw_pair_hashes = data.get("blind_pair_hashes")
    if not isinstance(raw_answer_hashes, Mapping) or not isinstance(
        raw_pair_hashes, Mapping
    ):
        raise PilotValidationError(
            "blind-map 缺少 v1.4.2 完整性哈希；请重新运行 blind"
        )
    if set(raw_answer_hashes) != set(clean_pairs) or set(raw_pair_hashes) != set(
        clean_pairs
    ):
        raise PilotValidationError("blind-map 完整性哈希未覆盖同一批任务")

    digest_pattern = re.compile(r"[0-9a-f]{64}")
    clean_answer_hashes: dict[str, Mapping[str, str]] = {}
    clean_pair_hashes: dict[str, str] = {}
    for task_id in clean_pairs:
        raw_task_hashes = raw_answer_hashes.get(task_id)
        if not isinstance(raw_task_hashes, Mapping) or set(raw_task_hashes) != {
            "baseline",
            "knowledge",
        }:
            raise PilotValidationError(f"blind-map 答案哈希非法：{task_id}")
        task_hashes: dict[str, str] = {}
        for version in ("baseline", "knowledge"):
            digest = raw_task_hashes.get(version)
            if not isinstance(digest, str) or digest_pattern.fullmatch(digest) is None:
                raise PilotValidationError(
                    f"blind-map 答案哈希非法：{task_id}:{version}"
                )
            task_hashes[version] = digest
        pair_digest = raw_pair_hashes.get(task_id)
        if (
            not isinstance(pair_digest, str)
            or digest_pattern.fullmatch(pair_digest) is None
        ):
            raise PilotValidationError(f"blind-map 盲测对哈希非法：{task_id}")
        clean_answer_hashes[task_id] = task_hashes
        clean_pair_hashes[task_id] = pair_digest
    return clean_pairs, clean_themes, seed, clean_answer_hashes, clean_pair_hashes


def _verify_blind_integrity(
    run: Path,
    task_ids: Sequence[str],
    expected_answer_hashes: Mapping[str, Mapping[str, str]],
    expected_pair_hashes: Mapping[str, str],
) -> None:
    """确认评分仍对应盲化时冻结的源答案与盲测文件。"""
    for task_id in sorted(task_ids):
        for version in ("baseline", "knowledge"):
            path = run / "generation" / version / f"{task_id}.md"
            if not path.is_file():
                raise PilotValidationError(f"缺少模型答案：{path}")
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != expected_answer_hashes[task_id][version]:
                raise PilotValidationError(
                    f"盲化后源答案被修改：{task_id}:{version}；请重新运行 blind"
                )
        pair_path = run / "blind" / "pairs" / f"{task_id}.md"
        if not pair_path.is_file():
            raise PilotValidationError(f"缺少盲测对：{pair_path}")
        actual_pair = hashlib.sha256(pair_path.read_bytes()).hexdigest()
        if actual_pair != expected_pair_hashes[task_id]:
            raise PilotValidationError(
                f"盲化后盲测对被修改：{task_id}；请重新运行 blind"
            )


def _load_run_manifest(
    run: Path,
) -> tuple[GenerationManifest, str, tuple[str, ...], int]:
    path = run / "manifest.json"
    if not path.is_file():
        raise PilotValidationError(f"找不到试验 manifest：{path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PilotValidationError(f"manifest JSON 非法：{exc.msg}") from exc
    if not isinstance(payload, Mapping):
        raise PilotValidationError("manifest 必须是对象")
    raw_manifest = payload.get("manifest")
    if not isinstance(raw_manifest, Mapping):
        raise PilotValidationError("manifest.manifest 必须是对象")
    manifest = GenerationManifest.from_dict(raw_manifest)
    run_mode = payload.get("run_mode", "")
    if run_mode not in {"formal_evaluation", "tooling_dry_run", ""}:
        raise PilotValidationError("manifest.run_mode 非法")
    seed = payload.get("seed")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise PilotValidationError("manifest.seed 必须是整数")
    return manifest, str(run_mode), manifest.missing_for_evaluation(), seed


def _score(row: Mapping[str, str], field: str) -> int:
    raw = (row.get(field) or "").strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise PilotValidationError(f"{field} 必须是 1—5 整数") from exc
    if not 1 <= value <= 5:
        raise PilotValidationError(f"{field} 必须是 1—5 整数")
    return value


def _optional_count(row: Mapping[str, str], field: str) -> int | None:
    raw = (row.get(field) or "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError as exc:
        raise PilotValidationError(f"{field} 必须是非负整数或留空") from exc
    if value < 0:
        raise PilotValidationError(f"{field} 必须是非负整数或留空")
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
                    raise PilotValidationError(
                        f"{path}:{line_number} 未知 Task：{task_id}"
                    )
                left = {
                    dimension: _score(row, f"left_{dimension}")
                    for dimension in SCORE_DIMENSIONS
                }
                right = {
                    dimension: _score(row, f"right_{dimension}")
                    for dimension in SCORE_DIMENSIONS
                }
                rating = BlindRating(
                    reviewer_id=reviewer_id,
                    task_id=task_id,
                    left_scores=left,
                    right_scores=right,
                    preference=(row.get("preference") or "").strip().casefold(),
                    reason=(row.get("reason") or "").strip(),
                    left_unsupported_precise_claims=_optional_count(
                        row, "left_unsupported_precise_claims"
                    ),
                    right_unsupported_precise_claims=_optional_count(
                        row, "right_unsupported_precise_claims"
                    ),
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
        * math.sqrt(
            proportion * (1 - proportion) / total + z * z / (4 * total**2)
        )
        / denominator
    )
    return centre - margin, centre + margin


def _specific_reason(reason: str) -> bool:
    compact = re.sub(r"[\s，。！？、,.;:!?]", "", reason).casefold()
    return len(compact) >= 12 and compact not in _GENERIC_REASONS


def _outcome(rating: BlindRating, pair: Mapping[str, str]) -> str:
    knowledge_side = "left" if pair["left"] == "knowledge" else "right"
    if rating.preference == "tie":
        return "tie"
    return "win" if rating.preference == knowledge_side else "loss"


def _majority_outcome(outcomes: Sequence[str]) -> str:
    """严格多数决；没有超过半数的单一结果则为任务级平局。"""
    counts = Counter(outcomes)
    threshold = len(outcomes) / 2
    if counts["win"] > threshold:
        return "win"
    if counts["loss"] > threshold:
        return "loss"
    return "tie"


def _tie_sensitivity(wins: int, losses: int, ties: int) -> dict[str, float | None]:
    total = wins + losses + ties
    non_ties = wins + losses
    return {
        "excluding_ties": wins / non_ties if non_ties else None,
        "tie_as_half": (wins + 0.5 * ties) / total if total else None,
        "ties_as_losses": wins / total if total else None,
        "ties_as_wins": (wins + ties) / total if total else None,
    }


def _percentile(sorted_values: Sequence[float], probability: float) -> float:
    if not sorted_values:
        raise ValueError("percentile requires at least one value")
    position = (len(sorted_values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    fraction = position - lower
    return sorted_values[lower] * (1 - fraction) + sorted_values[upper] * fraction


def _task_cluster_bootstrap(
    values: Mapping[str, Sequence[float]],
    *,
    seed: int,
    iterations: int = BOOTSTRAP_ITERATIONS,
) -> dict[str, Any]:
    """以任务为整群重抽样，不把同题的多个评审当独立样本。"""
    if not values:
        return {"method": "task_cluster", "iterations": iterations, "dimensions": {}}
    lengths = {len(series) for series in values.values()}
    if len(lengths) != 1 or not lengths or next(iter(lengths)) == 0:
        raise PilotValidationError("bootstrap 维度必须覆盖同一批任务")
    task_count = next(iter(lengths))
    generator = random.Random(seed)
    samples: dict[str, list[float]] = {name: [] for name in values}
    for _ in range(iterations):
        indexes = [generator.randrange(task_count) for _ in range(task_count)]
        for name, series in values.items():
            samples[name].append(mean(series[index] for index in indexes))
    intervals: dict[str, dict[str, float]] = {}
    for name, estimates in samples.items():
        estimates.sort()
        intervals[name] = {
            "lower": _percentile(estimates, 0.025),
            "upper": _percentile(estimates, 0.975),
        }
    return {
        "method": "deterministic_task_cluster_percentile",
        "iterations": iterations,
        "seed": seed,
        "dimensions": intervals,
    }


def _fleiss_kappa(outcomes_by_task: Mapping[str, Sequence[str]]) -> float | None:
    if not outcomes_by_task:
        return None
    reviewer_counts = {len(outcomes) for outcomes in outcomes_by_task.values()}
    if len(reviewer_counts) != 1:
        return None
    reviewer_count = next(iter(reviewer_counts))
    if reviewer_count < 2:
        return None
    categories = ("win", "loss", "tie")
    agreements: list[float] = []
    totals: Counter[str] = Counter()
    for outcomes in outcomes_by_task.values():
        counts = Counter(outcomes)
        totals.update(counts)
        numerator = sum(counts[category] ** 2 for category in categories) - reviewer_count
        agreements.append(numerator / (reviewer_count * (reviewer_count - 1)))
    observed = mean(agreements)
    all_ratings = len(outcomes_by_task) * reviewer_count
    expected = sum((totals[category] / all_ratings) ** 2 for category in categories)
    if math.isclose(expected, 1.0):
        return None
    return (observed - expected) / (1 - expected)


def _answer_hashes(run: Path, task_ids: Sequence[str]) -> dict[str, Any]:
    per_task: dict[str, dict[str, str]] = {}
    version_maps: dict[str, dict[str, str]] = {"baseline": {}, "knowledge": {}}
    for task_id in sorted(task_ids):
        task_hashes: dict[str, str] = {}
        for version in ("baseline", "knowledge"):
            path = run / "generation" / version / f"{task_id}.md"
            if not path.is_file():
                raise PilotValidationError(f"缺少模型答案：{path}")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            task_hashes[version] = digest
            version_maps[version][task_id] = digest
        per_task[task_id] = task_hashes
    return {
        "baseline_set_hash": hashlib.sha256(
            canonical_json(version_maps["baseline"]).encode("utf-8")
        ).hexdigest(),
        "knowledge_set_hash": hashlib.sha256(
            canonical_json(version_maps["knowledge"]).encode("utf-8")
        ).hexdigest(),
        "per_task": per_task,
    }


def _theme_rates(theme_counts: Mapping[str, Counter[str]]) -> dict[str, float | None]:
    return {
        theme: (
            counts["win"] / (counts["win"] + counts["loss"])
            if counts["win"] + counts["loss"]
            else None
        )
        for theme, counts in theme_counts.items()
    }


def score_run(run: Path, rating_paths: Sequence[Path]) -> dict[str, Any]:
    (
        pairs,
        themes,
        seed,
        expected_answer_hashes,
        expected_pair_hashes,
    ) = _load_blind_map(run)
    (
        generation_manifest,
        run_mode,
        missing_run_config,
        generation_seed,
    ) = _load_run_manifest(run)
    if generation_seed != seed:
        raise PilotValidationError("manifest.seed 与 blind-map.seed 不一致")
    _verify_blind_integrity(
        run,
        tuple(pairs),
        expected_answer_hashes,
        expected_pair_hashes,
    )
    ratings = load_ratings(rating_paths, set(pairs))
    reviewer_ids = sorted({rating.reviewer_id for rating in ratings})

    rating_outcomes: dict[str, list[str]] = defaultdict(list)
    dimension_by_task: dict[str, dict[str, list[int]]] = {
        task_id: {dimension: [] for dimension in SCORE_DIMENSIONS}
        for task_id in pairs
    }
    rating_dimension_deltas: dict[str, list[int]] = defaultdict(list)
    rating_theme_counts: dict[str, Counter[str]] = {
        theme: Counter() for theme in THEMES
    }
    specific_knowledge_win_reasons: dict[str, list[bool]] = defaultdict(list)
    claims_by_task: dict[str, list[tuple[int, int]]] = defaultdict(list)
    missing_claim_rows: list[str] = []

    for rating in ratings:
        pair = pairs[rating.task_id]
        outcome = _outcome(rating, pair)
        rating_outcomes[rating.task_id].append(outcome)
        rating_theme_counts[themes[rating.task_id]][outcome] += 1
        if outcome == "win":
            specific_knowledge_win_reasons[rating.task_id].append(
                _specific_reason(rating.reason)
            )

        knowledge_side = "left" if pair["left"] == "knowledge" else "right"
        baseline_scores = (
            rating.right_scores if knowledge_side == "left" else rating.left_scores
        )
        knowledge_scores = (
            rating.left_scores if knowledge_side == "left" else rating.right_scores
        )
        for dimension in SCORE_DIMENSIONS:
            delta = knowledge_scores[dimension] - baseline_scores[dimension]
            dimension_by_task[rating.task_id][dimension].append(delta)
            rating_dimension_deltas[dimension].append(delta)

        left_claims = rating.left_unsupported_precise_claims
        right_claims = rating.right_unsupported_precise_claims
        if left_claims is None or right_claims is None:
            missing_claim_rows.append(f"{rating.reviewer_id}:{rating.task_id}")
        elif knowledge_side == "left":
            claims_by_task[rating.task_id].append((right_claims, left_claims))
        else:
            claims_by_task[rating.task_id].append((left_claims, right_claims))

    task_counts: Counter[str] = Counter()
    task_theme_counts: dict[str, Counter[str]] = {
        theme: Counter() for theme in THEMES
    }
    task_outcome_map: dict[str, str] = {}
    agreement_values: list[float] = []
    task_dimension_series: dict[str, list[float]] = {
        dimension: [] for dimension in SCORE_DIMENSIONS
    }
    specific_winning_tasks = 0
    winning_tasks = 0
    baseline_claim_task_means: list[float] = []
    knowledge_claim_task_means: list[float] = []
    baseline_claim_task_occurrences: list[bool] = []
    knowledge_claim_task_occurrences: list[bool] = []

    for task_id in sorted(pairs):
        outcomes = rating_outcomes[task_id]
        task_outcome = _majority_outcome(outcomes)
        task_outcome_map[task_id] = task_outcome
        task_counts[task_outcome] += 1
        task_theme_counts[themes[task_id]][task_outcome] += 1
        agreement_values.append(max(Counter(outcomes).values()) / len(outcomes))
        for dimension in SCORE_DIMENSIONS:
            task_dimension_series[dimension].append(
                mean(dimension_by_task[task_id][dimension])
            )
        if task_outcome == "win":
            winning_tasks += 1
            reasons = specific_knowledge_win_reasons[task_id]
            if reasons and sum(reasons) >= math.ceil(len(reasons) / 2):
                specific_winning_tasks += 1
        task_claims = claims_by_task.get(task_id, [])
        if len(task_claims) == len(outcomes):
            baseline_claim_task_means.append(mean(item[0] for item in task_claims))
            knowledge_claim_task_means.append(mean(item[1] for item in task_claims))
            # 同一答案由多名评审独立标记；超过半数评审
            # 发现至少一个时，才记为该任务“出现”。
            baseline_claim_task_occurrences.append(
                sum(item[0] > 0 for item in task_claims) > len(task_claims) / 2
            )
            knowledge_claim_task_occurrences.append(
                sum(item[1] > 0 for item in task_claims) > len(task_claims) / 2
            )

    task_wins = task_counts["win"]
    task_losses = task_counts["loss"]
    task_ties = task_counts["tie"]
    task_non_ties = task_wins + task_losses
    task_win_rate = task_wins / task_non_ties if task_non_ties else None
    task_wilson_low, task_wilson_high = _wilson_interval(task_wins, task_non_ties)
    task_dimension_means = {
        dimension: mean(values) for dimension, values in task_dimension_series.items()
    }
    claims_complete = not missing_claim_rows
    baseline_claim_mean = (
        mean(baseline_claim_task_means) if claims_complete else None
    )
    knowledge_claim_mean = (
        mean(knowledge_claim_task_means) if claims_complete else None
    )
    baseline_claim_occurrence_rate = (
        mean(baseline_claim_task_occurrences) if claims_complete else None
    )
    knowledge_claim_occurrence_rate = (
        mean(knowledge_claim_task_occurrences) if claims_complete else None
    )
    task_specific_rate = (
        specific_winning_tasks / winning_tasks if winning_tasks else None
    )
    bootstrap = _task_cluster_bootstrap(
        task_dimension_series,
        seed=seed,
    )

    rating_counts = Counter(
        outcome for outcomes in rating_outcomes.values() for outcome in outcomes
    )
    rating_wins = rating_counts["win"]
    rating_losses = rating_counts["loss"]
    rating_ties = rating_counts["tie"]
    rating_non_ties = rating_wins + rating_losses
    rating_win_rate = rating_wins / rating_non_ties if rating_non_ties else None
    rating_wilson_low, rating_wilson_high = _wilson_interval(
        rating_wins, rating_non_ties
    )
    rating_specific_flags = [
        flag for flags in specific_knowledge_win_reasons.values() for flag in flags
    ]
    rating_specific_rate = (
        sum(rating_specific_flags) / len(rating_specific_flags)
        if rating_specific_flags
        else None
    )
    rating_claim_pairs = [
        pair for task_pairs in claims_by_task.values() for pair in task_pairs
    ]
    task_theme_rates = _theme_rates(task_theme_counts)
    rating_theme_rates = _theme_rates(rating_theme_counts)

    primary = {
        "analysis_unit": "task",
        "independent_sample_count": len(pairs),
        "aggregation_rule": "strict_reviewer_majority_else_tie",
        "knowledge_wins": task_wins,
        "baseline_wins": task_losses,
        "ties": task_ties,
        "knowledge_win_rate_excluding_ties": task_win_rate,
        "wilson_95": {"lower": task_wilson_low, "upper": task_wilson_high},
        "tie_rate": task_ties / len(pairs),
        "tie_sensitivity": _tie_sensitivity(task_wins, task_losses, task_ties),
        "theme_win_rates": task_theme_rates,
        "mean_dimension_deltas": task_dimension_means,
        "task_cluster_bootstrap_95": bootstrap,
        "mean_reviewer_agreement": mean(agreement_values),
        "fleiss_kappa": _fleiss_kappa(rating_outcomes),
        "specific_reason_rate_for_knowledge_winning_tasks": task_specific_rate,
        "unsupported_precise_claim_baseline": baseline_claim_occurrence_rate,
        "unsupported_precise_claim_knowledge": knowledge_claim_occurrence_rate,
        "unsupported_precise_claims": {
            "complete": claims_complete,
            "missing_rating_count": len(missing_claim_rows),
            "task_occurrence_aggregation": (
                "strict_majority_of_reviewers_marked_count_gt_zero"
            ),
            "baseline_task_occurrence_rate": baseline_claim_occurrence_rate,
            "knowledge_task_occurrence_rate": knowledge_claim_occurrence_rate,
            "baseline_mean_count_per_task": baseline_claim_mean,
            "knowledge_mean_count_per_task": knowledge_claim_mean,
        },
        "task_outcomes": task_outcome_map,
    }
    secondary = {
        "analysis_unit": "reviewer_task_rating",
        "independent_for_h1_gate": False,
        "rating_count": len(ratings),
        "knowledge_wins": rating_wins,
        "baseline_wins": rating_losses,
        "ties": rating_ties,
        "knowledge_win_rate_excluding_ties": rating_win_rate,
        "wilson_95_descriptive_only": {
            "lower": rating_wilson_low,
            "upper": rating_wilson_high,
        },
        "tie_rate": rating_ties / len(ratings),
        "tie_sensitivity": _tie_sensitivity(
            rating_wins, rating_losses, rating_ties
        ),
        "theme_win_rates": rating_theme_rates,
        "mean_dimension_deltas": {
            dimension: mean(values)
            for dimension, values in rating_dimension_deltas.items()
        },
        "specific_reason_rate_for_knowledge_wins": rating_specific_rate,
        "unsupported_precise_claim_baseline": (
            mean(item[0] > 0 for item in rating_claim_pairs)
            if claims_complete
            else None
        ),
        "unsupported_precise_claim_knowledge": (
            mean(item[1] > 0 for item in rating_claim_pairs)
            if claims_complete
            else None
        ),
        "unsupported_precise_claims": {
            "complete": claims_complete,
            "baseline_total": (
                sum(item[0] for item in rating_claim_pairs)
                if claims_complete
                else None
            ),
            "knowledge_total": (
                sum(item[1] for item in rating_claim_pairs)
                if claims_complete
                else None
            ),
            "baseline_rating_occurrence_rate": (
                mean(item[0] > 0 for item in rating_claim_pairs)
                if claims_complete
                else None
            ),
            "knowledge_rating_occurrence_rate": (
                mean(item[1] > 0 for item in rating_claim_pairs)
                if claims_complete
                else None
            ),
        },
    }

    answer_hashes = _answer_hashes(run, tuple(pairs))
    theme_task_counts = Counter(themes.values())
    evaluation_issues: list[str] = []
    if len(pairs) != 30:
        evaluation_issues.append("requires_exactly_30_tasks")
    if any(theme_task_counts[theme] != 10 for theme in THEMES):
        evaluation_issues.append("requires_10_tasks_per_theme")
    if len(reviewer_ids) < 3:
        evaluation_issues.append("requires_at_least_3_reviewers")
    if missing_run_config:
        evaluation_issues.append(
            "incomplete_run_config:" + ",".join(missing_run_config)
        )
    if run_mode != "formal_evaluation" and len(pairs) == 30:
        evaluation_issues.append("run_not_marked_formal_evaluation")
    if not claims_complete:
        evaluation_issues.append(
            f"missing_unsupported_precise_claim_counts:{len(missing_claim_rows)}"
        )
    eligible = not evaluation_issues
    evaluation_state = (
        "evaluated"
        if eligible
        else "tooling_validated"
        if len(pairs) < 30
        else "not_evaluated"
    )

    criteria = {
        "task_win_rate_gte_0_65": task_win_rate is not None
        and task_win_rate >= 0.65,
        "task_wilson_lower_gt_0_50": task_wilson_low is not None
        and task_wilson_low > 0.50,
        "every_theme_task_win_rate_gte_0_55": all(
            rate is not None and rate >= 0.55
            for rate in task_theme_rates.values()
        ),
        "key_task_dimension_delta_gte_0_40": all(
            task_dimension_means[dimension] >= 0.40
            for dimension in KEY_DIMENSIONS
        ),
        "unsupported_precise_claims_not_higher": (
            claims_complete
            and baseline_claim_occurrence_rate is not None
            and knowledge_claim_occurrence_rate is not None
            and knowledge_claim_occurrence_rate <= baseline_claim_occurrence_rate
        ),
        "specific_knowledge_win_rating_reason_rate_gte_0_70": rating_specific_rate
        is not None
        and rating_specific_rate >= 0.70,
    }
    status = (
        "pass"
        if eligible and all(criteria.values())
        else "fail"
        if eligible
        else "not_evaluated"
    )
    if evaluation_state == "tooling_validated":
        note = (
            "tooling_validated：仅验证工具链；少于 30 题不得解读为 "
            "H1 结论。"
        )
    elif evaluation_state == "not_evaluated":
        note = "Not Evaluated：正式评估条件不完整，不得自动写 Pass。"
    else:
        note = "evaluated：按预注册的任务级主分析门槛判定。"

    result = {
        "scope": {
            "task_count": len(pairs),
            "reviewer_count": len(reviewer_ids),
            "rating_count": len(ratings),
            "primary_independent_sample_count": len(pairs),
            "eligible_for_h1": eligible,
            "evaluation_state": evaluation_state,
            "evaluation_issues": evaluation_issues,
        },
        "run_configuration": {
            **generation_manifest.to_dict(),
            "generation_seed": generation_seed,
            "blind_seed": seed,
            "run_mode": run_mode or "legacy_unspecified",
            "complete_for_evaluation": not missing_run_config,
            "missing_fields": list(missing_run_config),
            "answer_hashes": answer_hashes,
        },
        "primary_task_level": primary,
        "secondary_rating_level": secondary,
        # 一个补丁版保留旧键，但语义已明确是任务级主分析。
        "outcomes": primary,
        "h1": {
            "status": status,
            "evaluation_state": evaluation_state,
            "criteria": criteria,
            "note": note,
        },
    }
    return result


def render_score_report(result: Mapping[str, Any]) -> str:
    scope = result.get("scope", {})
    h1 = result.get("h1", {})
    primary = result.get("primary_task_level", {})
    secondary = result.get("secondary_rating_level", {})
    lines = [
        "# H1 知识价值盲测报告",
        "",
        f"**H1 状态：{h1.get('status', 'not_evaluated')}**",
        f"**评估阶段：{scope.get('evaluation_state', 'not_evaluated')}**",
        "",
        "## 主分析：任务级",
        "",
        "每个任务先聚合评审者，再以任务为独立样本。",
        "",
        "```json",
        json.dumps(primary, ensure_ascii=False, indent=2, sort_keys=True),
        "```",
        "",
        "## 次要分析：评分级",
        "",
        "评审者×任务结果只作描述，不进入 H1 门槛。",
        "",
        "```json",
        json.dumps(secondary, ensure_ascii=False, indent=2, sort_keys=True),
        "```",
        "",
        "## 完整机读结果",
        "",
        "```json",
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True),
        "```",
        "",
    ]
    return "\n".join(lines)


def write_score_report(run: Path, result: Mapping[str, Any], output: Path) -> Path:
    content = render_score_report(result)
    if output.resolve().is_relative_to(run.resolve()):
        write_private_text(output, content)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
    return output
