"""结构化任务 Runtime CLI。"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from .runtime import SiyuRuntime
from .task import TaskValidationError
from .tracing import cleanup_old_traces


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="siyu-plan",
        description="把私域自然语言请求转换成可验证、可追踪的执行计划",
    )
    parser.add_argument("request", nargs="?", default="", help="用户的原始私域请求")
    parser.add_argument("--industry", default="")
    parser.add_argument("--stage", default="")
    parser.add_argument("--client", default="")
    parser.add_argument("--audience", default="")
    parser.add_argument("--no-trace", action="store_true")
    parser.add_argument(
        "--cleanup-traces",
        action="store_true",
        help="清理过期本地追踪文件后退出（不解析 request）",
    )
    parser.add_argument(
        "--trace-days",
        type=int,
        default=30,
        help="与 --cleanup-traces 联用，保留最近 N 天（默认 30）",
    )
    parser.add_argument(
        "--trace-dir",
        default=".siyu-team/traces",
        help="追踪目录（默认 .siyu-team/traces）",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cleanup_traces:
        count, size = cleanup_old_traces(args.trace_dir, args.trace_days)
        print(f"已删除 {count} 个追踪文件，释放 {size / 1024:.1f} KB")
        return 0
    if not args.request:
        print("缺少 request；清理追踪请用 --cleanup-traces", file=sys.stderr)
        return 2
    hints = {
        key: value
        for key, value in {
            "industry": args.industry,
            "stage": args.stage,
            "client": args.client,
            "audience": args.audience,
        }.items()
        if value
    }
    try:
        plan = SiyuRuntime().plan(
            args.request, hints=hints, trace=not args.no_trace
        )
    except TaskValidationError as exc:
        print(f"任务无效：{exc}", file=sys.stderr)
        message = str(exc)
        if "字符上限" in message or "source_text" in message:
            print(
                "提示：请把请求缩短到 20000 字以内后再试。",
                file=sys.stderr,
            )
        return 2
    if (
        plan.decision.needs_clarification
        and "kind" in plan.decision.required_fields
    ):
        print(
            "提示：意图信号不足或命中多个意图，建议先向用户确认要解决哪一个。",
            file=sys.stderr,
        )
    print(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
