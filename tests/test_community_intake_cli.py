from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from siyu_team.knowledge.models import KnowledgeAtomV2


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/community/sample_records.json"
WORKFLOW = ROOT / ".github/workflows/community-intake.yml"
SALT = "community-intake-test-salt"


def _scrubbed_env() -> dict[str, str]:
    return {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("SIYU_", "LARK_"))
    }


def _load_cli():
    path = ROOT / "tools/community_intake.py"
    spec = importlib.util.spec_from_file_location("community_intake_cli", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CommunityIntakeCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cli = _load_cli()

    def setUp(self) -> None:
        self._env_patch = patch.dict(os.environ, _scrubbed_env(), clear=True)
        self._env_patch.start()

    def tearDown(self) -> None:
        self._env_patch.stop()

    def test_salt_for_tests_required_in_fixture_mode(self) -> None:
        code = self.cli.main(
            ["--dry-run", "--from-json", str(FIXTURE)]
        )
        self.assertEqual(code, 2)

    def test_salt_for_tests_rejected_outside_dry_run_fixture(self) -> None:
        code = self.cli.main(
            ["--from-json", str(FIXTURE), "--salt-for-tests", SALT]
        )
        self.assertEqual(code, 2)

    def test_dry_run_fixture_with_test_salt_succeeds(self) -> None:
        code = self.cli.main(
            [
                "--dry-run",
                "--from-json",
                str(FIXTURE),
                "--salt-for-tests",
                SALT,
            ]
        )
        self.assertEqual(code, 0)

    def test_partition_puts_approved_community_apart_from_pending(self) -> None:
        seed_line = (
            ROOT / "knowledge/05-community/seeds.retail.jsonl"
        ).read_text(encoding="utf-8").splitlines()[0]
        seed = KnowledgeAtomV2.from_json(seed_line)
        approved_payload = seed.to_dict()
        approved_payload["source"]["source_type"] = "community"
        approved_payload["quality"]["review_status"] = "approved"
        approved_payload["quality"]["evidence_grade"] = "B"
        approved_payload["quality"]["reviewer"] = "maintainer"
        approved = KnowledgeAtomV2.from_dict(approved_payload)
        pending_payload = seed.to_dict()
        pending_payload["id"] = "ka_aaaaaaaaaaaaaaaa"
        pending_payload["source"]["source_type"] = "community"
        pending_payload["quality"]["review_status"] = "pending"
        pending = KnowledgeAtomV2.from_dict(pending_payload)
        buckets = self.cli._partition((approved, pending, seed))
        self.assertEqual(buckets["approved"], [approved])
        self.assertEqual(buckets["pending"], [pending])
        self.assertEqual(buckets["seed"], [seed])

    def test_zero_record_run_keeps_manifest_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            community = root / "05-community"
            community.mkdir(parents=True)
            src = ROOT / "knowledge/05-community"
            (community / "seeds.retail.jsonl").write_bytes(
                (src / "seeds.retail.jsonl").read_bytes()
            )
            seed_before = (community / "seeds.retail.jsonl").read_bytes()
            # 先用同样的 files/metrics 写一次基线 manifest，避免依赖仓库里真实
            # manifest 的当前状态（线上 Action 写入真实原子后会变化）。
            baseline_files = {
                "seeds.retail.jsonl": (
                    seed_before.count(b"\n"),
                    self.cli._sha256_bytes(seed_before),
                )
            }
            self.cli._write_manifest(
                community / "manifest.json",
                files=baseline_files,
                metrics={
                    "submissions_total": 0,
                    "pending_total": 0,
                    "approved_total": 0,
                    "rejected_total": 0,
                    "needs_manual": 0,
                    "median_hours_submit_to_approve": None,
                },
                last_run="2000-01-01T00:00:00Z",
            )
            before = (community / "manifest.json").read_bytes()
            existing = self.cli._existing_pipeline_atoms(community)
            previous = self.cli._partition(existing)
            merged = self.cli._merge_by_id(existing, ())
            buckets = self.cli._partition(merged)
            for name, key, path in (
                ("pending.jsonl", "pending", community / "pending.jsonl"),
                ("approved.jsonl", "approved", community / "approved.jsonl"),
                ("seeds.retail.jsonl", "seed", community / "seeds.retail.jsonl"),
            ):
                del name
                self.cli._write_jsonl_if_needed(path, buckets[key], previous[key])
            files = {
                "seeds.retail.jsonl": (
                    seed_before.count(b"\n"),
                    self.cli._sha256_bytes(seed_before),
                )
            }
            changed = self.cli._write_manifest(
                community / "manifest.json",
                files=files,
                metrics={
                    "submissions_total": 0,
                    "pending_total": 0,
                    "approved_total": 0,
                    "rejected_total": 0,
                    "needs_manual": 0,
                    "median_hours_submit_to_approve": None,
                },
                last_run="2099-01-01T00:00:00Z",
            )
            self.assertFalse(changed)
            self.assertEqual((community / "manifest.json").read_bytes(), before)
            self.assertEqual((community / "seeds.retail.jsonl").read_bytes(), seed_before)
            self.assertFalse((community / "pending.jsonl").exists())
            self.assertFalse((community / "inbox.jsonl").exists())

    def test_sync_skips_pending_and_rejected(self) -> None:
        path = ROOT / "tools/sync_public_knowledge.py"
        spec = importlib.util.spec_from_file_location("siyu_sync_public_knowledge", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        names = {str(item) for item in module.expected_files()}
        self.assertTrue(any(name.endswith("05-community/approved.jsonl") for name in names))
        self.assertFalse(any(name.endswith("05-community/pending.jsonl") for name in names))
        self.assertFalse(any(name.endswith("05-community/rejected.jsonl") for name in names))

    def test_workflow_skips_missing_salt_and_retries_push(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("SIYU_HASH_SALT", text)
        self.assertIn("[ \"${#SIYU_HASH_SALT}\" -lt 16 ]", text)
        self.assertIn("git pull --rebase origin main", text)
        self.assertIn("for attempt in 1 2 3", text)
        self.assertIn("make check", text)
        check_at = text.index("make check")
        commit_at = text.index("git commit")
        self.assertLess(check_at, commit_at)
        self.assertIn("opening PR", text)
        self.assertIn("SIYU_INTAKE_MODE", text)
        self.assertIn("vars.SIYU_INTAKE_MODE", text)
        self.assertIn("LARK_PUBLIC_BASE_TOKEN", text)
        self.assertIn("LARK_PUBLIC_TABLE", text)

    def test_revoke_cli_removes_atom_and_writes_log(self) -> None:
        seed_line = (
            ROOT / "knowledge/05-community/seeds.retail.jsonl"
        ).read_text(encoding="utf-8").splitlines()[0]
        atom = KnowledgeAtomV2.from_json(seed_line)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            community = root / "05-community"
            community.mkdir()
            (community / "seeds.retail.jsonl").write_text(seed_line + "\n", encoding="utf-8")
            code = self.cli.main(
                [
                    "--knowledge-root",
                    str(root),
                    "--revoke",
                    atom.id,
                    "--reason",
                    "maintainer",
                ]
            )
            self.assertEqual(code, 0)
            remaining = (community / "seeds.retail.jsonl").read_text(encoding="utf-8")
            self.assertNotIn(atom.id, remaining)
            revoked = (community / "revoked.jsonl").read_text(encoding="utf-8")
            self.assertIn(atom.id, revoked)
            self.assertIn("maintainer", revoked)
            self.assertTrue((community / "manifest.json").is_file())


if __name__ == "__main__":
    unittest.main()
