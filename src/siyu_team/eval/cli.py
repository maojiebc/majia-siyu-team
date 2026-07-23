"""siyu-eval：质量门 CLI。当前 static-only：命中 COMPLIANCE_RED 或软性反模式过多 → exit 1。
judge/monte_carlo 为 4 档规划，未实装，故本命令不产出质量分。
"""
from __future__ import annotations

import argparse
import os
import re
import sys

from . import static as static_mod


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
    # judge/蒙卡未实装，静态层不产出质量分，只做合规红线 + 反模式惩罚。
    print("（judge/蒙卡层未实装；当前仅静态合规检查，不产出质量分。设计见 docs/blueprint.md §3d）")
    # penalty 越低表示软性反模式越多；这不是质量分，仅用来把明显粗糙的稿子挡在阈值外。
    penalty_pct = round(st["penalty"] * 100, 1)
    print("反模式惩罚系数（非质量分，越低越粗糙）:", penalty_pct)
    if penalty_pct < args.threshold:
        print("软性反模式过多（%s < %d），建议打回精修。" % (penalty_pct, args.threshold))
        return 1
    print("✅ 未命中合规红线；方案质量高低需人工或 4 档 judge 评定，本命令不代表已过质量门。")
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
