"""知识目录发现；所有默认值都相对模块位置或用户目录，不依赖 cwd。"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Mapping


ENV_NAME = "SIYU_KNOWLEDGE_HOME"


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
