"""结构化任务 Runtime CLI。"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from .runtime import SiyuRuntime
from .task import TaskValidationError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="siyu-plan",
        description="把私域自然语言请求转换成可验证、可追踪的执行计划",
    )
    parser.add_argument("request", help="用户的原始私域请求")
    parser.add_argument("--industry", default="")
    parser.add_argument("--stage", default="")
    parser.add_argument("--client", default="")
    parser.add_argument("--audience", default="")
    parser.add_argument("--no-trace", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
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
        return 2
    print(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
