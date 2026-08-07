"""task.py 的路由回归测试。"""
from __future__ import annotations

import unittest

from siyu_team.task import (
    Channel,
    Goal,
    RiskLevel,
    TaskKind,
    infer_kind_with_confidence,
    parse_task,
)


class TestParseTask(unittest.TestCase):
    def test_save_memory_vs_moments_copy(self) -> None:
        """保存+朋友圈 → MOMENTS_COPY 优先，不误判为 SAVE_MEMORY。"""
        task = parse_task("保存上次朋友圈文案")
        self.assertEqual(task.kind, TaskKind.MOMENTS_COPY)

    def test_diagnosis_vs_group_campaign(self) -> None:
        """群发+异常 → DIAGNOSIS，不误判为 GROUP_CAMPAIGN。"""
        task = parse_task("群发三轮打开率还是很低，问题出在哪？")
        self.assertEqual(task.kind, TaskKind.DIAGNOSIS)

    def test_strategy_review_clear(self) -> None:
        """明确的全盘搭建 → STRATEGY_REVIEW。"""
        task = parse_task("帮我全面搭建私域体系")
        self.assertEqual(task.kind, TaskKind.STRATEGY_REVIEW)

    def test_market_research_vendor(self) -> None:
        """厂商选型 → MARKET_RESEARCH。"""
        task = parse_task("对比两家 SCRM 系统的报价和功能")
        self.assertEqual(task.kind, TaskKind.MARKET_RESEARCH)

    def test_moments_copy_with_audience(self) -> None:
        """带受众的朋友圈请求 → 正确推断 channel。"""
        task = parse_task("写本周朋友圈，主推周末套餐，受众是上班族")
        self.assertEqual(task.kind, TaskKind.MOMENTS_COPY)
        self.assertEqual(task.channel, Channel.WECHAT_MOMENTS)
        self.assertIn(task.goal, {Goal.CONVERSION, Goal.ENGAGEMENT, Goal.UNKNOWN})

    def test_high_risk_keywords(self) -> None:
        """触发高危关键词 → risk=HIGH。"""
        task = parse_task("批量群发 100% 中奖活动，拉 50 人送礼")
        self.assertEqual(task.risk, RiskLevel.HIGH)

    def test_medium_risk_keywords(self) -> None:
        """中危关键词 → risk=MEDIUM。"""
        task = parse_task("群发优惠券给会员")
        self.assertEqual(task.risk, RiskLevel.MEDIUM)

    def test_hints_override_inferred_kind(self) -> None:
        """显式 hints 覆盖正则推断。"""
        task = parse_task("写本周朋友圈", hints={"kind": "diagnosis"})
        self.assertEqual(task.kind, TaskKind.DIAGNOSIS)

    def test_industry_stage_normalization(self) -> None:
        """industry/stage 字段 strip + lower。"""
        task = parse_task(
            "写朋友圈",
            hints={"industry": " Catering ", "stage": " COLD "},
        )
        self.assertEqual(task.industry, "catering")
        self.assertEqual(task.stage, "cold")

    def test_unknown_fallback(self) -> None:
        """无明确意图 → UNKNOWN。"""
        task = parse_task("你好")
        self.assertEqual(task.kind, TaskKind.UNKNOWN)

    def test_pure_save_memory_still_works(self) -> None:
        """纯存档请求仍走 SAVE_MEMORY。"""
        task = parse_task("把这次结论保存下来")
        self.assertEqual(task.kind, TaskKind.SAVE_MEMORY)

    def test_infer_kind_confidence_range(self) -> None:
        kind, confidence = infer_kind_with_confidence("写本周朋友圈")
        self.assertEqual(kind, TaskKind.MOMENTS_COPY)
        self.assertGreater(confidence, 0.5)
        self.assertLessEqual(confidence, 1.0)


if __name__ == "__main__":
    unittest.main()
