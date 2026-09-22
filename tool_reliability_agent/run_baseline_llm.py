import csv
import random
from models import TaskInput
from agent.agent_core import AgentCore
from tools.simulated_tools import SimulatedToolA, SimulatedToolB
from config import RANDOM_SEED
from llm_router_prototype import LLMBaselineRouter

random.seed(RANDOM_SEED)


class MockReliabilityManager:
    def get_all_scores(self):
        return {"tool_a": 0.5, "tool_b": 0.5}
    def get_score(self, tool_name):
        return 0.5
    def update(self, result):
        pass
    def reset(self):
        pass


NUM_TASKS_SMALL = 10  # LLM 호출은 느려서 전체 100×10은 아직 돌리면 안 됨

tools = {"tool_a": SimulatedToolA(), "tool_b": SimulatedToolB()}
agent = AgentCore(tools=tools, reliability_manager=MockReliabilityManager(), router=LLMBaselineRouter())

logs = []
for task_id in range(1, NUM_TASKS_SMALL + 1):
    task = TaskInput(task_id=task_id, query=f"주제 {task_id}에 대한 정보를 검색")
    result = agent.run_task(task)
    logs.append({
        "task_id": task_id,
        "selected_tool": result.tool_name,
        "tool_success": int(result.success),
        "latency_sec": result.latency_sec,
    })
    print(f"[{task_id}] tool={result.tool_name} success={result.success}")

with open("baseline_llm_dryrun.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=logs[0].keys())
    writer.writeheader()
    writer.writerows(logs)

print("완료")