from __future__ import annotations

import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock

from tools import check_consistency
from tools import check_versions


ROOT = Path(__file__).resolve().parents[1]


class VersionReleaseContractTests(unittest.TestCase):
    def test_repository_distribution_versions_are_aligned(self) -> None:
        version, install_units, skill_count, errors = check_versions.check(ROOT)

        self.assertEqual(version, "1.4.2")
        self.assertEqual(install_units, 11)
        self.assertEqual(skill_count, 34)
        self.assertEqual(errors, [])

    def test_both_marketplaces_reject_metadata_and_plugin_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in (
                Path(".claude-plugin/marketplace.json"),
                Path(".codebuddy-plugin/marketplace.json"),
            ):
                with self.subTest(rel=rel):
                    path = root / rel
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(
                        json.dumps(
                            {
                                "metadata": {"version": "1.4.1"},
                                "plugins": [
                                    {"name": "majia-siyu", "version": "1.4.1"}
                                ],
                            }
                        ),
                        encoding="utf-8",
                    )
                    errors: list[str] = []

                    count = check_versions._check_marketplace(
                        root, rel, "1.4.2", errors
                    )

                    self.assertEqual(count, 1)
                    self.assertTrue(
                        any("metadata.version" in error for error in errors)
                    )
                    self.assertTrue(
                        any("majia-siyu.version" in error for error in errors)
                    )


class ConsistencyReleaseContractTests(unittest.TestCase):
    def _write_main_skill(self, root: Path, size: int) -> None:
        path = root / check_consistency.MAIN_ENTRY
        path.parent.mkdir(parents=True)
        tail = ("\n" + check_consistency.FOOTER).encode("utf-8")
        self.assertGreater(size, len(tail))
        path.write_bytes(b"x" * (size - len(tail)) + tail)

    def test_main_entry_keeps_500_byte_execution_margin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_main_skill(root, check_consistency.MAIN_ENTRY_MAX_BYTES + 1)
            with mock.patch.object(check_consistency, "ROOT", root):
                errors = check_consistency.skill_checks()

        self.assertTrue(any("预留至少 500 bytes" in error for error in errors))
        self.assertFalse(any("超过 8192 bytes 硬门" in error for error in errors))

    def test_global_8192_byte_gate_and_forbidden_terms_remain_hard(self) -> None:
        self.assertEqual(check_consistency.MAX_SKILL_BYTES, 8192)
        self.assertEqual(
            check_consistency.MAIN_ENTRY_MAX_BYTES,
            check_consistency.MAX_SKILL_BYTES - 500,
        )
        self.assertEqual(check_consistency.FORBIDDEN, ("slug", "snapshot", "session"))

    def test_user_facing_bare_slug_fails_but_internal_context_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / check_consistency.MAIN_ENTRY
            path.parent.mkdir(parents=True)
            path.write_text(
                "请用户输入 slug。\n" + check_consistency.FOOTER,
                encoding="utf-8",
            )
            with mock.patch.object(check_consistency, "ROOT", root):
                user_errors = check_consistency.skill_checks()

            path.write_text(
                "内部字段 slug 不外露。\n" + check_consistency.FOOTER,
                encoding="utf-8",
            )
            with mock.patch.object(check_consistency, "ROOT", root):
                internal_errors = check_consistency.skill_checks()

        self.assertTrue(
            any("面向用户的文字出现内部术语 ['slug']" in error for error in user_errors)
        )
        self.assertEqual(internal_errors, [])


class ManualReleaseChecklistTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = (ROOT / "docs/release-checklist.md").read_text(encoding="utf-8")

    def test_git_commit_and_clean_tree_three_way_gate_is_explicit(self) -> None:
        for command in ("git rev-parse HEAD", "git status --porcelain", "git ls-remote"):
            with self.subTest(command=command):
                self.assertIn(command, self.text)
        self.assertIn("LOCAL_COMMIT", self.text)
        self.assertIn("REMOTE_MAIN", self.text)

    def test_clawhub_is_explicit_package_only_with_ten_tags(self) -> None:
        self.assertIn("clawhub publish ./skillhub/majia-siyu", self.text)
        self.assertIn("<按官方 CLI 填写的 10 个 tag 参数>", self.text)
        self.assertIn("绝不裸跑 `clawhub`", self.text)
        self.assertIn("绝不运行 `clawhub sync`", self.text)
        tag_section = self.text.split("10 个 tags 必须正好是：", 1)[1].split(
            "安全硬门：", 1
        )[0]
        tags = re.findall(r"^\d+\. `([^`]+)`$", tag_section, re.MULTILINE)
        self.assertEqual(len(tags), 10)
        self.assertEqual(len(set(tags)), 10)

    def test_all_online_steps_are_manual_and_hypotheses_are_not_evaluated(self) -> None:
        self.assertIn("所有 GitHub、ClawHub、SkillHub", self.text)
        self.assertIn("同一 commit", self.text)
        self.assertIn("SemVer", self.text)
        self.assertIn("Not Evaluated", self.text)


if __name__ == "__main__":
    unittest.main()
