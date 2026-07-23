"""判官层：锚定 rubric 调 LLM 打分。【3档先留接口；4档接真实 LLM】

设计照 plugin-eval evaluation-methodology：把方案 + 某维度的五档锚定喂给 LLM，
要它只对这一个维度给 0.0–1.0 分并附理由。这里给出 prompt 工厂 + 占位评分。
"""
from __future__ import annotations
from .rubrics import ANCHORS, DIMENSION_WEIGHTS

JUDGE_PROMPT = """你是私域方案的严格评审。只评一个维度：{dim}。
锚定标准（0.0–1.0）：
{anchor}

待评方案：
---
{plan}
---
只输出该维度的分数(0.0–1.0)和不超过两句理由，JSON：{{"score": x, "why": "..."}}"""


def build_judge_prompt(dim: str, plan: str) -> str:
    return JUDGE_PROMPT.format(dim=dim, anchor=ANCHORS.get(dim, "（锚定待补，见 docs/blueprint.md §3d）"), plan=plan)


def score_with_judge(plan: str, dims=None) -> dict:
    """4档接入真实 LLM 调用（Claude）。当前为占位：返回 None 表示未启用判官层。"""
    raise NotImplementedError("judge 层需接 LLM。3档用 static-only 跑 eval；4档实现此函数。")
