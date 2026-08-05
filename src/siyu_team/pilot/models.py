"""Pilot 数据模型；只描述离线试验，不接 Runtime 或外部 API。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import re
from typing import Any, Mapping, Sequence


THEMES = ("add_wechat", "activity_increment", "repurchase_recall")
SCORE_DIMENSIONS = (
    "industry_realism",
    "action_priority",
    "organization_constraints",
    "metric_rigor",
    "boundary_awareness",
    "unsupported_claim_control",
    "actionability",
)
PREFERENCES = ("left", "right", "tie")
EDITORIAL_STATUSES = ("submitted", "need_info", "qualified", "rejected")
_TASK_ID = re.compile(r"pilot_[a-z0-9_]+_[0-9]{3}")


class PilotValidationError(ValueError):
    """Pilot 输入不完整、不安全或不可复现。"""


def _text(value: Any, name: str, *, required: bool = False) -> str:
    if not isinstance(value, str):
        raise PilotValidationError(f"{name} 必须是字符串")
    cleaned = value.strip()
    if required and not cleaned:
        raise PilotValidationError(f"{name} 不能为空")
    return cleaned


def _texts(value: Any, name: str, *, minimum: int = 0) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise PilotValidationError(f"{name} 必须是字符串数组")
    result = tuple(_text(item, name, required=True) for item in value)
    if len(result) < minimum:
        raise PilotValidationError(f"{name} 至少需要 {minimum} 项")
    if len(set(result)) != len(result):
        raise PilotValidationError(f"{name} 不能包含重复项")
    return result


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PilotValidationError(f"{name} 必须是对象")
    return value


def _strict_keys(
    data: Mapping[str, Any], required: set[str], optional: set[str] | None = None
) -> None:
    optional = optional or set()
    missing = required.difference(data)
    unknown = set(data).difference(required | optional)
    if missing:
        raise PilotValidationError(f"缺少字段：{', '.join(sorted(missing))}")
    if unknown:
        raise PilotValidationError(f"包含未知字段：{', '.join(sorted(unknown))}")


def _optional_float(value: Any, name: str) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise PilotValidationError(f"{name} 必须是非负数字或留空") from exc
    if number < 0:
        raise PilotValidationError(f"{name} 不能为负数")
    return number


def _optional_int(value: Any, name: str) -> int | None:
    if value in (None, ""):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise PilotValidationError(f"{name} 必须是整数或留空") from exc
    if number < 0:
        raise PilotValidationError(f"{name} 不能为负数")
    return number


def _optional_bool(value: Any, name: str) -> bool | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().casefold()
    if normalized in {"true", "1", "yes", "y", "是"}:
        return True
    if normalized in {"false", "0", "no", "n", "否"}:
        return False
    raise PilotValidationError(f"{name} 必须是 true/false 或留空")


@dataclass(frozen=True)
class PilotTask:
    id: str
    theme: str
    request: str
    context: Mapping[str, Any]
    must_address: tuple[str, ...]
    forbidden_claims: tuple[str, ...]
    risk_checks: tuple[str, ...]

    def __post_init__(self) -> None:
        if not _TASK_ID.fullmatch(self.id):
            raise PilotValidationError(f"非法 Task ID：{self.id!r}")
        if self.theme not in THEMES:
            raise PilotValidationError(f"未知主题：{self.theme!r}")
        object.__setattr__(self, "request", _text(self.request, "request", required=True))
        object.__setattr__(self, "context", dict(_mapping(self.context, "context")))
        object.__setattr__(
            self, "must_address", _texts(self.must_address, "must_address", minimum=2)
        )
        object.__setattr__(
            self,
            "forbidden_claims",
            _texts(self.forbidden_claims, "forbidden_claims", minimum=1),
        )
        object.__setattr__(
            self, "risk_checks", _texts(self.risk_checks, "risk_checks", minimum=1)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "theme": self.theme,
            "request": self.request,
            "context": dict(self.context),
            "must_address": list(self.must_address),
            "forbidden_claims": list(self.forbidden_claims),
            "risk_checks": list(self.risk_checks),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PilotTask":
        fields = {
            "id",
            "theme",
            "request",
            "context",
            "must_address",
            "forbidden_claims",
            "risk_checks",
        }
        _strict_keys(data, fields)
        return cls(
            id=str(data["id"]),
            theme=str(data["theme"]),
            request=str(data["request"]),
            context=_mapping(data["context"], "context"),
            must_address=_texts(data["must_address"], "must_address"),
            forbidden_claims=_texts(data["forbidden_claims"], "forbidden_claims"),
            risk_checks=_texts(data["risk_checks"], "risk_checks"),
        )


@dataclass(frozen=True)
class GenerationManifest:
    run_id: str
    model_name: str
    host: str
    generated_at: str
    task_hash: str
    atom_corpus_hash: str
    prompt_template_hash: str
    temperature: str
    max_output: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id, "run_id", required=True))
        for name in ("model_name", "host", "temperature"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        if self.generated_at:
            try:
                datetime.fromisoformat(self.generated_at.replace("Z", "+00:00"))
            except ValueError as exc:
                raise PilotValidationError("generated_at 必须是 ISO-8601") from exc
        for name in ("task_hash", "atom_corpus_hash", "prompt_template_hash"):
            value = _text(getattr(self, name), name, required=True)
            if not re.fullmatch(r"[0-9a-f]{64}", value):
                raise PilotValidationError(f"{name} 必须是 SHA-256")
        if not isinstance(self.max_output, int) or self.max_output < 0:
            raise PilotValidationError("max_output 必须是非负整数")

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "model_name": self.model_name or "未记录",
            "host": self.host or "未记录",
            "generated_at": self.generated_at or "未记录",
            "task_hash": self.task_hash,
            "atom_corpus_hash": self.atom_corpus_hash,
            "prompt_template_hash": self.prompt_template_hash,
            "temperature": self.temperature or "未记录",
            "max_output": self.max_output,
        }


@dataclass(frozen=True)
class BlindRating:
    reviewer_id: str
    task_id: str
    left_scores: Mapping[str, int]
    right_scores: Mapping[str, int]
    preference: str
    reason: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "reviewer_id", _text(self.reviewer_id, "reviewer_id", required=True)
        )
        if not _TASK_ID.fullmatch(self.task_id):
            raise PilotValidationError(f"非法评分 Task ID：{self.task_id!r}")
        if self.preference not in PREFERENCES:
            raise PilotValidationError("preference 只能是 left / right / tie")
        for side, scores in (("left", self.left_scores), ("right", self.right_scores)):
            if set(scores) != set(SCORE_DIMENSIONS):
                raise PilotValidationError(f"{side}_scores 必须完整覆盖全部评分维度")
            if any(not isinstance(value, int) or not 1 <= value <= 5 for value in scores.values()):
                raise PilotValidationError("评分只能为 1—5 的整数")
        object.__setattr__(self, "left_scores", dict(self.left_scores))
        object.__setattr__(self, "right_scores", dict(self.right_scores))
        object.__setattr__(self, "reason", _text(self.reason, "reason", required=True))


@dataclass(frozen=True)
class EditorialLog:
    submission_id: str
    status: str
    first_read_minutes: float | None
    followup_minutes: float | None
    atom_drafting_minutes: float | None
    privacy_minutes: float | None
    confirmation_minutes: float | None
    finalization_minutes: float | None
    followup_count: int | None
    draft_atom_count: int | None
    confirmed_atom_count: int | None
    case_card_delivered: bool | None
    would_contribute_again: bool | None
    value_exchange_score: int | None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "submission_id", _text(self.submission_id, "submission_id", required=True)
        )
        if self.status not in EDITORIAL_STATUSES:
            raise PilotValidationError(f"未知审核状态：{self.status!r}")
        if self.value_exchange_score is not None and not 1 <= self.value_exchange_score <= 5:
            raise PilotValidationError("value_exchange_score 只能为 1—5")

    @property
    def total_minutes(self) -> float | None:
        values = (
            self.first_read_minutes,
            self.followup_minutes,
            self.atom_drafting_minutes,
            self.privacy_minutes,
            self.confirmation_minutes,
            self.finalization_minutes,
        )
        if any(value is None for value in values):
            return None
        return sum(value for value in values if value is not None)

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "EditorialLog":
        status = _text(row.get("status", ""), "status", required=True).casefold().replace(" ", "_")
        return cls(
            submission_id=_text(row.get("submission_id", ""), "submission_id", required=True),
            status=status,
            first_read_minutes=_optional_float(row.get("first_read_minutes"), "first_read_minutes"),
            followup_minutes=_optional_float(row.get("followup_minutes"), "followup_minutes"),
            atom_drafting_minutes=_optional_float(row.get("atom_drafting_minutes"), "atom_drafting_minutes"),
            privacy_minutes=_optional_float(row.get("privacy_minutes"), "privacy_minutes"),
            confirmation_minutes=_optional_float(row.get("confirmation_minutes"), "confirmation_minutes"),
            finalization_minutes=_optional_float(row.get("finalization_minutes"), "finalization_minutes"),
            followup_count=_optional_int(row.get("followup_count"), "followup_count"),
            draft_atom_count=_optional_int(row.get("draft_atom_count"), "draft_atom_count"),
            confirmed_atom_count=_optional_int(row.get("confirmed_atom_count"), "confirmed_atom_count"),
            case_card_delivered=_optional_bool(row.get("case_card_delivered"), "case_card_delivered"),
            would_contribute_again=_optional_bool(row.get("would_contribute_again"), "would_contribute_again"),
            value_exchange_score=_optional_int(row.get("value_exchange_score"), "value_exchange_score"),
        )


def canonical_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
