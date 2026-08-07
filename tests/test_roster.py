"""roster 接线测试：官名单可配置（换角色不碰代码），默认行为不变。"""
from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from siyu_team.roster import DEFAULT_OFFICERS, load_roster, normalize_officers
from siyu_team.runtime import PANEL_OFFICERS, SiyuRuntime
from siyu_team.tracing import TraceRecorder


def _strategy_review_plan(runtime: SiyuRuntime):
    return runtime.plan(
        "帮我全面复盘这盘私域该怎么打",
        hints={"kind": "strategy_review", "industry": "catering", "stage": "growth"},
        trace=False,
    )


class TestRosterWiring(unittest.TestCase):
    def _runtime(self, roster=None) -> SiyuRuntime:
        return SiyuRuntime(
            trace_recorder=TraceRecorder(tempfile.mkdtemp()), roster=roster
        )

    def test_default_panel_matches_builtin(self) -> None:
        plan = _strategy_review_plan(self._runtime())
        self.assertEqual(
            tuple(context.officer for context in plan.agent_contexts),
            PANEL_OFFICERS,
        )

    def test_custom_officer_joins_panel(self) -> None:
        roster = {
            "version": "1.0.0",
            "officers": [
                *DEFAULT_OFFICERS,
                {
                    "name": "财务官",
                    "engine": "成本口径",
                    "description": "只盯预算与回收周期。",
                    "allowed_context": ["budget", "metrics"],
                },
            ],
        }
        plan = _strategy_review_plan(self._runtime(roster))
        officers = [context.officer for context in plan.agent_contexts]
        self.assertIn("财务官", officers)
        self.assertEqual(len(officers), 5)

    def test_custom_officer_without_allowlist_fails_closed(self) -> None:
        roster = {
            "officers": [
                {"name": "神秘官", "engine": "未知", "description": "没有声明白名单"}
            ]
        }
        with self.assertRaises(ValueError):
            _strategy_review_plan(self._runtime(roster))

    def test_empty_roster_falls_back_to_builtin(self) -> None:
        plan = _strategy_review_plan(self._runtime({"officers": []}))
        self.assertEqual(
            tuple(context.officer for context in plan.agent_contexts),
            PANEL_OFFICERS,
        )


class TestRosterLoading(unittest.TestCase):
    def test_negative_k_returns_empty(self) -> None:
        self.assertEqual(normalize_officers(k=-1), [])

    def test_k_capped_at_max(self) -> None:
        self.assertEqual(len(normalize_officers(k=99)), len(DEFAULT_OFFICERS))

    def test_broken_roster_warns_and_falls_back(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            broken = Path(tmp) / "roster.json"
            broken.write_text("{坏掉的JSON", encoding="utf-8")
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                roster = load_roster(str(broken))
        self.assertEqual(roster["officers"], DEFAULT_OFFICERS)
        self.assertIn("roster 加载失败", err.getvalue())

    def test_valid_roster_file_loads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "roster.json"
            path.write_text(
                json.dumps({"officers": [{"name": "公关官"}]}, ensure_ascii=False),
                encoding="utf-8",
            )
            roster = load_roster(str(path))
        self.assertEqual(roster["officers"][0]["name"], "公关官")


if __name__ == "__main__":
    unittest.main()
