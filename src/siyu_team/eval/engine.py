"""加权合成 + 反模式乘法惩罚 + 徽章。照 plugin-eval engine。

注意：composite()/badge() 依赖 judge/蒙卡产出的维度分；那两层当前未实装，
本模块也不被 score CLI 调用。score 只做静态合规检查，不据此产出质量分。
"""
from __future__ import annotations
from .rubrics import DIMENSION_WEIGHTS

BADGES = [(90, "Platinum 进案例库"), (80, "Gold 可直接交付"),
          (70, "Silver 内部复核后交付"), (60, "Bronze 需返工"), (0, "<60 不交付")]


def badge(score: float) -> str:
    for th, label in BADGES:
        if score >= th:
            return label
    return "<60 不交付"


def composite(dim_scores: dict, static_penalty: float = 1.0) -> dict:
    """dim_scores: {维度: 0.0–1.0}。缺的维度按 0 计并提示。"""
    total = 0.0
    missing = []
    for dim, (w, _) in DIMENSION_WEIGHTS.items():
        s = dim_scores.get(dim)
        if s is None:
            missing.append(dim)
            s = 0.0
        total += w * s
    score = round(total * 100 * static_penalty, 1)
    return {"score": score, "badge": badge(score), "missing_dims": missing, "static_penalty": static_penalty}
