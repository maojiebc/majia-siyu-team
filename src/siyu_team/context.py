"""代码级角色上下文隔离。

每位官只能拿到白名单字段。Prompt 负责表达角色，字段边界由这里强制执行。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .security import (
    MAX_CONTEXT_CHARS,
    ContentTooLargeError,
    ContextIncompleteError,
    json_size,
)
from .task import Task
from .tracing import redact


OFFICER_ALLOWED_CONTEXT: dict[str, frozenset[str]] = {
    "公关官": frozenset({"brand", "reputation", "customer_feedback"}),
    "产品官": frozenset({"offer", "content_assets", "customer_needs"}),
    "广告官": frozenset({"offer", "budget", "metrics", "funnel"}),
    "合规官": frozenset({"offer", "data_collection", "distribution_method", "consent"}),
}


@dataclass(frozen=True)
class OfficerContextPolicy:
    """单个专家可见字段、最小充分信息与总大小上限。"""

    allowed_fields: frozenset[str]
    required_any_of: frozenset[str]
    max_size: int = MAX_CONTEXT_CHARS


OFFICER_CONTEXT_POLICIES: dict[str, OfficerContextPolicy] = {
    "公关官": OfficerContextPolicy(
        allowed_fields=OFFICER_ALLOWED_CONTEXT["公关官"],
        required_any_of=frozenset(
            {"brand", "reputation", "customer_feedback"}
        ),
    ),
    "产品官": OfficerContextPolicy(
        allowed_fields=OFFICER_ALLOWED_CONTEXT["产品官"],
        required_any_of=frozenset(
            {"offer", "content_assets", "customer_needs"}
        ),
    ),
    "广告官": OfficerContextPolicy(
        allowed_fields=OFFICER_ALLOWED_CONTEXT["广告官"],
        required_any_of=frozenset(
            {"offer", "budget", "metrics", "funnel"}
        ),
    ),
    "合规官": OfficerContextPolicy(
        allowed_fields=OFFICER_ALLOWED_CONTEXT["合规官"],
        required_any_of=frozenset(
            {
                "source_text",
                "offer",
                "data_collection",
                "distribution_method",
                "consent",
            }
        ),
    ),
}

_COMMON_FIELDS = frozenset(
    {
        "task_id",
        "kind",
        "goal",
        "industry",
        "stage",
        "client",
        "audience",
        "constraints",
    }
)

# 增长/方法类共享字段：所有官可见（非客户隐私）
_SHARED_KNOWLEDGE_FIELDS = frozenset(
    {
        "growth_atoms",
        "growth_load_note",
        "knowledge_refs",
    }
)


@dataclass(frozen=True)
class AgentContext:
    officer: str
    fields: Mapping[str, Any]
    required_any_of: frozenset[str] = frozenset()
    max_size: int = MAX_CONTEXT_CHARS

    def to_dict(self) -> dict[str, Any]:
        return {"officer": self.officer, "fields": dict(self.fields)}

    @property
    def present_required_fields(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                key
                for key in self.required_any_of
                if key in self.fields and _has_meaningful_value(self.fields[key])
            )
        )

    @property
    def is_sufficient(self) -> bool:
        return bool(self.present_required_fields)

    def assert_dispatchable(self) -> None:
        """在真正派发给专家前执行 fail-closed 校验。"""
        if not self.is_sufficient:
            raise ContextIncompleteError(
                self.officer, tuple(sorted(self.required_any_of))
            )
        size = json_size(self.fields)
        if size > self.max_size:
            raise ContentTooLargeError(
                f"{self.officer} context 超过大小上限：{size} > {self.max_size} 字符"
            )


def _has_meaningful_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (Mapping, list, tuple, set, frozenset)):
        return bool(value)
    return True


def build_agent_context(
    task: Task,
    officer: str,
    *,
    shared_fields: Mapping[str, Any] | None = None,
    allowed_context: frozenset[str] | None = None,
    required_any_of: frozenset[str] | None = None,
    max_size: int | None = None,
) -> AgentContext:
    """构建单官上下文。

    ``allowed_context`` 供 roster 自定义官传入专属字段白名单；
    不传时回落内置四官白名单。既非内置官又没给白名单 → 拒绝
    （fail-closed：自定义官必须显式声明能看什么，不默认放行）。
    """
    policy = OFFICER_CONTEXT_POLICIES.get(officer)
    if allowed_context is None:
        if policy is None:
            raise ValueError(
                f"未知角色：{officer}（自定义官请在 roster 条目里提供 allowed_context 白名单）"
            )
        allowed_context = policy.allowed_fields

    if required_any_of is None:
        if policy is not None:
            required_any_of = policy.required_any_of
        else:
            # 自定义官至少要收到一个自己声明可见的业务字段。公开知识只能
            # 辅助分析，不能冒充本客户的最小充分信息。
            required_any_of = allowed_context
    effective_max_size = (
        max_size
        if max_size is not None
        else (policy.max_size if policy else MAX_CONTEXT_CHARS)
    )
    if effective_max_size <= 0:
        raise ValueError("max_size 必须大于 0")

    base = task.to_dict()
    fields = {key: redact(base[key], key) for key in _COMMON_FIELDS}
    for key in allowed_context:
        if key in task.context:
            fields[key] = redact(task.context[key], key)

    # 只有合规官可以读取原始请求，便于识别敏感收集、群发与承诺风险。
    if officer == "合规官":
        fields["source_text"] = redact(task.source_text)
        fields["risk"] = task.risk.value
        fields["need_compliance_check"] = task.need_compliance_check

    if shared_fields:
        for key, value in shared_fields.items():
            if key not in _SHARED_KNOWLEDGE_FIELDS:
                raise ValueError(f"不允许的共享字段：{key}")
            fields[key] = redact(value, key)

    return AgentContext(
        officer=officer,
        fields=fields,
        required_any_of=required_any_of,
        max_size=effective_max_size,
    )
