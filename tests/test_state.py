from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from siyu_team.state import StateError, StateStore


class StateStoreTests(unittest.TestCase):
    def test_initialize_update_and_complete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / ".siyu-team")
            state = store.initialize("示例客户", "catering", "growth")
            self.assertEqual(state["current_step"], 0)

            state = store.update(
                step=1,
                add_file="00-intake.md",
                add_completed="intake",
            )
            store.update(add_file="00-intake.md", add_completed="intake")
            self.assertEqual(state["files_created"], ["00-intake.md"])
            self.assertEqual(state["completed_steps"], ["intake"])

            completed = store.update(status="complete")
            self.assertEqual(completed["status"], "complete")
            self.assertEqual(completed["current_step"], "complete")

    def test_invalid_transition_fields_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / ".siyu-team")
            with self.assertRaises(StateError):
                store.initialize("")
            store.initialize("示例客户")
            with self.assertRaises(StateError):
                store.update(step=-1)
            with self.assertRaises(StateError):
                store.update(status="anything")
            with self.assertRaises(StateError):
                store.update(current_step=-1)

    def test_legacy_state_is_migrated_on_next_update(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_directory = Path(directory) / ".siyu-team"
            state_directory.mkdir()
            path = state_directory / "state.json"
            path.write_text(
                json.dumps(
                    {
                        "client": "旧客户",
                        "status": "in_progress",
                        "current_step": 1,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            store = StateStore(state_directory)
            self.assertEqual(store.read()["schema_version"], "1.0")
            store.update(step=2)
            persisted = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["schema_version"], "1.0")


if __name__ == "__main__":
    unittest.main()
