"""
Message format conversion utilities between τ²-bench and workflow-agent formats.

τ²-bench uses structured message objects (UserMessage, AssistantMessage, ToolMessage, etc.)
while workflow-agent uses simple dict format: {"role": "...", "content": "..."}
"""

from typing import Optional

from loguru import logger

from tau2.data_model.message import (
    AssistantMessage,
    Message,
    MultiToolMessage,
    ToolCall,
    ToolMessage,
    UserMessage,
)
from tau2.environment.tool import Tool


def tau2_to_workflow_message(message: Message) -> Optional[dict]:
    """
    Convert a τ²-bench message to workflow-agent format.
    
    Args:
        message: A τ²-bench message (UserMessage, AssistantMessage, ToolMessage, or MultiToolMessage)
        
    Returns:
        A dict in workflow-agent format: {"role": "...", "content": "..."}
        Returns None for messages that should be skipped (e.g., tool messages handled separately)
    """
    # Handle UserMessage
    if isinstance(message, UserMessage):
        # User messages with tool calls are not valid for agent input
        # But we handle them gracefully by extracting just the content
        content = message.content or ""
        if message.tool_calls:
            logger.warning(
                "user message contains tool calls, which are not supported in workflow-agent format"
            )
        return {"role": "user", "content": content}
    
    # Handle AssistantMessage
    if isinstance(message, AssistantMessage):
        content = message.content or ""
        # Note: tool_calls in AssistantMessage are handled separately during workflow execution
        # We only include the text content in conversation_history
        if message.tool_calls:
            logger.debug(
                "assistant message contains tool calls, only text content will be included in conversation_history"
            )
        return {"role": "assistant", "content": content}
    
    # Handle ToolMessage
    if isinstance(message, ToolMessage):
        # Tool results are critical for workflow progress
        return {
            "role": "tool",
            "name": message.name,
            "content": str(message.content),
            "tool_call_id": message.id
        }
    
    # Handle MultiToolMessage
    if isinstance(message, MultiToolMessage):
        # We need to return the last tool result or a combined format depending on expectations.
        # However, workflow-agent usually expects individual messages.
        # For simplicity in this turn-based system, we'll return the last one or log a warning.
        # Actually, let's return a list if possible, but the signature says Optional[dict].
        # In Tau2, MultiToolMessage is often passed back.
        # We'll just take the last result for now as a heuristic, or the first.
        if message.tool_messages:
            last_msg = message.tool_messages[-1]
            return {
                "role": "tool",
                "name": last_msg.name,
                "content": str(last_msg.content),
                "tool_call_id": last_msg.id
            }
        return None
    
    # Unknown message type
    logger.warning(f"unknown message type: {type(message)}, skipping conversion")
    return None


def workflow_to_tau2_message(
    workflow_response: dict,
    tools: Optional[list[Tool]] = None,
) -> AssistantMessage:
    """
    Convert a workflow-agent response to τ²-bench AssistantMessage format.
    
    Args:
        workflow_response: A dict from workflow-agent, typically from conversation_history
                          Format: {"role": "assistant", "content": "..."}
                          May also contain tool call information if workflow executed a tool
        tools: Optional list of tools (for validating tool calls if needed)
        
    Returns:
        An AssistantMessage with content and optionally tool_calls
    """
    # Extract basic fields
    role = workflow_response.get("role", "assistant")
    content = workflow_response.get("content", "")
    
    # Check if there are tool calls in the response
    # Workflow-agent typically doesn't include tool calls in conversation_history
    # But we check for them in case they're added in the future
    tool_calls = None
    if "tool_calls" in workflow_response:
        tool_calls_list = workflow_response["tool_calls"]
        if tool_calls_list:
            tool_calls = []
            for tc in tool_calls_list:
                # Convert workflow tool call format to τ²-bench ToolCall format
                tool_call = ToolCall(
                    id=tc.get("id", ""),
                    name=tc.get("name", ""),
                    arguments=tc.get("arguments", {}),
                    requestor=tc.get("requestor", "assistant"),
                )
                tool_calls.append(tool_call)
    
    # Handle empty messages
    if not content and not tool_calls:
        logger.warning(
            "workflow response has no content or tool calls, using default message"
        )
        content = "I'm processing your request."
    
    # Handle messages with both text and tool calls
    # τ²-bench doesn't allow both, so we prioritize tool calls if present
    if content and tool_calls:
        logger.warning(
            "workflow response has both content and tool calls, keeping both (tau2 will validate)"
        )
    
    # Create AssistantMessage
    assistant_message = AssistantMessage(
        role="assistant",
        content=content if content else None,
        tool_calls=tool_calls,
    )
    
    return assistant_message


def convert_message_history(messages: list[Message]) -> list[dict]:
    """
    Convert a list of τ²-bench messages to workflow-agent conversation_history format.
    
    Args:
        messages: List of τ²-bench messages
        
    Returns:
        List of dicts in workflow-agent format: [{"role": "...", "content": "..."}, ...]
        Tool messages are skipped as they're handled separately during workflow execution
    """
    conversation_history = []
    
    for msg in messages:
        workflow_msg = tau2_to_workflow_message(msg)
        if workflow_msg is not None:
            conversation_history.append(workflow_msg)
    
    return conversation_history


def convert_tool_message_to_workflow_format(
    tool_message: ToolMessage,
) -> Optional[dict]:
    """
    Convert a ToolMessage to a format that can be used by workflow-agent.
    
    This is a helper function for cases where tool results need to be included
    in the conversation context. Most of the time, tool messages are handled
    separately during workflow execution.
    
    Args:
        tool_message: A τ²-bench ToolMessage
        
    Returns:
        A dict with tool result information, or None if tool messages should be skipped
    """
    # For now, we skip tool messages as they're handled separately
    # This function exists for potential future use cases
    return None


def convert_multi_tool_message_to_workflow_format(
    multi_tool_message: MultiToolMessage,
) -> Optional[list[dict]]:
    """
    Convert a MultiToolMessage to workflow-agent format.
    
    Args:
        multi_tool_message: A τ²-bench MultiToolMessage
        
    Returns:
        List of tool result dicts, or None if tool messages should be skipped
    """
    # For now, we skip tool messages as they're handled separately
    # This function exists for potential future use cases
    return None
