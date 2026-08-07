"""host.py 提示词加载与守卫。"""
from __future__ import annotations

import unittest

from siyu_team.host import HOST_PROMPT, build_host_prompt, load_host_prompt


class HostPromptTests(unittest.TestCase):
    def test_load_external_or_builtin(self) -> None:
        text = load_host_prompt()
        self.assertIn("{question}", text)
        self.assertIn("{officers}", text)
        self.assertIn("团长拍板", text)

    def test_build_requires_two_officers(self) -> None:
        with self.assertRaises(ValueError):
            build_host_prompt("议题", [{"name": "合规官", "engine": "t", "content": "x"}])

    def test_build_renders_officers(self) -> None:
        prompt = build_host_prompt(
            "要不要上裂变",
            [
                {"name": "合规官", "engine": "a", "content": "红线"},
                {"name": "广告官", "engine": "b", "content": "可测"},
            ],
            success_criteria="不封号",
            constraints="本周内",
        )
        self.assertIn("要不要上裂变", prompt)
        self.assertIn("合规官", prompt)
        self.assertIn("广告官", prompt)
        self.assertIn("不封号", prompt)

    def test_builtin_fallback_shape(self) -> None:
        self.assertIn("<task>", HOST_PROMPT)
        self.assertIn("{officers}", HOST_PROMPT)


if __name__ == "__main__":
    unittest.main()
