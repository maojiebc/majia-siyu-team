from __future__ import annotations

import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
import tempfile
import unittest

from tools.ab_eval import blind
from tools.review_page.build import embed


class ScriptCounter(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.scripts = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag == "script":
            self.scripts += 1


class BlindEvalSafetyTests(unittest.TestCase):
    def test_untrusted_answers_cannot_end_json_script(self) -> None:
        value = {"answer": '</ScRiPt><script>alert("test")</script><!-- 中文'}
        encoded = embed(value)
        parser = ScriptCounter()
        parser.feed(f'<script type="application/json">{encoded}</script>')
        self.assertEqual(parser.scripts, 1)
        self.assertEqual(json.loads(encoded), value)

    def test_rerun_preserves_packet_key_and_previous_reviews(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, content in {
                "questions": [{"id": "q1", "request": "问题"}],
                "one": [{"id": "q1", "answer": "回答一"}],
                "two": [{"id": "q1", "answer": "回答二"}],
            }.items():
                (root / f"{name}.json").write_text(json.dumps(content))
            out = root / "run"
            args = argparse.Namespace(
                questions=str(root / "questions.json"),
                answers=[f"{name}={root / (name + '.json')}" for name in ("one", "two")],
                seed=1,
                out=str(out),
            )
            self.assertEqual(blind(args), 0)
            (out / "human").mkdir()
            (out / "human/review.json").write_text('[{"old": true}]')
            before = {p.relative_to(out): p.read_bytes() for p in out.rglob('*') if p.is_file()}
            args.seed = 2
            with self.assertRaisesRegex(SystemExit, "新目录或空目录"):
                blind(args)
            after = {p.relative_to(out): p.read_bytes() for p in out.rglob('*') if p.is_file()}
            self.assertEqual(after, before)
            args.out = str(root / "empty")
            Path(args.out).mkdir()
            self.assertEqual(blind(args), 0)
