"""Documented four-endpoint protocol, accounting and durable client journal.

This module contains no simulator, source coordinates, seed API or search policy.
Only successful HTTP responses can change the controller's observed state.
"""
from __future__ import annotations

import hashlib
import http.client
import json
import math
import socket
import time
import unicodedata
import uuid
from pathlib import Path
from urllib.parse import urlsplit


class ProtocolError(RuntimeError):
    pass


class UncertainAction(ProtocolError):
    """The action may have executed. Never issue a replacement with a new ID."""


def canonical(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False,
                      sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def identifier(value, limit):
    return (isinstance(value, str) and 1 <= len(value.encode("utf-8")) <= limit
            and not any(unicodedata.category(c) in ("Cc", "Cf") for c in value))


def validate_request(path, payload):
    expected = {"arena_id", "robot_id", "request_id"}
    if path in ("/measure", "/clear"):
        expected |= {"position", "channel"}
    elif path not in ("/enter", "/exit"):
        raise ProtocolError("Only the four exact documented paths are supported")
    if not isinstance(payload, dict) or set(payload) != expected:
        raise ProtocolError("Missing or unknown request fields")
    if payload["arena_id"] != "default":
        raise ProtocolError("arena_id must be default")
    if not identifier(payload["robot_id"], 64) or not identifier(payload["request_id"], 128):
        raise ProtocolError("Invalid robot_id or request_id")
    if path in ("/measure", "/clear"):
        p, ch = payload["position"], payload["channel"]
        if (not isinstance(p, dict) or set(p) != {"x", "y"}
                or not all(finite(v) and abs(v) <= 2_000_000 for v in p.values())):
            raise ProtocolError("Invalid position")
        if not finite(ch) or ch != int(ch) or not 1 <= ch <= 20:
            raise ProtocolError("Invalid channel")


def decode_response(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ProtocolError("Duplicate response key")
            result[key] = value
        return result

    def bad_constant(value):
        raise ProtocolError("Nonfinite response number: " + value)

    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=bad_constant)
    if not isinstance(value, dict):
        raise ProtocolError("Response must be a JSON object")
    return value


class Ledger:
    def __init__(self):
        self.position = (0.0, 0.0)
        self.channel = 1
        self.virtual_time = 0.0
        self.entered = False
        self.exited = False
        self.accepted_ids = {}
        self.cleared = set()
        self.events = []
        self.move_distance = 0.0
        self.rf_count = self.switch_count = self.optical_count = 0
        self.failed_action_count = self.rejected_count = self.optical_failed_count = 0
        self.network_retry_count = 0
        self.accounting_warnings = []

    def apply(self, path, payload, status, response):
        validate_request(path, payload)
        if (type(response.get("accepted")) is not bool
                or not finite(response.get("virtual_time_s"))
                or not finite(response.get("real_timestamp_ms"))):
            raise ProtocolError("Missing or invalid common response fields")
        # A rejection's virtual_time_s=0 never overwrites the current clock.
        if status != 200 or response["accepted"] is not True:
            if status != 200 and response["accepted"] is True:
                raise ProtocolError("Contradictory HTTP and business status")
            self.rejected_count += 1
            self.failed_action_count += 1
            return False
        key = payload["request_id"]
        fingerprint = digest({"path": path, "payload": payload})
        if key in self.accepted_ids:
            previous_fingerprint, previous_response = self.accepted_ids[key]
            if previous_fingerprint != fingerprint or previous_response != response:
                raise ProtocolError("Conflicting duplicate accepted request")
            return False
        if path == "/enter":
            if self.entered or response["virtual_time_s"] != 0:
                raise ProtocolError("Unexpected enter response")
            for field in ("max_virtual_duration_s", "max_real_duration_s",
                          "remaining_real_duration_s"):
                if not finite(response.get(field)) or response[field] < 0:
                    raise ProtocolError("Missing or invalid enter budget: " + field)
            if response["remaining_real_duration_s"] > response["max_real_duration_s"]:
                raise ProtocolError("Remaining budget exceeds maximum")
        elif not self.entered or self.exited:
            raise ProtocolError("Accepted action outside active client session")

        result = None
        if path == "/measure":
            result = response.get("measure_result")
            if result not in ("direction", "near", "no_signal"):
                raise ProtocolError("Unknown measurement result")
            if result == "direction":
                if not finite(response.get("svd_deg")) or not 0 <= response["svd_deg"] < 360:
                    raise ProtocolError("Missing or invalid bearing")
            elif "svd_deg" in response:
                raise ProtocolError("Unexpected bearing for non-direction result")
        elif path == "/clear":
            result = response.get("clear_result")
            if result not in ("success", "no_target_in_range"):
                raise ProtocolError("Unknown clear result")
            if result == "success" and payload["channel"] in self.cleared:
                raise ProtocolError("A channel was successfully cleared twice")
        elif path == "/exit":
            if response.get("exit_reason") != "user_exit":
                raise ProtocolError("Unexpected exit reason")

        previous_time = self.virtual_time
        if response["virtual_time_s"] < previous_time:
            raise ProtocolError("Accepted response moves clock backwards")
        distance = 0.0
        switch = 0
        rf = optical = clearing = 0.0
        new_position = self.position
        if path in ("/measure", "/clear"):
            new_position = (payload["position"]["x"], payload["position"]["y"])
            distance = math.dist(self.position, new_position)
        if path == "/measure":
            switch = int(payload["channel"] != self.channel)
            rf = 5.0
        elif path == "/clear":
            optical = 3.0
            clearing = 2.0 if result == "success" else 0.0
        expected = distance / 5 + switch + rf + optical + clearing
        delta = response["virtual_time_s"] - previous_time
        drift = delta - expected
        # Microsecond internal accumulation/response quantization is documented.
        if abs(drift) > 3e-6:
            self.accounting_warnings.append({"request_id": key, "drift_s": drift})

        self.position = new_position
        self.virtual_time = response["virtual_time_s"]
        self.move_distance += distance
        if path == "/enter":
            self.entered = True
        elif path == "/measure":
            self.channel = int(payload["channel"])
            self.rf_count += 1
            self.switch_count += switch
        elif path == "/clear":
            self.optical_count += 1
            if result == "success":
                self.cleared.add(int(payload["channel"]))
            else:
                self.optical_failed_count += 1
                self.failed_action_count += 1
        elif path == "/exit":
            self.exited = True
        self.accepted_ids[key] = (fingerprint, response.copy())
        self.events.append({"path": path, "request_id": key,
                            "position": list(self.position),
                            "channel": payload.get("channel"),
                            "rf_channel_after": self.channel,
                            "result": result, "svd_deg": response.get("svd_deg"),
                            "virtual_time_s": self.virtual_time,
                            "move_distance": distance, "move_time": distance / 5,
                            "RF_detection_time": rf, "channel_switch_time": switch,
                            "optical_time": optical, "clear_time": clearing,
                            "time_drift_s": drift})
        return True

    def metrics(self, metadata=None, jammer_count=None):
        metadata = metadata or {}
        if jammer_count is not None:
            if not self.exited:
                raise ProtocolError("Evaluation count is allowed only after successful exit")
            if (type(jammer_count) is not int or not 10 <= jammer_count <= 16
                    or jammer_count < len(self.cleared)):
                raise ProtocolError("Invalid post-run jammer count")
            if metadata.get("mode") != "training":
                raise ProtocolError("Only training UI exposes a post-run count")
        parts = {"move_time": self.move_distance / 5,
                 "RF_detection_time": 5 * self.rf_count,
                 "channel_switch_time": self.switch_count,
                 "optical_time": 3 * self.optical_count,
                 "clear_time": 2 * len(self.cleared)}
        per_channel = {str(ch): [e for e in self.events if e["channel"] == ch]
                       for ch in range(1, 21)}
        return {**metadata, "seed": metadata.get("seed"),
                "jammer_count": jammer_count, "clear_count": len(self.cleared),
                "clear_ratio": len(self.cleared) / jammer_count if jammer_count else None,
                "total_time": self.virtual_time, **parts,
                "accounted_total_time": sum(parts.values()),
                "mean_time_per_clear": self.virtual_time / len(self.cleared) if self.cleared else None,
                "move_distance": self.move_distance,
                "RF_detection_count": self.rf_count,
                "channel_switch_count": self.switch_count,
                "optical_count": self.optical_count,
                "failed_action_count": self.failed_action_count,
                "rejected_action_count": self.rejected_count,
                "optical_failed_count": self.optical_failed_count,
                "network_retry_count": self.network_retry_count,
                "trajectory": [[0.0, 0.0]] + [e["position"] for e in self.events
                                               if e["path"] in ("/measure", "/clear")],
                "per_channel_events": per_channel,
                "accounting_warnings": self.accounting_warnings,
                "run_status": "exited" if self.exited else "incomplete",
                "completion_proved": False}


class JsonlJournal:
    def __init__(self, path, metadata):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = self.path.open("x", encoding="utf-8", newline="\n")
        self.append({"event": "metadata", **metadata})

    def append(self, record):
        import os
        self.stream.write(canonical(record) + "\n")
        self.stream.flush()
        os.fsync(self.stream.fileno())

    def close(self):
        self.stream.close()


class HttpTransport:
    def __init__(self, base_url=None):
        raise ProtocolError("Local simulator only: an explicit isolated-process transport is required; HTTP connections are disabled")


class Client:
    def __init__(self, robot_id, journal, base_url=None,
                 attempts=3, transport=None):
        if not identifier(robot_id, 64):
            raise ProtocolError("A valid current team ID is required")
        if type(attempts) is not int or attempts < 1:
            raise ProtocolError("attempts must be positive")
        self.robot_id, self.journal = robot_id, journal
        self.transport = transport or HttpTransport(base_url)
        self.attempts = attempts
        self.ledger = Ledger()
        self.pending = None
        self.halted = False
        self.deadline = None
        self.virtual_limit = None

    def _budget(self):
        return math.inf if self.deadline is None else self.deadline - time.monotonic()

    def action(self, path, position=None, channel=None):
        if self.pending is not None or self.halted:
            raise UncertainAction("Client halted; inspect the journal before recovery")
        if path != "/enter" and (not self.ledger.entered or self.ledger.exited):
            raise ProtocolError("Client is not in an active run")
        if path == "/enter" and self.ledger.entered:
            raise ProtocolError("Cannot enter an active session twice")
        payload = {"arena_id": "default", "robot_id": self.robot_id,
                   "request_id": uuid.uuid4().hex}
        if path in ("/measure", "/clear"):
            if position is None or len(position) != 2:
                raise ProtocolError("A two-component position is required")
            payload.update(position={"x": position[0], "y": position[1]}, channel=channel)
        validate_request(path, payload)
        if self._budget() <= 1:
            raise ProtocolError("Insufficient real-time budget to issue a new action")
        if self.virtual_limit is not None and path in ("/measure", "/clear"):
            cost = math.dist(self.ledger.position, position) / 5 + 5
            if path == "/measure":
                cost += int(channel != self.ledger.channel)
            if self.ledger.virtual_time + cost >= self.virtual_limit:
                raise ProtocolError("Action would reach the virtual limit")
        body = canonical(payload).encode("utf-8")
        started = time.monotonic()
        self.pending = (path, payload)
        for attempt in range(1, self.attempts + 1):
            if self._budget() <= 0.1:
                break
            self.journal.append({"event": "request", "path": path, "payload": payload,
                                 "request_body": body.decode("utf-8"),
                                 "attempt": attempt, "monotonic_s": time.monotonic()})
            try:
                status, raw = self.transport(path, body, min(5.0, self._budget()))
            except (OSError, socket.timeout, http.client.HTTPException) as exc:
                self.journal.append({"event": "transport_error", "path": path,
                                     "request_id": payload["request_id"], "attempt": attempt,
                                     "error": type(exc).__name__})
                if attempt < self.attempts and self._budget() > 0.25:
                    self.ledger.network_retry_count += 1
                    time.sleep(min(0.1 * attempt, 0.5))
                continue
            self.journal.append({"event": "response", "path": path, "payload": payload,
                                 "http_status": status, "response_body": raw,
                                 "attempt": attempt, "monotonic_s": time.monotonic()})
            try:
                response = decode_response(raw)
                accepted = self.ledger.apply(path, payload, status, response)
            except Exception:
                self.halted = True
                raise
            if not accepted:
                self.halted = True
                raise ProtocolError(f"Action rejected: HTTP {status}; see journal")
            self.pending = None
            if path == "/enter":
                # Earliest attempt start is conservative even when an enter reply was lost.
                self.deadline = started + response["remaining_real_duration_s"]
                self.virtual_limit = response["max_virtual_duration_s"]
            if self.ledger.accounting_warnings:
                self.halted = True
                raise ProtocolError("Simulator time disagrees with contract; see journal")
            return response
        self.halted = True
        raise UncertainAction("No definitive response; same action may have executed; journal retained")


def parse_journal(path, jammer_count=None):
    ledger = Ledger()
    metadata = {}
    protocol_errors = []
    retries = set()
    certificate = None
    first_sent = last_received = None
    with Path(path).open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            record = decode_response(line)
            if record.get("event") == "metadata":
                metadata = {k: v for k, v in record.items() if k != "event"}
            elif record.get("event") == "request" and record.get("attempt", 1) > 1:
                retries.add((record["payload"]["request_id"], record["attempt"]))
            elif record.get("event") == "request" and first_sent is None:
                first_sent = record.get("monotonic_s")
            elif record.get("event") == "policy" and record.get("reason") == "completion_proved":
                certificate = record.get("certificate")
            elif record.get("event") == "response":
                last_received = record.get("monotonic_s")
                try:
                    ledger.apply(record["path"], record["payload"], record["http_status"],
                                 decode_response(record["response_body"]))
                except (ValueError, ProtocolError) as exc:
                    protocol_errors.append({"line": line_number, "error": str(exc)})
    ledger.network_retry_count = len(retries)
    metadata["raw_log_path"] = str(Path(path).resolve())
    result = ledger.metrics(metadata, jammer_count)
    result["protocol_errors"] = protocol_errors
    from coverage import validate_completion
    valid, proof_status = validate_completion(ledger.events, certificate)
    result["completion_proved"] = valid and not protocol_errors and not ledger.accounting_warnings
    result["completion_certificate"] = certificate
    result["completion_audit"] = proof_status
    result["program_wall_time_s"] = (last_received - first_sent
                                     if last_received is not None and first_sent is not None
                                     else None)
    if protocol_errors:
        result["run_status"] = "protocol_error"
    return result
