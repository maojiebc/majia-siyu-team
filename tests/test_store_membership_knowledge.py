"""Real entry-point checks for the distilled store scenarios (not business lift)."""
import unittest

from siyu_team.runtime import SiyuRuntime

SCENARIOS = (
    ("餐饮店收银话术怎么说，新客老客怎么区分", "L1-03"),
    ("餐饮店欢迎语怎么写，顾客领礼后怎么进群", "L1-04"),
    ("餐饮新店开业活动怎么安排", "L1-15"),
    ("餐饮店核销失败，顾客有券用不了", "L1-16"),
    ("餐饮加盟店收银员不推会员，员工激励怎么落地", "L1-17"),
    ("餐饮店核销下降，店长每天该查什么问题", "L1-18"),
)


class StoreMembershipKnowledgeTests(unittest.TestCase):
    def test_normal_entry_selects_concrete_store_knowledge(self):
        runtime = SiyuRuntime()
        for question, expected in SCENARIOS:
            with self.subTest(question=question):
                plan = runtime.plan(question, trace=False).to_dict()
                atoms = plan["knowledge"]["atoms"]
                matching = [a for a in atoms if a["locator"] == expected]
                self.assertTrue(matching, (plan["decision"]["skill"], [a["locator"] for a in atoms]))
                atom = matching[0]
                self.assertTrue(atom["applicability"]["preconditions"])
                self.assertTrue(atom["applicability"]["counterexamples"])
                self.assertIn("Codex", atom["quality"]["reviewer"])
                self.assertEqual(atom["source"]["observed_at"], "2026-09-14")

    def test_membership_calculation_still_goes_to_sister_project(self):
        p = SiyuRuntime().plan("餐饮门店新增会员的去重口径怎么算", trace=False).to_dict()
        self.assertEqual(p["decision"]["skill"], "majia-huiyuan")
        self.assertEqual(p["knowledge"]["atoms"], [])

    def test_store_content_not_selected_for_unknown_industry(self):
        p = SiyuRuntime().plan("核销失败，顾客有券用不了", trace=False).to_dict()
        self.assertNotIn("L1-16", [a["locator"] for a in p["knowledge"]["atoms"]])


if __name__ == "__main__":
    unittest.main()
