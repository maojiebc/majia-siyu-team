"""静态层：纯正则反模式，免费、确定性。命中即扣分；COMPLIANCE_RED 单独硬卡。"""
from __future__ import annotations
from typing import Dict, List, TypedDict
from .compliance_lexicon import PATTERNS, INDUCE_PATTERN, PRIVACY_PATTERN

class ComplianceDetail(TypedDict):
    flag: str
    desc: str
    severity: float
    hard: bool


# 裂变诱导（企微封号红线，硬卡）与未授权隐私索取（软提示，可能存在授权场景）。
# 这两条正则原先只被 skill lint 用；此处纳入 scan，让 score 质量门也一并拦截。
_EXTRA_PATTERNS = [
    ("INDUCE_SHARE", "诱导分享/集赞/拉人裂变（企微封号红线）", 0.20, True, INDUCE_PATTERN),
    ("PRIVACY_COLLECT", "未授权索取手机号/身份证等敏感信息", 0.15, False, PRIVACY_PATTERN),
]


def scan(text: str) -> Dict:
    flags: List[str] = []
    details: List[ComplianceDetail] = []
    for flag, desc, sev, hard, rx in PATTERNS + _EXTRA_PATTERNS:
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
    # 按 severity 加权：高危单 flag 比多个低危 flag 惩罚更重
    weighted_penalty_sum = sum(float(d["severity"]) for d in details)
    penalty = max(0.5, 1.0 - weighted_penalty_sum)
    hard_fail = any(d["hard"] for d in details)
    return {"flags": flags, "details": details, "penalty": penalty, "hard_fail": hard_fail}
