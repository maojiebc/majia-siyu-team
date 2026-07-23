from __future__ import annotations

import os
import unittest

from siyu_team.connectors import bi_platform
from siyu_team.connectors.base import (
    ConnectorNotConfigured,
    ConnectorNotImplemented,
    require_secret,
    resolve_secret,
)


class ConnectorSecretTests(unittest.TestCase):
    """keychain 骨架：解析机制真实，绝不硬编码 token。"""

    def test_resolve_from_env_var(self) -> None:
        os.environ["SIYU_UNITTEST_TOKEN"] = "s3cr3t"
        try:
            self.assertEqual(
                resolve_secret("keychain:siyu-team/unittest"), "s3cr3t"
            )
        finally:
            del os.environ["SIYU_UNITTEST_TOKEN"]

    def test_non_pointer_returns_none(self) -> None:
        self.assertIsNone(resolve_secret("not-a-pointer"))
        self.assertIsNone(resolve_secret(""))

    def test_require_secret_raises_when_absent(self) -> None:
        # 无环境变量；非 macOS 或 keychain 无此条目时统一 None → 抛未配置。
        os.environ.pop("SIYU_ABSENTTOOL_TOKEN", None)
        with self.assertRaises(ConnectorNotConfigured):
            require_secret(
                "keychain:siyu-team/absenttool", "测试平台", "SIYU_ABSENTTOOL_TOKEN"
            )

    def test_connector_call_flow(self) -> None:
        os.environ.pop("SIYU_BI_PLATFORM_TOKEN", None)
        with self.assertRaises(ConnectorNotConfigured):
            bi_platform.call()
        # 有密钥 → 骨架解析成功，落到 NotImplemented（具体 API 待接）。
        os.environ["SIYU_BI_PLATFORM_TOKEN"] = "token123"
        try:
            with self.assertRaises(ConnectorNotImplemented):
                bi_platform.call()
        finally:
            del os.environ["SIYU_BI_PLATFORM_TOKEN"]


if __name__ == "__main__":
    unittest.main()
