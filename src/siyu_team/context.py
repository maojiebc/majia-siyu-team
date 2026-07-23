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


@dataclass(frozen=True)
class AgentContext:
    officer: str
    fields: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"officer": self.officer, "fields": dict(self.fields)}


def build_agent_context(task: Task, officer: str) -> AgentContext:
    if officer not in OFFICER_ALLOWED_CONTEXT:
        raise ValueError(f"未知角色：{officer}")

    base = task.to_dict()
    fields = {key: redact(base[key], key) for key in _COMMON_FIELDS}
    for key in OFFICER_ALLOWED_CONTEXT[officer]:
        if key in task.context:
            fields[key] = redact(task.context[key], key)

    # 只有合规官可以读取原始请求，便于识别敏感收集、群发与承诺风险。
    if officer == "合规官":
        fields["source_text"] = redact(task.source_text)
        fields["risk"] = task.risk.value
        fields["need_compliance_check"] = task.need_compliance_check
    return AgentContext(officer=officer, fields=fields)
