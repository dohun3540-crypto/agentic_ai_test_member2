import unittest

from models import ToolResult
from reliability.reliability_manager import ReliabilityManager


def make_result(success: bool, task_id: int) -> ToolResult:
    return ToolResult(
        task_id=task_id,
        tool_name="tool_a",
        success=success,
        output=None,
        latency_sec=0.0,
        error_type=None if success else "test_failure",
    )


class ReliabilityMethodSequenceTests(unittest.TestCase):
    def test_methods_match_hand_computed_sequence(self):
        sequence = [1, 1, 1, 0, 0, 1, 0]
        expected = {
            "cumulative": [1.0, 1.0, 1.0, 0.75, 0.6, 2 / 3, 4 / 7],
            "sliding_window": [1.0, 1.0, 1.0, 2 / 3, 1 / 3, 1 / 3, 1 / 3],
            "ewma": [
                0.65,
                0.755,
                0.8285,
                0.57995,
                0.405965,
                0.5841755,
                0.40892285,
            ],
        }
        configs = {
            "cumulative": dict(method="cumulative"),
            "sliding_window": dict(method="sliding_window", window_size=3),
            "ewma": dict(method="ewma", ewma_alpha=0.3),
        }

        for method, kwargs in configs.items():
            manager = ReliabilityManager(**kwargs)
            actual = []
            for task_id, value in enumerate(sequence, start=1):
                manager.update(make_result(bool(value), task_id))
                actual.append(manager.get_score("tool_a"))

            for got, want in zip(actual, expected[method]):
                self.assertAlmostEqual(got, want, places=8)


if __name__ == "__main__":
    unittest.main()
