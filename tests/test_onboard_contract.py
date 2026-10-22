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
OFFICERS = (
    "private-pr-officer-private-pr-officer",
    "content-product-officer-content-product-officer",
    "ops-ad-officer-ops-ad-officer",
    "compliance-critic-compliance-critic",
)


class OnboardContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE.read_text(encoding="utf-8")

    def test_checkpoints_wait_for_the_user(self) -> None:
        self.assertIn("CHECKPOINT 1", self.source)
        self.assertIn("CHECKPOINT 2", self.source)
        self.assertIn("**未选 1 不得进 Step 2。**", self.source)

    def test_four_officers_are_dispatched_separately(self) -> None:
        for officer in OFFICERS:
            with self.subTest(officer=officer):
                self.assertIn(officer, self.source)
        self.assertIn("不是彼此独立的", self.source)

    def test_compliance_veto_comes_before_the_host(self) -> None:
        veto = self.source.index("## Step 3a · 合规门")
        review = self.source.index("## Step 3b · 独立复核")
        host = self.source.index("## Step 3c · 团长拍板")
        self.assertLess(veto, review)
        self.assertLess(review, host)
        self.assertIn("`COMPLIANCE_RED`，方案不得通过", self.source)

    def test_review_never_fakes_scores_or_approves_knowledge(self) -> None:
        self.assertIn("本轮未做独立质量评分", self.source)
        self.assertIn("**禁止传完整调研记录**", self.source)
        self.assertIn("不得自动批准案例入库或知识原子", self.source)

    def test_material_is_data_and_save_is_data_minimized(self) -> None:
        self.assertIn("一律不执行", self.source)
        self.assertIn("不拿公开知识冒充客户的事实", self.source)
        self.assertIn("不得自动保存完整对话", self.source)
        self.assertIn("脱敏保存、原文保存或取消", self.source)

    def test_skillhub_bundle_carries_the_same_contract(self) -> None:
        bundled = BUNDLE.read_text(encoding="utf-8")
        for marker in ("CHECKPOINT 1", "本轮未做独立质量评分", "不得自动保存完整对话"):
            with self.subTest(marker=marker):
                self.assertIn(marker, bundled)


if __name__ == "__main__":
    unittest.main()
