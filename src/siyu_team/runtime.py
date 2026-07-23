"""私域任务 Runtime：解析 → 路由 → 上下文隔离 → 追踪。

Runtime 只制定可验证的执行计划，不直接调用模型，也不替 Skill 生成内容。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .context import AgentContext, build_agent_context
from .routing import RouteDecision, route_task
from .task import Task, TaskKind, parse_task
from .tracing import TraceRecorder


PANEL_OFFICERS = ("公关官", "产品官", "广告官", "合规官")


@dataclass(frozen=True)
class ExecutionPlan:
    trace_id: str
    task: Task
    decision: RouteDecision
    agent_contexts: tuple[AgentContext, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "task": self.task.to_dict(),
            "decision": self.decision.to_dict(),
            "agent_contexts": [
                context.to_dict() for context in self.agent_contexts
            ],
        }


class SiyuRuntime:
    def __init__(self, trace_recorder: TraceRecorder | None = None) -> None:
        self.trace_recorder = trace_recorder or TraceRecorder()

    def plan(
        self,
        request: str,
        hints: Mapping[str, Any] | None = None,
        *,
        trace: bool = True,
    ) -> ExecutionPlan:
        task = parse_task(request, hints)
        decision = route_task(task)
        trace_id = self.trace_recorder.new_trace_id()

        contexts: tuple[AgentContext, ...] = ()
        if (
            task.kind is TaskKind.STRATEGY_REVIEW
            and not decision.needs_clarification
        ):
            contexts = tuple(
                build_agent_context(task, officer) for officer in PANEL_OFFICERS
            )

        plan = ExecutionPlan(
            trace_id=trace_id,
            task=task,
            decision=decision,
            agent_contexts=contexts,
        )
        if trace:
            self.trace_recorder.emit(
                trace_id, task.task_id, "task.created", task.to_dict()
            )
            self.trace_recorder.emit(
                trace_id, task.task_id, "task.routed", decision.to_dict()
            )
            if contexts:
                self.trace_recorder.emit(
                    trace_id,
                    task.task_id,
                    "contexts.created",
                    {
                        "officers": [context.officer for context in contexts],
                        "field_names": {
                            context.officer: sorted(context.fields)
                            for context in contexts
                        },
                    },
                )
        return plan
