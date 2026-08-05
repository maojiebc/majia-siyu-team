"""Phase 0 审核吞吐与价值交换报表。"""
from __future__ import annotations

import csv
import math
from pathlib import Path
from statistics import mean, median
from typing import Any, Mapping, Sequence

from .models import EditorialLog, PilotValidationError


_SUMMARY_FIELDS = (
    "pilot_invited_total",
    "complaint_count",
    "weekly_capacity_stable",
    "rework_count",
)


def _optional_count(value: str, field: str) -> int | None:
    if not value.strip():
        return None
    try:
        number = int(value)
    except ValueError as exc:
        raise PilotValidationError(f"{field} 必须是非负整数或留空") from exc
    if number < 0:
        raise PilotValidationError(f"{field} 不能为负数")
    return number


def _optional_bool(value: str, field: str) -> bool | None:
    if not value.strip():
        return None
    normalized = value.strip().casefold()
    if normalized in {"true", "1", "yes", "y", "是"}:
        return True
    if normalized in {"false", "0", "no", "n", "否"}:
        return False
    raise PilotValidationError(f"{field} 必须是 true/false 或留空")


def load_editorial_csv(
    path: Path,
) -> tuple[tuple[EditorialLog, ...], dict[str, Any], tuple[bool | None, ...]]:
    if not path.is_file():
        raise PilotValidationError(f"找不到审核日志 CSV：{path}")
    logs: list[EditorialLog] = []
    delivery_timeliness: list[bool | None] = []
    collected: dict[str, set[str]] = {field: set() for field in _SUMMARY_FIELDS}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise PilotValidationError("审核日志 CSV 缺少表头")
        for line_number, row in enumerate(reader, 2):
            try:
                log = EditorialLog.from_row(row)
                timeliness = _optional_bool(
                    row.get("case_card_within_5_workdays", ""),
                    "case_card_within_5_workdays",
                )
            except PilotValidationError as exc:
                raise PilotValidationError(f"{path}:{line_number} {exc}") from exc
            logs.append(log)
            delivery_timeliness.append(timeliness)
            for field in _SUMMARY_FIELDS:
                value = (row.get(field) or "").strip()
                if value:
                    collected[field].add(value)
    if not logs:
        raise PilotValidationError("审核日志 CSV 没有数据行")
    for field, values in collected.items():
        if len(values) > 1:
            raise PilotValidationError(f"汇总字段 {field} 在 CSV 中取值不一致")
    raw_summary = {field: next(iter(values), "") for field, values in collected.items()}
    summary: dict[str, Any] = {
        "pilot_invited_total": _optional_count(
            raw_summary["pilot_invited_total"], "pilot_invited_total"
        ),
        "complaint_count": _optional_count(
            raw_summary["complaint_count"], "complaint_count"
        ),
        "weekly_capacity_stable": _optional_bool(
            raw_summary["weekly_capacity_stable"], "weekly_capacity_stable"
        ),
        "rework_count": _optional_count(raw_summary["rework_count"], "rework_count"),
    }
    return tuple(logs), summary, tuple(delivery_timeliness)


def _nearest_rank(values: Sequence[float], percentile: float) -> float | None:
    if len(values) < 4:
        return None
    ordered = sorted(values)
    return ordered[math.ceil(percentile * len(ordered)) - 1]


def _status_metrics(logs: Sequence[EditorialLog]) -> dict[str, Any]:
    totals = [log.total_minutes for log in logs if log.total_minutes is not None]
    return {
        "count": len(logs),
        "complete_time_count": len(totals),
        "missing_time_count": len(logs) - len(totals),
        "median_minutes": median(totals) if totals else None,
        "p75_minutes_nearest_rank": _nearest_rank(totals, 0.75),
    }


def _known_bool_rate(
    values: Sequence[bool | None], *, require_complete: bool = False
) -> float | None:
    if require_complete and any(value is None for value in values):
        return None
    known = [value for value in values if value is not None]
    return sum(known) / len(known) if known else None


def _known_mean(
    values: Sequence[int | float | None], *, require_complete: bool = False
) -> float | None:
    if require_complete and any(value is None for value in values):
        return None
    known = [float(value) for value in values if value is not None]
    return mean(known) if known else None


def summarize_editorial(path: Path) -> dict[str, Any]:
    logs, summary, delivery_timeliness = load_editorial_csv(path)
    qualified_indexes = [index for index, log in enumerate(logs) if log.status == "qualified"]
    qualified = [logs[index] for index in qualified_indexes]
    rejected = [log for log in logs if log.status == "rejected"]
    submitted_count = len(logs)
    confirmed_atoms = sum(log.confirmed_atom_count or 0 for log in logs)
    willing_rate = _known_bool_rate(
        [log.would_contribute_again for log in logs], require_complete=True
    )
    value_scores = [
        log.value_exchange_score for log in logs if log.value_exchange_score is not None
    ]
    value_match_rate = (
        sum(score >= 4 for score in value_scores) / len(value_scores) if value_scores else None
    )
    if len(value_scores) != len(logs):
        value_match_rate = None
    qualified_metrics = _status_metrics(qualified)
    rejected_metrics = _status_metrics(rejected)
    average_followups = _known_mean(
        [log.followup_count for log in qualified], require_complete=True
    )
    average_draft_atoms = _known_mean(
        [log.draft_atom_count for log in qualified], require_complete=True
    )
    qualified_timeliness = [delivery_timeliness[index] for index in qualified_indexes]
    delivery_rate = _known_bool_rate(qualified_timeliness, require_complete=True)
    rework_rate = (
        summary["rework_count"] / len(qualified)
        if summary["rework_count"] is not None and qualified
        else None
    )

    h2_criteria: dict[str, bool | None] = {
        "invited_at_least_10": (
            summary["pilot_invited_total"] >= 10
            if summary["pilot_invited_total"] is not None
            else None
        ),
        "submitted_at_least_6": submitted_count >= 6,
        "qualified_at_least_4": len(qualified) >= 4,
        "confirmed_draft_atoms_at_least_8": confirmed_atoms >= 8,
        "would_contribute_again_gte_0_60": (
            willing_rate >= 0.60 if willing_rate is not None else None
        ),
        "value_match_gte_0_70": (
            value_match_rate >= 0.70 if value_match_rate is not None else None
        ),
        "no_authorization_or_reward_complaints": (
            summary["complaint_count"] == 0
            if summary["complaint_count"] is not None
            else None
        ),
    }
    h3_criteria: dict[str, bool | None] = {
        "qualified_median_minutes_lte_20": (
            qualified_metrics["median_minutes"] <= 20
            if qualified_metrics["median_minutes"] is not None
            and qualified_metrics["missing_time_count"] == 0
            else None
        ),
        "qualified_p75_minutes_lte_30": (
            qualified_metrics["p75_minutes_nearest_rank"] <= 30
            if qualified_metrics["p75_minutes_nearest_rank"] is not None
            and qualified_metrics["missing_time_count"] == 0
            else None
        ),
        "average_followups_lte_1": (
            average_followups <= 1 if average_followups is not None else None
        ),
        "average_reviewable_atoms_between_1_and_3": (
            1 <= average_draft_atoms <= 3 if average_draft_atoms is not None else None
        ),
        "case_cards_within_5_workdays": (
            delivery_rate == 1 if delivery_rate is not None else None
        ),
        "weekly_capacity_at_least_5_stable": summary["weekly_capacity_stable"],
        "privacy_misunderstanding_authorization_rework_lt_0_10": (
            rework_rate < 0.10 if rework_rate is not None else None
        ),
    }

    def hypothesis(criteria: Mapping[str, bool | None]) -> dict[str, Any]:
        complete = all(value is not None for value in criteria.values())
        if complete:
            status = "pass" if all(criteria.values()) else "fail"
        else:
            status = "not_evaluated"
        return {
            "status": status,
            "criteria": dict(criteria),
            "note": (
                "缺少判定所需字段，不得把未评估解读为通过。"
                if not complete
                else "按预注册门槛判定。"
            ),
        }

    return {
        "funnel": {
            "invited": summary["pilot_invited_total"],
            "submitted": submitted_count,
            "qualified": len(qualified),
            "confirmed_atoms": confirmed_atoms,
            "case_cards_delivered": sum(log.case_card_delivered is True for log in logs),
        },
        "human_cost": {
            "qualified": qualified_metrics,
            "rejected": rejected_metrics,
            "average_followups_qualified": average_followups,
            "average_draft_atoms_qualified": average_draft_atoms,
        },
        "contributor_value": {
            "would_contribute_again_rate": willing_rate,
            "value_match_score_4_or_5_rate": value_match_rate,
            "case_card_within_5_workdays_rate": delivery_rate,
        },
        "risks": {
            "complaint_count": summary["complaint_count"],
            "rework_count": summary["rework_count"],
            "rework_rate_among_qualified": rework_rate,
            "weekly_capacity_stable": summary["weekly_capacity_stable"],
        },
        "h2": hypothesis(h2_criteria),
        "h3": hypothesis(h3_criteria),
    }


def render_editorial_report(result: Mapping[str, Any]) -> str:
    funnel = result["funnel"]
    cost = result["human_cost"]
    value = result["contributor_value"]
    risks = result["risks"]

    def show(number: Any) -> str:
        if number is None:
            return "未记录"
        return str(round(number, 4) if isinstance(number, float) else number)

    return f"""# Phase 0 审核吞吐报告

> 本报告不包含贡献者姓名、联系方式或案例正文。缺失值未按 0 处理。

## 贡献漏斗

- 邀请：{show(funnel['invited'])}
- 提交：{show(funnel['submitted'])}
- Qualified：{show(funnel['qualified'])}
- 本人确认原子：{show(funnel['confirmed_atoms'])}
- 案例卡已交付：{show(funnel['case_cards_delivered'])}

## 人工成本

- Qualified 完整工时样本：{show(cost['qualified']['complete_time_count'])}
- Qualified 缺失工时样本：{show(cost['qualified']['missing_time_count'])}
- Qualified 中位数（分钟）：{show(cost['qualified']['median_minutes'])}
- Qualified P75（最近秩，n<4 不输出）：{show(cost['qualified']['p75_minutes_nearest_rank'])}
- Rejected 中位数（分钟）：{show(cost['rejected']['median_minutes'])}
- Qualified 平均补问次数：{show(cost['average_followups_qualified'])}
- Qualified 平均 Draft 原子数：{show(cost['average_draft_atoms_qualified'])}

## 贡献者价值

- 愿意再次参与：{show(value['would_contribute_again_rate'])}
- 交换价值评分 4—5 比例：{show(value['value_match_score_4_or_5_rate'])}
- 案例卡 5 个工作日内交付率：{show(value['case_card_within_5_workdays_rate'])}

## 风险

- 授权或回报投诉：{show(risks['complaint_count'])}
- 隐私、误解或授权返工：{show(risks['rework_count'])}
- 每周稳定处理至少 5 份：{show(risks['weekly_capacity_stable'])}

## 结论

- H2 Contribution Demand：{result['h2']['status']}
- H3 Editorial Throughput：{result['h3']['status']}
- H2 说明：{result['h2']['note']}
- H3 说明：{result['h3']['note']}
"""
