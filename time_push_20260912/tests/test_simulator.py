import copy
import json
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from engine import Session, Source, generate_sources
from q3client import canonical, Ledger, HttpTransport, ProtocolError
from coverage import coverage_partition, validate_completion
from geometry import open_held_karp, regular_fallback


class SimulatorTests(unittest.TestCase):
    def setUp(self):
        self.session = Session(seed=12, sources=[Source(3, 600, 800, 1000), Source(7, -200, 0, 1500)])
        self.index = 0

    def request(self, path, point=None, channel=None, **extra):
        self.index += 1
        payload = {"arena_id": "default", "robot_id": "local-robot", "request_id": str(self.index)}
        if point is not None:
            payload.update(position={"x": point[0], "y": point[1]}, channel=channel)
        payload.update(extra)
        return payload, self.session.handle(path, canonical(payload).encode())

    def enter(self):
        return self.request("/enter")[1][1]

    def test_documented_199_seconds(self):
        self.enter()
        self.request("/measure", (300, 400), 1)
        self.request("/measure", (300, 400), 2)
        self.request("/clear", (300, 0), 3)
        self.request("/measure", (300, 0), 2)
        self.assertEqual(self.request("/exit")[1][1]["virtual_time_s"], 199)

    def test_receiver_does_not_switch_on_clear(self):
        self.enter()
        self.request("/measure", (0, 0), 7)
        self.request("/clear", (600, 800), 3)
        self.assertEqual(self.session.channel, 7)
        before = self.session.microseconds
        self.request("/measure", (600, 800), 7)
        self.assertEqual(self.session.microseconds - before, 5_000_000)

    def test_reception_boundary_and_near_boundary(self):
        self.enter()
        self.assertEqual(self.request("/measure", (0, 0), 3)[1][1]["measure_result"], "direction")
        self.assertEqual(self.request("/measure", (-.001, 0), 3)[1][1]["measure_result"], "no_signal")
        response = self.request("/measure", (603, 804), 3)[1][1]
        self.assertEqual(response["measure_result"], "near")
        self.assertNotIn("svd_deg", response)

    def test_clear_boundary_success_and_failure(self):
        self.enter()
        response = self.request("/clear", (620.001, 800), 3)[1][1]
        self.assertEqual(response["clear_result"], "no_target_in_range")
        before = self.session.microseconds
        response = self.request("/clear", (620, 800), 3)[1][1]
        self.assertEqual(response["clear_result"], "success")
        self.assertEqual(self.session.microseconds - before, 5_000_200)
        self.assertEqual(self.request("/measure", (600, 800), 3)[1][1]["measure_result"], "no_signal")

    def test_same_point_error_fixed(self):
        self.enter()
        a = self.request("/measure", (0, 0), 3)[1][1]
        self.request("/measure", (100, 0), 7)
        b = self.request("/measure", (-0.0, 0.0), 3)[1][1]
        self.assertEqual(a["svd_deg"], b["svd_deg"])

    def test_error_bound_including_rounding(self):
        for mode in ("fixed_hash", "smooth", "plus_one", "minus_one"):
            self.session = Session(sources=[Source(1, 20, 0, 1000)], error_mode=mode)
            self.enter()
            for point in [(0, 0), (20, 30), (20, -30), (40, .001)]:
                angle = self.request("/measure", point, 1)[1][1]["svd_deg"]
                real = math.degrees(math.atan2(-point[1], 20 - point[0]))
                error = (angle - real + 180) % 360 - 180
                self.assertLessEqual(abs(error), 1.005 + 1e-9)
                self.assertTrue(0 <= angle < 360)

    def test_idempotency_and_conflict(self):
        self.enter()
        payload, original = self.request("/measure", (300, 400), 3)
        before = self.session.microseconds
        self.assertEqual(self.session.handle("/measure", canonical(payload).encode()), original)
        payload["channel"] = 4
        self.assertEqual(self.session.handle("/measure", canonical(payload).encode())[0], 409)
        self.assertEqual(self.session.microseconds, before)

    def test_rejected_unknown_does_not_claim_id_or_change_state(self):
        self.enter()
        payload, (status, reply) = self.request("/measure", (100, 100), 3, misspelled=1)
        self.assertEqual((status, reply["accepted"], reply["virtual_time_s"]), (200, False, 0))
        self.assertEqual(self.session.position, (0, 0))
        del payload["misspelled"]
        self.assertTrue(self.session.handle("/measure", canonical(payload).encode())[1]["accepted"])

    def test_protocol_errors(self):
        self.enter()
        for body in (b'{"a":1,"a":2}', b'[]', b'{"x":NaN}', b'{}'):
            self.assertEqual(self.session.handle("/measure", body)[0], 400)
        self.assertEqual(self.session.handle("/measure/", b'{}')[0], 404)
        self.assertEqual(self.session.handle("/measure?x=1", b'{}')[0], 404)
        self.assertEqual(self.session.handle("/measure", b'{}', method="GET")[0], 405)
        self.assertEqual(self.session.handle("/measure", b'{}', content_type="text/plain")[0], 415)
        self.assertEqual(self.session.handle("/measure", b' ' * 65537)[0], 413)

    def test_invalid_positions_and_channels(self):
        self.enter()
        for point, channel in [((2000001, 0), 1), ((0, 0), True), ((0, 0), 1.5), ((0, 0), 21)]:
            self.assertEqual(self.request("/measure", point, channel)[1][0], 400)
        self.assertTrue(self.request("/measure", (1900, 0), 1.0)[1][1]["accepted"])

    def test_robot_identity(self):
        self.assertFalse(self.request("/enter", robot_id="another")[1][1]["accepted"])
        self.assertTrue(self.enter()["accepted"])

    def test_no_truth_before_end(self):
        with self.assertRaises(RuntimeError):
            self.session.evaluation()
        self.enter()
        self.assertFalse(self.request("/enter")[1][1]["accepted"])
        self.request("/exit")
        self.assertEqual(self.session.evaluation()["jammer_count"], 2)
        self.assertFalse(self.request("/measure", (0, 0), 1)[1][1]["accepted"])

    def test_no_actions_before_enter(self):
        self.assertFalse(self.request("/measure", (0, 0), 1)[1][1]["accepted"])

    def test_deadlines(self):
        now = [100.0]
        self.session = Session(monotonic=lambda: now[0])
        now[0] += 400
        self.assertEqual(self.enter()["remaining_real_duration_s"], 1100)
        now[0] += 1101
        self.assertFalse(self.request("/measure", (0, 0), 1)[1][1]["accepted"])
        self.assertEqual(self.session.ended_reason, "window_timeout")

    def test_virtual_deadline(self):
        self.enter()
        self.session.microseconds = 359999_000000
        self.assertFalse(self.request("/measure", (0, 0), 1)[1][1]["accepted"])
        self.assertEqual(self.session.ended_reason, "virtual_timeout")

    def test_generation_reproducible_and_physical(self):
        for scene in ("uniform", "boundary", "clustered"):
            for seed in range(20):
                sources = generate_sources(seed, scenario=scene)
                self.assertEqual(sources, generate_sources(seed, scenario=scene))
                self.assertTrue(10 <= len(sources) <= 16)
                self.assertEqual(len(set(s.channel for s in sources)), len(sources))
                self.assertTrue(all(math.hypot(s.x, s.y) <= 1800 and 1000 <= s.radius <= 1500 for s in sources))

    def test_coverage_certificate_and_gap(self):
        stations, _ = regular_fallback()
        self.assertTrue(coverage_partition(stations, 12)["complete"])
        self.assertFalse(coverage_partition(stations[:-1], 12)["complete"])
        self.assertFalse(validate_completion([], {"kind": "analytic_center_ring"})[0])

    def test_no_outbound_http_transport(self):
        with self.assertRaises(ProtocolError):
            HttpTransport("http://127.0.0.1:2026")

    def test_oracle_edge_relaxation_lower_than_any_center_route(self):
        points = [(100, 100), (1000, 0), (0, -1000)]
        edges = [[max(0, math.dist(a, b) - 40) for b in points] for a in points]
        starts = [max(0, math.hypot(*p) - 20) for p in points]
        _, relaxed = open_held_karp((0, 0), points, edges, starts)
        _, centers = open_held_karp((0, 0), points)
        self.assertLessEqual(relaxed, centers)
        self.assertGreaterEqual(relaxed, centers - 100 - 1e-9)


if __name__ == "__main__":
    unittest.main()
