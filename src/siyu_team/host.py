"""主持人（团长）收口：对四官盲审意见做综合拍板。

提示词默认从 ``plugins/siyu-core/prompts/host-v1.md`` 读取，支持热更新；
文件缺失时回退到内置 ``HOST_PROMPT``。
"""
from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Dict, List


_PROMPT_CANDIDATES = (
    Path(__file__).resolve().parents[2] / "plugins/siyu-core/prompts/host-v1.md",
    Path(__file__).resolve().parent / "prompts" / "host-v1.md",
)

HOST_PROMPT = """\
<task>
你是「私域专家团」的团长，私域操盘手画像，负责对四官的独立评审拍板。
议题：{question}
方案成功标准：{success_criteria}
硬约束：{constraints}

四官（公关官 / 产品官 / 广告官 / 合规官）已各自独立给出意见，互相不知道对方写了什么。
你的任务不是投票，也不是把四个意见平均，而是评估每位的推理质量，找出他们互相补足的地方，
保留有价值的少数意见（哪怕只有一个官反对），最后替团队给出一个能落地的判断。
如果某官的关键前提站不住，明确点出来，不要因为他职位在就采信。
合规官的红线意见拥有一票否决权：只要他标了 COMPLIANCE_RED，方案不得通过，先整改。
如果这是第 2 轮，请把上一轮主持综合(H1)也当作一个可审查的输入，而不是最终答案。
</task>

<officers>
{officers}
</officers>

<output_rules>
用中文写给团队成员看，像内部拍板会，不像报告。短段落，重点加粗独立成段。
不要用"confidence""加权""综上所述""总而言之"这类词。不确定的地方直说。
口吻：解释者，谦逊沉稳克制，不灌鸡汤金句、不炫资历。

按这个结构输出：

## 四官吵到哪了
两三段：哪里四个人其实一致，哪个分歧最要命，为什么这个分歧决定方案能不能落地。

## 逐官点评
每位官 3-5 句：他这次最有价值的判断是什么，又漏看了什么。
（公关官扣『私域即公关』、产品官扣『内容即产品』、广告官扣『运营即广告』各自的视角是否到位。）

## 团长拍板
两到三句给最终答复：方案通过 / 整改后通过 / 不通过，可带条件，但不要躲在条件后面。
最后一句让人记得住。

## 落地前必须先解决的事
1-3 条还没解决、但不解决就别上线的硬问题（合规红线优先）。

## 如果决定执行，第一周做什么
1-3 条具体动作，落到谁、做什么、看什么指标（指标须可埋点进某 BI 平台）。否则省略本节。
</output_rules>"""


def _strip_frontmatter(text: str) -> str:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return text
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[index + 1 :]).lstrip("\n")
    return text


@lru_cache(maxsize=4)
def _load_host_prompt_from(path_str: str, mtime_ns: int) -> str:
    del mtime_ns  # 仅参与 cache key，强制文件变更后重读
    text = Path(path_str).read_text(encoding="utf-8")
    return _strip_frontmatter(text).strip() + "\n"


def load_host_prompt() -> str:
    """运行时读取外置提示词；不存在则回退内置版本。"""
    for path in _PROMPT_CANDIDATES:
        if path.is_file():
            try:
                stat = path.stat()
                return _load_host_prompt_from(str(path), stat.st_mtime_ns)
            except OSError:
                continue
    return HOST_PROMPT


def stable_shuffle_traces(question: str, traces: List[Dict]) -> List[Dict]:
    """去位置偏差：用 question 做种子稳定洗牌（同输入同顺序，可复现）。仿 heavy.py:474+。"""
    seed = int(hashlib.sha256(question.encode("utf-8")).hexdigest(), 16)
    idx = list(range(len(traces)))
    # 确定性洗牌（Fisher-Yates with seeded LCG，避免依赖 random 全局态）
    for i in range(len(idx) - 1, 0, -1):
        seed = (seed * 6364136223846793005 + 1442695040888963407) & ((1 << 64) - 1)
        j = seed % (i + 1)
        idx[i], idx[j] = idx[j], idx[i]
    return [traces[i] for i in idx]


def build_host_prompt(
    question: str,
    officer_outputs: List[Dict],
    success_criteria: str = "",
    constraints: str = "",
) -> str:
    if len(officer_outputs) < 2:
        raise ValueError("主持人收口至少需要 2 位官的独立意见")
    template = load_host_prompt()
    shuffled = stable_shuffle_traces(question, officer_outputs)
    blocks = []
    for i, o in enumerate(shuffled, 1):
        blocks.append(
            "<officer>\n[%d] %s（引擎：%s）\n%s\n</officer>"
            % (i, o.get("name", "官"), o.get("engine", ""), o.get("content", ""))
        )
    # 逐个替换已知占位符（不用 str.format：热更模板里出现示例花括号
    # 如 {分母} 时 format 会 KeyError 崩掉整条收口链，replace 原样保留）。
    fields = {
        "question": question,
        "success_criteria": success_criteria or "（未指定）",
        "constraints": constraints or "（无）",
        "officers": "\n\n".join(blocks),
    }
    prompt = template
    for key, value in fields.items():
        prompt = prompt.replace("{" + key + "}", value)
    return prompt
