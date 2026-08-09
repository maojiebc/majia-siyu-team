"""KnowledgeAtomV2 数据契约。

本模块只负责可审计的数据结构、稳定 ID、序列化和校验；不负责检索、
审批、Runtime 注入或外部存储。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "2.0"
ATOM_TYPES = frozenset(
    {"principle", "method", "case", "anti-pattern", "insight", "tool", "compliance"}
)
SOURCE_TYPES = frozenset(
    {"official", "internal_case", "public_case", "expert_judgment", "legacy"}
)
VISIBILITIES = frozenset({"public", "expert_private", "client_private"})
EVIDENCE_GRADES = frozenset({"A1", "A2", "B1", "B2", "C1", "C2", "D"})
CONFIDENCE_LEVELS = frozenset({"high", "medium", "low"})
REVIEW_STATUSES = frozenset(
    {"draft", "in_review", "approved", "superseded", "retired", "rejected"}
)
_ATOM_ID = re.compile(r"ka_[0-9a-f]{16}")
_SOURCE_ID = re.compile(r"src_[0-9a-f]{12}")


class KnowledgeValidationError(ValueError):
    """知识对象违反 V2 契约。"""


def _clean_text(value: Any, name: str, *, required: bool = False) -> str:
    if not isinstance(value, str):
        raise KnowledgeValidationError(f"{name} 必须是字符串")
    cleaned = value.strip()
    if required and not cleaned:
        raise KnowledgeValidationError(f"{name} 不能为空")
    return cleaned


def _tuple_of_text(value: Any, name: str) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise KnowledgeValidationError(f"{name} 必须是字符串数组")
    result = tuple(_clean_text(item, name, required=True) for item in value)
    if len(set(result)) != len(result):
        raise KnowledgeValidationError(f"{name} 不能包含重复项")
    return result


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise KnowledgeValidationError(f"{name} 必须是对象")
    return value


def _check_keys(
    data: Mapping[str, Any],
    name: str,
    required: set[str],
    optional: set[str] | None = None,
) -> None:
    optional = optional or set()
    missing = required.difference(data)
    unknown = set(data).difference(required | optional)
    if missing:
        raise KnowledgeValidationError(f"{name} 缺少字段：{', '.join(sorted(missing))}")
    if unknown:
        raise KnowledgeValidationError(f"{name} 包含未知字段：{', '.join(sorted(unknown))}")


def _iso_date(value: Any, name: str, *, allow_empty: bool = True) -> str:
    cleaned = _clean_text(value, name)
    if not cleaned and allow_empty:
        return ""
    try:
        date.fromisoformat(cleaned)
    except ValueError as exc:
        raise KnowledgeValidationError(f"{name} 必须是 YYYY-MM-DD") from exc
    return cleaned


def _enum(value: Any, name: str, allowed: frozenset[str]) -> str:
    cleaned = _clean_text(value, name, required=True)
    if cleaned not in allowed:
        raise KnowledgeValidationError(
            f"{name} 必须是：{', '.join(sorted(allowed))}"
        )
    return cleaned


def _normalize_source_identity(source_identity: str | Path) -> str:
    raw = str(source_identity).strip()
    if not raw:
        raise KnowledgeValidationError("source identity 不能为空")
    expanded = Path(raw).expanduser()
    if expanded.is_absolute():
        return expanded.resolve(strict=False).as_posix()
    return PurePosixPath(raw.replace("\\", "/")).as_posix().casefold()


def generate_source_id(source_identity: str | Path) -> str:
    """从稳定的来源身份生成 source_id；不读取文件内容。"""
    normalized = _normalize_source_identity(source_identity)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
    return f"src_{digest}"


def generate_atom_id(source_id: str, locator: str, local_index: int) -> str:
    """从来源、定位和来源内序号生成稳定 Atom ID。"""
    if not _SOURCE_ID.fullmatch(source_id):
        raise KnowledgeValidationError("source_id 格式必须是 src_ + 12 位小写十六进制")
    if not isinstance(local_index, int) or isinstance(local_index, bool) or local_index < 0:
        raise KnowledgeValidationError("local_index 必须是非负整数")
    normalized_locator = " ".join(locator.strip().split())
    payload = f"{source_id}\n{normalized_locator}\n{local_index}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"ka_{digest}"


@dataclass(frozen=True)
class Metric:
    name: str
    definition: str
    time_window: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _clean_text(self.name, "metric.name", required=True))
        object.__setattr__(
            self,
            "definition",
            _clean_text(self.definition, "metric.definition", required=True),
        )
        object.__setattr__(
            self, "time_window", _clean_text(self.time_window, "metric.time_window")
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "definition": self.definition,
            "time_window": self.time_window,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Metric":
        _check_keys(data, "metric", {"name", "definition", "time_window"})
        return cls(str(data["name"]), str(data["definition"]), str(data["time_window"]))


@dataclass(frozen=True)
class SourceRef:
    source_id: str
    source_type: str
    label: str
    path: str
    locator: str
    observed_at: str

    def __post_init__(self) -> None:
        if not _SOURCE_ID.fullmatch(self.source_id):
            raise KnowledgeValidationError("source.source_id 格式非法")
        object.__setattr__(
            self, "source_type", _enum(self.source_type, "source.source_type", SOURCE_TYPES)
        )
        for name in ("label", "path", "locator"):
            object.__setattr__(
                self, name, _clean_text(getattr(self, name), f"source.{name}", required=True)
            )
        object.__setattr__(
            self, "observed_at", _iso_date(self.observed_at, "source.observed_at", allow_empty=False)
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "source_id": self.source_id,
            "source_type": self.source_type,
            "label": self.label,
            "path": self.path,
            "locator": self.locator,
            "observed_at": self.observed_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SourceRef":
        _check_keys(
            data,
            "source",
            {"source_id", "source_type", "label", "path", "locator", "observed_at"},
        )
        return cls(**{key: str(value) for key, value in data.items()})


@dataclass(frozen=True)
class Scope:
    visibility: str
    client_id: str = ""
    industry: str = ""
    subindustry: str = ""
    business_model: str = ""
    channels: tuple[str, ...] = ()
    lifecycle_stages: tuple[str, ...] = ()
    roles: tuple[str, ...] = ()
    scenarios: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "visibility", _enum(self.visibility, "scope.visibility", VISIBILITIES)
        )
        for name in ("client_id", "industry", "subindustry", "business_model"):
            object.__setattr__(
                self, name, _clean_text(getattr(self, name), f"scope.{name}").lower()
            )
        for name in ("channels", "lifecycle_stages", "roles", "scenarios"):
            object.__setattr__(
                self, name, _tuple_of_text(getattr(self, name), f"scope.{name}")
            )
        if self.visibility == "client_private" and not self.client_id:
            raise KnowledgeValidationError("client_private 知识必须设置 scope.client_id")
        if self.visibility != "client_private" and self.client_id:
            raise KnowledgeValidationError("只有 client_private 知识可以设置 scope.client_id")

    def to_dict(self) -> dict[str, Any]:
        return {
            "visibility": self.visibility,
            "client_id": self.client_id,
            "industry": self.industry,
            "subindustry": self.subindustry,
            "business_model": self.business_model,
            "channels": list(self.channels),
            "lifecycle_stages": list(self.lifecycle_stages),
            "roles": list(self.roles),
            "scenarios": list(self.scenarios),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Scope":
        fields = {
            "visibility", "client_id", "industry", "subindustry", "business_model",
            "channels", "lifecycle_stages", "roles", "scenarios",
        }
        _check_keys(data, "scope", fields)
        return cls(
            visibility=str(data["visibility"]),
            client_id=str(data["client_id"]),
            industry=str(data["industry"]),
            subindustry=str(data["subindustry"]),
            business_model=str(data["business_model"]),
            channels=_tuple_of_text(data["channels"], "scope.channels"),
            lifecycle_stages=_tuple_of_text(data["lifecycle_stages"], "scope.lifecycle_stages"),
            roles=_tuple_of_text(data["roles"], "scope.roles"),
            scenarios=_tuple_of_text(data["scenarios"], "scope.scenarios"),
        )


@dataclass(frozen=True)
class Applicability:
    preconditions: tuple[str, ...] = ()
    recommended_action: tuple[str, ...] = ()
    metrics: tuple[Metric, ...] = ()
    failure_modes: tuple[str, ...] = ()
    counterexamples: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("preconditions", "recommended_action", "failure_modes", "counterexamples"):
            object.__setattr__(
                self, name, _tuple_of_text(getattr(self, name), f"applicability.{name}")
            )
        converted: list[Metric] = []
        for metric in self.metrics:
            if not isinstance(metric, Metric):
                raise KnowledgeValidationError("applicability.metrics 必须包含 Metric")
            converted.append(metric)
        object.__setattr__(self, "metrics", tuple(converted))

    def to_dict(self) -> dict[str, Any]:
        return {
            "preconditions": list(self.preconditions),
            "recommended_action": list(self.recommended_action),
            "metrics": [metric.to_dict() for metric in self.metrics],
            "failure_modes": list(self.failure_modes),
            "counterexamples": list(self.counterexamples),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Applicability":
        fields = {"preconditions", "recommended_action", "metrics", "failure_modes", "counterexamples"}
        _check_keys(data, "applicability", fields)
        metrics = data["metrics"]
        if isinstance(metrics, str) or not isinstance(metrics, Sequence):
            raise KnowledgeValidationError("applicability.metrics 必须是对象数组")
        return cls(
            preconditions=_tuple_of_text(data["preconditions"], "applicability.preconditions"),
            recommended_action=_tuple_of_text(data["recommended_action"], "applicability.recommended_action"),
            metrics=tuple(Metric.from_dict(_mapping(item, "metric")) for item in metrics),
            failure_modes=_tuple_of_text(data["failure_modes"], "applicability.failure_modes"),
            counterexamples=_tuple_of_text(data["counterexamples"], "applicability.counterexamples"),
        )


@dataclass(frozen=True)
class Quality:
    evidence_grade: str
    confidence: str
    review_status: str
    reviewer: str = ""
    reviewed_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "evidence_grade", _enum(self.evidence_grade, "quality.evidence_grade", EVIDENCE_GRADES)
        )
        object.__setattr__(
            self, "confidence", _enum(self.confidence, "quality.confidence", CONFIDENCE_LEVELS)
        )
        object.__setattr__(
            self, "review_status", _enum(self.review_status, "quality.review_status", REVIEW_STATUSES)
        )
        object.__setattr__(self, "reviewer", _clean_text(self.reviewer, "quality.reviewer"))
        object.__setattr__(
            self, "reviewed_at", _iso_date(self.reviewed_at, "quality.reviewed_at")
        )
        if self.review_status == "approved" and (not self.reviewer or not self.reviewed_at):
            raise KnowledgeValidationError("approved 知识必须有 reviewer 和 reviewed_at")

    def to_dict(self) -> dict[str, str]:
        return {
            "evidence_grade": self.evidence_grade,
            "confidence": self.confidence,
            "review_status": self.review_status,
            "reviewer": self.reviewer,
            "reviewed_at": self.reviewed_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Quality":
        fields = {"evidence_grade", "confidence", "review_status", "reviewer", "reviewed_at"}
        _check_keys(data, "quality", fields)
        return cls(**{key: str(value) for key, value in data.items()})


@dataclass(frozen=True)
class Lifecycle:
    valid_from: str
    valid_until: str = ""
    supersedes: tuple[str, ...] = ()
    contradicts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "valid_from", _iso_date(self.valid_from, "lifecycle.valid_from", allow_empty=False)
        )
        object.__setattr__(
            self, "valid_until", _iso_date(self.valid_until, "lifecycle.valid_until")
        )
        for name in ("supersedes", "contradicts"):
            values = _tuple_of_text(getattr(self, name), f"lifecycle.{name}")
            if any(not _ATOM_ID.fullmatch(value) for value in values):
                raise KnowledgeValidationError(f"lifecycle.{name} 包含非法 Atom ID")
            object.__setattr__(self, name, values)
        if self.valid_until and self.valid_until < self.valid_from:
            raise KnowledgeValidationError("valid_until 不能早于 valid_from")

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid_from": self.valid_from,
            "valid_until": self.valid_until or None,
            "supersedes": list(self.supersedes),
            "contradicts": list(self.contradicts),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Lifecycle":
        fields = {"valid_from", "valid_until", "supersedes", "contradicts"}
        _check_keys(data, "lifecycle", fields)
        valid_until = data["valid_until"]
        if valid_until is not None and not isinstance(valid_until, str):
            raise KnowledgeValidationError("lifecycle.valid_until 必须是日期或 null")
        return cls(
            valid_from=str(data["valid_from"]),
            valid_until=str(valid_until or ""),
            supersedes=_tuple_of_text(data["supersedes"], "lifecycle.supersedes"),
            contradicts=_tuple_of_text(data["contradicts"], "lifecycle.contradicts"),
        )


@dataclass(frozen=True)
class Privacy:
    contains_pii: bool = False
    contains_client_secret: bool = False
    exportable: bool = False

    def __post_init__(self) -> None:
        for name in ("contains_pii", "contains_client_secret", "exportable"):
            if not isinstance(getattr(self, name), bool):
                raise KnowledgeValidationError(f"privacy.{name} 必须是布尔值")
        if self.exportable and (self.contains_pii or self.contains_client_secret):
            raise KnowledgeValidationError(
                "含 PII 或客户秘密的知识禁止 exportable=true"
            )

    def to_dict(self) -> dict[str, bool]:
        return {
            "contains_pii": self.contains_pii,
            "contains_client_secret": self.contains_client_secret,
            "exportable": self.exportable,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Privacy":
        fields = {"contains_pii", "contains_client_secret", "exportable"}
        _check_keys(data, "privacy", fields)
        return cls(**{key: value for key, value in data.items()})


@dataclass(frozen=True)
class KnowledgeAtomV2:
    id: str
    statement: str
    type: str
    topics: tuple[str, ...]
    skills: tuple[str, ...]
    source: SourceRef
    scope: Scope
    applicability: Applicability
    quality: Quality
    lifecycle: Lifecycle
    privacy: Privacy
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise KnowledgeValidationError(f"不支持 schema_version={self.schema_version!r}")
        if not _ATOM_ID.fullmatch(self.id):
            raise KnowledgeValidationError("id 格式必须是 ka_ + 16 位小写十六进制")
        object.__setattr__(self, "statement", _clean_text(self.statement, "statement", required=True))
        object.__setattr__(self, "type", _enum(self.type, "type", ATOM_TYPES))
        object.__setattr__(self, "topics", _tuple_of_text(self.topics, "topics"))
        object.__setattr__(self, "skills", _tuple_of_text(self.skills, "skills"))
        for name, expected in (
            ("source", SourceRef), ("scope", Scope), ("applicability", Applicability),
            ("quality", Quality), ("lifecycle", Lifecycle), ("privacy", Privacy),
        ):
            if not isinstance(getattr(self, name), expected):
                raise KnowledgeValidationError(f"{name} 类型非法")
        if self.scope.visibility != "public" and self.privacy.exportable:
            raise KnowledgeValidationError("只有 public 知识可以 exportable=true")
        if self.scope.visibility == "client_private" and self.privacy.exportable:
            raise KnowledgeValidationError("客户私有知识禁止导出")
        if self.privacy.exportable and (
            self.privacy.contains_pii or self.privacy.contains_client_secret
        ):
            # Privacy 自身已经 fail-closed；这里保留跨对象不变量，
            # 防止未来 Privacy 的构造方式变化后 Atom 层失守。
            raise KnowledgeValidationError(
                "含 PII 或客户秘密的知识禁止 exportable=true"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "statement": self.statement,
            "type": self.type,
            "topics": list(self.topics),
            "skills": list(self.skills),
            "source": self.source.to_dict(),
            "scope": self.scope.to_dict(),
            "applicability": self.applicability.to_dict(),
            "quality": self.quality.to_dict(),
            "lifecycle": self.lifecycle.to_dict(),
            "privacy": self.privacy.to_dict(),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "KnowledgeAtomV2":
        required = {
            "schema_version", "id", "statement", "type", "topics", "skills", "source",
            "scope", "applicability", "quality", "lifecycle", "privacy",
        }
        _check_keys(data, "atom", required)
        return cls(
            schema_version=str(data["schema_version"]),
            id=str(data["id"]),
            statement=str(data["statement"]),
            type=str(data["type"]),
            topics=_tuple_of_text(data["topics"], "topics"),
            skills=_tuple_of_text(data["skills"], "skills"),
            source=SourceRef.from_dict(_mapping(data["source"], "source")),
            scope=Scope.from_dict(_mapping(data["scope"], "scope")),
            applicability=Applicability.from_dict(_mapping(data["applicability"], "applicability")),
            quality=Quality.from_dict(_mapping(data["quality"], "quality")),
            lifecycle=Lifecycle.from_dict(_mapping(data["lifecycle"], "lifecycle")),
            privacy=Privacy.from_dict(_mapping(data["privacy"], "privacy")),
        )

    @classmethod
    def from_json(cls, payload: str) -> "KnowledgeAtomV2":
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise KnowledgeValidationError(f"Atom JSON 非法：{exc.msg}") from exc
        return cls.from_dict(_mapping(data, "atom"))


def migrate_v1_atom(
    data: Mapping[str, Any],
    *,
    local_index: int = 0,
    source_identity: str | Path | None = None,
) -> KnowledgeAtomV2:
    """把单条旧示例迁移成安全的 V2 draft；不自动批准或导出。"""
    required = {"id", "knowledge", "original", "source", "date", "topics", "skills", "type", "confidence"}
    _check_keys(data, "v1 atom", required)
    source_path = _clean_text(data["source"], "source", required=True)
    identity = source_identity if source_identity is not None else source_path
    source_id = generate_source_id(identity)
    locator = f"legacy:{_clean_text(data['id'], 'id', required=True)}"
    statement = _clean_text(data["knowledge"], "knowledge") or _clean_text(
        data["original"], "original", required=True
    )
    observed_at = _iso_date(data["date"], "date", allow_empty=False)
    atom_type = str(data["type"])
    if atom_type not in ATOM_TYPES:
        atom_type = "insight"
    confidence = str(data["confidence"])
    if confidence not in CONFIDENCE_LEVELS:
        confidence = "low"
    return KnowledgeAtomV2(
        id=generate_atom_id(source_id, locator, local_index),
        statement=statement,
        type=atom_type,
        topics=_tuple_of_text(data["topics"], "topics"),
        skills=_tuple_of_text(data["skills"], "skills"),
        source=SourceRef(
            source_id=source_id,
            source_type="legacy",
            label=Path(source_path).name,
            path=source_path,
            locator=locator,
            observed_at=observed_at,
        ),
        scope=Scope(visibility="public"),
        applicability=Applicability(),
        quality=Quality(
            evidence_grade="D",
            confidence=confidence,
            review_status="draft",
        ),
        lifecycle=Lifecycle(valid_from=observed_at),
        privacy=Privacy(exportable=False),
    )
