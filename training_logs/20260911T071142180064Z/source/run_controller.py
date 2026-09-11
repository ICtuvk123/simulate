"""Run an initial search baseline in an already opened official training session."""
import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from controller import BaselineController
from experiment import ROOT, source_hash
from q3client import Client, JsonlJournal, digest, parse_journal


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--robot-id", required=True)
    parser.add_argument("--case-code", required=True)
    parser.add_argument("--baseline", choices=("A", "B"), default="A")
    parser.add_argument("--ring-radius", type=float, default=1300)
    parser.add_argument("--base-url", default="http://127.0.0.1:2026")
    args = parser.parse_args()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    directory = ROOT / "training_logs" / run_id
    config = {"baseline": args.baseline, "ring_radius": args.ring_radius,
              "bearing_error_deg": 1.01, "optical_grid_size": 20}
    metadata = {"run_id": run_id, "mode": "training", "case_code": args.case_code,
                "seed": None, "strategy_version": "baseline-" + args.baseline + "-v1",
                "strategy_hash": source_hash(), "commit": None,
                "parameter_hash": digest(config), "parameters": config,
                "purpose": "full_search_baseline"}
    journal = JsonlJournal(directory / "requests.jsonl", metadata)
    snapshot = directory / "source"
    snapshot.mkdir()
    for path in (ROOT / "code").glob("*.py"):
        shutil.copy2(path, snapshot / path.name)
    client = Client(args.robot_id, journal, args.base_url)
    controller = BaselineController(client, args.baseline, args.ring_radius)
    certificate = None
    error = None
    try:
        certificate = controller.run()
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        journal.append({"event": "client_stop", "error": error,
                        "pending_request": client.pending})
    finally:
        journal.close()
    metrics = parse_journal(directory / "requests.jsonl")
    metrics["completion_proved"] = certificate is not None
    metrics["completion_certificate"] = certificate
    metrics["client_error"] = error
    (directory / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2),
                                            encoding="utf-8")
    print(json.dumps({key: metrics.get(key) for key in
                      ("run_id", "case_code", "strategy_version", "run_status", "clear_count",
                       "total_time", "move_time", "RF_detection_count", "optical_count",
                       "completion_proved", "client_error")}, indent=2))
    print("Run directory:", directory)
    return 1 if error else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
