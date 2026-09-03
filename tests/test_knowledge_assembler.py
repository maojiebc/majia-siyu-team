from __future__ import annotations

from dataclasses import replace
import unittest

from siyu_team.knowledge.assembler import KnowledgeAssembler
from siyu_team.knowledge.corpus import Corpus
from siyu_team.knowledge.models import (
    Applicability,
    Confirmation,
    KnowledgeAtomV2,
    Lifecycle,
    Metric,
    Privacy,
    Quality,
    Scope,
    SourceRef,
)
from siyu_team.knowledge.query import KnowledgeQuery, query_atoms
from siyu_team.routing import RouteDecision, route_task
from siyu_team.task import Goal, Task, TaskKind


def _atom(
    index: int,
    *,
    locator: str,
    theme: str,
    layer: str,
    skills: tuple[str, ...] = ("siyu-wenzhen",),
    industry: str = "",
    statement: str = "复购下降时先确认消费周期和真实流失断点。",
    atom_type: str = "method",
    exportable: bool = True,
    contains_pii: bool = False,
) -> KnowledgeAtomV2:
    return KnowledgeAtomV2(
        id=f"ka_{index:016x}",
        statement=statement,
        type=atom_type,
        topics=(theme, layer, "用户增长"),
        skills=skills,
        source=SourceRef(
            source_id=f"src_{index:012x}",
            source_type="expert_judgment",
            label=f"test-{locator}",
            path=f"knowledge/test/{locator}.md",
            locator=locator,
            observed_at="2026-08-01",
        ),
        scope=Scope(
            visibility="public",
            industry=industry,
            scenarios=("user_growth", theme),
        ),
        applicability=Applicability(
            preconditions=("可以按同一消费周期观察用户",),
            recommended_action=("先分层，再验证第一断点",),
            metrics=(
                Metric(
                    name="观察窗复购率",
                    definition="周期内再次消费人数除以可观察人数",
                    time_window="一个消费周期",
                ),
            ),
            failure_modes=("把所有未购用户当成已经流失",),
            counterexamples=("尚未越过正常消费周期时不应判定流失",),
        ),
        quality=Quality(
            evidence_grade="C1",
            confidence="medium",
            review_status="approved",
            reviewer="test-reviewer",
            reviewed_at="2026-08-01",
        ),
        lifecycle=Lifecycle(valid_from="2026-08-01"),
        privacy=Privacy(
            contains_pii=contains_pii,
            contains_client_secret=False,
            exportable=exportable,
        ),
    )


def _corpus(atoms: tuple[KnowledgeAtomV2, ...]) -> Corpus:
    return Corpus.from_atoms(
        atoms,
        corpus_version="test-v1",
        release_batch="test-batch",
    )


def _diagnosis(industry: str) -> tuple[Task, RouteDecision]:
    task = Task(
        kind=TaskKind.DIAGNOSIS,
        source_text="复购下降，帮我定位流失断点",
        goal=Goal.RETENTION,
        industry=industry,
    )
    return task, route_task(task)


class KnowledgeAssemblerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.l0_repurchase = _atom(
            1,
            locator="L0-RETENTION",
            theme="repurchase_recall",
            layer="growth_l0",
        )
        self.l1_repurchase = _atom(
            2,
            locator="L1-RETENTION",
            theme="repurchase_recall",
            layer="growth_l1_catering",
            industry="catering",
        )
        self.l0_acquisition = _atom(
            3,
            locator="L0-ACQUISITION",
            theme="add_wechat",
            layer="growth_l0",
            statement="加微下降时先拆曝光、扫码和好友通过。",
        )
        self.other_skill = _atom(
            4,
            locator="L1-OTHER-SKILL",
            theme="repurchase_recall",
            layer="growth_l1_catering",
            skills=("siyu-qunfa",),
            industry="catering",
        )
        self.corpus = _corpus(
            (
                self.l0_acquisition,
                self.other_skill,
                self.l1_repurchase,
                self.l0_repurchase,
            )
        )

    def test_catering_wenzhen_selects_relevant_l0_and_l1(self) -> None:
        task, decision = _diagnosis("catering")
        selection = KnowledgeAssembler(self.corpus, limit=2).assemble(task, decision)
        self.assertEqual(
            {item.atom.source.locator for item in selection.atoms},
            {"L0-RETENTION", "L1-RETENTION"},
        )
        self.assertEqual({item.layer for item in selection.atoms}, {"l0", "l1_catering"})
        self.assertNotIn(self.other_skill, selection.raw_atoms)

    def test_edu_is_l0_only(self) -> None:
        task, decision = _diagnosis("edu")
        selection = KnowledgeAssembler(self.corpus).assemble(task, decision)
        self.assertGreater(selection.selection_count, 0)
        self.assertTrue(all(item.layer == "l0" for item in selection.atoms))
        self.assertNotIn(self.l1_repurchase, selection.raw_atoms)

    def test_route_skill_slug_is_normalized(self) -> None:
        task, decision = _diagnosis("catering")
        decision = replace(decision, skill="/siyu-wenzhen")
        selection = KnowledgeAssembler(self.corpus, limit=1).assemble(task, decision)
        self.assertEqual(selection.selection_count, 1)
        self.assertIn("skill:siyu-wenzhen", selection.atoms[0].why_selected)

    def test_selection_explains_and_carries_safe_applicability_context(self) -> None:
        task, decision = _diagnosis("catering")
        selection = KnowledgeAssembler(self.corpus, limit=1).assemble(task, decision)
        payload = selection.to_dict()
        self.assertEqual(payload["corpus_version"], "test-v1")
        self.assertTrue(str(payload["corpus_hash"]).startswith("sha256:"))
        self.assertEqual(payload["selection_count"], 1)
        row = payload["atoms"][0]
        self.assertTrue(row["why_selected"])
        self.assertIn("source_id", row)
        self.assertIn("locator", row)
        self.assertIn("statement", row)
        self.assertIn("applicability_summary", row)
        self.assertTrue(row["applicability_summary"]["preconditions"])
        self.assertTrue(row["applicability_summary"]["recommended_action"])
        self.assertTrue(row["applicability_summary"]["metrics"])
        self.assertTrue(row["applicability_summary"]["failure_modes"])
        self.assertEqual(selection.context_rows(), tuple(item.to_dict() for item in selection.atoms))

    def test_external_and_unknown_routes_select_zero(self) -> None:
        for kind, text in (
            (TaskKind.MARKET_RESEARCH, "对比最新 SCRM 报价"),
            (TaskKind.MEMBERSHIP_DATA, "给我会员复购 SQL"),
            (TaskKind.UPDATE, "更新思域"),
            (TaskKind.UNKNOWN, ""),
        ):
            with self.subTest(kind=kind):
                task = Task(kind=kind, source_text=text)
                selection = KnowledgeAssembler(self.corpus).assemble(
                    task,
                    route_task(task),
                )
                self.assertEqual(selection.selection_count, 0)
                self.assertEqual(selection.to_dict()["atoms"], [])

    def test_composition_entry_can_use_relevant_growth_bindings(self) -> None:
        task = Task(
            kind=TaskKind.STRATEGY_REVIEW,
            source_text="评审餐饮私域复购体系",
            goal=Goal.RETENTION,
            industry="catering",
            stage="growth",
        )
        selection = KnowledgeAssembler(self.corpus, limit=2).assemble(
            task,
            route_task(task),
        )
        self.assertEqual(selection.selection_count, 2)
        self.assertTrue(
            all("skill:siyu-onboard" in item.why_selected for item in selection.atoms)
        )

    def test_selection_does_not_depend_on_corpus_file_order(self) -> None:
        task, decision = _diagnosis("catering")
        forward = KnowledgeAssembler(self.corpus, limit=2).assemble(task, decision)
        reversed_corpus = _corpus(tuple(reversed(self.corpus.atoms)))
        backward = KnowledgeAssembler(reversed_corpus, limit=2).assemble(task, decision)
        self.assertEqual(
            [item.atom.id for item in forward.atoms],
            [item.atom.id for item in backward.atoms],
        )

    def test_pilot_may_use_nonexportable_public_atom_but_not_pii(self) -> None:
        nonexportable = _atom(
            20,
            locator="PILOT-SAFE",
            theme="repurchase_recall",
            layer="growth_l0",
            exportable=False,
        )
        pii = _atom(
            21,
            locator="PILOT-PII",
            theme="repurchase_recall",
            layer="growth_l0",
            exportable=False,
            contains_pii=True,
        )
        corpus = _corpus((pii, nonexportable))
        task, decision = _diagnosis("")
        production = KnowledgeAssembler(corpus).assemble(task, decision)
        pilot = KnowledgeAssembler(corpus, public_runtime=False).assemble(task, decision)
        self.assertEqual(production.selection_count, 0)
        self.assertEqual(pilot.raw_atoms, (nonexportable,))

    def test_limit_validation(self) -> None:
        with self.assertRaises(ValueError):
            KnowledgeAssembler(self.corpus, limit=-1)
        task, decision = _diagnosis("")
        with self.assertRaises(ValueError):
            KnowledgeAssembler(self.corpus).assemble(task, decision, limit=-1)

    def test_retail_seed_layer_and_community_grade_tag(self) -> None:
        retail = _atom(
            40,
            locator="L1-RETAIL-SEED",
            theme="repurchase_recall",
            layer="growth_l1_retail",
            industry="retail",
        )
        community = _atom(
            41,
            locator="COMMUNITY-C",
            theme="repurchase_recall",
            layer="growth_l0",
        )
        quality = Quality(
            evidence_grade="C",
            confidence="medium",
            review_status="approved",
            reviewer="community-intake",
            reviewed_at="2026-08-01",
            confirmations=(
                Confirmation("a" * 64, "b" * 64, "2026-08-01"),
                Confirmation("c" * 64, "d" * 64, "2026-08-02"),
            ),
        )
        community = KnowledgeAtomV2(
            **{**community.__dict__, "quality": quality}
        )
        task, decision = _diagnosis("retail")
        selection = KnowledgeAssembler(
            _corpus((self.l0_repurchase, retail)),
            community_atoms=(community,),
            limit=12,
        ).assemble(task, decision)
        locators = {item.atom.source.locator for item in selection.atoms}
        self.assertIn("L0-RETENTION", locators)
        self.assertIn("L1-RETAIL-SEED", locators)
        self.assertIn("COMMUNITY-C", locators)
        community_row = next(
            item for item in selection.atoms if item.atom.source.locator == "COMMUNITY-C"
        )
        self.assertTrue(
            any("社区C级" in reason for reason in community_row.why_selected)
        )
        self.assertEqual(community_row.layer, "l0")
        retail_row = next(
            item for item in selection.atoms if item.atom.source.locator == "L1-RETAIL-SEED"
        )
        self.assertEqual(retail_row.layer, "l1_retail")


class KnowledgeQueryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repurchase = _atom(
            30,
            locator="QUERY-RETENTION",
            theme="repurchase_recall",
            layer="growth_l0",
        )
        self.acquisition = _atom(
            31,
            locator="QUERY-ACQUISITION",
            theme="add_wechat",
            layer="growth_l0",
            statement="加微漏斗要拆成曝光、扫码和好友通过。",
        )
        self.corpus = _corpus((self.acquisition, self.repurchase))

    def test_search_normalizes_slug_and_filters_topic_type_keywords(self) -> None:
        result = KnowledgeQuery(self.corpus).search(
            skills="/siyu-wenzhen",
            topics="repurchase_recall",
            types="method",
            keywords=("复购", "周期"),
            limit=1,
        )
        self.assertEqual(result.atoms, (self.repurchase,))
        self.assertEqual(tuple(result), result.atoms)
        self.assertEqual(result.to_dict()["count"], 1)
        self.assertEqual(result.corpus_version, "test-v1")

    def test_query_output_is_deterministic_and_honors_limit(self) -> None:
        first = KnowledgeQuery(self.corpus).search(skills="siyu-wenzhen", limit=1)
        reversed_corpus = _corpus(tuple(reversed(self.corpus.atoms)))
        second = KnowledgeQuery(reversed_corpus).search(
            skills="siyu-wenzhen",
            limit=1,
        )
        self.assertEqual([atom.id for atom in first], [atom.id for atom in second])

    def test_query_atoms_convenience_and_zero_limit(self) -> None:
        self.assertEqual(
            query_atoms(corpus=self.corpus, topics="missing"),
            (),
        )
        self.assertEqual(
            KnowledgeQuery(self.corpus).search(limit=0).atoms,
            (),
        )
        with self.assertRaises(ValueError):
            KnowledgeQuery(self.corpus).search(limit=-1)


if __name__ == "__main__":
    unittest.main()
