#!/usr/bin/env python3
"""把一轮盲评包（和可选的案例）做成一个离线 HTML 审阅页，给真人逐题打分。

用法:
    python3 tools/review_page/build.py --run evals/runs/2026-10-21-r3 \
        --arms "分别来自：不装技能、v1.8.1、加了案例的新版。" --out 审阅台.html [--cases]

页面只读盲评包里的匿名 A/B/C，不读解盲键。导出的 JSON 里 blind_review 一段可以直接存成
<run>/human/blind-review.json，再用 tools/ab_eval.py tally --review 统计。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
FLAGS_FILE = HERE / "case_flags.json"


def embed(value: object) -> str:
    return json.dumps(value, ensure_ascii=False).replace("<", "\\u003c")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", required=True, help="含 blind-packet.json 的评测目录")
    parser.add_argument("--arms", required=True, help="告诉评审三份回答来自哪些版本（不说哪份是哪个）")
    parser.add_argument("--out", required=True)
    parser.add_argument("--cases", action="store_true", help="同时审 knowledge/cases/ 里的案例")
    args = parser.parse_args()

    run = Path(args.run)
    packet = json.loads((run / "blind-packet.json").read_text(encoding="utf-8"))
    for q in packet:
        if set(q) != {"id", "request", "evidence", "answers"}:
            raise SystemExit(f"❌ {q.get('id')} 字段不对，可能混进了解盲信息")

    cases, flags = [], {}
    if args.cases:
        for path in sorted((ROOT / "knowledge/cases").glob("*.md")):
            text = path.read_text(encoding="utf-8")
            number, _, name = path.stem.partition("-")
            cases.append({"file": path.name, "title": text.splitlines()[0].lstrip("# ").strip(),
                          "short": f"{number} {name}", "md": text})
        if FLAGS_FILE.is_file():
            flags = json.loads(FLAGS_FILE.read_text(encoding="utf-8"))

    html = (HERE / "template.html").read_text(encoding="utf-8")
    html = (html.replace("__BLIND__", embed(packet))
                .replace("__CASES__", embed(cases))
                .replace("__FLAGS__", embed(flags))
                .replace("__ARMS_NOTE__", "每题几份回答 A / B / C，顺序打乱了，" + args.arms)
                .replace("__RUN__", run.name))
    out = Path(args.out)
    out.write_text(html, encoding="utf-8")
    print(f"✅ {out}（{len(packet)} 题，{len(cases)} 篇案例）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
