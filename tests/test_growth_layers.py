from __future__ import annotations

import unittest

from siyu_team.knowledge.growth_layers import (
    L0_DOC,
    L1_CATERING_DOC,
    describe_growth_load,
    growth_atom_id,
    load_growth_draft_atoms,
    select_growth_doc_refs,
    select_growth_topics,
)
from siyu_team.routing import route_task
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

    def test_draft_atoms_filter_by_industry(self) -> None:
        bare = load_growth_draft_atoms("")
        cat = load_growth_draft_atoms("catering")
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


if __name__ == "__main__":
    unittest.main()
