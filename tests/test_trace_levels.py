from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import time
import unittest

from siyu_team import cli as plan_cli
from siyu_team.runtime import SiyuRuntime
from siyu_team.tracing import TraceLevel, TraceRecorder, cleanup_old_traces


def _records(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]


class TraceLevelTests(unittest.TestCase):
    def test_default_metadata_omits_source_and_context(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            recorder = TraceRecorder(Path(directory) / "traces")
            plan = SiyuRuntime(trace_recorder=recorder).plan(
                "帮我写朋友圈，联系人 13800138000，内部策略代号海鸥",
                hints={
                    "client": "机密客户",
                    "audience": "高价值会员",
                    "context": {"internal_strategy": "海鸥"},
                },
            )
            path = recorder.directory / f"{plan.trace_id}.jsonl"
            text = path.read_text(encoding="utf-8")
            created = _records(path)[0]

        self.assertNotIn("13800138000", text)
        self.assertNotIn("海鸥", text)
        self.assertNotIn("机密客户", text)
        self.assertNotIn("source_text", text)
        self.assertEqual(created["trace_level"], "metadata")
        payload = created["payload"]
        assert isinstance(payload, dict)
        self.assertGreater(payload["source_length"], 0)
        self.assertTrue(str(payload["source_hash"]).startswith("sha256:"))

    def test_redacted_level_keeps_safe_content_but_masks_sensitive_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            recorder = TraceRecorder(directory, level=TraceLevel.REDACTED)
            path = recorder.emit(
                recorder.new_trace_id(),
                "task_test",
                "task.created",
                {
                    "kind": "moments_copy",
                    "risk": "medium",
                    "source_text": "普通内容，联系 13800138000",
                    "context": {"token": "sk-live-abcdef12"},
                },
            )
            text = path.read_text(encoding="utf-8")

        self.assertIn("普通内容", text)
        self.assertIn("[PHONE]", text)
        self.assertIn("[REDACTED]", text)
        self.assertNotIn("13800138000", text)
        self.assertNotIn("sk-live-abcdef12", text)

    def test_full_level_keeps_source_only_when_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            recorder = TraceRecorder(directory, level="full")
            path = recorder.emit(
                recorder.new_trace_id(),
                "task_test",
                "task.created",
                {"source_text": "完整请求 13800138000"},
            )
            text = path.read_text(encoding="utf-8")

        self.assertIn("完整请求 13800138000", text)
        self.assertIn('"trace_level":"full"', text)

    def test_cli_wires_explicit_trace_level(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            trace_dir = Path(directory) / "traces"
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = plan_cli.main(
                    [
                        "写一条朋友圈，联系 13800138000",
                        "--trace-level",
                        "redacted",
                        "--trace-dir",
                        str(trace_dir),
                    ]
                )
            written = next(trace_dir.glob("trace_*.jsonl"))
            text = written.read_text(encoding="utf-8")

        self.assertEqual(code, 0)
        self.assertIn('"trace_level":"redacted"', text)
        self.assertNotIn("13800138000", text)

    def test_startup_cleanup_applies_ttl_and_capacity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stale = root / "trace_stale.jsonl"
            old_fresh = root / "trace_old_fresh.jsonl"
            newest = root / "trace_newest.jsonl"
            for path in (stale, old_fresh, newest):
                path.write_text("{}\n", encoding="utf-8")
            now = time.time()
            os.utime(stale, (now - 40 * 24 * 3600, now - 40 * 24 * 3600))
            os.utime(old_fresh, (now - 20, now - 20))
            os.utime(newest, (now - 10, now - 10))

            TraceRecorder(root, retention_days=30, max_files=1, max_bytes=None)

            remaining = sorted(path.name for path in root.glob("trace_*.jsonl"))
        self.assertEqual(remaining, ["trace_newest.jsonl"])

    def test_startup_cleanup_enforces_byte_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            oldest = root / "trace_a.jsonl"
            newest = root / "trace_b.jsonl"
            oldest.write_text("12345", encoding="utf-8")
            newest.write_text("67890", encoding="utf-8")
            now = time.time()
            os.utime(oldest, (now - 10, now - 10))
            os.utime(newest, (now - 5, now - 5))

            TraceRecorder(root, max_files=None, max_bytes=5)

            remaining = sorted(path.name for path in root.glob("trace_*.jsonl"))
        self.assertEqual(remaining, ["trace_b.jsonl"])

    def test_trace_id_cannot_escape_trace_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "traces"
            recorder = TraceRecorder(root)
            with self.assertRaisesRegex(ValueError, "trace_id"):
                recorder.emit("../escape", "task_test", "test", {"value": 1})
            self.assertFalse(Path(directory).joinpath("escape.jsonl").exists())

    def test_preexisting_trace_symlink_is_never_followed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "traces"
            root.mkdir()
            target = Path(directory) / "outside.txt"
            target.write_text("do-not-touch", encoding="utf-8")
            root.joinpath("trace_attacker.jsonl").symlink_to(target)
            recorder = TraceRecorder(root)

            with self.assertRaisesRegex(ValueError, "路径不安全"):
                recorder.emit(
                    "trace_attacker",
                    "task_test",
                    "test",
                    {"value": "malicious"},
                )

            self.assertEqual(target.read_text(encoding="utf-8"), "do-not-touch")

    def test_cleanup_rejects_symlink_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "outside"
            target.mkdir()
            trace = target / "trace_external.jsonl"
            trace.write_text("keep", encoding="utf-8")
            linked_root = Path(directory) / "linked-traces"
            linked_root.symlink_to(target, target_is_directory=True)

            with self.assertRaisesRegex(ValueError, "符号链接"):
                cleanup_old_traces(linked_root, days=0)

            self.assertEqual(trace.read_text(encoding="utf-8"), "keep")

    def test_unreasonably_large_retention_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "不得超过"):
                TraceRecorder(directory, retention_days=36_501)


if __name__ == "__main__":
    unittest.main()
