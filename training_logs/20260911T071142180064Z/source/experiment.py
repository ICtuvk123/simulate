"""Pre-deployment utilities. This is not a search controller or a simulator."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from q3client import Client, JsonlJournal, Ledger, ProtocolError, canonical, digest, parse_journal

ROOT = Path(__file__).resolve().parent.parent


def source_hash():
    hasher = hashlib.sha256()
    for path in sorted((ROOT / "code").glob("*.py")):
        hasher.update(path.name.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(path.read_bytes())
        hasher.update(b"\0")
    return hasher.hexdigest()


def documented_fixture(success=False):
    """The six steps published in the attachments, with the optional success branch."""
    t = [0, 105, 111, 196 if success else 194, 201 if success else 199,
         201 if success else 199]
    specifications = [("/enter", None, None), ("/measure", (300, 400), 1),
                      ("/measure", (300, 400), 2), ("/clear", (300, 0), 3),
                      ("/measure", (300, 0), 2), ("/exit", None, None)]
    fixture = []
    for index, (path, position, channel) in enumerate(specifications):
        payload = {"arena_id": "default", "robot_id": "DOCUMENTATION_FIXTURE",
                   "request_id": "fixture-" + str(index)}
        response = {"accepted": True, "real_timestamp_ms": 1760000000000 + index,
                    "virtual_time_s": t[index]}
        if position is not None:
            payload.update(position={"x": position[0], "y": position[1]}, channel=channel)
        if path == "/enter":
            response.update(max_virtual_duration_s=360000, max_real_duration_s=1200,
                            remaining_real_duration_s=1200)
        elif path == "/measure":
            # The accounting table doesn't specify RF readings. Arbitrary statuses are
            # explicit test fixtures, never measurements from a real environment.
            response["measure_result"] = "no_signal"
        elif path == "/clear":
            response["clear_result"] = "success" if success else "no_target_in_range"
        else:
            response["exit_reason"] = "user_exit"
        fixture.append((path, payload, response))
    return fixture


def inspect_sample():
    ledger = Ledger()
    for path, payload, response in documented_fixture():
        ledger.apply(path, payload, 200, response)
    metrics = ledger.metrics({"run_id": "documentation-example", "mode": "contract_test",
                              "evidence": "published_timing_example_with_test_statuses"})
    for key in ("total_time", "move_distance", "move_time", "RF_detection_time",
                "channel_switch_time", "optical_time", "clear_time", "run_status"):
        print(f"{key}: {metrics[key]}")
    print("Contract fixture only; no simulator was launched.")
    return 0


def smoke(args):
    if args.robot_id in ("YOUR_TEAM_ID", "<参赛队号>"):
        raise ProtocolError("Replace the example team ID before connecting")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    directory = ROOT / "training_logs" / run_id
    metadata = {"run_id": run_id, "mode": args.mode,
                "mode_verified_by_api": False, "case_code": args.case_code,
                "seed": None, "strategy_version": "protocol-smoke-v1",
                "strategy_hash": source_hash(), "commit": None,
                "parameter_hash": digest({"base_url": args.base_url,
                                          "actions": "attachment-example-v1"}),
                "purpose": "protocol_validation_only"}
    journal = JsonlJournal(directory / "requests.jsonl", metadata)
    client = Client(args.robot_id, journal, base_url=args.base_url)
    error = None
    try:
        client.action("/enter")
        for path, point, channel in [("/measure", (300, 400), 1),
                                     ("/measure", (300, 400), 2),
                                     ("/clear", (300, 0), 3),
                                     ("/measure", (300, 0), 2)]:
            response = client.action(path, point, channel)
            print(path, response.get("measure_result", response.get("clear_result")),
                  response["virtual_time_s"])
        client.action("/exit")
    except (OSError, ValueError, ProtocolError) as exc:
        error = str(exc)
        journal.append({"event": "client_stop", "error": error,
                        "pending_request": client.pending})
    finally:
        journal.close()
    metrics = parse_journal(directory / "requests.jsonl")
    if error:
        metrics["client_error"] = error
    (directory / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2),
                                            encoding="utf-8")
    print("Client journal:", directory / "requests.jsonl")
    print("Status:", metrics["run_status"])
    if error:
        print("Stopped:", error, file=sys.stderr)
        return 1
    print("Protocol smoke completed. This does not prove search completion.")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("inspect-sample", help="Offline replay of the published timing example")
    command = sub.add_parser("smoke", help="Run documented demo in an already started training session")
    command.add_argument("--robot-id", required=True)
    command.add_argument("--mode", choices=["training"], required=True)
    command.add_argument("--case-code", required=True, help="Copy the case code visible in the UI")
    command.add_argument("--base-url", default="http://127.0.0.1:2026")
    command = sub.add_parser("parse", help="Read a client journal without calling any HTTP endpoint")
    command.add_argument("--log", type=Path, required=True)
    command.add_argument("--jammer-count", type=int, help="Official training UI count, post-run only")
    args = parser.parse_args()
    if args.command == "inspect-sample":
        return inspect_sample()
    if args.command == "smoke":
        return smoke(args)
    metrics = parse_journal(args.log, args.jammer_count)
    output = args.log.with_name("post_run_evaluation.json" if args.jammer_count is not None
                                else "parsed_metrics.json")
    output.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        raise SystemExit(main())
    except ProtocolError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
