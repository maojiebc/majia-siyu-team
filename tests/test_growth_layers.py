from __future__ import annotations

import unittest

from siyu_team.knowledge.growth_layers import (
    L0_DOC,
    L1_CATERING_DOC,
    describe_growth_load,
    growth_atom_id,
    load_growth_atoms,
    select_growth_doc_refs,
    select_growth_topics,
)
from siyu_team.perspectives import build_isolated_officer_prompt
from siyu_team.routing import route_task
from siyu_team.runtime import SiyuRuntime
from siyu_team.task import TaskKind, parse_task


class GrowthLayerTests(unittest.TestCase):
    def test_no_industry_only_l0_docs(self) -> None:
        refs = select_growth_doc_refs("")
        self.assertEqual(refs, (L0_DOC,))
        self.assertNotIn(L1_CATERING_DOC, refs)

    def test_catering_loads_l0_and_l1(self) -> None:
        refs = select_growth_doc_refs("catering")
        self.assertEqual(refs[0], L0_DOC)
        self.assertIn(L1_CATERING_DOC, refs)

    def test_retail_shares_l1_for_now(self) -> None:
        self.assertIn(L1_CATERING_DOC, select_growth_doc_refs("retail"))

    def test_edu_only_l0(self) -> None:
        self.assertEqual(select_growth_doc_refs("edu"), (L0_DOC,))

    def test_topics_filter(self) -> None:
        self.assertEqual(select_growth_topics(""), ("growth_l0",))
        self.assertEqual(
            select_growth_topics("catering"),
            ("growth_l0", "growth_l1_catering"),
        )

    def test_growth_atoms_are_approved(self) -> None:
        atoms = load_growth_atoms("catering")
        self.assertGreater(len(atoms), 0)
        for atom in atoms:
            self.assertEqual(atom.quality.review_status, "approved")
            self.assertTrue(atom.quality.reviewer)
            themes = [t for t in ("add_wechat", "activity_increment", "repurchase_recall") if t in atom.topics]
            self.assertEqual(len(themes), 1)

    def test_draft_atoms_filter_by_industry(self) -> None:
        bare = load_growth_atoms("")
        cat = load_growth_atoms("catering")
        self.assertGreater(len(bare), 0)
        self.assertGreater(len(cat), len(bare))
        for atom in bare:
            self.assertIn("growth_l0", atom.topics)
            self.assertNotIn("growth_l1_catering", atom.topics)
        self.assertTrue(any("growth_l1_catering" in a.topics for a in cat))

    def test_atom_id_stable(self) -> None:
        a = growth_atom_id(L0_DOC, "L0-01", 0)
        b = growth_atom_id(L0_DOC, "L0-01", 0)
        c = growth_atom_id(L0_DOC, "L0-02", 0)
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertTrue(a.startswith("ka_"))

    def test_route_unknown_industry_gets_l0_only(self) -> None:
        plan_task = parse_task("群转化差怎么办")
        decision = route_task(plan_task)
        self.assertIn(L0_DOC, decision.knowledge_refs)
        self.assertNotIn(L1_CATERING_DOC, decision.knowledge_refs)
        self.assertIn("只加载通用", decision.focus)

    def test_route_catering_gets_l1(self) -> None:
        task = parse_task(
            "帮我看整盘私域",
            hints={"industry": "catering", "stage": "growth"},
        )
        # may be strategy or diagnosis
        decision = route_task(task)
        if task.kind is not TaskKind.MARKET_RESEARCH:
            self.assertIn(L0_DOC, decision.knowledge_refs)
            self.assertIn(L1_CATERING_DOC, decision.knowledge_refs)

    def test_market_research_skips_growth_layers(self) -> None:
        decision = route_task(parse_task("对比现在的 SCRM 厂商和报价"))
        self.assertEqual(decision.knowledge_refs, ())

    def test_describe_plain(self) -> None:
        self.assertIn("未声明业态", describe_growth_load(""))
        self.assertIn("L1", describe_growth_load("catering"))

    def test_officer_prompt_lists_growth_locators(self) -> None:
        plan = SiyuRuntime().plan(
            "帮我做整盘私域战略评审",
            hints={"industry": "catering", "stage": "growth"},
            trace=False,
        )
        ctx = plan.agent_contexts[0]
        prompt = build_isolated_officer_prompt(
            {"name": ctx.officer, "engine": "测", "description": "测"},
            ctx,
            routing="test",
        )
        self.assertIn("增长参考", prompt)
        self.assertIn("L0-01", prompt)


if __name__ == "__main__":
    unittest.main()

class GrowthContextInjectionTests(unittest.TestCase):
    def test_diagnosis_plan_attaches_l0_atoms_without_industry(self) -> None:
        from siyu_team.runtime import SiyuRuntime
        plan = SiyuRuntime().plan("群转化差、复购不行，帮我看看", trace=False)
        self.assertEqual(plan.decision.skill, "siyu-wenzhen")
        self.assertGreater(len(plan.growth_atoms), 0)
        self.assertTrue(all(a.get("layer") == "l0" for a in plan.growth_atoms))
        self.assertIn("未声明业态", plan.growth_load_note)
        # 诊断不派四位专家，但计划上必须带得上原子
        self.assertEqual(plan.agent_contexts, ())

    def test_strategy_contexts_include_growth_atoms(self) -> None:
        from siyu_team.runtime import SiyuRuntime
        plan = SiyuRuntime().plan(
            "帮我做整盘私域战略评审",
            hints={"industry": "catering", "stage": "growth"},
            trace=False,
        )
        self.assertFalse(plan.decision.needs_clarification)
        self.assertEqual(len(plan.agent_contexts), 4)
        self.assertGreater(len(plan.growth_atoms), 0)
        self.assertTrue(any(a.get("layer") == "l1_catering" for a in plan.growth_atoms))
        for ctx in plan.agent_contexts:
            self.assertIn("growth_atoms", ctx.fields)
            self.assertIn("growth_load_note", ctx.fields)
            self.assertGreater(len(ctx.fields["growth_atoms"]), 0)

    def test_market_research_has_no_growth_atoms(self) -> None:
        from siyu_team.runtime import SiyuRuntime
        plan = SiyuRuntime().plan("对比 SCRM 厂商报价", trace=False)
        self.assertEqual(plan.growth_atoms, ())
        self.assertEqual(plan.growth_load_note, "")
