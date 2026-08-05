from __future__ import annotations

import unittest

from siyu_team.contribution.models import ContributionPromptState, ContributionSignal
from siyu_team.contribution.signals import detect_contribution_signal


class ContributionSignalTests(unittest.TestCase):
    def test_detects_four_high_value_signals(self) -> None:
        cases = (
            (
                "我们门店实际做过扫码后拉群，后来调整成支付后一步加微才有效。",
                ContributionSignal.FIRSTHAND_CASE,
            ),
            (
                "不是这个原因，加盟门店不会这么执行，真实情况是店员没时间。",
                ContributionSignal.USER_CORRECTION,
            ),
            (
                "上次照你说的做了分组群发，结果核销提高，但退群也多了。",
                ContributionSignal.EXECUTION_FEEDBACK,
            ),
            (
                "我们实际试过，这个方法只在低客流门店有效，高峰期就不适用。",
                ContributionSignal.COUNTEREXAMPLE,
            ),
        )
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(detect_contribution_signal(text), expected)

    def test_does_not_trigger_on_questions_opinions_or_unverified_articles(self) -> None:
        for text in (
            "加盟门店怎么做加微？",
            "我觉得朋友圈应该多发一点。",
            "公众号文章说群发越多越好。",
            "谢谢。",
        ):
            with self.subTest(text=text):
                self.assertIsNone(detect_contribution_signal(text))

    def test_session_state_suppresses_repeat_and_pre_answer_prompt(self) -> None:
        text = "我们实际做过这个流程，后来发现高峰期不行。"
        self.assertIsNone(
            detect_contribution_signal(text, ContributionPromptState())
        )
        self.assertIsNone(
            detect_contribution_signal(
                text,
                ContributionPromptState(
                    primary_answer_delivered=True,
                    prompt_shown=True,
                ),
            )
        )


if __name__ == "__main__":
    unittest.main()
