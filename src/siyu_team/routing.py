"""结构化任务路由。

``route(industry, stage)`` 保留旧接口；新 Runtime 只通过 ``route_task(Task)``
做任务级路由，避免 Skill 直接吞自然语言。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .task import Task, TaskKind
from .knowledge.growth_layers import describe_growth_load, select_growth_doc_refs
from .knowledge.paths import COMPLIANCE_REDLINES_DOC, METHODOLOGY_AXIOMS_DOC


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
    TaskKind.MARKET_RESEARCH: (
        "siyu-market-research",
        "请求涉及厂商、产品、价格或市场动态，先实时检索并生成证据快照。",
    ),
    TaskKind.DIAGNOSIS: (
        "siyu-wenzhen",
        "请求包含结果异常或因果疑问，先验证问题是否成立。",
    ),
    TaskKind.STRATEGY_REVIEW: (
        "siyu-onboard",
        "请求涉及整盘结构，进入四位专家分头评审和总协调收口。",
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

    knowledge_refs: list[str] = []
    if task.kind is not TaskKind.MARKET_RESEARCH:
        knowledge_refs.extend(
            [
                COMPLIANCE_REDLINES_DOC,
                METHODOLOGY_AXIOMS_DOC,
            ]
        )
        # 增长分层：未声明业态只 L0；catering/retail 叠加 L1
        knowledge_refs.extend(select_growth_doc_refs(task.industry))
    industry_book = (
        None
        if task.kind is TaskKind.MARKET_RESEARCH
        else industry_route["industry_book"]
    )
    if industry_book and task.kind is not TaskKind.MARKET_RESEARCH:
        # industry_book 是目录；L1 文档已在 select_growth_doc_refs 精确挂上
        if industry_book not in knowledge_refs:
            knowledge_refs.append(industry_book)

    focus = industry_route["focus"]
    if task.kind is TaskKind.MARKET_RESEARCH:
        focus = "先完成实时检索与证据快照；证据不足的对象不得进入正式推荐。"
    else:
        growth_note = describe_growth_load(task.industry)
        if focus:
            focus = f"{focus} {growth_note}"
        else:
            focus = growth_note

    return RouteDecision(
        skill=skill,
        reason=reason,
        needs_clarification=bool(required),
        required_fields=tuple(required),
        industry_book=industry_book,
        focus=focus,
        knowledge_refs=tuple(knowledge_refs),
    )
