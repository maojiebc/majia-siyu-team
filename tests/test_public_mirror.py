from __future__ import annotations

from typing import Any, Mapping
import unittest

from siyu_team.connectors.lark import LarkBitable, LarkConfig
from siyu_team.contribution.intake import (
    ANON_LABEL,
    GIFT_REVOKED,
    STATUS_APPROVED,
    STATUS_MANUAL,
    STATUS_PENDING,
    STATUS_REJECTED_REVIEW,
    STATUS_REVOKED,
    IntakeDecision,
    candidate_to_atom,
    record_to_candidate,
    render_gift,
)
from siyu_team.contribution.public_mirror import (
    PUBLIC_FORBIDDEN_FIELDS,
    PUBLIC_SOURCE_FIELD,
    build_public_fields,
    mirror_public_table,
)


SALT = "test-salt"


class FakeTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, Mapping[str, Any] | None]] = []
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
        self.calls.append((method, url, body))
        del headers, query
        if not self.queue:
            raise AssertionError(f"unexpected request {method} {url}")
        return self.queue.pop(0)


def _config() -> LarkConfig:
    return LarkConfig(
        app_id="cli_test",
        app_secret="secret",
        app_token="publicbase",
        table_submissions="tbl_public",
        table_confirmations="tbl_public",
    )


def _record() -> dict[str, Any]:
    return {
        "record_id": "rec_pub",
        "fields": {
            "业态": "餐饮·正餐",
            "细分": "川菜",
            "经营模式": "直营",
            "门店数": "11-50",
            "这条属于": "方法",
            "一件有效的事（或没用的事）": "公开镜像只写脱敏后的判断句。",
            "数字/证据": "加微率 12%→19%",
            "发现时间": "2026-08-01",
            "现在还有效吗": "是",
            "公司/品牌": "江南茶社",
            "联系方式": "13800138000",
            "创建时间": "2026-09-01T02:00:00+08:00",
        },
    }


def _accepted() -> tuple[IntakeDecision, dict[str, Any]]:
    record = _record()
    atom = candidate_to_atom(record_to_candidate(record, salt=SALT), (), ())
    return (
        IntakeDecision(record["record_id"], STATUS_PENDING, atom, render_gift(atom), None),
        record,
    )


class PublicMirrorTests(unittest.TestCase):
    def test_public_fields_omit_company_and_use_display_or_anon(self) -> None:
        decision, record = _accepted()
        fields = build_public_fields(decision, record)
        assert fields is not None
        self.assertEqual(fields[PUBLIC_SOURCE_FIELD], "rec_pub")
        self.assertEqual(fields["判断"], "公开镜像只写脱敏后的判断句。")
        self.assertEqual(fields["数字/证据"], "加微率 12%→19%")
        self.assertEqual(fields["对外显示名"], ANON_LABEL)
        self.assertEqual(fields["状态"], STATUS_PENDING)
        self.assertEqual(fields["等级"], "待审（建议D）")
        self.assertEqual(fields["印证数"], 0)
        self.assertEqual(fields["业态"], "餐饮·正餐")
        for name in PUBLIC_FORBIDDEN_FIELDS:
            self.assertNotIn(name, fields)
        self.assertNotIn("13800138000", str(fields))
        self.assertNotIn("江南茶社", str(fields))

    def test_create_via_fake_transport(self) -> None:
        decision, record = _accepted()
        transport = FakeTransport()
        transport.push(200, {"code": 0, "tenant_access_token": "tok-1"})
        transport.push(200, {"code": 0, "data": {"items": [], "has_more": False}})
        transport.push(200, {"code": 0, "data": {"records": [{"record_id": "pub1"}]}})
        client = LarkBitable(_config(), transport=transport, sleeper=lambda _: None)
        plan = mirror_public_table(
            decisions=(decision,),
            submissions=(record,),
            client=client,
            table_id="tbl_public",
        )
        self.assertEqual(len(plan.creates), 1)
        self.assertEqual(plan.creates[0][PUBLIC_SOURCE_FIELD], "rec_pub")
        self.assertTrue(any("/records/batch_create" in url for _, url, _ in transport.calls))
        created = next(body for method, url, body in transport.calls if body and "batch_create" in url)
        payload = created["records"][0]["fields"]
        self.assertEqual(payload["来源记录"], "rec_pub")
        self.assertNotIn("公司/品牌", payload)
        self.assertNotIn("回礼", payload)

    def test_update_unchanged_skips_write(self) -> None:
        decision, record = _accepted()
        desired = build_public_fields(decision, record)
        assert desired is not None
        transport = FakeTransport()
        transport.push(200, {"code": 0, "tenant_access_token": "tok-1"})
        transport.push(
            200,
            {
                "code": 0,
                "data": {
                    "items": [
                        {
                            "record_id": "pub_existing",
                            "fields": desired,
                        }
                    ],
                    "has_more": False,
                },
            },
        )
        client = LarkBitable(_config(), transport=transport, sleeper=lambda _: None)
        plan = mirror_public_table(
            decisions=(decision,),
            submissions=(record,),
            client=client,
            table_id="tbl_public",
        )
        self.assertEqual(plan.skips, ("rec_pub",))
        self.assertEqual(plan.creates, ())
        self.assertEqual(plan.updates, ())
        self.assertFalse(
            any("batch_" in url for _method, url, _body in transport.calls)
        )

    def test_revoke_deletes_public_row(self) -> None:
        record = _record()
        decision = IntakeDecision(
            "rec_pub", STATUS_REVOKED, None, GIFT_REVOKED, None, writeback_atom_id="ka_deadbeefdeadbee"
        )
        transport = FakeTransport()
        transport.push(200, {"code": 0, "tenant_access_token": "tok-1"})
        transport.push(
            200,
            {
                "code": 0,
                "data": {
                    "items": [
                        {
                            "record_id": "pub_old",
                            "fields": {PUBLIC_SOURCE_FIELD: "rec_pub", "判断": "旧文"},
                        }
                    ],
                    "has_more": False,
                },
            },
        )
        transport.push(200, {"code": 0, "data": {"records": ["pub_old"]}})
        client = LarkBitable(_config(), transport=transport, sleeper=lambda _: None)
        plan = mirror_public_table(
            decisions=(decision,),
            submissions=(record,),
            client=client,
            table_id="tbl_public",
        )
        self.assertEqual(plan.deletes, ("pub_old",))
        delete = next(
            body for _method, url, body in transport.calls if body and "batch_delete" in url
        )
        self.assertEqual(delete, {"records": ["pub_old"]})

    def test_rejected_deletes_public_row(self) -> None:
        record = _record()
        decision = IntakeDecision(
            "rec_pub",
            STATUS_REJECTED_REVIEW,
            None,
            "",
            None,
            writeback_atom_id="ka_deadbeefdeadbee",
        )
        transport = FakeTransport()
        transport.push(200, {"code": 0, "tenant_access_token": "tok-1"})
        transport.push(
            200,
            {
                "code": 0,
                "data": {
                    "items": [
                        {
                            "record_id": "pub_old",
                            "fields": {PUBLIC_SOURCE_FIELD: "rec_pub", "判断": "旧文"},
                        }
                    ],
                    "has_more": False,
                },
            },
        )
        transport.push(200, {"code": 0, "data": {"records": ["pub_old"]}})
        client = LarkBitable(_config(), transport=transport, sleeper=lambda _: None)
        plan = mirror_public_table(
            decisions=(decision,),
            submissions=(record,),
            client=client,
            table_id="tbl_public",
        )
        self.assertEqual(plan.deletes, ("pub_old",))

    def test_approved_public_grade_uses_reviewer_letter(self) -> None:
        from siyu_team.knowledge.models import KnowledgeAtomV2

        record = _record()
        atom = candidate_to_atom(record_to_candidate(record, salt=SALT), (), ())
        payload = atom.to_dict()
        payload["quality"]["review_status"] = "approved"
        payload["quality"]["evidence_grade"] = "C"
        payload["quality"]["reviewer"] = "评审员"
        payload["quality"]["reviewed_at"] = "2026-09-03"
        atom = KnowledgeAtomV2.from_dict(payload)
        decision = IntakeDecision(
            record["record_id"], STATUS_APPROVED, atom, render_gift(atom), None
        )
        fields = build_public_fields(decision, record)
        assert fields is not None
        self.assertEqual(fields["状态"], STATUS_APPROVED)
        self.assertEqual(fields["等级"], "评审通过·C级")

    def test_manual_deletes_if_previously_mirrored(self) -> None:
        record = _record()
        decision = IntakeDecision("rec_pub", STATUS_MANUAL, None, "", None)
        transport = FakeTransport()
        transport.push(200, {"code": 0, "tenant_access_token": "tok-1"})
        transport.push(
            200,
            {
                "code": 0,
                "data": {
                    "items": [
                        {
                            "record_id": "pub_old",
                            "fields": {PUBLIC_SOURCE_FIELD: "rec_pub"},
                        }
                    ],
                    "has_more": False,
                },
            },
        )
        transport.push(200, {"code": 0, "data": {"records": ["pub_old"]}})
        client = LarkBitable(_config(), transport=transport, sleeper=lambda _: None)
        plan = mirror_public_table(
            decisions=(decision,),
            submissions=(record,),
            client=client,
            table_id="tbl_public",
        )
        self.assertEqual(plan.deletes, ("pub_old",))

    def test_dry_run_prints_plan_without_writes(self) -> None:
        decision, record = _accepted()
        transport = FakeTransport()
        transport.push(200, {"code": 0, "tenant_access_token": "tok-1"})
        transport.push(200, {"code": 0, "data": {"items": [], "has_more": False}})
        client = LarkBitable(_config(), transport=transport, sleeper=lambda _: None)
        plan = mirror_public_table(
            decisions=(decision,),
            submissions=(record,),
            client=client,
            table_id="tbl_public",
            dry_run=True,
        )
        self.assertEqual(len(plan.creates), 1)
        self.assertFalse(any("batch_" in url for _method, url, _body in transport.calls))


if __name__ == "__main__":
    unittest.main()
