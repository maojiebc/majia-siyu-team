#!/usr/bin/env python3
"""Build one self-contained `majia-siyu` registry package from all public modules.

The repository keeps modular Skills for plugin-capable hosts. SkillHub receives
one generated package: the router at the root plus every capability under
`modules/`. Generated output is committed under `skillhub/majia-siyu/` so
GitHub, ClawHub, and SkillHub can publish the exact same commit artifact.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROUTER = ROOT / "plugins/siyu-core/skills/majia-siyu"
DEFAULT_OUTPUT = ROOT / "skillhub/majia-siyu"
RASTER = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico"}


def skill_dirs() -> list[Path]:
    found = sorted({path.parent for path in (ROOT / "plugins").glob("**/skills/*/SKILL.md")})
    if ROUTER not in found:
        raise RuntimeError("找不到 siyu 主入口")
    return found


def metadata_version(skill_md: Path) -> str:
    text = skill_md.read_text(encoding="utf-8")
    match = re.search(r"^\s+version:\s*[\"']?([^\"'\n]+)", text, re.MULTILINE)
    if not match:
        raise RuntimeError("siyu SKILL.md 缺少 metadata.version")
    return match.group(1).strip()


def add_bundle_rules(skill_md: Path) -> None:
    text = skill_md.read_text(encoding="utf-8")
    marker = "# 私域专家团 · 马甲实战版\n"
    bundle_rule = """

## 单入口内置模块执行规则

当前包是完整单入口版。路由到某个能力时，不要求用户另外安装 Skill，也不输出“请先安装”：

1. 读取 `modules/index.json` 找到能力目录。
2. 完整读取对应 `modules/<slug>/SKILL.md`。
3. 按该模块的全部步骤直接执行；模块内相对路径以模块目录为基准。
4. 全盘深度诊断读取 `modules/_expert-team/siyu-onboard.md`，需要专家视角时再读取同目录的 agent 文件。

`/siyu` 是唯一需要用户记住的入口；`modules/` 只供内部路由，不作为独立商店条目。
"""
    if bundle_rule.strip() not in text:
        text = text.replace(marker, marker + bundle_rule, 1)
    skill_md.write_text(text, encoding="utf-8")


def copy_modules(output: Path, modules: list[Path]) -> dict[str, str]:
    index: dict[str, str] = {}
    module_root = output / "modules"
    module_root.mkdir(parents=True)
    for source in modules:
        if source == ROUTER:
            continue
        slug = source.name
        target = module_root / slug
        shutil.copytree(source, target)
        index[slug] = f"modules/{slug}/SKILL.md"

    expert = module_root / "_expert-team"
    expert.mkdir()
    shutil.copy2(
        ROOT / "plugins/_orchestrator/commands/siyu-onboard.md",
        expert / "siyu-onboard.md",
    )
    for agent in sorted((ROOT / "plugins").glob("*/agents/*.md")):
        shutil.copy2(agent, expert / agent.name)
    index["siyu-onboard"] = "modules/_expert-team/siyu-onboard.md"
    (module_root / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return index


def sanitize(output: Path) -> list[str]:
    removed: list[str] = []
    for path in list(output.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(output)
        if path.name.startswith(".") or path.suffix.lower() in RASTER:
            removed.append(str(rel))
            path.unlink()
    return removed


def build(output: Path) -> dict[str, object]:
    modules = skill_dirs()
    version = metadata_version(ROUTER / "SKILL.md")
    if output.exists():
        shutil.rmtree(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROUTER, output)
    index = copy_modules(output, modules)
    add_bundle_rules(output / "SKILL.md")
    license_file = ROOT / "LICENSE"
    if license_file.exists():
        shutil.copy2(license_file, output / "LICENSE.md")
    removed = sanitize(output)
    files = [path for path in output.rglob("*") if path.is_file()]
    total = sum(path.stat().st_size for path in files)
    if len(files) > 200:
        raise RuntimeError(f"文件数 {len(files)} 超过 SkillHub 上限 200")
    if total > 10 * 1024 * 1024:
        raise RuntimeError(f"包大小 {total} 超过 SkillHub 上限 10 MB")
    return {
        "output": str(output),
        "slug": "majia-siyu",
        "version": version,
        "moduleCount": len(index),
        "fileCount": len(files),
        "bytes": total,
        "removed": removed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="构建单入口 majia-siyu 发布包")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = build(args.output.expanduser().resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
