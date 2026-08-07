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


    def test_weighted_penalty_high_severity_single_flag(self) -> None:
        """单个高危 flag 的惩罚应不轻于低危绝对化表述。"""
        result_high = scan("100% 稳赚不赔")
        result_low = scan("绝对领先的唯一首选")
        self.assertTrue(result_high["hard_fail"])
        self.assertLessEqual(result_high["penalty"], result_low["penalty"])
        self.assertLess(result_high["penalty"], 1.0)

    def test_penalty_uses_severity_not_count(self) -> None:
        """penalty 应等于 1 - sum(severity)，并下限夹到 0.5。"""
        result = scan("100% 稳赚 最好 最佳")
        expected = max(0.5, 1.0 - sum(d["severity"] for d in result["details"]))
        self.assertAlmostEqual(result["penalty"], expected)



class ComplianceBlockedErrorTests(unittest.TestCase):
    def test_assert_compliant_raises_with_reasons(self) -> None:
        from siyu_team.errors import ComplianceBlockedError
        from siyu_team.eval.static import assert_compliant

        with self.assertRaises(ComplianceBlockedError) as ctx:
            assert_compliant("集赞转发拉人，100% 稳赚")
        self.assertIn("INDUCE_SHARE", ctx.exception.flags)
        self.assertGreater(len(ctx.exception.details), 0)
        self.assertTrue(all("desc" in d for d in ctx.exception.details))

    def test_assert_compliant_returns_scan_result_when_clean(self) -> None:
        from siyu_team.eval.static import assert_compliant

        result = assert_compliant("本周会员日到店 8 折")
        self.assertFalse(result["hard_fail"])
        self.assertGreater(result["penalty"], 0.5)

    def test_absolute_claim_softened_by_attribution(self) -> None:
        from siyu_team.eval.static import scan

        for text in (
            "对方自称领先品牌，实际效果待验证",
            "据报道称该品牌是唯一供应商",
            "厂商对外宣称最佳方案，需要尽调",
        ):
            result = scan(text)
            self.assertNotIn("ABSOLUTE_CLAIM", result["flags"], text)

    def test_absolute_claim_still_fires_without_attribution(self) -> None:
        from siyu_team.eval.static import scan

        result = scan("本店是本地领先品牌，服务最好")
        self.assertIn("ABSOLUTE_CLAIM", result["flags"])

if __name__ == "__main__":
    unittest.main()
