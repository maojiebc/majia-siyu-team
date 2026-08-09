"""私域任务 Runtime：解析 → 路由 → 上下文隔离 → 追踪。

Runtime 只制定可验证的执行计划，不直接调用模型，也不替 Skill 生成内容。
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Mapping

from .context import AgentContext, build_agent_context
from .knowledge.assembler import KnowledgeAssembler
from .knowledge.growth_layers import describe_growth_load
from .roster import MAX_OFFICERS, load_roster, normalize_officers
from .routing import RouteDecision, route_task
from .security import ContentTooLargeError, ContextIncompleteError
from .task import Task, TaskKind, parse_task
from .tracing import TraceRecorder


# 内置四官（roster 缺失/损坏时的回退名单；正常路径从 roster 读取）。
PANEL_OFFICERS = ("公关官", "产品官", "广告官", "合规官")
PLAN_SCHEMA_VERSION = "1.0"
EMPTY_CORPUS_HASH = (
    "sha256:e3b0c44298fc1c149afbf4c8996fb924"
    "27ae41e4649b934ca495991b7852b855"
)


class RuntimeMode(str, Enum):
    PYTHON = "python"
    PROMPT_ONLY = "prompt_only"

@dataclass(frozen=True)
class ExecutionPlan:
    trace_id: str
    task: Task
    decision: RouteDecision
    plan_schema_version: str = PLAN_SCHEMA_VERSION
    runtime_mode: RuntimeMode = RuntimeMode.PYTHON
    knowledge: Mapping[str, Any] | None = None
    warnings: tuple[str, ...] = ()
    agent_contexts: tuple[AgentContext, ...] = ()
    growth_atoms: tuple[dict[str, Any], ...] = ()
    growth_load_note: str = ""

    def to_dict(self) -> dict[str, Any]:
        knowledge = dict(
            self.knowledge
            or {
                "corpus_version": "unavailable",
                "corpus_hash": EMPTY_CORPUS_HASH,
                "selection_count": 0,
                "atoms": [],
            }
        )
        return {
            "plan_schema_version": self.plan_schema_version,
            "runtime_mode": self.runtime_mode.value,
            "trace_id": self.trace_id,
            "task": self.task.to_dict(),
            "decision": self.decision.to_dict(),
            "knowledge": knowledge,
            "warnings": list(self.warnings),
            "agent_contexts": [
                context.to_dict() for context in self.agent_contexts
            ],
            "growth_atoms": [dict(row) for row in self.growth_atoms],
            "growth_load_note": self.growth_load_note,
        }


def _panel_from_roster(roster: Mapping[str, Any]) -> tuple[tuple[str, frozenset[str] | None], ...]:
    """从 roster 提取 (官名, 自定义白名单) 面板；名单为空回落内置四官。

    这是「换角色不碰代码」的接线点：往 roster.json 加官即生效，
    自定义官需带 allowed_context（context.build_agent_context fail-closed）。
    """
    panel: list[tuple[str, frozenset[str] | None]] = []
    seen: set[str] = set()
    for officer in normalize_officers(roster.get("officers"), k=MAX_OFFICERS):
        if not isinstance(officer, Mapping):
            continue
        name = str(officer.get("name", "")).strip()
        if not name or name in seen:
            continue
        seen.add(name)
        allowed = officer.get("allowed_context")
        panel.append(
            (name, frozenset(str(key) for key in allowed) if allowed is not None else None)
        )
    if not panel:
        panel = [(name, None) for name in PANEL_OFFICERS]
    return tuple(panel)


class SiyuRuntime:
    def __init__(
        self,
        trace_recorder: TraceRecorder | None = None,
        roster: Mapping[str, Any] | None = None,
        knowledge_assembler: KnowledgeAssembler | None = None,
    ) -> None:
        self.trace_recorder = trace_recorder or TraceRecorder()
        # 官名单来自 roster（默认 examples/roster.example.json 或内置四官）。
        self._panel = _panel_from_roster(roster if roster is not None else load_roster())
        # Corpus 由 Assembler 在首次 plan 时严格加载并在实例内复用。
        # 选择结果不按业态缓存，因为它必须随任务与路由变化。
        self._knowledge_assembler = knowledge_assembler or KnowledgeAssembler()

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

        selection = self._knowledge_assembler.assemble(task, decision)
        growth_atoms = selection.context_rows()
        growth_note = ""
        if growth_atoms:
            growth_note = (
                f"{describe_growth_load(task.industry)}"
                f"（已按任务与路由相关性装配 "
                f"{selection.selection_count} 条）"
            )

        shared: dict[str, Any] | None = None
        if growth_atoms or growth_note:
            shared = {
                "growth_atoms": [dict(row) for row in growth_atoms],
                "growth_load_note": growth_note,
                "knowledge_refs": list(decision.knowledge_refs),
            }

        contexts: tuple[AgentContext, ...] = ()
        context_warnings: list[str] = []
        if (
            task.kind is TaskKind.STRATEGY_REVIEW
            and not decision.needs_clarification
        ):
            candidates = tuple(
                build_agent_context(
                    task, name, shared_fields=shared, allowed_context=allowed
                )
                for name, allowed in self._panel
            )
            blocked_fields: list[str] = []
            for context in candidates:
                try:
                    context.assert_dispatchable()
                except ContextIncompleteError as exc:
                    context_warnings.append(str(exc))
                    blocked_fields.append(f"context.{context.officer}")
                except ContentTooLargeError as exc:
                    context_warnings.append(
                        f"context_too_large: {context.officer}: {exc}"
                    )
                    blocked_fields.append(f"context.{context.officer}")
            if blocked_fields:
                # 四官面板必须作为一个完整评审单元运行。只派一部分会让 Host
                # 在缺失视角的情况下误以为已完成盲审，因此整组 fail-closed。
                required = tuple(
                    dict.fromkeys((*decision.required_fields, *blocked_fields))
                )
                decision = replace(
                    decision,
                    needs_clarification=True,
                    required_fields=required,
                    reason=(
                        decision.reason
                        + "（专家上下文不足，先补齐业务事实后再派发四官）"
                    ),
                )
            else:
                contexts = candidates

        plan = ExecutionPlan(
            trace_id=trace_id,
            task=task,
            decision=decision,
            knowledge=selection.to_dict(),
            warnings=tuple((*selection.warnings, *context_warnings)),
            agent_contexts=contexts,
            growth_atoms=growth_atoms,
            growth_load_note=growth_note,
        )
        if trace:
            self.trace_recorder.emit(
                trace_id, task.task_id, "task.created", task.to_dict()
            )
            self.trace_recorder.emit(
                trace_id, task.task_id, "task.routed", decision.to_dict()
            )
            if growth_atoms or growth_note:
                knowledge_payload = {
                    "corpus_version": selection.corpus_version,
                    "corpus_hash": selection.corpus_hash,
                    "count": selection.selection_count,
                    "atom_ids": [row.get("id") for row in growth_atoms[:20]],
                    "note": growth_note,
                    "locators": [row.get("locator") for row in growth_atoms[:20]],
                    "kind": task.kind.value,
                    "skill": decision.skill,
                }
                self.trace_recorder.emit(
                    trace_id,
                    task.task_id,
                    "knowledge.attached",
                    knowledge_payload,
                )
                # 保留旧事件名一个稳定版本，让现有 trace 消费方可平滑迁移。
                self.trace_recorder.emit(
                    trace_id,
                    task.task_id,
                    "growth_atoms.attached",
                    knowledge_payload,
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
