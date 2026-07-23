"""角色=视角配置表：换 prompt / 换绑定模型 完全不碰代码。
字段仿 qiaomu HeavyPerspectiveInput(schemas.py:144-152)。
"""
from __future__ import annotations
import json, os
from typing import Optional

DEFAULT_ROSTER_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "roster.example.json")

DEFAULT_OFFICERS = [
    {"name": "公关官", "engine": "私域即公关",
     "description": "只盯信任资产与口碑：IP/朋友圈人设/差评危机话术/转介绍。私域里每一次触达都是一次公关。",
     "subagent_type": "private-pr-officer-private-pr-officer", "model": "sonnet"},
    {"name": "产品官", "engine": "内容即产品",
     "description": "只盯内容与承接：选题/钩子/承接话术/社群促活，把内容当产品做（有钩子有承接有复购）。",
     "subagent_type": "content-product-officer-content-product-officer", "model": "sonnet"},
    {"name": "广告官", "engine": "运营即广告",
     "description": "只盯获客与转化漏斗：每个运营动作即一次广告投放，关心 UV→加微→首单→复购 每一跳的口径与埋点。",
     "subagent_type": "ops-ad-officer-ops-ad-officer", "model": "sonnet"},
    {"name": "合规官", "engine": "Critic",
     "description": "专找企微封号风险/违禁词/过度承诺/未授权收集个人信息，团里的怀疑者，对红线有一票否决权。",
     "subagent_type": "compliance-critic-compliance-critic", "model": "opus"},
]
MAX_OFFICERS = 6


def load_roster(path: Optional[str] = None) -> dict:
    path = path or DEFAULT_ROSTER_PATH
    if os.path.exists(path):
        return json.load(open(path))
    return {"version": "1.0.0", "officers": DEFAULT_OFFICERS, "host": {"mode": "codex", "rounds_max": 2}}


def normalize_officers(supplied=None, k: int = 4):
    """用户传了用用户的、否则用默认。仿 heavy.normalize_perspectives。"""
    officers = supplied or DEFAULT_OFFICERS
    return officers[:min(k, MAX_OFFICERS)]
