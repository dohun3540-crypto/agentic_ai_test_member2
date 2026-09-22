import random
from smolagents import LiteLLMModel
from models import TaskInput, RoutingDecision
from config import EXPLORATION_RATE

# GPU 없으면 "ollama_chat/qwen3:0.6b"로 바꿔서 테스트, GPU 잡히면 8b로
MODEL_ID = "ollama_chat/qwen3:8b"

_model = LiteLLMModel(
    model_id=MODEL_ID,
    api_base="http://localhost:11434",
    num_ctx=8192,
)


def _ask_llm_to_choose(task: TaskInput, candidate_tools: list, reliability_scores: dict) -> str:
    tool_desc = "\n".join(
        f"- {t}: 신뢰도 {reliability_scores.get(t, 0.5):.2f}" for t in candidate_tools
    )
    prompt = (
        f"다음 작업을 처리해야 합니다: '{task.query}'\n\n"
        f"사용 가능한 도구:\n{tool_desc}\n\n"
        f"이 작업에 가장 적합한 도구 하나만 골라서, 도구 이름만 정확히 출력하세요 "
        f"(예: tool_a 또는 tool_b). 다른 설명은 하지 마세요."
    )

    response = _model([
        {"role": "user", "content": [{"type": "text", "text": prompt}]}
    ])
    text = response.content.strip().lower()

    for t in candidate_tools:
        if t in text:
            return t

    # 파싱 실패시 폴백: 신뢰도 제일 높은 tool
    return max(candidate_tools, key=lambda t: reliability_scores.get(t, 0.5))


class LLMBaselineRouter:
    """Baseline: LLM한테 신뢰도 정보를 안 알려줌 (전부 0.5로 가림)"""
    def select_tool(self, task: TaskInput, candidate_tools: list, reliability_scores: dict) -> RoutingDecision:
        blind_scores = {t: 0.5 for t in candidate_tools}
        selected = _ask_llm_to_choose(task, candidate_tools, blind_scores)
        return RoutingDecision(
            task_id=task.task_id,
            selected_tool=selected,
            reliability_scores=reliability_scores,
            used_exploration=False,
        )


class LLMReliabilityRouter:
    """Proposed: LLM한테 실제 신뢰도 점수를 보여주고 판단시킴 + exploration"""
    def select_tool(self, task: TaskInput, candidate_tools: list, reliability_scores: dict) -> RoutingDecision:
        used_exploration = random.random() < EXPLORATION_RATE

        if used_exploration:
            selected = random.choice(candidate_tools)
        else:
            selected = _ask_llm_to_choose(task, candidate_tools, reliability_scores)

        return RoutingDecision(
            task_id=task.task_id,
            selected_tool=selected,
            reliability_scores=reliability_scores,
            used_exploration=used_exploration,
        )