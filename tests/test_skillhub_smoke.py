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

    def test_bundle_layout_and_version_are_self_contained(self) -> None:
        expected_version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(self.metadata.get("version"), expected_version)
        self.assertEqual(
            Path(str(self.metadata["output"])).resolve(),
            self.bundle.resolve(),
        )
        self.assertTrue((self.bundle / "SKILL.md").is_file())
        self.assertTrue((self.bundle / "modules/_knowledge/cases/00-判断清单.md").is_file())
        self.assertFalse((self.bundle / "modules/_runtime").exists())
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

    def test_bundled_report_scan_works_without_source_tree(self) -> None:
        report = self.temp_root / "report.md"
        report.write_text("本店全国销量第一，转发3个群领券。", encoding="utf-8")
        launcher = (
            "import sys,runpy; sys.path.insert(0,sys.argv.pop(1)); "
            "runpy.run_module('siyu_team.eval.cli',run_name='__main__')"
        )
        result = _run([
            sys.executable, "-I", "-B", "-c", launcher, self.bundle / "tools",
            "compliance", report, "--json",
        ], cwd=self.temp_root, env=self.env)
        self.assertEqual(result.returncode, 1, _output(result))
        payload = _json_object(result.stdout, "standalone compliance report")
        self.assertFalse(payload["passed"])

    def test_bundle_links_pass_repository_checker(self) -> None:
        links = _run(
            [sys.executable, "-I", "-B", LINK_CHECK, "--root", self.bundle],
            cwd=self.temp_root,
            env=self.env,
        )
        _require_success(links, "SkillHub Markdown 链接")

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
