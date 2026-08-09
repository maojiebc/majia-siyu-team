#!/usr/bin/env python3
"""Render the Runtime route contract into every public distribution."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src"
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))

from siyu_team.routing import route_contract_document  # noqa: E402


TARGETS = (
    ROOT / "plugins/siyu-core/skills/majia-siyu/references/route-contract.json",
    ROOT / "skillhub/majia-siyu/modules/_runtime/route-contract.json",
)


def rendered_bytes() -> bytes:
    return (
        json.dumps(
            route_contract_document(),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def check_targets(expected: bytes) -> list[str]:
    errors: list[str] = []
    for target in TARGETS:
        if not target.is_file():
            errors.append(f"缺少生成契约：{target.relative_to(ROOT)}")
        elif target.read_bytes() != expected:
            errors.append(f"生成契约已漂移：{target.relative_to(ROOT)}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 Runtime/Markdown 共用路由契约")
    parser.add_argument("--check", action="store_true", help="只检查，不写文件")
    args = parser.parse_args()
    expected = rendered_bytes()
    if args.check:
        errors = check_targets(expected)
        if errors:
            for error in errors:
                print(f"- {error}")
            return 1
        print("路由契约生成物一致")
        return 0
    for target in TARGETS:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(expected)
        print(target.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
