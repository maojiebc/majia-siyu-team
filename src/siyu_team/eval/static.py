"""静态层：纯正则反模式，免费、确定性。命中即扣分；COMPLIANCE_RED 单独硬卡。"""
from __future__ import annotations
from typing import List, Dict
from .compliance_lexicon import PATTERNS


def scan(text: str) -> Dict:
    flags: List[str] = []
    details = []
    for flag, desc, sev, hard, rx in PATTERNS:
        if flag in ("NO_RESPONSIBLE_PARTY",):
            continue
        if flag == "NO_METRIC":
            hit = not (rx and rx.search(text))
        else:
            hit = bool(rx and rx.search(text))
        if hit:
            flags.append(flag)
            details.append(
                {"flag": flag, "desc": desc, "severity": sev, "hard": hard}
            )
    penalty = max(0.5, 1.0 - 0.05 * len(flags))  # 照搬 plugin-eval static.py:30-32
    hard_fail = any(d["hard"] for d in details)
    return {"flags": flags, "details": details, "penalty": penalty, "hard_fail": hard_fail}
