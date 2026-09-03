"""结构化任务 Runtime CLI。"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from .errors import KnowledgeLoadError, SiyuBaseError
from .routing import ROUTE_CONTRACT_VERSION, route_contract_digest
from .runtime import PLAN_SCHEMA_VERSION, RuntimeMode, SiyuRuntime
from .task import TaskValidationError
from .tracing import (
    DEFAULT_TRACE_MAX_BYTES,
    DEFAULT_TRACE_MAX_FILES,
    MAX_TRACE_RETENTION_DAYS,
    TraceLevel,
    TraceRecorder,
    cleanup_old_traces,
)


def _non_negative_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("必须是非负整数") from exc
    if number < 0:
        raise argparse.ArgumentTypeError("必须是非负整数")
    return number


def _retention_days(value: str) -> int:
    number = _non_negative_int(value)
    if number > MAX_TRACE_RETENTION_DAYS:
        raise argparse.ArgumentTypeError(
            f"不得超过 {MAX_TRACE_RETENTION_DAYS} 天"
        )
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="siyu-plan",
        description="把私域自然语言请求转换成可验证、可追踪的执行计划",
    )
    parser.add_argument("request", nargs="?", default="", help="用户的原始私域请求")
    parser.add_argument("--industry", default="")
    parser.add_argument("--stage", default="")
    parser.add_argument(
        "--model",
        dest="business_model",
        default="",
        help="经营模式：direct 直营 / franchise 加盟 / mixed 混合",
    )
    parser.add_argument("--client", default="")
    parser.add_argument("--audience", default="")
    trace_group = parser.add_mutually_exclusive_group()
    trace_group.add_argument("--no-trace", action="store_true")
    trace_group.add_argument(
        "--trace-level",
        choices=[level.value for level in TraceLevel],
        default=TraceLevel.METADATA.value,
        help=(
            "追踪级别（默认 metadata 不保存原文；redacted/full 必须显式选择）"
        ),
    )
    parser.add_argument(
        "--contract-info",
        action="store_true",
        help="输出 Runtime/路由契约版本与哈希后退出",
    )
    parser.add_argument(
        "--cleanup-traces",
        action="store_true",
        help="清理过期本地追踪文件后退出（不解析 request）",
    )
    parser.add_argument(
        "--trace-days",
        type=_retention_days,
        default=30,
        help="追踪保留天数（默认 30；启动时自动清理）",
    )
    parser.add_argument(
        "--trace-dir",
        default=".siyu-team/traces",
        help="追踪目录（默认 .siyu-team/traces）",
    )
    parser.add_argument(
        "--trace-max-bytes",
        type=_non_negative_int,
        default=DEFAULT_TRACE_MAX_BYTES,
        help="追踪目录容量上限（默认 50 MiB）",
    )
    parser.add_argument(
        "--trace-max-files",
        type=_non_negative_int,
        default=DEFAULT_TRACE_MAX_FILES,
        help="追踪文件数量上限（默认 1000）",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.contract_info:
        print(
            json.dumps(
                {
                    "plan_schema_version": PLAN_SCHEMA_VERSION,
                    "route_contract_version": ROUTE_CONTRACT_VERSION,
                    "route_contract_hash": route_contract_digest(),
                    "runtime_modes": [mode.value for mode in RuntimeMode],
                    "trace_levels": [level.value for level in TraceLevel],
                    "default_trace_level": TraceLevel.METADATA.value,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.cleanup_traces:
        try:
            count, size = cleanup_old_traces(
                args.trace_dir,
                args.trace_days,
                max_bytes=args.trace_max_bytes,
                max_files=args.trace_max_files,
            )
        except (OSError, ValueError) as exc:
            print(f"追踪清理失败：{exc}", file=sys.stderr)
            return 2
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
            "business_model": args.business_model,
            "client": args.client,
            "audience": args.audience,
        }.items()
        if value
    }
    try:
        runtime = SiyuRuntime(
            trace_recorder=TraceRecorder(
                args.trace_dir,
                level=args.trace_level,
                retention_days=args.trace_days,
                max_bytes=args.trace_max_bytes,
                max_files=args.trace_max_files,
            )
        )
        plan = runtime.plan(
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
    except KnowledgeLoadError as exc:
        print(f"知识文件损坏：{exc}", file=sys.stderr)
        print(
            "提示：检查报错里指出的 JSONL 行并修复，或删除该私有副本后重跑"
            "（正式集可用 tools/build_growth_atoms.py 重建）。",
            file=sys.stderr,
        )
        return 2
    except SiyuBaseError as exc:
        print(f"执行失败：{exc}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as exc:
        print(f"追踪配置或路径无效：{exc}", file=sys.stderr)
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
