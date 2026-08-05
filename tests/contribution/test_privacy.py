from __future__ import annotations

import unittest

from siyu_team.contribution.privacy import scan_fields


class ContributionPrivacyTests(unittest.TestCase):
    def test_pii_credentials_and_store_ids_block_submission(self) -> None:
        cases = (
            "联系 13800138000",
            "身份证 11010119900307817X",
            "邮箱 user@example.com",
            "api_key=sk-live-secretvalue",
            "门店编号 ZL-001",
        )
        for text in cases:
            with self.subTest(text=text):
                scan = scan_fields((("fact", text),))
                self.assertFalse(scan.safe)
                self.assertEqual(scan.affected_fields, ("fact",))

    def test_business_metrics_warn_but_do_not_auto_block(self) -> None:
        scan = scan_fields((("result", "活动后毛利率 35%，需要确认授权。"),))
        self.assertTrue(scan.safe)
        self.assertTrue(scan.warnings)

    def test_normal_operational_fact_is_safe(self) -> None:
        scan = scan_fields((("fact", "高峰期把四步操作压缩成一步后执行更稳定。"),))
        self.assertTrue(scan.safe)
        self.assertEqual(scan.findings, ())


if __name__ == "__main__":
    unittest.main()
