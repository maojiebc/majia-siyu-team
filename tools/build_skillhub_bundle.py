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

# 随包分发的公开知识子集；03-majia-sop 是护城河，永不进包。
KNOWLEDGE_PUBLIC_DIRS = (
    "00-methodology",
    "01-wechat-official",
    "02-industry",
    "04-atoms",
)
# 随包分发的原子工具（零依赖可跑；atoms_validate 分发态自动降级 v1-only）。
BUNDLED_TOOLS = ("atoms_query.py", "atoms_validate.py")
# 包内路径重写：SKILL.md 里的仓库根相对引用改指包内 _knowledge，
# 否则独立安装态全是死指针。顺序敏感：先收相对逃逸，再收裸路径；
# 裸路径用负向后顾防止把已改写的 `_knowledge/...` 再匹配一次。
RELATIVE_ESCAPE = ("../../../../knowledge/", "../_knowledge/")
BARE_KNOWLEDGE_RE = re.compile(
    r"(?<![\w/])knowledge/(00-methodology|01-wechat-official|02-industry|04-atoms)"
)


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


def copy_knowledge(output: Path) -> int:
    """公开知识层随包走：modules/_knowledge/{00,01,02,04}+manifest。

    resolver（knowledge/paths.py）已给这个槽位留了发现优先级；
    03-majia-sop 显式排除——本机构建时该目录含真实 SOP。
    """
    target = output / "modules" / "_knowledge"
    target.mkdir(parents=True, exist_ok=True)
    copied = 0
    for name in KNOWLEDGE_PUBLIC_DIRS:
        source = ROOT / "knowledge" / name
        if not source.is_dir():
            raise RuntimeError(f"公开知识目录缺失：{source}")
        shutil.copytree(source, target / name)
        copied += sum(1 for path in (target / name).rglob("*") if path.is_file())
    manifest = ROOT / "knowledge" / "manifest.json"
    if manifest.exists():
        shutil.copy2(manifest, target / "manifest.json")
        copied += 1
    forbidden = target / "03-majia-sop"
    if forbidden.exists():
        raise RuntimeError("护城河目录被拷进 bundle，立即中止")
    return copied


def copy_tools(output: Path) -> int:
    """SKILL.md 引用的原子工具随包走，独立安装态命令不再是死指针。"""
    target = output / "tools"
    target.mkdir(parents=True, exist_ok=True)
    for name in BUNDLED_TOOLS:
        shutil.copy2(ROOT / "tools" / name, target / name)
    return len(BUNDLED_TOOLS)


def rewrite_knowledge_paths(output: Path) -> int:
    """把 bundle 副本 markdown 里的仓库根路径改写成包内路径（源文件不动）。"""
    rewritten = 0
    for path in output.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        updated = text.replace(*RELATIVE_ESCAPE)
        updated = BARE_KNOWLEDGE_RE.sub(r"modules/_knowledge/\1", updated)
        if updated != text:
            path.write_text(updated, encoding="utf-8")
            rewritten += 1
    return rewritten


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
    knowledge_files = copy_knowledge(output)
    tool_files = copy_tools(output)
    rewritten = rewrite_knowledge_paths(output)
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
        "knowledgeFiles": knowledge_files,
        "bundledTools": tool_files,
        "pathRewrites": rewritten,
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
