from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from siyu_team.context import build_agent_context
from siyu_team.runtime import SiyuRuntime
from siyu_team.task import (
    Channel,
    Goal,
    RiskLevel,
    TaskKind,
    TaskValidationError,
    parse_task,
)
from siyu_team.tracing import TraceRecorder, redact


class TaskParsingTests(unittest.TestCase):
    def test_structural_problem_routes_to_diagnosis_before_copywriting(self) -> None:
        task = parse_task("群发三轮都没人打开，长期这样，问题出在哪？")
        self.assertEqual(task.kind, TaskKind.DIAGNOSIS)
        self.assertEqual(task.channel, Channel.WECHAT_GROUP)
        self.assertEqual(task.goal, Goal.ENGAGEMENT)

    def test_execution_request_routes_to_group_campaign(self) -> None:
        task = parse_task("帮我写一条门店周年活动群发通知")
        self.assertEqual(task.kind, TaskKind.GROUP_CAMPAIGN)
        self.assertEqual(task.channel, Channel.WECHAT_GROUP)
        self.assertEqual(task.goal, Goal.CONVERSION)

    def test_explicit_hints_override_inference(self) -> None:
        task = parse_task(
            "看看这个",
            {
                "kind": "strategy_review",
                "industry": "CATERING",
                "stage": "growth",
            },
        )
        self.assertEqual(task.kind, TaskKind.STRATEGY_REVIEW)
        self.assertEqual(task.channel, Channel.MULTI_CHANNEL)
        self.assertEqual(task.goal, Goal.DIAGNOSIS)
        self.assertEqual(task.industry, "catering")

    def test_high_risk_signal_is_structured_not_executed(self) -> None:
        task = parse_task("批量群发并收集手机号，承诺100%有效")
        self.assertEqual(task.risk, RiskLevel.HIGH)
        self.assertTrue(task.need_compliance_check)

    def test_invalid_enum_fails_closed(self) -> None:
        with self.assertRaises(TaskValidationError):
            parse_task("写朋友圈", {"goal": "make_money"})

    def test_non_json_context_and_non_boolean_flag_fail_closed(self) -> None:
        with self.assertRaises(TaskValidationError):
            parse_task("写朋友圈", {"context": {"bad": object()}})
        with self.assertRaises(TaskValidationError):
            parse_task("写朋友圈", {"need_compliance_check": "false"})


class ContextIsolationTests(unittest.TestCase):
    def test_officers_only_receive_whitelisted_context(self) -> None:
        task = parse_task(
            "帮我做整盘私域战略评审",
            {
                "industry": "catering",
                "stage": "growth",
                "context": {
                    "brand": "示例门店",
                    "offer": "会员券",
                    "budget": 5000,
                    "metrics": {"conversion_rate": 0.1},
                    "token": "must-not-leak",
                },
            },
        )
        public_relations = build_agent_context(task, "公关官").fields
        advertising = build_agent_context(task, "广告官").fields
        compliance = build_agent_context(task, "合规官").fields

        self.assertEqual(public_relations["brand"], "示例门店")
        self.assertNotIn("budget", public_relations)
        self.assertEqual(advertising["budget"], 5000)
        self.assertNotIn("brand", advertising)
        self.assertNotIn("token", compliance)
        self.assertIn("source_text", compliance)

    def test_unknown_officer_fails_closed(self) -> None:
        task = parse_task("全盘诊断")
        with self.assertRaises(ValueError):
            build_agent_context(task, "旁观者")

    def test_personal_data_is_redacted_before_agent_dispatch(self) -> None:
        task = parse_task(
            "帮我做整盘私域战略评审，联系人 13800138000",
            {"audience": "会员 13800138000"},
        )
        context = build_agent_context(task, "合规官").fields
        self.assertNotIn("13800138000", str(context))
        self.assertIn("[PHONE]", str(context))


class RuntimeTests(unittest.TestCase):
    def test_strategy_plan_has_isolated_contexts_and_trace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            recorder = TraceRecorder(Path(directory) / "traces")
            runtime = SiyuRuntime(recorder)
            plan = runtime.plan(
                "帮我做整盘私域战略评审",
                hints={"industry": "catering", "stage": "growth"},
            )
            self.assertEqual(plan.decision.skill, "siyu-onboard")
            self.assertFalse(plan.decision.needs_clarification)
            self.assertEqual(len(plan.agent_contexts), 4)

            trace_path = Path(directory) / "traces" / f"{plan.trace_id}.jsonl"
            records = [
                json.loads(line)
                for line in trace_path.read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(
                [record["event"] for record in records],
                ["task.created", "task.routed", "contexts.created"],
            )

    def test_empty_request_requires_clarification(self) -> None:
        plan = SiyuRuntime().plan("", trace=False)
        self.assertEqual(plan.decision.skill, "/siyu")
        self.assertTrue(plan.decision.needs_clarification)

    def test_incomplete_strategy_does_not_dispatch_officers(self) -> None:
        plan = SiyuRuntime().plan("帮我做整盘私域战略评审", trace=False)
        self.assertTrue(plan.decision.needs_clarification)
        self.assertEqual(plan.agent_contexts, ())

    def test_trace_redacts_credentials_and_personal_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            recorder = TraceRecorder(directory)
            trace_id = recorder.new_trace_id()
            path = recorder.emit(
                trace_id,
                "task_test",
                "test",
                {
                    "token": "secret-value",
                    "message": "联系 13800138000，Bearer abc.def",
                },
            )
            content = path.read_text(encoding="utf-8")
            self.assertNotIn("secret-value", content)
            self.assertNotIn("13800138000", content)
            self.assertNotIn("abc.def", content)
            self.assertIn("[REDACTED]", content)


class RedactionHardeningTests(unittest.TestCase):
    """回归覆盖历史泄漏向量，并确保不误伤正常内容。"""

    def test_phone_with_country_code_is_masked(self) -> None:
        for raw in (
            "+8613812345678",
            "8613812345678",
            "008613812345678",
            "13812345678",
        ):
            self.assertNotIn("13812345678", str(redact({"note": raw})), raw)

    def test_credential_key_names_are_masked(self) -> None:
        for key in (
            "api_key",
            "apiKey",
            "access_key",
            "credential",
            "session",
            "密码",
            "密钥",
        ):
            out = redact({key: "sk-live-DEADBEEF-value"})
            self.assertEqual(out[key], "[REDACTED]", key)

    def test_bare_tokens_in_value_are_masked(self) -> None:
        for raw in ("ghp_abcd1234efgh", "sk-live-DEADBEEF", "AKIAIOSFODNN7EXAMPLE"):
            out = str(redact({"note": f"凭据是 {raw} 请勿外传"}))
            self.assertNotIn(raw, out, raw)
            self.assertIn("[TOKEN]", out, raw)

    def test_email_is_masked(self) -> None:
        out = str(redact({"note": "联系 zhangsan@company.com"}))
        self.assertNotIn("zhangsan@company.com", out)
        self.assertIn("[EMAIL]", out)

    def test_15_digit_id_card_is_masked(self) -> None:
        out = str(redact({"note": "老证号 110101900307817"}))
        self.assertNotIn("110101900307817", out)

    def test_integer_phone_is_masked(self) -> None:
        out = redact({"contact": 13812345678})
        self.assertEqual(out["contact"], "[PHONE]")

    def test_set_values_are_masked(self) -> None:
        out = redact({"s": {"13812345678"}})
        self.assertNotIn("13812345678", str(out))

    def test_does_not_over_redact_normal_content(self) -> None:
        # 含 sk 的普通词、短数字、正常整数、布尔都不应被改。
        self.assertEqual(redact({"job": "task-force123"})["job"], "task-force123")
        self.assertEqual(redact({"order": "12345678"})["order"], "12345678")
        self.assertEqual(redact({"budget": 5000})["budget"], 5000)
        self.assertIs(redact({"flag": True})["flag"], True)


if __name__ == "__main__":
    unittest.main()
