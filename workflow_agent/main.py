from typing import Optional, Any
from tau2.agent.base import LocalAgent, AgentState
from tau2.data_model.message import (
    AssistantMessage, Message, UserMessage, ToolMessage, MultiToolMessage, SystemMessage
)
from tau2.environment.tool import Tool
from tau2.agent.llm_agent import LLMAgent, LLMAgentState

from .memory.manager import MemoryManager
from .processor import orchestrator
from .tools import ToolExecutor
from .utils import config_utils

# Initialize logger with custom sink
config_utils.setup_logger()

# Agent that executes multi-step workflows based on user intent
class WorkflowAgent(LLMAgent):
    def __init__(self, tools: list[Tool], domain_policy: str, llm: Optional[str] = None, llm_args: Optional[dict] = None):
        super().__init__(tools, domain_policy, llm, llm_args)
        self.model = self.llm or "gpt-4"
        
        paths = config_utils.get_config_paths()
        self.workflows = config_utils.load_workflows_and_functions(paths["workflow"], paths["function"])
        self.tone_text = config_utils.load_tone(paths["tone"])
        self.constants = config_utils.load_constants(paths["constants"])
        self.tool_executor = ToolExecutor(tools)

    class WorkflowAgentState(LLMAgentState):
        memory: Any
        class Config: arbitrary_types_allowed = True

    # Prepares the agent's initial state with history and constants
    def get_init_state(self, message_history: Optional[list[Message]] = None) -> WorkflowAgentState:
        memory = MemoryManager()
        if self.constants: memory.set_variables(self.constants)
        
        if message_history:
            for msg in message_history:
                role = "user" if isinstance(msg, UserMessage) else "assistant"
                if hasattr(msg, 'content') and msg.content:
                    memory.add_to_history(role, msg.content)
        
        return self.WorkflowAgentState(
            system_messages=[SystemMessage(role="system", content="")],
            messages=message_history or [],
            memory=memory
        )

    # Processes a user message through the workflow orchestrator
    def generate_next_message(
        self, message: UserMessage | ToolMessage | MultiToolMessage, state: WorkflowAgentState
    ) -> tuple[AssistantMessage, WorkflowAgentState]:
        user_text = message.content if hasattr(message, 'content') else str(message)
        state.messages.append(message)

        response_text = orchestrator.run_workflow_cycle(
            user_text, state.memory, self.workflows, self.tone_text, self.model, self.tool_executor
        )
        
        response = AssistantMessage(role="assistant", content=response_text)
        state.messages.append(response)
        return response, state
