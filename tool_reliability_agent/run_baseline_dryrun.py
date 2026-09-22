import csv
import random
from models import TaskInput, RoutingDecision
from agent.agent_core import AgentCore
from tools.simulated_tools import SimulatedToolA, SimulatedToolB
from config import NUM_TASKS, NUM_RUNS, RANDOM_SEED

random.seed(RANDOM_SEED)  # 재현성 확보


class MockReliabilityManager:
    def get_all_scores(self):
        return {"tool_a": 0.5, "tool_b": 0.5}

    def get_score(self, tool_name):
        return 0.5

    def update(self, result):
        pass

    def reset(self):
        pass


class MockBaselineRouter:
    def select_tool(self, task, candidate_tools, reliability_scores):
        selected = random.choice(candidate_tools)
        return RoutingDecision(
            task_id=task.task_id,
            selected_tool=selected,
            reliability_scores=reliability_scores,
            used_exploration=False,  # Baseline은 exploration 개념 자체가 없음
        )


all_logs = []
for run_id in range(1, NUM_RUNS + 1):
    tools = {"tool_a": SimulatedToolA(), "tool_b": SimulatedToolB()}
    reliability_manager = MockReliabilityManager()
    router = MockBaselineRouter()
    agent = AgentCore(tools=tools, reliability_manager=reliability_manager, router=router)

    for task_id in range(1, NUM_TASKS + 1):
        task = TaskInput(task_id=task_id, query=f"topic_{task_id}")
        result = agent.run_task(task)
        decision = agent.last_decision  # agent_core.py에서 저장해둔 마지막 라우팅 결정

        scores = reliability_manager.get_all_scores()

        all_logs.append({
            "run_id": run_id,
            "task_id": task_id,
            "selected_tool": result.tool_name,
            "tool_success": int(result.success),
            "tool_a_reliability": scores.get("tool_a", 0.5),
            "tool_b_reliability": scores.get("tool_b", 0.5),
            "used_exploration": int(decision.used_exploration),
            "latency_sec": result.latency_sec,
            "retry_count": 0,  # 재시도 로직 아직 없음 — 고정값
        })

with open("baseline_provisional_results.csv", "w", newline="") as f:
    fieldnames = [
        "run_id", "task_id", "selected_tool", "tool_success",
        "tool_a_reliability", "tool_b_reliability", "used_exploration",
        "latency_sec", "retry_count",
    ]
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(all_logs)

print(f"{len(all_logs)}개 row 저장 완료 (컬럼 {len(fieldnames)}개)")