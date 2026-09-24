"""Generate presentation-ready PNG figures from reliability comparison results."""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from statistics import fmean

import matplotlib.pyplot as plt

import config

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results" / "reliability_comparison"
FIGURES = RESULTS / "figures"
CANONICAL = [
    ("cumulative", "Cumulative"),
    ("sliding_w10", "Sliding Window (10)"),
    ("ewma_a03", "EWMA (0.3)"),
]


def load_trace(condition: str) -> dict[int, float]:
    by_task = defaultdict(list)
    for path in sorted((RESULTS / condition).glob("run_*.csv")):
        with path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                by_task[int(row["task_id"])].append(float(row["tool_a_reliability"]))
    return {task: fmean(values) for task, values in sorted(by_task.items())}


def actual_rates() -> dict[int, float]:
    return {
        task_id: config.get_tool_success_probability("tool_a", task_id)
        for task_id in range(1, config.NUM_TASKS + 1)
    }


def summary_rows() -> list[dict]:
    with (RESULTS / "summary.csv").open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def save(fig, name: str) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(FIGURES / name, dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_method_traces() -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    for key, label in CANONICAL:
        trace = load_trace(key)
        ax.plot(list(trace), list(trace.values()), label=label)
    ax.axvline(26, linestyle="--", alpha=0.5)
    ax.axvline(76, linestyle="--", alpha=0.5)
    ax.set(
        title="Tool A Reliability by Task",
        xlabel="Task ID",
        ylabel="Estimated Reliability",
        ylim=(0, 1),
    )
    ax.legend()
    ax.grid(alpha=0.25)
    save(fig, "tool_a_reliability_methods.png")


def plot_truth_vs_estimates() -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    truth = actual_rates()
    ax.step(
        list(truth),
        list(truth.values()),
        where="post",
        linewidth=2,
        label="Tool A Ground Truth",
    )
    for key, label in CANONICAL:
        trace = load_trace(key)
        ax.plot(list(trace), list(trace.values()), label=label)
    ax.set(
        title="Tool A Ground Truth vs Reliability Estimates",
        xlabel="Task ID",
        ylabel="Probability / Reliability",
        ylim=(0, 1),
    )
    ax.legend()
    ax.grid(alpha=0.25)
    save(fig, "tool_a_ground_truth_vs_estimates.png")


def proposed_rows() -> list[dict]:
    return [row for row in summary_rows() if row["routing"] == "proposed"]


def plot_lags() -> None:
    rows = proposed_rows()
    names = [row["condition"] for row in rows]
    detection = [
        float(row["mean_detection_lag_when_detected"])
        if row["mean_detection_lag_when_detected"] else 0
        for row in rows
    ]
    recovery = [
        float(row["mean_recovery_lag_when_recovered"])
        if row["mean_recovery_lag_when_recovered"] else 0
        for row in rows
    ]
    x = range(len(names))
    width = 0.38
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.bar([i - width / 2 for i in x], detection, width, label="Detection Lag")
    ax.bar([i + width / 2 for i in x], recovery, width, label="Recovery Lag")
    ax.set(
        title="Detection / Recovery Lag (Successful Runs Only)",
        xlabel="Reliability Condition",
        ylabel="Mean Lag (Tasks)",
    )
    ax.set_xticks(list(x), names, rotation=30, ha="right")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)
    save(fig, "detection_recovery_lag.png")


def plot_detection_recovery_success() -> None:
    rows = proposed_rows()
    names = [row["condition"] for row in rows]
    x = range(len(names))
    width = 0.38
    detection = [float(row["detection_success_rate"]) for row in rows]
    recovery = [float(row["recovery_success_rate"]) for row in rows]
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.bar([i - width / 2 for i in x], detection, width, label="Detection Success Rate")
    ax.bar([i + width / 2 for i in x], recovery, width, label="Recovery Success Rate")
    ax.set(
        title="Detection / Recovery Success Rate",
        xlabel="Reliability Condition",
        ylabel="Success Rate",
        ylim=(0, 1.05),
    )
    ax.set_xticks(list(x), names, rotation=30, ha="right")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)
    save(fig, "detection_recovery_success_rate.png")


def plot_task_success() -> None:
    rows = summary_rows()
    names = [row["condition"] for row in rows]
    values = [float(row["task_success_rate"]) for row in rows]
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.bar(names, values)
    ax.set(
        title="Task Success Rate by Reliability Condition",
        xlabel="Condition",
        ylabel="Task Success Rate",
        ylim=(0, 1),
    )
    ax.tick_params(axis="x", rotation=30)
    ax.grid(axis="y", alpha=0.25)
    save(fig, "task_success_rate_comparison.png")


def main() -> None:
    if not (RESULTS / "summary.csv").exists():
        raise SystemExit("Run run_reliability_comparison.py first")
    plot_method_traces()
    plot_truth_vs_estimates()
    plot_lags()
    plot_detection_recovery_success()
    plot_task_success()
    print(f"saved figures: {FIGURES}")


if __name__ == "__main__":
    main()
