"""Contract tests, not training episodes or official simulator verification."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from experiment import documented_fixture
from q3client import (Client, HttpTransport, JsonlJournal, Ledger, ProtocolError,
                      UncertainAction, canonical, decode_response, parse_journal, validate_request)


class MemoryJournal:
    def __init__(self):
        self.records = []

    def append(self, record):
        self.records.append(copy.deepcopy(record))


class AccountingTests(unittest.TestCase):
    def fixture(self, success=False):
        ledger = Ledger()
        for path, payload, response in documented_fixture(success):
            ledger.apply(path, payload, 200, response)
        return ledger

    def test_published_example_is_199_seconds(self):
        ledger = self.fixture()
        metrics = ledger.metrics()
        self.assertEqual(metrics["total_time"], 199)
        self.assertEqual(metrics["accounted_total_time"], 199)
        self.assertEqual(metrics["move_distance"], 900)
        self.assertEqual(metrics["RF_detection_time"], 15)
        self.assertEqual(metrics["channel_switch_count"], 1)
        self.assertEqual(metrics["optical_time"], 3)
        self.assertEqual(metrics["optical_failed_count"], 1)
        self.assertEqual(metrics["accounting_warnings"], [])

    def test_clear_success_adds_two_seconds_and_does_not_switch_rf(self):
        ledger = self.fixture(True)
        self.assertEqual(ledger.virtual_time, 201)
        self.assertEqual(ledger.channel, 2)
        self.assertEqual(ledger.switch_count, 1)
        self.assertEqual(ledger.cleared, {3})

    def test_rejection_does_not_reset_time_or_position(self):
        ledger = Ledger()
        actions = documented_fixture()
        for path, payload, response in actions[:2]:
            ledger.apply(path, payload, 200, response)
        path, payload, _ = actions[2]
        payload["position"] = {"x": 1, "y": 2}
        ledger.apply(path, payload, 200,
                     {"accepted": False, "real_timestamp_ms": 1, "virtual_time_s": 0})
        self.assertEqual((ledger.position, ledger.channel, ledger.virtual_time),
                         ((300, 400), 1, 105))

    def test_idempotent_response_not_counted_twice(self):
        ledger = Ledger()
        for path, payload, response in documented_fixture():
            ledger.apply(path, payload, 200, response)
            ledger.apply(path, payload, 200, response)
        self.assertEqual((ledger.virtual_time, ledger.rf_count), (199, 3))

    def test_conflicting_id_rejected(self):
        ledger = Ledger()
        actions = documented_fixture()
        for path, payload, response in actions[:2]:
            ledger.apply(path, payload, 200, response)
        path, payload, response = copy.deepcopy(actions[1])
        payload["channel"] = 7
        with self.assertRaises(ProtocolError):
            ledger.apply(path, payload, 200, response)

    def test_count_cannot_be_used_before_exit(self):
        ledger = Ledger()
        with self.assertRaises(ProtocolError):
            ledger.metrics({"mode": "training"}, 12)

    def test_unknown_count_stays_null(self):
        metrics = self.fixture(True).metrics()
        self.assertIsNone(metrics["jammer_count"])
        self.assertIsNone(metrics["clear_ratio"])

    def test_count_requires_training_mode(self):
        with self.assertRaises(ProtocolError):
            self.fixture(True).metrics({"mode": "formal"}, 12)
        result = self.fixture(True).metrics({"mode": "training"}, 12)
        self.assertEqual(result["clear_ratio"], 1 / 12)

    def test_bad_bearing_has_no_state_effect(self):
        ledger = Ledger()
        actions = documented_fixture()
        ledger.apply(actions[0][0], actions[0][1], 200, actions[0][2])
        path, payload, response = copy.deepcopy(actions[1])
        response["measure_result"] = "direction"
        with self.assertRaises(ProtocolError):
            ledger.apply(path, payload, 200, response)
        self.assertEqual(ledger.position, (0, 0))

    def test_near_without_bearing_supported(self):
        ledger = Ledger()
        actions = documented_fixture()
        ledger.apply(actions[0][0], actions[0][1], 200, actions[0][2])
        path, payload, response = copy.deepcopy(actions[1])
        response["measure_result"] = "near"
        self.assertTrue(ledger.apply(path, payload, 200, response))

    def test_fractional_movement_time_is_retained(self):
        ledger = Ledger()
        actions = documented_fixture()
        ledger.apply(actions[0][0], actions[0][1], 200, actions[0][2])
        path, payload, response = copy.deepcopy(actions[1])
        payload["position"] = {"x": 1, "y": 1}
        response["virtual_time_s"] = 5.282843
        ledger.apply(path, payload, 200, response)
        self.assertEqual(ledger.virtual_time, 5.282843)
        self.assertFalse(ledger.accounting_warnings)

    def test_time_mismatch_is_visible(self):
        ledger = Ledger()
        actions = documented_fixture()
        ledger.apply(actions[0][0], actions[0][1], 200, actions[0][2])
        path, payload, response = copy.deepcopy(actions[1])
        response["virtual_time_s"] += 1
        ledger.apply(path, payload, 200, response)
        self.assertEqual(ledger.accounting_warnings[0]["drift_s"], 1)


class ProtocolTests(unittest.TestCase):
    def test_bad_fields_coordinates_channels_rejected(self):
        path, payload, _ = documented_fixture()[1]
        for point in ({"x": float("nan"), "y": 0}, {"x": 2000001, "y": 0},
                      {"x": True, "y": 0}, {"x": 0, "y": 0, "z": 0}):
            with self.subTest(point=point), self.assertRaises(ProtocolError):
                validate_request(path, {**payload, "position": point})
        for channel in (True, 0, 21, 1.5, "1"):
            with self.subTest(channel=channel), self.assertRaises(ProtocolError):
                validate_request(path, {**payload, "channel": channel})
        with self.assertRaises(ProtocolError):
            validate_request(path, {**payload, "seed": 123})

    def test_unknown_paths_rejected(self):
        _, payload, _ = documented_fixture()[0]
        for path in ("/reset", "/status", "/enter/", "/enter?seed=1", "/optical", "/move"):
            with self.subTest(path=path), self.assertRaises(ProtocolError):
                validate_request(path, payload)

    def test_identifiers_reject_invisible_and_overlong_content(self):
        path, payload, _ = documented_fixture()[0]
        for robot in ("", "x\u200by", "x\ny", "a" * 65):
            with self.subTest(robot=robot), self.assertRaises(ProtocolError):
                validate_request(path, {**payload, "robot_id": robot})

    def test_json_duplicate_keys_and_nonfinite_are_rejected(self):
        for raw in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}', '[]'):
            with self.subTest(raw=raw), self.assertRaises(ProtocolError):
                decode_response(raw)

    def test_only_loopback_origins(self):
        for url in ("http://example.com:2026", "http://127.0.0.1:2026/status",
                    "http://user:password@127.0.0.1:2026", "https://127.0.0.1"):
            with self.subTest(url=url), self.assertRaises(ProtocolError):
                HttpTransport(url)

    def test_lost_reply_reuses_exact_bytes_and_counts_once(self):
        bodies = []
        response = documented_fixture()[0][2]
        def transport(path, body, timeout):
            bodies.append(body)
            if len(bodies) == 1:
                raise TimeoutError("test lost reply")
            return 200, canonical(response)
        client = Client("test-team", MemoryJournal(), transport=transport)
        client.action("/enter")
        self.assertEqual(bodies[0], bodies[1])
        self.assertEqual(len(client.ledger.accepted_ids), 1)
        self.assertEqual(client.ledger.network_retry_count, 1)

    def test_unresolved_action_blocks_new_ids(self):
        def transport(path, body, timeout):
            raise TimeoutError("test unavailable")
        client = Client("test-team", MemoryJournal(), attempts=1, transport=transport)
        with self.assertRaises(UncertainAction):
            client.action("/enter")
        with self.assertRaises(UncertainAction):
            client.action("/enter")

    def test_short_enter_budget_prevents_next_action(self):
        response = {**documented_fixture()[0][2], "remaining_real_duration_s": 0}
        client = Client("test-team", MemoryJournal(), transport=lambda *a: (200, canonical(response)))
        client.action("/enter")
        with self.assertRaises(ProtocolError):
            client.action("/measure", (0, 0), 1)

    def test_raw_journal_roundtrip_and_original_file_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "client.jsonl"
            journal = JsonlJournal(path, {"mode": "contract_test", "run_id": "example"})
            for route, payload, response in documented_fixture():
                journal.append({"event": "response", "path": route, "payload": payload,
                                "http_status": 200, "response_body": canonical(response)})
            journal.close()
            before = path.read_bytes()
            metrics = parse_journal(path)
            self.assertEqual(metrics["total_time"], 199)
            self.assertEqual(metrics["run_status"], "exited")
            self.assertEqual(path.read_bytes(), before)
            with self.assertRaises(FileExistsError):
                JsonlJournal(path, {})


if __name__ == "__main__":
    unittest.main()
