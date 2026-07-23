"""蒙卡层：同一客户诉求生成 N 份测一致性。【4档实现】
可靠性分 = 0.40×命中率 + 0.30×(1−CV) + 0.20×(1−崩溃率) + 0.10×篇幅效率
配 Wilson/Clopper-Pearson 置信区间，对外可说 "50 次里 92% 命中可执行SOP，95%CI[0.85,0.96]"。
"""
from __future__ import annotations


def reliability(samples) -> dict:
    raise NotImplementedError("蒙卡层需多次生成+统计。4档实现。设计见 docs/blueprint.md §3d。")
