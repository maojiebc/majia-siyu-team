"""One business request must retain every requested output and its gates."""
from __future__ import annotations

import unittest

from siyu_team.errors import TaskValidationError
from siyu_team.runtime import SiyuRuntime


CAMPAIGN = "为同一场周末活动写朋友圈、群发通知和顾客私聊答疑话术，活动规则已经确定"
RECALL = "先按会员消费记录圈选召回人群，再写私聊召回话术"


class CompositionTests(unittest.TestCase):
    def plan(self, request: str, composition: dict | None = None):
        hints = {"context": {"composition": composition}} if composition is not None else None
        return SiyuRuntime().plan(request, hints=hints, trace=False)

    def workflow(self, plan):
        return plan.to_dict().get("workflow") or {}

    def skills(self, plan):
        return [step["skill"] for step in self.workflow(plan).get("steps", [])]

    def test_same_campaign_produces_all_three_outputs_without_intent_question(self):
        plan = self.plan(CAMPAIGN)
        self.assertEqual(self.skills(plan), ["siyu-pyq", "siyu-qunfa", "siyu-huashu"])
        self.assertFalse(plan.decision.needs_clarification)
        self.assertEqual(plan.agent_contexts, ())
        self.assertEqual(self.workflow(plan)["execution"], "sequential")

    def test_data_selection_is_retained_before_recall_copy(self):
        plan = self.plan(RECALL, {"available_skills": ["majia-huiyuan"]})
        self.assertEqual(self.skills(plan), ["majia-huiyuan", "siyu-huashu"])
        first, second = self.workflow(plan)["steps"]
        self.assertEqual(first["target_type"], "external")
        self.assertEqual(first["status"], "ready")
        self.assertEqual(second["depends_on"], [first["id"]])
        self.assertEqual(second["status"], "waiting")
        self.assertEqual(plan.decision.skill, "majia-huiyuan")

    def test_missing_external_skill_blocks_dependent_copy(self):
        plan = self.plan(RECALL, {"available_skills": []})
        self.assertEqual(self.skills(plan), ["majia-huiyuan", "siyu-huashu"])
        first, second = self.workflow(plan)["steps"]
        self.assertEqual(first["status"], "blocked")
        self.assertEqual(second["status"], "blocked")
        self.assertIn("majia-huiyuan", first["reason"])
        self.assertEqual(self.workflow(plan)["status"], "blocked")

    def test_one_moments_copy_still_goes_straight_to_one_skill(self):
        plan = self.plan("给新品写一条朋友圈文案")
        self.assertEqual(self.skills(plan), ["siyu-pyq"])
        self.assertFalse(plan.decision.needs_clarification)
        self.assertEqual(self.workflow(plan)["steps"][0]["status"], "ready")

    def test_channel_comparison_does_not_request_both_outputs(self):
        plan = self.plan("朋友圈还是群发通知更适合这次活动？")
        self.assertEqual(self.skills(plan), [])
        self.assertTrue(plan.decision.needs_clarification)

    def test_channel_names_in_material_are_not_three_new_assignments(self):
        plan = self.plan("这是朋友圈、群发、私聊话术的历史数据，请诊断为什么转化差")
        self.assertEqual(plan.decision.skill, "siyu-wenzhen")
        self.assertEqual(self.skills(plan), ["siyu-wenzhen"])

    def test_negated_channel_is_not_scheduled(self):
        plan = self.plan("不要写朋友圈，只写群发通知")
        self.assertEqual(self.skills(plan), ["siyu-qunfa"])
        self.assertFalse(plan.decision.needs_clarification)

    def test_finished_copy_is_not_rewritten(self):
        plan = self.plan("朋友圈已经定稿，只补同一活动的群发通知")
        self.assertEqual(self.skills(plan), ["siyu-qunfa"])

    def test_diagnosis_is_a_gate_before_content(self):
        plan = self.plan("先诊断群不活跃的原因，再写群发通知")
        self.assertEqual(self.skills(plan), ["siyu-wenzhen", "siyu-qunfa"])
        first, second = self.workflow(plan)["steps"]
        self.assertEqual(second["depends_on"], [first["id"]])
        self.assertEqual(second["status"], "waiting")

    def test_diagnosis_stop_does_not_release_content(self):
        plan = self.plan("先诊断群不活跃的原因，再写群发通知", {
            "results": {
                "diagnosis": {
                    "status": "passed", "artifact": "outputs/diagnosis.md",
                    "disposition": "stop",
                }
            }
        })
        self.assertEqual(self.skills(plan), ["siyu-wenzhen", "siyu-qunfa"])
        self.assertEqual(self.workflow(plan)["steps"][1]["status"], "blocked")
        self.assertNotEqual(self.workflow(plan)["status"], "complete")

    def test_verified_audience_releases_copy_without_running_data_again(self):
        plan = self.plan(RECALL, {
            "results": {
                "membership_audience": {
                    "status": "passed", "artifact": "outputs/audience-rules.md",
                    "disposition": "proceed",
                }
            },
        })
        self.assertEqual(self.skills(plan), ["majia-huiyuan", "siyu-huashu"])
        first, second = self.workflow(plan)["steps"]
        self.assertEqual(first["status"], "complete")
        self.assertEqual(second["status"], "ready")
        self.assertEqual(plan.decision.skill, "siyu-huashu")

    def test_failed_one_channel_does_not_block_unrelated_channel_drafts(self):
        plan = self.plan(CAMPAIGN, {
            "results": {
                "moments_copy": {
                    "status": "failed", "artifact": "outputs/moments.md",
                    "reason": "合规检查未通过",
                }
            },
        })
        self.assertEqual(self.skills(plan), ["siyu-pyq", "siyu-qunfa", "siyu-huashu"])
        self.assertEqual([s["status"] for s in self.workflow(plan)["steps"]],
                         ["blocked", "ready", "ready"])
        self.assertNotEqual(self.workflow(plan)["status"], "complete")

    def test_handoff_keeps_facts_and_hypotheses_separate(self):
        plan = self.plan(CAMPAIGN, {
            "confirmed_facts": {"活动截止": "以用户确认的规则为准"},
            "hypotheses": ["疑似权益吸引力不足，尚未验证"],
        })
        steps = self.workflow(plan).get("steps", [])
        self.assertEqual(len(steps), 3)
        for step in steps:
            handoff = step["handoff"]
            self.assertEqual(handoff["original_request"], "task.source_text")
            self.assertEqual(handoff["confirmed_facts"], "task.context.composition.confirmed_facts")
            self.assertEqual(handoff["hypotheses"], "task.context.composition.hypotheses")
            self.assertTrue(step["acceptance"])

    def test_bad_completion_record_cannot_skip_work(self):
        for record in (
            {"status": "passed"},
            {"status": "passed", "artifact": "", "disposition": "proceed"},
            {"status": "passed", "artifact": "outputs/data.md"},
        ):
            with self.subTest(record=record), self.assertRaises(TaskValidationError):
                self.plan(RECALL, {"results": {"membership_audience": record}})

    def test_declared_outputs_support_host_interpretation_without_keyword_guess(self):
        plan = self.plan("按已经确认的活动条件，补齐两个触达渠道", {
            "deliverables": ["moments_copy", "group_message"],
        })
        self.assertEqual(self.skills(plan), ["siyu-pyq", "siyu-qunfa"])
        self.assertFalse(plan.decision.needs_clarification)

    def test_unknown_output_is_rejected_instead_of_hallucinating_a_skill(self):
        with self.assertRaises(TaskValidationError):
            self.plan("帮我发出去", {"deliverables": ["publish_to_wechat"]})

    def test_finished_campaign_still_needs_cross_channel_review(self):
        plan = self.plan(CAMPAIGN, {
            "results": {
                output: {"status": "passed", "artifact": f"outputs/{output}.md"}
                for output in ("moments_copy", "group_message", "dm_script")
            },
        })
        self.assertEqual(self.workflow(plan)["status"], "awaiting_review")
        self.assertEqual(plan.decision.skill, "majia-siyu")
        self.assertFalse(plan.decision.needs_clarification)

    def test_finished_single_output_does_not_start_over(self):
        plan = self.plan("写一条朋友圈", {
            "results": {
                "moments_copy": {"status": "passed", "artifact": "outputs/copy.md"}
            },
        })
        self.assertEqual(self.workflow(plan)["status"], "complete")
        self.assertEqual(plan.decision.skill, "majia-siyu")
        self.assertFalse(plan.decision.needs_clarification)

    def test_membership_rules_are_not_overwritten_by_copy_intent(self):
        for request in (
            "先确定会员流失阈值，再写私聊召回话术",
            "先按 RFM 分层规则分析会员，再写私聊召回话术",
        ):
            with self.subTest(request=request):
                plan = self.plan(request)
                self.assertEqual(self.skills(plan), ["majia-huiyuan", "siyu-huashu"])
                self.assertEqual(self.workflow(plan)["steps"][-1]["status"], "blocked")

    def test_dynamic_fact_gate_survives_a_stronger_data_intent(self):
        plan = self.plan("先圈出90天未购会员，核验当前平台规则，再写群发通知", {
            "results": {
                "membership_audience": {
                    "status": "passed", "artifact": "audience.md", "disposition": "proceed",
                },
            },
        })
        self.assertEqual(self.skills(plan), ["majia-huiyuan", "siyu-market-research", "siyu-qunfa"])
        self.assertEqual(self.workflow(plan)["steps"][-1]["status"], "waiting")

    def test_failed_final_review_blocks_even_one_output(self):
        plan = self.plan("写一条朋友圈", {
            "results": {
                "moments_copy": {"status": "passed", "artifact": "copy.md"},
            },
            "delivery_review": {
                "status": "failed", "artifact": "review.md", "reason": "价格冲突未解决",
            },
        })
        self.assertEqual(self.workflow(plan)["status"], "blocked")
        self.assertTrue(plan.decision.needs_clarification)

    def test_channel_specific_script_does_not_add_private_messages(self):
        for request, expected in (
            ("给社群写一条群发话术", ["siyu-qunfa"]),
            ("帮我写一条朋友圈话术", ["siyu-pyq"]),
        ):
            with self.subTest(request=request):
                self.assertEqual(self.skills(self.plan(request)), expected)

    def test_negation_after_channel_and_on_prerequisite_is_respected(self):
        for request, expected in (
            ("朋友圈不要写，只写群发通知", ["siyu-qunfa"]),
            ("不需要圈选会员，直接写私聊话术", ["siyu-huashu"]),
        ):
            with self.subTest(request=request):
                self.assertEqual(self.skills(self.plan(request)), expected)

    def test_explicit_prerequisite_order_is_preserved(self):
        plan = self.plan("先诊断召回是否值得做，再圈选会员，再写私聊话术")
        self.assertEqual(self.skills(plan), ["siyu-wenzhen", "majia-huiyuan", "siyu-huashu"])
        self.assertEqual(self.workflow(plan)["steps"][0]["status"], "ready")
        self.assertEqual(self.workflow(plan)["steps"][1]["status"], "waiting")

    def test_diagnosis_joined_with_and_is_still_a_requested_step(self):
        plan = self.plan("帮我诊断群不活跃的原因，并写群发通知")
        self.assertEqual(self.skills(plan), ["siyu-wenzhen", "siyu-qunfa"])

    def test_parallel_outputs_can_share_one_verb_across_a_comma(self):
        plan = self.plan("帮我写朋友圈，群发通知和私聊答疑")
        self.assertEqual(self.skills(plan), ["siyu-pyq", "siyu-qunfa", "siyu-huashu"])

    def test_writing_constraint_does_not_remove_requested_output(self):
        for ending in ("但不要写得太长", "不要写太长", "但不要写群发通知"):
            with self.subTest(ending=ending):
                plan = self.plan("先核验最新平台规则，再写朋友圈" + ending, {
                    "results": {
                        "market_evidence": {
                            "status": "passed", "artifact": "market.md",
                            "disposition": "proceed",
                        },
                    },
                })
                self.assertEqual(self.skills(plan), ["siyu-market-research", "siyu-pyq"])
                self.assertEqual(self.workflow(plan)["steps"][-1]["status"], "ready")
                self.assertNotEqual(self.workflow(plan)["status"], "complete")

    def test_explicit_archive_kind_is_not_overridden_by_material_keywords(self):
        plan = SiyuRuntime().plan(
            "把当前会员 RFM 分层规则存档，不要重算",
            hints={"kind": "save_memory"}, trace=False,
        )
        self.assertEqual(plan.decision.skill, "siyu-save")
        self.assertFalse(plan.decision.needs_clarification)
        self.assertIsNone(plan.workflow)

    def test_diagnostic_wording_keeps_existing_dynamic_fact_route(self):
        plan = self.plan("请诊断当前平台规则变化对我们的影响")
        self.assertEqual(plan.decision.skill, "siyu-market-research")
        self.assertIsNone(plan.workflow)

    def test_explicit_content_kind_still_respects_completed_artifact(self):
        plan = SiyuRuntime().plan("写一条朋友圈", hints={
            "kind": "moments_copy",
            "context": {"composition": {"results": {
                "moments_copy": {"status": "passed", "artifact": "copy.md"},
            }}},
        }, trace=False)
        self.assertEqual(self.workflow(plan)["status"], "complete")
        self.assertEqual(plan.decision.skill, "majia-siyu")


if __name__ == "__main__":
    unittest.main()
