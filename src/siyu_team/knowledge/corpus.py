"""公开批准知识库的严格加载契约。

``CorpusLoader`` 是生产读取入口：manifest、原始文件哈希、
数量和 Atom Schema 任一不一致都 fail-closed。``lenient`` 只允许
跳过无法解析的单行，不会关闭哈希、重复 ID 或安全门。
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence

from ..errors import KnowledgeLoadError
from .models import (
    SCHEMA_VERSION,
    KnowledgeAtomV2,
    KnowledgeValidationError,
)
from .paths import (
    GROWTH_ATOMS_APPROVED,
    PUBLIC_MANIFEST,
    KnowledgePathResolver,
)


_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")
_MANIFEST_REQUIRED = frozenset(
    {
        "corpus_version",
        "release_batch",
        "corpus_hash",
        "atom_count",
        "atom_schema_version",
        "public_corpora",
    }
)
_METRIC_NOT_APPLICABLE_PREFIXES = (
    "metric:not_applicable",
    "metrics:not_applicable",
    "metric_not_applicable:",
    "指标不适用：",
    "验证指标不适用：",
)


def _required_text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise KnowledgeLoadError(f"{name} 必须是非空字符串")
    return value.strip()


def _validated_hash(value: Any, name: str = "corpus_hash") -> str:
    digest = _required_text(value, name)
    if not _SHA256.fullmatch(digest):
        raise KnowledgeLoadError(f"{name} 必须是 sha256: + 64 位小写十六进制")
    return digest


def _raw_sha256(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _canonical_jsonl(atoms: Sequence[KnowledgeAtomV2]) -> bytes:
    if not atoms:
        return b""
    return ("\n".join(atom.to_json() for atom in atoms) + "\n").encode("utf-8")


@dataclass(frozen=True)
class CorpusMetadata:
    corpus_version: str
    release_batch: str
    corpus_hash: str
    atom_count: int
    atom_schema_version: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "corpus_version",
            _required_text(self.corpus_version, "corpus_version"),
        )
        object.__setattr__(
            self,
            "release_batch",
            _required_text(self.release_batch, "release_batch"),
        )
        object.__setattr__(
            self,
            "corpus_hash",
            _validated_hash(self.corpus_hash),
        )
        if (
            not isinstance(self.atom_count, int)
            or isinstance(self.atom_count, bool)
            or self.atom_count < 0
        ):
            raise KnowledgeLoadError("atom_count 必须是非负整数")
        object.__setattr__(
            self,
            "atom_schema_version",
            _required_text(self.atom_schema_version, "atom_schema_version"),
        )

    def to_dict(self) -> dict[str, str | int]:
        return {
            "corpus_version": self.corpus_version,
            "release_batch": self.release_batch,
            "corpus_hash": self.corpus_hash,
            "atom_count": self.atom_count,
            "atom_schema_version": self.atom_schema_version,
        }


@dataclass(frozen=True)
class Corpus:
    metadata: CorpusMetadata
    atoms: tuple[KnowledgeAtomV2, ...]
    source_path: Path | None = None
    manifest_path: Path | None = None
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.metadata, CorpusMetadata):
            raise KnowledgeLoadError("metadata 必须是 CorpusMetadata")
        atoms = tuple(self.atoms)
        for atom in atoms:
            if not isinstance(atom, KnowledgeAtomV2):
                raise KnowledgeLoadError("Corpus.atoms 必须只包含 KnowledgeAtomV2")
            if atom.schema_version != self.metadata.atom_schema_version:
                raise KnowledgeLoadError(
                    f"Atom {atom.id} schema_version 与 corpus manifest 不一致"
                )
        duplicate_ids = sorted(
            atom_id
            for atom_id, count in Counter(atom.id for atom in atoms).items()
            if count > 1
        )
        if duplicate_ids:
            raise KnowledgeLoadError(
                "Corpus 包含重复 atom_id：" + ", ".join(duplicate_ids)
            )
        warnings = tuple(self.warnings)
        if any(not isinstance(item, str) or not item for item in warnings):
            raise KnowledgeLoadError("Corpus.warnings 必须是非空字符串数组")
        object.__setattr__(self, "atoms", atoms)
        object.__setattr__(self, "warnings", warnings)
        if self.source_path is not None:
            object.__setattr__(self, "source_path", Path(self.source_path))
        if self.manifest_path is not None:
            object.__setattr__(self, "manifest_path", Path(self.manifest_path))

    @property
    def corpus_version(self) -> str:
        return self.metadata.corpus_version

    @property
    def corpus_hash(self) -> str:
        return self.metadata.corpus_hash

    @property
    def selection_count(self) -> int:
        return len(self.atoms)

    @classmethod
    def empty(cls) -> "Corpus":
        """表示所有合法来源都不存在，便于 Runtime 明确降级。"""
        return cls(
            metadata=CorpusMetadata(
                corpus_version="unavailable",
                release_batch="unavailable",
                corpus_hash=_raw_sha256(b""),
                atom_count=0,
                atom_schema_version=SCHEMA_VERSION,
            ),
            atoms=(),
            warnings=("current_no_available_public_corpus",),
        )

    @classmethod
    def from_atoms(
        cls,
        atoms: Iterable[KnowledgeAtomV2],
        *,
        corpus_version: str = "test",
        release_batch: str = "test",
        atom_schema_version: str = SCHEMA_VERSION,
        warnings: Iterable[str] = (),
    ) -> "Corpus":
        """从内存 Atom 构造可重现 Corpus，主要用于测试夹具。

        生产读取不得用此方法绕过 manifest，必须调用
        :class:`CorpusLoader`。该辅助仍会检查 Schema 和重复 ID。
        """
        materialized = tuple(atoms)
        raw = _canonical_jsonl(materialized)
        metadata = CorpusMetadata(
            corpus_version=corpus_version,
            release_batch=release_batch,
            corpus_hash=_raw_sha256(raw),
            atom_count=len(materialized),
            atom_schema_version=atom_schema_version,
        )
        return cls(metadata, materialized, warnings=tuple(warnings))


class CorpusLoader:
    """发现并严格加载公开 approved Corpus。"""

    def __init__(
        self,
        resolver: KnowledgePathResolver | None = None,
        *,
        today: date | None = None,
        lenient: bool = False,
    ) -> None:
        if today is not None and not isinstance(today, date):
            raise TypeError("today 必须是 datetime.date")
        if not isinstance(lenient, bool):
            raise TypeError("lenient 必须是 bool")
        self.resolver = resolver or KnowledgePathResolver()
        self.today = today or date.today()
        self.lenient = lenient

    def load(
        self,
        path: str | Path | None = None,
        *,
        manifest_path: str | Path | None = None,
    ) -> Corpus:
        """加载显式文件，或按 resolver 优先级发现正式集。"""
        resolved = self._resolve_paths(path, manifest_path)
        if resolved is None:
            return Corpus.empty()
        corpus_path, resolved_manifest = resolved
        metadata, descriptor = self._read_manifest(
            resolved_manifest,
            corpus_path,
        )
        raw = self._read_bytes(corpus_path)
        actual_hash = _raw_sha256(raw)
        if actual_hash != metadata.corpus_hash:
            raise KnowledgeLoadError(
                f"corpus hash 不一致：manifest={metadata.corpus_hash}，"
                f"actual={actual_hash}"
            )
        self._validate_descriptor(descriptor, metadata, actual_hash)
        atoms, warnings = self._parse_atoms(raw, corpus_path, metadata)
        selected, filter_warnings = self._select_public_atoms(atoms)
        return Corpus(
            metadata=metadata,
            atoms=selected,
            source_path=corpus_path,
            manifest_path=resolved_manifest,
            warnings=warnings + filter_warnings,
        )

    def load_public(
        self,
        path: str | Path | None = None,
        *,
        manifest_path: str | Path | None = None,
    ) -> Corpus:
        """``load`` 的语义化别名，便于调用方表达公开加载。"""
        return self.load(path, manifest_path=manifest_path)

    def load_from_root(self, root: str | Path) -> Corpus:
        """从一个明确的 knowledge 根目录加载默认正式集。"""
        knowledge_root = Path(root).expanduser().resolve(strict=False)
        return self.load(
            knowledge_root / GROWTH_ATOMS_APPROVED,
            manifest_path=knowledge_root / PUBLIC_MANIFEST,
        )

    def _resolve_paths(
        self,
        path: str | Path | None,
        manifest_path: str | Path | None,
    ) -> tuple[Path, Path] | None:
        if path is None:
            if manifest_path is not None:
                raise KnowledgeLoadError("manifest_path 不能在未指定 corpus path 时单独使用")
            discovered = self._discover()
            if discovered is None:
                # “没有候选”是可解释的降级态，不是损坏；一旦候选
                # 存在，后续 manifest/hash/schema 的任何违约仍会抛错。
                return None
            return discovered

        corpus_path = Path(path).expanduser().resolve(strict=False)
        if corpus_path.is_dir():
            root = corpus_path
            corpus_path = root / GROWTH_ATOMS_APPROVED
            default_manifest = root / PUBLIC_MANIFEST
        else:
            default_manifest = self._manifest_for_explicit(corpus_path)
        resolved_manifest = (
            Path(manifest_path).expanduser().resolve(strict=False)
            if manifest_path is not None
            else default_manifest
        )
        if not corpus_path.is_file():
            raise KnowledgeLoadError(f"公开批准知识库不存在：{corpus_path}")
        if not resolved_manifest.is_file():
            raise KnowledgeLoadError(f"知识 manifest 不存在：{resolved_manifest}")
        return corpus_path, resolved_manifest

    def _discover(self) -> tuple[Path, Path] | None:
        # 先按固定 approved 路径遍历所有 root。候选列表中没有
        # draft，因此高优先级 root 里的 draft 不可能遮蔽低级 approved。
        pairs = self.resolver.approved_corpus_candidates()
        for corpus_path, manifest_path in pairs:
            if corpus_path.is_file():
                return corpus_path.resolve(strict=False), manifest_path.resolve(strict=False)

            declared = self._discover_declared_approved(manifest_path)
            if declared is not None:
                return declared, manifest_path.resolve(strict=False)
        return None

    def _discover_declared_approved(self, manifest_path: Path) -> Path | None:
        if not manifest_path.is_file():
            return None
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            # 只有已知的 approved 文件存在时，才让后续正式读取
            # 报出 manifest 错误；单独的坏 manifest 不遮蔽低优先级正式集。
            atom_dir = manifest_path.parent / "04-atoms"
            matches = sorted(atom_dir.glob("*.approved.jsonl"))
            return matches[0].resolve(strict=False) if matches else None
        if not isinstance(payload, Mapping):
            return None
        public_corpora = payload.get("public_corpora", ())
        if isinstance(public_corpora, (str, bytes)) or not isinstance(
            public_corpora, Sequence
        ):
            return None
        for entry in public_corpora:
            relative = self._descriptor_path(entry, strict=False)
            if relative is None:
                continue
            candidate = manifest_path.parent / relative
            if candidate.is_file():
                return candidate.resolve(strict=False)
        return None

    def _manifest_for_explicit(self, corpus_path: Path) -> Path:
        for root in self.resolver.candidates():
            normalized_root = root.resolve(strict=False)
            try:
                corpus_path.relative_to(normalized_root)
            except ValueError:
                continue
            return normalized_root / PUBLIC_MANIFEST
        if corpus_path.parent.name == "04-atoms":
            return corpus_path.parent.parent / PUBLIC_MANIFEST
        return corpus_path.parent / PUBLIC_MANIFEST

    def _read_manifest(
        self,
        manifest_path: Path,
        corpus_path: Path,
    ) -> tuple[CorpusMetadata, Mapping[str, Any]]:
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise KnowledgeLoadError(f"manifest 读取失败：{manifest_path}（{exc}）") from exc
        except UnicodeDecodeError as exc:
            raise KnowledgeLoadError(f"manifest 不是 UTF-8：{manifest_path}") from exc
        except json.JSONDecodeError as exc:
            raise KnowledgeLoadError(
                f"manifest JSON 非法：{manifest_path}:{exc.lineno}:{exc.colno}"
            ) from exc
        if not isinstance(payload, Mapping):
            raise KnowledgeLoadError("manifest 顶层必须是对象")
        missing = sorted(_MANIFEST_REQUIRED.difference(payload))
        if missing:
            raise KnowledgeLoadError("manifest 缺少字段：" + ", ".join(missing))
        metadata = CorpusMetadata(
            corpus_version=payload["corpus_version"],
            release_batch=payload["release_batch"],
            corpus_hash=payload["corpus_hash"],
            atom_count=payload["atom_count"],
            atom_schema_version=payload["atom_schema_version"],
        )
        public_corpora = payload["public_corpora"]
        if isinstance(public_corpora, (str, bytes)) or not isinstance(
            public_corpora, Sequence
        ):
            raise KnowledgeLoadError("manifest.public_corpora 必须是数组")

        root = manifest_path.parent.resolve(strict=False)
        resolved_corpus = corpus_path.resolve(strict=False)
        try:
            selected_relative = resolved_corpus.relative_to(root).as_posix()
        except ValueError as exc:
            raise KnowledgeLoadError("corpus path 必须位于 manifest knowledge root 内") from exc

        selected_descriptor: Mapping[str, Any] | None = None
        for entry in public_corpora:
            relative = self._descriptor_path(entry, strict=True)
            if relative != selected_relative:
                continue
            selected_descriptor = (
                entry if isinstance(entry, Mapping) else {"path": relative}
            )
            break
        if selected_descriptor is None:
            raise KnowledgeLoadError(
                f"manifest.public_corpora 未声明正式集：{selected_relative}"
            )
        return metadata, selected_descriptor

    def _descriptor_path(self, entry: Any, *, strict: bool) -> str | None:
        value: Any
        if isinstance(entry, str):
            value = entry
        elif isinstance(entry, Mapping):
            value = entry.get("path")
        else:
            if strict:
                raise KnowledgeLoadError(
                    "manifest.public_corpora 成员必须是路径字符串或对象"
                )
            return None
        if not isinstance(value, str) or not value.strip():
            if strict:
                raise KnowledgeLoadError("public corpus descriptor.path 必须是非空字符串")
            return None
        normalized = value.replace("\\", "/").strip("/")
        relative = Path(normalized)
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or ".approved." not in relative.name
        ):
            if strict:
                raise KnowledgeLoadError(
                    "manifest.public_corpora 只能声明 knowledge root 内的 approved 文件"
                )
            return None
        return relative.as_posix()

    def _validate_descriptor(
        self,
        descriptor: Mapping[str, Any],
        metadata: CorpusMetadata,
        actual_hash: str,
    ) -> None:
        hash_value = descriptor.get("sha256", descriptor.get("corpus_hash"))
        if hash_value is not None and _validated_hash(
            hash_value, "public_corpora.sha256"
        ) != actual_hash:
            raise KnowledgeLoadError("public corpus descriptor sha256 与原始文件不一致")
        expected_values: tuple[tuple[str, Any], ...] = (
            ("corpus_version", metadata.corpus_version),
            ("release_batch", metadata.release_batch),
            ("atom_count", metadata.atom_count),
            ("schema_version", metadata.atom_schema_version),
            ("atom_schema_version", metadata.atom_schema_version),
        )
        for field, expected in expected_values:
            if field in descriptor and descriptor[field] != expected:
                raise KnowledgeLoadError(
                    f"public corpus descriptor.{field} 与 manifest 顶层不一致"
                )

    def _read_bytes(self, path: Path) -> bytes:
        try:
            return path.read_bytes()
        except OSError as exc:
            raise KnowledgeLoadError(f"corpus 读取失败：{path}（{exc}）") from exc

    def _parse_atoms(
        self,
        raw: bytes,
        path: Path,
        metadata: CorpusMetadata,
    ) -> tuple[tuple[KnowledgeAtomV2, ...], tuple[str, ...]]:
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise KnowledgeLoadError(f"corpus 不是 UTF-8：{path}") from exc
        records = [
            (line_no, line.strip())
            for line_no, line in enumerate(text.splitlines(), 1)
            if line.strip()
        ]
        if len(records) != metadata.atom_count:
            raise KnowledgeLoadError(
                f"atom_count 不一致：manifest={metadata.atom_count}，"
                f"raw_records={len(records)}"
            )

        atoms: list[KnowledgeAtomV2] = []
        warnings: list[str] = []
        seen_raw_ids: set[str] = set()
        for line_no, line in records:
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError as exc:
                if self.lenient:
                    warnings.append(
                        f"malformed_skipped:{path.name}:{line_no}:json:{exc.msg}"
                    )
                    continue
                raise KnowledgeLoadError(
                    f"Atom JSON 非法：{path}:{line_no}（{exc.msg}）"
                ) from exc
            if not isinstance(parsed, Mapping):
                if self.lenient:
                    warnings.append(
                        f"malformed_skipped:{path.name}:{line_no}:not_object"
                    )
                    continue
                raise KnowledgeLoadError(f"Atom 必须是对象：{path}:{line_no}")

            raw_id = parsed.get("id")
            if isinstance(raw_id, str):
                if raw_id in seen_raw_ids:
                    raise KnowledgeLoadError(f"Corpus 包含重复 atom_id：{raw_id}")
                seen_raw_ids.add(raw_id)
            schema_version = parsed.get("schema_version")
            if schema_version != metadata.atom_schema_version:
                raise KnowledgeLoadError(
                    f"Atom Schema 不一致：{path}:{line_no}，"
                    f"manifest={metadata.atom_schema_version!r}，"
                    f"atom={schema_version!r}"
                )
            try:
                atoms.append(KnowledgeAtomV2.from_dict(parsed))
            except (KnowledgeValidationError, TypeError, ValueError) as exc:
                if self.lenient:
                    warnings.append(
                        f"malformed_skipped:{path.name}:{line_no}:validation:{exc}"
                    )
                    continue
                raise KnowledgeLoadError(
                    f"Atom 校验失败：{path}:{line_no}（{exc}）"
                ) from exc
        return tuple(atoms), tuple(warnings)

    def _select_public_atoms(
        self,
        atoms: Sequence[KnowledgeAtomV2],
    ) -> tuple[tuple[KnowledgeAtomV2, ...], tuple[str, ...]]:
        filtered = Counter[str]()
        candidates: list[KnowledgeAtomV2] = []
        for atom in atoms:
            status = atom.quality.review_status
            if status != "approved":
                filtered[f"review_status={status}"] += 1
                continue
            if atom.scope.visibility != "public":
                filtered[f"visibility={atom.scope.visibility}"] += 1
                continue
            if not atom.privacy.exportable:
                filtered["not_exportable"] += 1
                continue
            if atom.privacy.contains_pii:
                filtered["contains_pii"] += 1
                continue
            if atom.privacy.contains_client_secret:
                filtered["contains_client_secret"] += 1
                continue

            valid_from = date.fromisoformat(atom.lifecycle.valid_from)
            valid_until = (
                date.fromisoformat(atom.lifecycle.valid_until)
                if atom.lifecycle.valid_until
                else None
            )
            if valid_from > self.today:
                filtered["future_valid"] += 1
                continue
            if valid_until is not None and valid_until < self.today:
                filtered["expired"] += 1
                continue
            self._validate_approved_completeness(atom)
            candidates.append(atom)

        superseded_ids = {
            superseded_id
            for atom in candidates
            for superseded_id in atom.lifecycle.supersedes
        }
        selected: list[KnowledgeAtomV2] = []
        for atom in candidates:
            if atom.id in superseded_ids:
                filtered["superseded_by_active_atom"] += 1
                continue
            selected.append(atom)
        warnings = tuple(
            f"filtered:{reason}:{count}" for reason, count in sorted(filtered.items())
        )
        return tuple(selected), warnings

    def _validate_approved_completeness(self, atom: KnowledgeAtomV2) -> None:
        applicability = atom.applicability
        missing: list[str] = []
        if not applicability.preconditions:
            missing.append("preconditions")
        if not applicability.recommended_action:
            missing.append("recommended_action")
        if not applicability.metrics and not self._has_metric_not_applicable_marker(atom):
            missing.append("metrics_or_explicit_not_applicable")
        if not applicability.failure_modes and not applicability.counterexamples:
            missing.append("failure_modes_or_counterexamples")
        if missing:
            raise KnowledgeLoadError(
                f"批准 Atom {atom.id} 完整性不足：" + ", ".join(missing)
            )

    def _has_metric_not_applicable_marker(self, atom: KnowledgeAtomV2) -> bool:
        values = (
            atom.applicability.preconditions
            + atom.applicability.recommended_action
            + atom.applicability.failure_modes
            + atom.applicability.counterexamples
        )
        return any(
            text.strip().casefold().startswith(_METRIC_NOT_APPLICABLE_PREFIXES)
            for text in values
        )


__all__ = ["Corpus", "CorpusLoader", "CorpusMetadata"]
