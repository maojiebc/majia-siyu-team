from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "plugins/siyu-core/skills/majia-siyu/SKILL.md"
# 已删除的后台运行时产物；技能文字再提到它们，就是在让模型调用不存在的东西。
RUNTIME_LEFTOVERS = (
    "route-contract",
    "handoff-contract",
    "siyu-plan",
    "runtime_mode",
    "atoms_query",
    "04-atoms",
    "05-community",
    ".siyu-team",
    "StateStore",
    "perspectives.py",
    "connectors/",
    "growth_atoms",
)


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _shipped_markdown(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.md") if path.is_file())


class RepositoryContractTests(unittest.TestCase):
    def test_repository_markdown_links_exist(self) -> None:
        result = _run("tools/check_links.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_shipped_prompts_never_point_at_deleted_runtime(self) -> None:
        for root in (ROOT / "plugins", ROOT / "skillhub/majia-siyu"):
            for path in _shipped_markdown(root):
                text = path.read_text(encoding="utf-8")
                for marker in RUNTIME_LEFTOVERS:
                    with self.subTest(path=str(path.relative_to(ROOT)), marker=marker):
                        self.assertNotIn(marker, text)

    def test_generic_only_industries_never_get_a_made_up_book(self) -> None:
        entry = ENTRY.read_text(encoding="utf-8")
        self.assertIn("零售、教培只用通用方法，不虚构行业册", entry)
        self.assertTrue((ROOT / "knowledge/02-industry/catering").is_dir())
        self.assertFalse((ROOT / "knowledge/02-industry/edu").exists())

    def test_judgment_list_is_wired_into_entry_and_diagnosis(self) -> None:
        self.assertTrue((ROOT / "knowledge/cases/00-判断清单.md").is_file())
        for path in (
            ENTRY,
            ROOT / "plugins/siyu-core/skills/siyu-wenzhen/SKILL.md",
            ROOT / "plugins/_orchestrator/commands/siyu-onboard.md",
        ):
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertIn("knowledge/cases/00-判断清单.md", path.read_text(encoding="utf-8"))

    def test_clean_skillhub_build_has_valid_links(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / "majia-siyu"
            built = _run("tools/build_skillhub_bundle.py", "--output", str(bundle))
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            metadata = json.loads(built.stdout)
            self.assertEqual(
                Path(metadata["output"]).resolve(strict=False),
                bundle.resolve(strict=False),
            )
            self.assertTrue((bundle / "modules/_knowledge/cases/00-判断清单.md").is_file())
            self.assertFalse((bundle / "modules/_knowledge/03-majia-sop").exists())
            links = _run("tools/check_links.py", "--root", str(bundle))
            self.assertEqual(links.returncode, 0, links.stdout + links.stderr)


if __name__ == "__main__":
    unittest.main()
