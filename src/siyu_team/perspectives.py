"""四位专家独立采样 prompt 工厂。
每位专家只用自己那一个视角分析，互不可见、不提及其他专家。
"""
from __future__ import annotations

import json

from .context import AgentContext

_TEMPLATE = """你是私域专家团的{name}，你的方法论引擎是『{engine}』。
只用『{engine}』这一个视角独立分析本案，不要提及、不要假设其他专家会说什么。
写给客户的话要说人话，少用黑话。

## 客户背景
{intake}

## 路由结论
{routing}

## 你的视角定义
{description}
{growth_block}
## Deliverables（严格按此结构输出，给可落地细节，不要泛泛而谈）
1. 现状盘点（你这个视角下，客户私域现在什么样）
2. 核心问题（你这个视角看到的最要命的 1-2 个问题）
3. 可落地动作（每条写：触发人群 / 话术或物料 / 时间点 / 责任人 / 可埋点指标）
4. 最脆弱的前提（你的方案最可能在哪一步崩）
5. 合规风险提示（涉及企微规则/广告法的地方先自查）
"""


def _growth_block_from_fields(fields: dict) -> str:
    atoms = fields.get("growth_atoms")
    note = fields.get("growth_load_note") or ""
    if not atoms:
        return ""
    lines = ["## 增长参考（按业态加载，可引用 locator）"]
    if note:
        lines.append(str(note))
    lines.append("下列是精简判断句，用来对齐增长结构；不要整段复读，要落到本案动作。")
    for row in atoms:
        if not isinstance(row, dict):
            continue
        locator = row.get("locator", "")
        layer = row.get("layer", "")
        statement = row.get("statement", "")
        lines.append(f"- [{locator}|{layer}] {statement}")
    return "\n".join(lines) + "\n"


def build_officer_prompt(officer: dict, intake: str, routing: str, growth_block: str = "") -> str:
    block = f"\n{growth_block}\n" if growth_block else "\n"
    return _TEMPLATE.format(
        name=officer.get("name", "专家"),
        engine=officer.get("engine", ""),
        description=officer.get("description", ""),
        intake=intake,
        routing=routing,
        growth_block=block,
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
    fields = dict(context.fields)
    growth_block = _growth_block_from_fields(fields)
    # 不把大块 atoms 再塞进 intake JSON，避免重复；只留 note + refs
    slim = {
        key: value
        for key, value in fields.items()
        if key not in {"growth_atoms"}
    }
    intake = json.dumps(
        slim,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    return build_officer_prompt(officer, intake, routing, growth_block=growth_block)
