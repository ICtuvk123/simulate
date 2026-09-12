"""Run reproducible local cases through an isolated simulator process."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import multiprocessing
from pathlib import Path
import shutil
import sys
import time

from controller import BaselineController
from dynamic import DynamicController
from optimized import OptimizedController
from engine import simulator_worker
from geometry import open_held_karp, clip_bearing, outer_disk, minimum_circle
from q3client import Client, JsonlJournal, canonical, parse_journal

ROOT = Path(__file__).resolve().parents[1]


def observation_regions(events):
    polygons, changes = {}, []
    for event in events:
        response, ch = event["response"], event["channel"]
        if event["path"] == "/measure" and response.get("measure_result") == "direction":
            poly = clip_bearing(polygons.get(ch, outer_disk()), event["position"], response["svd_deg"])
            polygons[ch] = poly
            center, radius = minimum_circle(poly)
            changes.append({"event_index": event["index"], "channel": ch, "polygon": poly,
                            "center": center, "radius": radius})
        elif event["path"] == "/clear" and response.get("clear_result") == "success":
            polygons.pop(ch, None)
            changes.append({"event_index": event["index"], "channel": ch, "cleared": True})
    return changes


def oracle_bound(evaluation):
    """Post-run only: a certified edge-relaxed lower bound, not exact TSPN."""
    points = [(s["x"], s["y"]) for s in evaluation["sources"]]
    edges = [[max(0, math.dist(a, b) - 40) for b in points] for a in points]
    starts = [max(0, math.hypot(*p) - 20) for p in points]
    order, length = open_held_karp((0, 0), points, edges, starts)
    return {"lower_bound_time": length / 5 + 5 * len(points),
            "relaxation": "open_Held_Karp_with_disk_distance_lower_edges",
            "relaxed_order_channels": [evaluation["sources"][i]["channel"] for i in order],
            "ground_truth_used_only_after_exit": True}


def run_case(seed=1, strategy="C", scenario="uniform", reception="mixed",
             error_mode="fixed_hash", count=None, depth=2, beam_width=8,
             opportunistic=True, compute_oracle=True, output=None, policy_options=None):
    if strategy not in ("A", "B", "C", "D"):
        raise ValueError("unknown strategy")
    if (type(seed) is not int or scenario not in ("uniform", "boundary", "clustered")
            or reception not in ("mixed", "minimum", "maximum")
            or error_mode not in ("fixed_hash", "smooth", "plus_one", "minus_one")
            or (count is not None and (type(count) is not int or not 10 <= count <= 16))
            or type(depth) is not int or depth not in (1, 2, 3)
            or type(beam_width) is not int or not 1 <= beam_width <= 32):
        raise ValueError("invalid local experiment configuration")
    policy_options = dict(policy_options or {})
    allowed_options = {'mode', 'ring_radius', 'scan_gain', 'known_scan', 'max_region',
                       'opportunistic_clear', 'optical_trial', 'ring_rotation', 'prune_stations',
                       'adaptive_plan', 'future_stops', 'exact_neighborhood', 'local_rollout',
                       'bearing_factor', 'near_prediction'}
    if set(policy_options) - allowed_options or (policy_options and strategy != 'D'):
        raise ValueError('Invalid policy options')
    config = dict(seed=seed, count=count, scenario=scenario, reception=reception, error_mode=error_mode)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_id = f"{stamp}-s{seed}-{strategy}"
    directory = Path(output) if output else ROOT / "runs" / run_id
    directory.mkdir(parents=True, exist_ok=False)
    source_dir = directory / "source"
    source_dir.mkdir()
    fingerprint = hashlib.sha256()
    for path in sorted((ROOT / "code").glob("*.py")):
        fingerprint.update(path.name.encode() + path.read_bytes())
        shutil.copy2(path, source_dir / path.name)
    policy_config = dict(strategy=strategy, depth=depth, beam_width=beam_width, opportunistic=opportunistic,
                         policy_options=policy_options)
    metadata = {"run_id": run_id, "mode": "training", "data_origin": "self_written_simulator",
                "seed": seed, "strategy_version": f"local-{strategy}-v1",
                "strategy_hash": fingerprint.hexdigest(), "configuration": config,
                "policy_configuration": policy_config,
                "parameter_hash": hashlib.sha256(canonical(policy_config).encode()).hexdigest()}
    journal = JsonlJournal(directory / "requests.jsonl", metadata)
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    worker = context.Process(target=simulator_worker, args=(child, config), daemon=True)
    worker.start()
    child.close()
    busy = False
    def transport(path, body, timeout):
        nonlocal busy
        if busy:
            raise RuntimeError("different actions must not run concurrently")
        busy = True
        try:
            parent.send(("action", path, body))
            if not parent.poll(max(5, timeout)):
                raise TimeoutError("local engine did not respond")
            return parent.recv()
        finally:
            busy = False
    client = Client("local-robot", journal, transport=transport)
    controller = (OptimizedController(client, **policy_options) if strategy == 'D' else
                  DynamicController(client, depth, beam_width, opportunistic)
                  if strategy == "C" else BaselineController(client, strategy))
    error = None
    started = time.perf_counter()
    try:
        controller.run()
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        journal.append({"event": "client_stop", "error": error})
    finally:
        journal.close()
    wall_time = time.perf_counter() - started
    try:
        parent.send(("evaluation" if client.ledger.exited else "abort",))
        if not parent.poll(10):
            raise RuntimeError("evaluation timed out")
        evaluation = parent.recv()
    finally:
        if worker.is_alive():
            parent.send(("close",))
        worker.join(5)
        if worker.is_alive():
            worker.terminate()
            worker.join()
        parent.close()
    metrics = parse_journal(directory / "requests.jsonl", evaluation["jammer_count"] if client.ledger.exited else None)
    metrics.update(client_error=error, measured_program_wall_time_s=wall_time,
                   evaluated_clear_ratio=evaluation["clear_ratio"],
                   evaluated_jammer_count=evaluation["jammer_count"])
    if compute_oracle:
        bound = oracle_bound(evaluation)
        metrics["oracle"] = bound
        metrics["oracle_gap"] = (metrics["total_time"] - bound["lower_bound_time"]) / bound["lower_bound_time"]
    payload = {"metadata": metadata, "metrics": metrics, "evaluation": evaluation,
               "observation_regions": observation_regions(evaluation["events"])}
    (directory / "result.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (directory / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / "runs" / "latest.json").write_text(json.dumps({"run_id": directory.name}), encoding="utf-8")
    return directory, payload


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--strategy", choices=["A", "B", "C", "D"], default="C")
    p.add_argument('--policy-options', type=json.loads, default=None, help='D strategy JSON options')
    p.add_argument("--scenario", choices=["uniform", "boundary", "clustered"], default="uniform")
    p.add_argument("--reception", choices=["mixed", "minimum", "maximum"], default="mixed")
    p.add_argument("--error-mode", choices=["fixed_hash", "smooth", "plus_one", "minus_one"], default="fixed_hash")
    p.add_argument("--count", type=int, choices=range(10, 17))
    p.add_argument("--depth", type=int, choices=[1, 2, 3], default=2)
    p.add_argument("--beam-width", type=int, default=8)
    p.add_argument("--no-opportunistic", action="store_true")
    p.add_argument("--no-oracle", action="store_true")
    args = vars(p.parse_args())
    args["opportunistic"] = not args.pop("no_opportunistic")
    args["compute_oracle"] = not args.pop("no_oracle")
    directory, result = run_case(**args)
    m = result["metrics"]
    print(json.dumps({k: m.get(k) for k in ("run_id", "clear_count", "jammer_count", "clear_ratio",
                     "total_time", "RF_detection_count", "completion_proved", "client_error")}, ensure_ascii=False))
    print(str(directory))
    return int(bool(m["client_error"]) or m["evaluated_clear_ratio"] < 1 or not m["completion_proved"])


if __name__ == "__main__":
    multiprocessing.freeze_support()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
