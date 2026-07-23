#!/usr/bin/env python3
"""巡检 footer、用户措辞、护城河占位与 SKILL.md 体积。"""
from __future__ import annotations

import os
from pathlib import Path
import sys


ROOT = Path(os.environ.get("SIYU_CONSISTENCY_ROOT", Path(__file__).resolve().parents[1])).resolve()
FOOTER = """---

## 不知道下一步用哪个 skill？

输入 `/siyu`。

这是私域工具箱的导航入口。它会读取刚才的具体结论，选择当前最值得处理的一个方向，
并直接路由到对应 skill。迷路了就回 `/siyu`。"""
FORBIDDEN = ("slug", "snapshot", "session")
TECHNICAL_CONTEXT = ("不说", "不用", "不要", "不外露", "内部", "措辞", "技术标识", "字段", "路径", "frontmatter")
TEXT_SUFFIXES = {".md", ".py", ".json", ".toml", ".mmd", ".yml", ".yaml"}


def skill_checks() -> list[str]:
    errors = []
    skill_files = sorted((ROOT / "plugins").rglob("SKILL.md"))
    if not skill_files:
        return ["没有找到任何 SKILL.md"]
    for path in skill_files:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        rel = path.relative_to(ROOT)
        if len(raw) > 8 * 1024:
            errors.append(f"{rel}: {len(raw)} bytes，超过 8KB")
        if not text.rstrip().endswith(FOOTER):
            errors.append(f"{rel}: 缺少或改动了统一 footer")
        for line_no, line in enumerate(text.splitlines(), 1):
            lowered = line.casefold()
            words = [word for word in FORBIDDEN if word in lowered]
            if words and not any(marker in line for marker in TECHNICAL_CONTEXT):
                errors.append(f"{rel}:{line_no}: 面向用户的文字出现内部术语 {words}")
    print(f"SKILL 巡检：{len(skill_files)} 个文件")
    return errors


def moat_markers() -> list[tuple[str, int]]:
    found = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        rel = path.relative_to(ROOT)
        if not rel.parts or rel.parts[0] not in {"plugins", "knowledge"}:
            continue
        if any(part in {".git", "dist", "_benchmark-src"} for part in rel.parts):
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_no, line in enumerate(lines, 1):
            if "【待马甲填真实SOP】" in line:
                found.append((str(rel), line_no))
    return found


def main() -> int:
    errors = skill_checks()
    markers = moat_markers()
    print(f"护城河待填标记：{len(markers)} 处")
    for path, line in markers:
        print(f"- {path}:{line}")
    if errors:
        print("一致性巡检失败：", file=sys.stderr)
        for error in errors:
            print("-", error, file=sys.stderr)
        return 1
    print("一致性巡检通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
