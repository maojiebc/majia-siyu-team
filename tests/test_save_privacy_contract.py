from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SAVE_SKILL = ROOT / "plugins" / "siyu-core" / "skills" / "siyu-save" / "SKILL.md"


class SavePrivacyContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = SAVE_SKILL.read_text(encoding="utf-8")

    def test_patch_keeps_version_unchanged(self) -> None:
        self.assertIn('version: "1.4.1"', self.text)
        self.assertNotIn('version: "1.4.2"', self.text)

    def test_default_scope_is_structured_conclusions_not_full_chat(self) -> None:
        self.assertIn("默认只保存结构化结论，不复制完整对话", self.text)
        self.assertIn("完整对话、逐字稿和整段原始用户输入", self.text)
        self.assertIn("content_scope: structured_conclusions", self.text)

    def test_sensitive_preview_happens_before_any_write_or_directory(self) -> None:
        preview = self.text.index("敏感信息预览（写盘前）")
        choice = self.text.index("等待用户选择")
        path = self.text.index("生成路径", choice)
        write = self.text.index("写入固定格式", path)
        self.assertLess(preview, choice)
        self.assertLess(choice, path)
        self.assertLess(path, write)
        self.assertIn("在任何写盘之前，先向用户显示", self.text)
        self.assertIn("还不创建目录或文件", self.text)

    def test_preview_is_minimized_and_never_echoes_credentials(self) -> None:
        for category in (
            "手机号",
            "身份证号",
            "邮箱",
            "微信号",
            "精确经营数字",
            "token",
            "API key",
            "密码",
            "cookie",
        ):
            with self.subTest(category=category):
                self.assertIn(category, self.text)
        self.assertIn("「[凭据，已隐藏]」", self.text)
        self.assertIn("不得在预览中重复完整值", self.text)
        self.assertIn("未发现常见敏感信息，不代表绝对安全", self.text)

    def test_user_must_choose_redacted_original_or_cancel(self) -> None:
        self.assertIn("1. 脱敏后保存（推荐）", self.text)
        self.assertIn("2. 原文保存", self.text)
        self.assertIn("3. 取消", self.text)
        self.assertIn(
            "未收到明确选择时，不得写入、创建目录或视为默认同意",
            self.text,
        )
        self.assertIn("「原文」不代表改为保存完整对话", self.text)
        self.assertIn("不创建任何文件或目录", self.text)
        self.assertIn("已取消存档", self.text)

    def test_saved_record_carries_privacy_audit_metadata(self) -> None:
        self.assertIn("privacy_mode: {redacted | original}", self.text)
        self.assertIn("sensitive_categories:", self.text)
        self.assertIn("privacy_mode` 必须与用户选择一致", self.text)
        self.assertIn("不粘贴完整对话", self.text)

    def test_plaintext_and_distribution_boundaries_are_explicit(self) -> None:
        self.assertIn("`~/.siyu/` 是未加密纯文本", self.text)
        self.assertIn("不自动上传、分享或写入仓库", self.text)
        self.assertIn("操作系统备份、云盘或其他同步工具", self.text)
        self.assertIn("敏感扫描是尽力而为的辅助", self.text)
        self.assertIn("`list` 模式只读", self.text)


if __name__ == "__main__":
    unittest.main()
