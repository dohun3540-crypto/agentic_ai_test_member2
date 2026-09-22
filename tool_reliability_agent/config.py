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

# 아래는 2번 담당 영역이지만 구조상 같은 파일에 있어야 하니 값만 비워둬도 됨
RELIABILITY_METHOD = "sliding_window"
WINDOW_SIZE = 10
EWMA_ALPHA = 0.30
EXPLORATION_RATE = 0.10