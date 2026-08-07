"""routing.py 的路由决策测试。"""
from __future__ import annotations

import unittest

from siyu_team.knowledge.growth_layers import L0_DOC, L1_CATERING_DOC
from siyu_team.knowledge.paths import COMPLIANCE_REDLINES_DOC, METHODOLOGY_AXIOMS_DOC
from siyu_team.routing import route_task
from siyu_team.task import Task, TaskKind


class TestRouteTask(unittest.TestCase):
    def test_moments_copy_route(self) -> None:
        task = Task(kind=TaskKind.MOMENTS_COPY, source_text="写朋友圈")
        decision = route_task(task)
        self.assertEqual(decision.skill, "/siyu-pyq")
        self.assertFalse(decision.needs_clarification)

    def test_market_research_skip_industry_book(self) -> None:
        """市场调研任务不注入 industry_book / 合规方法论包。"""
        task = Task(
            kind=TaskKind.MARKET_RESEARCH,
            source_text="对比 SCRM",
            industry="catering",
        )
        decision = route_task(task)
        self.assertIsNone(decision.industry_book)
        self.assertEqual(decision.knowledge_refs, ())
        self.assertNotIn("knowledge/02-industry/catering/", decision.knowledge_refs)

    def test_strategy_review_requires_industry_if_missing(self) -> None:
        """全盘诊断缺 industry → required_fields 含 industry。"""
        task = Task(kind=TaskKind.STRATEGY_REVIEW, source_text="整盘怎么搭")
        decision = route_task(task)
        self.assertTrue(decision.needs_clarification)
        self.assertIn("industry", decision.required_fields)

    def test_strategy_review_with_industry_no_clarification(self) -> None:
        """全盘诊断已有 industry 和 stage → 不需要澄清。"""
        task = Task(
            kind=TaskKind.STRATEGY_REVIEW,
            source_text="整盘怎么搭",
            industry="catering",
            stage="cold",
        )
        decision = route_task(task)
        self.assertFalse(decision.needs_clarification)
        self.assertEqual(decision.required_fields, ())
        self.assertIn(COMPLIANCE_REDLINES_DOC, decision.knowledge_refs)
        self.assertIn(METHODOLOGY_AXIOMS_DOC, decision.knowledge_refs)
        self.assertIn(L0_DOC, decision.knowledge_refs)
        self.assertIn(L1_CATERING_DOC, decision.knowledge_refs)

    def test_unknown_kind_requires_kind_field(self) -> None:
        """kind=UNKNOWN → required_fields=['kind']。"""
        task = Task(kind=TaskKind.UNKNOWN, source_text="你好")
        decision = route_task(task)
        self.assertTrue(decision.needs_clarification)
        self.assertIn("kind", decision.required_fields)

    def test_diagnosis_focus_includes_growth_note(self) -> None:
        task = Task(kind=TaskKind.DIAGNOSIS, source_text="转化差怎么办")
        decision = route_task(task)
        self.assertIn("L0", decision.focus)
        self.assertIn(L0_DOC, decision.knowledge_refs)



class TestLowConfidenceRouting(unittest.TestCase):
    def test_low_confidence_requires_kind_confirmation(self) -> None:
        task = Task(
            kind=TaskKind.MOMENTS_COPY,
            source_text="写朋友圈和群发通知",
            confidence=0.56,
        )
        decision = route_task(task)
        self.assertTrue(decision.needs_clarification)
        self.assertIn("kind", decision.required_fields)
        self.assertIn("先确认", decision.reason)
        self.assertEqual(decision.confidence, 0.56)

    def test_high_confidence_does_not_clarify(self) -> None:
        task = Task(
            kind=TaskKind.MOMENTS_COPY,
            source_text="写本周朋友圈",
            confidence=0.8,
        )
        decision = route_task(task)
        self.assertFalse(decision.needs_clarification)
        self.assertEqual(decision.required_fields, ())

    def test_uncomputed_confidence_does_not_clarify(self) -> None:
        """直接构造的 Task（confidence=None）不触发置信度追问。"""
        task = Task(kind=TaskKind.MOMENTS_COPY, source_text="写朋友圈")
        decision = route_task(task)
        self.assertFalse(decision.needs_clarification)
        self.assertIsNone(decision.confidence)

if __name__ == "__main__":
    unittest.main()
