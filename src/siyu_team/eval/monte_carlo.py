"""蒙卡层：宿主对同一诉求生成 N 份方案，脚本统计一致性——B 路径，脚本只做数学。

可靠性分 = 0.40×命中率 + 0.30×(1−CV) + 0.20×(1−崩溃率) + 0.10×篇幅效率。
配 Wilson 置信区间，对外可说 "N 次里 x% 命中可执行 SOP，95%CI[...]"。

"生成 N 份"由宿主 Agent 完成（复用对话额度，无额外 API）；本模块只吃这 N 份的
度量并出统计结论。
"""
from __future__ import annotations

import math
from statistics import mean, pstdev
from typing import Any, Mapping, Sequence


def wilson_interval(hits: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """命中率的 Wilson 置信区间；小样本比正态近似更稳，且不会越出 [0,1]。"""
    if n <= 0:
        return (0.0, 0.0)
    p = hits / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


def reliability(samples: Sequence[Mapping[str, Any]]) -> dict:
    """吃 N 份样本的度量，出可靠性分 + 命中率置信区间。

    每份样本字段（缺省安全）：
    - ``score``   float 0–1：该份方案的主评分（可用 judge 合成分）
    - ``hit``     bool：是否命中"可执行 SOP"（达标）
    - ``crashed`` bool：是否跑崩/离题/空转
    - ``length``  int：字数，用于篇幅稳定性
    """
    n = len(samples)
    if n == 0:
        raise ValueError("蒙卡层至少需要 1 份样本")

    scores = [float(s.get("score", 0.0)) for s in samples]
    hits = sum(1 for s in samples if s.get("hit"))
    crashes = sum(1 for s in samples if s.get("crashed"))
    lengths = [int(s["length"]) for s in samples if s.get("length")]

    hit_rate = hits / n
    crash_rate = crashes / n
    avg_score = mean(scores) if scores else 0.0
    # 变异系数 CV = 标准差/均值，越低越稳；均值为 0 时视为无信号。
    cv = (pstdev(scores) / avg_score) if avg_score > 0 else 0.0
    # 篇幅效率：长度越集中越好（1 − 长度变异系数），样本不足则不惩罚。
    length_eff = 1.0
    if len(lengths) > 1 and mean(lengths) > 0:
        length_eff = max(0.0, 1 - pstdev(lengths) / mean(lengths))

    reliability_score = round(
        0.40 * hit_rate
        + 0.30 * (1 - min(cv, 1.0))
        + 0.20 * (1 - crash_rate)
        + 0.10 * length_eff,
        3,
    )
    low, high = wilson_interval(hits, n)
    return {
        "n": n,
        "reliability": reliability_score,
        "hit_rate": round(hit_rate, 3),
        "crash_rate": round(crash_rate, 3),
        "score_cv": round(cv, 3),
        "hit_ci95": [round(low, 3), round(high, 3)],
    }
