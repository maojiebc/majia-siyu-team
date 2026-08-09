from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import unittest

from siyu_team.state import StateError, StateStore


class RunStoreTests(unittest.TestCase):
    def test_initialize_without_explicit_id_starts_a_new_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / ".siyu-team"
            first = StateStore(root)
            first.initialize("客户 A")
            second = StateStore(root)
            second.initialize("客户 B")

            self.assertNotEqual(first.run_id, second.run_id)
            self.assertEqual(first.read()["client"], "客户 A")
            self.assertEqual(second.read()["client"], "客户 B")

    def test_two_runs_in_same_root_are_isolated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / ".siyu-team"
            first = StateStore(root, run_id="run_a")
            second = StateStore(root, run_id="run_b")
            first.initialize("客户 A")
            second.initialize("客户 B")

            first.update(step=1, add_file="a.md")
            second.update(step=2, add_file="b.md")

            self.assertEqual(first.read()["files_created"], ["a.md"])
            self.assertEqual(second.read()["files_created"], ["b.md"])
            self.assertNotEqual(first.path, second.path)
            self.assertEqual(root.joinpath("current").read_text().strip(), "run_b")
            for store in (first, second):
                self.assertTrue(store.task_path.is_file())
                self.assertTrue(store.outputs_directory.is_dir())
                self.assertTrue(store.traces_directory.is_dir())

    def test_legacy_state_is_copied_without_modifying_original(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / ".siyu-team"
            root.mkdir()
            legacy = root / "state.json"
            original = json.dumps(
                {
                    "client": "旧客户",
                    "status": "in_progress",
                    "current_step": 1,
                },
                ensure_ascii=False,
            )
            legacy.write_text(original, encoding="utf-8")

            store = StateStore(root)
            migrated = store.read()
            store.update(step=2)

            self.assertEqual(legacy.read_text(encoding="utf-8"), original)
            self.assertNotEqual(store.path, legacy)
            self.assertEqual(migrated["migrated_from"], "state.json")
            self.assertEqual(store.read()["current_step"], 2)
            self.assertTrue(legacy.exists())

    def test_file_lock_prevents_lost_updates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / ".siyu-team"
            creator = StateStore(root, run_id="run_parallel")
            creator.initialize("并发客户")

            def add(index: int) -> None:
                # 独立实例模拟两个宿主进程，不共享 Python 对象锁。
                StateStore(root, run_id="run_parallel").update(
                    add_file=f"output-{index}.md"
                )

            with ThreadPoolExecutor(max_workers=8) as executor:
                list(executor.map(add, range(32)))

            state = creator.read()
            self.assertEqual(len(state["files_created"]), 32)
            self.assertEqual(state["revision"], 33)

    def test_expected_revision_rejects_stale_writer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / ".siyu-team", run_id="run_cas")
            initial = store.initialize("CAS 客户")
            store.update(step=1, expected_revision=initial["revision"])
            with self.assertRaisesRegex(StateError, "revision 冲突"):
                store.update(step=2, expected_revision=initial["revision"])
            self.assertEqual(store.read()["current_step"], 1)

    def test_invalid_or_existing_run_id_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / ".siyu-team"
            with self.assertRaises(StateError):
                StateStore(root, run_id="../escape")
            store = StateStore(root, run_id="run_existing")
            store.initialize("客户")
            with self.assertRaisesRegex(StateError, "拒绝覆盖"):
                StateStore(root, run_id="run_existing").initialize("另一个客户")

    def test_raw_conversation_fields_cannot_be_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / ".siyu-team", run_id="run_private")
            store.initialize("隐私客户")

            for payload in (
                {"source_text": "客户原始请求"},
                {"full_chat": "完整聊天"},
                {"result": {"messages": [{"content": "逐字对话"}]}},
                {"prompt": "系统提示词"},
            ):
                with self.subTest(payload=payload):
                    with self.assertRaisesRegex(StateError, "只保存结构化结论"):
                        store.update(**payload)

            self.assertEqual(store.read()["revision"], 1)

    def test_managed_run_directory_symlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / ".siyu-team"
            runs = root / "runs"
            runs.mkdir(parents=True)
            outside = Path(directory) / "outside"
            outside.mkdir()
            runs.joinpath("run_link").symlink_to(outside, target_is_directory=True)

            with self.assertRaisesRegex(StateError, "符号链接"):
                StateStore(root, run_id="run_link").initialize("客户")

            self.assertFalse(outside.joinpath("state.json").exists())

    def test_legacy_and_current_symlinks_are_never_followed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            outside = base / "outside.json"
            outside.write_text(
                json.dumps(
                    {
                        "client": "外部客户",
                        "status": "in_progress",
                        "current_step": 1,
                    }
                ),
                encoding="utf-8",
            )

            legacy_root = base / "legacy" / ".siyu-team"
            legacy_root.mkdir(parents=True)
            legacy_root.joinpath("state.json").symlink_to(outside)
            with self.assertRaisesRegex(StateError, "符号链接"):
                StateStore(legacy_root).read()

            current_root = base / "current" / ".siyu-team"
            current_root.mkdir(parents=True)
            current_root.joinpath("current").symlink_to(outside)
            with self.assertRaisesRegex(StateError, "符号链接"):
                StateStore(current_root)

            self.assertEqual(
                json.loads(outside.read_text(encoding="utf-8"))["client"],
                "外部客户",
            )


if __name__ == "__main__":
    unittest.main()
