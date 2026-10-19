"""Check that restaurant questions reach reviewed, conditional rehearsal knowledge."""
import unittest

from siyu_team.runtime import SiyuRuntime


class RehearsalKnowledgeTests(unittest.TestCase):
    def test_real_questions_select_new_knowledge(self):
        cases = (
            ('火锅餐饮店饭后结账，桌贴应该写本单还是下次优惠', 'L1-21'),
            ('餐饮店排队很长，直接进群还是先加好友', 'L1-22'),
            ('餐饮加盟店没有动作，优惠谁出钱，低执行门店怎么跟进', 'L1-23'),
            ('餐饮群发昵称太长，消息折叠，顾客看不到利益点', 'L1-24'),
            ('餐饮店每天菜单变化，素材谁做谁发谁接', 'L1-25'),
            ('餐饮活动明天推送，部分门店缺货，谁来撤停', 'L1-26'),
            ('餐饮会员等级和召回分层有什么区别，不能统一14天吧', 'L1-27'),
            ('餐饮召回方案店员从有空变没空，不加人不换系统不加预算', 'L1-28'),
        )
        runtime = SiyuRuntime()
        for question, expected in cases:
            with self.subTest(question=question):
                plan = runtime.plan(question, trace=False).to_dict()
                self.assertFalse(plan['decision']['needs_clarification'])
                atoms = {a['locator']: a for a in plan['knowledge']['atoms']}
                self.assertIn(expected, atoms)
                atom = atoms[expected]
                self.assertEqual(atom['source']['observed_at'], '2026-10-19')
                self.assertTrue(atom['applicability']['counterexamples'])
                self.assertTrue(atom['applicability']['preconditions'])

    def test_operating_choices_do_not_override_explicit_tasks(self):
        cases = (
            ('餐饮桌贴写本单优惠，帮我写一条朋友圈', 'siyu-pyq'),
            ('餐饮会员等级和召回分层一直不合理，帮我写SQL计算人群', 'majia-huiyuan'),
            ('活动缺货，帮我重写新推送', 'siyu-qunfa'),
            ('把这次素材谁做谁发谁接的结论保存下来', 'siyu-save'),
        )
        for question, expected in cases:
            with self.subTest(question=question):
                decision = SiyuRuntime().plan(question, trace=False).to_dict()['decision']
                self.assertEqual(decision['skill'], expected)
                self.assertFalse(decision['needs_clarification'])

    def test_unknown_industry_does_not_receive_restaurant_assumptions(self):
        plan = SiyuRuntime().plan('店员没空，不加人不换系统，怎么改召回方案', trace=False).to_dict()
        self.assertFalse(any(a['locator'] in {f'L1-{i}' for i in range(21, 29)}
                             for a in plan['knowledge']['atoms']))


if __name__ == '__main__':
    unittest.main()
