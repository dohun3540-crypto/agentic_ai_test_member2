"""Run the integrated member1 + member2 + member3 experiments."""

from __future__ import annotations

import json
import random
from pathlib import Path
from statistics import fmean

import config
from agent.agent_core import AgentCore
from evaluation.evaluator import Evaluator
from models import TaskInput
from reliability.reliability_manager import ReliabilityManager
from routing.tool_router import BaselineRouter, ReliabilityRouter
from tools.simulated_tools import SimulatedToolA, SimulatedToolB


ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "results"


def build_tools() -> dict:
    """Build the authoritative member1 Tool implementations."""
    return {
        "tool_a": SimulatedToolA(),
        "tool_b": SimulatedToolB(),
    }


def build_router(experiment: str, seed: int):
    if experiment == "baseline":
        return BaselineRouter()
    if experiment == "proposed":
        return ReliabilityRouter(random_seed=seed)
    raise ValueError(f"Unknown experiment: {experiment}")


def run_one_experiment(experiment: str, run_id: int, seed: int) -> dict:
    """Run one 100-task experiment and save its integrated CSV."""
    random.seed(seed)

    evaluator = Evaluator(run_id=run_id)
    reliability_manager = ReliabilityManager(initial_score=config.INITIAL_RELIABILITY)
    agent = AgentCore(
        tools=build_tools(),
        reliability_manager=reliability_manager,
        router=build_router(experiment, seed),
        evaluator=evaluator,
    )

    for task_id in range(1, config.NUM_TASKS + 1):
        agent.run_task(TaskInput(task_id=task_id, query=f"Task {task_id}"))

    output_path = RESULTS_DIR / f"integrated_{experiment}_run_{run_id:02d}.csv"
    evaluator.save_results(str(output_path))
    return evaluator.compute_metrics()


def average_numeric_metrics(metrics: list[dict]) -> dict[str, float | None]:
    """Average each metric across runs while ignoring undefined lags."""
    result: dict[str, float | None] = {}
    for key in metrics[0]:
        values = [item[key] for item in metrics if item[key] is not None]
        result[key] = fmean(float(value) for value in values) if values else None
    return result


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    all_metrics: dict[str, list[dict]] = {"baseline": [], "proposed": []}

    for run_id in range(1, config.NUM_RUNS + 1):
        seed = config.RANDOM_SEED + run_id - 1

        baseline_metrics = run_one_experiment("baseline", run_id, seed)
        proposed_metrics = run_one_experiment("proposed", run_id, seed)

        all_metrics["baseline"].append(baseline_metrics)
        all_metrics["proposed"].append(proposed_metrics)
        print(
            f"run {run_id:02d}/{config.NUM_RUNS}: "
            f"baseline={baseline_metrics['task_success_rate']:.3f}, "
            f"proposed={proposed_metrics['task_success_rate']:.3f}"
        )

    summary = {
        "experiment": "integrated_member1_member2_member3",
        "num_tasks": config.NUM_TASKS,
        "num_runs": config.NUM_RUNS,
        "random_seed": config.RANDOM_SEED,
        "reliability_method": config.RELIABILITY_METHOD,
        "baseline": average_numeric_metrics(all_metrics["baseline"]),
        "proposed": average_numeric_metrics(all_metrics["proposed"]),
        "per_run": all_metrics,
    }

    summary_path = RESULTS_DIR / "integrated_summary.json"
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)

    print(json.dumps(
        {"baseline": summary["baseline"], "proposed": summary["proposed"]},
        ensure_ascii=False,
        indent=2,
    ))
    print(f"saved: {summary_path}")


if __name__ == "__main__":
    main()
