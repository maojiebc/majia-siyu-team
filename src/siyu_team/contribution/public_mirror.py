"""把已定级的社区投稿镜像到独立公开 Base。不含公司、联系方式、回礼。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Protocol, Sequence

from .intake import (
    PUBLIC_MIRROR_STATUSES,
    PUBLIC_REMOVE_STATUSES,
    SHANGHAI,
    TYPE_LABELS,
    IntakeDecision,
    _as_labels,
    _as_text,
    _fields_of,
    _get,
    _record_id,
    public_mirror_grade,
    independent_confirmation_count,
    parse_observed_date,
    public_display_name,
    redact_pii,
)
from .privacy import scan_fields

PUBLIC_SOURCE_FIELD = "来源记录"
PUBLIC_FORBIDDEN_FIELDS = frozenset({"公司/品牌", "联系方式", "回礼"})
BATCH_SIZE = 500
COPY_TEXT_FIELDS = (
    "这条属于",
    "业态",
    "细分",
    "经营模式",
    "门店数",
    "分公司层",
    "你的位置",
    "现在还有效吗",
)


class PublicTableClient(Protocol):
    def list_records(
        self,
        table_id: str,
        *,
        filter_expr: str | None = None,
        page_size: int = 500,
    ) -> list[dict[str, Any]]:
        ...

    def batch_create_records(
        self,
        table_id: str,
        records: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        ...

    def batch_update_records(
        self,
        table_id: str,
        records: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        ...

    def batch_delete_records(
        self,
        table_id: str,
        record_ids: Sequence[str],
    ) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class PublicMirrorPlan:
    creates: tuple[dict[str, Any], ...]
    updates: tuple[tuple[str, dict[str, Any]], ...]
    deletes: tuple[str, ...]
    skips: tuple[str, ...]

    def as_summary(self, *, dry_run: bool) -> dict[str, Any]:
        return {
            "create": [item.get(PUBLIC_SOURCE_FIELD) for item in self.creates],
            "update": [record_id for record_id, _fields in self.updates],
            "delete": list(self.deletes),
            "skip": list(self.skips),
            "dry_run": dry_run,
        }


def _date_ms(value: Any) -> int | None:
    parsed = parse_observed_date(_as_text(value))
    if not parsed:
        return None
    when = datetime.fromisoformat(parsed).replace(tzinfo=SHANGHAI)
    return int(when.timestamp() * 1000)


def _date_key(value: Any) -> str:
    return parse_observed_date(_as_text(value)) or ""


def _number_key(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    text = _as_text(value)
    if not text:
        return 0
    try:
        return int(float(text))
    except ValueError:
        return 0


def _safe_text(value: str) -> str:
    cleaned = redact_pii(value.strip())
    if not scan_fields((("public", cleaned),)).safe:
        return ""
    return cleaned


def _atom_evidence(decision: IntakeDecision) -> str:
    atom = decision.atom
    if atom is None or not atom.applicability.metrics:
        return ""
    return _safe_text(atom.applicability.metrics[0].definition)


def build_public_fields(
    decision: IntakeDecision,
    record: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    if decision.status in PUBLIC_REMOVE_STATUSES or decision.atom is None:
        return None
    if decision.status not in PUBLIC_MIRROR_STATUSES:
        return None
    atom = decision.atom
    fields = _fields_of(record or {})
    payload: dict[str, Any] = {
        "判断": _safe_text(atom.statement),
        "原子ID": decision.atom_id_for_writeback() or atom.id,
        "状态": decision.status,
        PUBLIC_SOURCE_FIELD: decision.record_id,
        "对外显示名": public_display_name(atom.source.contributor_display_name),
        "等级": public_mirror_grade(atom, decision.status),
        "印证数": independent_confirmation_count(atom),
        "数字/证据": _atom_evidence(decision),
    }
    for name in COPY_TEXT_FIELDS:
        text = _get(fields, name)
        if name == "细分":
            text = _safe_text(text)
        if text:
            payload[name] = text
    if "这条属于" not in payload:
        payload["这条属于"] = TYPE_LABELS.get(atom.type, "方法")
    channels = _as_labels(fields["主要私域载体"] if "主要私域载体" in fields else None)
    payload["主要私域载体"] = channels
    observed = _date_ms(_get(fields, "发现时间") or atom.source.observed_at)
    if observed is not None:
        payload["发现时间"] = observed
    submitted = _date_ms(_get(fields, "创建时间", "提交时间") or atom.source.observed_at)
    if submitted is not None:
        payload["提交时间"] = submitted
    for forbidden in PUBLIC_FORBIDDEN_FIELDS:
        payload.pop(forbidden, None)
    return payload


def canonical_public_fields(fields: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "判断": _as_text(fields.get("判断")),
        "原子ID": _as_text(fields.get("原子ID")),
        "状态": _as_text(fields.get("状态")),
        "这条属于": _as_text(fields.get("这条属于")),
        "业态": _as_text(fields.get("业态")),
        "细分": _as_text(fields.get("细分")),
        "经营模式": _as_text(fields.get("经营模式")),
        "门店数": _as_text(fields.get("门店数")),
        "分公司层": _as_text(fields.get("分公司层")),
        "你的位置": _as_text(fields.get("你的位置")),
        "主要私域载体": tuple(_as_labels(fields.get("主要私域载体"))),
        "数字/证据": _as_text(fields.get("数字/证据")),
        "发现时间": _date_key(fields.get("发现时间")),
        "现在还有效吗": _as_text(fields.get("现在还有效吗")),
        "提交时间": _date_key(fields.get("提交时间")),
        PUBLIC_SOURCE_FIELD: _as_text(fields.get(PUBLIC_SOURCE_FIELD)),
        "对外显示名": _as_text(fields.get("对外显示名")),
        "等级": _as_text(fields.get("等级")),
        "印证数": _number_key(fields.get("印证数")),
    }


def index_public_rows(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        fields = _fields_of(row)
        source = _as_text(fields.get(PUBLIC_SOURCE_FIELD))
        if source and source not in indexed:
            indexed[source] = dict(row)
    return indexed


def plan_public_mirror(
    decisions: Sequence[IntakeDecision],
    submissions: Sequence[Mapping[str, Any]],
    public_rows: Sequence[Mapping[str, Any]],
) -> PublicMirrorPlan:
    records_by_id = {
        _record_id(row): row
        for row in submissions
        if isinstance(row, Mapping) and _record_id(row)
    }
    existing = index_public_rows(public_rows)
    creates: list[dict[str, Any]] = []
    updates: list[tuple[str, dict[str, Any]]] = []
    deletes: list[str] = []
    skips: list[str] = []
    for decision in decisions:
        if not decision.record_id:
            continue
        desired = build_public_fields(decision, records_by_id.get(decision.record_id))
        current = existing.get(decision.record_id)
        public_id = ""
        if current:
            public_id = str(current.get("record_id") or current.get("recordId") or "")
        if desired is None:
            if public_id:
                deletes.append(public_id)
            else:
                skips.append(decision.record_id)
            continue
        if current is None or not public_id:
            creates.append(desired)
            continue
        if canonical_public_fields(desired) == canonical_public_fields(
            _fields_of(current)
        ):
            skips.append(decision.record_id)
            continue
        updates.append((public_id, desired))
    return PublicMirrorPlan(
        creates=tuple(creates),
        updates=tuple(updates),
        deletes=tuple(deletes),
        skips=tuple(skips),
    )


def _chunks(items: Sequence[Any], size: int = BATCH_SIZE) -> list[Sequence[Any]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def apply_public_mirror(
    client: PublicTableClient,
    table_id: str,
    plan: PublicMirrorPlan,
    *,
    dry_run: bool = False,
) -> PublicMirrorPlan:
    if dry_run:
        return plan
    for batch in _chunks(plan.creates):
        client.batch_create_records(
            table_id, [{"fields": dict(item)} for item in batch]
        )
    for batch in _chunks(plan.updates):
        client.batch_update_records(
            table_id,
            [
                {"record_id": record_id, "fields": dict(fields)}
                for record_id, fields in batch
            ],
        )
    for batch in _chunks(plan.deletes):
        client.batch_delete_records(table_id, list(batch))
    return plan


def mirror_public_table(
    *,
    decisions: Sequence[IntakeDecision],
    submissions: Sequence[Mapping[str, Any]],
    client: PublicTableClient,
    table_id: str,
    dry_run: bool = False,
) -> PublicMirrorPlan:
    rows = client.list_records(table_id)
    plan = plan_public_mirror(decisions, submissions, rows)
    return apply_public_mirror(client, table_id, plan, dry_run=dry_run)
