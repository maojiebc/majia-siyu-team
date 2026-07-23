"""判官层：锚定 rubric，由宿主 Agent 打分——B 路径，不调外部 API。

脚本只负责两件确定性的事：
1. build_judge_prompt / build_judge_batch —— 把方案 + 某维度五档锚定拼成评审 prompt；
2. parse_judge_scores —— 解析宿主返回的 {维度: 0.0–1.0} 评分，校验范围与维度合法。

真正的"打分"由宿主 Claude（judge subagent，见 plugins/_orchestrator）完成，复用现有
对话额度，无额外 API 账单。宿主评完把维度分回填给 engine.composite 出加权总分。
"""
from __future__ import annotations

import json
from typing import Any, Mapping

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
    return JUDGE_PROMPT.format(
        dim=dim,
        anchor=ANCHORS.get(dim, "（锚定待补，见 docs/blueprint.md §3d）"),
        plan=plan,
    )


def build_judge_batch(plan: str, dims: list[str] | None = None) -> dict[str, str]:
    """为每个维度生成一条评审 prompt，供宿主逐维独立打分。"""
    dims = dims or list(DIMENSION_WEIGHTS)
    unknown = [d for d in dims if d not in DIMENSION_WEIGHTS]
    if unknown:
        raise ValueError(f"未知评分维度：{', '.join(unknown)}")
    return {dim: build_judge_prompt(dim, plan) for dim in dims}


def parse_judge_scores(raw: Any) -> dict[str, float]:
    """解析宿主返回的维度分。

    接受 dict 或 JSON 字符串；每维的值可以是数字，也可以是 {"score": x, "why": ...}。
    校验维度合法且分数落在 0.0–1.0，任一不合规即 fail-closed 抛错。
    """
    if isinstance(raw, str):
        raw = json.loads(raw)
    if not isinstance(raw, Mapping):
        raise ValueError("judge 评分必须是 {维度: 分数} 对象")
    scores: dict[str, float] = {}
    for dim, value in raw.items():
        if dim not in DIMENSION_WEIGHTS:
            raise ValueError(f"未知评分维度：{dim}")
        raw_score = value.get("score") if isinstance(value, Mapping) else value
        try:
            score = float(raw_score)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{dim} 分数不是数字：{raw_score!r}") from exc
        if not 0.0 <= score <= 1.0:
            raise ValueError(f"{dim} 分数越界（需 0.0–1.0）：{score}")
        scores[dim] = score
    return scores
