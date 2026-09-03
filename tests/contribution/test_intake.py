from __future__ import annotations

import json
from pathlib import Path
import unittest

from datetime import date, datetime
from zoneinfo import ZoneInfo

from siyu_team.contribution.intake import (
    HASH_SALT_ENV,
    MODE_LENIENT,
    MODE_STRICT,
    ANON_LABEL,
    PUBLIC_DASHBOARD_URL,
    NOTE_PII_DISPLAY_NAME,
    NOTE_PII_REDACTED,
    NOTE_UNKNOWN_KIND,
    STATUS_APPROVED,
    STATUS_MANUAL,
    STATUS_PENDING,
    STATUS_REJECTED_REVIEW,
    STATUS_REVOKED,
    HashSaltError,
    _as_link,
    _as_text,
    _with_confirmations,
    candidate_to_atom,
    dedupe,
    flag_conflicts,
    hash_identity,
    hash_salt,
    map_channels,
    map_contributor_role,
    map_industry,
    map_org_layers,
    map_scale_band,
    normalize_company_name,
    parse_confirmation_row,
    record_to_candidate,
    resolve_confirmation_target,
    render_gift,
    run_intake,
    statement_jaccard,
    writeback_fields_changed,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/community/sample_records.json"
SALT = "test-salt"


class CommunityIntakeTests(unittest.TestCase):
    def test_hash_is_salted_and_normalized(self) -> None:
        first = hash_identity("江南茶社", SALT)
        second = hash_identity(" 江南 茶社 ", SALT)
        other = hash_identity("北城面馆", SALT)
        self.assertEqual(first, second)
        self.assertNotEqual(first, other)
        self.assertEqual(len(first), 64)

    def test_company_suffixes_and_regions_hash_as_one(self) -> None:
        names = ("江南茶社", "江南茶社有限公司", "江南茶社（上海）", "江南茶社(上海)")
        hashes = {hash_identity(name, SALT) for name in names}
        self.assertEqual(len(hashes), 1)
        self.assertEqual(normalize_company_name("江南茶社上海分公司"), "江南茶社上海")

    def test_hash_salt_fails_closed_when_missing_or_short(self) -> None:
        with self.assertRaises(HashSaltError):
            hash_salt({HASH_SALT_ENV: ""})
        with self.assertRaises(HashSaltError):
            hash_salt({HASH_SALT_ENV: "short-salt"})
        self.assertEqual(
            hash_salt({HASH_SALT_ENV: "community-intake-test-salt"}),
            "community-intake-test-salt",
        )

    def test_fixture_promotes_two_company_statement_and_holds_pii(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        result = run_intake(
            payload["submissions"],
            payload["confirmations"],
            salt=SALT,
            mode=MODE_STRICT,
        )
        self.assertEqual(result.metrics["submissions_total"], 7)
        self.assertEqual(result.metrics["approved_total"], 2)
        self.assertGreaterEqual(result.metrics["pending_total"], 1)
        self.assertEqual(result.metrics["needs_manual"], 3)
        self.assertEqual(result.metrics["confirmations_unresolved"], 0)
        statuses = {item.record_id: item.status for item in result.decisions}
        self.assertEqual(statuses["rec_s1"], STATUS_APPROVED)
        self.assertEqual(statuses["rec_s2"], STATUS_APPROVED)
        self.assertEqual(statuses["rec_s3"], STATUS_PENDING)
        self.assertEqual(statuses["rec_s4"], STATUS_MANUAL)
        self.assertEqual(statuses["rec_s5"], STATUS_MANUAL)
        self.assertEqual(statuses["rec_s6"], STATUS_MANUAL)
        self.assertEqual(statuses["rec_s7"], STATUS_PENDING)
        large = next(item.atom for item in result.decisions if item.record_id == "rec_s7")
        assert large is not None
        self.assertEqual(large.scope.scale_band, ("5000+",))
        self.assertEqual(large.scope.org_layers, "regional")
        self.assertEqual(large.source.contributor_role, "hq")
        self.assertEqual(large.scope.channels, ("wecom", "miniprogram_member"))
        self.assertEqual(large.scope.industry, "catering")
        self.assertTrue(all(item.atom is None or "13800138000" not in item.atom.statement for item in result.decisions))
        c_atoms = [atom for atom in result.atoms if atom.quality.evidence_grade == "C"]
        self.assertEqual(len(c_atoms), 1)
        self.assertEqual(c_atoms[0].type, "platform_workaround")
        self.assertEqual(c_atoms[0].quality.platform_rule_risk, "medium")
        self.assertTrue(c_atoms[0].lifecycle.valid_until)
        self.assertEqual(c_atoms[0].source.contributor_display_name, "江南茶社小林")
        self.assertEqual(c_atoms[0].quality.confirmations[0].display_name, "江南茶社小林")
        d_atoms = [atom for atom in result.atoms if atom.quality.evidence_grade == "D"]
        self.assertTrue(all(not atom.source.contributor_display_name for atom in d_atoms))

    def test_candidate_to_atom_is_deterministic(self) -> None:
        record = {
            "record_id": "rec_x",
            "fields": {
                "业态": "零售",
                "经营模式": "直营",
                "门店数": "1",
                "这条属于": "方法",
                "一件有效的事（或没用的事）": "提货时加企微，不要把会员资产留在导购个微。",
                "发现时间": "2026-08-01",
                "现在还有效吗": "是",
                "公司/品牌": "巷口便利",
            },
        }
        candidate = record_to_candidate(record, salt=SALT)
        first = candidate_to_atom(candidate, (), ())
        second = candidate_to_atom(candidate, (), ())
        self.assertEqual(first.id, second.id)
        self.assertEqual(first.quality.evidence_grade, "D")
        self.assertNotIn("巷口便利", first.to_json())

    def test_dedupe_jaccard_becomes_confirmation(self) -> None:
        record_a = {
            "record_id": "a",
            "fields": {
                "业态": "餐饮",
                "经营模式": "加盟",
                "门店数": "2-10",
                "这条属于": "方法",
                "一件有效的事（或没用的事）": "高峰只保留一步加微，店员才做得到。",
                "发现时间": "2026-08-01",
                "现在还有效吗": "是",
                "公司/品牌": "甲店",
            },
        }
        record_b = {
            "record_id": "b",
            "fields": {
                "业态": "餐饮",
                "经营模式": "直营",
                "门店数": "2-10",
                "这条属于": "方法",
                "一件有效的事（或没用的事）": "高峰只保留一步加微，店员才做得到。",
                "发现时间": "2026-08-02",
                "现在还有效吗": "是",
                "公司/品牌": "乙店",
            },
        }
        atom_a = candidate_to_atom(record_to_candidate(record_a, salt=SALT), (), ())
        atom_b = candidate_to_atom(record_to_candidate(record_b, salt=SALT), (), ())
        self.assertGreaterEqual(statement_jaccard(atom_a.statement, atom_b.statement), 0.8)
        merged = dedupe((atom_b,), (atom_a,))
        self.assertEqual(len(merged.atoms), 1)
        self.assertEqual(merged.atoms[0].quality.evidence_grade, "C")

    def test_conflicts_are_recorded_not_resolved(self) -> None:
        left = candidate_to_atom(
            record_to_candidate(
                {
                    "record_id": "c1",
                    "fields": {
                        "业态": "餐饮",
                        "经营模式": "直营",
                        "门店数": "1",
                        "这条属于": "方法",
                        "一件有效的事（或没用的事）": "晚八点群发对转化有效。",
                        "发现时间": "2026-08-01",
                        "现在还有效吗": "是",
                        "公司/品牌": "甲",
                    },
                },
                salt=SALT,
            ),
            (),
            (),
        )
        right = candidate_to_atom(
            record_to_candidate(
                {
                    "record_id": "c2",
                    "fields": {
                        "业态": "餐饮",
                        "经营模式": "直营",
                        "门店数": "1",
                        "这条属于": "方法",
                        "一件有效的事（或没用的事）": "晚八点群发对转化无效。",
                        "发现时间": "2026-08-02",
                        "现在还有效吗": "是",
                        "公司/品牌": "乙",
                    },
                },
                salt=SALT,
            ),
            (),
            (),
        )
        flagged = flag_conflicts(right, (left,))
        self.assertIn(left.id, flagged.lifecycle.contradicts)
        self.assertEqual(flagged.quality.evidence_grade, right.quality.evidence_grade)

    def test_gift_mentions_grade_and_optional_benchmark(self) -> None:
        atom = candidate_to_atom(
            record_to_candidate(
                {
                    "record_id": "g1",
                    "fields": {
                        "业态": "餐饮",
                        "经营模式": "加盟",
                        "门店数": "11-50",
                        "这条属于": "数字基线",
                        "一件有效的事（或没用的事）": "同规模加盟茶饮加微率需要带门店样本。",
                        "数字/证据": "加微率 12%→19%，n=37 店",
                        "发现时间": "2026-08-01",
                        "现在还有效吗": "是",
                        "公司/品牌": "丙",
                    },
                },
                salt=SALT,
            ),
            (),
            (),
        )
        text = render_gift(atom, "餐饮 × 11-50：n=1，中位数 19")
        self.assertIn("【同行案例卡】", text)
        self.assertIn(f"原子ID：{atom.id}", text)
        self.assertIn(f"署名：{ANON_LABEL}", text)
        self.assertEqual(text.splitlines()[2], f"署名：{ANON_LABEL}")
        self.assertEqual(
            text.splitlines()[3], f"同行都交了什么：{PUBLIC_DASHBOARD_URL}"
        )
        self.assertIn("类型：数字基线", text)
        self.assertIn("业态/模式/规模：餐饮 / 加盟 / 11-50", text)
        self.assertIn("证据等级：单源D级", text)
        self.assertIn("评审：待审，通过后进入下一版 skill", text)
        self.assertIn("平台规则风险：无", text)
        self.assertIn("想撤回，告诉发起人即可。", text)
        self.assertIn("餐饮 × 11-50", text)
        for code in (
            "benchmark",
            "catering",
            "franchise",
            "platform_workaround",
            "none",
            "low",
            "medium",
            "high",
            "direct",
            "mixed",
            "method",
        ):
            self.assertNotIn(code, text)

    def test_maintainer_id_marks_grade_a(self) -> None:
        candidate = record_to_candidate(
            {
                "record_id": "m1",
                "fields": {
                    "业态": "餐饮",
                    "经营模式": "直营",
                    "门店数": "1",
                    "这条属于": "方法",
                    "一件有效的事（或没用的事）": "维护者自己复盘的加微步骤。",
                    "发现时间": "2026-08-01",
                    "现在还有效吗": "是",
                    "公司/品牌": "马甲机构",
                    "联系方式": "m9224@163.com",
                },
            },
            salt=SALT,
        )
        atom = candidate_to_atom(candidate, (), {"m9224@163.com"})
        self.assertEqual(atom.quality.suggested_grade, "A")
        self.assertEqual(atom.quality.evidence_grade, "A")
        self.assertEqual(atom.quality.review_status, "pending")
        self.assertNotIn("m9224@163.com", atom.to_json())

    def test_self_confirmation_is_ignored(self) -> None:
        record = {
            "record_id": "rec_self",
            "fields": {
                "业态": "餐饮",
                "经营模式": "直营",
                "门店数": "1",
                "这条属于": "方法",
                "一件有效的事（或没用的事）": "自评不能把等级抬上去。",
                "发现时间": "2026-08-01",
                "现在还有效吗": "是",
                "公司/品牌": "江南茶社",
            },
        }
        confirmation = {
            "fields": {
                "关联提交": {"text": "自评", "record_id": "rec_self"},
                "印证人公司": "江南茶社有限公司",
                "印证时间": "2026-08-02",
            }
        }
        result = run_intake((record,), (confirmation,), salt=SALT)
        self.assertEqual(result.metrics["pending_total"], 1)
        self.assertEqual(result.metrics["approved_total"], 0)
        self.assertEqual(result.decisions[0].status, STATUS_PENDING)
        assert result.decisions[0].atom is not None
        self.assertEqual(result.decisions[0].atom.quality.suggested_grade, "D")

    def test_two_submissions_same_company_stay_d(self) -> None:
        statement = "同一家公司交两遍不能升 C。"
        first = {
            "record_id": "rec_same_a",
            "fields": {
                "业态": "餐饮",
                "经营模式": "直营",
                "门店数": "1",
                "这条属于": "方法",
                "一件有效的事（或没用的事）": statement,
                "发现时间": "2026-08-01",
                "现在还有效吗": "是",
                "公司/品牌": "江南茶社",
            },
        }
        second = {
            "record_id": "rec_same_b",
            "fields": {
                "业态": "餐饮",
                "经营模式": "直营",
                "门店数": "1",
                "这条属于": "方法",
                "一件有效的事（或没用的事）": statement,
                "发现时间": "2026-08-02",
                "现在还有效吗": "是",
                "公司/品牌": "江南茶社（上海）",
            },
        }
        result = run_intake((first, second), (), salt=SALT)
        self.assertEqual(result.metrics["approved_total"], 0)
        self.assertEqual(result.metrics["pending_total"], 2)
        self.assertEqual({item.status for item in result.decisions}, {STATUS_PENDING})
        assert result.atoms[0].quality.suggested_grade == "D"

    def test_confirmation_link_prefers_record_id(self) -> None:
        parsed = parse_confirmation_row(
            {
                "fields": {
                    "关联提交": {
                        "text": "江南茶社的投稿",
                        "record_id": "rec_s1",
                    },
                    "印证人公司": "西湖烘焙",
                    "印证时间": "2026-08-15",
                }
            },
            salt=SALT,
        )
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.link_record_id, "rec_s1")
        self.assertEqual(parsed.link_display, "江南茶社的投稿")
        self.assertTrue(parsed.confirmation.company_hash)
        self.assertEqual(
            _as_link({"text": "展示名", "record_id": "rec_bound"}),
            "rec_bound",
        )

    def test_reviewer_grade_is_authoritative(self) -> None:
        record = {
            "record_id": "rec_b",
            "fields": {
                "业态": "餐饮",
                "经营模式": "直营",
                "门店数": "1",
                "这条属于": "方法",
                "一件有效的事（或没用的事）": "评审员定 B，机器建议仍是 D。",
                "发现时间": "2026-08-01",
                "现在还有效吗": "是",
                "公司/品牌": "甲店",
                "评审结论": "通过",
                "评审等级": "B",
                "评审人": [{"name": "李四"}],
                "评审批注": "我核对过",
            },
        }
        result = run_intake((record,), (), salt=SALT)
        atom = result.decisions[0].atom
        assert atom is not None
        self.assertEqual(result.decisions[0].status, STATUS_APPROVED)
        self.assertEqual(atom.quality.evidence_grade, "B")
        self.assertEqual(atom.quality.suggested_grade, "D")
        self.assertEqual(atom.quality.reviewer, "李四")
        self.assertEqual(atom.quality.review_notes, "我核对过")
        self.assertIn("评审：已通过（B级）", result.decisions[0].gift)

    def test_bitable_ms_epoch_uses_shanghai(self) -> None:
        instant = datetime(2026, 8, 1, 0, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
        ms = int(instant.timestamp() * 1000)
        self.assertEqual(_as_text(ms), "2026-08-01")
        utc_date = datetime.fromtimestamp(ms / 1000, tz=ZoneInfo("UTC")).date().isoformat()
        self.assertEqual(utc_date, "2026-07-31")
        candidate = record_to_candidate(
            {
                "record_id": "rec_tz",
                "fields": {
                    "业态": "餐饮",
                    "经营模式": "直营",
                    "门店数": "1",
                    "这条属于": "平台技巧",
                    "一件有效的事（或没用的事）": "日期按上海时区取日历日。",
                    "发现时间": ms,
                    "现在还有效吗": "是",
                    "公司/品牌": "时区店",
                },
            },
            salt=SALT,
        )
        atom = candidate_to_atom(candidate, (), ())
        self.assertEqual(atom.source.observed_at, "2026-08-01")
        self.assertEqual(atom.lifecycle.valid_until, "2027-01-28")

    def test_still_valid_yes_uses_submission_date_not_observed(self) -> None:
        from siyu_team.knowledge.models import Confirmation

        candidate = record_to_candidate(
            {
                "record_id": "rec_live",
                "fields": {
                    "业态": "餐饮·快餐小吃",
                    "经营模式": "直营",
                    "门店数": "51-300",
                    "这条属于": "平台技巧",
                    "一件有效的事（或没用的事）": "企微防骚扰下把敏感词做成关键字自动应答。",
                    "发现时间": "2023-04-03",
                    "现在还有效吗": "是",
                    "公司/品牌": "南岸茶栈",
                    "创建时间": "2026-09-03T10:00:00+08:00",
                },
            },
            salt=SALT,
        )
        atom = candidate_to_atom(candidate, (), (), today=date(2026, 9, 3))
        self.assertEqual(atom.lifecycle.valid_from, "2023-04-03")
        self.assertEqual(atom.lifecycle.valid_until, "2027-03-02")
        gift = render_gift(atom)
        self.assertIn("类型：平台技巧", gift)
        self.assertIn("餐饮·快餐小吃", gift)
        self.assertIn("直营", gift)
        self.assertIn(f"原子ID：{atom.id}", gift)
        self.assertIn(f"署名：{ANON_LABEL}", gift)
        for code in (
            "platform_workaround",
            "catering",
            "direct",
            "none",
            "medium",
        ):
            self.assertNotIn(code, gift)

        unsure = record_to_candidate(
            {
                "record_id": "rec_unsure",
                "fields": {
                    "业态": "餐饮",
                    "经营模式": "直营",
                    "门店数": "1",
                    "这条属于": "规则变化",
                    "一件有效的事（或没用的事）": "规则是否还有效说不准。",
                    "发现时间": "2023-04-03",
                    "现在还有效吗": "不确定",
                    "公司/品牌": "北城面馆",
                    "创建时间": "2026-09-03",
                },
            },
            salt=SALT,
        )
        unsure_atom = candidate_to_atom(unsure, (), (), today=date(2026, 9, 3))
        self.assertEqual(unsure_atom.lifecycle.valid_until, "2026-10-03")

        expired = record_to_candidate(
            {
                "record_id": "rec_dead",
                "fields": {
                    "业态": "餐饮",
                    "经营模式": "直营",
                    "门店数": "1",
                    "这条属于": "平台技巧",
                    "一件有效的事（或没用的事）": "这招已经失效。",
                    "发现时间": "2023-04-03",
                    "现在还有效吗": "已失效",
                    "公司/品牌": "江东点心",
                    "创建时间": "2026-09-03",
                },
            },
            salt=SALT,
        )
        dead = candidate_to_atom(expired, (), (), today=date(2026, 9, 3))
        self.assertEqual(dead.lifecycle.valid_until, "2023-04-03")

        method = record_to_candidate(
            {
                "record_id": "rec_method",
                "fields": {
                    "业态": "餐饮",
                    "经营模式": "直营",
                    "门店数": "1",
                    "这条属于": "方法",
                    "一件有效的事（或没用的事）": "非窗口类型不写有效期。",
                    "发现时间": "2023-04-03",
                    "现在还有效吗": "是",
                    "公司/品牌": "巷口便利",
                    "创建时间": "2026-09-03",
                },
            },
            salt=SALT,
        )
        plain = candidate_to_atom(method, (), (), today=date(2026, 9, 3))
        self.assertEqual(plain.lifecycle.valid_until, "")

        confirmed = _with_confirmations(
            atom,
            (
                Confirmation(
                    contributor_hash="c" * 64,
                    company_hash="d" * 64,
                    confirmed_at="2026-09-10",
                ),
            ),
        )
        self.assertEqual(confirmed.lifecycle.valid_until, "2027-03-09")

    def test_writeback_skips_unchanged_fields(self) -> None:
        record = {
            "record_id": "rec_wb",
            "fields": {
                "状态": "已收录D",
                "原子ID": "ka_deadbeefdeadbee",
                "回礼": "【同行案例卡】",
            },
        }
        self.assertFalse(
            writeback_fields_changed(record, "已收录D", "ka_deadbeefdeadbee", "【同行案例卡】")
        )
        self.assertTrue(
            writeback_fields_changed(record, "已通过", "ka_deadbeefdeadbee", "【同行案例卡】")
        )

    def test_seed_confirmation_stays_in_dedupe_pool(self) -> None:
        from siyu_team.knowledge.models import KnowledgeAtomV2

        seed_path = ROOT / "knowledge/05-community/seeds.retail.jsonl"
        seed = KnowledgeAtomV2.from_json(seed_path.read_text(encoding="utf-8").splitlines()[0])
        record = {
            "record_id": "rec_seed",
            "fields": {
                "业态": "零售",
                "经营模式": "直营",
                "门店数": "2-10",
                "这条属于": "方法",
                "一件有效的事（或没用的事）": seed.statement,
                "发现时间": "2026-08-01",
                "现在还有效吗": "是",
                "公司/品牌": "巷口便利",
            },
        }
        result = run_intake((record,), (), (seed,), salt=SALT)
        self.assertIn(seed.id, {atom.id for atom in result.existing_updated} | {atom.id for atom in result.atoms})
        updated = next(
            atom
            for atom in (*result.existing_updated, *result.atoms)
            if atom.id == seed.id
        )
        self.assertGreaterEqual(len(updated.quality.confirmations), 1)
        self.assertEqual(updated.quality.evidence_grade, "D")

    def test_cellvalue_shapes_from_live_bitable(self) -> None:
        record = {
            "record_id": "rec_live",
            "fields": {
                "业态": ["餐饮"],
                "经营模式": ["直营"],
                "门店数": ["1"],
                "这条属于": ["方法"],
                "一件有效的事（或没用的事）": [
                    {"text": "飞书单元格既可能是片段也可能是纯文本。", "type": "text"}
                ],
                "发现时间": "2026-09-03T00:00:00.000+08:00",
                "现在还有效吗": ["是"],
                "公司/品牌": [{"text": "巷口便利", "type": "text"}],
            },
        }
        candidate = record_to_candidate(record, salt=SALT)
        self.assertEqual(candidate.industry, "catering")
        self.assertEqual(candidate.kind, "方法")
        self.assertEqual(candidate.observed_at[:10], "2026-09-03")
        atom = candidate_to_atom(candidate, (), ())
        self.assertEqual(atom.source.observed_at, "2026-09-03")
        self.assertIn("飞书单元格", atom.statement)
        parsed = parse_confirmation_row(
            {
                "fields": {
                    "关联提交": [{"id": "rec_live"}],
                    "印证人公司": [{"text": "北城面馆", "type": "text"}],
                    "印证时间": "2026-09-03T00:00:00.000+08:00",
                }
            },
            salt=SALT,
        )
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.link_record_id, "rec_live")
        self.assertEqual(parsed.confirmation.confirmed_at, "2026-09-03")
        result = run_intake((record,), (
            {
                "fields": {
                    "关联提交": [{"id": "rec_live"}],
                    "印证人公司": "北城面馆",
                    "印证时间": "2026-09-03T00:00:00.000+08:00",
                }
            },
        ), salt=SALT)
        self.assertEqual(result.metrics["pending_total"], 1)
        self.assertEqual(result.decisions[0].atom.quality.suggested_grade, "C")
        self.assertEqual(result.metrics["confirmations_unresolved"], 0)

    def test_confirmation_matches_pasted_atom_id(self) -> None:
        record = {
            "record_id": "rec_paste",
            "fields": {
                "业态": "餐饮",
                "经营模式": "直营",
                "门店数": "1",
                "这条属于": "方法",
                "一件有效的事（或没用的事）": "印证人只贴原子ID也能对上。",
                "发现时间": "2026-08-01",
                "现在还有效吗": "是",
                "公司/品牌": "甲店",
            },
        }
        atom = candidate_to_atom(record_to_candidate(record, salt=SALT), (), ())
        raw_id = atom.id.removeprefix("ka_").upper()
        result = run_intake(
            (record,),
            (
                {
                    "fields": {
                        "关联提交": None,
                        "印证的原子ID": f"  {raw_id}  ",
                        "印证人公司": "乙店",
                        "印证时间": "2026-08-02",
                    }
                },
            ),
            salt=SALT,
        )
        self.assertEqual(result.metrics["pending_total"], 1)
        assert result.decisions[0].atom is not None
        self.assertEqual(result.decisions[0].atom.quality.suggested_grade, "C")
        self.assertEqual(result.metrics["confirmations_unresolved"], 0)
        parsed = parse_confirmation_row(
            {
                "fields": {
                    "关联提交": None,
                    "印证的原子ID": f"  {raw_id}  ",
                    "印证人公司": "乙店",
                }
            },
            salt=SALT,
        )
        assert parsed is not None
        target = resolve_confirmation_target(
            parsed,
            atom_ids={atom.id},
            locator_to_atom={},
            record_to_atom={},
        )
        self.assertEqual(target, atom.id)

    def test_form_v151_industry_scale_and_wuwen_mappings(self) -> None:
        self.assertEqual(map_industry("餐饮", "火锅"), ("catering", "火锅"))
        self.assertEqual(map_industry("零售", ""), ("retail", ""))
        self.assertEqual(map_industry("其他", "医美"), ("other", "其他 · 医美"))
        self.assertEqual(map_industry("餐饮·正餐", ""), ("catering", "餐饮·正餐"))
        self.assertEqual(
            map_industry("餐饮·正餐", "川菜"), ("catering", "餐饮·正餐 · 川菜")
        )
        self.assertEqual(map_industry("咖啡茶饮", ""), ("catering", "咖啡茶饮"))
        self.assertEqual(map_industry("烘焙甜品", "蛋糕"), ("catering", "烘焙甜品 · 蛋糕"))
        self.assertEqual(map_industry("零售·便利店", ""), ("retail", "零售·便利店"))
        self.assertEqual(map_industry("零售·母婴宠物", "猫粮"), ("retail", "零售·母婴宠物 · 猫粮"))
        self.assertEqual(map_scale_band("5000+"), "5000+")
        self.assertEqual(map_scale_band("301-1000"), "301-1000")
        self.assertEqual(map_scale_band("1001-5000"), "1001-5000")
        self.assertEqual(map_scale_band("300+"), "any")
        self.assertEqual(map_org_layers("有"), "regional")
        self.assertEqual(map_org_layers("没有"), "none")
        self.assertEqual(map_org_layers("不清楚"), "any")
        self.assertEqual(map_contributor_role("总部"), "hq")
        self.assertEqual(map_contributor_role("分公司或区域"), "regional")
        self.assertEqual(map_contributor_role("加盟商"), "franchisee")
        self.assertEqual(map_contributor_role("门店"), "store")
        self.assertEqual(map_contributor_role("服务商或顾问"), "vendor_or_consultant")
        self.assertEqual(map_contributor_role(""), "unknown")
        self.assertEqual(
            map_channels(["企业微信", "小程序会员", "小红书"]),
            ("wecom", "miniprogram_member", "xiaohongshu"),
        )
        record = {
            "record_id": "rec_wuwen",
            "fields": {
                "业态": ["零售·商超生鲜"],
                "经营模式": ["直营"],
                "门店数": ["1001-5000"],
                "分公司层": ["没有"],
                "你的位置": ["加盟商"],
                "主要私域载体": ["个人微信", "微信社群"],
                "这条属于": ["方法"],
                "一件有效的事（或没用的事）": "生鲜到家的群只发当天能履约的品。",
                "发现时间": "2026-08-01",
                "现在还有效吗": ["是"],
                "公司/品牌": "田间市集",
            },
        }
        candidate = record_to_candidate(record, salt=SALT)
        self.assertEqual(candidate.industry, "retail")
        self.assertEqual(candidate.subindustry, "零售·商超生鲜")
        self.assertEqual(candidate.scale_band, "1001-5000")
        self.assertEqual(candidate.org_layers, "none")
        self.assertEqual(candidate.contributor_role, "franchisee")
        self.assertEqual(candidate.channels, ("personal_wechat", "wechat_group"))
        atom = candidate_to_atom(candidate, (), ())
        self.assertEqual(atom.scope.industry, "retail")
        self.assertEqual(atom.scope.scale_band, ("1001-5000",))
        self.assertEqual(atom.scope.org_layers, "none")
        self.assertEqual(atom.source.contributor_role, "franchisee")
        self.assertEqual(atom.source.contributor_display_name, "")
        self.assertEqual(atom.scope.channels, ("personal_wechat", "wechat_group"))

    def test_unresolved_confirmation_is_counted_not_raised(self) -> None:
        record = {
            "record_id": "rec_ok",
            "fields": {
                "业态": "餐饮",
                "经营模式": "直营",
                "门店数": "1",
                "这条属于": "方法",
                "一件有效的事（或没用的事）": "对不上的印证不能把管线打崩。",
                "发现时间": "2026-08-01",
                "现在还有效吗": "是",
                "公司/品牌": "甲店",
            },
        }
        result = run_intake(
            (record,),
            (
                {
                    "fields": {
                        "关联提交": None,
                        "印证的原子ID": "不是一个原子",
                        "印证人公司": "乙店",
                    }
                },
                {
                    "fields": {
                        "关联提交": None,
                        "印证的原子ID": "",
                        "印证人公司": "",
                    }
                },
            ),
            salt=SALT,
        )
        self.assertEqual(result.metrics["confirmations_unresolved"], 2)
        self.assertEqual(result.metrics["pending_total"], 1)
        self.assertEqual(result.decisions[0].status, STATUS_PENDING)

    def test_fixture_lenient_redacts_pii_and_accepts_unknown_kind(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        result = run_intake(
            payload["submissions"],
            payload["confirmations"],
            salt=SALT,
            mode=MODE_LENIENT,
        )
        statuses = {item.record_id: item.status for item in result.decisions}
        self.assertEqual(result.metrics["needs_manual"], 0)
        self.assertEqual(statuses["rec_s4"], STATUS_PENDING)
        self.assertEqual(statuses["rec_s5"], STATUS_PENDING)
        self.assertEqual(statuses["rec_s6"], STATUS_PENDING)
        pii = next(item.atom for item in result.decisions if item.record_id == "rec_s4")
        assert pii is not None
        self.assertNotIn("13800138000", pii.statement)
        self.assertIn("1**********", pii.statement)
        self.assertIn(NOTE_PII_REDACTED, pii.quality.review_notes)
        unknown = next(item.atom for item in result.decisions if item.record_id == "rec_s5")
        assert unknown is not None
        self.assertEqual(unknown.type, "method")
        self.assertIn(NOTE_UNKNOWN_KIND, unknown.quality.review_notes)
        dated = next(item.atom for item in result.decisions if item.record_id == "rec_s6")
        assert dated is not None
        self.assertEqual(dated.source.observed_at, "2026-09-02")

    def test_revoke_status_removes_atom_and_blocks_reingest(self) -> None:
        record = {
            "record_id": "rec_keep",
            "fields": {
                "业态": "餐饮",
                "经营模式": "直营",
                "门店数": "1",
                "这条属于": "方法",
                "一件有效的事（或没用的事）": "这条先入库再撤销。",
                "发现时间": "2026-08-01",
                "现在还有效吗": "是",
                "公司/品牌": "甲店",
            },
        }
        first = run_intake((record,), (), salt=SALT, mode=MODE_LENIENT)
        atom = first.decisions[0].atom
        assert atom is not None
        revoked_record = {
            "record_id": "rec_keep",
            "fields": {
                **record["fields"],
                "状态": "撤销",
                "原子ID": atom.id,
            },
        }
        second = run_intake(
            (revoked_record,),
            (),
            (atom,),
            salt=SALT,
            mode=MODE_LENIENT,
        )
        self.assertEqual(second.decisions[0].status, STATUS_REVOKED)
        self.assertEqual(second.decisions[0].gift, "已撤销")
        self.assertEqual(second.atoms, ())
        self.assertEqual(second.revoked[0].id, atom.id)
        self.assertEqual(second.revoked[0].reason, "feishu_status")
        edited = {
            "record_id": "rec_keep",
            "fields": {
                **record["fields"],
                "一件有效的事（或没用的事）": "改过正文也不该再入库。",
                "状态": "已收录D",
            },
        }
        third = run_intake(
            (edited,),
            (
                {
                    "fields": {
                        "关联提交": None,
                        "印证的原子ID": atom.id,
                        "印证人公司": "乙店",
                        "印证时间": "2026-08-02",
                    }
                },
            ),
            (atom,),
            salt=SALT,
            mode=MODE_LENIENT,
            revoked_ids=(atom.id,),
            revoked_record_ids=("rec_keep",),
        )
        self.assertEqual(third.decisions[0].status, STATUS_REVOKED)
        self.assertEqual(third.atoms, ())
        self.assertEqual(third.metrics["confirmations_unresolved"], 0)
        self.assertEqual(third.metrics["approved_total"], 0)

    def test_display_name_maps_and_stays_unhashed(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        s1 = next(item for item in payload["submissions"] if item["record_id"] == "rec_s1")
        candidate = record_to_candidate(s1, salt=SALT)
        self.assertEqual(candidate.contributor_display_name, "江南茶社小林")
        atom = candidate_to_atom(candidate, (), ())
        self.assertEqual(atom.source.contributor_display_name, "江南茶社小林")
        self.assertEqual(atom.quality.confirmations[0].display_name, "江南茶社小林")
        dumped = atom.to_json()
        self.assertIn("江南茶社小林", dumped)
        self.assertNotIn(hash_identity("江南茶社小林", SALT), dumped)
        gift = render_gift(atom)
        self.assertIn("署名：江南茶社小林", gift)
        self.assertNotIn(atom.quality.confirmations[0].company_hash, gift)

    def test_display_name_pii_lenient_becomes_anonymous(self) -> None:
        record = {
            "record_id": "rec_dn_phone",
            "fields": {
                "业态": "餐饮",
                "经营模式": "直营",
                "门店数": "1",
                "这条属于": "方法",
                "一件有效的事（或没用的事）": "显示名写成手机号时宽松应收录为匿名。",
                "发现时间": "2026-08-01",
                "现在还有效吗": "是",
                "公司/品牌": "甲店",
                "对外显示名": "13800138000",
            },
        }
        result = run_intake((record,), (), salt=SALT, mode=MODE_LENIENT)
        self.assertEqual(result.decisions[0].status, STATUS_PENDING)
        atom = result.decisions[0].atom
        assert atom is not None
        self.assertEqual(atom.source.contributor_display_name, "")
        self.assertEqual(atom.quality.confirmations[0].display_name, "")
        self.assertIn(NOTE_PII_DISPLAY_NAME, atom.quality.review_notes)
        self.assertNotIn("13800138000", atom.to_json())
        self.assertIn(f"署名：{ANON_LABEL}", render_gift(atom))

        email = {
            "record_id": "rec_dn_email",
            "fields": {
                **record["fields"],
                "一件有效的事（或没用的事）": "显示名写成邮箱时宽松也应匿名。",
                "对外显示名": "xiaolin@example.com",
            },
        }
        emailed = run_intake((email,), (), salt=SALT, mode=MODE_LENIENT)
        emailed_atom = emailed.decisions[0].atom
        assert emailed_atom is not None
        self.assertEqual(emailed.decisions[0].status, STATUS_PENDING)
        self.assertEqual(emailed_atom.source.contributor_display_name, "")
        self.assertIn(NOTE_PII_DISPLAY_NAME, emailed_atom.quality.review_notes)
        self.assertNotIn("xiaolin@example.com", emailed_atom.to_json())

    def test_display_name_pii_strict_needs_manual(self) -> None:
        record = {
            "record_id": "rec_dn_strict",
            "fields": {
                "业态": "餐饮",
                "经营模式": "直营",
                "门店数": "1",
                "这条属于": "方法",
                "一件有效的事（或没用的事）": "显示名写成手机号时严格需人工。",
                "发现时间": "2026-08-01",
                "现在还有效吗": "是",
                "公司/品牌": "甲店",
                "对外显示名": "13800138000",
            },
        }
        result = run_intake((record,), (), salt=SALT, mode=MODE_STRICT)
        self.assertEqual(result.decisions[0].status, STATUS_MANUAL)
        self.assertIsNone(result.decisions[0].atom)
        emailed = run_intake(
            (
                {
                    "record_id": "rec_dn_strict_email",
                    "fields": {
                        **record["fields"],
                        "对外显示名": "xiaolin@example.com",
                    },
                },
            ),
            (),
            salt=SALT,
            mode=MODE_STRICT,
        )
        self.assertEqual(emailed.decisions[0].status, STATUS_MANUAL)
        self.assertIsNone(emailed.decisions[0].atom)

    def test_confirmation_display_name_pii_is_anonymized_not_dropped(self) -> None:
        parsed = parse_confirmation_row(
            {
                "fields": {
                    "印证的原子ID": "ka_abcd1234abcd1234",
                    "印证人公司": "西湖烘焙",
                    "印证时间": "2026-08-15",
                    "对外显示名": "13800138000",
                }
            },
            salt=SALT,
        )
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.confirmation.display_name, "")
        self.assertTrue(parsed.confirmation.company_hash)
        named = parse_confirmation_row(
            {
                "fields": {
                    "印证的原子ID": "ka_abcd1234abcd1234",
                    "印证人公司": "西湖烘焙",
                    "印证时间": "2026-08-15",
                    "对外显示名": "路人甲",
                }
            },
            salt=SALT,
        )
        assert named is not None
        self.assertEqual(named.confirmation.display_name, "路人甲")

    def test_review_pass_moves_pending_to_approved_without_duplicate(self) -> None:
        fields = {
            "业态": "餐饮",
            "经营模式": "直营",
            "门店数": "1",
            "这条属于": "方法",
            "一件有效的事（或没用的事）": "评审通过后同一原子只出现一次。",
            "发现时间": "2026-08-01",
            "现在还有效吗": "是",
            "公司/品牌": "甲店",
        }
        first = run_intake(({"record_id": "rec_gate", "fields": fields},), (), salt=SALT)
        self.assertEqual(first.decisions[0].status, STATUS_PENDING)
        self.assertEqual(len(first.atoms), 1)
        atom_id = first.atoms[0].id
        passed = {
            "record_id": "rec_gate",
            "fields": {
                **fields,
                "评审结论": "通过",
                "评审等级": "C",
                "评审人": "评审员",
            },
        }
        second = run_intake((passed,), (), first.atoms, salt=SALT)
        self.assertEqual(second.decisions[0].status, STATUS_APPROVED)
        self.assertEqual(len(second.atoms), 1)
        self.assertEqual(second.atoms[0].id, atom_id)
        self.assertEqual(second.atoms[0].quality.evidence_grade, "C")
        self.assertEqual(second.atoms[0].quality.review_status, "approved")
        self.assertEqual(second.atoms[0].quality.reviewer, "评审员")

    def test_review_reject_after_pass_blocks_reingest_until_reopened(self) -> None:
        fields = {
            "业态": "餐饮",
            "经营模式": "直营",
            "门店数": "1",
            "这条属于": "方法",
            "一件有效的事（或没用的事）": "通过之后改驳回要出库且不再重收。",
            "发现时间": "2026-08-01",
            "现在还有效吗": "是",
            "公司/品牌": "甲店",
            "评审结论": "通过",
            "评审等级": "B",
        }
        first = run_intake(({"record_id": "rec_flip", "fields": fields},), (), salt=SALT)
        self.assertEqual(first.decisions[0].status, STATUS_APPROVED)
        atom_id = first.atoms[0].id
        rejected_record = {
            "record_id": "rec_flip",
            "fields": {**fields, "评审结论": "驳回", "评审批注": "数字对不上"},
        }
        second = run_intake((rejected_record,), (), first.atoms, salt=SALT)
        self.assertEqual(second.decisions[0].status, STATUS_REJECTED_REVIEW)
        self.assertEqual(second.atoms, ())
        self.assertEqual(len(second.rejected), 1)
        self.assertEqual(second.rejected[0].id, atom_id)
        self.assertEqual(second.rejected[0].reason, "数字对不上")
        third = run_intake(
            (rejected_record,),
            (),
            first.atoms,
            salt=SALT,
            rejected_ids=(atom_id,),
            rejected_record_ids=("rec_flip",),
        )
        self.assertEqual(third.decisions[0].status, STATUS_REJECTED_REVIEW)
        self.assertEqual(third.atoms, ())
        reopened = {
            "record_id": "rec_flip",
            "fields": {**fields, "评审结论": "通过", "评审等级": "D"},
        }
        fourth = run_intake(
            (reopened,),
            (),
            (),
            salt=SALT,
            rejected_ids=(atom_id,),
            rejected_record_ids=("rec_flip",),
        )
        self.assertEqual(fourth.decisions[0].status, STATUS_APPROVED)
        self.assertEqual(fourth.atoms[0].id, atom_id)
        self.assertIn(atom_id, fourth.reopened)


if __name__ == "__main__":
    unittest.main()
