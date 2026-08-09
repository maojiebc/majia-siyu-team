"""Python Runtime、Prompt-only 分发与 ExecutionPlan 的共同契约。"""
from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any
import unittest

from siyu_team.routing import (
    TASK_ROUTES,
    normalize_skill_slug,
    route_contract_digest,
    route_contract_document,
    route_task,
)
from siyu_team.runtime import PLAN_SCHEMA_VERSION, RuntimeMode, SiyuRuntime
from siyu_team.task import parse_task


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "tests/fixtures/routing-contract-cases.jsonl"
PLUGIN_CONTRACT = (
    ROOT
    / "plugins/siyu-core/skills/majia-siyu/references/route-contract.json"
)
SKILLHUB_CONTRACT = (
    ROOT / "skillhub/majia-siyu/modules/_runtime/route-contract.json"
)

REQUIRED_CATEGORIES = frozenset(
    {
        "single_intent",
        "multi_intent",
        "archive_conflict",
        "dynamic_market_facts",
        "membership_data_boundary",
        "high_risk",
        "empty_or_unknown",
        "industry_capability",
    }
)
EXPECTED_CASE_FIELDS = frozenset(
    {
        "kind",
        "skill",
        "needs_clarification",
        "required_fields",
        "risk",
        "industry_book",
    }
)


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _load_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for line_no, raw_line in enumerate(
        FIXTURE_PATH.read_text(encoding="utf-8").splitlines(), 1
    ):
        line = raw_line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AssertionError(
                f"路由合同夹具不是合法 JSON：{FIXTURE_PATH}:{line_no}"
            ) from exc
        if not isinstance(value, dict):
            raise AssertionError(
                f"路由合同夹具每行必须是对象：{FIXTURE_PATH}:{line_no}"
            )
        cases.append(value)
    return cases


def _route_skill_map(document: Mapping[str, Any]) -> dict[str, str]:
    """兼容 routes 的对象/数组表示，提取 kind -> normalized skill。"""
    routes = document.get("routes")
    result: dict[str, str] = {}
    if isinstance(routes, Mapping):
        for kind, value in routes.items():
            if isinstance(value, Mapping):
                skill = value.get("skill")
            else:
                skill = value
            if isinstance(skill, str):
                result[str(kind)] = skill
        return result
    if isinstance(routes, list):
        for entry in routes:
            if not isinstance(entry, Mapping):
                continue
            kind = entry.get("kind")
            skill = entry.get("skill")
            if isinstance(kind, str) and isinstance(skill, str):
                result[kind] = skill
        return result
    raise AssertionError("route-contract.routes 必须是对象或数组")


def _canonical_contract_digest(document: Mapping[str, Any]) -> str:
    payload = dict(document)
    payload.pop("content_sha256", None)
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


class RoutingFixtureContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = _load_cases()

    def test_fixture_has_at_least_fifty_unique_categorized_cases(self) -> None:
        self.assertGreaterEqual(len(self.cases), 50)
        ids = [case.get("id") for case in self.cases]
        self.assertTrue(all(isinstance(case_id, str) and case_id for case_id in ids))
        self.assertEqual(len(ids), len(set(ids)), "路由合同 case id 必须唯一")

        categories = {case.get("category") for case in self.cases}
        self.assertTrue(
            REQUIRED_CATEGORIES.issubset(categories),
            f"缺少必需分类：{sorted(REQUIRED_CATEGORIES - categories)}",
        )

    def test_fixture_rows_have_complete_human_expectations(self) -> None:
        for case in self.cases:
            with self.subTest(case=case.get("id")):
                self.assertEqual(
                    set(case), {"id", "category", "request", "hints", "expected"}
                )
                self.assertIsInstance(case["request"], str)
                self.assertIsInstance(case["hints"], dict)
                self.assertIsInstance(case["expected"], dict)
                self.assertEqual(set(case["expected"]), EXPECTED_CASE_FIELDS)

    def test_python_parser_and_router_match_every_human_expectation(self) -> None:
        for case in self.cases:
            with self.subTest(case=case["id"], category=case["category"]):
                task = parse_task(case["request"], case["hints"])
                decision = route_task(task)
                actual = {
                    "kind": task.kind.value,
                    "skill": decision.skill,
                    "needs_clarification": decision.needs_clarification,
                    "required_fields": list(decision.required_fields),
                    "risk": task.risk.value,
                    "industry_book": decision.industry_book,
                }
                self.assertEqual(actual, case["expected"])

    def test_prompt_contract_routes_match_fixture_expectations(self) -> None:
        route_skills = _route_skill_map(route_contract_document())
        for case in self.cases:
            expected = case["expected"]
            with self.subTest(case=case["id"], kind=expected["kind"]):
                self.assertIn(expected["kind"], route_skills)
                self.assertEqual(
                    route_skills[expected["kind"]],
                    normalize_skill_slug(expected["skill"]),
                )


class GeneratedRouteContractTests(unittest.TestCase):
    def test_contract_document_has_stable_top_level_shape(self) -> None:
        document = route_contract_document()
        self.assertEqual(
            set(document),
            {
                "contract_schema_version",
                "content_sha256",
                "task",
                "routes",
                "industry_capabilities",
                "stages",
                "required_fields",
            },
        )
        self.assertEqual(document["contract_schema_version"], "1.0")

    def test_rendered_contracts_are_byte_identical_and_current(self) -> None:
        plugin_bytes = PLUGIN_CONTRACT.read_bytes()
        skillhub_bytes = SKILLHUB_CONTRACT.read_bytes()
        self.assertEqual(plugin_bytes, skillhub_bytes)

        rendered = json.loads(plugin_bytes.decode("utf-8"))
        self.assertEqual(rendered, route_contract_document())

    def test_contract_content_hash_is_valid(self) -> None:
        document = json.loads(PLUGIN_CONTRACT.read_text(encoding="utf-8"))
        claimed = document.get("content_sha256")
        self.assertIsInstance(claimed, str)
        self.assertRegex(claimed, r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(claimed, _canonical_contract_digest(document))
        self.assertEqual(claimed, route_contract_digest())

    def test_render_route_contract_check_mode_passes(self) -> None:
        result = _run("tools/render_route_contract.py", "--check")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_all_runtime_routes_use_normalized_slugs(self) -> None:
        for kind, (skill, _reason) in TASK_ROUTES.items():
            with self.subTest(kind=kind.value, skill=skill):
                self.assertFalse(skill.startswith("/"))
                self.assertEqual(skill, normalize_skill_slug(skill))

    def test_slug_normalization_accepts_legacy_leading_slash(self) -> None:
        for raw in ("siyu-pyq", "/siyu-pyq", " /siyu-pyq "):
            with self.subTest(raw=raw):
                self.assertEqual(normalize_skill_slug(raw), "siyu-pyq")


class ExecutionPlanContractTests(unittest.TestCase):
    def test_runtime_modes_and_schema_version_are_stable(self) -> None:
        self.assertEqual(PLAN_SCHEMA_VERSION, "1.0")
        self.assertEqual(RuntimeMode.PYTHON.value, "python")
        self.assertEqual(RuntimeMode.PROMPT_ONLY.value, "prompt_only")

    def test_python_plan_has_complete_v1_shape_and_legacy_fields(self) -> None:
        plan = SiyuRuntime().plan(
            "餐饮私域转化差怎么办",
            hints={"industry": "catering"},
            trace=False,
        )
        payload = plan.to_dict()
        expected_top_level = {
            "plan_schema_version",
            "runtime_mode",
            "trace_id",
            "task",
            "decision",
            "knowledge",
            "warnings",
            "agent_contexts",
            "growth_atoms",
            "growth_load_note",
        }
        self.assertEqual(set(payload), expected_top_level)
        self.assertEqual(payload["plan_schema_version"], PLAN_SCHEMA_VERSION)
        self.assertEqual(payload["runtime_mode"], RuntimeMode.PYTHON.value)
        self.assertIs(plan.runtime_mode, RuntimeMode.PYTHON)
        self.assertIsInstance(payload["warnings"], list)

        knowledge = payload["knowledge"]
        self.assertIsInstance(knowledge, dict)
        self.assertTrue(
            {"corpus_version", "corpus_hash", "selection_count", "atoms"}
            .issubset(knowledge)
        )
        self.assertIsInstance(knowledge["corpus_version"], str)
        self.assertTrue(knowledge["corpus_version"])
        self.assertIsInstance(knowledge["corpus_hash"], str)
        self.assertTrue(knowledge["corpus_hash"])
        self.assertIsInstance(knowledge["selection_count"], int)
        self.assertIsInstance(knowledge["atoms"], list)
        self.assertEqual(knowledge["selection_count"], len(knowledge["atoms"]))

        for atom in knowledge["atoms"]:
            self.assertTrue(
                {"id", "source_id", "locator", "why_selected"}.issubset(atom)
            )
            self.assertIsInstance(atom["why_selected"], list)
            self.assertTrue(atom["why_selected"])
            self.assertEqual(
                len(atom["why_selected"]), len(set(atom["why_selected"]))
            )

        # 旧消费者仍可继续读取 growth_*，不必立即迁移到 knowledge。
        self.assertEqual(payload["growth_atoms"], list(plan.growth_atoms))
        self.assertEqual(payload["growth_load_note"], plan.growth_load_note)

        schema = json.loads(
            (ROOT / "schemas/execution-plan-v1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertTrue(set(schema["required"]).issubset(payload))
        self.assertFalse(schema["additionalProperties"])


class RepositoryRegressionTests(unittest.TestCase):
    def test_repository_no_longer_mentions_nonexistent_plan_call(self) -> None:
        needle = "Siyu后台自动系统" + ".plan()"
        ignored_parts = {".git", ".venv", "__pycache__", "build", "dist"}
        text_suffixes = {
            "",
            ".json",
            ".jsonl",
            ".md",
            ".py",
            ".sh",
            ".toml",
            ".txt",
            ".yaml",
            ".yml",
        }
        offenders: list[str] = []
        for path in ROOT.rglob("*"):
            relative = path.relative_to(ROOT)
            if ignored_parts.intersection(relative.parts):
                continue
            if not path.is_file() or path.suffix.lower() not in text_suffixes:
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if needle in content:
                offenders.append(relative.as_posix())
        self.assertEqual(offenders, [], f"仍存在概念性伪调用：{offenders}")


if __name__ == "__main__":
    unittest.main()
