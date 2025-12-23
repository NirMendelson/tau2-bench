import json
import litellm
import os
from loguru import logger
from ..actions import prompts

DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

class StepExecutionResult:
    def __init__(self, status, message=None, next_step_id=None, result=None):
        self.status = status  # 'completed', 'blocking', 'failed'
        self.message = message
        self.next_step_id = next_step_id
        self.result = result

def clean_json_response(response_text):
    """
    Cleans the LLM response to ensure it's valid JSON/YAML.
    Removes markdown code blocks if present.
    """
    response_text = response_text.strip()
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        # Remove first line (```yaml or ```json)
        lines = lines[1:]
        # Remove last line if it is ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        response_text = "\n".join(lines)
    return response_text

def execute_fetch(step, memory, conversation, tone_text, llm_model):
    """
    Checks if field exists in conversation. If yes, sets variable. If no, asks user.
    """
    field = step.get('field')
    fields = step.get('fields')
    
    # Handle single or multiple fields
    target_fields = fields if fields else [field]
    
    # Check if we already have them in memory? 
    # The requirement says "check if the field exists in the conversation".
    # But usually we check memory first to avoid re-extraction.
    # However, for "fetch", we might want to ensure it's in the CURRENT conversation context 
    # or just use memory. Let's assume memory is the source of truth.
    
    missing_fields = [f for f in target_fields if not memory.get_variable(f)]
    
    if not missing_fields:
        return StepExecutionResult("completed")
    
    # We need to fetch the first missing field (or all?)
    # The prompt handles one field at a time usually, or we can adapt it.
    # Let's handle one by one for simplicity as per the prompt structure.
    target_field = missing_fields[0]
    
    # Get prompt
    conv_text = memory.get_history_as_text()
    prompt = prompts.get_fetch_prompt(target_field, conv_text, tone_text)
    
    if DEBUG_MODE:
        logger.info(f"DEBUG PROMPT (fetch): {prompt}")

    response = litellm.completion(
        model=llm_model,
        messages=[{"role": "user", "content": prompt}]
    )
    
    content = clean_json_response(response.choices[0].message.content)
    
    try:
        # Parse YAML/JSON result
        import yaml
        result = yaml.safe_load(content)
        
        if result.get('found'):
            memory.set_variable(target_field, result.get('value'))
            # Recursively check if we have more missing fields
            return execute_fetch(step, memory, conversation, tone_text, llm_model)
        else:
            return StepExecutionResult("blocking", message=result.get('question'))
            
    except Exception as e:
        # Fallback if parsing fails
        print(f"Error parsing fetch response: {e}")
        return StepExecutionResult("failed", message="Failed to extract information.")

def execute_fetch_with_condition(step, memory, conversation, tone_text, llm_model):
    """
    Checks if field exists and satisfies condition. If not, asks user or re-fetches.
    """
    field = step.get('field')
    condition = step.get('condition')
    condition_str = json.dumps(condition) # Pass the structural condition for context
    
    # Check memory first
    val = memory.get_variable(field)
    
    conv_text = memory.get_history_as_text()
    prompt = prompts.get_fetch_with_condition_prompt(field, condition_str, conv_text, tone_text)
    
    if DEBUG_MODE:
        logger.info(f"DEBUG PROMPT (fetch_with_condition): {prompt}")

    response = litellm.completion(
        model=llm_model,
        messages=[{"role": "user", "content": prompt}]
    )
    
    content = clean_json_response(response.choices[0].message.content)
    
    try:
        import yaml
        result = yaml.safe_load(content)
        
        if result.get('found'):
            memory.set_variable(field, result.get('value'))
            
            # Use the LLM's evaluation of the condition
            condition_met = result.get('condition_result')
            
            # If explicit 'true'/'false' string, convert to boolean
            if isinstance(condition_met, str):
                condition_met = condition_met.lower() == 'true'
            
            if condition_met:
                # Condition met -> execute 'then' steps
                # The orchestrator handles nested steps. We just return 'completed'
                # But wait, looking at the YAML, 'fetch_with_condition' acts as a branch node
                # It has 'then' and 'else'.
                
                # If we return 'completed', we need to tell the orchestrator WHICH path to take?
                # Actually, the orchestrator should handle the 'then'/'else' logic based on the result.
                # But step_executor usually handles single steps.
                # Let's modify StepExecutionResult to support branching direction or let orchestrator handle it.
                
                # If we are here, we found the value AND condition is true.
                # The orchestrator should look at 'then'
                return StepExecutionResult("completed", result={"condition": True})
            else:
                # Found value but condition false
                return StepExecutionResult("completed", result={"condition": False})
        else:
            # Not found -> ask question
            return StepExecutionResult("blocking", message=result.get('question'))
            
    except Exception as e:
        print(f"Error parsing fetch_condition response: {e}")
        return StepExecutionResult("failed")

def execute_fetch_with_message(step, memory, conversation, tone_text, llm_model):
    """
    Sends a specific question and fetches the answer to a variable.
    But in a turn-based execution, we first need to SEND the message if we haven't yet.
    """
    field = step.get('field')
    message_template = step.get('message')
    
    # Check if we already have the variable
    if memory.get_variable(field):
        return StepExecutionResult("completed")
    
    # Resolve templates in message
    resolved_message = memory.resolve_templates(message_template)
    
    # Generate message with tone
    conv_text = memory.get_history_as_text()
    prompt = prompts.get_fetch_with_message_prompt(resolved_message, conv_text, tone_text)
    
    if DEBUG_MODE:
        logger.info(f"DEBUG PROMPT (fetch_with_message): {prompt}")

    response = litellm.completion(
        model=llm_model,
        messages=[{"role": "user", "content": prompt}]
    )
    
    final_message = response.choices[0].message.content.strip()
    
    # This is blocking because we need to wait for the user's answer
    return StepExecutionResult("blocking", message=final_message)

def execute_reply(step, memory, conversation, tone_text, llm_model):
    """
    Sends a message to the user based on the reply action.
    """
    message_template = step.get('message')
    resolved_message = memory.resolve_templates(message_template)
    
    conv_text = memory.get_history_as_text()
    prompt = prompts.get_reply_prompt(resolved_message, tone_text, conv_text)
    
    if DEBUG_MODE:
        logger.info(f"DEBUG PROMPT (reply): {prompt}")

    response = litellm.completion(
        model=llm_model,
        messages=[{"role": "user", "content": prompt}]
    )
    
    final_message = response.choices[0].message.content.strip()
    return StepExecutionResult("blocking", message=final_message)

def execute_set_variable(step, memory):
    """
    Directly sets a variable in memory.
    """
    variable = step.get('variable')
    value = step.get('value')
    # Resolve value if it's a template
    if isinstance(value, str):
        value = memory.resolve_templates(value)
    
    memory.set_variable(variable, value)
    return StepExecutionResult("completed")

def execute_condition(step, memory, conversation, tone_text, llm_model):
    """
    Evaluates a condition and determines which steps to follow next.
    """
    condition = step.get('condition')
    # Use LLM to evaluate complex conditions if needed
    # The condition object has 'operator', 'left', 'right' usually
    
    operator = condition.get('operator')
    left = condition.get('left')
    right = condition.get('right')
    
    # Resolve templates
    left_val = memory.resolve_templates(left) if isinstance(left, str) else left
    right_val = memory.resolve_templates(right) if isinstance(right, str) else right
    
    is_true = False
    
    # Simple operators we can handle in Python
    if operator == 'eq':
        if isinstance(right, list): # Check if list
            is_true = left_val in right # Check if in list
        else:
            is_true = str(left_val) == str(right_val)
    elif operator == 'gt':
        try:
            is_true = float(left_val) > float(right_val)
        except: is_true = False
    elif operator == 'gte':
        try:
            is_true = float(left_val) >= float(right_val)
        except: is_true = False
    elif operator == 'lt':
        try:
            is_true = float(left_val) < float(right_val)
        except: is_true = False
    elif operator == 'lte' or operator == 'less_equal':
        try:
            is_true = float(left_val) <= float(right_val)
        except: is_true = False
    elif operator == 'contains':
        is_true = str(right_val) in str(left_val)
    else:
        # Fallback to LLM for complex/unknown operators
        conv_text = memory.get_history_as_text()
        prompt = prompts.get_condition_eval_prompt(json.dumps(condition), str(memory.variables), conv_text)
        
        if DEBUG_MODE:
            logger.info(f"DEBUG PROMPT (condition): {prompt}")
            
        response = litellm.completion(model=llm_model, messages=[{"role": "user", "content": prompt}])
        is_true = response.choices[0].message.content.strip().lower() == 'true'
        
    return StepExecutionResult("completed", result={"condition": is_true})

def execute_use_tool(step, memory, tools):
    """
    Calls an external tool (e.g., airline tools) and handles the output.
    """
    tool_name = step.get('tool_name')
    
    # Special handling for calculate
    if tool_name == 'calculate':
        expression = step.get('expression')
        resolved_expr = memory.resolve_templates(expression)
        try:
            result = tools.calculate(resolved_expr)
            # Calculate usually implies we store the result implicitly or explicitly
            # The YAML usually has 'set_variables' or we use 'calculate_result'?
            # Let's check if the result is needed clearly.
            # Usually tool results are stored in a variable named "{tool_name}_result" by default?
            # Or the step has explicit variable setting?
            
            # Default storage
            memory.set_variable(f"{tool_name}_result", result)
             # Also store as calculate_result as per some workflow examples
            memory.set_variable("calculate_result", result)
            
            return StepExecutionResult("completed")
        except Exception as e:
            print(f"Calculation failed: {e}")
            return StepExecutionResult("failed")

    # Generic tool call
    if not hasattr(tools, tool_name):
        return StepExecutionResult("failed", message=f"Tool {tool_name} not found")
        
    tool_func = getattr(tools, tool_name)
    
    # Prepare arguments
    # The step arguments are all keys except id, action, tool_name, set_variables, filter
    tool_args = {}
    for key, value in step.items():
        if key in ['id', 'action', 'tool_name', 'set_variables', 'filter', 'then', 'else']:
            continue
        # Resolve templates in argument values
        if isinstance(value, str):
             tool_args[key] = memory.resolve_templates(value)
        elif isinstance(value, list):
             # Resolve list of strings
             tool_args[key] = [memory.resolve_templates(v) if isinstance(v, str) else v for v in value]
        else:
             tool_args[key] = value
             
    # Clean up args (some args might be passed as "input" list for some tools?)
    # Looking at YAML: `input: ["{{ user_id }}", ...]` for book_reservation
    if 'input' in tool_args and tool_name == 'book_reservation':
        # Map input list to actual arguments for book_reservation?
        # Or does book_reservation take distinct args?
        # The tools.py definition shows distinct args.
        # This implies we need to map the list 'input' to the function args in order.
        # This is tricky without introspection or strict contract.
        # Let's check tools.py again. book_reservation signature:
        # (user_id, origin, destination, flight_type, cabin, flights, ...)
        
        # If 'input' is passed, we might need to unpack it.
        # But 'book_reservation' step in YAML line 209 has `input` as a list.
        # We need to unpack `input` to *args.
        inp = tool_args.pop('input')
        if isinstance(inp, list):
            # We will use *inp for the function call? 
            # But we also have keyword args. logic is clearer if we use kwargs.
            # But if the YAML gives a list, we must map positionally.
            try:
                # Introspection to get arg names? 
                # Or just assume the order matches?
                # Let's assume order matches for now or try to map.
                # Actually, tools.py uses type hints.
                result = tool_func(*inp)
            except Exception as e:
                print(f"Tool call failed with positional args: {e}")
                return StepExecutionResult("failed")
        else:
             # Single input?
             result = tool_func(inp)
             
    else:
        # Use kwargs
        try:
             result = tool_func(**tool_args)
        except Exception as e:
             print(f"Tool call {tool_name} failed: {e}")
             return StepExecutionResult("failed", message=str(e))
    
    # Store result
    # Default: {tool_name}_result
    memory.set_variable(f"{tool_name}_result", result)
    
    # Handle set_variables mapping
    # "set_variables": ["var1", "var2"] -> map from result object attributes or dict keys
    set_vars = step.get('set_variables', [])
    if set_vars:
        # result can be Object or Dict
        for var_name in set_vars:
            val = None
            if isinstance(result, dict):
                val = result.get(var_name)
            elif hasattr(result, var_name):
                val = getattr(result, var_name)
            
            if val is not None:
                memory.set_variable(var_name, val)
                
    return StepExecutionResult("completed")

def handle_fallback(memory, tools):
    """
    Executes the fallback action (transfer to human) when data or logic path is missing.
    """
    result = tools.transfer_to_human_agents("Workflow fallback triggered")
    return StepExecutionResult("blocking", message=result)

def execute_step(step, memory, conversation, tone_text, llm_model, tools):
    """
    Main entry point for executing an individual step based on its action type.
    """
    if DEBUG_MODE:
        logger.info(f"DEBUG STEP EXECUTION: {step}")

    action = step.get('action')
    
    if action == 'fetch':
        return execute_fetch(step, memory, conversation, tone_text, llm_model)
    elif action == 'fetch_with_condition':
        return execute_fetch_with_condition(step, memory, conversation, tone_text, llm_model)
    elif action == 'fetch_with_message':
        return execute_fetch_with_message(step, memory, conversation, tone_text, llm_model)
    elif action == 'reply':
        return execute_reply(step, memory, conversation, tone_text, llm_model)
    elif action == 'set_variable':
        return execute_set_variable(step, memory)
    elif action == 'conditional' or action == 'condition':
        return execute_condition(step, memory, conversation, tone_text, llm_model)
    elif action == 'use_tool':
        return execute_use_tool(step, memory, tools)
    elif action == 'use_subworkflow':
        # Handled by orchestrator usually, or we treat it as completed so orchestrator can push stack
        return StepExecutionResult("completed") # Orchestrator will see action type
        
    return StepExecutionResult("failed", message=f"Unknown action: {action}")
