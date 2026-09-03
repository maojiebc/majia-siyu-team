from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def _load_render():
    path = ROOT / "tools/render_benchmarks.py"
    spec = importlib.util.spec_from_file_location("render_benchmarks_mod", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RenderBenchmarksTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = _load_render()

    def test_new_bands_sort_in_operational_order(self) -> None:
        index = {
            ("retail", "5000+"): "零售 × 5000+",
            ("retail", "1"): "零售 × 1",
            ("catering", "1001-5000"): "餐饮 × 1001-5000",
            ("catering", "11-50"): "餐饮 × 11-50",
            ("other", "any"): "其他 × any",
        }
        text = self.mod.render_markdown(index)
        positions = [
            text.index(index[key])
            for key in sorted(index, key=self.mod._group_sort_key)
        ]
        self.assertEqual(positions, sorted(positions))
        self.assertLess(text.index("餐饮 × 11-50"), text.index("餐饮 × 1001-5000"))
        self.assertLess(text.index("零售 × 1"), text.index("零售 × 5000+"))
        self.assertIn("301-1000", self.mod.BAND_ORDER)
        self.assertIn("5000+", self.mod.BAND_ORDER)
        self.assertNotIn("300+", self.mod.BAND_ORDER)


if __name__ == "__main__":
    unittest.main()
