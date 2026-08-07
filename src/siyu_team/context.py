"""代码级角色上下文隔离。

每位官只能拿到白名单字段。Prompt 负责表达角色，字段边界由这里强制执行。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .task import Task
from .tracing import redact


OFFICER_ALLOWED_CONTEXT: dict[str, frozenset[str]] = {
    "公关官": frozenset({"brand", "reputation", "customer_feedback"}),
    "产品官": frozenset({"offer", "content_assets", "customer_needs"}),
    "广告官": frozenset({"offer", "budget", "metrics", "funnel"}),
    "合规官": frozenset(
        {"offer", "data_collection", "distribution_method", "consent"}
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

    def to_dict(self) -> dict[str, Any]:
        return {"officer": self.officer, "fields": dict(self.fields)}


def build_agent_context(
    task: Task,
    officer: str,
    *,
    shared_fields: Mapping[str, Any] | None = None,
    allowed_context: frozenset[str] | None = None,
) -> AgentContext:
    """构建单官上下文。

    ``allowed_context`` 供 roster 自定义官传入专属字段白名单；
    不传时回落内置四官白名单。既非内置官又没给白名单 → 拒绝
    （fail-closed：自定义官必须显式声明能看什么，不默认放行）。
    """
    if allowed_context is None:
        builtin = OFFICER_ALLOWED_CONTEXT.get(officer)
        if builtin is None:
            raise ValueError(
                f"未知角色：{officer}（自定义官请在 roster 条目里提供 allowed_context 白名单）"
            )
        allowed_context = builtin

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

    return AgentContext(officer=officer, fields=fields)
