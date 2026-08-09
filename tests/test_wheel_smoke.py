"""离线 wheel 构建、干净安装与已安装 CLI 冒烟。"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, ClassVar
import unittest


ROOT = Path(__file__).resolve().parents[1]
REQUIRE_INSTALL_ENV = "SIYU_REQUIRE_INSTALL_TESTS"
BUILD_MODULES = ("build", "hatchling")


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
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(part) for part in command],
        cwd=cwd,
        env=dict(env),
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


def _venv_python(venv: Path) -> Path:
    if os.name == "nt":
        return venv / "Scripts/python.exe"
    return venv / "bin/python"


def _venv_script(venv: Path, name: str) -> Path:
    if os.name == "nt":
        return venv / "Scripts" / f"{name}.exe"
    return venv / "bin" / name


def _json_object(text: str, label: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"{label} 不是合法 JSON：{exc}\n{text}") from exc
    if not isinstance(value, dict):
        raise AssertionError(f"{label} 必须是 JSON 对象")
    return value


class WheelInstallSmokeTests(unittest.TestCase):
    _temporary: ClassVar[tempfile.TemporaryDirectory[str]]
    temp_root: ClassVar[Path]
    wheel: ClassVar[Path]
    venv: ClassVar[Path]
    runtime_cwd: ClassVar[Path]
    runtime_env: ClassVar[dict[str, str]]

    @classmethod
    def setUpClass(cls) -> None:
        missing = [name for name in BUILD_MODULES if importlib.util.find_spec(name) is None]
        if missing:
            message = (
                "wheel smoke 需要预装 build+hatchling；"
                f"缺少：{', '.join(missing)}"
            )
            if os.environ.get(REQUIRE_INSTALL_ENV) == "1":
                raise RuntimeError(message)
            raise unittest.SkipTest(message)

        cls._temporary = tempfile.TemporaryDirectory(prefix="siyu-wheel-smoke-")
        cls.addClassCleanup(cls._temporary.cleanup)
        cls.temp_root = Path(cls._temporary.name)
        wheel_dir = cls.temp_root / "dist"
        wheel_dir.mkdir()
        env = _offline_env()

        built = _run(
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
            env=env,
        )
        _require_success(built, "离线构建 wheel")
        wheels = sorted(wheel_dir.glob("*.whl"))
        if len(wheels) != 1:
            raise AssertionError(f"应只生成一个 wheel，实际为：{wheels}")
        cls.wheel = wheels[0]

        cls.venv = cls.temp_root / "clean-venv"
        created = _run(
            [sys.executable, "-m", "venv", cls.venv],
            cwd=cls.temp_root,
            env=env,
        )
        _require_success(created, "创建干净 venv")
        installed = _run(
            [
                _venv_python(cls.venv),
                "-m",
                "pip",
                "install",
                "--no-index",
                "--no-deps",
                cls.wheel,
            ],
            cwd=cls.temp_root,
            env=env,
        )
        _require_success(installed, "离线安装 wheel")

        cls.runtime_cwd = cls.temp_root / "outside-repository"
        cls.runtime_cwd.mkdir()
        isolated_home = cls.temp_root / "isolated-home"
        isolated_home.mkdir()
        empty_knowledge = cls.temp_root / "empty-knowledge"
        empty_knowledge.mkdir()
        shim = cls.temp_root / "sitecustomize"
        shim.mkdir()
        (shim / "sitecustomize.py").write_text(
            "import pathlib\n"
            "pathlib.Path.home = classmethod("
            f"lambda cls: pathlib.Path({str(isolated_home)!r}))\n",
            encoding="utf-8",
        )
        cls.runtime_env = env
        cls.runtime_env.update(
            {
                "PYTHONPATH": str(shim),
                "SIYU_KNOWLEDGE_HOME": str(empty_knowledge),
            }
        )

    def test_import_and_version_come_from_clean_venv(self) -> None:
        expected_version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        script = (
            "import importlib.metadata,json,pathlib,siyu_team;"
            "print(json.dumps({'origin':str(pathlib.Path(siyu_team.__file__).resolve()),"
            "'version':importlib.metadata.version('siyu-team')}))"
        )
        result = _run(
            [_venv_python(self.venv), "-I", "-c", script],
            cwd=self.runtime_cwd,
            env=self.runtime_env,
        )
        _require_success(result, "从干净 venv 导入安装包")
        payload = _json_object(result.stdout, "安装包来源")
        origin = Path(str(payload["origin"]))
        self.assertTrue(
            origin.is_relative_to(self.venv.resolve()),
            f"导入来源不在临时 venv：{origin}",
        )
        self.assertEqual(payload["version"], expected_version)
        self.assertNotIn(str(ROOT / "src"), str(origin))

    def test_installed_siyu_plan_loads_packaged_approved_knowledge(self) -> None:
        result = _run(
            [
                _venv_script(self.venv, "siyu-plan"),
                "群转化差怎么办",
                "--no-trace",
            ],
            cwd=self.runtime_cwd,
            env=self.runtime_env,
        )
        _require_success(result, "已安装 siyu-plan")
        payload = _json_object(result.stdout, "已安装 siyu-plan 输出")
        self.assertEqual(payload.get("runtime_mode"), "python")
        self.assertEqual(payload.get("plan_schema_version"), "1.0")
        knowledge = payload.get("knowledge")
        self.assertIsInstance(knowledge, dict)
        assert isinstance(knowledge, dict)
        self.assertGreater(knowledge.get("selection_count", 0), 0)
        self.assertRegex(
            str(knowledge.get("corpus_hash", "")),
            r"^sha256:[0-9a-f]{64}$",
        )
        atoms = knowledge.get("atoms")
        self.assertIsInstance(atoms, list)
        assert isinstance(atoms, list)
        self.assertTrue(all(atom.get("why_selected") for atom in atoms))

    def test_installed_contract_info_is_machine_readable(self) -> None:
        result = _run(
            [_venv_script(self.venv, "siyu-plan"), "--contract-info"],
            cwd=self.runtime_cwd,
            env=self.runtime_env,
        )
        _require_success(result, "已安装 siyu-plan --contract-info")
        payload = _json_object(result.stdout, "contract info")
        self.assertEqual(payload.get("plan_schema_version"), "1.0")
        self.assertRegex(
            str(payload.get("route_contract_hash", "")),
            r"^sha256:[0-9a-f]{64}$",
        )
        self.assertEqual(payload.get("default_trace_level"), "metadata")


if __name__ == "__main__":
    unittest.main()
