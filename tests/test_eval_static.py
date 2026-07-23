from __future__ import annotations

import unittest

from siyu_team.eval.static import scan


class ComplianceGateTests(unittest.TestCase):
    """回归：确保 score 静态门真的拦裂变/绝对化，并把隐私索取标出来。"""

    def test_fission_inducement_hard_fails(self) -> None:
        for text in (
            "转发3群集20赞、拉5人、进群留手机号和身份证号",
            "参加活动集满38个赞即可领取礼品",
            "集齐20赞到店兑换",
        ):
            result = scan(text)
            self.assertTrue(result["hard_fail"], text)
            self.assertIn("INDUCE_SHARE", result["flags"], text)

    def test_absolute_claims_hard_fail(self) -> None:
        result = scan("绝对唯一的最佳选择，效果最强")
        self.assertTrue(result["hard_fail"])
        self.assertIn("COMPLIANCE_RED", result["flags"])

    def test_privacy_collection_is_flagged_but_soft(self) -> None:
        # 索取隐私可能存在授权场景，故标记提示但不硬卡。
        result = scan("把您的手机号发给我登记")
        self.assertIn("PRIVACY_COLLECT", result["flags"])
        self.assertFalse(result["hard_fail"])

    def test_clean_copy_does_not_false_positive(self) -> None:
        for text in (
            "本周会员日，到店消费享8折，欢迎光临",
            "我们在收集点赞数据做复盘",
        ):
            result = scan(text)
            for flag in ("INDUCE_SHARE", "PRIVACY_COLLECT", "COMPLIANCE_RED"):
                self.assertNotIn(flag, result["flags"], f"{text} 误命中 {flag}")


if __name__ == "__main__":
    unittest.main()
