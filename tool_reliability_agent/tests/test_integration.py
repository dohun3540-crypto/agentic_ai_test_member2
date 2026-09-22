from __future__ import annotations

import csv
import random
import tempfile
import unittest
from pathlib import Path

import config
from agent.agent_core import AgentCore
from evaluation.evaluator import Evaluator
from models import RoutingDecision, TaskInput, ToolResult
from reliability.reliability_manager import ReliabilityManager
from routing.tool_router import BaselineRouter, ReliabilityRouter
from tools.simulated_tools import SimulatedToolA, SimulatedToolB


def build_real_tools():
    return {"tool_a": SimulatedToolA(), "tool_b": SimulatedToolB()}


class RoutingTests(unittest.TestCase):
    def test_reliability_router_selects_higher_score(self):
        router = ReliabilityRouter(
            exploration_rate=0.0,
            forced_probe_interval=0,
            min_switch_gain=0.0,
        )
        decision = router.select_tool(
            TaskInput(1, "test"),
            ["tool_a", "tool_b"],
            {"tool_a": 0.30, "tool_b": 0.80},
        )
        self.assertEqual(decision.selected_tool, "tool_b")
        self.assertFalse(decision.used_exploration)

    def test_baseline_ignores_reliability(self):
        router = BaselineRouter(preferred_tool="tool_a")
        decision = router.select_tool(
            TaskInput(1, "test"),
            ["tool_a", "tool_b"],
            {"tool_a": 0.05, "tool_b": 0.99},
        )
        self.assertEqual(decision.selected_tool, "tool_a")
        self.assertFalse(decision.used_exploration)

    def test_exploration_can_choose_alternative_tool(self):
        router = ReliabilityRouter(
            exploration_rate=1.0,
            forced_probe_interval=0,
            min_switch_gain=0.0,
            random_seed=42,
        )
        first = router.select_tool(
            TaskInput(1, "test"),
            ["tool_a", "tool_b"],
            {"tool_a": 0.9, "tool_b": 0.1},
        )
        second = router.select_tool(
            TaskInput(2, "test"),
            ["tool_a", "tool_b"],
            {"tool_a": 0.9, "tool_b": 0.1},
        )
        self.assertTrue(first.used_exploration)
        self.assertTrue(second.used_exploration)
        self.assertNotEqual(first.selected_tool, second.selected_tool)

    def test_forced_probe_revisits_ignored_tool(self):
        router = ReliabilityRouter(
            exploration_rate=0.0,
            forced_probe_interval=3,
            min_switch_gain=0.0,
        )
        decisions = [
            router.select_tool(
                TaskInput(task_id, "test"),
                ["tool_a", "tool_b"],
                {"tool_a": 0.90, "tool_b": 0.10},
            )
            for task_id in range(1, 5)
        ]
        self.assertTrue(
            any(
                d.selected_tool == "tool_b" and d.used_exploration
                for d in decisions
            )
        )

    def test_hysteresis_blocks_small_gain_switch(self):
        router = ReliabilityRouter(
            exploration_rate=0.0,
            forced_probe_interval=0,
            min_switch_gain=0.05,
        )
        first = router.select_tool(
            TaskInput(1, "test"),
            ["tool_a", "tool_b"],
            {"tool_a": 0.60, "tool_b": 0.50},
        )
        second = router.select_tool(
            TaskInput(2, "test"),
            ["tool_a", "tool_b"],
            {"tool_a": 0.60, "tool_b": 0.63},
        )
        self.assertEqual(first.selected_tool, "tool_a")
        self.assertEqual(second.selected_tool, "tool_a")

    def test_invalid_reliability_is_rejected(self):
        router = ReliabilityRouter()
        with self.assertRaises(ValueError):
            router.select_tool(
                TaskInput(1, "test"),
                ["tool_a"],
                {"tool_a": 1.20},
            )


class EvaluatorTests(unittest.TestCase):
    def _log(self, evaluator: Evaluator, task_id: int, tool_name: str, success: bool):
        scores = {"tool_a": 0.5, "tool_b": 0.5}
        task = TaskInput(task_id, f"Task {task_id}")
        decision = RoutingDecision(task_id, tool_name, dict(scores), False)
        result = ToolResult(task_id, tool_name, success, None, 0.01, None)
        evaluator.log_step(task, decision, result, scores)

    def test_compute_metrics_returns_fixed_names(self):
        evaluator = Evaluator()
        self._log(evaluator, 1, "tool_a", True)
        self.assertEqual(
            set(evaluator.compute_metrics()),
            {
                "task_success_rate",
                "failure_avoidance_rate",
                "detection_lag",
                "recovery_lag",
                "tool_switching_rate",
                "retry_count",
                "token_count",
                "avg_latency_sec",
            },
        )

    def test_csv_columns_match_config_order(self):
        evaluator = Evaluator(run_id=3)
        self._log(evaluator, 1, "tool_a", True)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "log.csv"
            evaluator.save_results(str(path))
            with path.open(encoding="utf-8-sig", newline="") as handle:
                header = next(csv.reader(handle))
        self.assertEqual(header, list(config.LOG_COLUMNS))

    def test_reset_clears_logs(self):
        evaluator = Evaluator()
        self._log(evaluator, 1, "tool_a", True)
        evaluator.reset()
        with self.assertRaises(ValueError):
            evaluator.compute_metrics()

    def test_task_id_mismatch_is_rejected(self):
        evaluator = Evaluator()
        with self.assertRaises(ValueError):
            evaluator.log_step(
                TaskInput(1, "test"),
                RoutingDecision(2, "tool_a", {"tool_a": 0.5}, False),
                ToolResult(1, "tool_a", True, None, 0.1),
                {"tool_a": 0.5, "tool_b": 0.5},
            )

    def test_selected_tool_result_mismatch_is_rejected(self):
        evaluator = Evaluator()
        with self.assertRaises(ValueError):
            evaluator.log_step(
                TaskInput(1, "test"),
                RoutingDecision(1, "tool_a", {"tool_a": 0.5}, False),
                ToolResult(1, "tool_b", True, None, 0.1),
                {"tool_a": 0.5, "tool_b": 0.5},
            )


class FullIntegrationTests(unittest.TestCase):
    def test_agent_baseline_evaluator_one_task(self):
        random.seed(42)
        evaluator = Evaluator()
        agent = AgentCore(
            tools=build_real_tools(),
            reliability_manager=ReliabilityManager(),
            router=BaselineRouter(),
            evaluator=evaluator,
        )
        result = agent.run_task(TaskInput(1, "test"))
        self.assertEqual(result.tool_name, "tool_a")
        self.assertEqual(len(evaluator._rows), 1)
        self.assertEqual(evaluator._rows[0]["tool_a_reliability"], 0.5)
        self.assertEqual(evaluator._rows[0]["tool_b_reliability"], 0.5)

    def test_reliability_scores_are_used_on_next_routing_decision(self):
        random.seed(42)
        manager = ReliabilityManager()
        router = ReliabilityRouter(
            exploration_rate=0.0,
            forced_probe_interval=0,
            min_switch_gain=0.0,
            random_seed=42,
        )
        agent = AgentCore(build_real_tools(), manager, router)
        agent.run_task(TaskInput(1, "first"))
        updated_a = manager.get_score("tool_a")
        agent.run_task(TaskInput(2, "second"))
        self.assertEqual(agent.last_decision.reliability_scores["tool_a"], updated_a)

    def test_proposed_100_tasks_tracks_degradation_and_recovery(self):
        random.seed(42)
        manager = ReliabilityManager()
        evaluator = Evaluator()
        agent = AgentCore(
            build_real_tools(),
            manager,
            ReliabilityRouter(random_seed=42),
            evaluator,
        )
        decisions = []
        for task_id in range(1, config.NUM_TASKS + 1):
            agent.run_task(TaskInput(task_id, f"Task {task_id}"))
            decisions.append(agent.last_decision)

        metrics = evaluator.compute_metrics()
        self.assertTrue(0.0 <= metrics["task_success_rate"] <= 1.0)
        self.assertTrue(0.0 <= metrics["failure_avoidance_rate"] <= 1.0)
        self.assertTrue(0.0 <= metrics["tool_switching_rate"] <= 1.0)
        self.assertGreaterEqual(metrics["avg_latency_sec"], 0.0)

        degraded = [d for d in decisions if 51 <= d.task_id <= 75]
        recovery = [d for d in decisions if 76 <= d.task_id <= 100]
        self.assertTrue(any(d.selected_tool == "tool_b" for d in degraded))
        self.assertTrue(any(d.selected_tool == "tool_a" for d in recovery))
        self.assertTrue(any(d.used_exploration for d in recovery))


if __name__ == "__main__":
    unittest.main()
