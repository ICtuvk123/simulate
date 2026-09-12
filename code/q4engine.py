"""Independent Q4 simulator. Public physics, locally chosen scene distributions.

No official software, database, network, accounts or hidden answers are accessed.
"""
from dataclasses import asdict, dataclass
import hashlib
import json
import math
import random
import struct
import time

from q3client import canonical, decode_response, identifier, validate_request, ProtocolError


@dataclass(frozen=True)
class Source:
    channel: int
    x: float
    y: float
    radius: float
    direction_deg: float | None = None


def generate_sources(seed, count=None, scenario="uniform", reception="mixed", source_mix="mixed", orientation="random"):
    rng = random.Random(f"q4-world-v1:{seed}")
    n = rng.randint(10, 16) if count is None else count
    if type(n) is not int or not 10 <= n <= 16:
        raise ValueError("Q4 requires 10 to 16 sources")
    if scenario not in ("uniform", "boundary", "clustered"):
        raise ValueError("unknown scene distribution")
    if reception not in ("mixed", "minimum", "maximum"):
        raise ValueError("unknown reception mode")
    channels = rng.sample(range(1, 21), n)
    if source_mix not in ("mixed","omni","directional") or orientation not in ("random","outward","inward","angle_boundary"):
        raise ValueError("invalid Q4 type/orientation distribution")
    directed = set(rng.sample(channels, rng.randint(1,n-1))) if source_mix=="mixed" else set(channels) if source_mix=="directional" else set()
    sources = []
    for ch in channels:
        a = rng.uniform(0, 2 * math.pi)
        if scenario == "uniform":
            r = 1800 * math.sqrt(rng.random())
            x, y = r * math.cos(a), r * math.sin(a)
        elif scenario == "boundary":
            r = rng.uniform(1740, 1800)
            x, y = r * math.cos(a), r * math.sin(a)
        else:
            center = rng.choice(((-950, 250), (600, -800), (200, 1050)))
            r = 240 * math.sqrt(rng.random())
            x, y = center[0] + r * math.cos(a), center[1] + r * math.sin(a)
        radius = rng.uniform(1000, 1500) if reception == "mixed" else (1000 if reception == "minimum" else 1500)
        direction = None
        if ch in directed:
            direction = (rng.uniform(0,360) if orientation=="random" else math.degrees(math.atan2(y,x)) + (0 if orientation=="outward" else 180 if orientation=="inward" else 90)) % 360
        sources.append(Source(ch, x, y, radius, direction))
    return sorted(sources, key=lambda source: source.channel)


class Session:
    """Authoritative state; kept in a separate process from the controller."""
    def __init__(self, seed=0, count=None, scenario="uniform", reception="mixed",
                 error_mode="fixed_hash", robot_id="local-robot", sources=None, source_mix="mixed", orientation="random",
                 monotonic=time.monotonic, timestamp=time.time):
        self._sources = sources if sources is not None else generate_sources(seed, count, scenario, reception, source_mix, orientation)
        self._by_channel = {source.channel: source for source in self._sources}
        if len(self._by_channel) != len(self._sources):
            raise ValueError("channels must be unique")
        if any(not 1 <= s.channel <= 20 or math.hypot(s.x, s.y) > 1800 + 1e-8
               or not 1000 <= s.radius <= 1500 or (s.direction_deg is not None and not math.isfinite(s.direction_deg)) for s in self._sources):
            raise ValueError("invalid Q4 source")
        if error_mode not in ("fixed_hash", "smooth", "plus_one", "minus_one"):
            raise ValueError("unknown error model")
        self._error_seed = hashlib.sha256(f"q4-error-v1:{seed}".encode()).digest()
        self._error_mode = error_mode
        self.robot_id = robot_id
        self.clock, self.timestamp = monotonic, timestamp
        self.ready_at = self.clock()
        self.entered_at = None
        self.ended_reason = None
        self.position = (0.0, 0.0)
        self.channel = 1
        self.microseconds = 0
        self.cleared = set()
        self.cache = {}
        self.events = []

    def _reply(self, accepted=False, **fields):
        return {"accepted": accepted, "real_timestamp_ms": int(self.timestamp() * 1000),
                "virtual_time_s": self.microseconds / 1_000_000 if accepted else 0, **fields}

    def _error(self, channel, point):
        if self._error_mode == "plus_one":
            return 1.0
        if self._error_mode == "minus_one":
            return -1.0
        if self._error_mode == "smooth":
            phase = int.from_bytes(hashlib.sha256(self._error_seed + bytes([channel])).digest()[:8], "big") / 2 ** 64 * 2 * math.pi
            x, y = point
            return (math.sin(x / 170 + phase) + math.sin(y / 230 - phase)
                    + math.sin((x + y) / 310 + 2 * phase)) / 3
        # Canonicalize signed zero; identical physical points get identical error.
        x, y = (v if v != 0 else 0.0 for v in point)
        raw = self._error_seed + bytes([channel]) + struct.pack("!dd", float(x), float(y))
        value = int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")
        return 2 * value / (2 ** 64 - 1) - 1

    def handle(self, path, body, method="POST", content_type="application/json"):
        if path not in ("/enter", "/measure", "/clear", "/exit"):
            return 404, self._reply()
        if method != "POST":
            return 405, self._reply()
        if content_type.split(";")[0].strip().lower() != "application/json":
            return 415, self._reply()
        if len(body) > 65536:
            return 413, self._reply()
        try:
            payload = decode_response(body.decode("utf-8"))
            expected = {"arena_id", "robot_id", "request_id"}
            if path in ("/measure", "/clear"):
                expected |= {"position", "channel"}
            if set(payload) - expected:
                return 200, self._reply()
            if isinstance(payload.get("position"), dict) and set(payload["position"]) - {"x", "y"}:
                return 200, self._reply()
            sanitized = dict(payload)
            if "arena_id" in sanitized and isinstance(sanitized["arena_id"], str):
                sanitized["arena_id"] = "default"
            validate_request(path, sanitized)
        except (ValueError, TypeError, UnicodeError, KeyError, ProtocolError):
            return 400, self._reply()
        if payload["arena_id"] != "default" or payload["robot_id"] != self.robot_id:
            return 200, self._reply()
        key = payload["request_id"]
        fingerprint = canonical({"path": path, "payload": payload})
        if key in self.cache:
            old, status, result = self.cache[key]
            return (status, dict(result)) if fingerprint == old else (409, self._reply())
        now = self.clock()
        if now - self.ready_at >= 1500:
            self.ended_reason = self.ended_reason or "window_timeout"
        if self.entered_at is not None and now - self.entered_at >= 1200:
            self.ended_reason = self.ended_reason or "real_timeout"
        if self.ended_reason:
            return 200, self._reply()
        if (path == "/enter") == (self.entered_at is not None):
            return 200, self._reply()
        fields = {}
        move = switch = rf = optical = clearing = 0.0
        before = self.position
        if path == "/enter":
            self.entered_at = now
            fields = {"max_virtual_duration_s": 360000, "max_real_duration_s": 1200,
                      "remaining_real_duration_s": min(1200, max(0, 1500 - (now - self.ready_at)))}
        elif path == "/exit":
            self.ended_reason = "user_exit"
            fields = {"exit_reason": "user_exit"}
        else:
            point = (float(payload["position"]["x"]), float(payload["position"]["y"]))
            ch = int(payload["channel"])
            move = math.dist(self.position, point) / 5
            source = self._by_channel.get(ch)
            if ch in self.cleared:
                source = None
            distance = math.dist(point, (source.x, source.y)) if source else math.inf
            if path == "/measure":
                switch, rf = int(ch != self.channel), 5
                emitting = source is not None and (source.direction_deg is None or
                    (point[0]-source.x)*math.cos(math.radians(source.direction_deg)) +
                    (point[1]-source.y)*math.sin(math.radians(source.direction_deg)) >= -1e-10)
                if not emitting or distance > (source.radius if source else 0):
                    fields = {"measure_result": "no_signal"}
                elif distance <= 5:
                    fields = {"measure_result": "near"}
                else:
                    bearing = math.degrees(math.atan2(source.y - point[1], source.x - point[0]))
                    fields = {"measure_result": "direction", "svd_deg":
                              round((bearing + self._error(ch, point)) % 360, 2) % 360}
            else:
                optical = 3
                clearing = 2 if distance <= 20 else 0
                fields = {"clear_result": "success" if clearing else "no_target_in_range"}
            increment = round(move * 1_000_000) + int((switch + rf + optical + clearing) * 1_000_000)
            if self.microseconds + increment >= 360000 * 1_000_000:
                self.ended_reason = "virtual_timeout"
                return 200, self._reply()
            self.position = point
            self.microseconds += increment
            if path == "/measure":
                self.channel = ch
            elif clearing:
                self.cleared.add(ch)
        response = self._reply(True, **fields)
        self.cache[key] = (fingerprint, 200, dict(response))
        self.events.append({"index": len(self.events), "path": path, "from": before,
                            "position": self.position, "channel": payload.get("channel"),
                            "rf_channel_after": self.channel, "response": dict(response),
                            "move_time": move, "RF_time": rf, "switch_time": switch,
                            "optical_time": optical, "clear_time": clearing,
                            "cleared_count": len(self.cleared)})
        return 200, response

    def evaluation(self):
        if not self.ended_reason:
            raise RuntimeError("ground truth is unavailable until the run ends")
        return {"jammer_count": len(self._sources), "directional_count": sum(s.direction_deg is not None for s in self._sources), "clear_count": len(self.cleared),
                "clear_ratio": len(self.cleared) / len(self._sources),
                "sources": [asdict(source) for source in self._sources],
                "cleared_channels": sorted(self.cleared), "events": self.events,
                "ended_reason": self.ended_reason, "data_origin": "self_written_simulator",
                "distribution_is_official": False}


def simulator_worker(connection, configuration):
    session = Session(**configuration)
    try:
        while True:
            command = connection.recv()
            if command[0] == "action":
                status, response = session.handle(command[1], command[2])
                connection.send((status, canonical(response)))
            elif command[0] == "evaluation":
                connection.send(session.evaluation())
            elif command[0] == "abort":
                session.ended_reason = session.ended_reason or "local_controller_stop"
                connection.send(session.evaluation())
            elif command[0] == "close":
                break
    except EOFError:
        pass
    finally:
        connection.close()
