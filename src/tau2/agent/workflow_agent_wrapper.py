from typing import Optional

from loguru import logger

from tau2.agent.base import LocalAgent, ValidAgentInputMessage, is_valid_agent_history_message
from tau2.data_model.message import AssistantMessage, Message
from tau2.environment.tool import Tool

from tau2.agent.workflow_agent.flow import create_workflow_flow
from tau2.agent.workflow_agent.convert_to_tau_utils import (
    convert_message_history,
    tau2_to_workflow_message,
    workflow_to_tau2_message,
)


class WorkflowAgent(LocalAgent[dict]):
    """
    A workflow-agent that uses CSPL workflows from YAML files instead of raw policy text.
    Wraps the workflow-agent flow (LoadCodebaseNode → MatchWorkflowNode → ExecuteWorkflowNode).
    """

    def __init__(
        self,
        tools: list[Tool],
        domain_policy: str,  # Not used by workflow-agent, but required by LocalAgent
        domain: str,  # Domain name (e.g., "airline") to load codebase files
        llm: Optional[str] = None,
        llm_args: Optional[dict] = None,
    ):
        """
        Initialize the WorkflowAgent.
        
        Args:
            tools: List of tau2 tools available to the agent
            domain_policy: Domain policy (not used by workflow-agent, kept for compatibility)
            domain: Domain name to load codebase files from
            llm: LLM model name (optional, for future use)
            llm_args: LLM arguments (optional, for future use)
        """
        super().__init__(tools=tools, domain_policy=domain_policy)
        self.domain = domain
        self.llm = llm
        self.llm_args = llm_args or {}
        
        # Create workflow flow (will be reused for each message)
        self.flow = create_workflow_flow()

    def get_init_state(
        self, message_history: Optional[list[Message]] = None
    ) -> dict:
        """
        Get the initial state of the agent.
        
        Converts τ²-bench Message history to workflow-agent's conversation_history format
        and initializes the shared store dictionary.
        
        Args:
            message_history: The message history of the conversation.
            
        Returns:
            A dictionary representing the workflow-agent's shared store.
        """
        if message_history is None:
            message_history = []
        
        # Validate message history contains only valid messages
        assert all(is_valid_agent_history_message(m) for m in message_history), (
            "Message history must contain only AssistantMessage, UserMessage, or ToolMessage to Agent."
        )
        
        # Convert message history to workflow-agent conversation_history format
        conversation_history = convert_message_history(message_history)
        
        # Initialize state (only mutable conversation state)
        # Codebase files (workflows, constants, tone_config) will be loaded by LoadCodebaseNode
        # when the flow runs, not stored in agent instance
        state = {
            "conversation_history": conversation_history,
            "selected_workflow": None,
            "current_step": None,
            "extracted_fields": {},
        }
        
        return state

    def generate_next_message(
        self, message: ValidAgentInputMessage, state: dict
    ) -> tuple[AssistantMessage, dict]:
        """
        Generate the next message from a user/tool message and agent state.
        
        Converts incoming message, runs workflow-agent flow, and extracts response.
        
        Args:
            message: The user message or tool message(s).
            state: The agent state (workflow-agent's shared store).
            
        Returns:
            A tuple of an assistant message and updated state.
        """
        # Convert incoming message to workflow-agent format
        workflow_message = tau2_to_workflow_message(message)
        
        # Add message to conversation history if conversion succeeded
        if workflow_message is not None:
            state["conversation_history"].append(workflow_message)
        else:
            # Message was skipped (e.g., tool message handled separately)
            logger.debug(f"message type {type(message)} was skipped in conversion")
        
        # Create shared store for workflow-agent flow
        shared = state.copy()
        # Pass domain to LoadCodebaseNode so it can load codebase files
        shared["domain"] = self.domain
        # Pass tools to shared store (workflow executor needs them)
        shared["tools"] = self.tools
        # Codebase files (workflows, constants, tone_config) will be loaded by LoadCodebaseNode
        # into the shared store when needed
        
        # Run workflow-agent flow
        try:
            self.flow.run(shared)
            
            # Update state from shared store (only mutable fields)
            state["conversation_history"] = shared["conversation_history"]
            state["selected_workflow"] = shared.get("selected_workflow")
            state["current_step"] = shared.get("current_step")
            state["extracted_fields"] = shared.get("extracted_fields", {})
        except Exception as e:
            logger.error(f"error running workflow flow: {e}")
            # Return error message
            error_message = AssistantMessage(
                role="assistant",
                content=f"I encountered an error: {str(e)}"
            )
            return error_message, state
        
        # Extract assistant response from conversation_history
        # Find last assistant message in conversation_history
        workflow_response = None
        for msg in reversed(shared["conversation_history"]):
            if msg.get("role") == "assistant":
                workflow_response = msg
                break
        
        # Convert workflow response to τ²-bench AssistantMessage format
        if workflow_response is not None:
            assistant_message = workflow_to_tau2_message(
                workflow_response, tools=self.tools
            )
        else:
            # No assistant message found, create default response
            logger.warning("no assistant message found in conversation_history, using default")
            assistant_message = AssistantMessage(
                role="assistant",
                content="I'm processing your request."
            )
        
        # TODO (Phase 4): Handle tool calls if workflow step calls a tool
        # Tool calls will be handled separately when workflow executes use_tool actions
        
        return assistant_message, state

    def stop(
        self,
        message: Optional[ValidAgentInputMessage] = None,
        state: Optional[dict] = None,
    ) -> None:
        """
        Stops the agent.
        Can be used for cleanup if needed.
        """
        pass

    def set_seed(self, seed: int):
        """
        Set the seed for the agent.
        Currently not implemented for workflow-agent.
        """
        logger.warning(
            f"Setting seed for WorkflowAgent is not implemented"
        )
