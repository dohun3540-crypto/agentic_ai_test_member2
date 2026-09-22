from models import TaskInput, ToolResult


class AgentCore:
    def __init__(self, tools: dict, reliability_manager, router):
        self.tools = tools
        self.reliability_manager = reliability_manager
        self.router = router
        self.last_decision = None  # Evaluator 로깅용으로 마지막 결정 보관

    def run_task(self, task: TaskInput) -> ToolResult:
        reliability_scores = self.reliability_manager.get_all_scores()

        decision = self.router.select_tool(
            task=task,
            candidate_tools=list(self.tools.keys()),
            reliability_scores=reliability_scores,
        )
        self.last_decision = decision

        selected_tool = self.tools[decision.selected_tool]
        result = selected_tool.run(task)

        self.reliability_manager.update(result)

        return result