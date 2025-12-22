import os
from typing import Dict, List, Any, Optional
from .action_executor import (
    execute_fetch,
    execute_fetch_with_condition,
    evaluate_condition,
    execute_reply,
    execute_tool,
    execute_include
)
from .workflow_registry import build_step_registry, get_next_step_id, get_first_step_id, get_next_step


def _is_debugging_enabled():
    """Check if DEBUGGING_MODE is enabled from environment variables."""
    return os.environ.get("DEBUGGING_MODE", "").lower() in ("true", "1", "yes")


def _log_workflow_step(workflow_name: str, step_id: str, action: str, outcome: str):
    """Log workflow step execution details when debugging is enabled."""
    if not _is_debugging_enabled():
        return
    print(f"[DEBUG] workflow '{workflow_name}' step '{step_id}' action '{action}': {outcome}")


def validate_workflow_execution(selected_workflow: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not selected_workflow:
        return {
            "valid": False,
            "status": "no_workflow",
            "workflow_def": None,
            "steps": None
        }
    
    workflow_def = selected_workflow.get("definition", {})
    steps = workflow_def.get("steps", [])
    
    if not steps:
        return {
            "valid": False,
            "status": "complete",
            "workflow_def": workflow_def,
            "steps": steps
        }
    
    return {
        "valid": True,
        "status": None,
        "workflow_def": workflow_def,
        "steps": steps
    }


def get_current_step_with_fallback(
    current_step_id: Optional[str],
    steps: List[Dict[str, Any]],
    step_registry: Dict[str, Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    # If no current step, start with first step
    if not current_step_id:
        current_step_id = get_first_step_id(steps)
        if not current_step_id:
            return None
    
    # Get step from registry
    step = step_registry.get(current_step_id)
    return step


def check_and_handle_prerequisites(
    current_step_id: str,
    steps: List[Dict[str, Any]],
    constants: Dict[str, Any],
    conversation_history: List[Dict[str, str]]
) -> None:
    if current_step_id != get_first_step_id(steps):
        return
    
    default_prereqs = constants.get("default_prerequisites", [])
    for prereq_field in default_prereqs:
        # Try to extract prerequisite fields from conversation
        # This is a simplified version - in practice, you might want to use LLM
        # For now, we'll assume state is always extracted from user input
        if prereq_field == "state":
            # Extract state from conversation (e.g., "I'm from NY")
            for msg in conversation_history:
                content = msg.get("content", "").lower()
                # Simple extraction - look for "from [state]" pattern
                if "from" in content:
                    # This is a placeholder - real implementation would use LLM
                    pass


def build_step_result(
    status: str,
    next_step_id: Optional[str],
    extracted_fields: Optional[Dict[str, str]] = None,
    reply: Optional[str] = None,
    include_info: Optional[str] = None
) -> Dict[str, Any]:
    result = {
        "status": status,
        "next_step_id": next_step_id
    }
    
    if extracted_fields is not None:
        result["extracted_fields"] = extracted_fields
    
    if reply is not None:
        result["reply"] = reply
    
    if include_info is not None:
        result["include_info"] = include_info
    
    return result


def determine_workflow_status(next_step_id: Optional[str]) -> str:
    return "continue" if next_step_id else "complete"


def handle_fetch_action(
    step: Dict[str, Any],
    current_step_id: str,
    steps: List[Dict[str, Any]],
    conversation_history: List[Dict[str, str]],
    extracted_fields: Dict[str, str],
    workflow_name: str = "",
    step_registry: Optional[Dict[str, Dict[str, Any]]] = None,
    model: str = "",
    llm_args: Dict[str, Any] = {}
) -> Dict[str, Any]:
    """
    Handle fetch action. If the next step is a condition, use fetch_with_condition instead.
    """
    # Check if next step is a condition
    if step_registry:
        next_step = get_next_step(current_step_id, steps, step_registry)
        if next_step and next_step.get("action") == "conditional":
            # Use combined fetch_with_condition action
            return handle_fetch_with_condition_action(
                step, next_step, current_step_id, steps, conversation_history, 
                extracted_fields, workflow_name, step_registry, model, llm_args
            )
    
    # Regular fetch action
    result = execute_fetch(step, conversation_history, model, llm_args)
    
    if result.get("found"):
        # Fields found - extract values and continue to next step
        found_fields = result.get("fields", {})
        for field_name, field_data in found_fields.items():
            if field_data.get("found"):
                extracted_fields[field_name] = field_data.get("value")
        
        next_step_id = get_next_step_id(current_step_id, steps)
        status = determine_workflow_status(next_step_id)
        
        fields_preview = ", ".join([f"{k}={str(v.get('value'))[:20]}" for k, v in found_fields.items() if v.get('found')])
        _log_workflow_step(workflow_name, current_step_id, "fetch", f"succeeded to extract fields from conversation history: {fields_preview}")
    else:
        # Some fields not found - question was asked, wait for user input
        # Stay on the same step so it can be retried when new input arrives
        next_step_id = current_step_id
        status = "waiting_for_input"
        _log_workflow_step(workflow_name, current_step_id, "fetch", f"needs to get fields from user (question asked)")
    
    return build_step_result(
        status=status,
        next_step_id=next_step_id,
        extracted_fields=extracted_fields
    )


def handle_fetch_with_condition_action(
    fetch_step: Dict[str, Any],
    condition_step: Optional[Dict[str, Any]],
    current_step_id: str,
    steps: List[Dict[str, Any]],
    conversation_history: List[Dict[str, str]],
    extracted_fields: Dict[str, str],
    workflow_name: str = "",
    step_registry: Optional[Dict[str, Dict[str, Any]]] = None,
    model: str = "",
    llm_args: Dict[str, Any] = {}
) -> Dict[str, Any]:
    """
    Handle combined fetch and condition action in a single LLM call.
    """
    # If condition_step is None, the condition is embedded in fetch_step itself
    if condition_step is None:
        condition_step = fetch_step
    
    result = execute_fetch_with_condition(fetch_step, condition_step, conversation_history, extracted_fields, model, llm_args)
    
    if result.get("found"):
        # Fields found - extract values
        found_fields = result.get("fields", {})
        for field_name, field_data in found_fields.items():
            if field_data.get("found"):
                extracted_fields[field_name] = field_data.get("value")
        
        # Evaluate condition result
        condition_result = result.get("condition_result")
        if condition_result is None:
            # If condition_result wasn't provided, evaluate it separately
            condition = condition_step.get("condition", {})
            condition_result = evaluate_condition(condition, conversation_history, extracted_fields, model, llm_args)
        
        # Get next step based on condition result
        # If fetch_step has embedded then/else branches, use fetch_step's id (current_step_id)
        # Otherwise, use condition_step's id
        if fetch_step.get("then") or fetch_step.get("else"):
            step_id_for_navigation = current_step_id
        else:
            step_id_for_navigation = condition_step.get("id") if condition_step else None
        
        if step_id_for_navigation:
            next_step_id = get_next_step_id(step_id_for_navigation, steps, condition_result)
        else:
            next_step_id = None
        
        status = determine_workflow_status(next_step_id)
        
        fields_preview = ", ".join([f"{k}={str(v.get('value'))[:20]}" for k, v in found_fields.items() if v.get('found')])
        _log_workflow_step(workflow_name, current_step_id, "fetch_with_condition", 
                          f"succeeded to extract fields: {fields_preview}, condition evaluated to {condition_result}, next step: {next_step_id}")
    else:
        # Some fields not found - question was asked, wait for user input
        # Stay on the same step so it can be retried when new input arrives
        next_step_id = current_step_id
        status = "waiting_for_input"
        _log_workflow_step(workflow_name, current_step_id, "fetch_with_condition", 
                          f"needs to get fields from user (question asked)")
    
    return build_step_result(
        status=status,
        next_step_id=next_step_id,
        extracted_fields=extracted_fields
    )


def handle_conditional_action(
    step: Dict[str, Any],
    current_step_id: str,
    steps: List[Dict[str, Any]],
    conversation_history: List[Dict[str, str]],
    extracted_fields: Dict[str, str],
    model: str,
    llm_args: Dict[str, Any],
    workflow_name: str = ""
) -> Dict[str, Any]:
    condition = step.get("condition", {})
    condition_result = evaluate_condition(condition, conversation_history, extracted_fields, model, llm_args)
    
    next_step_id = get_next_step_id(current_step_id, steps, condition_result)
    status = determine_workflow_status(next_step_id)
    
    condition_str = str(condition).replace("\n", " ")[:100]
    _log_workflow_step(workflow_name, current_step_id, "conditional", f"condition evaluated to {condition_result}, next step: {next_step_id}")
    
    return build_step_result(
        status=status,
        next_step_id=next_step_id
    )


def handle_reply_action(
    step: Dict[str, Any],
    current_step_id: str,
    steps: List[Dict[str, Any]],
    conversation_history: List[Dict[str, str]],
    tone_config: Dict[str, Any],
    extracted_fields: Dict[str, str],
    model: str,
    llm_args: Dict[str, Any],
    workflow_name: str = ""
) -> Dict[str, Any]:
    reply = execute_reply(step, conversation_history, tone_config, extracted_fields, model, llm_args)
    next_step_id = get_next_step_id(current_step_id, steps)
    
    # If there's a next step, wait for user input before continuing
    # (The next step might be a fetch that needs user response)
    if next_step_id:
        status = "waiting_for_input"
        _log_workflow_step(workflow_name, current_step_id, "reply", f"reply generated, waiting for user input, next step: {next_step_id}")
    else:
        # No next step - workflow is complete
        status = "complete"
        _log_workflow_step(workflow_name, current_step_id, "reply", "reply generated, workflow complete")
    
    return build_step_result(
        status=status,
        next_step_id=next_step_id,
        reply=reply
    )


def handle_tool_action(
    step: Dict[str, Any],
    current_step_id: str,
    steps: List[Dict[str, Any]],
    conversation_history: List[Dict[str, str]],
    tone_config: Dict[str, Any],
    tools: List,
    extracted_fields: Dict[str, str],
    model: str,
    llm_args: Dict[str, Any],
    workflow_name: str = ""
) -> Dict[str, Any]:
    """
    Handle tool action by preparing tool call for orchestrator execution or extracting result.
    """
    tool_name = step.get("tool_name", "")
    
    # Check if this tool already has a result in conversation history
    # (orchestrator adds tool results to history)
    last_msg = conversation_history[-1] if conversation_history else {}
    if last_msg.get("role") == "tool" and last_msg.get("name") == tool_name:
        # Tool execution result found!
        tool_output = last_msg.get("content", "")
        _log_workflow_step(workflow_name, current_step_id, "use_tool", f"found execution result for '{tool_name}'")
        
        # Extract variables if set_variables is specified
        set_variables = step.get("set_variables", [])
        if set_variables:
            import json
            try:
                # Try to parse tool output as JSON
                result_data = json.loads(tool_output) if isinstance(tool_output, str) else tool_output
                
                for var_name in set_variables:
                    # Extract from dict if possible, otherwise use whole output for first var
                    if isinstance(result_data, dict) and var_name in result_data:
                        extracted_fields[var_name] = result_data[var_name]
                    elif len(set_variables) == 1:
                        extracted_fields[var_name] = result_data
                    
                _log_workflow_step(workflow_name, current_step_id, "use_tool", f"extracted variables from tool result: {set_variables}")
            except Exception as e:
                # If not JSON or other error, and we only expect one variable, store the raw output
                if len(set_variables) == 1:
                    extracted_fields[set_variables[0]] = tool_output
                    _log_workflow_step(workflow_name, current_step_id, "use_tool", f"stored raw tool result in '{set_variables[0]}'")
                else:
                    print(f"error extracting variables from tool result: {e}")
        
        # Also store result with tool_name_result suffix for backward compatibility/templates
        extracted_fields[f"{tool_name}_result"] = tool_output
        
        # Move to next step
        next_step_id = get_next_step_id(current_step_id, steps)
        status = determine_workflow_status(next_step_id)
        return build_step_result(
            status=status,
            next_step_id=next_step_id,
            extracted_fields=extracted_fields
        )

    # If no result in history, prepare the tool call
    tool_result = execute_tool(step, conversation_history, tone_config, tools, extracted_fields, model, llm_args)
    
    # Handle escalation tool (executed synchronously)
    if tool_result.get("executed"):
        result_preview = str(tool_result.get("result", ""))[:50] + "..." if len(str(tool_result.get("result", ""))) > 50 else str(tool_result.get("result", ""))
        _log_workflow_step(workflow_name, current_step_id, "use_tool", f"executed escalation tool '{tool_name}' successfully, result: {result_preview}")
        next_step_id = get_next_step_id(current_step_id, steps)
        status = determine_workflow_status(next_step_id)
        return build_step_result(
            status=status,
            next_step_id=next_step_id
        )
    
    # Handle regular tool call preparation
    if tool_result.get("prepared"):
        tool_call_info = tool_result.get("tool_call_info")
        _log_workflow_step(workflow_name, current_step_id, "use_tool", f"prepared tool call for '{tool_name}', waiting for orchestrator execution")
        
        # Store tool call info in step result for ExecuteWorkflowNode to add to conversation_history
        return build_step_result(
            status="tool_call_needed",
            next_step_id=current_step_id,  # Stay on same step until tool result arrives
            tool_call_info=tool_call_info
        )
    else:
        # Tool call preparation failed
        error_msg = tool_result.get("error", "unknown error")
        _log_workflow_step(workflow_name, current_step_id, "use_tool", f"failed to prepare tool call for '{tool_name}': {error_msg}")
        
        # Add error message to conversation history
        conversation_history.append({
            "role": "assistant",
            "content": f"I encountered an error while preparing to call {tool_name}: {error_msg}"
        })
        
        # Continue to next step despite error
        next_step_id = get_next_step_id(current_step_id, steps)
        status = determine_workflow_status(next_step_id)
        
        return build_step_result(
            status=status,
            next_step_id=next_step_id
        )


def handle_set_variable_action(
    step: Dict[str, Any],
    current_step_id: str,
    steps: List[Dict[str, Any]],
    extracted_fields: Dict[str, str],
    workflow_name: str = ""
) -> Dict[str, Any]:
    """
    Handle set_variable action.
    """
    variable = step.get("variable")
    value = step.get("value")
    
    if variable:
        # Resolve value if it's a template
        resolved_value = str(value)
        for f_name, f_val in extracted_fields.items():
            resolved_value = resolved_value.replace(f"{{{{ {f_name} }}}}", str(f_val))
            resolved_value = resolved_value.replace(f"{{{{{ {f_name} }}}}}", str(f_val))
        
        extracted_fields[variable] = resolved_value
        _log_workflow_step(workflow_name, current_step_id, "set_variable", f"set '{variable}' to '{resolved_value}'")
    
    next_step_id = get_next_step_id(current_step_id, steps)
    status = determine_workflow_status(next_step_id)
    
    return build_step_result(
        status=status,
        next_step_id=next_step_id,
        extracted_fields=extracted_fields
    )


def handle_include_action(
    step: Dict[str, Any],
    current_step_id: str,
    steps: List[Dict[str, Any]],
    conversation_history: List[Dict[str, str]],
    tone_config: Dict[str, Any],
    model: str,
    llm_args: Dict[str, Any],
    workflow_name: str = ""
) -> Dict[str, Any]:
    reply = execute_include(step, conversation_history, tone_config, model, llm_args)
    next_step_id = get_next_step_id(current_step_id, steps)
    
    # If there's a next step, wait for user input before continuing
    # (The next step might be a fetch that needs user response)
    if next_step_id:
        status = "waiting_for_input"
        _log_workflow_step(workflow_name, current_step_id, "include", f"included content, waiting for user input, next step: {next_step_id}")
    else:
        # No next step - workflow is complete
        status = "complete"
        _log_workflow_step(workflow_name, current_step_id, "include", "included content, workflow complete")
    
    return build_step_result(
        status=status,
        next_step_id=next_step_id,
        reply=reply
    )


def execute_workflow_step(prep_res: Dict[str, Any]) -> Dict[str, Any]:
    # Extract context
    selected_workflow = prep_res["selected_workflow"]
    current_step_id = prep_res["current_step"].get("step_id") if prep_res["current_step"] else None
    conversation_history = prep_res["conversation_history"]
    constants = prep_res["constants"]
    tone_config = prep_res["tone_config"]
    extracted_fields = prep_res["extracted_fields"]
    tools = prep_res.get("tools", [])
    model = prep_res.get("llm")
    llm_args = prep_res.get("llm_args", {})
    
    # Get workflow name for logging
    workflow_name = selected_workflow.get("name", "unknown") if selected_workflow else "none"
    
    # Validate workflow
    validation = validate_workflow_execution(selected_workflow)
    if not validation["valid"]:
        if _is_debugging_enabled():
            print(f"[DEBUG] workflow '{workflow_name}': {validation['status']}")
        return build_step_result(
            status=validation["status"],
            next_step_id=None
        )
    
    steps = validation["steps"]
    
    # Build step registry
    step_registry = build_step_registry(steps)
    
    # Get current step
    step = get_current_step_with_fallback(current_step_id, steps, step_registry)
    if not step:
        if _is_debugging_enabled():
            print(f"[DEBUG] workflow '{workflow_name}': no step found, workflow complete")
        return build_step_result(
            status="complete",
            next_step_id=None
        )
    
    # Update current_step_id if it was None (initialized to first step)
    if not current_step_id:
        current_step_id = step.get("id")
    
    # Handle container steps (steps with nested steps but no action)
    # If this is a container step, automatically proceed to its first nested step
    if "steps" in step and not step.get("action"):
        nested_steps = step.get("steps", [])
        if nested_steps:
            first_nested_step_id = get_first_step_id(nested_steps)
            if first_nested_step_id:
                # Recursively process the first nested step
                # Update current_step_id to the first nested step
                current_step_id = first_nested_step_id
                # Get the nested step from registry
                step = step_registry.get(first_nested_step_id)
                if not step:
                    if _is_debugging_enabled():
                        print(f"[DEBUG] workflow '{workflow_name}': nested step '{first_nested_step_id}' not found in registry")
                    return build_step_result(
                        status="complete",
                        next_step_id=None
                    )
            else:
                # Container step with no nested steps - treat as complete
                if _is_debugging_enabled():
                    print(f"[DEBUG] workflow '{workflow_name}': container step '{current_step_id}' has no nested steps")
                return build_step_result(
                    status="complete",
                    next_step_id=None
                )
    
    # Check prerequisites if this is the first step
    check_and_handle_prerequisites(current_step_id, steps, constants, conversation_history)
    
    # Route to appropriate action handler
    action = step.get("action", "")
    
    if action == "fetch" or action == "fetch_with_message":
        return handle_fetch_action(
            step, current_step_id, steps, conversation_history, extracted_fields, workflow_name, step_registry, model, llm_args
        )
    elif action == "fetch_with_condition":
        # This action type can be explicitly set in workflow YAML
        # Check if step has embedded condition with then/else branches
        if step.get("condition") and (step.get("then") or step.get("else")):
            # fetch_with_condition with embedded branches - handle directly
            return handle_fetch_with_condition_action(
                step, None, current_step_id, steps, conversation_history, 
                extracted_fields, workflow_name, step_registry, model, llm_args
            )
        else:
            # Find the condition step (should be the next step)
            next_step = get_next_step(current_step_id, steps, step_registry)
            if next_step and next_step.get("action") == "conditional":
                return handle_fetch_with_condition_action(
                    step, next_step, current_step_id, steps, conversation_history, 
                    extracted_fields, workflow_name, step_registry, model, llm_args
                )
            else:
                # Fallback to regular fetch if no condition step found
                return handle_fetch_action(
                    step, current_step_id, steps, conversation_history, extracted_fields, workflow_name, step_registry, model, llm_args
                )
    elif action == "conditional":
        return handle_conditional_action(
            step, current_step_id, steps, conversation_history, extracted_fields, model, llm_args, workflow_name
        )
    elif action == "reply":
        return handle_reply_action(
            step, current_step_id, steps, conversation_history, tone_config, extracted_fields, model, llm_args, workflow_name
        )
    elif action == "use_tool":
        return handle_tool_action(
            step, current_step_id, steps, conversation_history, tone_config, tools, extracted_fields, model, llm_args, workflow_name
        )
    elif action == "set_variable":
        return handle_set_variable_action(
            step, current_step_id, steps, extracted_fields, workflow_name
        )
    elif action == "include":
        return handle_include_action(
            step, current_step_id, steps, conversation_history, tone_config, model, llm_args, workflow_name
        )
    else:
        raise ValueError(f"unknown action type: '{action}' in step '{current_step_id}'")

