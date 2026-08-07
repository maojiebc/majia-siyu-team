"""结构化私域任务模型。

Skill 仍负责生成内容；本模块负责在进入 Skill 前，把自然语言请求固定成可验证、
可追踪、可回放的任务对象。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import json
import re
from typing import Any, Mapping, TypeVar
from uuid import uuid4


SCHEMA_VERSION = "1.0"
MAX_SOURCE_TEXT_LENGTH = 20_000


class TaskValidationError(ValueError):
    """任务字段不符合 schema。"""


class TaskKind(str, Enum):
    MOMENTS_COPY = "moments_copy"
    GROUP_CAMPAIGN = "group_campaign"
    CONVERSATION_SCRIPT = "conversation_script"
    MARKET_RESEARCH = "market_research"
    DIAGNOSIS = "diagnosis"
    STRATEGY_REVIEW = "strategy_review"
    SAVE_MEMORY = "save_memory"
    RESTORE_MEMORY = "restore_memory"
    REPORT = "report"
    UNKNOWN = "unknown"


class Channel(str, Enum):
    WECHAT_MOMENTS = "wechat_moments"
    WECHAT_GROUP = "wechat_group"
    WECHAT_DM = "wechat_dm"
    MULTI_CHANNEL = "multi_channel"
    UNKNOWN = "unknown"


class Goal(str, Enum):
    CONVERSION = "conversion"
    RETENTION = "retention"
    ACQUISITION = "acquisition"
    ENGAGEMENT = "engagement"
    TRUST = "trust"
    DIAGNOSIS = "diagnosis"
    DOCUMENTATION = "documentation"
    UNKNOWN = "unknown"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# (kind, pattern, weight)：多规则同时命中时取最高分；同分保留先登记顺序。
# 内容生产类权重大于存档类，避免「保存上次朋友圈文案」误判为 SAVE_MEMORY。
_KIND_RULES: tuple[tuple[TaskKind, re.Pattern[str], float], ...] = (
    (
        TaskKind.MARKET_RESEARCH,
        re.compile(
            r"(厂商|供应商|服务商|竞品|市场格局|市场地图|产品选型|"
            r"SCRM|CRM|公司存续|客户案例|最新政策|平台规则|"
            r"对比.{0,16}(报价|功能|价格|厂商|软件|系统|平台)|"
            r"(产品|软件|平台|系统).{0,8}(价格|报价|收费|功能|版本|接口|停服|在营)|"
            r"(价格|报价|功能|版本|接口).{0,8}(厂商|供应商|服务商|软件|平台|产品|系统)|"
            r"是否.{0,8}(经营|停服|注销))"
        ),
        3.0,
    ),
    (
        TaskKind.STRATEGY_REVIEW,
        re.compile(r"(全盘|整盘|战略评审|私域体系|全面搭建|怎么搭|四官)"),
        2.8,
    ),
    (
        TaskKind.DIAGNOSIS,
        re.compile(
            r"(为什么|怎么办|问题出在哪|长期|一直|连续.{0,5}(低|差|没)|"
            r"转化差|留存.{0,3}(掉|差)|没人加微|不活跃|没回复|没打开|"
            r"打开率.{0,6}(低|差|还是))"
        ),
        2.6,
    ),
    (
        TaskKind.MOMENTS_COPY,
        re.compile(r"(朋友圈|发圈|内容池|节日文案|导购素材)"),
        2.4,
    ),
    (
        TaskKind.GROUP_CAMPAIGN,
        re.compile(r"(群发|社群栏目|秒杀通知|活动通知|群公告|推送脚本)"),
        2.2,
    ),
    (
        TaskKind.CONVERSATION_SCRIPT,
        re.compile(r"(欢迎语|破冰|答疑|话术|新人进群|加人后|私聊脚本)"),
        2.2,
    ),
    (
        TaskKind.REPORT,
        re.compile(r"(出报告|生成报告|打包给.{0,6}(老板|客户))"),
        2.0,
    ),
    (
        TaskKind.RESTORE_MEMORY,
        re.compile(r"(恢复|接着上次|上次聊|之前聊到哪)"),
        1.5,
    ),
    (
        TaskKind.SAVE_MEMORY,
        re.compile(r"(保存|存档|记下来|留下结论)"),
        1.0,
    ),
)

# 存档/恢复类与内容生产类同时命中时，压低存档分，优先内容任务。
_CONTENT_KINDS = frozenset(
    {
        TaskKind.MOMENTS_COPY,
        TaskKind.GROUP_CAMPAIGN,
        TaskKind.CONVERSATION_SCRIPT,
        TaskKind.MARKET_RESEARCH,
        TaskKind.DIAGNOSIS,
        TaskKind.STRATEGY_REVIEW,
        TaskKind.REPORT,
    }
)

_GOAL_RULES: tuple[tuple[Goal, re.Pattern[str]], ...] = (
    (Goal.RETENTION, re.compile(r"(留存|复购|召回|唤醒)")),
    (Goal.ACQUISITION, re.compile(r"(获客|拉新|加微|引流)")),
    (Goal.ENGAGEMENT, re.compile(r"(活跃|打开|回复|互动)")),
    (Goal.TRUST, re.compile(r"(信任|口碑|人设|公关)")),
    (Goal.CONVERSION, re.compile(r"(转化|成交|下单|销售|GMV|活动)")),
)

_HIGH_RISK = re.compile(
    r"(批量.{0,4}(加好友|群发)|手机号|身份证|定位|外挂|虚拟定位|"
    r"诱导分享|拉.{0,3}\d+.{0,3}人|100%|稳赚|包赚|最便宜|最好)"
)
_MEDIUM_RISK = re.compile(r"(群发|裂变|优惠|折扣|秒杀|收集|电话|微信号)")

EnumType = TypeVar("EnumType", bound=Enum)


def _enum_value(
    enum_type: type[EnumType],
    value: Any,
    field_name: str,
) -> EnumType:
    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        allowed = ", ".join(item.value for item in enum_type)
        raise TaskValidationError(f"{field_name} 必须是：{allowed}") from exc


def _clean_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise TaskValidationError("context 必须是对象")
    cleaned = {str(key): item for key, item in value.items()}
    try:
        json.dumps(cleaned, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise TaskValidationError("context 必须可序列化为 JSON") from exc
    return cleaned


def _boolean_value(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise TaskValidationError(f"{field_name} 必须是布尔值")
    return value


@dataclass(frozen=True)
class Task:
    kind: TaskKind
    source_text: str
    channel: Channel = Channel.UNKNOWN
    goal: Goal = Goal.UNKNOWN
    risk: RiskLevel = RiskLevel.LOW
    industry: str = ""
    stage: str = ""
    client: str = ""
    audience: str = ""
    constraints: tuple[str, ...] = ()
    context: Mapping[str, Any] = field(default_factory=dict)
    need_compliance_check: bool = True
    task_id: str = field(default_factory=lambda: f"task_{uuid4().hex}")
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        text = self.source_text.strip()
        if len(text) > MAX_SOURCE_TEXT_LENGTH:
            raise TaskValidationError(
                f"source_text 超过 {MAX_SOURCE_TEXT_LENGTH} 字符上限"
            )
        if not self.task_id.startswith("task_"):
            raise TaskValidationError("task_id 必须以 task_ 开头")
        if self.schema_version != SCHEMA_VERSION:
            raise TaskValidationError(
                f"不支持 schema_version={self.schema_version!r}"
            )
        object.__setattr__(self, "source_text", text)
        object.__setattr__(self, "industry", self.industry.strip().lower())
        object.__setattr__(self, "stage", self.stage.strip().lower())
        object.__setattr__(self, "client", self.client.strip())
        object.__setattr__(self, "audience", self.audience.strip())
        object.__setattr__(self, "constraints", tuple(self.constraints))
        object.__setattr__(self, "context", _clean_mapping(self.context))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "task_id": self.task_id,
            "kind": self.kind.value,
            "source_text": self.source_text,
            "channel": self.channel.value,
            "goal": self.goal.value,
            "risk": self.risk.value,
            "industry": self.industry,
            "stage": self.stage,
            "client": self.client,
            "audience": self.audience,
            "constraints": list(self.constraints),
            "context": dict(self.context),
            "need_compliance_check": self.need_compliance_check,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Task":
        if not isinstance(data, Mapping):
            raise TaskValidationError("任务必须是对象")
        constraints = data.get("constraints", ())
        if isinstance(constraints, str) or not isinstance(constraints, (list, tuple)):
            raise TaskValidationError("constraints 必须是字符串数组")
        return cls(
            schema_version=str(data.get("schema_version", SCHEMA_VERSION)),
            task_id=str(data.get("task_id") or f"task_{uuid4().hex}"),
            kind=_enum_value(TaskKind, data.get("kind", "unknown"), "kind"),
            source_text=str(data.get("source_text", "")),
            channel=_enum_value(
                Channel, data.get("channel", "unknown"), "channel"
            ),
            goal=_enum_value(Goal, data.get("goal", "unknown"), "goal"),
            risk=_enum_value(RiskLevel, data.get("risk", "low"), "risk"),
            industry=str(data.get("industry", "")),
            stage=str(data.get("stage", "")),
            client=str(data.get("client", "")),
            audience=str(data.get("audience", "")),
            constraints=tuple(str(item) for item in constraints),
            context=_clean_mapping(data.get("context")),
            need_compliance_check=_boolean_value(
                data.get("need_compliance_check", True),
                "need_compliance_check",
            ),
        )


def _infer_kind(text: str) -> TaskKind:
    """多规则积分；低置信度内容任务优先于存档类，避免顺序依赖误判。"""
    scores: dict[TaskKind, float] = {}
    order: list[TaskKind] = []
    for kind, pattern, weight in _KIND_RULES:
        if pattern.search(text):
            if kind not in scores:
                order.append(kind)
            scores[kind] = scores.get(kind, 0.0) + weight

    if not scores:
        return TaskKind.UNKNOWN

    # 「保存上次朋友圈文案」会同时命中 SAVE_MEMORY 与 MOMENTS_COPY。
    if scores.keys() & _CONTENT_KINDS:
        for memory_kind in (TaskKind.SAVE_MEMORY, TaskKind.RESTORE_MEMORY):
            if memory_kind in scores:
                scores[memory_kind] *= 0.25

    best_score = max(scores.values())
    for kind in order:
        if scores[kind] == best_score:
            return kind
    return TaskKind.UNKNOWN


def infer_kind_with_confidence(text: str) -> tuple[TaskKind, float]:
    """对外暴露 kind + 置信度，便于路由层在低分时改问用户。"""
    kind = _infer_kind(text)
    if kind is TaskKind.UNKNOWN:
        return kind, 0.0
    # 归一到 0-1：权重表最高约 3.0
    raw = 0.0
    for candidate, pattern, weight in _KIND_RULES:
        if candidate is kind and pattern.search(text):
            raw = weight
            break
    if kind in _CONTENT_KINDS and (
        re.search(r"(保存|存档|记下来|留下结论|恢复|接着上次)", text)
    ):
        # 内容优先场景仍保持较高置信度
        confidence = min(1.0, raw / 3.0 + 0.15)
    else:
        confidence = min(1.0, raw / 3.0)
    return kind, round(confidence, 3)


def _infer_channel(kind: TaskKind, text: str) -> Channel:
    if kind is TaskKind.MOMENTS_COPY:
        return Channel.WECHAT_MOMENTS
    if kind is TaskKind.GROUP_CAMPAIGN or re.search(r"(群|社群)", text):
        return Channel.WECHAT_GROUP
    if kind is TaskKind.CONVERSATION_SCRIPT or re.search(r"(私聊|加微)", text):
        return Channel.WECHAT_DM
    if kind is TaskKind.STRATEGY_REVIEW:
        return Channel.MULTI_CHANNEL
    return Channel.UNKNOWN


def _infer_goal(kind: TaskKind, text: str) -> Goal:
    if kind in {
        TaskKind.DIAGNOSIS,
        TaskKind.MARKET_RESEARCH,
        TaskKind.STRATEGY_REVIEW,
    }:
        fallback = Goal.DIAGNOSIS
    elif kind in {
        TaskKind.SAVE_MEMORY,
        TaskKind.RESTORE_MEMORY,
        TaskKind.REPORT,
    }:
        fallback = Goal.DOCUMENTATION
    else:
        fallback = Goal.UNKNOWN
    for goal, pattern in _GOAL_RULES:
        if pattern.search(text):
            return goal
    return fallback


def _infer_risk(text: str) -> RiskLevel:
    if _HIGH_RISK.search(text):
        return RiskLevel.HIGH
    if _MEDIUM_RISK.search(text):
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def parse_task(text: str, hints: Mapping[str, Any] | None = None) -> Task:
    """把自然语言转成 Task；显式 hints 始终覆盖规则推断。"""
    clean_text = str(text).strip()
    supplied = dict(hints or {})
    inferred_kind = _infer_kind(clean_text)
    effective_kind = _enum_value(
        TaskKind,
        supplied.get("kind", inferred_kind.value),
        "kind",
    )
    inferred_channel = _infer_channel(effective_kind, clean_text)
    inferred_goal = _infer_goal(effective_kind, clean_text)
    inferred_risk = _infer_risk(clean_text)

    payload: dict[str, Any] = {
        "kind": effective_kind.value,
        "source_text": clean_text,
        "channel": inferred_channel.value,
        "goal": inferred_goal.value,
        "risk": inferred_risk.value,
    }
    payload.update(supplied)
    payload["source_text"] = clean_text
    return Task.from_dict(payload)
