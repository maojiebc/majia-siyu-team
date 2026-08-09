#!/usr/bin/env python3
"""Fail when a repository Markdown link points at a missing local path."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
from typing import Iterable
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
LINK_RE = re.compile(r"!?\[[^\]\n]*\]\(([^)\n]+)\)")
REFERENCE_RE = re.compile(r"^\s*\[[^\]]+\]:\s*(\S+)")
HTML_LINK_RE = re.compile(
    r"<(?:a|img)\b[^>]*\b(?:href|src)=[\"']([^\"']+)[\"']",
    re.IGNORECASE,
)
SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
SKIP_PARTS = {
    ".git",
    ".venv",
    "__pycache__",
    "_benchmark-src",
    "build",
    "dist",
}


@dataclass(frozen=True)
class LinkIssue:
    source: Path
    line: int
    target: str
    reason: str

    def describe(self, root: Path) -> str:
        try:
            source = self.source.relative_to(root)
        except ValueError:
            source = self.source
        return f"{source}:{self.line}: {self.target}（{self.reason}）"


def _destination(raw: str) -> str:
    value = raw.strip()
    if value.startswith("<") and ">" in value:
        return value[1 : value.index(">")].strip()
    # Markdown 可在目标后放可选 title；仓库内含空格的路径必须用 <...> 或 %20。
    return value.split(maxsplit=1)[0] if value else ""


def _is_external_or_anchor(target: str) -> bool:
    return (
        not target
        or target.startswith(("#", "/", "//"))
        or bool(SCHEME_RE.match(target))
    )


def _tracked_markdown_files(root: Path) -> tuple[Path, ...] | None:
    if not (root / ".git").exists():
        return None
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "--", "*.md"],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return tuple(
        root / raw.decode("utf-8")
        for raw in result.stdout.split(b"\0")
        if raw
    )


def _markdown_files(paths: Iterable[Path]) -> Iterable[Path]:
    seen: set[Path] = set()
    for item in paths:
        item = item.resolve(strict=False)
        candidates = (item,) if item.is_file() else item.rglob("*.md")
        for path in candidates:
            if path.suffix.lower() != ".md" or any(
                part in SKIP_PARTS for part in path.parts
            ):
                continue
            resolved = path.resolve(strict=False)
            if resolved not in seen:
                seen.add(resolved)
                yield resolved


def _has_exact_case(path: Path, root: Path) -> bool:
    """Do not let a case-insensitive developer filesystem hide CI failures."""
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return False
    current = root
    for part in parts:
        if not current.is_dir() or part not in {item.name for item in current.iterdir()}:
            return False
        current /= part
    return True


def check_markdown_links(
    root: Path = ROOT,
    paths: Iterable[Path] | None = None,
) -> list[LinkIssue]:
    """Return missing/escaping local Markdown links under ``paths``."""
    root = root.resolve(strict=False)
    tracked = _tracked_markdown_files(root) if paths is None else None
    scan_paths = tracked if tracked is not None else (
        tuple(paths) if paths is not None else (root,)
    )
    issues: list[LinkIssue] = []
    for source in _markdown_files(scan_paths):
        in_fence = False
        for line_no, line in enumerate(
            source.read_text(encoding="utf-8").splitlines(), 1
        ):
            stripped = line.lstrip()
            if stripped.startswith(("```", "~~~")):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            raw_targets = [match.group(1) for match in LINK_RE.finditer(line)]
            raw_targets.extend(
                match.group(1) for match in HTML_LINK_RE.finditer(line)
            )
            reference = REFERENCE_RE.match(line)
            if reference:
                raw_targets.append(reference.group(1))
            for raw in raw_targets:
                target = _destination(raw)
                if _is_external_or_anchor(target):
                    continue
                local = unquote(target.split("#", 1)[0].split("?", 1)[0])
                if not local:
                    continue
                candidate = (source.parent / local).resolve(strict=False)
                try:
                    candidate.relative_to(root)
                except ValueError:
                    issues.append(
                        LinkIssue(source, line_no, target, "相对链接逃出分发根目录")
                    )
                    continue
                if not candidate.exists():
                    issues.append(LinkIssue(source, line_no, target, "目标不存在"))
                elif not _has_exact_case(candidate, root):
                    issues.append(
                        LinkIssue(source, line_no, target, "目标大小写与文件系统不一致")
                    )
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="检查 Markdown 本地链接")
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    root = args.root.expanduser().resolve(strict=False)
    paths = tuple(path.expanduser() for path in args.paths) or None
    issues = check_markdown_links(root, paths)
    if issues:
        print(f"Markdown 链接检查失败：{len(issues)} 个问题")
        for issue in issues:
            print(f"- {issue.describe(root)}")
        return 1
    print("Markdown 链接检查通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
