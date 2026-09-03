from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest

from siyu_team.contribution.intake import (
    ANON_LABEL,
    candidate_to_atom,
    hash_identity,
    record_to_candidate,
)
from siyu_team.knowledge.models import Confirmation, KnowledgeAtomV2


ROOT = Path(__file__).resolve().parents[1]
SALT = "test-salt"


def _load_renderer():
    path = ROOT / "tools/render_contributors.py"
    spec = importlib.util.spec_from_file_location("siyu_render_contributors", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _atom(
    record_id: str,
    statement: str,
    company: str,
    *,
    name: str = "",
    extra: tuple[Confirmation, ...] = (),
) -> KnowledgeAtomV2:
    fields = {
        "业态": "餐饮",
        "经营模式": "直营",
        "门店数": "1",
        "这条属于": "方法",
        "一件有效的事（或没用的事）": statement,
        "发现时间": "2026-08-01",
        "现在还有效吗": "是",
        "公司/品牌": company,
    }
    if name:
        fields["对外显示名"] = name
    return candidate_to_atom(
        record_to_candidate({"record_id": record_id, "fields": fields}, salt=SALT),
        extra,
        (),
    )


def _confirm(company: str, person: str, when: str, name: str = "") -> Confirmation:
    return Confirmation(
        contributor_hash=hash_identity(person, SALT),
        company_hash=hash_identity(company, SALT),
        confirmed_at=when,
        display_name=name,
    )


class RenderContributorsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = _load_renderer()

    def test_named_sort_anonymous_aggregate_and_no_company_leak(self) -> None:
        named_c = _atom(
            "rec_named",
            "署名作者的一条被另一家印证。",
            "江南茶社",
            name="江南茶社小林",
            extra=(_confirm("北城面馆", "北城店员", "2026-08-20", "路人"),),
        )
        named_c_payload = named_c.to_dict()
        named_c_payload["quality"]["review_status"] = "approved"
        named_c_payload["quality"]["evidence_grade"] = "C"
        named_c_payload["quality"]["reviewer"] = "maintainer"
        named_c_payload["quality"]["reviewed_at"] = "2026-08-20"
        named_c = KnowledgeAtomV2.from_dict(named_c_payload)
        named_d = _atom(
            "rec_named2",
            "同一署名的第二条仍算这个人。",
            "江南茶社",
            name="江南茶社小林",
        )
        anon_one = _atom("rec_anon1", "匿名作者甲的方法。", "巷口便利")
        anon_two = _atom("rec_anon2", "匿名作者乙的方法。", "江东点心")
        text = self.mod.render_markdown([named_c, named_d, anon_one, anon_two])
        self.assertIn("# 贡献者", text)
        self.assertIn(
            "每条经验背后都是一个真的踩过坑或验过招的同行，按提交条数排序，不显示公司名",
            text,
        )
        self.assertIn(
            "江南茶社小林 · 通过 1（A 0 / B 0 / C 1 / D 0）· 待审 1 · 印证 1",
            text,
        )
        self.assertIn(f"{ANON_LABEL} · 2 位 · 通过 0 · 待审 2", text)
        self.assertNotIn("company_hash", text)
        self.assertNotIn(named_c.quality.confirmations[0].company_hash, text)
        self.assertNotIn(named_c.quality.confirmations[0].contributor_hash, text)
        self.assertNotIn("巷口便利", text)
        self.assertNotIn("北城面馆", text)
        named_line = next(
            line for line in text.splitlines() if line.startswith("江南茶社小林")
        )
        anon_line = next(line for line in text.splitlines() if line.startswith(ANON_LABEL))
        self.assertLess(text.index(named_line), text.index(anon_line))

    def test_empty_wall_is_stable(self) -> None:
        first = self.mod.render_markdown([])
        second = self.mod.render_markdown([])
        self.assertEqual(first, second)
        self.assertIn("目前还没有公开署名的社区投稿。", first)
        self.assertNotIn(f"{ANON_LABEL} ·", first)

    def test_seeds_excluded_and_write_is_idempotent(self) -> None:
        named = _atom("rec_wall", "贡献者墙要排除种子。", "甲店", name="小林")
        seed = _atom("rec_seed", "种子不该上墙。", "乙店")
        seed = KnowledgeAtomV2.from_dict(
            {
                **seed.to_dict(),
                "source": {**seed.to_dict()["source"], "source_type": "seed"},
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            community = root / "05-community"
            community.mkdir()
            (community / "pending.jsonl").write_text(
                named.to_json() + "\n", encoding="utf-8"
            )
            (community / "seeds.retail.jsonl").write_text(
                seed.to_json() + "\n", encoding="utf-8"
            )
            path = self.mod.render_contributors(root)
            first = path.read_bytes()
            self.assertIn(
                "小林 · 通过 0（A 0 / B 0 / C 0 / D 0）· 待审 1 · 印证 0".encode("utf-8"),
                first,
            )
            self.assertNotIn("种子不该上墙".encode("utf-8"), first)
            self.assertNotIn(ANON_LABEL.encode("utf-8"), first)
            self.mod.render_contributors(root)
            self.assertEqual(path.read_bytes(), first)

    def test_b_grade_counts_with_a(self) -> None:
        atom = _atom("rec_b", "维护者手改的B级仍算A档。", "丙店", name="维护者")
        payload = atom.to_dict()
        payload["quality"]["evidence_grade"] = "B"
        payload["quality"]["review_status"] = "approved"
        payload["quality"]["reviewer"] = "maintainer"
        payload["quality"]["reviewed_at"] = "2026-08-01"
        text = self.mod.render_markdown([KnowledgeAtomV2.from_dict(payload)])
        self.assertIn(
            "维护者 · 通过 1（A 0 / B 1 / C 0 / D 0）· 待审 0 · 印证 0",
            text,
        )


if __name__ == "__main__":
    unittest.main()
