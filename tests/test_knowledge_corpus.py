from __future__ import annotations

from dataclasses import replace
from datetime import date
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from siyu_team.errors import KnowledgeLoadError
from siyu_team.knowledge.corpus import Corpus, CorpusLoader
from siyu_team.knowledge.models import (
    Applicability,
    KnowledgeAtomV2,
    KnowledgeValidationError,
    Lifecycle,
    Metric,
    Privacy,
    Quality,
    Scope,
    SourceRef,
    generate_atom_id,
    generate_source_id,
)
from siyu_team.knowledge.paths import (
    ENV_NAME,
    GROWTH_ATOMS_APPROVED,
    GROWTH_ATOMS_DRAFT,
    KnowledgePathResolver,
)


TODAY = date(2026, 8, 9)


def build_atom(index: int = 0) -> KnowledgeAtomV2:
    source_id = generate_source_id("fixtures/public-corpus.md")
    locator = f"C-{index:02d}"
    return KnowledgeAtomV2(
        id=generate_atom_id(source_id, locator, 0),
        statement=f"公开知识 {index}",
        type="method",
        topics=("growth_l0", "repurchase_recall"),
        skills=("siyu-wenzhen",),
        source=SourceRef(
            source_id=source_id,
            source_type="expert_judgment",
            label="公开方法",
            path="knowledge/00-methodology/public-corpus.md",
            locator=locator,
            observed_at="2026-08-01",
        ),
        scope=Scope(visibility="public"),
        applicability=Applicability(
            preconditions=("已有可观测基线",),
            recommended_action=("先做小流量对照",),
            metrics=(Metric("增量转化率", "实验组减对照组", "7日"),),
            failure_modes=("没有对照就归因",),
        ),
        quality=Quality("C1", "medium", "approved", "reviewer", "2026-08-02"),
        lifecycle=Lifecycle("2026-08-01"),
        privacy=Privacy(exportable=True),
    )


def sha256(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def write_corpus(
    root: Path,
    atoms: tuple[KnowledgeAtomV2, ...] = (),
    *,
    extra_lines: tuple[str, ...] = (),
    manifest_overrides: dict[str, object] | None = None,
) -> tuple[Path, Path]:
    corpus_path = root / GROWTH_ATOMS_APPROVED
    corpus_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [atom.to_json() for atom in atoms] + list(extra_lines)
    raw = (("\n".join(lines) + "\n") if lines else "").encode("utf-8")
    corpus_path.write_bytes(raw)
    digest = sha256(raw)
    manifest: dict[str, object] = {
        "corpus_version": "0.4.0",
        "release_batch": "v1.4.2-public-1",
        "corpus_hash": digest,
        "atom_count": len(lines),
        "atom_schema_version": "2.0",
        "public_corpora": [
            {
                "path": GROWTH_ATOMS_APPROVED,
                "sha256": digest,
                "atom_count": len(lines),
                "atom_schema_version": "2.0",
                "corpus_version": "0.4.0",
                "release_batch": "v1.4.2-public-1",
            }
        ],
    }
    if manifest_overrides:
        manifest.update(manifest_overrides)
    manifest_path = root / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return corpus_path, manifest_path


class CorpusStrictLoadingTests(unittest.TestCase):
    def test_load_validates_manifest_and_raw_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path, manifest = write_corpus(Path(directory), (build_atom(),))
            corpus = CorpusLoader(today=TODAY).load(path, manifest_path=manifest)
            self.assertEqual(corpus.corpus_version, "0.4.0")
            self.assertRegex(corpus.corpus_hash, r"^sha256:[0-9a-f]{64}$")
            self.assertEqual(corpus.metadata.atom_count, 1)
            self.assertEqual(corpus.metadata.atom_schema_version, "2.0")
            self.assertEqual(corpus.atoms, (build_atom(),))
            self.assertEqual(corpus.warnings, ())

    def test_missing_required_manifest_field_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, manifest = write_corpus(root, (build_atom(),))
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            del payload["release_batch"]
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(KnowledgeLoadError, "release_batch"):
                CorpusLoader(today=TODAY).load(path, manifest_path=manifest)

    def test_descriptor_schema_alias_must_match_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path, manifest = write_corpus(Path(directory), (build_atom(),))
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            descriptor = payload["public_corpora"][0]
            descriptor.pop("atom_schema_version")
            descriptor["schema_version"] = "9.9"
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(KnowledgeLoadError, "schema_version"):
                CorpusLoader(today=TODAY).load(path, manifest_path=manifest)

    def test_raw_hash_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path, manifest = write_corpus(Path(directory), (build_atom(),))
            path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            with self.assertRaisesRegex(KnowledgeLoadError, "hash"):
                CorpusLoader(today=TODAY).load(path, manifest_path=manifest)

    def test_raw_record_count_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path, manifest = write_corpus(
                Path(directory),
                (build_atom(),),
                manifest_overrides={"atom_count": 2},
            )
            with self.assertRaisesRegex(KnowledgeLoadError, "atom_count"):
                CorpusLoader(today=TODAY).load(path, manifest_path=manifest)

    def test_atom_schema_mismatch_is_hard_error_even_when_lenient(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data = build_atom().to_dict()
            data["schema_version"] = "9.9"
            path, manifest = write_corpus(
                Path(directory), extra_lines=(json.dumps(data),)
            )
            with self.assertRaisesRegex(KnowledgeLoadError, "Schema"):
                CorpusLoader(today=TODAY, lenient=True).load(
                    path, manifest_path=manifest
                )

    def test_duplicate_atom_id_always_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            atom = build_atom()
            path, manifest = write_corpus(Path(directory), (atom, atom))
            with self.assertRaisesRegex(KnowledgeLoadError, "重复 atom_id"):
                CorpusLoader(today=TODAY, lenient=True).load(
                    path, manifest_path=manifest
                )

    def test_malformed_defaults_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path, manifest = write_corpus(
                Path(directory), (build_atom(),), extra_lines=("{broken",)
            )
            with self.assertRaisesRegex(KnowledgeLoadError, "JSON 非法"):
                CorpusLoader(today=TODAY).load(path, manifest_path=manifest)

    def test_lenient_explicitly_skips_malformed_and_warns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path, manifest = write_corpus(
                Path(directory), (build_atom(),), extra_lines=("{broken",)
            )
            corpus = CorpusLoader(today=TODAY, lenient=True).load(
                path, manifest_path=manifest
            )
            self.assertEqual(len(corpus.atoms), 1)
            self.assertTrue(
                any(item.startswith("malformed_skipped:") for item in corpus.warnings)
            )


class CorpusDiscoveryTests(unittest.TestCase):
    def test_high_priority_draft_does_not_shadow_lower_approved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            high = base / "high"
            draft = high / GROWTH_ATOMS_DRAFT
            draft.parent.mkdir(parents=True)
            draft.write_text(build_atom(9).to_json() + "\n", encoding="utf-8")

            low_repository = base / "low-repository"
            approved, _ = write_corpus(
                low_repository / "knowledge", (build_atom(1),)
            )
            resolver = KnowledgePathResolver(
                repository_root=low_repository,
                package_root=base / "missing-package",
                home=base / "home",
                environ={ENV_NAME: str(high)},
            )
            corpus = CorpusLoader(resolver, today=TODAY).load()
            self.assertEqual(corpus.source_path, approved.resolve())
            self.assertEqual(tuple(atom.id for atom in corpus.atoms), (build_atom(1).id,))

    def test_no_approved_source_returns_explicit_empty_corpus(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            resolver = KnowledgePathResolver(
                repository_root=base / "repo",
                package_root=base / "package",
                home=base / "home",
                environ={},
            )
            corpus = CorpusLoader(resolver, today=TODAY).load()
            self.assertEqual(corpus.corpus_version, "unavailable")
            self.assertEqual(corpus.atoms, ())
            self.assertIn("current_no_available_public_corpus", corpus.warnings)

    def test_existing_approved_without_manifest_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / GROWTH_ATOMS_APPROVED
            path.parent.mkdir(parents=True)
            path.write_text(build_atom().to_json() + "\n", encoding="utf-8")
            resolver = KnowledgePathResolver(
                repository_root=root.parent / "unused",
                package_root=root,
                home=root.parent / "home",
                environ={ENV_NAME: str(root)},
            )
            with self.assertRaisesRegex(KnowledgeLoadError, "manifest"):
                CorpusLoader(resolver, today=TODAY).load()


class CorpusSafetyFilterTests(unittest.TestCase):
    def test_filters_status_visibility_privacy_and_lifecycle(self) -> None:
        valid = build_atom(0)
        draft = replace(
            build_atom(1),
            quality=Quality("C1", "medium", "draft"),
        )
        rejected = replace(
            build_atom(2),
            quality=Quality("C1", "medium", "rejected"),
        )
        retired = replace(
            build_atom(3),
            quality=Quality("C1", "medium", "retired"),
        )
        private = replace(
            build_atom(4),
            scope=Scope(visibility="expert_private"),
            privacy=Privacy(exportable=False),
        )
        not_exportable = replace(
            build_atom(5), privacy=Privacy(exportable=False)
        )
        pii = replace(
            build_atom(6),
            privacy=Privacy(contains_pii=True, exportable=False),
        )
        secret = replace(
            build_atom(7),
            privacy=Privacy(contains_client_secret=True, exportable=False),
        )
        future = replace(
            build_atom(8), lifecycle=Lifecycle("2026-08-10")
        )
        expired = replace(
            build_atom(9), lifecycle=Lifecycle("2026-01-01", "2026-08-08")
        )
        atoms = (
            valid,
            draft,
            rejected,
            retired,
            private,
            not_exportable,
            pii,
            secret,
            future,
            expired,
        )
        with tempfile.TemporaryDirectory() as directory:
            path, manifest = write_corpus(Path(directory), atoms)
            corpus = CorpusLoader(today=TODAY).load(path, manifest_path=manifest)
        self.assertEqual(corpus.atoms, (valid,))
        warnings = "\n".join(corpus.warnings)
        self.assertIn("review_status=draft", warnings)
        self.assertIn("review_status=rejected", warnings)
        self.assertIn("review_status=retired", warnings)
        self.assertIn("future_valid", warnings)
        self.assertIn("expired", warnings)

    def test_active_atom_removes_atom_it_supersedes(self) -> None:
        old = build_atom(0)
        replacement = replace(
            build_atom(1),
            lifecycle=Lifecycle("2026-08-02", supersedes=(old.id,)),
        )
        with tempfile.TemporaryDirectory() as directory:
            path, manifest = write_corpus(Path(directory), (old, replacement))
            corpus = CorpusLoader(today=TODAY).load(path, manifest_path=manifest)
        self.assertEqual(corpus.atoms, (replacement,))
        self.assertIn("filtered:superseded_by_active_atom:1", corpus.warnings)

    def test_sensitive_atom_cannot_be_exportable_at_model_boundary(self) -> None:
        for privacy in (
            {"contains_pii": True, "exportable": True},
            {"contains_client_secret": True, "exportable": True},
        ):
            with self.subTest(privacy=privacy):
                with self.assertRaises(KnowledgeValidationError):
                    Privacy(**privacy)


class ApprovedCompletenessTests(unittest.TestCase):
    def assert_incomplete(self, atom: KnowledgeAtomV2, expected: str) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path, manifest = write_corpus(Path(directory), (atom,))
            with self.assertRaisesRegex(KnowledgeLoadError, expected):
                CorpusLoader(today=TODAY).load(path, manifest_path=manifest)

    def test_requires_precondition(self) -> None:
        atom = build_atom()
        self.assert_incomplete(
            replace(
                atom,
                applicability=replace(atom.applicability, preconditions=()),
            ),
            "preconditions",
        )

    def test_requires_recommended_action(self) -> None:
        atom = build_atom()
        self.assert_incomplete(
            replace(
                atom,
                applicability=replace(atom.applicability, recommended_action=()),
            ),
            "recommended_action",
        )

    def test_requires_metric_or_explicit_not_applicable_marker(self) -> None:
        atom = build_atom()
        self.assert_incomplete(
            replace(
                atom,
                applicability=replace(atom.applicability, metrics=()),
            ),
            "metrics_or_explicit_not_applicable",
        )
        marked = replace(
            atom,
            applicability=replace(
                atom.applicability,
                metrics=(),
                recommended_action=(
                    "先执行安全检查",
                    "metric:not_applicable 该条目仅定义硬红线",
                ),
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            path, manifest = write_corpus(Path(directory), (marked,))
            corpus = CorpusLoader(today=TODAY).load(path, manifest_path=manifest)
        self.assertEqual(corpus.atoms, (marked,))

    def test_requires_failure_mode_or_counterexample(self) -> None:
        atom = build_atom()
        self.assert_incomplete(
            replace(
                atom,
                applicability=replace(
                    atom.applicability,
                    failure_modes=(),
                    counterexamples=(),
                ),
            ),
            "failure_modes_or_counterexamples",
        )


class CorpusFixtureConstructionTests(unittest.TestCase):
    def test_from_atoms_is_deterministic_and_keeps_controlled_private_fixture(self) -> None:
        controlled = replace(build_atom(), privacy=Privacy(exportable=False))
        first = Corpus.from_atoms((controlled,), corpus_version="fixture-1")
        second = Corpus.from_atoms((controlled,), corpus_version="fixture-1")
        self.assertEqual(first.corpus_hash, second.corpus_hash)
        self.assertEqual(first.atoms, (controlled,))
        self.assertIsNone(first.source_path)

    def test_from_atoms_still_rejects_duplicate_ids(self) -> None:
        atom = build_atom()
        with self.assertRaisesRegex(KnowledgeLoadError, "重复 atom_id"):
            Corpus.from_atoms((atom, atom))


if __name__ == "__main__":
    unittest.main()
