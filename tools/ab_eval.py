#!/usr/bin/env python3
"""装和不装的盲评：打乱、隐名、统计。

不调用模型。回答由宿主里互相独立的对话生成，评审由另一个看不到版本名的对话
（或真人）完成；本脚本只负责把答案打乱成匿名的 A/B/C，再按解盲键统计胜负。

用法:
    python3 tools/ab_eval.py blind --questions evals/questions.json \
        --answers bare=answers-bare.json v181=answers-v181.json --seed 20261020 \
        --out evals/runs/2026-10-20
    python3 tools/ab_eval.py tally --run evals/runs/2026-10-20 [--review 评审文件]

答案文件是 [{"id": 题目id, "answer": 回答}]。评审文件 blind-review.json 是
[{"id", "ratings": {"A": {"critical_errors", "usefulness", "reason"}}, "preferred": ["A"]}]。
一题里 X 胜 Y：严重错误更少；严重错误一样多时，有用程度分更高。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from itertools import combinations
from pathlib import Path

LABELS = "ABCDEFGH"


def _load(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit(f"❌ {path} 必须是 JSON 数组")
    return data


def _write(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def blind(args: argparse.Namespace) -> int:
    questions = _load(Path(args.questions))
    arms: dict[str, dict[str, str]] = {}
    for spec in args.answers:
        name, _, path = spec.partition("=")
        if not name or not path:
            raise SystemExit(f"❌ --answers 写成 名字=路径：{spec}")
        arms[name] = {item["id"]: item["answer"] for item in _load(Path(path))}
    if len(arms) > len(LABELS):
        raise SystemExit("❌ 版本太多")

    packet, key = [], {}
    for q in questions:
        missing = [name for name, answers in arms.items() if not answers.get(q["id"], "").strip()]
        if missing:
            raise SystemExit(f"❌ {q['id']} 缺少回答：{', '.join(missing)}")
        # 各版本独立作答，一字不差多半是答题时共用了临时文件，互相覆盖了。
        twins = [(a, b) for a, b in combinations(sorted(arms), 2) if arms[a][q["id"]] == arms[b][q["id"]]]
        if twins:
            raise SystemExit(f"❌ {q['id']} 有两组回答一字不差：{twins}，先查答题过程")
        order = sorted(arms)
        salt = hashlib.sha256(f"{args.seed}:{q['id']}".encode()).hexdigest()
        random.Random(salt).shuffle(order)
        labels = dict(zip(LABELS, order))
        key[q["id"]] = labels
        packet.append({
            "id": q["id"],
            "request": q["request"],
            "evidence": q.get("evidence", ""),
            "answers": {label: arms[arm][q["id"]] for label, arm in labels.items()},
        })

    out = Path(args.out)
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise SystemExit("❌ 输出目录必须是新目录或空目录，不能覆盖已有盲评记录")
    out.mkdir(parents=True, exist_ok=True)
    _write(out / "blind-packet.json", packet)
    _write(out / "blind-key.json", {"seed": args.seed, "key": key})
    for name, answers in arms.items():
        _write(out / f"answers-{name}.json", [{"id": q["id"], "answer": answers[q["id"]]} for q in questions])

    lines = ["# 盲评单", "", "每题几份回答顺序已打乱，看不出是哪个版本。按“有经验的私域负责人看了会不会照着做”打 1–5 分，记下严重错误（编造事实、超出证据下结论、会让门店吃亏的建议）。", ""]
    for item in packet:
        lines += [f"## {item['id']}", "", f"**用户问**：{item['request']}", "", f"**已知限制**：{item['evidence']}", ""]
        for label, answer in item["answers"].items():
            lines += [f"### 回答 {label}", "", answer, ""]
        lines += ["| 回答 | 严重错误数 | 有用程度 1–5 | 一句理由 |", "|---|---|---|---|"]
        lines += [f"| {label} |  |  |  |" for label in item["answers"]]
        lines += ["", "更想要哪份：", ""]
    (out / "blind-packet.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"✅ {len(packet)} 题，{len(arms)} 个版本 → {out}")
    return 0


def _rank(rating: dict) -> tuple[int, float]:
    return (-int(rating.get("critical_errors", 0)), float(rating.get("usefulness", 0)))


def tally(args: argparse.Namespace) -> int:
    run = Path(args.run)
    key = json.loads((run / "blind-key.json").read_text(encoding="utf-8"))["key"]
    review_path = Path(args.review) if args.review else run / "blind-review.json"
    reviews = {item["id"]: item for item in _load(review_path)}
    missing = sorted(set(key) - set(reviews))
    if missing:
        raise SystemExit(f"❌ 评审缺题：{', '.join(missing)}")

    arms = sorted({arm for labels in key.values() for arm in labels.values()})
    pair = {(x, y): [0, 0, 0] for x, y in combinations(arms, 2)}
    errors = {arm: 0 for arm in arms}
    scores: dict[str, list[float]] = {arm: [] for arm in arms}
    preferred = {arm: 0 for arm in arms}
    for qid, labels in key.items():
        review = reviews[qid]
        by_arm = {arm: review["ratings"][label] for label, arm in labels.items()}
        for arm, rating in by_arm.items():
            errors[arm] += int(rating.get("critical_errors", 0))
            scores[arm].append(float(rating.get("usefulness", 0)))
        for label in review.get("preferred", []):
            preferred[labels[label]] += 1
        for (x, y), counts in pair.items():
            rx, ry = _rank(by_arm[x]), _rank(by_arm[y])
            counts[0 if rx > ry else 2 if rx < ry else 1] += 1

    lines = [f"共 {len(key)} 题。", "", "| 版本 | 平均有用程度 | 严重错误合计 | 被评为最想要 |", "|---|---:|---:|---:|"]
    for arm in arms:
        avg = sum(scores[arm]) / len(scores[arm])
        lines.append(f"| {arm} | {avg:.2f} | {errors[arm]} | {preferred[arm]} |")
    lines += ["", "| 对比 | 前者胜 | 平 | 前者负 |", "|---|---:|---:|---:|"]
    for (x, y), (win, tie, loss) in pair.items():
        lines.append(f"| {x} vs {y} | {win} | {tie} | {loss} |")
    text = "\n".join(lines) + "\n"
    (review_path.parent / "results.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("blind", help="打乱并隐去版本名")
    b.add_argument("--questions", required=True)
    b.add_argument("--answers", nargs="+", required=True, metavar="名字=路径")
    b.add_argument("--seed", type=int, required=True)
    b.add_argument("--out", required=True)
    t = sub.add_parser("tally", help="按解盲键统计胜负")
    t.add_argument("--run", required=True)
    t.add_argument("--review", help="评审文件，默认 <run>/blind-review.json；结果写在它旁边")
    args = parser.parse_args(argv)
    return blind(args) if args.command == "blind" else tally(args)


if __name__ == "__main__":
    sys.exit(main())
