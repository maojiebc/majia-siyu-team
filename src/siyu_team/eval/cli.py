"""siyu-eval：质量门 CLI。方案分 <阈值 或 命中 COMPLIANCE_RED → exit 1。
3档：static-only 可跑（合规红线 + 反模式惩罚）。4档：接 judge/monte_carlo 出完整分。
"""
from __future__ import annotations

import argparse
import os
import re
import sys

from . import static as static_mod
from .engine import badge


def cmd_score(args) -> int:
    if not os.path.exists(args.file):
        print("找不到文件:", args.file)
        return 2
    text = open(args.file, encoding="utf-8").read()
    st = static_mod.scan(text)
    print("== 静态层 ==")
    print("flags:", st["flags"] or "无")
    print("反模式惩罚系数:", st["penalty"])
    if st["hard_fail"]:
        print("❌ COMPLIANCE_RED：命中合规红线，方案不得交付。")
        return 1
    # 3档：判官/蒙卡未接，给出 static-only 提示分（仅惩罚维度可见）
    print("（judge/蒙卡层为 4 档功能，当前 static-only。完整打分见 docs/blueprint.md §3d）")
    # 用惩罚系数粗估一个下限分，纯提示
    approx = round(st["penalty"] * 100, 1)
    print("static-only 上限提示分:", approx, "|", badge(approx))
    if approx < args.threshold:
        print("低于阈值 %d，打回。" % args.threshold)
        return 1
    return 0


def cmd_validate(args) -> int:
    """校验 SKILL.md 的 frontmatter、目录名和 8KB 体积上限。"""
    root = args.path
    problems = 0
    for dirpath, _, files in os.walk(root):
        for fn in files:
            if fn != "SKILL.md":
                continue
            p = os.path.join(dirpath, fn)
            raw = open(p, "rb").read()
            text = raw.decode("utf-8")
            match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
            if not match:
                print("⚠️ 缺 frontmatter:", p)
                problems += 1
                continue
            name_match = re.search(r"^name:\s*([^\n]+)$", match.group(1), re.MULTILINE)
            if not name_match:
                print("⚠️ 缺 frontmatter name:", p)
                problems += 1
            else:
                name = name_match.group(1).strip().strip("'\"")
                dirname = os.path.basename(dirpath)
                if name != dirname:
                    print(f"⚠️ name 与目录名不一致: {p} ({name!r} != {dirname!r})")
                    problems += 1
            if len(raw) > 8 * 1024:
                print(f"⚠️ 超过 8KB: {p} ({len(raw)} bytes)")
                problems += 1
    print("校验完成，问题数:", problems)
    return 1 if problems else 0


def main() -> None:
    ap = argparse.ArgumentParser(prog="siyu-eval", description="私域专家团质量门")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("score")
    s.add_argument("file")
    s.add_argument("--threshold", type=int, default=80)
    s.set_defaults(func=cmd_score)
    v = sub.add_parser("validate")
    v.add_argument("path", nargs="?", default="plugins/")
    v.set_defaults(func=cmd_validate)
    args = ap.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
