#!/usr/bin/env python3
"""Sync the public knowledge truth source into wheel package data."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "knowledge"
PACKAGE_ROOT = ROOT / "src/siyu_team/knowledge/data"
BUNDLE_ROOT = ROOT / "skillhub/majia-siyu/modules/_knowledge"
PUBLIC_DIRS = ("00-methodology", "01-wechat-official", "02-industry", "04-atoms", "05-community")
COMMUNITY_UNSHIPPED = frozenset({"pending.jsonl", "rejected.jsonl"})
_BARE_KNOWLEDGE_RE = re.compile(
    r"(?<![\w/])knowledge/(00-methodology|01-wechat-official|02-industry|04-atoms|05-community)"
)


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _jsonl_summary(path: Path) -> tuple[int, set[str]]:
    count = 0
    versions: set[str] = set()
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no} JSON 非法：{exc.msg}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_no} 必须是对象")
        count += 1
        versions.add(str(row.get("schema_version", "")))
    return count, versions


def validate_manifest(root: Path) -> list[str]:
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        return [f"缺少 manifest：{manifest_path}"]
    try:
        manifest: Any = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"manifest JSON 非法：{manifest_path}（{exc.msg}）"]
    if not isinstance(manifest, dict):
        return [f"manifest 必须是对象：{manifest_path}"]
    required = {
        "corpus_version",
        "release_batch",
        "corpus_hash",
        "atom_count",
        "atom_schema_version",
        "public_corpora",
    }
    errors = [
        f"manifest 缺字段：{name}" for name in sorted(required.difference(manifest))
    ]
    corpora = manifest.get("public_corpora")
    if not isinstance(corpora, list) or not corpora:
        return errors + ["manifest.public_corpora 必须是非空数组"]
    total = 0
    hashes: list[str] = []
    for entry in corpora:
        if not isinstance(entry, dict):
            errors.append("manifest.public_corpora 每项必须是对象")
            continue
        relative = entry.get("path")
        if not isinstance(relative, str) or not relative.endswith(".approved.jsonl"):
            errors.append(f"public corpus 只能指向 approved JSONL：{relative!r}")
            continue
        corpus_path = root / relative
        if not corpus_path.is_file():
            errors.append(f"public corpus 不存在：{corpus_path}")
            continue
        try:
            count, versions = _jsonl_summary(corpus_path)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        digest = _sha256(corpus_path)
        total += count
        hashes.append(digest)
        expected = {
            "corpus_version": manifest.get("corpus_version"),
            "release_batch": manifest.get("release_batch"),
            "sha256": digest,
            "atom_count": count,
            "schema_version": manifest.get("atom_schema_version"),
        }
        for key, value in expected.items():
            if entry.get(key) != value:
                errors.append(
                    f"{relative}: manifest {key}={entry.get(key)!r}，应为 {value!r}"
                )
        if versions != {str(manifest.get("atom_schema_version"))}:
            errors.append(f"{relative}: Schema 版本混用：{sorted(versions)}")
    if len(hashes) == 1 and manifest.get("corpus_hash") != hashes[0]:
        errors.append("manifest.corpus_hash 与 approved 文件 SHA-256 不一致")
    if manifest.get("atom_count") != total:
        errors.append(f"manifest.atom_count={manifest.get('atom_count')!r}，应为 {total}")
    return errors


def _file_map(root: Path) -> dict[Path, bytes]:
    if not root.is_dir():
        return {}
    return {
        path.relative_to(root): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and not path.name.startswith(".")
    }


def expected_files() -> dict[Path, bytes]:
    files = {Path("manifest.json"): (SOURCE_ROOT / "manifest.json").read_bytes()}
    for directory in PUBLIC_DIRS:
        source = SOURCE_ROOT / directory
        if not source.is_dir():
            raise ValueError(f"公开知识目录缺失：{source}")
        for path in source.rglob("*"):
            if path.is_file() and not path.name.startswith("."):
                if directory == "05-community" and path.name in COMMUNITY_UNSHIPPED:
                    continue
                files[path.relative_to(SOURCE_ROOT)] = path.read_bytes()
    if any("03-majia-sop" in path.parts for path in files):
        raise ValueError("私有护城河目录不得进入公开知识生成物")
    return files


def expected_bundle_files(expected: dict[Path, bytes]) -> dict[Path, bytes]:
    """Apply the bundle's intentional Markdown path rewrites.

    Manifest and approved JSONL remain byte-identical across all three forms;
    Markdown links are rewritten only in SkillHub so they resolve inside the
    standalone package.
    """
    bundled: dict[Path, bytes] = {}
    for path, payload in expected.items():
        if path.suffix != ".md":
            bundled[path] = payload
            continue
        text = payload.decode("utf-8")
        text = text.replace("../../../../knowledge/", "../_knowledge/")
        text = text.replace(
            "../../siyu-core/skills/majia-siyu/references/",
            "../../references/",
        )
        text = text.replace(
            "references/route-contract.json",
            "modules/_runtime/route-contract.json",
        )
        text = _BARE_KNOWLEDGE_RE.sub(r"modules/_knowledge/\1", text)
        bundled[path] = text.encode("utf-8")
    return bundled


def _compare(root: Path, expected: dict[Path, bytes], label: str) -> list[str]:
    actual = _file_map(root)
    errors: list[str] = []
    for path in sorted(expected.keys() - actual.keys()):
        errors.append(f"{label} 缺少：{path}")
    for path in sorted(actual.keys() - expected.keys()):
        errors.append(f"{label} 多出：{path}")
    for path in sorted(expected.keys() & actual.keys()):
        if expected[path] != actual[path]:
            errors.append(f"{label} 已漂移：{path}")
    return errors


def sync(expected: dict[Path, bytes]) -> None:
    if PACKAGE_ROOT.exists():
        shutil.rmtree(PACKAGE_ROOT)
    for relative, payload in expected.items():
        target = PACKAGE_ROOT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="只检查生成物，不写文件")
    args = parser.parse_args()
    errors = validate_manifest(SOURCE_ROOT)
    try:
        expected = expected_files()
    except ValueError as exc:
        errors.append(str(exc))
        expected = {}
    if args.check:
        if expected:
            errors.extend(_compare(PACKAGE_ROOT, expected, "wheel package data"))
            if BUNDLE_ROOT.is_dir():
                errors.extend(
                    _compare(
                        BUNDLE_ROOT,
                        expected_bundle_files(expected),
                        "SkillHub knowledge",
                    )
                )
        if errors:
            for error in errors:
                print(f"- {error}")
            return 1
        print("公开知识三端生成物与 manifest 一致")
        return 0
    if errors:
        for error in errors:
            print(f"- {error}")
        return 1
    sync(expected)
    print(f"已同步 {len(expected)} 个公开知识文件到 {PACKAGE_ROOT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
