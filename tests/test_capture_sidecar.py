from __future__ import annotations

import sys
import struct
import unittest
from pathlib import Path
from unittest.mock import patch


DESKTOP = Path(__file__).resolve().parents[1] / "desktop"
sys.path.insert(0, str(DESKTOP))

from capture_sidecar import (  # noqa: E402
    CaptureDeltaTracker,
    NteCoreCapture,
    PcapEventPreviewTracker,
    _build_core_audit_record,
    _event_category,
)


class CaptureDeltaTrackerTests(unittest.TestCase):
    @patch("capture_sidecar.time.time", return_value=123.456)
    def test_single_new_hit_is_importable(self, _mock_time) -> None:
        tracker = CaptureDeltaTracker()
        tracker.ingest(
            {
                "skills": [
                    {
                        "char_id": 1001,
                        "char_name": "测试角色",
                        "name": "技能A",
                        "category": "E技能",
                        "ability_name": "GA_Test_Skill",
                        "gameplay_effect_name": "GE_Test_Skill_Damage",
                        "hits": 1,
                        "damage": 4413,
                    }
                ]
            }
        )
        groups = tracker.drain()
        self.assertEqual(len(groups), 1)
        self.assertTrue(groups[0]["single_hit"])
        self.assertEqual(groups[0]["damage"], 4413)
        self.assertEqual(groups[0]["gameplay_effect_name"], "GE_Test_Skill_Damage")

    def test_cumulative_summary_only_yields_delta(self) -> None:
        tracker = CaptureDeltaTracker()
        base = {
            "char_id": 1001,
            "name": "浊燃",
            "category": "浊燃",
            "gameplay_effect_name": "GE_Reaction_5_Damage",
        }
        tracker.ingest({"skills": [{**base, "hits": 2, "damage": 4200}]})
        tracker.drain()
        tracker.ingest({"skills": [{**base, "hits": 3, "damage": 6534}]})
        groups = tracker.drain()
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["hits"], 1)
        self.assertEqual(groups[0]["damage"], 2334)

    def test_multiple_hits_are_marked_as_group(self) -> None:
        tracker = CaptureDeltaTracker()
        tracker.ingest(
            {"skills": [{"name": "多段技能", "category": "普攻", "hits": 4, "damage": 6821}]}
        )
        group = tracker.drain()[0]
        self.assertFalse(group["single_hit"])
        self.assertEqual(group["hits"], 4)


class PcapEventPreviewTrackerTests(unittest.TestCase):
    @staticmethod
    def _game_payload(packet_id: int, token: str, value: float) -> bytes:
        payload = bytearray(9)
        payload[0] |= 3 << 3  # non-handshake PacketHandler signature
        for index in range(14):
            if packet_id & (1 << index):
                bit_offset = 24 + index
                payload[bit_offset // 8] |= 1 << (bit_offset % 8)
        payload.extend(token.encode("ascii"))
        payload.append(0)
        payload.extend(struct.pack("<f", value))
        payload.append(0x80)  # UE terminal bit
        return bytes(payload)

    def test_discovers_event_after_stream_sequence_is_confirmed(self) -> None:
        tracker = PcapEventPreviewTracker()
        for packet_id in range(10, 14):
            tracker._observe_udp(
                1_000.0 + packet_id / 10,
                bytes((192, 168, 1, 2)),
                40_000,
                bytes((203, 0, 113, 8)),
                20_000,
                self._game_payload(packet_id, "Melee1", 4413.0),
            )
        events = tracker.drain(force=True)
        melee_events = [event for event in events if event["name"] == "Melee1"]
        self.assertTrue(melee_events)
        self.assertEqual(melee_events[0]["direction"], "C2S")
        self.assertIn(4413.0, melee_events[0]["candidates"])

    def test_does_not_preview_unconfirmed_udp_stream(self) -> None:
        tracker = PcapEventPreviewTracker()
        tracker._observe_udp(
            1_000.0,
            bytes((192, 168, 1, 2)),
            40_000,
            bytes((203, 0, 113, 8)),
            20_000,
            b"Melee1\x00" + struct.pack("<f", 4413.0) + b"\x80",
        )
        self.assertEqual(tracker.drain(force=True), [])

    def test_confirms_test_server_stream_from_multiple_strong_event_signatures(self) -> None:
        tracker = PcapEventPreviewTracker()
        common = (
            bytes((192, 168, 1, 2)),
            40_000,
            bytes((203, 0, 113, 8)),
            20_000,
        )
        tracker._observe_udp(1_000.0, *common, b"\x00FCharacterForNet\x00")
        tracker._observe_udp(1_000.1, *common, b"\x00AbilitySystemComponent\x00")
        names = [event["name"] for event in tracker.drain(force=True)]
        self.assertIn("FCharacterForNet", names)
        self.assertIn("AbilitySystemComponent", names)

    def test_ability_system_component_is_a_damage_carrier(self) -> None:
        tracker = PcapEventPreviewTracker()
        common = (
            bytes((192, 168, 1, 2)),
            40_000,
            bytes((203, 0, 113, 8)),
            20_000,
        )
        tracker._observe_udp(1_000.0, *common, b"\x00FCharacterForNet\x00")
        tracker._observe_udp(1_000.1, *common, b"\x00AbilitySystemComponent\x00")
        event = next(
            event
            for event in tracker.drain(force=True)
            if event["name"] == "AbilitySystemComponent"
        )
        self.assertEqual(event["category"], "carrier")

    def test_buff_class_with_skill_in_name_remains_an_effect(self) -> None:
        self.assertEqual(
            _event_category("Default__Buff_Zankou_RefuseGSkill_C"),
            "effect",
        )


class NteCoreCaptureTests(unittest.TestCase):
    def test_capture_uses_detected_device_and_incoming_packets(self) -> None:
        params = NteCoreCapture._capture_start_params(
            {"recommended_device": r"\Device\NPF_TEST"}
        )
        self.assertEqual(
            params["device"], {"mode": "name", "name": r"\Device\NPF_TEST"}
        )
        self.assertTrue(params["include_incoming"])

    def test_capture_falls_back_to_auto_device(self) -> None:
        params = NteCoreCapture._capture_start_params({"recommended_device": None})
        self.assertEqual(params["device"], {"mode": "auto"})

    def test_core_audit_keeps_buff_identifiers_and_redacts_sensitive_fields(self) -> None:
        record = _build_core_audit_record(
            "event.effect.apply",
            {
                "effect": "Default__Buff_Zankou_Passive1_C",
                "stacks": 3,
                "payload": "secret packet bytes",
            },
            observed_at_unix_ms=123456,
        )
        self.assertEqual(record["method"], "event.effect.apply")
        self.assertIn("Default__Buff_Zankou_Passive1_C", record["identifiers"])
        self.assertIn("params.payload", record["schema"])
        self.assertNotIn("secret packet bytes", str(record))
        self.assertIn("[已隐藏]", str(record))


if __name__ == "__main__":
    unittest.main()
