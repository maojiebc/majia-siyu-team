"""WorkBuddy 专家团发布包的干净构建与平台契约冒烟。"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
from typing import Any, ClassVar
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = ROOT / "tools/build_workbuddy_bundle.py"
EXPECTED_AGENT_IDS = {
    "majia-siyu-team-lead",
    "private-pr-officer",
    "content-product-officer",
    "ops-ad-officer",
    "compliance-critic",
}


def _run(command: list[object], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
        }
    )
    return subprocess.run(
        [str(part) for part in command],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )


def _output(result: subprocess.CompletedProcess[str]) -> str:
    return f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"


def _json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"{path} 必须是 JSON 对象")
    return value


def _frontmatter(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\n(?P<body>.*?)\n---\n", text, re.DOTALL)
    if match is None:
        raise AssertionError(f"{path} 缺少 YAML frontmatter")
    values: dict[str, object] = {}
    current: str | None = None
    for line in match.group("body").splitlines():
        if line.startswith("  ") and current:
            key, raw = line.strip().split(":", 1)
            nested = values.setdefault(current, {})
            assert isinstance(nested, dict)
            nested[key] = raw.strip().strip('"')
            continue
        key, raw = line.split(":", 1)
        current = key
        values[key] = raw.strip().strip('"') if raw.strip() else {}
    return values


def _png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    if len(data) != 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionError(f"{path} 不是合法 PNG")
    return struct.unpack(">II", data[16:24])


class WorkBuddyBundleTests(unittest.TestCase):
    _temporary: ClassVar[tempfile.TemporaryDirectory[str]]
    temp_root: ClassVar[Path]
    bundle: ClassVar[Path]
    archive: ClassVar[Path]
    metadata: ClassVar[dict[str, Any]]

    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary = tempfile.TemporaryDirectory(prefix="siyu-workbuddy-")
        cls.addClassCleanup(cls._temporary.cleanup)
        cls.temp_root = Path(cls._temporary.name)
        cls.bundle = cls.temp_root / "majia-siyu"
        cls.archive = cls.temp_root / "majia-siyu.zip"
        result = _run(
            [
                sys.executable,
                "-I",
                "-B",
                BUILD_SCRIPT,
                "--output",
                cls.bundle,
                "--archive",
                cls.archive,
            ],
            cwd=cls.temp_root,
        )
        if result.returncode != 0:
            raise AssertionError(f"WorkBuddy 构建失败\n{_output(result)}")
        cls.metadata = json.loads(result.stdout)

    def test_manifest_matches_expert_team_contract(self) -> None:
        manifest = _json_object(self.bundle / ".codebuddy-plugin/plugin.json")
        self.assertEqual(manifest["name"], "majia-siyu")
        self.assertEqual(manifest["version"], (ROOT / "VERSION").read_text().strip())
        self.assertEqual(manifest["expertType"], "team")
        self.assertEqual(manifest["agentName"], "majia-siyu-team-lead")
        self.assertEqual(manifest["plugin"], manifest["name"])
        self.assertEqual(manifest["profession"], manifest["displayName"])
        self.assertEqual(manifest["defaultInitPrompt"], manifest["quickPrompts"][0])
        self.assertEqual(len(manifest["tags"]), 3)
        self.assertEqual(len(manifest["quickPrompts"]), 3)
        chinese_description = manifest["displayDescription"]["zh"]
        chinese_characters = re.findall(r"[\u3400-\u9fff]", chinese_description)
        self.assertGreaterEqual(len(chinese_characters), 40)
        self.assertLessEqual(len(chinese_characters), 50)
        self.assertEqual(
            set(manifest["teamInfo"]["memberAgents"]),
            EXPECTED_AGENT_IDS - {"majia-siyu-team-lead"},
        )
        self.assertEqual(
            {member["id"] for member in manifest["members"]},
            EXPECTED_AGENT_IDS,
        )

    def test_manifest_paths_and_agent_frontmatter_are_self_contained(self) -> None:
        manifest = _json_object(self.bundle / ".codebuddy-plugin/plugin.json")
        bundle_root = self.bundle.resolve()
        for raw_path in [*manifest["agents"], *manifest["skills"], manifest["avatar"]]:
            target = (self.bundle / raw_path).resolve()
            self.assertTrue(target.is_relative_to(bundle_root), raw_path)
            self.assertTrue(target.exists(), raw_path)
        for member in manifest["members"]:
            avatar = (self.bundle / member["avatar"]).resolve()
            self.assertTrue(avatar.is_relative_to(bundle_root))
            self.assertTrue(avatar.is_file(), member["avatar"])
        for agent_path in sorted((self.bundle / "agents").glob("*.md")):
            fields = _frontmatter(agent_path)
            self.assertEqual(fields["name"], agent_path.stem)
            self.assertTrue(fields.get("description"))
            self.assertIsInstance(fields.get("displayName"), dict)
            self.assertIsInstance(fields.get("profession"), dict)

    def test_avatars_meet_platform_limits(self) -> None:
        avatars = sorted((self.bundle / "avatars").glob("*.png"))
        self.assertEqual(len(avatars), 6)
        for avatar in avatars:
            with self.subTest(avatar=avatar.name):
                self.assertEqual(_png_dimensions(avatar), (512, 512))
                self.assertLessEqual(avatar.stat().st_size, 500_000)

    def test_bundle_excludes_private_sop_caches_and_symlinks(self) -> None:
        relative_files = [
            path.relative_to(self.bundle)
            for path in self.bundle.rglob("*")
            if path.is_file()
        ]
        self.assertFalse(any("03-majia-sop" in path.parts for path in relative_files))
        self.assertFalse(any("__pycache__" in path.parts for path in relative_files))
        self.assertFalse(any(path.suffix == ".pyc" for path in relative_files))
        self.assertFalse(any(path.is_symlink() for path in self.bundle.rglob("*")))
        self.assertEqual(
            _json_object(self.bundle / "setting.json"),
            {"agent": "majia-siyu-team-lead"},
        )
        self.assertEqual(
            _json_object(self.bundle / "settings.json"),
            {"agent": "majia-siyu-team-lead"},
        )

    def test_archive_has_one_clean_top_level_directory(self) -> None:
        self.assertTrue(self.archive.is_file())
        with zipfile.ZipFile(self.archive) as archive:
            names = archive.namelist()
        self.assertTrue(names)
        self.assertTrue(all(name.startswith("majia-siyu/") for name in names))
        self.assertFalse(any("__MACOSX" in name or ".DS_Store" in name for name in names))
        self.assertEqual(Path(self.metadata["archive"]).resolve(), self.archive.resolve())
        self.assertEqual(self.metadata["version"], (ROOT / "VERSION").read_text().strip())

    def test_check_builds_in_temporary_directory_without_committed_dist(self) -> None:
        missing_output = self.temp_root / "not-prebuilt" / "majia-siyu"
        result = _run(
            [
                sys.executable,
                "-I",
                "-B",
                BUILD_SCRIPT,
                "--output",
                missing_output,
                "--check",
            ],
            cwd=self.temp_root,
        )
        self.assertEqual(result.returncode, 0, _output(result))
        self.assertIn("临时构建校验通过", result.stdout)
        self.assertFalse(missing_output.exists())


if __name__ == "__main__":
    unittest.main()
