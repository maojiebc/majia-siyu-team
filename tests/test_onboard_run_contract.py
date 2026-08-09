from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "plugins" / "_orchestrator" / "commands" / "siyu-onboard.md"
BUNDLE = (
    ROOT
    / "skillhub"
    / "majia-siyu"
    / "modules"
    / "_expert-team"
    / "siyu-onboard.md"
)


class OnboardRunContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE.read_text(encoding="utf-8")

    def test_every_output_is_scoped_to_a_unique_run(self) -> None:
        self.assertIn(".siyu-team/runs/$RUN_ID", self.source)
        self.assertIn("$RUN_DIR/outputs/00-intake.md", self.source)
        self.assertIn("$RUN_DIR/outputs/04-playbook.md", self.source)
        self.assertIn("$RUN_DIR/traces", self.source)
        self.assertNotIn("`.siyu-team/00-intake.md`", self.source)
        self.assertNotIn("`.siyu-team/04-playbook.md`", self.source)

    def test_legacy_state_is_read_only_and_updates_use_cas(self) -> None:
        self.assertIn("只读复制迁移", self.source)
        self.assertIn("原文件不得修改或删除", self.source)
        self.assertIn("expected_revision", self.source)
        self.assertIn("文件锁 + 原子替换完成 CAS", self.source)
        self.assertIn("目录已存在就停止，绝不覆盖", self.source)

    def test_runtime_trace_and_prompt_only_boundaries_are_explicit(self) -> None:
        self.assertIn("--trace-dir \"$RUN_DIR/traces\"", self.source)
        self.assertIn("默认 trace level 为 `metadata`", self.source)
        self.assertIn("prompt_only_state_lock_not_code_enforced", self.source)
        self.assertIn("不可信数据", self.source)
        self.assertIn("公开知识原子不能顶替", self.source)

    def test_host_and_save_are_data_minimized(self) -> None:
        self.assertIn("`name / engine / content`", self.source)
        self.assertIn("不得把官员输出拼进指令区", self.source)
        self.assertIn("不得自动保存完整对话", self.source)
        self.assertIn("脱敏保存、原文保存或取消", self.source)

    def test_skillhub_bundle_carries_the_same_run_contract(self) -> None:
        bundled = BUNDLE.read_text(encoding="utf-8")
        for marker in (
            ".siyu-team/runs/$RUN_ID",
            "expected_revision",
            "prompt_only_state_lock_not_code_enforced",
            "不得自动保存完整对话",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, bundled)


if __name__ == "__main__":
    unittest.main()
