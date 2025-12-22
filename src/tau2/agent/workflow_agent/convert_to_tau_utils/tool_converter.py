"""
Tool format conversion utilities between τ²-bench and workflow-agent formats.

τ²-bench uses Tool objects with Pydantic params, while workflow-agent uses
simple dict format with tool_name and arguments.
"""

from typing import Dict, List, Any, Optional

from loguru import logger

from tau2.environment.tool import Tool


def convert_tau2_tools_to_workflow_format(tools: list[Tool]) -> Dict[str, Dict[str, Any]]:
    """
    Convert τ²-bench Tool objects to a format that can be used by workflow-agent.
    
    This creates a mapping of tool names to tool descriptions/schemas that can be
    used for workflow matching or tool execution.
    
    Args:
        tools: List of τ²-bench Tool objects
        
    Returns:
        A dict mapping tool names to tool information:
        {
            "tool_name": {
                "name": "tool_name",
                "description": "...",
                "schema": {...},  # OpenAI schema
                "tool": <Tool object>  # Reference to original tool
            },
            ...
        }
    """
    tool_dict = {}
    
    for tool in tools:
        tool_info = {
            "name": tool.name,
            "description": tool._get_description(),
            "schema": tool.openai_schema,
            "tool": tool,  # Keep reference to original tool for execution
        }
        tool_dict[tool.name] = tool_info
    
    return tool_dict


def execute_workflow_tool_call(
    tool_name: str,
    arguments: Dict[str, Any],
    tools: list[Tool],
    extracted_fields: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Execute a workflow tool call using τ²-bench tools.
    
    Args:
        tool_name: Name of the tool to execute (must match a τ²-bench tool name)
        arguments: Dictionary of tool arguments
        tools: List of available τ²-bench Tool objects
        extracted_fields: Optional dict of extracted fields that can be used to
                         resolve template variables in arguments
        
    Returns:
        A dict with execution results:
        {
            "success": bool,
            "result": Any,  # Tool execution result
            "error": Optional[str],  # Error message if execution failed
        }
    """
    # Find the tool by name
    tool = None
    for t in tools:
        if t.name == tool_name:
            tool = t
            break
    
    if tool is None:
        error_msg = f"tool '{tool_name}' not found in available tools"
        logger.error(error_msg)
        return {
            "success": False,
            "result": None,
            "error": error_msg,
        }
    
    # Resolve template variables in arguments using extracted_fields
    resolved_arguments = arguments.copy()
    if extracted_fields:
        for key, value in resolved_arguments.items():
            if isinstance(value, str):
                # Replace template variables like {{ field_name }}
                for field_name, field_value in extracted_fields.items():
                    value = value.replace(f"{{{{ {field_name} }}}}", str(field_value))
                    value = value.replace(f"{{{{{ {field_name} }}}}}", str(field_value))
                resolved_arguments[key] = value
    
    # Validate arguments against tool's params schema
    try:
        # Create params instance to validate arguments
        params_instance = tool.params(**resolved_arguments)
        # Convert to dict for tool call
        tool_kwargs = params_instance.model_dump()
    except Exception as e:
        error_msg = f"invalid arguments for tool '{tool_name}': {e}"
        logger.error(error_msg)
        return {
            "success": False,
            "result": None,
            "error": error_msg,
        }
    
    # Execute the tool
    try:
        result = tool(**tool_kwargs)
        logger.debug(f"successfully executed tool '{tool_name}' with arguments: {tool_kwargs}")
        return {
            "success": True,
            "result": result,
            "error": None,
        }
    except Exception as e:
        error_msg = f"error executing tool '{tool_name}': {e}"
        logger.error(error_msg)
        return {
            "success": False,
            "result": None,
            "error": error_msg,
        }


def extract_tool_arguments_from_step(
    step: Dict[str, Any],
    extracted_fields: Dict[str, str],
) -> Dict[str, Any]:
    """
    Extract tool arguments from a workflow step.
    
    Tool arguments can come from:
    1. Direct specification in step["arguments"]
    2. Direct keys in step (excluding standard workflow keys like id, action, tool_name)
    3. Template variables in arguments that reference extracted_fields
    
    Args:
        step: Workflow step dict with action="use_tool"
        extracted_fields: Dict of fields extracted during workflow execution
        
    Returns:
        Dictionary of tool arguments ready for execution
    """
    STANDARD_STEP_KEYS = {
        "id", "action", "tool_name", "set_variables", "then", "else", 
        "condition", "steps", "fields", "field", "message", "variable", 
        "value", "information", "subworkflow", "reason", "arguments"
    }
    
    # 1. Start with explicit arguments if present
    arguments = step.get("arguments", {}).copy()
    
    # 2. Add other keys that are not standard step keys
    for key, value in step.items():
        if key not in STANDARD_STEP_KEYS:
            arguments[key] = value
    
    # Resolve template variables in arguments recursively
    def resolve_templates(val):
        if isinstance(val, str):
            resolved_val = val
            for field_name, field_value in extracted_fields.items():
                resolved_val = resolved_val.replace(f"{{{{ {field_name} }}}}", str(field_value))
                resolved_val = resolved_val.replace(f"{{{{{ {field_name} }}}}}", str(field_value))
            return resolved_val
        elif isinstance(val, list):
            return [resolve_templates(item) for item in val]
        elif isinstance(val, dict):
            return {k: resolve_templates(v) for k, v in val.items()}
        return val

    resolved_arguments = {}
    for key, value in arguments.items():
        resolved_arguments[key] = resolve_templates(value)
    
    return resolved_arguments
