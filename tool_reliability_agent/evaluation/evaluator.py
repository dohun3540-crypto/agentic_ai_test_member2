"""통합 규격의 로그 및 평가 지표 구현."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from statistics import fmean

import config
from models import RoutingDecision, TaskInput, ToolResult


class Evaluator:
    def __init__(self, run_id: int = 1) -> None:
        self.run_id = run_id
        self._rows: list[dict[str, object]] = []

    def log_step(
        self,
        task: TaskInput,
        decision: RoutingDecision,
        result: ToolResult,
        reliability_scores: dict[str, float],
    ) -> None:
        if task.task_id != decision.task_id or task.task_id != result.task_id:
            raise ValueError("task_id must match across TaskInput, RoutingDecision, and ToolResult")
        if decision.selected_tool != result.tool_name:
            raise ValueError("selected_tool and result.tool_name must match")
        if self._rows and task.task_id <= int(self._rows[-1]["task_id"]):
            raise ValueError("task_id must be strictly increasing within one run")

        self._rows.append(
            {
                "run_id": self.run_id,
                "task_id": task.task_id,
                "selected_tool": decision.selected_tool,
                "tool_success": int(result.success),
                "tool_a_reliability": float(
                    reliability_scores.get("tool_a", config.INITIAL_RELIABILITY)
                ),
                "tool_b_reliability": float(
                    reliability_scores.get("tool_b", config.INITIAL_RELIABILITY)
                ),
                "used_exploration": int(decision.used_exploration),
                "latency_sec": float(result.latency_sec),
                "retry_count": 0,
            }
        )

    def compute_metrics(self) -> dict:
        if not self._rows:
            raise ValueError("No evaluation logs are available")

        success_rate = fmean(float(row["tool_success"]) for row in self._rows)
        avoidance_rate = self._compute_failure_avoidance_rate()
        detection_lag = self._compute_detection_lag()
        recovery_lag = self._compute_recovery_lag()
        switch_count = sum(
            left["selected_tool"] != right["selected_tool"]
            for left, right in zip(self._rows, self._rows[1:])
        )
        switching_rate = switch_count / max(len(self._rows) - 1, 1)

        return {
            "task_success_rate": success_rate,
            "failure_avoidance_rate": avoidance_rate,
            "detection_lag": detection_lag,
            "recovery_lag": recovery_lag,
            "tool_switching_rate": switching_rate,
            "retry_count": sum(int(row["retry_count"]) for row in self._rows),
            "token_count": 0,
            "avg_latency_sec": fmean(float(row["latency_sec"]) for row in self._rows),
        }

    def save_results(self, path: str) -> None:
        target = Path(path)
        if target.suffix.lower() == ".csv":
            target.parent.mkdir(parents=True, exist_ok=True)
            self._write_csv(target)
            return

        target.mkdir(parents=True, exist_ok=True)
        self._write_csv(target / "experiment_log.csv")
        with (target / "metrics.json").open("w", encoding="utf-8") as handle:
            json.dump(self.compute_metrics(), handle, ensure_ascii=False, indent=2)

    def reset(self) -> None:
        self._rows.clear()

    def _write_csv(self, path: Path) -> None:
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(config.LOG_COLUMNS))
            writer.writeheader()
            writer.writerows(self._rows)

    def _compute_failure_avoidance_rate(self) -> float:
        opportunities = 0
        avoided = 0
        for row in self._rows:
            task_id = int(row["task_id"])
            probabilities = {
                tool: config.get_tool_success_probability(tool, task_id)
                for tool in config.TOOL_IDS
            }
            best_probability = max(probabilities.values())
            if len(set(probabilities.values())) == 1:
                continue
            opportunities += 1
            selected_tool = str(row["selected_tool"])
            avoided += probabilities[selected_tool] == best_probability
        return avoided / opportunities if opportunities else 0.0

    def _compute_detection_lag(self) -> int | None:
        degradation_task = _first_relative_state_change(worse=True)
        if degradation_task is None:
            return None
        for row in self._rows:
            if (
                int(row["task_id"]) >= degradation_task
                and not bool(row["used_exploration"])
                and row["selected_tool"] != "tool_a"
            ):
                return int(row["task_id"]) - degradation_task
        return None

    def _compute_recovery_lag(self) -> int | None:
        recovery_task = _first_relative_state_change(worse=False)
        if recovery_task is None:
            return None
        avoided_before_recovery = any(
            int(row["task_id"]) < recovery_task
            and row["selected_tool"] != "tool_a"
            and not bool(row["used_exploration"])
            for row in self._rows
        )
        if not avoided_before_recovery:
            return None
        for row in self._rows:
            if (
                int(row["task_id"]) >= recovery_task
                and not bool(row["used_exploration"])
                and row["selected_tool"] == "tool_a"
            ):
                return int(row["task_id"]) - recovery_task
        return None


def _first_relative_state_change(worse: bool) -> int | None:
    previous_relation: bool | None = None
    for task_id in range(1, config.NUM_TASKS + 1):
        a_probability = config.get_tool_success_probability("tool_a", task_id)
        b_probability = config.get_tool_success_probability("tool_b", task_id)
        current_relation = a_probability < b_probability
        if previous_relation is not None and current_relation != previous_relation:
            if current_relation is worse:
                return task_id
        previous_relation = current_relation
    return None
