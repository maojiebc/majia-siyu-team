from __future__ import annotations

import unittest
from typing import Any, Mapping

from siyu_team.connectors.lark import (
    BITABLE_BASE,
    LarkAPIError,
    LarkBitable,
    LarkConfig,
    TOKEN_URL,
)


class FakeTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, Mapping[str, str] | None]] = []
        self.queue: list[tuple[int, dict[str, Any]]] = []

    def push(self, status: int, payload: dict[str, Any]) -> None:
        self.queue.append((status, payload))

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        body: Mapping[str, Any] | None = None,
        query: Mapping[str, str] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        self.calls.append((method, url, headers, body))
        del query
        if not self.queue:
            raise AssertionError(f"unexpected request {method} {url}")
        return self.queue.pop(0)


def _config() -> LarkConfig:
    return LarkConfig(
        app_id="cli_test",
        app_secret="secret",
        app_token="basetoken",
        table_submissions="tbl_sub",
        table_confirmations="tbl_conf",
    )


class LarkBitableTests(unittest.TestCase):
    def test_token_and_paginated_list_and_update(self) -> None:
        transport = FakeTransport()
        transport.push(200, {"code": 0, "tenant_access_token": "tok-1"})
        transport.push(
            200,
            {
                "code": 0,
                "data": {
                    "items": [{"record_id": "rec1", "fields": {"业态": "餐饮"}}],
                    "has_more": True,
                    "page_token": "p2",
                },
            },
        )
        transport.push(
            200,
            {
                "code": 0,
                "data": {
                    "items": [{"record_id": "rec2", "fields": {"业态": "零售"}}],
                    "has_more": False,
                },
            },
        )
        transport.push(200, {"code": 0, "data": {"record": {"record_id": "rec1"}}})
        client = LarkBitable(_config(), transport=transport, sleeper=lambda _: None)
        records = client.list_records("tbl_sub")
        self.assertEqual([row["record_id"] for row in records], ["rec1", "rec2"])
        updated = client.update_record("tbl_sub", "rec1", {"状态": "已收录D"})
        self.assertEqual(updated["code"], 0)
        self.assertEqual(transport.calls[0][1], TOKEN_URL)
        self.assertIn(f"{BITABLE_BASE}/basetoken/tables/tbl_sub/records", transport.calls[1][1])
        self.assertTrue(transport.calls[1][2]["Authorization"].endswith("tok-1"))

    def test_retries_on_429_then_succeeds(self) -> None:
        transport = FakeTransport()
        transport.push(200, {"code": 0, "tenant_access_token": "tok-1"})
        transport.push(429, {"code": 999, "msg": "busy"})
        transport.push(
            200,
            {"code": 0, "data": {"items": [], "has_more": False}},
        )
        sleeps: list[float] = []
        client = LarkBitable(
            _config(), transport=transport, sleeper=lambda seconds: sleeps.append(seconds)
        )
        self.assertEqual(client.list_records("tbl_sub"), [])
        self.assertEqual(sleeps, [1.0])

    def test_business_error_raises(self) -> None:
        transport = FakeTransport()
        transport.push(200, {"code": 999, "msg": "nope"})
        client = LarkBitable(_config(), transport=transport, sleeper=lambda _: None)
        with self.assertRaises(LarkAPIError):
            client.tenant_access_token()

    def test_error_message_omits_request_and_raw_body(self) -> None:
        transport = FakeTransport()
        transport.push(
            400,
            {
                "code": 999,
                "msg": "invalid",
                "app_secret": "super-secret",
                "tenant_access_token": "leak-me",
            },
        )
        client = LarkBitable(_config(), transport=transport, sleeper=lambda _: None)
        with self.assertRaises(LarkAPIError) as ctx:
            client.tenant_access_token()
        text = str(ctx.exception)
        self.assertIn("HTTP 400", text)
        self.assertIn("code=999", text)
        self.assertIn("msg=invalid", text)
        self.assertNotIn("super-secret", text)
        self.assertNotIn("leak-me", text)
        self.assertNotIn("app_secret", text)

    def test_from_env_uses_lark_variables(self) -> None:
        transport = FakeTransport()
        transport.push(200, {"code": 0, "tenant_access_token": "tok-env"})
        transport.push(200, {"code": 0, "data": {"items": [], "has_more": False}})
        env = {
            "LARK_APP_ID": "id",
            "LARK_APP_SECRET": "sec",
            "LARK_BASE_APP_TOKEN": "base",
            "LARK_TABLE_SUBMISSIONS": "tbl_sub",
            "LARK_TABLE_CONFIRMATIONS": "tbl_conf",
        }
        client = LarkBitable.from_env(env, transport=transport)
        self.assertEqual(client.list_submissions(), [])

    def test_batch_create_update_delete(self) -> None:
        transport = FakeTransport()
        transport.push(200, {"code": 0, "tenant_access_token": "tok-1"})
        transport.push(200, {"code": 0, "data": {"records": [{"record_id": "pub1"}]}})
        transport.push(200, {"code": 0, "data": {"records": [{"record_id": "pub1"}]}})
        transport.push(200, {"code": 0, "data": {"records": ["pub1"]}})
        client = LarkBitable(_config(), transport=transport, sleeper=lambda _: None)
        created = client.batch_create_records(
            "tbl_pub", [{"fields": {"判断": "一条", "来源记录": "rec_s1"}}]
        )
        self.assertEqual(created["code"], 0)
        client.batch_update_records(
            "tbl_pub",
            [{"record_id": "pub1", "fields": {"状态": "已收录D"}}],
        )
        client.batch_delete_records("tbl_pub", ["pub1"])
        self.assertIn("/records/batch_create", transport.calls[1][1])
        self.assertEqual(
            transport.calls[1][3],
            {"records": [{"fields": {"判断": "一条", "来源记录": "rec_s1"}}]},
        )
        self.assertIn("/records/batch_update", transport.calls[2][1])
        self.assertIn("/records/batch_delete", transport.calls[3][1])
        self.assertEqual(transport.calls[3][3], {"records": ["pub1"]})


if __name__ == "__main__":
    unittest.main()
