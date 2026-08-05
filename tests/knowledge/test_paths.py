from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from siyu_team.knowledge.paths import KnowledgePathResolver


class KnowledgePathTests(unittest.TestCase):
    def test_env_precedes_user_repo_package_and_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resolver = KnowledgePathResolver(
                repository_root=root / "repo",
                package_root=root / "package",
                bundle_root=root / "bundle",
                home=root / "home",
                environ={"SIYU_KNOWLEDGE_HOME": str(root / "explicit")},
            )
            self.assertEqual(
                resolver.candidates(),
                (
                    (root / "explicit").resolve(),
                    (root / "home" / ".siyu-team" / "knowledge").resolve(),
                    (root / "repo" / "knowledge").resolve(),
                    (root / "package").resolve(),
                    (root / "bundle" / "modules" / "_knowledge").resolve(),
                ),
            )

    def test_default_private_root_can_be_created_with_private_mode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            resolver = KnowledgePathResolver(home=Path(directory), environ={})
            root = resolver.writable_root(create=True)
            self.assertTrue(root.is_dir())
            self.assertEqual(root.stat().st_mode & 0o777, 0o700)

    def test_resolution_does_not_depend_on_current_directory(self) -> None:
        resolver = KnowledgePathResolver(environ={})
        repository_knowledge = resolver.candidates()[1]
        expected = Path(__file__).resolve().parents[2] / "knowledge"
        self.assertEqual(repository_knowledge, expected)

    def test_client_id_cannot_escape_private_directory(self) -> None:
        resolver = KnowledgePathResolver(environ={})
        for unsafe in ("", "..", "a/b", "a\\b"):
            with self.assertRaises(ValueError):
                resolver.client_approved_file(unsafe)


if __name__ == "__main__":
    unittest.main()
