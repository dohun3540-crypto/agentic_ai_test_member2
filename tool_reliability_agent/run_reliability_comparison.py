"""Compare Reliability memory methods under identical simulation/router settings."""
from __future__ import annotations

import csv
import json
import random
from pathlib import Path
from statistics import fmean, pstdev

import config
from agent.agent_core import AgentCore
from evaluation.evaluator import Evaluator
from models import TaskInput
from reliability.reliability_manager import ReliabilityManager
from routing.tool_router import BaselineRouter, ReliabilityRouter
from tools.simulated_tools import SimulatedToolA, SimulatedToolB

ROOT = Path(__file__).resolve().parent
OUTPUT_ROOT = ROOT / "results" / "reliability_comparison"

CONDITIONS = [
    {"name": "cumulative", "method": "cumulative", "window_size": None, "alpha": None},
    {"name": "sliding_w5", "method": "sliding_window", "window_size": 5, "alpha": None},
    {"name": "sliding_w10", "method": "sliding_window", "window_size": 10, "alpha": None},
    {"name": "sliding_w20", "method": "sliding_window", "window_size": 20, "alpha": None},
    {"name": "ewma_a01", "method": "ewma", "window_size": None, "alpha": 0.1},
    {"name": "ewma_a03", "method": "ewma", "window_size": None, "alpha": 0.3},
    {"name": "ewma_a05", "method": "ewma", "window_size": None, "alpha": 0.5},
]
TASK_FIELDS = [
    "reliability_method", "window_size", "alpha", "run_id", "task_id",
    "selected_tool", "tool_success", "tool_a_reliability", "tool_b_reliability",
    "used_exploration", "latency_sec",
]


def build_tools() -> dict:
    return {"tool_a": SimulatedToolA(), "tool_b": SimulatedToolB()}


def make_manager(condition: dict) -> ReliabilityManager:
    return ReliabilityManager(
        method=condition["method"],
        window_size=condition["window_size"] or config.WINDOW_SIZE,
        ewma_alpha=condition["alpha"] or config.EWMA_ALPHA,
        initial_score=config.INITIAL_RELIABILITY,
    )


def reliability_diagnostics(rows: list[dict]) -> dict[str, float]:
    values = [float(row["tool_a_reliability"]) for row in rows]
    changes = [abs(b - a) for a, b in zip(values, values[1:])]
    return {
        "tool_a_reliability_stddev": pstdev(values) if len(values) > 1 else 0.0,
        "tool_a_mean_abs_step_change": fmean(changes) if changes else 0.0,
    }


def save_task_rows(path: Path, rows: list[dict], condition: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TASK_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "reliability_method": condition["method"],
                "window_size": condition["window_size"],
                "alpha": condition["alpha"],
                "run_id": row["run_id"],
                "task_id": row["task_id"],
                "selected_tool": row["selected_tool"],
                "tool_success": row["tool_success"],
                "tool_a_reliability": row["tool_a_reliability"],
                "tool_b_reliability": row["tool_b_reliability"],
                "used_exploration": row["used_exploration"],
                "latency_sec": row["latency_sec"],
            })


def run_condition(condition: dict, routing: str = "proposed") -> list[dict]:
    per_run_metrics = []
    condition_dir = OUTPUT_ROOT / condition["name"]

    for run_id in range(1, config.NUM_RUNS + 1):
        seed = config.RANDOM_SEED + run_id - 1
        random.seed(seed)
        evaluator = Evaluator(run_id=run_id)
        manager = make_manager(condition)
        router = BaselineRouter() if routing == "baseline" else ReliabilityRouter(random_seed=seed)
        agent = AgentCore(build_tools(), manager, router, evaluator)

        for task_id in range(1, config.NUM_TASKS + 1):
            agent.run_task(TaskInput(task_id=task_id, query=f"Task {task_id}"))

        rows = [dict(row) for row in evaluator._rows]
        metrics = evaluator.compute_metrics()
        metrics.update(reliability_diagnostics(rows))
        metrics["detection_success"] = metrics["detection_lag"] is not None
        metrics["recovery_success"] = metrics["recovery_lag"] is not None
        metrics["run_id"] = run_id
        metrics["seed"] = seed
        per_run_metrics.append(metrics)
        save_task_rows(condition_dir / f"run_{run_id:02d}.csv", rows, condition)

    with (condition_dir / "per_run_metrics.json").open("w", encoding="utf-8") as handle:
        json.dump(per_run_metrics, handle, ensure_ascii=False, indent=2)
    return per_run_metrics


def aggregate(condition: dict, routing: str, metrics: list[dict]) -> dict:
    detection_lags = [m["detection_lag"] for m in metrics if m["detection_lag"] is not None]
    recovery_lags = [m["recovery_lag"] for m in metrics if m["recovery_lag"] is not None]
    n = len(metrics)
    return {
        "condition": condition["name"],
        "routing": routing,
        "reliability_method": condition["method"],
        "window_size": condition["window_size"],
        "alpha": condition["alpha"],
        "num_runs": n,
        "num_tasks_per_run": config.NUM_TASKS,
        "task_success_rate": fmean(m["task_success_rate"] for m in metrics),
        "failure_avoidance_rate": fmean(m["failure_avoidance_rate"] for m in metrics),
        "tool_switching_rate": fmean(m["tool_switching_rate"] for m in metrics),
        "valid_detection_runs": len(detection_lags),
        "detection_success_rate": len(detection_lags) / n,
        "mean_detection_lag_when_detected": fmean(detection_lags) if detection_lags else None,
        "valid_recovery_runs": len(recovery_lags),
        "recovery_success_rate": len(recovery_lags) / n,
        "mean_recovery_lag_when_recovered": fmean(recovery_lags) if recovery_lags else None,
        "tool_a_reliability_stddev": fmean(m["tool_a_reliability_stddev"] for m in metrics),
        "tool_a_mean_abs_step_change": fmean(m["tool_a_mean_abs_step_change"] for m in metrics),
    }


def write_summary(rows: list[dict], per_run: dict[str, list[dict]]) -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    with (OUTPUT_ROOT / "summary.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    payload = {
        "experiment": "member2_reliability_comparison",
        "num_tasks": config.NUM_TASKS,
        "num_runs_per_condition": config.NUM_RUNS,
        "random_seed": config.RANDOM_SEED,
        "seed_policy": "RANDOM_SEED + run_id - 1",
        "routing_parameters": {
            "exploration_rate": config.EXPLORATION_RATE,
            "forced_probe_interval": config.FORCED_PROBE_INTERVAL,
            "min_switch_gain": config.MIN_SWITCH_GAIN,
        },
        "conditions": rows,
        "per_run": per_run,
    }
    with (OUTPUT_ROOT / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    summary_rows = []
    all_per_run = {}

    baseline_condition = {
        "name": "baseline_reference",
        "method": config.RELIABILITY_METHOD,
        "window_size": config.WINDOW_SIZE,
        "alpha": None,
    }
    baseline_metrics = run_condition(baseline_condition, routing="baseline")
    summary_rows.append(aggregate(baseline_condition, "baseline", baseline_metrics))
    all_per_run["baseline_reference"] = baseline_metrics
    print(f"baseline_reference: success={summary_rows[-1]['task_success_rate']:.3f}")

    for condition in CONDITIONS:
        metrics = run_condition(condition, routing="proposed")
        row = aggregate(condition, "proposed", metrics)
        summary_rows.append(row)
        all_per_run[condition["name"]] = metrics
        print(
            f"{condition['name']}: success={row['task_success_rate']:.3f}, "
            f"detect={row['detection_success_rate']:.2f}/lag={row['mean_detection_lag_when_detected']}, "
            f"recover={row['recovery_success_rate']:.2f}/lag={row['mean_recovery_lag_when_recovered']}"
        )

    write_summary(summary_rows, all_per_run)
    print(f"saved: {OUTPUT_ROOT}")


if __name__ == "__main__":
    main()
