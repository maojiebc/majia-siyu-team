#!/usr/bin/env python3
"""校验所有发布面都声明与 ``VERSION`` 相同的 SemVer。"""
from __future__ import annotations

from collections.abc import Iterable
import json
import os
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(
    os.environ.get("SIYU_RELEASE_ROOT", Path(__file__).resolve().parents[1])
).resolve()
SEMVER_RE = re.compile(r"\d+\.\d+\.\d+")
SKILL_VERSION_RE = re.compile(
    r"^\s+version:\s*[\"']?([^\"'\n]+)[\"']?\s*$",
    re.MULTILINE,
)
BADGE_RE = re.compile(
    r"img\.shields\.io/badge/(?:skill-)?v?([0-9.]+)-[A-Fa-f0-9]+\.svg"
)
KNOWLEDGE_MANIFESTS = (
    Path("knowledge/manifest.json"),
    Path("src/siyu_team/knowledge/data/manifest.json"),
    Path("skillhub/majia-siyu/modules/_knowledge/manifest.json"),
)


def _read_text(root: Path, rel: Path, errors: list[str]) -> str | None:
    path = root / rel
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"{rel}: 无法读取（{exc}）")
        return None


def _read_json(root: Path, rel: Path, errors: list[str]) -> dict[str, Any] | None:
    text = _read_text(root, rel, errors)
    if text is None:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        errors.append(f"{rel}: JSON 无效（{exc}）")
        return None
    if not isinstance(payload, dict):
        errors.append(f"{rel}: 顶层必须是对象")
        return None
    return payload


def _check_value(label: str, found: object, version: str, errors: list[str]) -> None:
    if found != version:
        errors.append(f"{label} 为 {found!r}，与 VERSION {version!r} 不一致")


def _check_marketplace(
    root: Path,
    rel: Path,
    version: str,
    errors: list[str],
) -> int:
    payload = _read_json(root, rel, errors)
    if payload is None:
        return 0
    metadata = payload.get("metadata")
    metadata_version = metadata.get("version") if isinstance(metadata, dict) else None
    _check_value(f"{rel} metadata.version", metadata_version, version, errors)

    plugins = payload.get("plugins")
    if not isinstance(plugins, list) or not plugins:
        errors.append(f"{rel}: plugins 必须是非空数组")
        return 0
    for index, plugin in enumerate(plugins):
        if not isinstance(plugin, dict):
            errors.append(f"{rel} plugins[{index}]: 必须是对象")
            continue
        name = plugin.get("name", f"plugins[{index}]")
        _check_value(f"{rel} 插件 {name}.version", plugin.get("version"), version, errors)
    return len(plugins)


def _check_json_versions(
    root: Path,
    paths: Iterable[Path],
    version: str,
    errors: list[str],
) -> int:
    count = 0
    for rel in paths:
        payload = _read_json(root, rel, errors)
        if payload is None:
            continue
        _check_value(f"{rel} version", payload.get("version"), version, errors)
        count += 1
    return count


def _check_skill_versions(
    root: Path,
    base: Path,
    version: str,
    errors: list[str],
) -> int:
    absolute = root / base
    paths = sorted(absolute.rglob("SKILL.md")) if absolute.is_dir() else []
    if not paths:
        errors.append(f"{base}: 没有找到 SKILL.md")
        return 0
    for path in paths:
        rel = path.relative_to(root)
        text = _read_text(root, rel, errors)
        if text is None:
            continue
        lines = text.splitlines()
        if not lines or lines[0].strip() != "---":
            errors.append(f"{rel}: 缺少 frontmatter 起始分隔线")
            continue
        try:
            end = next(
                index for index, line in enumerate(lines[1:], 1) if line.strip() == "---"
            )
        except StopIteration:
            errors.append(f"{rel}: 缺少 frontmatter 结束分隔线")
            continue
        frontmatter = "\n".join(lines[1:end])
        match = SKILL_VERSION_RE.search(frontmatter)
        if match is None:
            errors.append(f"{rel}: frontmatter 缺少 metadata.version")
            continue
        _check_value(f"{rel} metadata.version", match.group(1).strip(), version, errors)
    return len(paths)


def _check_python_version_files(
    root: Path,
    version: str,
    errors: list[str],
) -> None:
    checks = (
        (
            Path("src/siyu_team/__init__.py"),
            re.compile(r'__version__\s*=\s*"([^"]+)"'),
            "__version__",
        ),
        (
            Path("pyproject.toml"),
            re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE),
            "project.version",
        ),
    )
    for rel, pattern, label in checks:
        text = _read_text(root, rel, errors)
        if text is None:
            continue
        match = pattern.search(text)
        if match is None:
            errors.append(f"{rel}: 未找到 {label}")
            continue
        _check_value(f"{rel} {label}", match.group(1), version, errors)


def _check_readmes(root: Path, version: str, errors: list[str]) -> None:
    for rel in (
        Path("README.md"),
        Path("README.en.md"),
        Path("plugins/siyu-core/skills/majia-siyu/README.md"),
        Path("skillhub/majia-siyu/README.md"),
    ):
        text = _read_text(root, rel, errors)
        if text is None:
            continue
        badge = BADGE_RE.search(text)
        if badge is None:
            errors.append(f"{rel}: 未找到版本徽章")
        else:
            _check_value(f"{rel} 徽章版本", badge.group(1), version, errors)
        if f"- **v{version}**" not in text:
            errors.append(f"{rel}: 版本记录缺少 v{version}")


def _check_release_documents(root: Path, version: str, errors: list[str]) -> None:
    changelog = _read_text(root, Path("CHANGELOG.md"), errors)
    if changelog is not None:
        heading = re.search(r"^## \[([0-9.]+)\]", changelog, re.MULTILINE)
        if heading is None:
            errors.append("CHANGELOG.md: 未找到发布版本标题")
        else:
            _check_value("CHANGELOG.md 最新发布版本", heading.group(1), version, errors)

    framework = _read_text(root, Path("docs/framework.svg"), errors)
    if framework is not None and framework.count(f"v{version}") < 2:
        errors.append("docs/framework.svg: 标题与版本芯片未同时更新")


def _check_knowledge_manifests(root: Path, version: str, errors: list[str]) -> None:
    expected_batch_marker = f"v{version}"
    batch_pattern = re.compile(
        rf"(?:^|[^0-9]){re.escape(expected_batch_marker)}(?:$|[^0-9])"
    )
    for rel in KNOWLEDGE_MANIFESTS:
        payload = _read_json(root, rel, errors)
        if payload is None:
            continue
        batches: list[tuple[str, object]] = []

        def collect(value: object, location: str) -> None:
            if isinstance(value, dict):
                for key, child in value.items():
                    child_location = f"{location}.{key}" if location else str(key)
                    if key == "release_batch":
                        batches.append((child_location, child))
                    collect(child, child_location)
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    collect(child, f"{location}[{index}]")

        collect(payload, "")
        if not batches:
            errors.append(f"{rel}: 缺少 release_batch")
        for location, release_batch in batches:
            if (
                not isinstance(release_batch, str)
                or batch_pattern.search(release_batch) is None
            ):
                errors.append(
                    f"{rel} {location} {release_batch!r} "
                    f"未标记 {expected_batch_marker}"
                )


def check(root: Path = ROOT) -> tuple[str, int, int, list[str]]:
    """返回版本、安装单元数、Skill 数与所有漂移错误。"""
    errors: list[str] = []
    version_text = _read_text(root, Path("VERSION"), errors)
    version = version_text.strip() if version_text is not None else ""
    if SEMVER_RE.fullmatch(version) is None:
        errors.append(f"VERSION 不是 x.y.z 语义版本：{version!r}")

    install_units = _check_marketplace(
        root, Path(".claude-plugin/marketplace.json"), version, errors
    )
    _check_marketplace(root, Path(".codebuddy-plugin/marketplace.json"), version, errors)

    plugin_root = root / "plugins"
    component_paths = (
        [
            (path / ".claude-plugin/plugin.json").relative_to(root)
            for path in sorted(plugin_root.iterdir())
            if path.is_dir()
        ]
        if plugin_root.is_dir()
        else []
    )
    if not component_paths:
        errors.append("plugins: 没有找到组件 plugin.json")
    _check_json_versions(root, component_paths, version, errors)
    _check_json_versions(
        root, (Path(".codebuddy-plugin/plugin.json"),), version, errors
    )

    skill_count = _check_skill_versions(root, Path("plugins"), version, errors)
    skill_count += _check_skill_versions(
        root, Path("skillhub/majia-siyu"), version, errors
    )
    _check_python_version_files(root, version, errors)
    _check_readmes(root, version, errors)
    _check_release_documents(root, version, errors)
    _check_knowledge_manifests(root, version, errors)
    return version, install_units, skill_count, errors


def main() -> int:
    version, install_units, skill_count, errors = check()
    if errors:
        print("版本校验失败：", file=sys.stderr)
        for error in errors:
            print("-", error, file=sys.stderr)
        return 1
    print(
        f"版本校验通过：{version}（{install_units} 个安装单元，"
        f"{skill_count} 份源码/分发 Skill）"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
