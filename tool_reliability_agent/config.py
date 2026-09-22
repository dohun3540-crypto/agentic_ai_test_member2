NUM_TASKS = 100
NUM_RUNS = 10
RANDOM_SEED = 42

TOOL_A_SUCCESS_SCHEDULE = {
    (1, 25): 0.95,
    (26, 50): 0.60,
    (51, 75): 0.20,
    (76, 100): 0.95,
}
TOOL_B_SUCCESS_RATE = 0.80

# 2번 Reliability 설정
RELIABILITY_METHOD = "sliding_window"
WINDOW_SIZE = 10
EWMA_ALPHA = 0.30
EXPLORATION_RATE = 0.10

# 3번 Routing / Evaluation 설정
INITIAL_RELIABILITY = 0.50
FORCED_PROBE_INTERVAL = 10
MIN_SWITCH_GAIN = 0.05
BASELINE_PREFERRED_TOOL = "tool_a"
TOOL_IDS = ("tool_a", "tool_b")

LOG_COLUMNS = (
    "run_id",
    "task_id",
    "selected_tool",
    "tool_success",
    "tool_a_reliability",
    "tool_b_reliability",
    "used_exploration",
    "latency_sec",
    "retry_count",
)


def get_tool_success_probability(tool_name: str, task_id: int) -> float:
    """Return the simulation ground-truth success probability for evaluation."""
    if tool_name == "tool_a":
        for (start, end), probability in TOOL_A_SUCCESS_SCHEDULE.items():
            if start <= task_id <= end:
                return probability
        raise ValueError(f"task_id {task_id} is outside Tool A schedule")
    if tool_name == "tool_b":
        return TOOL_B_SUCCESS_RATE
    raise ValueError(f"Unknown tool ID: {tool_name}")
