import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "research"))

from gold_timeline import parse_gold


class GoldTimelineTests(unittest.TestCase):
    def test_partial_terminal_minute_is_omitted_not_used_as_full_minute(self):
        parts = []
        for i, role in enumerate(["TOP", "JGL", "MID", "BOT", "SPT"] * 2):
            color = "97,148,198,1" if i < 5 else "198,97,97,1"
            parts.append(
                f"label:'{role}',data:[500,700,900,1000],borderColor:'rgba({color})'"
            )
        html = (
            "var golddatas = {labels:['0','1','2','2'],datasets:["
            + ",".join(parts)
            + "]\n};"
        )
        gold = parse_gold(html)
        self.assertEqual(gold, {0: (2500, 2500), 1: (3500, 3500)})
        with self.assertRaises(ValueError):
            parse_gold(html.replace("'0','1'", "'1','0'"))
