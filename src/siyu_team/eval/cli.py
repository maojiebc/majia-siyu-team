"""``siyu-eval`` command line interface.

The command surface separates two different gates:

* ``compliance`` scans deterministic rules and never emits a quality score;
* ``judge`` turns independently supplied rubric scores into a JudgeReport.

``score`` remains a deprecated compatibility alias for ``compliance`` during
the v1.4.2 transition.  It does not create a score or badge.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from . import static as static_mod
from .models import ScanMode


_COMPLIANCE_FLAGS = {
    "COMPLIANCE_RED",
    "ABSOLUTE_CLAIM",
    "INDUCE_SHARE",
    "PRIVACY_COLLECT",
    "ATTRIBUTED_CLAIM",
    "QUOTED_RISK_MENTION",
    "RISK_TERM_MENTION",
}


def _scan_payload(text: str, mode: ScanMode) -> dict[str, Any]:
    """Use the typed scanner with a short compatibility fallback."""

    scan_result = getattr(static_mod, "scan_result", None)
    if scan_result is not None:
        return scan_result(text, mode=mode).to_dict()

    # During a source/wheel rolling upgrade, keep the old scanner callable but
    # label its missing context fields explicitly instead of fabricating them.
    legacy = static_mod.scan(text)
    details: list[dict[str, Any]] = []
    for raw_detail in legacy.get("details", []):
        detail = dict(raw_detail)
        detail.setdefault("description", detail.get("desc", ""))
        detail.setdefault("offset", -1)
        detail.setdefault("end", -1)
        detail.setdefault("snippet", "")
        detail.setdefault("rule", detail.get("flag", "legacy"))
        detail.setdefault("mode", mode.value)
        detail.setdefault("soft", not bool(detail.get("hard")))
        details.append(detail)
    return {
        "flags": list(legacy.get("flags", [])),
        "details": details,
        "hard_fail": bool(legacy.get("hard_fail")),
        "mode": mode.value,
        "text_length": len(text),
    }


def _compliance_file(path: str, mode: ScanMode) -> tuple[int, dict[str, Any]]:
    if not os.path.exists(path):
        return 2, {"file": path, "error": "找不到文件", "passed": False}
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return 2, {"file": path, "error": f"读取失败：{exc}", "passed": False}
    result = _compliance_payload(text, mode)
    return (
        1 if result["hard_fail"] else 0,
        {
            "file": path,
            "mode": result["mode"],
            "passed": not result["hard_fail"],
            "hard_fail": result["hard_fail"],
            "flags": result["flags"],
            "hits": result["details"],
        },
    )


def _compliance_payload(text: str, mode: ScanMode) -> dict[str, Any]:
    """Keep compliance facts separate from roughness/quality heuristics."""

    result = _scan_payload(text, mode)
    details = [
        detail
        for detail in result["details"]
        if detail.get("flag") in _COMPLIANCE_FLAGS
    ]
    flags = list(dict.fromkeys(str(detail["flag"]) for detail in details))
    return {
        **result,
        "flags": flags,
        "details": details,
        "hard_fail": any(bool(detail.get("hard")) for detail in details),
    }


def _print_compliance_report(report: dict[str, Any]) -> None:
    path = report["file"]
    if report.get("error"):
        print(f"❌ {path}：{report['error']}")
        return
    print(f"== 静态合规检查：{path}（mode={report['mode']}） ==")
    hits = report["hits"]
    if not hits:
        print("规则命中：无")
    for hit in hits:
        level = "阻断" if hit["hard"] else "提示"
        location = (
            f"offset={hit['offset']}:{hit['end']}"
            if hit["offset"] >= 0
            else "document"
        )
        description = hit.get("description") or hit.get("desc", "")
        print(f"- [{level}] {hit['rule']} ({location})：{description}")
        if hit.get("snippet"):
            print(f"  snippet: {hit['snippet']}")
    if report["passed"]:
        print("✅ 静态合规检查通过。")
    else:
        print("❌ 命中硬性合规规则，方案不得交付。")


def cmd_compliance(args: argparse.Namespace) -> int:
    """Scan one or more files; output compliance facts only."""

    mode = ScanMode(getattr(args, "mode", ScanMode.CUSTOMER_COPY.value))
    reports: list[dict[str, Any]] = []
    worst = 0
    for path in args.files:
        code, report = _compliance_file(path, mode)
        worst = max(worst, code)
        reports.append(report)

    payload = {
        "schema_version": "1.0",
        "report_type": "compliance",
        "mode": mode.value,
        "passed": worst == 0,
        "files": reports,
    }
    if getattr(args, "json", False):
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for report in reports:
            _print_compliance_report(report)
        if len(reports) > 1:
            print(
                "整体结果（静态合规）：%s（%d 个文件）"
                % ("✅ 全部通过" if worst == 0 else "❌ 存在不通过", len(reports))
            )
        print("静态合规扫描结束。")
    return worst


def cmd_score(args: argparse.Namespace) -> int:
    """Deprecated compatibility alias for ``compliance``."""

    print("⚠️ `siyu-eval score` 已 deprecated；本次按静态合规检查执行。")
    if args.threshold != 80:
        print("⚠️ --threshold 仅为旧参数兼容，静态合规检查不会计算质量分。")
    return cmd_compliance(args)


def _emit_json(payload: Mapping[str, Any], output: str | None = None) -> bool:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if not output:
        print(rendered, end="")
        return True
    destination = Path(output)
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(rendered, encoding="utf-8")
    except OSError as exc:
        print("报告写入失败:", exc)
        return False
    print(f"已写入机器可读报告：{destination}")
    return True


def _load_review_config(path: str | None) -> Mapping[str, Any] | None:
    if path is None:
        return None
    with open(path, encoding="utf-8") as handle:
        config = json.load(handle)
    if not isinstance(config, Mapping):
        raise ValueError("Judge config 必须是 JSON 对象")
    return config


def cmd_judge(args: argparse.Namespace) -> int:
    """Build Judge prompts or compose an independent JudgeReport."""

    if not os.path.exists(args.file):
        print("找不到文件:", args.file)
        return 2
    try:
        text = Path(args.file).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        print("方案读取失败:", exc)
        return 2

    # Judge is downstream of the compliance gate.  Rechecking here is a safe
    # precondition, not a component of the quality score.
    compliance = _compliance_payload(
        text,
        ScanMode(getattr(args, "mode", ScanMode.CUSTOMER_COPY.value)),
    )
    if compliance["hard_fail"]:
        print("❌ 命中硬性合规规则，Judge 不评分，方案不得交付。")
        for detail in compliance["details"]:
            print("-", detail["rule"], detail.get("description", ""))
        return 1

    if args.emit_prompts:
        from .judge import build_judge_batch

        written = _emit_json(
            build_judge_batch(text), getattr(args, "output", None)
        )
        return 0 if written else 2

    if not args.scores:
        print("用法：先 `judge <方案> --emit-prompts` 交给独立宿主 Judge，")
        print("     再 `judge <方案> --scores <评分.json>` 生成 JudgeReport。")
        print("本轮未做独立质量评分。")
        return 2

    from .judge import build_judge_report

    try:
        with open(args.scores, encoding="utf-8") as handle:
            raw_scores = json.load(handle)
        review_config = _load_review_config(getattr(args, "config", None))
        report = build_judge_report(
            raw_scores,
            source=args.file,
            threshold=args.threshold,
            model=getattr(args, "model", None),
            config=review_config,
            reviewed_at=getattr(args, "reviewed_at", None),
            review_method=getattr(args, "review_method", None),
        )
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print("维度分解析失败:", exc)
        return 2

    payload = report.to_dict()
    payload["quality_threshold"] = args.threshold
    payload["gate_passed"] = report.status == "passed"
    payload["automation_boundary"] = (
        "质量分与徽章仅用于交付复核，不自动批准案例入库或知识原子"
    )
    if args.samples:
        from .monte_carlo import reliability

        try:
            with open(args.samples, encoding="utf-8") as handle:
                payload["reliability"] = reliability(json.load(handle))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print("蒙卡样本解析失败:", exc)
            return 2

    if not _emit_json(payload, getattr(args, "output", None)):
        return 2
    if report.score is None:
        return 2
    return 0 if report.status == "passed" else 1


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate SKILL.md frontmatter, directory names and the 8KB limit."""

    root = args.path
    problems = 0
    for dirpath, _, files in os.walk(root):
        for filename in files:
            if filename != "SKILL.md":
                continue
            path = os.path.join(dirpath, filename)
            raw = open(path, "rb").read()
            text = raw.decode("utf-8")
            match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
            if not match:
                print("⚠️ 缺 frontmatter:", path)
                problems += 1
                continue
            name_match = re.search(
                r"^name:\s*([^\n]+)$", match.group(1), re.MULTILINE
            )
            if not name_match:
                print("⚠️ 缺 frontmatter name:", path)
                problems += 1
            else:
                name = name_match.group(1).strip().strip("'\"")
                dirname = os.path.basename(dirpath)
                if name != dirname:
                    print(
                        f"⚠️ name 与目录名不一致: {path} "
                        f"({name!r} != {dirname!r})"
                    )
                    problems += 1
            if len(raw) > 8 * 1024:
                print(f"⚠️ 超过 8KB: {path} ({len(raw)} bytes)")
                problems += 1
    print("校验完成，问题数:", problems)
    return 1 if problems else 0


def _add_mode_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--mode",
        choices=[mode.value for mode in ScanMode],
        default=ScanMode.CUSTOMER_COPY.value,
        help="扫描语境（默认 customer_copy）",
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="siyu-eval", description="私域方案合规门与独立 Judge"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    compliance_parser = sub.add_parser(
        "compliance", help="静态合规扫描（不产出质量分或徽章）"
    )
    compliance_parser.add_argument("files", nargs="+", metavar="file")
    compliance_parser.add_argument("--json", action="store_true")
    _add_mode_argument(compliance_parser)
    compliance_parser.set_defaults(func=cmd_compliance)

    score_parser = sub.add_parser(
        "score", help="deprecated：兼容别名，等同 compliance"
    )
    score_parser.add_argument("files", nargs="+", metavar="file")
    score_parser.add_argument("--threshold", type=int, default=80)
    score_parser.add_argument("--json", action="store_true")
    _add_mode_argument(score_parser)
    score_parser.set_defaults(func=cmd_score)

    judge_parser = sub.add_parser(
        "judge", help="独立 Judge prompts / JudgeReport"
    )
    judge_parser.add_argument("file")
    judge_action = judge_parser.add_mutually_exclusive_group()
    judge_action.add_argument(
        "--emit-prompts", action="store_true", help="输出独立评审 prompts"
    )
    judge_action.add_argument("--scores", help="独立宿主回填的评分 JSON")
    judge_parser.add_argument("--samples", help="N 份蒙卡样本度量 JSON")
    judge_parser.add_argument("--threshold", type=int, default=80)
    judge_parser.add_argument("--output", help="机器可读输出文件")
    judge_parser.add_argument("--model", help="Judge 模型标识")
    judge_parser.add_argument("--config", help="Judge 配置 JSON 文件")
    judge_parser.add_argument("--reviewed-at", help="评审时间（ISO 8601）")
    judge_parser.add_argument("--review-method", help="评审方式")
    _add_mode_argument(judge_parser)
    judge_parser.set_defaults(func=cmd_judge)

    validate_parser = sub.add_parser("validate")
    validate_parser.add_argument("path", nargs="?", default="plugins/")
    validate_parser.set_defaults(func=cmd_validate)

    args = parser.parse_args(argv)
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
