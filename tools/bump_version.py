#!/usr/bin/env python3
"""Bump SemVer across every tracked file that declares the current VERSION."""
from __future__ import annotations

import argparse
from datetime import date
import os
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(os.environ.get("SIYU_RELEASE_ROOT", Path(__file__).resolve().parents[1])).resolve()
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
SKIP_DIR_NAMES = {
    ".venv",
    "dist",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    ".git",
}
CHANGELOG_HEADER = "# Changelog\n"
CHANGELOG_STUB_BODY = "### 变更\n- （待填写）\n"


def _version_pattern(old: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![0-9]){re.escape(old)}(?![0-9])")


def _read_version(root: Path) -> str:
    text = (root / "VERSION").read_text(encoding="utf-8").strip()
    if SEMVER_RE.fullmatch(text) is None:
        raise SystemExit(f"VERSION 不是 x.y.z 语义版本：{text!r}")
    return text


def _git_grep_files(root: Path, version: str) -> list[Path]:
    result = subprocess.run(
        ["git", "grep", "-l", version],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode not in (0, 1):
        raise SystemExit(f"git grep 失败：{result.stderr.strip()}")
    paths: list[Path] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        rel = Path(line.strip())
        if any(part in SKIP_DIR_NAMES for part in rel.parts):
            continue
        paths.append(rel)
    return sorted(set(paths))


def _is_probably_binary(path: Path) -> bool:
    try:
        sample = path.read_bytes()[:8192]
    except OSError:
        return True
    if b"\0" in sample:
        return True
    try:
        sample.decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False


def _unstaged_changes(root: Path, files: list[Path]) -> list[Path]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "--", *[str(f) for f in files]],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"git diff 失败：{result.stderr.strip()}")
    dirty = [Path(line.strip()) for line in result.stdout.splitlines() if line.strip()]
    return sorted(dirty)


def _ensure_changelog_stub(
    root: Path,
    new_version: str,
    *,
    dry_run: bool,
) -> tuple[Path, int]:
    rel = Path("CHANGELOG.md")
    path = root / rel
    text = path.read_text(encoding="utf-8")
    heading = f"## [{new_version}]"
    if heading in text:
        return rel, 0
    today = date.today().isoformat()
    stub = f"{heading} - {today}\n{CHANGELOG_STUB_BODY}\n"
    if text.startswith(CHANGELOG_HEADER):
        updated = CHANGELOG_HEADER + "\n" + stub + text[len(CHANGELOG_HEADER) + 1 :]
    else:
        updated = stub + text
    if not dry_run:
        path.write_text(updated, encoding="utf-8")
    return rel, 1


def bump(
    root: Path,
    new_version: str,
    *,
    dry_run: bool = False,
    force: bool = False,
) -> int:
    if SEMVER_RE.fullmatch(new_version) is None:
        print(f"目标版本不是 x.y.z：{new_version!r}", file=sys.stderr)
        return 1

    old_version = _read_version(root)
    if old_version == new_version:
        print(f"VERSION 已是 {new_version}，无需 bump。")
        return 0

    pattern = _version_pattern(old_version)
    candidates = _git_grep_files(root, old_version)
    if not candidates:
        print(f"git grep 未找到包含 {old_version!r} 的 tracked 文件。", file=sys.stderr)
        return 1

    touchable: list[Path] = []
    skipped_binary: list[Path] = []
    for rel in candidates:
        path = root / rel
        if not path.is_file():
            continue
        if _is_probably_binary(path):
            skipped_binary.append(rel)
            continue
        touchable.append(rel)

    dirty = _unstaged_changes(root, touchable)
    if dirty and not force:
        print("以下文件有未暂存改动，拒绝 bump（可用 --force 覆盖）：", file=sys.stderr)
        for rel in dirty:
            print(f"  - {rel}", file=sys.stderr)
        return 1

    total_replacements = 0
    files_changed = 0
    mode = "dry-run" if dry_run else "write"

    for rel in touchable:
        path = root / rel
        original = path.read_text(encoding="utf-8")
        count = len(pattern.findall(original))
        if count == 0:
            continue
        updated = pattern.sub(new_version, original)
        files_changed += 1
        total_replacements += count
        print(f"{rel}: {count} replacement(s) [{mode}]")
        if not dry_run:
            path.write_text(updated, encoding="utf-8")

    changelog_rel, changelog_added = _ensure_changelog_stub(
        root, new_version, dry_run=dry_run
    )
    if changelog_added:
        files_changed += 1
        total_replacements += changelog_added
        print(f"{changelog_rel}: added stub section [{mode}]")

    if skipped_binary:
        print(f"跳过 {len(skipped_binary)} 个疑似二进制文件。", file=sys.stderr)
        for rel in skipped_binary:
            print(f"  - {rel}", file=sys.stderr)

    print(
        f"\n{'Would bump' if dry_run else 'Bumped'} {old_version} → {new_version}: "
        f"{files_changed} file(s), {total_replacements} change(s)."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bump SemVer across tracked release surfaces.")
    parser.add_argument("new_version", help="Target x.y.z version")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned replacements without writing files",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow bump when target files have unstaged changes",
    )
    args = parser.parse_args(argv)
    return bump(ROOT, args.new_version, dry_run=args.dry_run, force=args.force)


if __name__ == "__main__":
    raise SystemExit(main())
