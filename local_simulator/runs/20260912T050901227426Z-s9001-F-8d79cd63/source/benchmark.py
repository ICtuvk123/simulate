"""Paired local comparisons on common, predeclared scene seeds."""
import csv
import json
import statistics
from runner import ROOT, run_case


def percentile(values, q):
    values = sorted(values)
    at = (len(values) - 1) * q
    a = int(at)
    return values[a] + (values[min(a + 1, len(values) - 1)] - values[a]) * (at - a)


def main():
    cases = [(seed, "train", "uniform", "mixed", "fixed_hash") for seed in range(101, 105)]
    cases += [(seed, "validation", "uniform", "mixed", "fixed_hash") for seed in range(501, 505)]
    cases += [(901, "stress", "boundary", "minimum", "plus_one"),
              (902, "stress", "boundary", "minimum", "minus_one"),
              (903, "stress", "clustered", "minimum", "smooth"),
              (904, "stress", "uniform", "minimum", "smooth")]
    manifest = {"cases": cases, "strategies": ["A", "B", "C"], "data_origin": "self_written_simulator",
                "purpose": "initial simulator and strategy validation, not a plateau claim"}
    (ROOT / "reports" / "benchmark_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    rows = []
    for seed, split, scenario, reception, error_mode in cases:
        for strategy in ("A", "B", "C"):
            directory, payload = run_case(seed, strategy, scenario, reception, error_mode, compute_oracle=False)
            m = payload["metrics"]
            row = {"seed": seed, "split": split, "strategy": strategy, "scenario": scenario,
                   "reception": reception, "error_mode": error_mode,
                   **{k: m.get(k) for k in ("run_id", "clear_count", "jammer_count", "clear_ratio", "total_time",
                       "move_time", "RF_detection_time", "channel_switch_time", "optical_time", "clear_time",
                       "RF_detection_count", "completion_proved", "client_error")}}
            rows.append(row)
            with (ROOT / "reports" / "paired_runs.csv").open("w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            print(json.dumps({k: row[k] for k in ("seed", "strategy", "clear_ratio", "total_time", "client_error")}), flush=True)
    summary = []
    for split in ("train", "validation", "stress", "all"):
        for strategy in ("A", "B", "C"):
            group = [r for r in rows if r["strategy"] == strategy and (split == "all" or r["split"] == split)]
            times = [r["total_time"] for r in group]
            summary.append({"split": split, "strategy": strategy, "runs": len(group),
                            "all_100_percent": all(r["clear_ratio"] == 1 and r["completion_proved"] for r in group),
                            "mean_total_time": statistics.mean(times), "median": statistics.median(times),
                            "p90": percentile(times, .9), "p95": percentile(times, .95), "worst": max(times),
                            **{f"mean_{k}": statistics.mean(r[k] for r in group) for k in
                               ("move_time", "RF_detection_time", "channel_switch_time", "optical_time", "clear_time")}})
    (ROOT / "reports" / "benchmark_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    with (ROOT / "reports" / "leaderboard.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    print("BENCHMARK_COMPLETE", flush=True)


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    main()
