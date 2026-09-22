import csv
import random
from pathlib import Path
from statistics import mean

from agent.agent_core import AgentCore
from config import EWMA_ALPHA, NUM_TASKS, RANDOM_SEED, WINDOW_SIZE
from models import RoutingDecision, TaskInput
from reliability.reliability_manager import ReliabilityManager
from tools.simulated_tools import SimulatedToolA, SimulatedToolB


OUTPUT_PATH = Path(__file__).resolve().parent / "reliability_dryrun_results.csv"
METHODS = ("sliding_window", "ewma")
SEGMENTS = (
    (1, 25, "95%"),
    (26, 50, "60%"),
    (51, 75, "20%"),
    (76, 100, "95%"),
)


class AlwaysToolARouter:
    """Test-only Router used only to exercise AgentCore -> Tool -> Reliability."""

    def select_tool(self, task, candidate_tools, reliability_scores):
        return RoutingDecision(
            task_id=task.task_id,
            selected_tool="tool_a",
            reliability_scores=dict(reliability_scores),
            used_exploration=False,
        )


def run_method(method: str):
    random.seed(RANDOM_SEED)
    reliability_manager = ReliabilityManager(
        method=method,
        window_size=WINDOW_SIZE,
        ewma_alpha=EWMA_ALPHA,
    )
    agent = AgentCore(
        tools={"tool_a": SimulatedToolA(), "tool_b": SimulatedToolB()},
        reliability_manager=reliability_manager,
        router=AlwaysToolARouter(),
    )

    rows = []
    for task_id in range(1, NUM_TASKS + 1):
        task = TaskInput(task_id=task_id, query=f"topic_{task_id}")
        result = agent.run_task(task)
        rows.append(
            {
                "task_id": task_id,
                "tool_name": result.tool_name,
                "success": int(result.success),
                "reliability_score": round(
                    reliability_manager.get_score(result.tool_name), 6
                ),
                "reliability_method": method,
            }
        )
    return rows


def summarize(rows):
    print("\nReliability trend summary")
    for method in METHODS:
        method_rows = [row for row in rows if row["reliability_method"] == method]
        print(f"[{method}]")
        for start, end, configured_rate in SEGMENTS:
            segment_rows = [
                row for row in method_rows if start <= row["task_id"] <= end
            ]
            average_score = mean(row["reliability_score"] for row in segment_rows)
            final_score = segment_rows[-1]["reliability_score"]
            success_rate = mean(row["success"] for row in segment_rows)
            print(
                f"  tasks {start:>3}-{end:<3} (Tool A cfg {configured_rate}): "
                f"success={success_rate:.3f}, avg_R={average_score:.3f}, "
                f"end_R={final_score:.3f}"
            )


def main():
    all_rows = []
    for method in METHODS:
        all_rows.extend(run_method(method))

    fieldnames = [
        "task_id",
        "tool_name",
        "success",
        "reliability_score",
        "reliability_method",
    ]
    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"{len(all_rows)} rows saved: {OUTPUT_PATH.name}")
    summarize(all_rows)


if __name__ == "__main__":
    main()
