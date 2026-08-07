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

# 组件 plugin.json 的 version 也要与发布版一致（此前是 CI 盲区，会静默漂移）。
for plugin_json in sorted(ROOT.glob("plugins/*/.claude-plugin/plugin.json")):
    data = json.loads(plugin_json.read_text(encoding="utf-8"))
    if data.get("version") != version:
        errors.append(
            f"组件 {plugin_json.parent.parent.name}/plugin.json 版本 "
            f"{data.get('version')!r} 与 VERSION 不一致"
        )

# Python 包 __version__ 同样是漂移盲区（曾停在 0.4.0 直到 1.3.0 才发现）。
init_text = (ROOT / "src/siyu_team/__init__.py").read_text(encoding="utf-8")
init_match = re.search(r'__version__\s*=\s*"([^"]+)"', init_text)
if not init_match:
    errors.append("src/siyu_team/__init__.py 未找到 __version__")
elif init_match.group(1) != version:
    errors.append(f"__init__.py __version__ {init_match.group(1)!r} 与 VERSION 不一致")

pyproject_text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
pyproject_match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject_text, re.M)
if not pyproject_match:
    errors.append("pyproject.toml 未找到 version")
elif pyproject_match.group(1) != version:
    errors.append(f"pyproject.toml version {pyproject_match.group(1)!r} 与 VERSION 不一致")

# CodeBuddy 分发面同样漂移过（marketplace 停 1.2.1、plugin 停 1.2.8 直到 1.4.0 才发现）。
for rel in (".codebuddy-plugin/marketplace.json", ".codebuddy-plugin/plugin.json"):
    cb_path = ROOT / rel
    if not cb_path.exists():
        continue
    cb_data = json.loads(cb_path.read_text(encoding="utf-8"))
    cb_versions = [cb_data.get("version"), cb_data.get("metadata", {}).get("version")]
    cb_versions += [plugin.get("version") for plugin in cb_data.get("plugins", [])]
    for found in cb_versions:
        if found is not None and found != version:
            errors.append(f"{rel} 版本 {found!r} 与 VERSION 不一致")

badge = re.search(
    r"img\.shields\.io/badge/(?:skill-)?v?([0-9.]+)-[A-Fa-f0-9]+\.svg",
    readme,
)
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
