import csv
import time
import random
from models import TaskInput
from agent.agent_core import AgentCore
from tools.simulated_tools import SimulatedToolA, SimulatedToolB
from config import NUM_TASKS, NUM_RUNS, RANDOM_SEED
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


fieldnames = [
    "run_id", "task_id", "selected_tool", "tool_success",
    "tool_a_reliability", "tool_b_reliability", "used_exploration",
    "latency_sec", "retry_count",
]

# 중간에 멈춰도 지금까지 결과는 파일에 남도록, 매 task마다 바로 씀
f = open("baseline_llm_full.csv", "w", newline="")
writer = csv.DictWriter(f, fieldnames=fieldnames)
writer.writeheader()

task_times = []
start_total = time.time()
total_tasks = NUM_TASKS * NUM_RUNS

try:
    for run_id in range(1, NUM_RUNS + 1):
        tools = {"tool_a": SimulatedToolA(), "tool_b": SimulatedToolB()}
        reliability_manager = MockReliabilityManager()
        router = LLMBaselineRouter()
        agent = AgentCore(tools=tools, reliability_manager=reliability_manager, router=router)

        for task_id in range(1, NUM_TASKS + 1):
            t0 = time.time()
            task = TaskInput(task_id=task_id, query=f"topic_{task_id}")
            result = agent.run_task(task)
            elapsed = time.time() - t0
            task_times.append(elapsed)

            decision = agent.last_decision
            scores = reliability_manager.get_all_scores()

            row = {
                "run_id": run_id,
                "task_id": task_id,
                "selected_tool": result.tool_name,
                "tool_success": int(result.success),
                "tool_a_reliability": scores.get("tool_a", 0.5),
                "tool_b_reliability": scores.get("tool_b", 0.5),
                "used_exploration": int(decision.used_exploration),
                "latency_sec": round(result.latency_sec, 3),
                "retry_count": 0,
            }
            writer.writerow(row)
            f.flush()  # 중간에 꺼져도 여기까진 파일에 저장되게

            done = len(task_times)
            avg = sum(task_times) / done
            remaining_sec = (total_tasks - done) * avg
            print(
                f"[run {run_id}/{NUM_RUNS}][{task_id}/{NUM_TASKS}] "
                f"{elapsed:.1f}s | 평균 {avg:.1f}s/task | "
                f"진행 {done}/{total_tasks} | 예상 잔여 {remaining_sec/60:.1f}분"
            )

except KeyboardInterrupt:
    print("\n중단됨 — 지금까지 결과는 baseline_llm_full.csv에 저장돼 있음")

finally:
    f.close()
    total_elapsed = time.time() - start_total
    print(f"\n총 {len(task_times)}개 완료, 총 소요시간 {total_elapsed/60:.1f}분")