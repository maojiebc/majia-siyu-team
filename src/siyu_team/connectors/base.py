"""连接器共享骨架：keychain 密钥解析 + 统一异常。

公开层只提供**解析机制**，绝不硬编码任何真实 token/endpoint。
真实 API 调用由各连接器在接入时实现（私有版注入）。
"""
from __future__ import annotations

import os
import subprocess


class ConnectorNotConfigured(RuntimeError):
    """密钥未配置：keychain 与环境变量里都找不到。"""


class ConnectorNotImplemented(NotImplementedError):
    """密钥已解析，但该平台的具体 API 调用尚未接入。"""


def resolve_secret(pointer: str) -> str | None:
    """解析 ``keychain:siyu-team/<tool>`` 指针 → 真实密钥。

    顺序：环境变量 ``SIYU_<TOOL>_TOKEN`` → macOS keychain（``security`` 命令）。
    都没有则返回 ``None``；本函数永不返回硬编码值。
    """
    if not pointer or not pointer.startswith("keychain:"):
        return None
    service = pointer.split(":", 1)[1]  # siyu-team/<tool>
    tool = service.rsplit("/", 1)[-1]
    env_key = f"SIYU_{tool.upper().replace('-', '_')}_TOKEN"
    if os.environ.get(env_key):
        return os.environ[env_key]
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-w"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    secret = result.stdout.strip()
    return secret or None


def require_secret(pointer: str, label: str, env_hint: str) -> str:
    """解析密钥；找不到就抛出可操作的未配置错误。"""
    secret = resolve_secret(pointer)
    if not secret:
        raise ConnectorNotConfigured(
            f"{label}未配置：把密钥存入 keychain（{pointer}），"
            f"或设环境变量 {env_hint}。真实 token 不入库。"
        )
    return secret
