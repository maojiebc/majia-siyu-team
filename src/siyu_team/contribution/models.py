"""同行贡献的纯领域模型。

模型显式分离用户事实、模型推断和已有知识；完整聊天永不进入 payload。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json
import re
from typing import Any, Mapping, Sequence
from uuid import uuid4


MAX_FIELD_LENGTH = 4_000
_HASH = re.compile(r"[0-9a-f]{64}")


class ContributionValidationError(ValueError):
    """贡献对象违反授权、来源或隐私边界。"""


class ContributionSignal(str, Enum):
    FIRSTHAND_CASE = "firsthand_case"
    USER_CORRECTION = "user_correction"
    EXECUTION_FEEDBACK = "execution_feedback"
    COUNTEREXAMPLE = "counterexample"


class AuthorizationScope(str, Enum):
    NAMED_PUBLIC = "named_public"
    ANONYMOUS_PUBLIC = "anonymous_public"
    INTERNAL_ONLY = "internal_only"
    CONTACT_BEFORE_USE = "contact_before_use"


def _text(value: Any, name: str, *, required: bool = False) -> str:
    if not isinstance(value, str):
        raise ContributionValidationError(f"{name} 必须是字符串")
    cleaned = value.strip()
    if required and not cleaned:
        raise ContributionValidationError(f"{name} 不能为空")
    if len(cleaned) > MAX_FIELD_LENGTH:
        raise ContributionValidationError(f"{name} 超过 {MAX_FIELD_LENGTH} 字符")
    return cleaned


def _texts(value: Any, name: str) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ContributionValidationError(f"{name} 必须是字符串数组")
    result = tuple(_text(item, name, required=True) for item in value)
    if len(set(result)) != len(result):
        raise ContributionValidationError(f"{name} 不能包含重复项")
    return result


def _iso_datetime(value: str, name: str) -> str:
    cleaned = _text(value, name, required=True)
    try:
        parsed = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContributionValidationError(f"{name} 必须是 ISO 8601 时间") from exc
    if parsed.tzinfo is None:
        raise ContributionValidationError(f"{name} 必须包含时区")
    return cleaned


@dataclass(frozen=True)
class ContributionPromptState:
    """单次对话的纯状态；由上层持久化，不在此模块读写会话。"""

    primary_answer_delivered: bool = False
    prompt_shown: bool = False
    user_declined: bool = False

    def __post_init__(self) -> None:
        for name in ("primary_answer_delivered", "prompt_shown", "user_declined"):
            if not isinstance(getattr(self, name), bool):
                raise ContributionValidationError(f"{name} 必须是布尔值")

    @property
    def can_prompt(self) -> bool:
        return (
            self.primary_answer_delivered
            and not self.prompt_shown
            and not self.user_declined
        )

    def mark_prompted(self) -> "ContributionPromptState":
        if not self.can_prompt:
            raise ContributionValidationError("当前会话状态不允许再次提示贡献")
        return ContributionPromptState(True, True, False)

    def decline(self) -> "ContributionPromptState":
        return ContributionPromptState(self.primary_answer_delivered, self.prompt_shown, True)


@dataclass(frozen=True)
class ContributionCandidate:
    signal: ContributionSignal
    user_facts: tuple[str, ...]
    summary: str
    scene: str = ""
    actions: tuple[str, ...] = ()
    result: str = ""
    boundaries: tuple[str, ...] = ()
    model_inferences: tuple[str, ...] = ()
    existing_knowledge: tuple[str, ...] = ()
    topic_id: str = ""
    candidate_id: str = field(default_factory=lambda: f"candidate_{uuid4().hex}")
    include_full_chat: bool = field(default=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.signal, ContributionSignal):
            raise ContributionValidationError("signal 必须是 ContributionSignal")
        if not re.fullmatch(r"candidate_[0-9a-f]{32}", self.candidate_id):
            raise ContributionValidationError("candidate_id 格式非法")
        for name in (
            "user_facts", "actions", "boundaries", "model_inferences", "existing_knowledge"
        ):
            object.__setattr__(self, name, _texts(getattr(self, name), name))
        for name in ("summary", "scene", "result", "topic_id"):
            object.__setattr__(
                self, name, _text(getattr(self, name), name, required=name == "summary")
            )
        if not self.user_facts:
            raise ContributionValidationError("候选贡献必须包含至少一条用户明确提供的事实")
        if self.include_full_chat is not False:
            raise ContributionValidationError("include_full_chat 永远必须为 false")

    def submission_content(self) -> dict[str, Any]:
        """只返回用户事实层；模型推断和既有知识不进入提交内容。"""
        return {
            "candidate_id": self.candidate_id,
            "topic_id": self.topic_id,
            "contribution_type": self.signal.value,
            "summary": self.summary,
            "scene": self.scene,
            "user_facts": list(self.user_facts),
            "actions": list(self.actions),
            "result": self.result,
            "boundaries": list(self.boundaries),
            "include_full_chat": False,
        }


@dataclass(frozen=True)
class ContributionPreview:
    candidate: ContributionCandidate
    safe: bool
    warnings: tuple[str, ...]
    redacted_fields: tuple[str, ...]
    preview_hash: str
    include_full_chat: bool = field(default=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.candidate, ContributionCandidate):
            raise ContributionValidationError("candidate 类型非法")
        if not isinstance(self.safe, bool):
            raise ContributionValidationError("safe 必须是布尔值")
        object.__setattr__(self, "warnings", _texts(self.warnings, "warnings"))
        object.__setattr__(
            self, "redacted_fields", _texts(self.redacted_fields, "redacted_fields")
        )
        if not _HASH.fullmatch(self.preview_hash):
            raise ContributionValidationError("preview_hash 必须是 SHA-256")
        if self.include_full_chat is not False:
            raise ContributionValidationError("include_full_chat 永远必须为 false")

    def to_dict(self) -> dict[str, Any]:
        return {
            "safe": self.safe,
            "warnings": list(self.warnings),
            "redacted_fields": list(self.redacted_fields),
            "preview_hash": self.preview_hash,
            "candidate": self.candidate.submission_content(),
            "provenance": {
                "user_facts": list(self.candidate.user_facts),
                "model_inferences": list(self.candidate.model_inferences),
                "existing_knowledge": list(self.candidate.existing_knowledge),
            },
            "include_full_chat": False,
        }


@dataclass(frozen=True)
class ContributionAuthorization:
    scope: AuthorizationScope
    confirmed: bool = False
    confirmed_at: str = ""
    display_name: str = ""
    contact: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.scope, AuthorizationScope):
            raise ContributionValidationError("scope 必须是 AuthorizationScope")
        if not isinstance(self.confirmed, bool):
            raise ContributionValidationError("confirmed 必须是布尔值")
        object.__setattr__(self, "display_name", _text(self.display_name, "display_name"))
        object.__setattr__(self, "contact", _text(self.contact, "contact"))
        if self.confirmed:
            object.__setattr__(
                self, "confirmed_at", _iso_datetime(self.confirmed_at, "confirmed_at")
            )
        elif self.confirmed_at:
            raise ContributionValidationError("未确认时不能设置 confirmed_at")
        if self.scope is AuthorizationScope.NAMED_PUBLIC and not self.display_name:
            raise ContributionValidationError("署名公开必须提供 display_name")
        if self.scope is AuthorizationScope.CONTACT_BEFORE_USE and not self.contact:
            raise ContributionValidationError("使用前确认必须提供 contact")

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope": self.scope.value,
            "confirmed": self.confirmed,
            "confirmed_at": self.confirmed_at,
            "display_name": self.display_name,
            "contact": self.contact,
        }


@dataclass(frozen=True)
class ContributionSubmission:
    preview: ContributionPreview
    authorization: ContributionAuthorization
    idempotency_key: str
    submission_id: str = field(default_factory=lambda: f"local_{uuid4().hex}")
    include_full_chat: bool = field(default=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.preview, ContributionPreview):
            raise ContributionValidationError("preview 类型非法")
        if not isinstance(self.authorization, ContributionAuthorization):
            raise ContributionValidationError("authorization 类型非法")
        if not self.preview.safe:
            raise ContributionValidationError("未通过安全扫描的预览不能形成提交")
        if not self.authorization.confirmed:
            raise ContributionValidationError("必须获得用户明确确认后才能形成提交")
        object.__setattr__(
            self, "idempotency_key", _text(self.idempotency_key, "idempotency_key", required=True)
        )
        if self.include_full_chat is not False:
            raise ContributionValidationError("include_full_chat 永远必须为 false")

    def to_payload(self) -> Mapping[str, Any]:
        return {
            "client_submission_id": self.submission_id,
            "preview_hash": self.preview.preview_hash,
            "authorization": self.authorization.to_dict(),
            "case": self.preview.candidate.submission_content(),
            "idempotency_key": self.idempotency_key,
            "include_full_chat": False,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_payload(), ensure_ascii=False, sort_keys=True)
