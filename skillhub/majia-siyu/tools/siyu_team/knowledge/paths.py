"""知识目录发现；所有默认值都相对模块位置或用户目录，不依赖 cwd。"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Mapping


ENV_NAME = "SIYU_KNOWLEDGE_HOME"


# 通用合规与方法论（相对仓库根，供路由/上下文引用）
COMPLIANCE_REDLINES_DOC = "knowledge/01-wechat-official/compliance/redlines.md"
METHODOLOGY_AXIOMS_DOC = "knowledge/00-methodology/私域公理与消解案例库.md"

# 增长分层文档与原子库（与 growth_layers 共享语义；此处为权威路径常量）
L0_DOC = "knowledge/00-methodology/L0-通用用户增长原则.md"
L1_CATERING_DOC = "knowledge/02-industry/catering/L1-餐饮零售用增Know-how.md"
GROWTH_INDEX_DOC = "knowledge/00-methodology/用户增长分层索引.md"
PUBLIC_MANIFEST = "manifest.json"
GROWTH_ATOMS_APPROVED = "04-atoms/growth-layers.approved.jsonl"
GROWTH_ATOMS_DRAFT = "04-atoms/growth-layers.draft.jsonl"


@dataclass(frozen=True)
class KnowledgePathResolver:
    repository_root: Path | None = None
    package_root: Path | None = None
    bundle_root: Path | None = None
    home: Path | None = None
    environ: Mapping[str, str] | None = None

    def _env(self) -> Mapping[str, str]:
        return os.environ if self.environ is None else self.environ

    def _home(self) -> Path:
        return Path.home() if self.home is None else self.home.expanduser()

    def _repository_root(self) -> Path:
        if self.repository_root is not None:
            return self.repository_root.expanduser().resolve(strict=False)
        return Path(__file__).resolve().parents[3]

    def _package_root(self) -> Path:
        if self.package_root is not None:
            return self.package_root.expanduser().resolve(strict=False)
        return Path(__file__).resolve().parent / "data"

    def candidates(self) -> tuple[Path, ...]:
        """按契约优先级返回候选目录，并稳定去重。"""
        env_path = self._env().get(ENV_NAME, "").strip()
        raw = []
        if env_path:
            raw.append(Path(env_path).expanduser().resolve(strict=False))
        raw.extend(
            [
                (self._home() / ".siyu-team" / "knowledge").resolve(strict=False),
                self._repository_root() / "knowledge",
                self._package_root(),
            ]
        )
        if self.bundle_root is not None:
            raw.append(
                self.bundle_root.expanduser().resolve(strict=False)
                / "modules"
                / "_knowledge"
            )
        result: list[Path] = []
        seen: set[str] = set()
        for path in raw:
            key = os.path.normcase(str(path))
            if key not in seen:
                seen.add(key)
                result.append(path)
        return tuple(result)

    def existing_roots(self) -> tuple[Path, ...]:
        return tuple(path for path in self.candidates() if path.is_dir())

    def approved_corpus_candidates(
        self,
        relative_path: str = GROWTH_ATOMS_APPROVED,
    ) -> tuple[tuple[Path, Path], ...]:
        """返回（正式集, manifest）候选，严格沿用 resolver 优先级。

        本方法故意不接受 draft 路径。这样高优先级目录中只有
        ``*.draft.jsonl`` 时，不会遮蔽低优先级目录的 approved 正式集。
        """
        normalized = relative_path.replace("\\", "/").strip("/")
        parts = Path(normalized).parts
        if (
            not normalized
            or Path(normalized).is_absolute()
            or ".." in parts
            or ".approved." not in Path(normalized).name
        ):
            raise ValueError("relative_path 必须是安全的 approved 相对路径")
        return tuple(
            (root / normalized, root / PUBLIC_MANIFEST)
            for root in self.candidates()
        )

    def writable_root(self, *, create: bool = False) -> Path:
        """返回私有写入目录；绝不把仓库或 bundle 作为默认写目标。"""
        env_path = self._env().get(ENV_NAME, "").strip()
        target = (
            Path(env_path).expanduser().resolve(strict=False)
            if env_path
            else (self._home() / ".siyu-team" / "knowledge").resolve(strict=False)
        )
        if create:
            target.mkdir(parents=True, exist_ok=True, mode=0o700)
            try:
                target.chmod(0o700)
            except OSError:
                pass
        return target

    def client_approved_file(self, client_id: str) -> Path:
        cleaned = client_id.strip()
        if not cleaned or cleaned in {".", ".."} or "/" in cleaned or "\\" in cleaned:
            raise ValueError("client_id 必须是非空且不含路径分隔符的标识")
        return self.writable_root() / "approved" / "clients" / f"{cleaned}.atoms.jsonl"
