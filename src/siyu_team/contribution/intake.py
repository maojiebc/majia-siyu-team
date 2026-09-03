"""同行表单 → 社区原子：纯函数，无网络。"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
import os
import re
from statistics import median
from typing import Any, Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo

from ..knowledge.models import (
    Applicability,
    Confirmation,
    KnowledgeAtomV2,
    Lifecycle,
    Metric,
    Privacy,
    Quality,
    CHANNELS,
    CONTRIBUTOR_ROLES,
    ORG_LAYERS,
    Scope,
    SourceRef,
    generate_community_atom_id,
    generate_source_id,
)
from .models import ContributionCandidate, ContributionSignal, ContributionValidationError
from .privacy import redact_pii, scan_fields


HASH_SALT_ENV = "SIYU_HASH_SALT"
MAINTAINER_IDS_ENV = "SIYU_MAINTAINER_IDS"
INTAKE_MODE_ENV = "SIYU_INTAKE_MODE"
MODE_LENIENT = "lenient"
MODE_STRICT = "strict"
MIN_SALT_LEN = 16
STATUS_PENDING = "待审"
STATUS_APPROVED = "已通过"
STATUS_REJECTED_REVIEW = "已驳回"
STATUS_MANUAL = "需人工"
STATUS_REJECTED = "已拒"
STATUS_REVOKED = "撤销"
GIFT_REVOKED = "已撤销"
REVIEW_PENDING = "待审"
REVIEW_PASS = "通过"
REVIEW_REJECT = "驳回"
REVIEW_GRADES = frozenset({"A", "B", "C", "D"})
NOTE_UNKNOWN_KIND = "类别未知，内测宽松收录"
NOTE_DATE_FALLBACK = "发现时间无法解析，改用创建时间"
NOTE_PII_REDACTED = "已脱敏：原文含个人信息，未入库"
NOTE_PII_DISPLAY_NAME = "对外显示名含个人信息，已改为匿名同行"
ANON_LABEL = "匿名同行"
PUBLIC_DASHBOARD_URL = (
    "https://supermjbc.feishu.cn/share/base/dashboard/shrcnqmdXTKecILgQsKXMGfN4Oe"
)
PUBLIC_MIRROR_STATUSES = frozenset({STATUS_PENDING, STATUS_APPROVED})
PUBLIC_REMOVE_STATUSES = frozenset(
    {STATUS_REVOKED, STATUS_REJECTED, STATUS_REJECTED_REVIEW, STATUS_MANUAL}
)
REASON_FEISHU = "feishu_status"
REASON_CLI = "cli"
SHANGHAI = ZoneInfo("Asia/Shanghai")
COMPANY_SUFFIXES = (
    "股份有限公司",
    "有限责任公司",
    "餐饮管理",
    "有限公司",
    "分公司",
    "集团",
    "控股",
    "餐饮",
    "科技",
    "商贸",
    "连锁",
    "品牌",
    "总部",
)
PAREN_REGION = re.compile(r"[（(][^）)]*[）)]")
COMPANY_PUNCT = re.compile(r"[\W_]+", re.UNICODE)
VALID_TYPES_WITH_TTL = frozenset({"platform_workaround", "rule_change"})
ANTONYM_PAIRS = (
    ("有效", "无效"),
    ("涨", "跌"),
    ("上升", "下降"),
    ("提高", "降低"),
    ("增加", "减少"),
)
KIND_TO_TYPE = {
    "平台技巧": "platform_workaround",
    "文案钩子": "hook_pattern",
    "排版": "layout_pattern",
    "发送时机": "timing",
    "数字基线": "benchmark",
    "反例翻车": "anti-pattern",
    "厂商体验": "vendor_experience",
    "规则变化": "rule_change",
    "方法": "method",
}
INDUSTRY_MAP = {"餐饮": "catering", "零售": "retail", "其他": "other"}
CATERING_LABELS = frozenset(
    {
        "餐饮",
        "餐饮·正餐",
        "餐饮·快餐小吃",
        "餐饮·火锅烧烤",
        "咖啡茶饮",
        "烘焙甜品",
    }
)
RETAIL_LABELS = frozenset(
    {
        "零售",
        "零售·便利店",
        "零售·商超生鲜",
        "零售·服饰美妆",
        "零售·母婴宠物",
    }
)
MODEL_MAP = {"直营": "direct", "加盟": "franchise", "混合": "mixed"}
SCALE_VALUES = frozenset(
    {"1", "2-10", "11-50", "51-300", "301-1000", "1001-5000", "5000+", "any"}
)
ORG_LAYER_MAP = {"有": "regional", "没有": "none", "不清楚": "any"}
ROLE_MAP = {
    "总部": "hq",
    "分公司或区域": "regional",
    "加盟商": "franchisee",
    "门店": "store",
    "服务商或顾问": "vendor_or_consultant",
}
CHANNEL_MAP = {
    "企业微信": "wecom",
    "个人微信": "personal_wechat",
    "微信社群": "wechat_group",
    "小程序会员": "miniprogram_member",
    "公众号": "official_account",
    "抖音快手私信": "douyin_kuaishou_dm",
    "小红书": "xiaohongshu",
    "其他": "other",
}
KIND_TOPICS = {
    "platform_workaround": ("add_wechat",),
    "hook_pattern": ("activity_increment",),
    "layout_pattern": ("activity_increment",),
    "timing": ("activity_increment",),
    "benchmark": ("activity_increment",),
    "anti-pattern": ("repurchase_recall",),
    "vendor_experience": ("add_wechat",),
    "rule_change": ("add_wechat",),
    "method": ("add_wechat",),
}
KIND_SKILLS = {
    "platform_workaround": ("siyu-huashu", "siyu-wenzhen"),
    "hook_pattern": ("siyu-pyq", "siyu-wenzhen"),
    "layout_pattern": ("siyu-pyq", "siyu-wenzhen"),
    "timing": ("siyu-qunfa", "siyu-wenzhen"),
    "benchmark": ("siyu-wenzhen",),
    "anti-pattern": ("siyu-wenzhen",),
    "vendor_experience": ("siyu-market-research", "siyu-wenzhen"),
    "rule_change": ("siyu-wenzhen",),
    "method": ("siyu-wenzhen",),
}
HIGH_RISK = re.compile(r"(外挂|群发软件|虚拟定位|改定位|诱导分享)")
MEDIUM_RISK = re.compile(r"(敏感词|关键字|自动应答|绕过|规避|防骚扰)")
LOW_RISK = re.compile(r"(绝对|最好|第一|保证|稳赚)")
PUNCT = re.compile(r"[\s，。！？、；：,.!?;:（）()【】\[\]\"'《》·…—\-]+")


class HashSaltError(ValueError):
    """SIYU_HASH_SALT 未设置或过短，拒绝继续。"""


def intake_mode(
    environ: Mapping[str, str] | None = None,
    override: str = "",
) -> str:
    """未设置或无法识别时默认 lenient；只有 strict 收紧。"""
    if override.strip().casefold() == MODE_STRICT:
        return MODE_STRICT
    if override.strip().casefold() == MODE_LENIENT:
        return MODE_LENIENT
    env = os.environ if environ is None else environ
    value = (env.get(INTAKE_MODE_ENV) or "").strip().casefold()
    if value == MODE_STRICT:
        return MODE_STRICT
    return MODE_LENIENT


def hash_salt(environ: Mapping[str, str] | None = None) -> str:
    env = os.environ if environ is None else environ
    value = (env.get(HASH_SALT_ENV) or "").strip()
    if len(value) < MIN_SALT_LEN:
        raise HashSaltError(
            f"{HASH_SALT_ENV} 未设置或短于 {MIN_SALT_LEN} 个字符，已拒绝继续"
        )
    return value


def normalize_company_name(name: str) -> str:
    text = name.strip().casefold()
    while True:
        stripped = PAREN_REGION.sub("", text)
        if stripped == text:
            break
        text = stripped
    text = COMPANY_PUNCT.sub("", text)
    changed = True
    while changed and text:
        changed = False
        for suffix in COMPANY_SUFFIXES:
            if text.endswith(suffix) and len(text) > len(suffix):
                text = text[: -len(suffix)]
                changed = True
                break
    return text


def hash_identity(value: str, salt: str | None = None) -> str:
    normalized = normalize_company_name(value)
    used_salt = hash_salt() if salt is None else salt
    payload = f"{used_salt}\n{normalized}".encode("utf-8")
    return sha256(payload).hexdigest()


def maintainer_ids(environ: Mapping[str, str] | None = None) -> frozenset[str]:
    env = os.environ if environ is None else environ
    raw = env.get(MAINTAINER_IDS_ENV, "")
    return frozenset(part.strip().casefold() for part in raw.split(",") if part.strip())


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        if isinstance(value, int) and value > 10_000_000_000:
            try:
                return datetime.fromtimestamp(value / 1000, tz=SHANGHAI).date().isoformat()
            except (OSError, OverflowError, ValueError):
                return str(value)
        return str(value)
    if isinstance(value, Mapping):
        for key in ("text", "name", "value", "record_id"):
            if key in value:
                return _as_text(value[key])
        texts = [_as_text(item) for item in value.values()]
        return " ".join(item for item in texts if item)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return " ".join(part for part in (_as_text(item) for item in value) if part)
    return str(value).strip()


def _extract_record_ids(value: Any) -> list[str]:
    found: list[str] = []
    if value is None:
        return found
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("rec"):
            found.append(text)
        return found
    if isinstance(value, Mapping):
        for key in (
            "record_id",
            "recordId",
            "record_ids",
            "recordIds",
            "link_record_ids",
            "id",
        ):
            if key in value:
                found.extend(_extract_record_ids(value[key]))
        return found
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for item in value:
            found.extend(_extract_record_ids(item))
    return found


def _as_link_record_id(value: Any) -> str:
    ids = _extract_record_ids(value)
    return ids[0] if ids else ""


def _as_link_display(value: Any) -> str:
    """只要展示文本，不要把 rec_ id 当成文案。"""
    if value is None:
        return ""
    if isinstance(value, Mapping):
        for key in ("text", "name"):
            if key in value:
                text = _as_text(value[key])
                if text:
                    return text
        return ""
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        parts = [_as_link_display(item) for item in value]
        return " ".join(part for part in parts if part)
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("rec"):
            return ""
        return text
    return _as_text(value)


def _as_link(value: Any) -> str:
    """关联字段优先 record_id（rec_… / id），没有才回退到展示文本。"""
    record_id = _as_link_record_id(value)
    if record_id:
        return record_id
    return _as_link_display(value) or _as_text(value)


def _fields_of(record: Mapping[str, Any]) -> Mapping[str, Any]:
    fields = record.get("fields")
    if isinstance(fields, Mapping):
        return fields
    return record


def _record_id(record: Mapping[str, Any]) -> str:
    for key in ("record_id", "recordId", "id"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    fields = _fields_of(record)
    return _as_text(fields.get("Submission ID") or fields.get("记录ID"))


def _get(fields: Mapping[str, Any], *names: str) -> str:
    for name in names:
        if name in fields:
            text = _as_text(fields[name])
            if text:
                return text
    return ""


def _as_labels(value: Any) -> list[str]:
    """多选/单选：list of strings，或纯字符串，或带 text 的片段。"""
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, Mapping):
        text = _as_text(value)
        return [text] if text else []
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        labels: list[str] = []
        for item in value:
            labels.extend(_as_labels(item))
        return labels
    text = _as_text(value)
    return [text] if text else []


def _compose_subindustry(label: str, detail: str) -> str:
    extra = detail.strip()
    if label and extra:
        return f"{label} · {extra}"
    return label or extra


def map_industry(label: str, detail: str = "") -> tuple[str, str]:
    """业态标签 → (industry, subindustry)。认新选项，也认旧的 餐饮/零售。"""
    text = label.strip()
    extra = detail.strip()
    if text in CATERING_LABELS or text.startswith("餐饮"):
        industry = "catering"
        sub_label = "" if text == "餐饮" else text
        return industry, _compose_subindustry(sub_label, extra)
    if text in RETAIL_LABELS or text.startswith("零售"):
        industry = "retail"
        sub_label = "" if text == "零售" else text
        return industry, _compose_subindustry(sub_label, extra)
    if text == "其他":
        return "other", _compose_subindustry(text, extra)
    if text in INDUSTRY_MAP:
        return INDUSTRY_MAP[text], extra
    return text.casefold(), extra


def map_scale_band(value: str) -> str:
    text = value.strip()
    if text == "300+":
        return "any"
    if text in SCALE_VALUES:
        return text
    return "any"


def map_org_layers(value: str) -> str:
    text = value.strip()
    if text in ORG_LAYERS:
        return text
    return ORG_LAYER_MAP.get(text, "any")


def map_contributor_role(value: str) -> str:
    text = value.strip()
    if text in CONTRIBUTOR_ROLES:
        return text
    return ROLE_MAP.get(text, "unknown")


def map_channels(value: Any) -> tuple[str, ...]:
    found: list[str] = []
    for label in _as_labels(value):
        if label in CHANNELS:
            mapped = label
        else:
            mapped = CHANNEL_MAP.get(label, "")
        if mapped and mapped not in found:
            found.append(mapped)
    return tuple(found)


def known_kind(kind: str) -> bool:
    return kind in KIND_TO_TYPE or kind in KIND_TO_TYPE.values()


def parse_observed_date(value: str) -> str | None:
    """发现时间：能解析则 YYYY-MM-DD，空或无法解析返回 None，不回落到今天。"""
    text = value.strip()
    if not text:
        return None
    if "T" in text:
        text = text.split("T", 1)[0]
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        return None


def record_status(record: Mapping[str, Any]) -> str:
    return _get(_fields_of(record), "状态", "status")


def record_atom_id(record: Mapping[str, Any]) -> str:
    return normalize_atom_ref(_get(_fields_of(record), "原子ID", "atom_id"))


def redact_candidate(candidate: ContributionCandidate) -> ContributionCandidate:
    summary = redact_pii(candidate.summary)
    evidence = redact_pii(candidate.evidence_text)
    facts = tuple(redact_pii(item) for item in candidate.user_facts) or (summary,)
    return replace(
        candidate,
        summary=summary,
        evidence_text=evidence,
        user_facts=facts,
        result=redact_pii(candidate.result),
    )


def apply_lenient_policy(
    candidate: ContributionCandidate,
) -> tuple[ContributionCandidate, str]:
    notes: list[str] = []
    updated = candidate
    if statement_has_blocking_pii(updated):
        updated = redact_candidate(updated)
        notes.append(NOTE_PII_REDACTED)
    if not known_kind(updated.kind):
        updated = replace(updated, kind="方法")
        notes.append(NOTE_UNKNOWN_KIND)
    if parse_observed_date(updated.observed_at) is None:
        fallback = parse_observed_date(updated.created_at)
        if fallback:
            updated = replace(updated, observed_at=fallback)
            notes.append(NOTE_DATE_FALLBACK)
    cleaned_name, dirty_name = sanitize_display_name(updated.contributor_display_name)
    if dirty_name:
        updated = replace(updated, contributor_display_name=cleaned_name)
        notes.append(NOTE_PII_DISPLAY_NAME)
    return updated, "；".join(notes)


@dataclass(frozen=True)
class RevokedAtom:
    id: str
    revoked_at: str
    reason: str
    record_id: str = ""

    def to_dict(self) -> dict[str, str]:
        payload = {
            "id": self.id,
            "revoked_at": self.revoked_at,
            "reason": self.reason,
        }
        if self.record_id:
            payload["record_id"] = self.record_id
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RevokedAtom | None":
        atom_id = str(data.get("id") or "").strip()
        if not atom_id.startswith("ka_"):
            atom_id = normalize_atom_ref(atom_id) if atom_id else ""
        record_id = str(data.get("record_id") or "").strip()
        if not atom_id and not record_id:
            return None
        when = str(data.get("revoked_at") or "").strip() or date.today().isoformat()
        parsed = parse_observed_date(when) or date.today().isoformat()
        reason = str(data.get("reason") or REASON_CLI).strip() or REASON_CLI
        return cls(id=atom_id, revoked_at=parsed, reason=reason, record_id=record_id)


def load_revoked_entries(path: Any) -> tuple[RevokedAtom, ...]:
    from pathlib import Path

    target = Path(path)
    if not target.is_file():
        return ()
    found: list[RevokedAtom] = []
    seen: set[tuple[str, str]] = set()
    for raw in target.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if not isinstance(payload, Mapping):
            continue
        item = RevokedAtom.from_dict(payload)
        if item is None or (item.id, item.record_id) in seen:
            continue
        seen.add((item.id, item.record_id))
        found.append(item)
    return tuple(found)


def merge_revoked(
    existing: Sequence[RevokedAtom],
    incoming: Sequence[RevokedAtom],
) -> tuple[RevokedAtom, ...]:
    by_key: dict[tuple[str, str], RevokedAtom] = {}
    for item in (*existing, *incoming):
        key = (item.id, item.record_id)
        if key in by_key:
            continue
        by_key[key] = item
    return tuple(by_key.values())


def write_revoked_jsonl(path: Any, entries: Sequence[RevokedAtom]) -> bytes:
    from pathlib import Path

    target = Path(path)
    ordered = sorted(entries, key=lambda item: (item.id, item.record_id, item.revoked_at))
    encoded = (
        ("\n".join(json.dumps(item.to_dict(), ensure_ascii=False) for item in ordered) + "\n")
        .encode("utf-8")
        if ordered
        else b""
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file() and target.read_bytes() == encoded:
        return encoded
    if not encoded and not target.is_file():
        return b""
    target.write_bytes(encoded)
    return encoded


@dataclass(frozen=True)
class RejectedAtom:
    id: str
    rejected_at: str
    reviewer: str
    reason: str
    record_id: str = ""

    def to_dict(self) -> dict[str, str]:
        payload = {
            "id": self.id,
            "rejected_at": self.rejected_at,
            "reviewer": self.reviewer,
            "reason": self.reason,
        }
        if self.record_id:
            payload["record_id"] = self.record_id
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RejectedAtom | None":
        atom_id = str(data.get("id") or "").strip()
        if atom_id and not atom_id.startswith("ka_"):
            atom_id = normalize_atom_ref(atom_id)
        record_id = str(data.get("record_id") or "").strip()
        if not atom_id and not record_id:
            return None
        when = parse_observed_date(str(data.get("rejected_at") or "")) or date.today().isoformat()
        return cls(
            id=atom_id,
            rejected_at=when,
            reviewer=str(data.get("reviewer") or "").strip(),
            reason=str(data.get("reason") or "").strip(),
            record_id=record_id,
        )


def load_rejected_entries(path: Any) -> tuple[RejectedAtom, ...]:
    from pathlib import Path

    target = Path(path)
    if not target.is_file():
        return ()
    found: list[RejectedAtom] = []
    seen: set[tuple[str, str]] = set()
    for raw in target.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if not isinstance(payload, Mapping):
            continue
        item = RejectedAtom.from_dict(payload)
        if item is None or (item.id, item.record_id) in seen:
            continue
        seen.add((item.id, item.record_id))
        found.append(item)
    return tuple(found)


def merge_rejected(
    existing: Sequence[RejectedAtom],
    incoming: Sequence[RejectedAtom],
) -> tuple[RejectedAtom, ...]:
    by_key: dict[tuple[str, str], RejectedAtom] = {}
    for item in (*existing, *incoming):
        key = (item.id, item.record_id)
        if key not in by_key:
            by_key[key] = item
    return tuple(by_key.values())


def write_rejected_jsonl(path: Any, entries: Sequence[RejectedAtom]) -> bytes:
    from pathlib import Path

    target = Path(path)
    ordered = sorted(entries, key=lambda item: (item.id, item.record_id, item.rejected_at))
    encoded = (
        ("\n".join(json.dumps(item.to_dict(), ensure_ascii=False) for item in ordered) + "\n")
        .encode("utf-8")
        if ordered
        else b""
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file() and target.read_bytes() == encoded:
        return encoded
    if not encoded and not target.is_file():
        return b""
    target.write_bytes(encoded)
    return encoded


def resolve_revoke_target(
    record: Mapping[str, Any],
    *,
    existing_atoms: Sequence[KnowledgeAtomV2],
    salt: str | None = None,
) -> tuple[str, str]:
    """返回 (atom_id, record_id)。"""
    record_id = _record_id(record)
    atom_id = record_atom_id(record)
    if atom_id:
        return atom_id, record_id
    for atom in existing_atoms:
        if record_id and atom.source.locator == record_id:
            return atom.id, record_id
    try:
        candidate = record_to_candidate(record, salt=salt)
    except ContributionValidationError:
        return "", record_id
    return generate_community_atom_id(candidate.summary, candidate.company_hash), record_id


def scan_platform_rule_risk(text: str, atom_type: str) -> str:
    """只标注，不拦截。eval 模块保持只读；这里复用同类关键词。"""
    if HIGH_RISK.search(text):
        return "high"
    if MEDIUM_RISK.search(text):
        return "medium"
    if atom_type in VALID_TYPES_WITH_TTL:
        if LOW_RISK.search(text):
            return "low"
        return "low"
    if LOW_RISK.search(text):
        return "low"
    return "none"


def record_to_candidate(
    record: Mapping[str, Any],
    *,
    salt: str | None = None,
) -> ContributionCandidate:
    """把一条飞书记录映成 ContributionCandidate；公司名当场哈希，联系方式不进提交内容。"""
    fields = _fields_of(record)
    statement = _get(fields, "一件有效的事（或没用的事）", "statement")
    if not statement:
        raise ContributionValidationError("一件有效的事（或没用的事）不能为空")
    company = _get(fields, "公司/品牌", "company")
    if not company:
        raise ContributionValidationError("公司/品牌不能为空")
    used_salt = hash_salt() if salt is None else salt
    contact = _get(fields, "联系方式", "contact", "contributor_id")
    contributor_token = contact or _record_id(record) or company
    industry_label = _get(fields, "业态", "industry")
    industry, subindustry = map_industry(
        industry_label, _get(fields, "细分", "subindustry")
    )
    kind = _get(fields, "这条属于", "kind")
    observed = _get(fields, "发现时间", "observed_at")
    created = _get(fields, "创建时间", "created_at") or observed
    evidence = _get(fields, "数字/证据", "evidence")
    channel_value = None
    for name in ("主要私域载体", "channels"):
        if name in fields:
            channel_value = fields[name]
            break
    candidate_id_source = _record_id(record) or statement
    digest = sha256(candidate_id_source.encode("utf-8")).hexdigest()[:32]
    return ContributionCandidate(
        signal=ContributionSignal.FIRSTHAND_CASE,
        user_facts=(statement,),
        summary=statement,
        scene=" / ".join(
            part
            for part in (
                industry_label,
                _get(fields, "经营模式", "business_model"),
                _get(fields, "门店数", "scale_band"),
            )
            if part
        ),
        result=evidence,
        candidate_id=f"candidate_{digest}",
        record_id=_record_id(record),
        company_hash=hash_identity(company, used_salt),
        contributor_hash=hash_identity(contributor_token, used_salt),
        contributor_id=contact,
        industry=industry,
        subindustry=subindustry,
        business_model=MODEL_MAP.get(
            _get(fields, "经营模式", "business_model"), "any"
        ),
        scale_band=map_scale_band(_get(fields, "门店数", "scale_band")),
        org_layers=map_org_layers(_get(fields, "分公司层", "org_layers")),
        contributor_role=map_contributor_role(
            _get(fields, "你的位置", "contributor_role")
        ),
        channels=map_channels(channel_value),
        kind=kind,
        observed_at=observed,
        still_valid=_get(fields, "现在还有效吗", "still_valid"),
        evidence_text=evidence,
        created_at=created,
        contributor_display_name=_get(
            fields, "对外显示名", "contributor_display_name", "display_name"
        ),
    )


@dataclass(frozen=True)
class ParsedConfirmation:
    confirmation: Confirmation
    link_record_id: str
    pasted_atom_id: str
    link_display: str


def normalize_atom_ref(value: str) -> str:
    """空白去掉、小写；没有 ka_ 前缀也认。"""
    text = "".join(value.split()).casefold()
    if not text:
        return ""
    if text.startswith("ka_"):
        return text
    return f"ka_{text}"


def parse_confirmation_row(
    record: Mapping[str, Any],
    *,
    salt: str | None = None,
) -> ParsedConfirmation | None:
    """缺公司则无法建印证（返回 None）；关联可以后补解析。"""
    fields = _fields_of(record)
    company = _get(fields, "印证人公司", "company")
    if not company:
        return None
    link_value = fields["关联提交"] if "关联提交" in fields else None
    link_record_id = _as_link_record_id(link_value)
    link_display = _as_link_display(link_value)
    if not link_record_id:
        fallback = _get(fields, "record_id", "submission_id")
        if fallback.startswith("rec"):
            link_record_id = fallback
        elif fallback and not link_display:
            link_display = fallback
    pasted_atom_id = _get(fields, "印证的原子ID", "atom_id")
    when = _get(fields, "印证时间", "confirmed_at") or date.today().isoformat()
    used_salt = hash_salt() if salt is None else salt
    contact = _get(fields, "印证人联系方式", "contact", "contributor_id")
    token = contact or company
    parsed_when = parse_observed_date(when) or date.today().isoformat()
    display_name, _dirty = sanitize_display_name(
        _get(fields, "对外显示名", "display_name")
    )
    return ParsedConfirmation(
        confirmation=Confirmation(
            contributor_hash=hash_identity(token, used_salt),
            company_hash=hash_identity(company, used_salt),
            confirmed_at=parsed_when,
            display_name=display_name,
        ),
        link_record_id=link_record_id,
        pasted_atom_id=pasted_atom_id,
        link_display=link_display,
    )


def resolve_confirmation_target(
    parsed: ParsedConfirmation,
    *,
    atom_ids: set[str],
    locator_to_atom: Mapping[str, str],
    record_to_atom: Mapping[str, str],
) -> str | None:
    """按 关联record_id → 印证的原子ID → 关联展示文本 解析到 atom id。"""
    known_atoms = {normalize_atom_ref(atom_id): atom_id for atom_id in atom_ids}

    def _atom_from_record(record_id: str) -> str | None:
        if record_id in record_to_atom:
            return record_to_atom[record_id]
        if record_id in locator_to_atom:
            return locator_to_atom[record_id]
        return None

    if parsed.link_record_id:
        hit = _atom_from_record(parsed.link_record_id)
        if hit:
            return hit
    pasted = normalize_atom_ref(parsed.pasted_atom_id)
    if pasted and pasted in known_atoms:
        return known_atoms[pasted]
    display = parsed.link_display.strip()
    if display:
        hit = _atom_from_record(display)
        if hit:
            return hit
        display_atom = normalize_atom_ref(display)
        if display_atom in known_atoms:
            return known_atoms[display_atom]
    return None


def _date_only(value: str) -> str:
    parsed = parse_observed_date(value)
    if parsed is not None:
        return parsed
    return date.today().isoformat()


WINDOW_DAYS = 180
MIN_VISIBLE_DAYS = 30
TYPE_LABELS = {value: key for key, value in KIND_TO_TYPE.items()}
MODEL_LABELS = {"direct": "直营", "franchise": "加盟", "mixed": "混合", "any": "不限"}
INDUSTRY_LABELS = {"catering": "餐饮", "retail": "零售", "other": "其他"}
RISK_LABELS = {"none": "无", "low": "低", "medium": "中", "high": "高"}
GRADE_LABELS = {
    "A": "维护者A级",
    "B": "维护者B级",
}


def _as_date(value: str, fallback: date | None = None) -> date:
    parsed = parse_observed_date(value)
    if parsed:
        return date.fromisoformat(parsed)
    return fallback or date.today()


def _valid_until(
    atom_type: str,
    observed_at: str,
    still_valid: str,
    *,
    submitted_at: str = "",
    today: date | None = None,
) -> str:
    used_today = today or date.today()
    observed = _as_date(observed_at, used_today)
    if still_valid == "已失效":
        return observed.isoformat()
    if atom_type not in VALID_TYPES_WITH_TTL:
        return ""
    if still_valid == "是":
        submitted = parse_observed_date(submitted_at)
        base = date.fromisoformat(submitted) if submitted else used_today
        return (base + timedelta(days=WINDOW_DAYS)).isoformat()
    from_observed = observed + timedelta(days=WINDOW_DAYS)
    floor = used_today + timedelta(days=MIN_VISIBLE_DAYS)
    return max(from_observed, floor).isoformat()


def extend_valid_until(current: str, confirmed_at: str) -> str:
    parsed = parse_observed_date(confirmed_at)
    if not parsed:
        return current
    extra = (date.fromisoformat(parsed) + timedelta(days=WINDOW_DAYS)).isoformat()
    if not current:
        return extra
    return extra if extra > current else current


def _industry_gift_label(atom: KnowledgeAtomV2) -> str:
    sub = atom.scope.subindustry.strip()
    if sub and not sub.isascii():
        return sub
    industry = INDUSTRY_LABELS.get(atom.scope.industry, "") or (
        atom.scope.industry if atom.scope.industry and not atom.scope.industry.isascii() else ""
    )
    if industry and sub and sub not in industry and not sub.isascii():
        return f"{industry} · {sub}"
    return industry or "未声明"


def _layer_topic(industry: str) -> str:
    if industry == "retail":
        return "growth_l1_retail"
    if industry == "catering":
        return "growth_l1_catering"
    return "growth_l0"


def _metrics(evidence: str) -> tuple[Metric, ...]:
    cleaned = evidence.strip()
    if not cleaned:
        return ()
    return (
        Metric(
            name="投稿数字",
            definition=cleaned,
            time_window="投稿当时",
        ),
    )


def _confidence(grade: str) -> str:
    if grade == "A":
        return "high"
    if grade == "C":
        return "medium"
    return "low"


def filter_independent_confirmations(
    origin_company: str,
    origin_contributor: str,
    confirmations: Sequence[Confirmation],
) -> tuple[Confirmation, ...]:
    """去掉自评、同公司重复、同贡献者重复；每家公司只留一条。"""
    kept: list[Confirmation] = []
    seen_companies = {origin_company} if origin_company else set()
    seen_contributors = {origin_contributor} if origin_contributor else set()
    for item in confirmations:
        if origin_company and item.company_hash == origin_company:
            continue
        if origin_contributor and item.contributor_hash == origin_contributor:
            continue
        if item.company_hash and item.company_hash in seen_companies:
            continue
        if item.contributor_hash and item.contributor_hash in seen_contributors:
            continue
        kept.append(item)
        if item.company_hash:
            seen_companies.add(item.company_hash)
        if item.contributor_hash:
            seen_contributors.add(item.contributor_hash)
    return tuple(kept)


def suggest_grade(
    company_hash: str,
    confirmations: Sequence[Confirmation],
    *,
    contributor_hash: str = "",
    contributor_id: str = "",
    maintainer_id_set: Iterable[str] | None = None,
) -> str:
    """机器建议，不是发布等级。A=维护者，C=至少两家独立公司印证，否则 D。"""
    maintainers = frozenset(maintainer_id_set or ())
    if contributor_id.strip().casefold() in maintainers:
        return "A"
    independent = filter_independent_confirmations(
        company_hash, contributor_hash, confirmations
    )
    companies = {
        hash_
        for hash_ in (company_hash, *(item.company_hash for item in independent))
        if hash_
    }
    if len(companies) >= 2:
        return "C"
    return "D"


def evaluate_grade(
    company_hash: str,
    confirmations: Sequence[Confirmation],
    *,
    contributor_hash: str = "",
    contributor_id: str = "",
    maintainer_id_set: Iterable[str] | None = None,
    sticky_grade: str = "",
) -> str:
    del sticky_grade
    return suggest_grade(
        company_hash,
        confirmations,
        contributor_hash=contributor_hash,
        contributor_id=contributor_id,
        maintainer_id_set=maintainer_id_set,
    )


def candidate_to_atom(
    candidate: ContributionCandidate,
    confirmations: Sequence[Confirmation] = (),
    maintainer_ids: Iterable[str] | None = None,
    *,
    today: date | None = None,
    review_notes: str = "",
) -> KnowledgeAtomV2:
    if not candidate.company_hash:
        raise ContributionValidationError("candidate_to_atom 需要 company_hash")
    if candidate.kind in KIND_TO_TYPE:
        atom_type = KIND_TO_TYPE[candidate.kind]
    elif candidate.kind in KIND_TO_TYPE.values():
        atom_type = candidate.kind
    else:
        raise ContributionValidationError("这条属于无法识别，不能入库")
    observed = parse_observed_date(candidate.observed_at)
    if observed is None:
        raise ContributionValidationError("发现时间无法解析，不能入库")
    scale = map_scale_band(candidate.scale_band)
    industry = candidate.industry or ""
    org_layers = map_org_layers(candidate.org_layers)
    contributor_role = map_contributor_role(candidate.contributor_role)
    channels = map_channels(candidate.channels)
    display_name, _dirty = sanitize_display_name(candidate.contributor_display_name)
    topics = (
        *KIND_TOPICS.get(atom_type, ("add_wechat",)),
        _layer_topic(industry),
    )
    confirm_list = tuple(confirmations)
    original = Confirmation(
        contributor_hash=candidate.contributor_hash or candidate.company_hash,
        company_hash=candidate.company_hash,
        confirmed_at=observed,
        display_name=display_name,
    )
    independent = filter_independent_confirmations(
        original.company_hash,
        original.contributor_hash,
        confirm_list,
    )
    merged = (original, *independent)
    suggested = suggest_grade(
        candidate.company_hash,
        merged,
        contributor_hash=original.contributor_hash,
        contributor_id=candidate.contributor_id,
        maintainer_id_set=maintainer_ids,
    )
    risk = scan_platform_rule_risk(candidate.summary, atom_type)
    preconditions = [
        f"业态={industry or '未声明'}",
        f"经营模式={candidate.business_model or 'any'}",
        f"门店规模={scale}",
    ]
    if not candidate.evidence_text:
        preconditions.append("指标不适用：投稿未给数字")
    recommended = (
        (f"避免：{candidate.summary}",)
        if atom_type == "anti-pattern"
        else (candidate.summary,)
    )
    source_id = generate_source_id(f"community:{candidate.company_hash}")
    atom_id = generate_community_atom_id(candidate.summary, candidate.company_hash)
    return KnowledgeAtomV2(
        id=atom_id,
        statement=candidate.summary,
        type=atom_type,
        topics=topics,
        skills=KIND_SKILLS.get(atom_type, ("siyu-wenzhen",)),
        source=SourceRef(
            source_id=source_id,
            source_type="community",
            label="同行共建",
            path="knowledge/05-community/",
            locator=candidate.record_id or atom_id,
            observed_at=observed,
            contributor_role=contributor_role,
            contributor_display_name=display_name,
        ),
        scope=Scope(
            visibility="public",
            industry=industry,
            subindustry=candidate.subindustry,
            business_model=candidate.business_model or "any",
            scale_band=(scale,),
            org_layers=org_layers,
            channels=channels,
            scenarios=KIND_TOPICS.get(atom_type, ("add_wechat",)),
        ),
        applicability=Applicability(
            preconditions=tuple(preconditions),
            recommended_action=recommended,
            metrics=_metrics(candidate.evidence_text),
            failure_modes=("未在同规模、同模式门店印证前，不能当成普遍规律",),
            execution_boundary=(
                "hq_tools_incentives"
                if candidate.business_model == "franchise"
                else "any"
            ),
        ),
        quality=Quality(
            evidence_grade=suggested,
            confidence=_confidence(suggested),
            review_status="pending",
            confirmations=merged,
            platform_rule_risk=risk,
            review_notes=review_notes,
            suggested_grade=suggested,
        ),
        lifecycle=Lifecycle(
            valid_from=observed,
            valid_until=_windowed_until(
                atom_type,
                _valid_until(
                    atom_type,
                    observed,
                    candidate.still_valid,
                    submitted_at=candidate.created_at,
                    today=today,
                ),
                independent,
            ),
        ),
        privacy=Privacy(exportable=True),
    )


def statement_tokens(text: str) -> frozenset[str]:
    compact = PUNCT.sub("", text.casefold())
    if not compact:
        return frozenset()
    if len(compact) == 1:
        return frozenset({compact})
    return frozenset(compact[i : i + 2] for i in range(len(compact) - 1))


def statement_jaccard(left: str, right: str) -> float:
    a = statement_tokens(left)
    b = statement_tokens(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass(frozen=True)
class DedupeResult:
    atoms: tuple[KnowledgeAtomV2, ...]
    merged_into: Mapping[str, str]


def _origin_hashes(atom: KnowledgeAtomV2) -> tuple[str, str]:
    if atom.quality.confirmations:
        first = atom.quality.confirmations[0]
        return first.company_hash, first.contributor_hash
    return "", ""


def _with_confirmations(
    atom: KnowledgeAtomV2,
    extra: Sequence[Confirmation],
    *,
    maintainer: bool = False,
) -> KnowledgeAtomV2:
    del maintainer
    origin_company, origin_contributor = _origin_hashes(atom)
    existing_rest = atom.quality.confirmations[1:] if atom.quality.confirmations else ()
    independent = filter_independent_confirmations(
        origin_company,
        origin_contributor,
        (*existing_rest, *extra),
    )
    if atom.quality.confirmations:
        merged = [atom.quality.confirmations[0], *independent]
    else:
        merged = list(independent)
    suggested = suggest_grade(
        origin_company,
        tuple(merged),
        contributor_hash=origin_contributor,
    )
    grade = (
        atom.quality.evidence_grade
        if atom.quality.review_status == "approved"
        else suggested
    )
    quality = Quality(
        evidence_grade=grade,
        confidence=_confidence(grade),
        review_status=atom.quality.review_status,
        reviewer=atom.quality.reviewer,
        reviewed_at=atom.quality.reviewed_at,
        confirmations=tuple(merged),
        platform_rule_risk=atom.quality.platform_rule_risk,
        review_notes=atom.quality.review_notes,
        suggested_grade=suggested,
    )
    lifecycle = atom.lifecycle
    if atom.type in VALID_TYPES_WITH_TTL:
        until = atom.lifecycle.valid_until
        for item in extra:
            until = extend_valid_until(until, item.confirmed_at)
        if until != atom.lifecycle.valid_until:
            lifecycle = Lifecycle(
                valid_from=atom.lifecycle.valid_from,
                valid_until=until,
                supersedes=atom.lifecycle.supersedes,
                contradicts=atom.lifecycle.contradicts,
            )
    return KnowledgeAtomV2(
        id=atom.id,
        statement=atom.statement,
        type=atom.type,
        topics=atom.topics,
        skills=atom.skills,
        source=atom.source,
        scope=atom.scope,
        applicability=atom.applicability,
        quality=quality,
        lifecycle=lifecycle,
        privacy=atom.privacy,
    )


def dedupe(
    new_atoms: Sequence[KnowledgeAtomV2],
    existing_atoms: Sequence[KnowledgeAtomV2],
) -> DedupeResult:
    """Jaccard ≥ 0.8 视为对已有原子的印证，不新建。"""
    pool: list[KnowledgeAtomV2] = list(existing_atoms)
    merged_into: dict[str, str] = {}
    accepted: list[KnowledgeAtomV2] = []
    for atom in new_atoms:
        target_index = None
        for index, current in enumerate(pool):
            if statement_jaccard(atom.statement, current.statement) >= 0.8:
                target_index = index
                break
        if target_index is None:
            pool.append(atom)
            accepted.append(atom)
            continue
        current = pool[target_index]
        updated = _with_confirmations(current, atom.quality.confirmations)
        pool[target_index] = updated
        merged_into[atom.id] = updated.id
        if current in accepted:
            accepted[accepted.index(current)] = updated
        else:
            # existing atom updated in place for later writers
            pass
    # Return new-or-updated atoms that originated in this batch plus
    # existing atoms that received confirmations.
    changed_ids = set(merged_into.values()) | {atom.id for atom in accepted}
    result = tuple(atom for atom in pool if atom.id in changed_ids)
    return DedupeResult(atoms=result, merged_into=merged_into)


def flag_conflicts(
    atom: KnowledgeAtomV2,
    existing: Sequence[KnowledgeAtomV2],
) -> KnowledgeAtomV2:
    """同主题且判断句含反义标记时写入 contradicts，不自动消解。"""
    hits: list[str] = []
    for other in existing:
        if other.id == atom.id:
            continue
        if other.scope.industry != atom.scope.industry:
            continue
        shared_topics = set(atom.topics).intersection(other.topics)
        if not shared_topics:
            continue
        if not _has_antonym(atom.statement, other.statement):
            continue
        hits.append(other.id)
    if not hits:
        return atom
    contradicts = tuple(dict.fromkeys((*atom.lifecycle.contradicts, *hits)))
    lifecycle = Lifecycle(
        valid_from=atom.lifecycle.valid_from,
        valid_until=atom.lifecycle.valid_until,
        supersedes=atom.lifecycle.supersedes,
        contradicts=contradicts,
    )
    return replace_lifecycle(atom, lifecycle)


def replace_lifecycle(atom: KnowledgeAtomV2, lifecycle: Lifecycle) -> KnowledgeAtomV2:
    return KnowledgeAtomV2(
        id=atom.id,
        statement=atom.statement,
        type=atom.type,
        topics=atom.topics,
        skills=atom.skills,
        source=atom.source,
        scope=atom.scope,
        applicability=atom.applicability,
        quality=atom.quality,
        lifecycle=lifecycle,
        privacy=atom.privacy,
    )


def _has_antonym(left: str, right: str) -> bool:
    for positive, negative in ANTONYM_PAIRS:
        if (positive in left and negative in right) or (
            negative in left and positive in right
        ):
            return True
    return False


def _windowed_until(
    atom_type: str,
    current: str,
    confirmations: Sequence[Confirmation],
) -> str:
    if atom_type not in VALID_TYPES_WITH_TTL:
        return current
    until = current
    for item in confirmations:
        until = extend_valid_until(until, item.confirmed_at)
    return until


def independent_confirmation_count(atom: KnowledgeAtomV2) -> int:
    if not atom.quality.confirmations:
        return 0
    origin = atom.quality.confirmations[0]
    return len(
        filter_independent_confirmations(
            origin.company_hash,
            origin.contributor_hash,
            atom.quality.confirmations[1:],
        )
    )


def grade_label(atom: KnowledgeAtomV2) -> str:
    n_companies = len({item.company_hash for item in atom.quality.confirmations})
    grade = atom.quality.evidence_grade
    if grade in GRADE_LABELS:
        return GRADE_LABELS[grade]
    if grade == "C":
        return f"社区C级（{n_companies}家印证）"
    return "单源D级"


def _replace_quality(atom: KnowledgeAtomV2, quality: Quality) -> KnowledgeAtomV2:
    return KnowledgeAtomV2(
        id=atom.id,
        statement=atom.statement,
        type=atom.type,
        topics=atom.topics,
        skills=atom.skills,
        source=atom.source,
        scope=atom.scope,
        applicability=atom.applicability,
        quality=quality,
        lifecycle=atom.lifecycle,
        privacy=atom.privacy,
    )


def parse_reviewer_name(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, Mapping):
        return _as_text(value.get("name") or value.get("text") or value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        names = [parse_reviewer_name(item) for item in value]
        return "、".join(part for part in names if part)
    return _as_text(value)


def parse_review_conclusion(record: Mapping[str, Any]) -> str:
    text = _get(_fields_of(record), "评审结论")
    if text == REVIEW_PASS:
        return REVIEW_PASS
    if text == REVIEW_REJECT:
        return REVIEW_REJECT
    return REVIEW_PENDING


def parse_review_grade(record: Mapping[str, Any]) -> str:
    text = _get(_fields_of(record), "评审等级")
    return text if text in REVIEW_GRADES else ""


def record_modified_date(record: Mapping[str, Any], fallback: date) -> str:
    for key in ("last_modified_time", "modified_time", "updated_time", "last_modified"):
        if key in record:
            parsed = parse_observed_date(_as_text(record[key]))
            if parsed:
                return parsed
    fields = _fields_of(record)
    for name in ("最后修改时间", "修改时间"):
        parsed = parse_observed_date(_get(fields, name))
        if parsed:
            return parsed
    return fallback.isoformat()


def apply_human_review(
    atom: KnowledgeAtomV2,
    record: Mapping[str, Any],
    *,
    today: date | None = None,
) -> tuple[KnowledgeAtomV2 | None, str, RejectedAtom | None]:
    used_today = today or date.today()
    conclusion = parse_review_conclusion(record)
    fields = _fields_of(record)
    reviewer = parse_reviewer_name(fields.get("评审人")) or "maintainer"
    notes = _get(fields, "评审批注")
    when = record_modified_date(record, used_today)
    record_id = _record_id(record)
    if conclusion == REVIEW_REJECT:
        return (
            None,
            STATUS_REJECTED_REVIEW,
            RejectedAtom(
                id=atom.id,
                rejected_at=when,
                reviewer=reviewer,
                reason=notes,
                record_id=record_id,
            ),
        )
    if conclusion == REVIEW_PASS:
        grade = parse_review_grade(record) or atom.quality.suggested_grade or "D"
        quality = Quality(
            evidence_grade=grade,
            confidence=_confidence(grade),
            review_status="approved",
            reviewer=reviewer,
            reviewed_at=when,
            confirmations=atom.quality.confirmations,
            platform_rule_risk=atom.quality.platform_rule_risk,
            review_notes=notes or atom.quality.review_notes,
            suggested_grade=atom.quality.suggested_grade,
        )
        return _replace_quality(atom, quality), STATUS_APPROVED, None
    return atom, STATUS_PENDING, None


def review_line(atom: KnowledgeAtomV2) -> str:
    if atom.quality.review_status == "approved":
        return f"评审：已通过（{atom.quality.evidence_grade}级）"
    return "评审：待审，通过后进入下一版 skill"


def public_mirror_grade(atom: KnowledgeAtomV2, status: str) -> str:
    suggested = atom.quality.suggested_grade or atom.quality.evidence_grade
    if status == STATUS_PENDING:
        return f"待审（建议{suggested}）"
    if status == STATUS_APPROVED:
        return f"评审通过·{atom.quality.evidence_grade}级"
    return grade_label(atom)


def render_gift(atom: KnowledgeAtomV2, benchmark_summary: str = "") -> str:
    grade_line = grade_label(atom)
    type_label = TYPE_LABELS.get(atom.type, "方法")
    model_label = MODEL_LABELS.get(atom.scope.business_model, "不限")
    scale = "、".join(
        "不限" if band == "any" else band for band in atom.scope.scale_band
    )
    risk_line = RISK_LABELS.get(atom.quality.platform_rule_risk, "无")
    lines = [
        "【同行案例卡】",
        f"原子ID：{atom.id}",
        f"署名：{public_display_name(atom.source.contributor_display_name)}",
        f"同行都交了什么：{PUBLIC_DASHBOARD_URL}",
        f"判断：{atom.statement}",
        f"类型：{type_label}",
        (
            f"业态/模式/规模：{_industry_gift_label(atom)} / "
            f"{model_label} / {scale}"
        ),
        f"证据：{atom.applicability.metrics[0].definition if atom.applicability.metrics else '未提供数字'}",
        f"证据等级：{grade_line}",
        review_line(atom),
        f"平台规则风险：{risk_line}",
    ]
    if atom.lifecycle.valid_until:
        lines.append(f"有效期至：{atom.lifecycle.valid_until}")
    if benchmark_summary:
        lines.append(f"同规模基线：{benchmark_summary}")
    else:
        lines.append("同规模基线：暂无同业态×规模带的社区数字。")
    lines.append("想撤回，告诉发起人即可。")
    return "\n".join(lines)


def statement_has_blocking_pii(candidate: ContributionCandidate) -> bool:
    scan = scan_fields(
        (
            ("statement", candidate.summary),
            ("evidence", candidate.evidence_text),
        )
    )
    return not scan.safe


def display_name_has_pii(value: str) -> bool:
    name = value.strip()
    if not name:
        return False
    return not scan_fields((("display_name", name),)).safe


def sanitize_display_name(value: str) -> tuple[str, bool]:
    """公开署名不做哈希；含手机号/邮箱等则清空，由调用方决定宽松备注或需人工。"""
    name = value.strip()
    if not name:
        return "", False
    if display_name_has_pii(name):
        return "", True
    return name, False


def public_display_name(value: str) -> str:
    return value.strip() or ANON_LABEL


def writeback_fields_changed(
    record: Mapping[str, Any],
    status: str,
    atom_id: str,
    gift: str,
    suggested_grade: str = "",
    confirm_count: int | None = None,
) -> bool:
    """只有 状态/原子ID/回礼/建议等级/印证数 真的变了才回写。"""
    fields = _fields_of(record)
    current = (
        _as_text(fields.get("状态")),
        _as_text(fields.get("原子ID")),
        _as_text(fields.get("回礼")),
        _as_text(fields.get("建议等级")),
        _as_text(fields.get("印证数")),
    )
    wanted_count = "" if confirm_count is None else str(confirm_count)
    return current != (status, atom_id, gift, suggested_grade, wanted_count)


@dataclass(frozen=True)
class IntakeDecision:
    record_id: str
    status: str
    atom: KnowledgeAtomV2 | None
    gift: str
    hours_to_publish: float | None
    writeback_atom_id: str = ""

    def atom_id_for_writeback(self) -> str:
        if self.writeback_atom_id:
            return self.writeback_atom_id
        return "" if self.atom is None else self.atom.id


@dataclass(frozen=True)
class IntakeRun:
    decisions: tuple[IntakeDecision, ...]
    atoms: tuple[KnowledgeAtomV2, ...]
    existing_updated: tuple[KnowledgeAtomV2, ...]
    metrics: Mapping[str, Any]
    revoked: tuple[RevokedAtom, ...] = ()
    rejected: tuple[RejectedAtom, ...] = ()
    reopened: tuple[str, ...] = ()


def _created_hours(created_at: str, now: datetime) -> float | None:
    text = created_at.strip()
    if not text:
        return None
    try:
        if "T" in text:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
        else:
            parsed = datetime.fromisoformat(_date_only(text)).replace(tzinfo=SHANGHAI)
    except ValueError:
        return None
    return max(0.0, (now - parsed).total_seconds() / 3600.0)


def run_intake(
    records: Sequence[Mapping[str, Any]],
    confirmation_rows: Sequence[Mapping[str, Any]] = (),
    existing_atoms: Sequence[KnowledgeAtomV2] = (),
    *,
    maintainer_id_set: Iterable[str] | None = None,
    salt: str | None = None,
    today: date | None = None,
    now: datetime | None = None,
    benchmark_index: Mapping[tuple[str, str], str] | None = None,
    mode: str | None = None,
    revoked_ids: Iterable[str] = (),
    revoked_record_ids: Iterable[str] = (),
    rejected_ids: Iterable[str] = (),
    rejected_record_ids: Iterable[str] = (),
) -> IntakeRun:
    used_today = today or date.today()
    used_now = now or datetime.now(timezone.utc)
    used_mode = intake_mode(override=mode or "")
    blocked_ids = {item for item in revoked_ids if item}
    blocked_records = {item for item in revoked_record_ids if item}
    blocked_rejected_ids = {item for item in rejected_ids if item}
    blocked_rejected_records = {item for item in rejected_record_ids if item}
    records_by_id = {_record_id(record): record for record in records if _record_id(record)}
    maintainers = frozenset(maintainer_id_set if maintainer_id_set is not None else maintainer_ids())
    parsed_confirmations = [
        parse_confirmation_row(row, salt=salt) for row in confirmation_rows
    ]

    decisions: list[IntakeDecision] = []
    pending: list[tuple[ContributionCandidate, str]] = []
    newly_revoked: list[RevokedAtom] = []
    for record in records:
        record_id = _record_id(record)
        if record_status(record) == STATUS_REVOKED or record_id in blocked_records:
            atom_id, rec_id = resolve_revoke_target(
                record, existing_atoms=existing_atoms, salt=salt
            )
            if atom_id:
                blocked_ids.add(atom_id)
            if rec_id:
                blocked_records.add(rec_id)
            if atom_id or rec_id:
                newly_revoked.append(
                    RevokedAtom(
                        id=atom_id,
                        revoked_at=used_today.isoformat(),
                        reason=REASON_FEISHU,
                        record_id=rec_id,
                    )
                )
            decisions.append(
                IntakeDecision(
                    record_id,
                    STATUS_REVOKED,
                    None,
                    GIFT_REVOKED,
                    None,
                    writeback_atom_id=atom_id,
                )
            )
            continue
        try:
            candidate = record_to_candidate(record, salt=salt)
        except ContributionValidationError:
            decisions.append(
                IntakeDecision(record_id, STATUS_REJECTED, None, "", None)
            )
            continue
        notes = ""
        if used_mode == MODE_LENIENT:
            candidate, notes = apply_lenient_policy(candidate)
            if statement_has_blocking_pii(candidate):
                decisions.append(
                    IntakeDecision(record_id, STATUS_MANUAL, None, "", None)
                )
                continue
        elif statement_has_blocking_pii(candidate):
            decisions.append(
                IntakeDecision(record_id, STATUS_MANUAL, None, "", None)
            )
            continue
        elif display_name_has_pii(candidate.contributor_display_name):
            decisions.append(
                IntakeDecision(record_id, STATUS_MANUAL, None, "", None)
            )
            continue
        elif not known_kind(candidate.kind):
            decisions.append(
                IntakeDecision(record_id, STATUS_MANUAL, None, "", None)
            )
            continue
        elif parse_observed_date(candidate.observed_at) is None:
            decisions.append(
                IntakeDecision(record_id, STATUS_MANUAL, None, "", None)
            )
            continue
        if used_mode == MODE_LENIENT and parse_observed_date(candidate.observed_at) is None:
            decisions.append(
                IntakeDecision(record_id, STATUS_MANUAL, None, "", None)
            )
            continue
        atom_id = generate_community_atom_id(candidate.summary, candidate.company_hash)
        if (
            (atom_id in blocked_rejected_ids or record_id in blocked_rejected_records)
            and parse_review_conclusion(record) != REVIEW_PASS
        ):
            decisions.append(
                IntakeDecision(
                    record_id,
                    STATUS_REJECTED_REVIEW,
                    None,
                    "",
                    None,
                    writeback_atom_id=atom_id,
                )
            )
            continue
        if atom_id in blocked_ids or record_id in blocked_records:
            if atom_id:
                blocked_ids.add(atom_id)
            if record_id:
                blocked_records.add(record_id)
            newly_revoked.append(
                RevokedAtom(
                    id=atom_id,
                    revoked_at=used_today.isoformat(),
                    reason=REASON_FEISHU,
                    record_id=record_id,
                )
            )
            decisions.append(
                IntakeDecision(
                    record_id,
                    STATUS_REVOKED,
                    None,
                    GIFT_REVOKED,
                    None,
                    writeback_atom_id=atom_id,
                )
            )
            continue
        pending.append((candidate, notes))

    record_to_atom: dict[str, str] = {}
    batch_atom_ids: set[str] = set()
    for candidate, _notes in pending:
        atom_id = generate_community_atom_id(candidate.summary, candidate.company_hash)
        batch_atom_ids.add(atom_id)
        if candidate.record_id:
            record_to_atom[candidate.record_id] = atom_id
    existing_atoms = tuple(atom for atom in existing_atoms if atom.id not in blocked_ids)
    existing_by_id = {atom.id: atom for atom in existing_atoms}
    locator_to_atom = {
        atom.source.locator: atom.id
        for atom in existing_atoms
        if atom.source.locator.startswith("rec")
    }
    known_atom_ids = set(existing_by_id) | batch_atom_ids

    confirm_by_record: dict[str, list[Confirmation]] = {}
    confirm_by_atom: dict[str, list[Confirmation]] = {}
    unresolved = 0
    for parsed in parsed_confirmations:
        if parsed is None:
            unresolved += 1
            continue
        target = resolve_confirmation_target(
            parsed,
            atom_ids=known_atom_ids,
            locator_to_atom=locator_to_atom,
            record_to_atom=record_to_atom,
        )
        pasted = normalize_atom_ref(parsed.pasted_atom_id)
        if (target and target in blocked_ids) or pasted in blocked_ids:
            continue
        if target is None:
            unresolved += 1
            continue
        record_for_atom = next(
            (rec for rec, atom_id in record_to_atom.items() if atom_id == target),
            "",
        )
        if record_for_atom:
            confirm_by_record.setdefault(record_for_atom, []).append(parsed.confirmation)
        else:
            confirm_by_atom.setdefault(target, []).append(parsed.confirmation)

    existing_pool = dict(existing_by_id)
    existing_confirmation_ids: list[str] = []
    for atom_id, extras in confirm_by_atom.items():
        current = existing_pool.get(atom_id)
        if current is None:
            continue
        existing_pool[atom_id] = _with_confirmations(current, extras)
        existing_confirmation_ids.append(atom_id)

    new_atoms: list[KnowledgeAtomV2] = []
    for candidate, notes in pending:
        extra_confirms = tuple(confirm_by_record.get(candidate.record_id, ()))
        atom = candidate_to_atom(
            candidate,
            extra_confirms,
            maintainers,
            today=used_today,
            review_notes=notes,
        )
        new_atoms.append(atom)
        decisions.append(
            IntakeDecision(
                candidate.record_id,
                "",
                atom,
                "",
                _created_hours(candidate.created_at, used_now),
            )
        )

    existing_atoms = tuple(existing_pool.values())
    existing_by_id = dict(existing_pool)
    result = dedupe(tuple(new_atoms), tuple(existing_atoms))
    final_atoms: dict[str, KnowledgeAtomV2] = dict(existing_by_id)
    final_atoms.update({atom.id: atom for atom in result.atoms})

    updated_existing: list[KnowledgeAtomV2] = []
    finalized_decisions: list[IntakeDecision] = []
    newly_rejected: list[RejectedAtom] = []
    reopened: set[str] = set()
    rejected_atom_ids: set[str] = set()
    for decision in decisions:
        if decision.status in {
            STATUS_MANUAL,
            STATUS_REJECTED,
            STATUS_REVOKED,
            STATUS_REJECTED_REVIEW,
        }:
            finalized_decisions.append(decision)
            continue
        assert decision.atom is not None
        atom_id = result.merged_into.get(decision.atom.id, decision.atom.id)
        atom = final_atoms[atom_id]
        source_record = records_by_id.get(decision.record_id, {})
        reviewed, status, rejected = apply_human_review(
            atom, source_record, today=used_today
        )
        if (
            status == STATUS_PENDING
            and atom.quality.review_status == "approved"
            and rejected is None
        ):
            reviewed, status = atom, STATUS_APPROVED
        if rejected is not None:
            newly_rejected.append(rejected)
            if rejected.id:
                rejected_atom_ids.add(rejected.id)
                blocked_ids.add(rejected.id)
            finalized_decisions.append(
                IntakeDecision(
                    decision.record_id,
                    STATUS_REJECTED_REVIEW,
                    None,
                    "",
                    decision.hours_to_publish,
                    writeback_atom_id=atom_id,
                )
            )
            continue
        assert reviewed is not None
        if status == STATUS_APPROVED:
            reopened.add(reviewed.id)
            if decision.record_id:
                reopened.add(decision.record_id)
        atom = flag_conflicts(
            reviewed,
            tuple(item for item in final_atoms.values() if item.id != reviewed.id),
        )
        final_atoms[atom.id] = atom
        if atom.id in existing_by_id:
            updated_existing.append(atom)
        scale = atom.scope.scale_band[0] if atom.scope.scale_band else "any"
        bench = ""
        if benchmark_index:
            bench = benchmark_index.get((atom.scope.industry, scale), "")
        gift = render_gift(atom, bench)
        finalized_decisions.append(
            IntakeDecision(decision.record_id, status, atom, gift, decision.hours_to_publish)
        )

    seen_updated = {item.id for item in updated_existing}
    for atom_id in existing_confirmation_ids:
        confirmed = final_atoms.get(atom_id)
        if confirmed is not None and confirmed.id not in seen_updated:
            updated_existing.append(confirmed)
            seen_updated.add(confirmed.id)

    approve_hours: list[float] = []
    for item in finalized_decisions:
        if item.status != STATUS_APPROVED or item.atom is None:
            continue
        reviewed_at = item.atom.quality.reviewed_at
        created = ""
        source_record = records_by_id.get(item.record_id, {})
        created = _get(_fields_of(source_record), "创建时间", "提交时间")
        hours = _created_hours(created, used_now) if created else item.hours_to_publish
        if reviewed_at:
            reviewed_hours = _created_hours(reviewed_at, used_now)
            created_hours = _created_hours(created, used_now) if created else None
            if created_hours is not None and reviewed_hours is not None:
                hours = max(0.0, created_hours - reviewed_hours)
        if hours is not None:
            approve_hours.append(hours)
    batch_ids = {
        item.atom.id
        for item in finalized_decisions
        if item.atom is not None and item.status in {STATUS_PENDING, STATUS_APPROVED}
    }
    metrics = {
        "submissions_total": len(records),
        "pending_total": sum(
            1 for item in finalized_decisions if item.status == STATUS_PENDING
        ),
        "approved_total": sum(
            1 for item in finalized_decisions if item.status == STATUS_APPROVED
        ),
        "rejected_total": sum(
            1
            for item in finalized_decisions
            if item.status in {STATUS_REJECTED, STATUS_REJECTED_REVIEW}
        ),
        "needs_manual": sum(
            1 for item in finalized_decisions if item.status == STATUS_MANUAL
        ),
        "median_hours_submit_to_approve": (
            round(float(median(approve_hours)), 2) if approve_hours else None
        ),
        "confirmations_unresolved": unresolved,
        "revoked": len({item.id or item.record_id for item in newly_revoked}),
    }
    return IntakeRun(
        decisions=tuple(finalized_decisions),
        atoms=tuple(
            atom
            for atom in final_atoms.values()
            if atom.id in batch_ids
            and atom.id not in blocked_ids
            and atom.id not in rejected_atom_ids
        ),
        existing_updated=tuple(
            atom
            for atom in updated_existing
            if atom.id not in blocked_ids and atom.id not in rejected_atom_ids
        ),
        metrics=metrics,
        revoked=tuple(newly_revoked),
        rejected=tuple(newly_rejected),
        reopened=tuple(reopened),
    )


def maybe_enrich(atom: KnowledgeAtomV2, environ: Mapping[str, str] | None = None) -> KnowledgeAtomV2:
    """可选 LLM 钩子。没有 SIYU_LLM_API_KEY 时原样返回。"""
    env = os.environ if environ is None else environ
    if not (env.get("SIYU_LLM_API_KEY") or "").strip():
        return atom
    return atom
