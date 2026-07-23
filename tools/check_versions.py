#!/usr/bin/env python3
"""校验 VERSION、marketplace 和 README 版本徽章一致。"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys


ROOT = Path(os.environ.get("SIYU_RELEASE_ROOT", Path(__file__).resolve().parents[1])).resolve()
version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
readme = (ROOT / "README.md").read_text(encoding="utf-8")
errors = []

if not re.fullmatch(r"\d+\.\d+\.\d+", version):
    errors.append(f"VERSION 不是语义版本：{version!r}")
if marketplace.get("metadata", {}).get("version") != version:
    errors.append("marketplace metadata.version 与 VERSION 不一致")
for plugin in marketplace.get("plugins", []):
    if plugin.get("version") != version:
        errors.append(f"marketplace 插件 {plugin.get('name', '<未命名>')} 版本不一致")

badge = re.search(r"img\.shields\.io/badge/version-([0-9.]+)-[A-Fa-f0-9]+\.svg", readme)
if not badge:
    errors.append("README 未找到版本徽章")
elif badge.group(1) != version:
    errors.append(f"README 徽章版本 {badge.group(1)!r} 与 VERSION 不一致")

if errors:
    print("版本校验失败：", file=sys.stderr)
    for error in errors:
        print("-", error, file=sys.stderr)
    raise SystemExit(1)
print(f"版本校验通过：{version}（{len(marketplace.get('plugins', []))} 个安装单元）")
