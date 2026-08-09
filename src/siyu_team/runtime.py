"""私域任务 Runtime：解析 → 路由 → 上下文隔离 → 追踪。

Runtime 只制定可验证的执行计划，不直接调用模型，也不替 Skill 生成内容。
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from typing import Any, Mapping

from .context import AgentContext, build_agent_context
from .knowledge.growth_layers import format_growth_atoms_for_context
from .roster import MAX_OFFICERS, load_roster, normalize_officers
from .routing import RouteDecision, route_task
from .task import Task, TaskKind, parse_task
from .tracing import TraceRecorder


# 内置四官（roster 缺失/损坏时的回退名单；正常路径从 roster 读取）。
PANEL_OFFICERS = ("公关官", "产品官", "广告官", "合规官")
PLAN_SCHEMA_VERSION = "1.0"
LEGACY_CORPUS_VERSION = "0.3.0"


class RuntimeMode(str, Enum):
    PYTHON = "python"
    PROMPT_ONLY = "prompt_only"

# 诊断与全盘诊断注入增长 draft 原子
_GROWTH_CONTEXT_KINDS = frozenset(
    {
        TaskKind.DIAGNOSIS,
        TaskKind.STRATEGY_REVIEW,
    }
)


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
        knowledge = dict(self.knowledge or _legacy_knowledge(self.growth_atoms))
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


def _legacy_knowledge(
    growth_atoms: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    """Expose legacy rows through the v1 envelope until PR-03 replaces loading."""
    atoms = [dict(row) for row in growth_atoms]
    canonical = json.dumps(
        atoms,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "corpus_version": LEGACY_CORPUS_VERSION,
        "corpus_hash": "sha256:" + hashlib.sha256(canonical).hexdigest(),
        "selection_count": len(atoms),
        "atoms": atoms,
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
    ) -> None:
        self.trace_recorder = trace_recorder or TraceRecorder()
        # 官名单来自 roster（默认 examples/roster.example.json 或内置四官）。
        self._panel = _panel_from_roster(roster if roster is not None else load_roster())
        # 增长原子内存缓存：key=归一化业态，生命周期与实例绑定，跨 plan 复用。
        self._atom_cache: dict[str, tuple[Any, ...]] = {}

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

        growth_atoms: tuple[dict[str, Any], ...] = ()
        growth_note = ""
        if task.kind in _GROWTH_CONTEXT_KINDS:
            growth_atoms, growth_note = format_growth_atoms_for_context(
                task.industry, cache=self._atom_cache
            )

        shared: dict[str, Any] | None = None
        if growth_atoms or growth_note:
            shared = {
                "growth_atoms": [dict(row) for row in growth_atoms],
                "growth_load_note": growth_note,
                "knowledge_refs": list(decision.knowledge_refs),
            }

        contexts: tuple[AgentContext, ...] = ()
        if (
            task.kind is TaskKind.STRATEGY_REVIEW
            and not decision.needs_clarification
        ):
            contexts = tuple(
                build_agent_context(
                    task, name, shared_fields=shared, allowed_context=allowed
                )
                for name, allowed in self._panel
            )

        plan = ExecutionPlan(
            trace_id=trace_id,
            task=task,
            decision=decision,
            knowledge=_legacy_knowledge(growth_atoms),
            warnings=(
                ("legacy_growth_selection_pending_strict_corpus",)
                if growth_atoms
                else ()
            ),
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
                self.trace_recorder.emit(
                    trace_id,
                    task.task_id,
                    "growth_atoms.attached",
                    {
                        "count": len(growth_atoms),
                        "note": growth_note,
                        "locators": [row.get("locator") for row in growth_atoms[:20]],
                        "kind": task.kind.value,
                    },
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
