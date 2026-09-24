import random
import unittest

from agent.agent_core import AgentCore
from models import RoutingDecision, TaskInput, ToolResult
from reliability.reliability_manager import ReliabilityManager
from tools.simulated_tools import SimulatedToolA, SimulatedToolB


def make_result(tool_name: str, success: bool, task_id: int = 1) -> ToolResult:
    return ToolResult(
        task_id=task_id,
        tool_name=tool_name,
        success=success,
        output=None,
        latency_sec=0.0,
        error_type=None if success else "test_failure",
    )


class AlwaysToolARouter:
    def select_tool(self, task, candidate_tools, reliability_scores):
        return RoutingDecision(
            task_id=task.task_id,
            selected_tool="tool_a",
            reliability_scores=dict(reliability_scores),
            used_exploration=False,
        )


class ReliabilityManagerTests(unittest.TestCase):
    def test_initial_tool_a_score_is_neutral(self):
        manager = ReliabilityManager()
        self.assertEqual(manager.get_score("tool_a"), 0.5)

    def test_initial_tool_b_score_is_neutral(self):
        manager = ReliabilityManager()
        self.assertEqual(manager.get_score("tool_b"), 0.5)

    def test_sliding_window_successes_increase_score(self):
        manager = ReliabilityManager(method="sliding_window", window_size=3)
        for task_id in range(1, 4):
            manager.update(make_result("tool_a", True, task_id))
        self.assertGreater(manager.get_score("tool_a"), 0.5)
        self.assertEqual(manager.get_score("tool_a"), 1.0)

    def test_sliding_window_failures_decrease_score(self):
        manager = ReliabilityManager(method="sliding_window", window_size=3)
        for task_id in range(1, 4):
            manager.update(make_result("tool_a", False, task_id))
        self.assertLess(manager.get_score("tool_a"), 0.5)
        self.assertEqual(manager.get_score("tool_a"), 0.0)

    def test_sliding_window_evicts_oldest_record(self):
        manager = ReliabilityManager(method="sliding_window", window_size=3)
        sequence = [False, True, True, True]
        for task_id, success in enumerate(sequence, start=1):
            manager.update(make_result("tool_a", success, task_id))
        self.assertEqual(manager.get_score("tool_a"), 1.0)

    def test_tool_histories_are_independent(self):
        manager = ReliabilityManager(method="sliding_window")
        manager.update(make_result("tool_a", True))
        self.assertEqual(manager.get_score("tool_a"), 1.0)
        self.assertEqual(manager.get_score("tool_b"), 0.5)

    def test_scores_always_stay_in_unit_interval(self):
        for method in ("sliding_window", "ewma", "cumulative"):
            manager = ReliabilityManager(method=method)
            for task_id in range(1, 101):
                manager.update(
                    make_result("tool_a", success=(task_id % 3 != 0), task_id=task_id)
                )
                self.assertGreaterEqual(manager.get_score("tool_a"), 0.0)
                self.assertLessEqual(manager.get_score("tool_a"), 1.0)

    def test_ewma_matches_formula(self):
        manager = ReliabilityManager(method="ewma", ewma_alpha=0.30)
        manager.update(make_result("tool_a", True))
        expected = 0.30 * 1.0 + 0.70 * 0.5
        self.assertAlmostEqual(manager.get_score("tool_a"), expected, places=12)

    def test_cumulative_initial_score_is_neutral(self):
        manager = ReliabilityManager(method="cumulative")
        self.assertEqual(manager.get_score("tool_a"), 0.5)

    def test_cumulative_first_success(self):
        manager = ReliabilityManager(method="cumulative")
        manager.update(make_result("tool_a", True))
        self.assertEqual(manager.get_score("tool_a"), 1.0)

    def test_cumulative_first_failure(self):
        manager = ReliabilityManager(method="cumulative")
        manager.update(make_result("tool_a", False))
        self.assertEqual(manager.get_score("tool_a"), 0.0)

    def test_cumulative_running_mean(self):
        manager = ReliabilityManager(method="cumulative")
        for task_id, success in enumerate([True, True, False, True], start=1):
            manager.update(make_result("tool_a", success, task_id))
        self.assertEqual(manager.get_score("tool_a"), 0.75)

    def test_cumulative_tool_independence(self):
        manager = ReliabilityManager(method="cumulative")
        manager.update(make_result("tool_a", True))
        manager.update(make_result("tool_b", False, 2))
        self.assertEqual(manager.get_all_scores(), {"tool_a": 1.0, "tool_b": 0.0})

    def test_reset_restores_all_state(self):
        for method in ("ewma", "cumulative"):
            manager = ReliabilityManager(method=method)
            manager.update(make_result("tool_a", True))
            manager.update(make_result("tool_b", False))
            manager.reset()
            self.assertEqual(manager.get_all_scores(), {"tool_a": 0.5, "tool_b": 0.5})
            if method == "cumulative":
                manager.update(make_result("tool_a", False))
                self.assertEqual(manager.get_score("tool_a"), 0.0)

    def test_get_all_scores_returns_expected_copy(self):
        manager = ReliabilityManager()
        scores = manager.get_all_scores()
        self.assertEqual(scores, {"tool_a": 0.5, "tool_b": 0.5})
        scores["tool_a"] = 0.0
        self.assertEqual(manager.get_score("tool_a"), 0.5)

    def test_invalid_method_raises_value_error(self):
        with self.assertRaises(ValueError):
            ReliabilityManager(method="not_a_method")

    def test_unknown_tool_id_raises_clear_value_error(self):
        manager = ReliabilityManager()
        with self.assertRaisesRegex(ValueError, "Unknown tool_name"):
            manager.get_score("tool_typo")

    def test_agent_core_integration_updates_reliability(self):
        random.seed(42)
        manager = ReliabilityManager(method="sliding_window", window_size=10)
        tools = {"tool_a": SimulatedToolA(), "tool_b": SimulatedToolB()}
        agent = AgentCore(
            tools=tools,
            reliability_manager=manager,
            router=AlwaysToolARouter(),
        )
        result = agent.run_task(TaskInput(task_id=1, query="integration_test"))
        self.assertEqual(result.tool_name, "tool_a")
        self.assertNotEqual(manager.get_score("tool_a"), 0.5)
        self.assertEqual(manager.get_score("tool_b"), 0.5)
        self.assertEqual(agent.last_decision.selected_tool, "tool_a")

    def test_agent_core_integration_updates_cumulative(self):
        random.seed(42)
        manager = ReliabilityManager(method="cumulative")
        tools = {"tool_a": SimulatedToolA(), "tool_b": SimulatedToolB()}
        agent = AgentCore(
            tools=tools,
            reliability_manager=manager,
            router=AlwaysToolARouter(),
        )
        result = agent.run_task(TaskInput(task_id=1, query="integration_test"))
        expected = 1.0 if result.success else 0.0
        self.assertEqual(manager.get_score("tool_a"), expected)


if __name__ == "__main__":
    unittest.main()
