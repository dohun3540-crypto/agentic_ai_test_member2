from models import TaskInput, ToolResult

class BaseTool:
    def run(self, task: TaskInput) -> ToolResult:
        raise NotImplementedError