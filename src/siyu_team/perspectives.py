"""四官独立采样 prompt 工厂。仿 heavy.build_perspective_prompt：
每个官只用自己那一个『引擎视角』分析，互不可见、不提及其他官。
"""
from __future__ import annotations

import json

from .context import AgentContext

_TEMPLATE = """你是私域专家团的{name}，你的方法论引擎是『{engine}』。
只用『{engine}』这一个视角独立分析本案，不要提及、不要假设其他官会说什么。

## 客户背景
{intake}

## 路由结论
{routing}

## 你的视角定义
{description}

## Deliverables（严格按此结构输出，给可落地细节，不要泛泛而谈）
1. 现状盘点（你这个视角下，客户私域现在什么样）
2. 核心问题（你这个视角看到的最要命的 1-2 个问题）
3. 可落地动作（每条写：触发人群 / 话术或物料 / 时间点 / 责任人 / 可埋点指标）
4. 最脆弱的前提（你的方案最可能在哪一步崩）
5. 合规风险提示（涉及企微规则/广告法的地方先自查）
"""


def build_officer_prompt(officer: dict, intake: str, routing: str) -> str:
    return _TEMPLATE.format(
        name=officer.get("name", "专家"),
        engine=officer.get("engine", ""),
        description=officer.get("description", ""),
        intake=intake, routing=routing,
    )


def build_isolated_officer_prompt(
    officer: dict,
    context: AgentContext,
    routing: str,
) -> str:
    """使用 Runtime 白名单上下文构造 prompt，不接受未过滤的 intake。"""
    expected_name = officer.get("name", "专家")
    if expected_name != context.officer:
        raise ValueError(
            f"角色与上下文不一致：{expected_name!r} != {context.officer!r}"
        )
    intake = json.dumps(
        dict(context.fields),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    return build_officer_prompt(officer, intake, routing)
