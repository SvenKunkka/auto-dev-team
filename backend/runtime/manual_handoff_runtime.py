from backend.runtime.agent_runtime import (
    AgentRuntime,
    RuntimeRequest,
    RuntimeResult,
    RuntimeStatus,
)


class ManualHandoffRuntime(AgentRuntime):
    def __init__(self, agent_name: str, tool_name: str, url: str) -> None:
        self.agent_name = agent_name
        self.tool_name = tool_name
        self.url = url

    def run(self, request: RuntimeRequest) -> RuntimeResult:
        return RuntimeResult(
            agent_name=self.agent_name,
            status=RuntimeStatus.BLOCKED,
            output=(
                f"MANUAL_HANDOFF: {self.tool_name}\n"
                f"URL: {self.url}\n"
                "请完成设计并把导出文件作为任务文档上传后重试。"
            ),
            error=f"{self.tool_name} requires a human handoff",
        )
