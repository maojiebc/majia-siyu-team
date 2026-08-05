"""四类高价值贡献信号的保守识别。"""
from __future__ import annotations

import re

from .models import ContributionPromptState, ContributionSignal


_FIRSTHAND = re.compile(
    r"(我们|我|本公司|我们门店|当时|实际|亲自).{0,24}"
    r"(做过|试过|发现|调整|执行|落地|复盘|结果|有效|没用|不行)"
)
_CORRECTION = re.compile(
    r"(不是这个原因|真实情况是|这个阈值不对|行业里.{0,12}(不是|不会)|"
    r"加盟门店不会这么执行|实际不是这样)"
)
_FEEDBACK = re.compile(
    r"(上次|之前|照你说的|建议).{0,30}(采纳|试了|做了|执行|上线|调整)"
    r".{0,30}(结果|有效|无效|副作用|反而)?"
)
_BOUNDARY = re.compile(
    r"(只在.{0,20}(有效|成立)|在.{0,20}(失效|不适用|不行)|"
    r"除非|例外|反例|不同.{0,12}(门店|区域|业态).{0,16}(相反|不一样))"
)
_UNVERIFIED_REFERENCE = re.compile(r"(文章|公众号|网上|别人说|听说|据说|网课).{0,12}(提到|说|认为)?")
_CASUAL = re.compile(r"^(你好|谢谢|好的|哈哈|收到|辛苦了|再见)[！!。\s]*$")


def detect_contribution_signal(
    text: str,
    state: ContributionPromptState | None = None,
) -> ContributionSignal | None:
    """只识别明确亲历/纠错/反馈/边界；不把问题或转述当贡献。"""
    cleaned = text.strip()
    if not cleaned or _CASUAL.fullmatch(cleaned):
        return None
    if state is not None and not state.can_prompt:
        return None
    if _UNVERIFIED_REFERENCE.search(cleaned) and not _FIRSTHAND.search(cleaned):
        return None
    if cleaned.endswith(("?", "？")) and not any(
        pattern.search(cleaned) for pattern in (_FIRSTHAND, _CORRECTION, _FEEDBACK, _BOUNDARY)
    ):
        return None
    if _CORRECTION.search(cleaned):
        return ContributionSignal.USER_CORRECTION
    if _FEEDBACK.search(cleaned):
        return ContributionSignal.EXECUTION_FEEDBACK
    if _BOUNDARY.search(cleaned) and _FIRSTHAND.search(cleaned):
        return ContributionSignal.COUNTEREXAMPLE
    if _FIRSTHAND.search(cleaned):
        return ContributionSignal.FIRSTHAND_CASE
    return None
