#!/usr/bin/env python3
"""每日社区语料 intake：飞书表单 → 校验/去重 → knowledge/05-community/。"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import os
import sys
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from siyu_team.connectors.base import ConnectorNotConfigured  # noqa: E402
from siyu_team.contribution.intake import (  # noqa: E402
    REASON_CLI,
    HashSaltError,
    RejectedAtom,
    RevokedAtom,
    hash_salt,
    independent_confirmation_count,
    intake_mode,
    load_rejected_entries,
    load_revoked_entries,
    maybe_enrich,
    merge_rejected,
    merge_revoked,
    run_intake,
    write_rejected_jsonl,
    write_revoked_jsonl,
    writeback_fields_changed,
)
from siyu_team.knowledge.models import KnowledgeAtomV2, KnowledgeValidationError  # noqa: E402

COMMUNITY_REL = Path("05-community")
PENDING = COMMUNITY_REL / "pending.jsonl"
APPROVED = COMMUNITY_REL / "approved.jsonl"
SEEDS = COMMUNITY_REL / "seeds.retail.jsonl"
REVOKED = COMMUNITY_REL / "revoked.jsonl"
REJECTED = COMMUNITY_REL / "rejected.jsonl"
MANIFEST = COMMUNITY_REL / "manifest.json"
LEGACY_ATOM_FILES = (
    COMMUNITY_REL / "inbox.jsonl",
    COMMUNITY_REL / "confirmed.jsonl",
    COMMUNITY_REL / "maintainer.jsonl",
)
WRITEBACK_FIELDS = ("状态", "原子ID", "回礼", "建议等级", "印证数")
PUBLIC_BASE_ENV = "LARK_PUBLIC_BASE_TOKEN"
PUBLIC_TABLE_ENV = "LARK_PUBLIC_TABLE"
MANIFEST_METRIC_KEYS = (
    "submissions_total",
    "pending_total",
    "approved_total",
    "rejected_total",
    "needs_manual",
    "median_hours_submit_to_approve",
    "confirmations_unresolved",
)


def _sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _read_jsonl(path: Path) -> list[KnowledgeAtomV2]:
    if not path.is_file():
        return []
    atoms: list[KnowledgeAtomV2] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            atoms.append(KnowledgeAtomV2.from_json(raw))
        except (KnowledgeValidationError, ValueError, TypeError) as exc:
            print(f"跳过 {path.name}:{line_no}：{exc}", file=sys.stderr)
    return atoms


def _write_jsonl(path: Path, atoms: Sequence[KnowledgeAtomV2]) -> bytes:
    ordered = sorted(atoms, key=lambda item: item.id)
    payload = (
        ("\n".join(atom.to_json() for atom in ordered) + "\n").encode("utf-8")
        if ordered
        else b""
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.read_bytes() == payload:
        return payload
    path.write_bytes(payload)
    return payload


def _same_atoms(
    left: Sequence[KnowledgeAtomV2], right: Sequence[KnowledgeAtomV2]
) -> bool:
    return {atom.id: atom.to_json() for atom in left} == {
        atom.id: atom.to_json() for atom in right
    }


def _write_jsonl_if_needed(
    path: Path,
    atoms: Sequence[KnowledgeAtomV2],
    previous: Sequence[KnowledgeAtomV2],
) -> tuple[bytes, bool]:
    """语义没变就不改文件；空且原本不存在则不创建。"""
    if _same_atoms(previous, atoms):
        if path.is_file():
            return path.read_bytes(), False
        return b"", False
    if not atoms and not path.is_file():
        return b"", False
    return _write_jsonl(path, atoms), True


def _load_tool(name: str) -> Any:
    path = ROOT / f"tools/{name}.py"
    spec = importlib.util.spec_from_file_location(f"siyu_{name}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _render_mod() -> Any:
    return _load_tool("render_benchmarks")


def _contributors_mod() -> Any:
    return _load_tool("render_contributors")


def _load_fixture(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload, []
    if not isinstance(payload, Mapping):
        raise ValueError("fixture 必须是对象或数组")
    submissions = payload.get("submissions") or payload.get("records") or []
    confirmations = payload.get("confirmations") or []
    if not isinstance(submissions, list) or not isinstance(confirmations, list):
        raise ValueError("fixture.submissions / confirmations 必须是数组")
    return submissions, confirmations


def _existing_pipeline_atoms(community_root: Path) -> list[KnowledgeAtomV2]:
    atoms: list[KnowledgeAtomV2] = []
    for relative in (PENDING, APPROVED, SEEDS, *LEGACY_ATOM_FILES):
        atoms.extend(_read_jsonl(community_root.parent / relative))
    return atoms


def _partition(atoms: Sequence[KnowledgeAtomV2]) -> dict[str, list[KnowledgeAtomV2]]:
    buckets: dict[str, list[KnowledgeAtomV2]] = {
        "pending": [],
        "approved": [],
        "seed": [],
    }
    for atom in atoms:
        if atom.source.source_type == "seed":
            buckets["seed"].append(atom)
        elif atom.quality.review_status == "approved":
            buckets["approved"].append(atom)
        else:
            buckets["pending"].append(atom)
    return buckets


def _merge_by_id(
    previous: Sequence[KnowledgeAtomV2],
    updated: Sequence[KnowledgeAtomV2],
) -> list[KnowledgeAtomV2]:
    by_id = {atom.id: atom for atom in previous}
    for atom in updated:
        by_id[atom.id] = atom
    return list(by_id.values())


def _manifest_metrics(metrics: Mapping[str, Any]) -> dict[str, Any]:
    payload = {key: metrics.get(key) for key in MANIFEST_METRIC_KEYS}
    if payload.get("confirmations_unresolved") is None:
        payload["confirmations_unresolved"] = 0
    return payload


def _write_manifest(
    path: Path,
    *,
    files: Mapping[str, tuple[int, str]],
    metrics: Mapping[str, Any],
    last_run: str,
) -> bool:
    file_meta = {
        name: {"atom_count": count, "sha256": digest}
        for name, (count, digest) in files.items()
    }
    metric_meta = _manifest_metrics(metrics)
    if path.is_file():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}
        if (
            isinstance(existing, Mapping)
            and existing.get("files") == file_meta
            and _manifest_metrics(existing.get("metrics") or {}) == metric_meta
        ):
            return False
    payload = {
        "last_run": last_run,
        "files": file_meta,
        "metrics": metric_meta,
    }
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.write_text(encoded, encoding="utf-8")
    return True


def _public_client(
    private_client: Any,
    environ: Mapping[str, str] | None = None,
) -> tuple[Any, str]:
    env = os.environ if environ is None else environ
    token = (env.get(PUBLIC_BASE_ENV) or "").strip()
    table = (env.get(PUBLIC_TABLE_ENV) or "").strip()
    if not token:
        print("notice: LARK_PUBLIC_BASE_TOKEN unset, skip public mirror")
        return None, ""
    if not table:
        print("notice: LARK_PUBLIC_TABLE unset, skip public mirror")
        return None, ""
    from siyu_team.connectors.lark import LarkBitable, LarkConfig

    if private_client is not None:
        config = LarkConfig(
            app_id=private_client.config.app_id,
            app_secret=private_client.config.app_secret,
            app_token=token,
            table_submissions=table,
            table_confirmations=private_client.config.table_confirmations or table,
        )
        public = LarkBitable(
            config,
            transport=private_client.transport,
            sleeper=private_client._sleeper,
        )
        public._token = private_client._token
        return public, table
    app_id = (env.get("LARK_APP_ID") or "").strip()
    app_secret = (env.get("LARK_APP_SECRET") or "").strip()
    if not app_id or not app_secret:
        print("notice: LARK_APP_ID unset, skip public mirror")
        return None, ""
    return LarkBitable.from_env(
        {
            "LARK_APP_ID": app_id,
            "LARK_APP_SECRET": app_secret,
            "LARK_BASE_APP_TOKEN": token,
            "LARK_TABLE_SUBMISSIONS": table,
            "LARK_TABLE_CONFIRMATIONS": table,
        }
    ), table


def _run_public_mirror(
    *,
    submissions: Sequence[Mapping[str, Any]],
    decisions: Sequence[Any],
    private_client: Any,
    dry_run: bool,
    public_client: Any = None,
    environ: Mapping[str, str] | None = None,
) -> Any:
    from siyu_team.contribution.public_mirror import mirror_public_table

    client = public_client
    table = ""
    if client is None:
        client, table = _public_client(private_client, environ)
    else:
        table = client.config.table_submissions
    if client is None:
        return None
    plan = mirror_public_table(
        decisions=decisions,
        submissions=submissions,
        client=client,
        table_id=table or client.config.table_submissions,
        dry_run=dry_run,
    )
    print(
        json.dumps(
            {"public_mirror": plan.as_summary(dry_run=dry_run)},
            ensure_ascii=False,
            indent=2,
        )
    )
    return plan


def _load_records(
    args: argparse.Namespace,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], Any]:
    if args.from_json:
        submissions, confirmations = _load_fixture(Path(args.from_json))
        return submissions, confirmations, None
    if not os.environ.get("LARK_APP_ID", "").strip():
        print("LARK_APP_ID 未设置，跳过飞书拉取。", file=sys.stderr)
        return [], [], None
    from siyu_team.connectors.lark import LarkBitable

    client = LarkBitable.from_env()
    return client.list_submissions(), client.list_confirmations(), client


def _write_community_state(
    knowledge_root: Path,
    *,
    previous_buckets: Mapping[str, Sequence[KnowledgeAtomV2]],
    atoms: Sequence[KnowledgeAtomV2],
    revoked_entries: Sequence[RevokedAtom],
    rejected_entries: Sequence[RejectedAtom] = (),
    metrics: Mapping[str, Any],
    last_run: str,
) -> None:
    buckets = _partition(atoms)
    file_meta: dict[str, tuple[int, str]] = {}
    targets = (
        (PENDING.name, "pending", knowledge_root / PENDING),
        (APPROVED.name, "approved", knowledge_root / APPROVED),
        (SEEDS.name, "seed", knowledge_root / SEEDS),
    )
    for name, key, path in targets:
        payload, _changed = _write_jsonl_if_needed(
            path, buckets[key], previous_buckets[key]
        )
        if payload or path.is_file():
            digest = _sha256_bytes(payload) if payload else _sha256_bytes(b"")
            file_meta[name] = (payload.count(b"\n") if payload else 0, digest)
    revoked_payload = write_revoked_jsonl(knowledge_root / REVOKED, revoked_entries)
    if revoked_payload or (knowledge_root / REVOKED).is_file():
        file_meta[REVOKED.name] = (
            revoked_payload.count(b"\n") if revoked_payload else 0,
            _sha256_bytes(revoked_payload) if revoked_payload else _sha256_bytes(b""),
        )
    rejected_payload = write_rejected_jsonl(knowledge_root / REJECTED, rejected_entries)
    if rejected_payload or (knowledge_root / REJECTED).is_file():
        file_meta[REJECTED.name] = (
            rejected_payload.count(b"\n") if rejected_payload else 0,
            _sha256_bytes(rejected_payload) if rejected_payload else _sha256_bytes(b""),
        )
    for stale in LEGACY_ATOM_FILES:
        stale_path = knowledge_root / stale
        if stale_path.is_file():
            stale_path.unlink()
    _write_manifest(
        knowledge_root / MANIFEST,
        files=file_meta,
        metrics=metrics,
        last_run=last_run,
    )
    try:
        _render_mod().render_benchmarks(knowledge_root)
    except Exception as exc:
        print(f"基线渲染跳过：{exc}", file=sys.stderr)
    try:
        _contributors_mod().render_contributors(knowledge_root)
    except Exception as exc:
        print(f"贡献者墙渲染跳过：{exc}", file=sys.stderr)


def _revoke_local(args: argparse.Namespace) -> int:
    from siyu_team.contribution.intake import normalize_atom_ref

    knowledge_root = Path(args.knowledge_root)
    atom_id = normalize_atom_ref(str(args.revoke or ""))
    if not atom_id:
        print("error: --revoke 需要原子 ID", file=sys.stderr)
        return 2
    existing = _existing_pipeline_atoms(knowledge_root / COMMUNITY_REL)
    previous_buckets = _partition(existing)
    previous_revoked = load_revoked_entries(knowledge_root / REVOKED)
    incoming = RevokedAtom(
        id=atom_id,
        revoked_at=date.today().isoformat(),
        reason=str(args.reason or REASON_CLI).strip() or REASON_CLI,
    )
    merged_revoked = merge_revoked(previous_revoked, (incoming,))
    blocked = {item.id for item in merged_revoked if item.id}
    kept = [atom for atom in existing if atom.id not in blocked]
    last_run = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    metrics = {
        "submissions_total": 0,
        "pending_total": 0,
        "approved_total": 0,
        "rejected_total": 0,
        "needs_manual": 0,
        "median_hours_submit_to_approve": None,
        "confirmations_unresolved": 0,
        "revoked": 1,
    }
    if not args.dry_run:
        _write_community_state(
            knowledge_root,
            previous_buckets=previous_buckets,
            atoms=kept,
            revoked_entries=merged_revoked,
            rejected_entries=load_rejected_entries(knowledge_root / REJECTED),
            metrics=metrics,
            last_run=last_run,
        )
    print(
        json.dumps(
            {
                "revoked": incoming.to_dict(),
                "removed": atom_id in {atom.id for atom in existing},
                "dry_run": bool(args.dry_run),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _resolve_salt(args: argparse.Namespace) -> str:
    if args.salt_for_tests:
        if not (args.dry_run and args.from_json):
            raise HashSaltError("--salt-for-tests 只能和 --dry-run --from-json 一起用")
        return str(args.salt_for_tests)
    return hash_salt()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="不回写飞书")
    parser.add_argument("--from-json", help="本地 fixture，不访问网络")
    parser.add_argument(
        "--salt-for-tests",
        default="",
        help="仅 --dry-run --from-json 可用的测试盐",
    )
    parser.add_argument(
        "--knowledge-root",
        default=str(ROOT / "knowledge"),
        help="知识真源根目录",
    )
    parser.add_argument("--revoke", default="", help="本地撤销原子 ID（不访问飞书）")
    parser.add_argument("--reason", default=REASON_CLI, help="--revoke 的原因")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.revoke:
        return _revoke_local(args)

    if not args.from_json and not os.environ.get("LARK_APP_ID", "").strip():
        print("notice: LARK_APP_ID unset, skip community intake")
        return 0

    try:
        used_salt = _resolve_salt(args)
    except HashSaltError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        submissions, confirmations, client = _load_records(args)
    except ConnectorNotConfigured as exc:
        print(f"notice: {exc}", file=sys.stderr)
        return 0

    knowledge_root = Path(args.knowledge_root)
    community_root = knowledge_root / COMMUNITY_REL
    existing = _existing_pipeline_atoms(community_root)
    previous_revoked = load_revoked_entries(knowledge_root / REVOKED)
    previous_rejected = load_rejected_entries(knowledge_root / REJECTED)
    previous_buckets = _partition(existing)
    try:
        benchmark_index = _render_mod().load_benchmark_index(knowledge_root)
    except Exception:
        benchmark_index = {}

    result = run_intake(
        submissions,
        confirmations,
        existing,
        salt=used_salt,
        benchmark_index=benchmark_index,
        today=date.today(),
        now=datetime.now(timezone.utc),
        mode=intake_mode(),
        revoked_ids=tuple(item.id for item in previous_revoked if item.id),
        revoked_record_ids=tuple(item.record_id for item in previous_revoked if item.record_id),
        rejected_ids=tuple(item.id for item in previous_rejected if item.id),
        rejected_record_ids=tuple(item.record_id for item in previous_rejected if item.record_id),
    )
    enriched = tuple(maybe_enrich(atom) for atom in result.atoms)
    summary = {
        "submissions_total": result.metrics["submissions_total"],
        "pending_total": result.metrics["pending_total"],
        "approved_total": result.metrics["approved_total"],
        "rejected_total": result.metrics["rejected_total"],
        "needs_manual": result.metrics["needs_manual"],
        "confirmations_unresolved": result.metrics["confirmations_unresolved"],
        "median_hours_submit_to_approve": result.metrics[
            "median_hours_submit_to_approve"
        ],
        "writebacks": [
            {
                "record_id": item.record_id,
                "status": item.status,
                "atom_id": item.atom_id_for_writeback() or None,
            }
            for item in result.decisions
        ],
        "intake_mode": intake_mode(),
        "revoked": result.metrics.get("revoked", 0),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    _run_public_mirror(
        submissions=submissions,
        decisions=result.decisions,
        private_client=client,
        dry_run=bool(args.dry_run),
    )
    if args.dry_run:
        return 0

    merged_revoked = merge_revoked(previous_revoked, result.revoked)
    reopened = set(result.reopened)
    merged_rejected = tuple(
        item
        for item in merge_rejected(previous_rejected, result.rejected)
        if item.id not in reopened and item.record_id not in reopened
    )
    blocked_ids = {item.id for item in merged_revoked if item.id}
    blocked_ids.update(item.id for item in merged_rejected if item.id)
    merged = [
        atom
        for atom in _merge_by_id(existing, (*enriched, *result.existing_updated))
        if atom.id not in blocked_ids
    ]
    _write_community_state(
        knowledge_root,
        previous_buckets=previous_buckets,
        atoms=merged,
        revoked_entries=merged_revoked,
        rejected_entries=merged_rejected,
        metrics=result.metrics,
        last_run=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

    if client is None:
        return 0

    from siyu_team.connectors.lark import LarkConfig

    table_id = client.config.table_submissions if isinstance(client.config, LarkConfig) else ""
    records_by_id = {
        str(row.get("record_id") or row.get("recordId") or ""): row
        for row in submissions
        if isinstance(row, Mapping)
    }
    for item in result.decisions:
        if not item.record_id:
            continue
        atom_id = item.atom_id_for_writeback()
        original = records_by_id.get(item.record_id, {})
        suggested = ""
        confirm_count = None
        if item.atom is not None:
            suggested = item.atom.quality.suggested_grade
            confirm_count = independent_confirmation_count(item.atom)
        if not writeback_fields_changed(
            original,
            item.status,
            atom_id,
            item.gift,
            suggested,
            confirm_count,
        ):
            continue
        payload: dict[str, Any] = {
            WRITEBACK_FIELDS[0]: item.status,
            WRITEBACK_FIELDS[1]: atom_id,
            WRITEBACK_FIELDS[2]: item.gift,
        }
        if suggested:
            payload[WRITEBACK_FIELDS[3]] = suggested
        if confirm_count is not None:
            payload[WRITEBACK_FIELDS[4]] = confirm_count
        client.update_record(table_id, item.record_id, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
