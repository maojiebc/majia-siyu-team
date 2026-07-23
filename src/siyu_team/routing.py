"""行业×阶段 规则路由（不花 token）。仿 qiaomu routing.py，换成私域类目。
返回：选定行业册路径 + 阶段重点 + 四官各自要重点回答的子问题。
"""
from __future__ import annotations

INDUSTRIES = {"catering": "餐饮", "retail": "零售", "edu": "教培"}
STAGES = {
    "cold": "冷启动（0 起步 / 有微信没体系）",
    "growth": "扩张（有体系要提效）",
    "mature": "成熟（要规模化裂变）",
}

# 阶段 -> 团长要四官重点回答的子问题
STAGE_FOCUS = {
    "cold": "先解决『加得上人 + 加进来不流失』：钩子、承接、第一周 SOP。",
    "growth": "先解决『分层提效 + 复购』：标签体系、自动化 SOP、复购召回。",
    "mature": "先解决『规模化裂变 + 会员体系』：合规裂变机制、会员等级、案例复制。",
}


def route(industry: str, stage: str) -> dict:
    industry = industry if industry in INDUSTRIES else ""
    stage = stage if stage in STAGES else ""
    book = "knowledge/02-industry/%s/" % industry if industry else None
    return {
        "industry": industry, "industry_cn": INDUSTRIES.get(industry, "未定，需 Step 0 补问"),
        "stage": stage, "stage_cn": STAGES.get(stage, "未定，需 Step 0 补问"),
        "industry_book": book,
        "focus": STAGE_FOCUS.get(stage, "Step 0 调研补齐阶段后再定重点。"),
    }
