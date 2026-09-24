from collections import deque
from typing import Deque, Dict, Iterable

from config import EWMA_ALPHA, RELIABILITY_METHOD, WINDOW_SIZE
from models import ToolResult


class ReliabilityManager:
    """Track independent reliability scores for the configured tools.

    Unknown tool IDs raise ``ValueError`` with the supported IDs so typos are
    explicit instead of silently creating a new reliability state.
    """

    DEFAULT_TOOL_NAMES = ("tool_a", "tool_b")
    SUPPORTED_METHODS = {"sliding_window", "ewma", "cumulative"}

    def __init__(
        self,
        method: str = RELIABILITY_METHOD,
        window_size: int = WINDOW_SIZE,
        ewma_alpha: float = EWMA_ALPHA,
        initial_score: float = 0.5,
        tool_names: Iterable[str] = DEFAULT_TOOL_NAMES,
    ) -> None:
        self.method = method
        self.window_size = window_size
        self.ewma_alpha = ewma_alpha
        self.initial_score = initial_score
        self.tool_names = tuple(tool_names)

        self._validate_configuration()
        self._histories: Dict[str, Deque[float]] = {}
        self._scores: Dict[str, float] = {}
        self._success_counts: Dict[str, int] = {}
        self._total_counts: Dict[str, int] = {}
        self.reset()

    def update(self, result: ToolResult) -> None:
        """Update the reliability state from one existing ``ToolResult``."""
        tool_name = result.tool_name
        self._validate_tool_name(tool_name)

        if not isinstance(result.success, bool):
            raise TypeError("ToolResult.success must be bool")

        observation = 1.0 if result.success else 0.0

        if self.method == "sliding_window":
            history = self._histories[tool_name]
            history.append(observation)
            new_score = sum(history) / len(history)
        elif self.method == "ewma":
            previous_score = self._scores[tool_name]
            new_score = (
                self.ewma_alpha * observation
                + (1.0 - self.ewma_alpha) * previous_score
            )
        else:  # self.method == "cumulative"
            self._total_counts[tool_name] += 1
            self._success_counts[tool_name] += int(result.success)
            new_score = (
                self._success_counts[tool_name] / self._total_counts[tool_name]
            )

        self._scores[tool_name] = self._clamp(new_score)

    def get_score(self, tool_name: str) -> float:
        """Return one tool score, raising ValueError for an unknown tool ID."""
        self._validate_tool_name(tool_name)
        return float(self._scores[tool_name])

    def get_all_scores(self) -> Dict[str, float]:
        """Return a copy suitable for passing directly to the Router."""
        return {name: float(score) for name, score in self._scores.items()}

    def reset(self) -> None:
        """Clear all histories/counters and restore neutral initial scores."""
        self._histories = {
            name: deque(maxlen=self.window_size) for name in self.tool_names
        }
        self._scores = {name: float(self.initial_score) for name in self.tool_names}
        self._success_counts = {name: 0 for name in self.tool_names}
        self._total_counts = {name: 0 for name in self.tool_names}

    def _validate_configuration(self) -> None:
        if self.method not in self.SUPPORTED_METHODS:
            supported = ", ".join(sorted(self.SUPPORTED_METHODS))
            raise ValueError(
                f"Unsupported reliability method '{self.method}'. "
                f"Supported methods: {supported}"
            )
        if not self.tool_names:
            raise ValueError("tool_names must contain at least one tool ID")
        if len(set(self.tool_names)) != len(self.tool_names):
            raise ValueError("tool_names must not contain duplicates")
        if self.window_size <= 0:
            raise ValueError("window_size must be greater than 0")
        if not 0.0 < self.ewma_alpha <= 1.0:
            raise ValueError("ewma_alpha must satisfy 0.0 < alpha <= 1.0")
        if not 0.0 <= self.initial_score <= 1.0:
            raise ValueError("initial_score must be in the range [0.0, 1.0]")

    def _validate_tool_name(self, tool_name: str) -> None:
        if tool_name not in self._scores:
            supported = ", ".join(self.tool_names)
            raise ValueError(
                f"Unknown tool_name '{tool_name}'. Supported tool IDs: {supported}"
            )

    @staticmethod
    def _clamp(score: float) -> float:
        return min(1.0, max(0.0, float(score)))
