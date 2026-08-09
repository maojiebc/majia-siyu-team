"""公开知识在源码、wheel 与 SkillHub 安装态中的分发回归。"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any, ClassVar
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
ROOT_KNOWLEDGE = ROOT / "knowledge"
PACKAGE_KNOWLEDGE = ROOT / "src/siyu_team/knowledge/data"
APPROVED_CORPUS = Path("04-atoms/growth-layers.approved.jsonl")
WHEEL_DATA_PREFIX = "siyu_team/knowledge/data"
REQUIRE_INSTALL_ENV = "SIYU_REQUIRE_INSTALL_TESTS"
INSTALL_PREREQUISITE_MESSAGE = (
    "需要预装 build+hatchling；PR-06 安装态 CI 强制执行"
)


def _offline_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PIP_NO_INDEX": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "UV_OFFLINE": "1",
            "UV_PYTHON_DOWNLOADS": "never",
        }
    )
    return env


def _run(
    command: Sequence[str | os.PathLike[str]],
    *,
    cwd: Path,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(part) for part in command],
        cwd=cwd,
        env=dict(env) if env is not None else None,
        text=True,
        capture_output=True,
        check=False,
    )


def _process_output(result: subprocess.CompletedProcess[str]) -> str:
    return f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"


def _require_success(
    result: subprocess.CompletedProcess[str],
    label: str,
) -> None:
    if result.returncode != 0:
        raise AssertionError(
            f"{label} 失败，exit={result.returncode}\n{_process_output(result)}"
        )


def _load_json_object(payload: bytes | str, label: str) -> dict[str, Any]:
    text = payload.decode("utf-8") if isinstance(payload, bytes) else payload
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"{label} 不是合法 JSON：{exc}") from exc
    if not isinstance(value, dict):
        raise AssertionError(f"{label} 必须是 JSON 对象")
    return value


def _venv_python(venv: Path) -> Path:
    if os.name == "nt":
        return venv / "Scripts/python.exe"
    return venv / "bin/python"


def _venv_script(venv: Path, name: str) -> Path:
    if os.name == "nt":
        return venv / "Scripts" / f"{name}.exe"
    return venv / "bin" / name


class InstalledKnowledgeTests(unittest.TestCase):
    _temporary: ClassVar[tempfile.TemporaryDirectory[str]]
    temp_root: ClassVar[Path]
    bundle_root: ClassVar[Path]
    bundle_knowledge: ClassVar[Path]
    wheel_path: ClassVar[Path | None] = None
    venv: ClassVar[Path | None] = None
    wheel_prerequisites_available: ClassVar[bool]

    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary = tempfile.TemporaryDirectory(prefix="siyu-installed-knowledge-")
        cls.addClassCleanup(cls._temporary.cleanup)
        cls.temp_root = Path(cls._temporary.name)

        cls.bundle_root = cls.temp_root / "skillhub-bundle"
        bundle_result = _run(
            [
                sys.executable,
                ROOT / "tools/build_skillhub_bundle.py",
                "--output",
                cls.bundle_root,
            ],
            cwd=ROOT,
            env=_offline_env(),
        )
        _require_success(bundle_result, "构建临时 SkillHub bundle")
        cls.bundle_knowledge = cls.bundle_root / "modules/_knowledge"

        cls.wheel_prerequisites_available = (
            importlib.util.find_spec("build") is not None
            and importlib.util.find_spec("hatchling") is not None
        )
        if not cls.wheel_prerequisites_available:
            return

        wheel_dir = cls.temp_root / "wheel"
        wheel_dir.mkdir()
        build_result = _run(
            [
                sys.executable,
                "-m",
                "build",
                "--wheel",
                "--no-isolation",
                "--outdir",
                wheel_dir,
            ],
            cwd=ROOT,
            env=_offline_env(),
        )
        _require_success(build_result, "离线构建 wheel")
        wheels = sorted(wheel_dir.glob("*.whl"))
        if len(wheels) != 1:
            raise AssertionError(f"应只生成一个 wheel，实际为：{wheels}")
        cls.wheel_path = wheels[0]

        cls.venv = cls.temp_root / "venv"
        venv_result = _run(
            [sys.executable, "-m", "venv", cls.venv],
            cwd=cls.temp_root,
            env=_offline_env(),
        )
        _require_success(venv_result, "创建 wheel 安装态临时 venv")
        install_result = _run(
            [
                _venv_python(cls.venv),
                "-m",
                "pip",
                "install",
                "--no-index",
                "--no-deps",
                cls.wheel_path,
            ],
            cwd=cls.temp_root,
            env=_offline_env(),
        )
        _require_success(install_result, "离线安装 wheel")

    def _require_wheel(self) -> tuple[Path, Path]:
        if not self.wheel_prerequisites_available:
            if os.environ.get(REQUIRE_INSTALL_ENV) == "1":
                self.fail(INSTALL_PREREQUISITE_MESSAGE)
            self.skipTest(INSTALL_PREREQUISITE_MESSAGE)
        self.assertIsNotNone(self.wheel_path)
        self.assertIsNotNone(self.venv)
        assert self.wheel_path is not None
        assert self.venv is not None
        return self.wheel_path, self.venv

    def _assert_manifest_matches_corpus(
        self,
        manifest: Mapping[str, Any],
        corpus_bytes: bytes,
    ) -> None:
        digest = f"sha256:{hashlib.sha256(corpus_bytes).hexdigest()}"
        lines = [
            line
            for line in corpus_bytes.decode("utf-8").splitlines()
            if line.strip()
        ]
        atoms = [_load_json_object(line, "approved corpus row") for line in lines]

        self.assertRegex(digest, r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(manifest.get("corpus_hash"), digest)
        self.assertEqual(manifest.get("atom_count"), len(atoms))
        self.assertIsInstance(manifest.get("corpus_version"), str)
        self.assertTrue(manifest.get("corpus_version"))
        self.assertIsInstance(manifest.get("release_batch"), str)
        self.assertTrue(manifest.get("release_batch"))

        public_corpora = manifest.get("public_corpora")
        self.assertIsInstance(public_corpora, list)
        assert isinstance(public_corpora, list)
        entry = next(
            (
                item
                for item in public_corpora
                if isinstance(item, dict)
                and item.get("path") == APPROVED_CORPUS.as_posix()
            ),
            None,
        )
        self.assertIsNotNone(entry, "manifest 未登记 approved corpus")
        assert isinstance(entry, dict)
        self.assertEqual(entry.get("sha256"), digest)
        self.assertEqual(entry.get("atom_count"), len(atoms))
        self.assertEqual(entry.get("corpus_version"), manifest.get("corpus_version"))
        self.assertEqual(entry.get("release_batch"), manifest.get("release_batch"))
        self.assertEqual(
            entry.get("schema_version"),
            manifest.get("atom_schema_version"),
        )
        self.assertEqual(
            {atom.get("schema_version") for atom in atoms},
            {manifest.get("atom_schema_version")},
        )

    def test_source_package_data_and_skillhub_share_manifest_and_corpus(
        self,
    ) -> None:
        roots = (ROOT_KNOWLEDGE, PACKAGE_KNOWLEDGE, self.bundle_knowledge)
        manifest_bytes = (ROOT_KNOWLEDGE / "manifest.json").read_bytes()
        corpus_bytes = (ROOT_KNOWLEDGE / APPROVED_CORPUS).read_bytes()

        for root in roots:
            with self.subTest(root=root):
                self.assertEqual((root / "manifest.json").read_bytes(), manifest_bytes)
                self.assertEqual((root / APPROVED_CORPUS).read_bytes(), corpus_bytes)

        manifest = _load_json_object(manifest_bytes, "root manifest")
        self._assert_manifest_matches_corpus(manifest, corpus_bytes)

    def test_public_directory_and_skillhub_exclude_private_sop(self) -> None:
        for root in (PACKAGE_KNOWLEDGE, self.bundle_knowledge):
            leaked = [
                path.relative_to(root)
                for path in root.rglob("*")
                if path.is_file() and "03-majia-sop" in path.parts
            ]
            self.assertEqual(
                leaked,
                [],
                f"公开知识生成物泄漏私有 SOP：{leaked}",
            )

    def test_skillhub_default_query_uses_bundled_public_knowledge(self) -> None:
        query = self.bundle_root / "tools/atoms_query.py"
        result = _run(
            [sys.executable, "-I", query, "--skills", "siyu-qunfa"],
            cwd=self.bundle_root,
            env=_offline_env(),
        )
        combined = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, _process_output(result))
        self.assertNotIn("03-majia-sop", combined)
        self.assertNotIn("原子库不存在", combined)
        match = re.search(r"命中\s*(\d+)\s*条", combined)
        self.assertIsNotNone(match, _process_output(result))
        assert match is not None
        self.assertGreaterEqual(int(match.group(1)), 0)

    def test_built_wheel_contains_identical_manifest_and_corpus(self) -> None:
        wheel, _ = self._require_wheel()
        manifest_member = f"{WHEEL_DATA_PREFIX}/manifest.json"
        corpus_member = f"{WHEEL_DATA_PREFIX}/{APPROVED_CORPUS.as_posix()}"
        with zipfile.ZipFile(wheel) as archive:
            names = archive.namelist()
            self.assertIn(manifest_member, names)
            self.assertIn(corpus_member, names)
            self.assertFalse(
                any("03-majia-sop" in Path(name).parts for name in names),
                "wheel 不得包含私有 SOP",
            )
            wheel_manifest = archive.read(manifest_member)
            wheel_corpus = archive.read(corpus_member)

        self.assertEqual(
            wheel_manifest,
            (ROOT_KNOWLEDGE / "manifest.json").read_bytes(),
        )
        self.assertEqual(
            wheel_corpus,
            (ROOT_KNOWLEDGE / APPROVED_CORPUS).read_bytes(),
        )
        self._assert_manifest_matches_corpus(
            _load_json_object(wheel_manifest, "wheel manifest"),
            wheel_corpus,
        )

    def test_clean_wheel_install_siyu_plan_selects_public_knowledge(self) -> None:
        _, venv = self._require_wheel()
        isolated_home = self.temp_root / "isolated-home"
        isolated_home.mkdir(exist_ok=True)
        empty_override = self.temp_root / "empty-knowledge-override"
        empty_override.mkdir(exist_ok=True)
        runtime_cwd = self.temp_root / "runtime-cwd"
        runtime_cwd.mkdir(exist_ok=True)
        shim = self.temp_root / "sitecustomize"
        shim.mkdir(exist_ok=True)
        (shim / "sitecustomize.py").write_text(
            "import pathlib\n"
            "pathlib.Path.home = classmethod("
            f"lambda cls: pathlib.Path({str(isolated_home)!r}))\n",
            encoding="utf-8",
        )

        env = _offline_env()
        env.update(
            {
                "PYTHONNOUSERSITE": "1",
                "PYTHONPATH": str(shim),
                "SIYU_KNOWLEDGE_HOME": str(empty_override),
            }
        )
        result = _run(
            [
                _venv_script(venv, "siyu-plan"),
                "群转化差怎么办",
                "--no-trace",
            ],
            cwd=runtime_cwd,
            env=env,
        )
        self.assertEqual(result.returncode, 0, _process_output(result))
        payload = _load_json_object(result.stdout, "installed siyu-plan output")
        knowledge = payload.get("knowledge")
        self.assertIsInstance(knowledge, dict)
        assert isinstance(knowledge, dict)

        selection_count = knowledge.get("selection_count")
        self.assertIs(type(selection_count), int)
        assert isinstance(selection_count, int)
        self.assertGreater(selection_count, 0)
        atoms = knowledge.get("atoms")
        self.assertIsInstance(atoms, list)
        assert isinstance(atoms, list)
        self.assertEqual(selection_count, len(atoms))

        manifest = _load_json_object(
            (ROOT_KNOWLEDGE / "manifest.json").read_bytes(),
            "root manifest",
        )
        self.assertEqual(knowledge.get("corpus_version"), manifest["corpus_version"])
        self.assertEqual(knowledge.get("corpus_hash"), manifest["corpus_hash"])
        self.assertRegex(str(knowledge.get("corpus_hash")), r"^sha256:[0-9a-f]{64}$")
        self.assertNotIn(
            "legacy_growth_selection_pending_strict_corpus",
            payload.get("warnings", []),
        )
        for atom in atoms:
            self.assertIsInstance(atom, dict)
            self.assertTrue(
                {"id", "source_id", "locator", "why_selected"}.issubset(atom)
            )
            self.assertIsInstance(atom["why_selected"], list)
            self.assertTrue(atom["why_selected"])


if __name__ == "__main__":
    unittest.main()
