"""结构化任务路由。

``route(industry, stage)`` 保留旧接口；新 Runtime 只通过 ``route_task(Task)``
做任务级路由，避免 Skill 直接吞自然语言。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .task import Task, TaskKind


INDUSTRIES = {"catering": "餐饮", "retail": "零售", "edu": "教培"}
STAGES = {
    "cold": "冷启动（0 起步 / 有微信没体系）",
    "growth": "扩张（有体系要提效）",
    "mature": "成熟（要规模化裂变）",
}

STAGE_FOCUS = {
    "cold": "先解决『加得上人 + 加进来不流失』：钩子、承接、第一周 SOP。",
    "growth": "先解决『分层提效 + 复购』：标签体系、自动化 SOP、复购召回。",
    "mature": "先解决『规模化裂变 + 会员体系』：合规裂变机制、会员等级、案例复制。",
}

TASK_ROUTES: dict[TaskKind, tuple[str, str]] = {
    TaskKind.MOMENTS_COPY: (
        "/siyu-pyq",
        "请求的是朋友圈内容生产，走执行层并做生成前合规检查。",
    ),
    TaskKind.GROUP_CAMPAIGN: (
        "/siyu-qunfa",
        "请求的是群发或社群推送，走栏目与承接脚本执行层。",
    ),
    TaskKind.CONVERSATION_SCRIPT: (
        "/siyu-huashu",
        "请求的是欢迎、破冰或答疑话术，走一对一承接执行层。",
    ),
    TaskKind.DIAGNOSIS: (
        "siyu-wenzhen",
        "请求包含结果异常或因果疑问，先验证问题是否成立。",
    ),
    TaskKind.STRATEGY_REVIEW: (
        "siyu-onboard",
        "请求涉及整盘结构，进入四官独立评审和团长收口。",
    ),
    TaskKind.SAVE_MEMORY: (
        "/siyu-save",
        "请求是保存当前结论，进入本地客户档案。",
    ),
    TaskKind.RESTORE_MEMORY: (
        "/siyu-restore",
        "请求是恢复上次结论，读取本地客户档案。",
    ),
    TaskKind.REPORT: (
        "/siyu-report",
        "请求是汇总交付物，进入报告生成与合规扫描。",
    ),
    TaskKind.UNKNOWN: (
        "/siyu",
        "当前信息不足以安全选择执行能力，由入口只补问一个关键问题。",
    ),
}


@dataclass(frozen=True)
class RouteDecision:
    skill: str
    reason: str
    needs_clarification: bool
    required_fields: tuple[str, ...]
    industry_book: str | None
    focus: str
    knowledge_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill": self.skill,
            "reason": self.reason,
            "needs_clarification": self.needs_clarification,
            "required_fields": list(self.required_fields),
            "industry_book": self.industry_book,
            "focus": self.focus,
            "knowledge_refs": list(self.knowledge_refs),
        }


def route(industry: str, stage: str) -> dict[str, Any]:
    """旧版行业×阶段接口，供现有 orchestrator/Skill 继续使用。"""
    normalized_industry = industry if industry in INDUSTRIES else ""
    normalized_stage = stage if stage in STAGES else ""
    book = (
        f"knowledge/02-industry/{normalized_industry}/"
        if normalized_industry
        else None
    )
    return {
        "industry": normalized_industry,
        "industry_cn": INDUSTRIES.get(
            normalized_industry, "未定，需 Step 0 补问"
        ),
        "stage": normalized_stage,
        "stage_cn": STAGES.get(normalized_stage, "未定，需 Step 0 补问"),
        "industry_book": book,
        "focus": STAGE_FOCUS.get(
            normalized_stage, "Step 0 调研补齐阶段后再定重点。"
        ),
    }


def route_task(task: Task) -> RouteDecision:
    skill, reason = TASK_ROUTES[task.kind]
    industry_route = route(task.industry, task.stage)
    required: list[str] = []
    if task.kind is TaskKind.UNKNOWN:
        required.append("kind")
    if task.kind is TaskKind.STRATEGY_REVIEW:
        if not industry_route["industry"]:
            required.append("industry")
        if not industry_route["stage"]:
            required.append("stage")

    knowledge_refs = [
        "knowledge/01-wechat-official/compliance/redlines.md",
        "knowledge/00-methodology/私域公理与消解案例库.md",
    ]
    industry_book = industry_route["industry_book"]
    if industry_book:
        knowledge_refs.append(industry_book)

    return RouteDecision(
        skill=skill,
        reason=reason,
        needs_clarification=bool(required),
        required_fields=tuple(required),
        industry_book=industry_book,
        focus=industry_route["focus"],
        knowledge_refs=tuple(knowledge_refs),
    )
