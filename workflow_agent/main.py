import os
import sys
import yaml
from loguru import logger
from typing import Optional, Any

# Configure logger to show only messages (no timestamps, levels, file names, or function names)
def simple_sink(message):
    """Custom sink that prints only the message content"""
    sys.stderr.write(message.record["message"] + "\n")
    sys.stderr.flush()

logger.remove()
logger.add(simple_sink)

from tau2.agent.base import LocalAgent, AgentState
from tau2.data_model.message import (
    AssistantMessage, 
    Message, 
    UserMessage,
    ToolMessage,
    MultiToolMessage,
    SystemMessage
)
from tau2.environment.tool import Tool

from .memory.manager import MemoryManager
from .processor import orchestrator
from .tools import ToolExecutor

# Load configuration files
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(BASE_DIR)) # Adjust based on where this file is
# Actually, let's look for absolute paths or relative to repository root
# User provided paths: data/tau2/domains/airline/codebase/workflow.yaml

DOMAIN_PATH = os.path.join(os.getcwd(), "data/tau2/domains/airline/codebase")
WORKFLOW_FILE = os.path.join(DOMAIN_PATH, "workflow.yaml")
TONE_FILE = os.path.join(DOMAIN_PATH, "tone.yaml")
CONSTANTS_FILE = os.path.join(DOMAIN_PATH, "constants.yaml")

from tau2.agent.llm_agent import LLMAgent, LLMAgentState

# ...

class WorkflowAgent(LLMAgent):
    def __init__(self, tools: list[Tool], domain_policy: str, llm: Optional[str] = None, llm_args: Optional[dict] = None):
        super().__init__(tools, domain_policy, llm, llm_args)
        
        # We use self.llm as the model name
        self.model = self.llm if self.llm else "gpt-4"
        
        # Load external resources
        self.workflows = self._load_workflows()
        self.tone_text = self._load_tone()
        self.constants = self._load_constants()
        
        # Initialize internal toolset
        self.tool_executor = self._build_tool_executor(tools)

    def _load_workflows(self):
        with open(WORKFLOW_FILE, 'r') as f:
            # Load all documents and filter out None values (empty documents)
            return [w for w in yaml.safe_load_all(f) if w is not None]

    def _load_tone(self):
        with open(TONE_FILE, 'r') as f:
            data = yaml.safe_load(f)
            # Flatten or format tone data into a string?
            # The tone file has 'identity', 'tone', 'guidelines'.
            # We will format it as a string for the prompt.
            lines = []
            if 'identity' in data:
                lines.append(f"Identity: {data['identity'].get('role', '')}")
            if 'tone' in data and data['tone']:
                 lines.append(f"Tone: {data['tone']}")
            if 'guidelines' in data:
                lines.append("Guidelines:")
                for g in data['guidelines']:
                    lines.append(f"- {g}")
            return "\n".join(lines)

    def _load_constants(self):
        """
        Loads constants from constants.yaml file and returns as a dictionary.
        Returns empty dict if file doesn't exist or is empty.
        """
        try:
            with open(CONSTANTS_FILE, 'r') as f:
                data = yaml.safe_load(f)
                return data if data is not None else {}
        except FileNotFoundError:
            logger.warning(f"constants file not found: {CONSTANTS_FILE}")
            return {}
        except Exception as e:
            logger.error(f"error loading constants file: {e}")
            return {}

    def _build_tool_executor(self, tools_list):
        """
        Creates a ToolExecutor that handles workflow syntax to tool calls.
        """
        return ToolExecutor(tools_list)

    class WorkflowAgentState(LLMAgentState):
        memory: Any
        
        class Config:
            arbitrary_types_allowed = True

    def get_init_state(self, message_history: Optional[list[Message]] = None) -> WorkflowAgentState:
        # Create standard LLMAgentState parts
        if message_history is None:
            message_history = []
            
        system_messages = [SystemMessage(role="system", content="")] # Dummy, we don't use system prompt in the same way via orchestration
        
        # Initialize MemoryManager
        memory = MemoryManager()
        
        # Load constants into memory variables
        if self.constants:
            memory.set_variables(self.constants)
        
        if message_history:
            for msg in message_history:
                if isinstance(msg, UserMessage):
                    memory.add_to_history("user", msg.content)
                elif isinstance(msg, AssistantMessage) and msg.has_text_content():
                    memory.add_to_history("assistant", msg.content)
        
        return self.WorkflowAgentState(
            system_messages=system_messages,
            messages=message_history,
            memory=memory
        )

    def generate_next_message(
        self, message: UserMessage | ToolMessage | MultiToolMessage, state: WorkflowAgentState
    ) -> tuple[AssistantMessage, WorkflowAgentState]:
        
        # We only really care about UserMessages to trigger the cycle.
        user_text = ""
        if isinstance(message, UserMessage):
            user_text = message.content
        elif isinstance(message, ToolMessage):
             user_text = str(message.content)

        # Update base state messages list
        state.messages.append(message)

        response_text = orchestrator.run_workflow_cycle(
            user_text,
            state.memory,
            self.workflows,
            self.tone_text,
            self.model,
            self.tool_executor
        )
        
        # Create response
        response = AssistantMessage(
            role="assistant",
            content=response_text
        )
        
        # Update base state
        state.messages.append(response)
        
        return response, state

