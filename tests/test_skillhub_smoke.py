"""临时目录中的 SkillHub 干净构建与独立 bundle 冒烟。"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, ClassVar
import unittest


ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = ROOT / "tools/build_skillhub_bundle.py"
LINK_CHECK = ROOT / "tools/check_links.py"
ROUTE_CHECK = ROOT / "tools/check_route_contracts.py"
LINT_SCRIPTS = {
    "siyu-pyq": "pyq_lint.py",
    "siyu-qunfa": "qunfa_lint.py",
    "siyu-huashu": "huashu_lint.py",
}


def _offline_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.update(
        {
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PIP_NO_INDEX": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
            "UV_OFFLINE": "1",
            "UV_PYTHON_DOWNLOADS": "never",
        }
    )
    return env


def _run(
    command: Sequence[str | os.PathLike[str]],
    *,
    cwd: Path,
    env: Mapping[str, str],
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(part) for part in command],
        cwd=cwd,
        env=dict(env),
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )


def _output(result: subprocess.CompletedProcess[str]) -> str:
    return f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"


def _require_success(
    result: subprocess.CompletedProcess[str],
    label: str,
) -> None:
    if result.returncode != 0:
        raise AssertionError(
            f"{label} 失败，exit={result.returncode}\n{_output(result)}"
        )


def _json_object(text: str, label: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"{label} 不是合法 JSON：{exc}\n{text}") from exc
    if not isinstance(value, dict):
        raise AssertionError(f"{label} 必须是 JSON 对象")
    return value


class SkillHubBundleSmokeTests(unittest.TestCase):
    _temporary: ClassVar[tempfile.TemporaryDirectory[str]]
    temp_root: ClassVar[Path]
    bundle: ClassVar[Path]
    metadata: ClassVar[dict[str, Any]]
    env: ClassVar[dict[str, str]]

    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary = tempfile.TemporaryDirectory(prefix="siyu-skillhub-smoke-")
        cls.addClassCleanup(cls._temporary.cleanup)
        cls.temp_root = Path(cls._temporary.name)
        cls.bundle = cls.temp_root / "majia-siyu"
        cls.env = _offline_env()
        result = _run(
            [
                sys.executable,
                "-I",
                "-B",
                BUILD_SCRIPT,
                "--output",
                cls.bundle,
            ],
            cwd=cls.temp_root,
            env=cls.env,
        )
        _require_success(result, "临时目录干净构建 SkillHub bundle")
        cls.metadata = _json_object(result.stdout, "bundle build metadata")

    def test_bundle_layout_routes_and_version_are_self_contained(self) -> None:
        expected_version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(self.metadata.get("version"), expected_version)
        self.assertEqual(
            Path(str(self.metadata["output"])).resolve(),
            self.bundle.resolve(),
        )
        self.assertTrue((self.bundle / "SKILL.md").is_file())
        self.assertTrue((self.bundle / "modules/_knowledge/manifest.json").is_file())
        self.assertTrue(
            (self.bundle / "modules/_runtime/route-contract.json").is_file()
        )
        self.assertFalse(any(path.is_symlink() for path in self.bundle.rglob("*")))

        index = _json_object(
            (self.bundle / "modules/index.json").read_text(encoding="utf-8"),
            "bundle module index",
        )
        bundle_root = self.bundle.resolve()
        for slug, raw_path in index.items():
            with self.subTest(slug=slug):
                relative = Path(str(raw_path))
                self.assertFalse(relative.is_absolute())
                self.assertNotIn("..", relative.parts)
                target = (self.bundle / relative).resolve()
                self.assertTrue(target.is_relative_to(bundle_root))
                self.assertTrue(target.is_file(), target)

        contract = _json_object(
            (
                self.bundle / "modules/_runtime/route-contract.json"
            ).read_text(encoding="utf-8"),
            "bundle route contract",
        )
        routes = contract.get("routes")
        self.assertIsInstance(routes, dict)
        assert isinstance(routes, dict)
        for route in routes.values():
            self.assertIsInstance(route, dict)
            assert isinstance(route, dict)
            skill = route.get("skill")
            if route.get("target_type") == "bundled" and skill != "majia-siyu":
                self.assertIn(skill, index)

    def test_bundle_links_and_routes_pass_repository_checkers(self) -> None:
        links = _run(
            [sys.executable, "-I", "-B", LINK_CHECK, "--root", self.bundle],
            cwd=self.temp_root,
            env=self.env,
        )
        _require_success(links, "SkillHub Markdown 链接")
        routes = _run(
            [
                sys.executable,
                "-I",
                "-B",
                ROUTE_CHECK,
                "--root",
                ROOT,
                "--bundle",
                self.bundle,
            ],
            cwd=self.temp_root,
            env=self.env,
        )
        _require_success(routes, "SkillHub 路由契约")

    def test_bundle_query_loads_strict_public_corpus_without_source_path(self) -> None:
        query = self.bundle / "tools/atoms_query.py"
        result = _run(
            [
                sys.executable,
                "-I",
                "-B",
                query,
                "--skills",
                "siyu-qunfa",
                "--limit",
                "1",
            ],
            cwd=self.bundle,
            env=self.env,
        )
        _require_success(result, "SkillHub 独立知识查询")
        rows = [line for line in result.stdout.splitlines() if line.strip()]
        self.assertEqual(len(rows), 1, _output(result))
        atom = _json_object(rows[0], "SkillHub query atom")
        self.assertEqual(atom.get("quality", {}).get("review_status"), "approved")
        combined = result.stdout + result.stderr
        self.assertNotIn(str(ROOT / "src"), combined)
        self.assertNotIn("03-majia-sop", combined)
        self.assertRegex(combined, r"hash=sha256:[0-9a-f]{64}")

    def test_bundled_execution_lints_work_in_isolated_mode(self) -> None:
        for slug, script_name in LINT_SCRIPTS.items():
            script = self.bundle / "modules" / slug / "scripts" / script_name
            with self.subTest(slug=slug, case="safe"):
                safe = _run(
                    [sys.executable, "-I", "-B", script, "-"],
                    cwd=self.bundle,
                    env=self.env,
                    input_text="第一步，先做小范围验证。",
                )
                self.assertEqual(safe.returncode, 0, _output(safe))
            with self.subTest(slug=slug, case="blocked"):
                blocked = _run(
                    [sys.executable, "-I", "-B", script, "-"],
                    cwd=self.bundle,
                    env=self.env,
                    input_text="本品牌全国销量第一，转发3个群领券。",
                )
                self.assertEqual(blocked.returncode, 1, _output(blocked))

    def test_bundle_excludes_private_sop_and_repository_cache_files(self) -> None:
        relative_files = [
            path.relative_to(self.bundle)
            for path in self.bundle.rglob("*")
            if path.is_file()
        ]
        self.assertFalse(
            any("03-majia-sop" in path.parts for path in relative_files)
        )
        self.assertFalse(
            any("__pycache__" in path.parts or path.suffix == ".pyc" for path in relative_files)
        )


if __name__ == "__main__":
    unittest.main()
