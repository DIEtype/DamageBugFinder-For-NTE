from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "desktop"))

from panel_ocr import OcrLine, parse_panel  # noqa: E402


class PanelOcrParserTests(unittest.TestCase):
    def test_attack_split_and_damage_fields(self) -> None:
        lines = [
            OcrLine("攻击力", 420, 380, 150, 35),
            OcrLine("1158 + 1250", 1880, 382, 210, 30),
            OcrLine("暴击伤害", 420, 680, 180, 35),
            OcrLine("134 ． 00％", 1920, 682, 160, 30),
            OcrLine("通用伤害增强", 420, 780, 240, 35),
            OcrLine("24 · 00％", 1940, 782, 140, 30),
        ]
        fields = parse_panel(lines, (2560, 1440))["fields"]
        values = {(item["field"], item.get("attribute")): item["value"] for item in fields}
        self.assertEqual(values[("panel_attack", None)], 2408)
        self.assertEqual(values[("base_attack", None)], 1158)
        self.assertEqual(values[("crit_damage", None)], 134)
        self.assertEqual(values[("general_bonus", None)], 24)

    def test_elemental_bonus_does_not_read_resistance(self) -> None:
        lines = [
            OcrLine("光属性异能伤害增强", 420, 240, 300, 35),
            OcrLine("47 · 50％", 1940, 242, 140, 30),
            OcrLine("光属性异能伤害抗性", 420, 340, 300, 35),
            OcrLine("20 · 00％", 1940, 342, 140, 30),
        ]
        fields = parse_panel(lines, (2560, 1440))["fields"]
        elemental = [item for item in fields if item["field"] == "elemental_bonus"]
        self.assertEqual(len(elemental), 1)
        self.assertEqual(elemental[0]["attribute"], "光")
        self.assertEqual(elemental[0]["value"], 47.5)

    def test_level_fallback_uses_max_level_when_slash_is_misread(self) -> None:
        lines = [OcrLine("Lv：8 伊 80", 1700, 330, 220, 35)]
        fields = parse_panel(lines, (2560, 1440))["fields"]
        self.assertEqual(fields[0]["field"], "character_level")
        self.assertEqual(fields[0]["value"], 80)


if __name__ == "__main__":
    unittest.main()

