import json
import litellm
import os
from loguru import logger
from ..actions import prompts
import re


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
    Checks if field(s) exist in conversation. If yes, sets variable(s). If no, asks user.
    Handles both single field and multiple fields.
    """
    field = step.get('field')
    fields = step.get('fields')
    
    # Normalize to list - handle both single field and multiple fields
    target_fields = fields if fields else [field]
    
    # Check which fields are missing from memory
    missing_fields = [f for f in target_fields if not memory.get_variable(f)]
    
    # If all fields are found, we're done
    if not missing_fields:
        return StepExecutionResult("completed")
    
    # Get conversation text
    conv_text = memory.get_history_as_text()
    
    # Format memory info for prompts
    memory_info = "\n".join([f"  {key}: {value}" for key, value in memory.variables.items()]) if memory.variables else "  (no variables set yet)"
    
    # Get comment if provided
    comment = step.get('comment')
    
    # Determine if single or multiple fields and call appropriate prompt
    is_single_field = len(target_fields) == 1
    
    if is_single_field:
        # Single field - use single field prompt
        prompt = prompts.get_fetch_single_prompt(target_fields[0], conv_text, tone_text, memory_info, comment)
    else:
        # Multiple fields - use multi-field prompt to check all at once
        prompt = prompts.get_fetch_multi_prompt(target_fields, conv_text, tone_text, memory_info, comment)
    
    if DEBUG_MODE:
        print("--- Fetch Prompt ---")
        print(prompt)
        print("--------------------------------")

    response = litellm.completion(
        model=llm_model,
        messages=[{"role": "user", "content": prompt}]
    )
    
    content = clean_json_response(response.choices[0].message.content)

    if DEBUG_MODE:
        print("---agent yaml output---")
        print(content)
    
    try:
        # Parse YAML/JSON result
        import yaml
        result = yaml.safe_load(content)
        
        # Handle response format - check if it's multi-field format or single field format
        if 'fields' in result:
            # Multi-field response format
            fields_data = result.get('fields', {})
            questions_data = result.get('questions', {})
            
            # Store found fields in memory
            for field_name in target_fields:
                if field_name in fields_data and fields_data[field_name] is not None:
                    memory.set_variable(field_name, fields_data[field_name])
            
            # Check if we now have all fields
            still_missing = [f for f in target_fields if not memory.get_variable(f)]
            
            if not still_missing:
                # All fields found - we're done
                return StepExecutionResult("completed")
            else:
                # Some or all fields still missing - ask user
                # Prefer combined question if available
                combined_question = result.get('combined_question')
                if combined_question:
                    return StepExecutionResult("blocking", message=combined_question)
                else:
                    # Combine individual questions for missing fields
                    questions = [q for f, q in questions_data.items() if f in still_missing and q]
                    if questions:
                        if len(questions) == 1:
                            return StepExecutionResult("blocking", message=questions[0])
                        else:
                            # Combine multiple questions naturally
                            combined = " ".join(questions)
                            return StepExecutionResult("blocking", message=combined)
                    else:
                        # Fallback if no questions provided
                        missing_list = ", ".join(still_missing)
                        return StepExecutionResult("blocking", message=f"Please provide: {missing_list}")
        else:
            # Single field response format (backward compatible)
            if result.get('found'):
                memory.set_variable(target_fields[0], result.get('value'))
                # Recursively check if we have more missing fields (for backward compatibility)
                return execute_fetch(step, memory, conversation, tone_text, llm_model)
            else:
                return StepExecutionResult("blocking", message=result.get('question'))
            
    except Exception as e:
        # Fallback if parsing fails
        logger.error(f"error parsing fetch response: {e}")
        return StepExecutionResult("failed", message="Failed to extract information.")

def execute_fetch_with_condition(step, memory, conversation, tone_text, llm_model):
    """
    Checks if field exists and satisfies condition. If not, asks user or re-fetches.
    Conditions are in natural language format like "{variable} = value" or "{variable} <= 5".
    """
    field = step.get('field')
    condition = step.get('condition')
    # Condition is now in natural language format (string) like "{variable} = value"
    
    # Check memory first
    val = memory.get_variable(field)
    
    conv_text = memory.get_history_as_text()
    # Format memory info for prompts
    memory_info = "\n".join([f"  {key}: {value}" for key, value in memory.variables.items()]) if memory.variables else "  (no variables set yet)"
    # Get comment if provided
    comment = step.get('comment')
    prompt = prompts.get_fetch_with_condition_prompt(field, condition, conv_text, tone_text, memory_info, comment)
    
    if DEBUG_MODE:
        print("--- Fetch with Condition Prompt ---")
        print(prompt)
        print("--------------------------------")

    response = litellm.completion(
        model=llm_model,
        messages=[{"role": "user", "content": prompt}]
    )
    
    content = clean_json_response(response.choices[0].message.content)

    if DEBUG_MODE:
        print("---agent yaml output---")
        print(content)
    
    try:
        import yaml
        result = yaml.safe_load(content)
        
        # Use the LLM's evaluation of the condition
        condition_met = result.get('condition_result')
        
        # If explicit 'true'/'false' string, convert to boolean
        if isinstance(condition_met, str):
            condition_met = condition_met.lower() == 'true'

        if result.get('found'):
            memory.set_variable(field, result.get('value'))
        
        if condition_met:
            # Condition met -> execute 'then' steps
            return StepExecutionResult("completed", result={"condition": True})
        
        if result.get('found'):
            # Found value but condition false
            return StepExecutionResult("completed", result={"condition": False})
        else:
            # Not found and condition false -> ask question
            return StepExecutionResult("blocking", message=result.get('question'))
            
    except Exception as e:
        print(f"Error parsing fetch_condition response: {e}")
        return StepExecutionResult("failed")

def execute_fetch_with_message(step, memory, conversation, tone_text, llm_model):
    """
    Checks if field(s) exist in conversation. If yes, sets variable(s). If no, asks user with the provided message.
    Handles both single field and multiple fields.
    """
    field = step.get('field')
    fields = step.get('fields')
    
    # Normalize to list - handle both single field and multiple fields
    target_fields = fields if fields else [field]
    
    # Check which fields are missing from memory
    missing_fields = [f for f in target_fields if not memory.get_variable(f)]
    
    # If all fields are found, we're done
    if not missing_fields:
        return StepExecutionResult("completed")
    
    # Resolve templates in message
    message_template = step.get('message')
    resolved_message = memory.resolve_templates(message_template)
    
    # Get conversation text
    conv_text = memory.get_history_as_text()
    
    # Call prompt with field names
    prompt = prompts.get_fetch_with_message_prompt(target_fields, resolved_message, conv_text, tone_text)
    
    if DEBUG_MODE:
        print("--- Fetch with Message Prompt ---")
        print(prompt)
        print("--------------------------------")
    
    response = litellm.completion(
        model=llm_model,
        messages=[{"role": "user", "content": prompt}]
    )
    
    content = clean_json_response(response.choices[0].message.content)

    if DEBUG_MODE:
        print("---agent yaml output---")
        print(content)
    
    try:
        # Parse YAML/JSON result
        import yaml
        result = yaml.safe_load(content)
        
        # Handle response format
        if 'fields' in result:
            # Multi-field response format
            fields_data = result.get('fields', {})
            questions_data = result.get('questions', {})
            
            # Store found fields in memory
            for field_name in target_fields:
                if field_name in fields_data and fields_data[field_name] is not None:
                    memory.set_variable(field_name, fields_data[field_name])
            
            # Check if we now have all fields
            still_missing = [f for f in target_fields if not memory.get_variable(f)]
            
            if not still_missing:
                # All fields found - we're done
                return StepExecutionResult("completed")
            else:
                # Some or all fields still missing - use the question from YAML
                # Get question for the first missing field (or combine if multiple)
                questions = [q for f, q in questions_data.items() if f in still_missing and q]
                if questions:
                    if len(questions) == 1:
                        return StepExecutionResult("blocking", message=questions[0])
                    else:
                        # Combine multiple questions naturally
                        combined = " ".join(questions)
                        return StepExecutionResult("blocking", message=combined)
                else:
                    # Fallback to the provided message if no questions in response
                    return StepExecutionResult("blocking", message=resolved_message)
        else:
            # Fallback if response format is unexpected
            logger.warning(f"unexpected response format from fetch_with_message: {result}")
            return StepExecutionResult("blocking", message=resolved_message)
            
    except Exception as e:
        # Fallback if parsing fails
        logger.error(f"error parsing fetch_with_message response: {e}")
        return StepExecutionResult("blocking", message=resolved_message)

def execute_reply(step, memory, conversation, tone_text, llm_model):
    """
    Sends a message to the user based on the reply action.
    """
    message_template = step.get('message')
    resolved_message = memory.resolve_templates(message_template)
    
    conv_text = memory.get_history_as_text()
    # Format memory info for prompts
    memory_info = "\n".join([f"  {key}: {value}" for key, value in memory.variables.items()]) if memory.variables else "  (no variables set yet)"
    prompt = prompts.get_reply_prompt(resolved_message, tone_text, conv_text, memory_info)
    
    if DEBUG_MODE:
        print("--- Reply Prompt ---")
        print(prompt)
        print("--------------------------------")

    response = litellm.completion(
        model=llm_model,
        messages=[{"role": "user", "content": prompt}]
    )
    
    final_message = response.choices[0].message.content.strip()

    if DEBUG_MODE:
        print("---agent output---")
        print(final_message)
    return StepExecutionResult("blocking", message=final_message)

def execute_reply_exact_message(step, memory, conversation, tone_text, llm_model):
    """
    Sends a message to the user based on the reply_exact_message action.
    """
    message_template = step.get('message')
    resolved_message = memory.resolve_templates(message_template)
    
    conv_text = memory.get_history_as_text()
    prompt = prompts.get_reply_exact_message_prompt(resolved_message, tone_text, conv_text)
    
    if DEBUG_MODE:
        print("--- Reply Exact Message Prompt ---")
        print(prompt)
        print("--------------------------------")

    response = litellm.completion(
        model=llm_model,
        messages=[{"role": "user", "content": prompt}]
    )
    
    final_message = response.choices[0].message.content.strip()

    if DEBUG_MODE:
        print("---agent output---")
        print(final_message)
    return StepExecutionResult("blocking", message=final_message)

def execute_set_variable(step, memory):
    """
    Directly sets a variable in memory.
    """
    variable = step.get('variable')
    value = step.get('value')
    # Resolve value if it's a template
    if isinstance(value, str):
        # Check if it's a simple variable reference like "{{ variable_name }}"
        import re
        var_ref_pattern = r'^\{\{\s*(\w+)\s*\}\}$'
        match = re.match(var_ref_pattern, value.strip())
        if match:
            # It's a direct variable reference, get the variable value directly
            var_name = match.group(1)
            value = memory.get_variable(var_name)
            if value is None:
                logger.warning(f"variable {var_name} not found in memory")
        else:
            # It's a template string, resolve it
            value = memory.resolve_templates(value)
    
    memory.set_variable(variable, value)
    return StepExecutionResult("completed")

def execute_condition(step, memory, conversation, tone_text, llm_model):
    """
    Evaluates a condition and determines which steps to follow next.
    Conditions are now in natural language format like "{variable} = value" or "{variable} <= 5".
    """
    condition = step.get('condition')
    
    # Conditions are now in natural language format (string)
    # Resolve any template variables in the condition string
    if isinstance(condition, str):
        condition_str = memory.resolve_templates(condition)
    else:
        # Fallback: if condition is still an object (old format), convert to string
        condition_str = str(condition)
    
    # Use LLM to evaluate the natural language condition
    conv_text = memory.get_history_as_text()
    # Format memory info consistently with fetch prompts
    memory_info = "\n".join([f"  {key}: {value}" for key, value in memory.variables.items()]) if memory.variables else "  (no variables set yet)"
    prompt = prompts.get_condition_eval_prompt(condition_str, memory_info, conv_text)
    
    if DEBUG_MODE:
        print("--- Condition Prompt ---")
        print(prompt)
        print("--------------------------------")
        
    response = litellm.completion(model=llm_model, messages=[{"role": "user", "content": prompt}])
    content = response.choices[0].message.content.strip()
    
    if DEBUG_MODE:
        print("---agent output---")
        print(content)
        
    is_true = content.lower() == 'true'
    
    return StepExecutionResult("completed", result={"condition": is_true})

def execute_conditional_with_message(step, memory, conversation, tone_text, llm_model):
    """
    Evaluates a condition and sends a message if specified for the result.
    Re-evaluates on each cycle until condition result matches a branch with no message.
    
    Supports:
    - message_on_true: message to send when condition is true
    - message_on_false: message to send when condition is false
    
    If a message exists for the current condition result, sends it and blocks.
    If no message exists for the current condition result, completes and continues.
    
    Uses a single LLM call to evaluate the condition and generate the message if needed.
    """
    condition = step.get('condition')
    
    # Resolve any template variables in the condition string
    if isinstance(condition, str):
        condition_str = memory.resolve_templates(condition)
    else:
        # Fallback: if condition is still an object (old format), convert to string
        condition_str = str(condition)
    
    # Resolve templates in message templates if they exist
    message_on_true = step.get('message_on_true')
    message_on_false = step.get('message_on_false')
    if message_on_true:
        message_on_true = memory.resolve_templates(message_on_true)
    if message_on_false:
        message_on_false = memory.resolve_templates(message_on_false)
    
    # Use LLM to evaluate the condition and generate message in one call
    conv_text = memory.get_history_as_text()
    # Format memory info consistently with fetch prompts
    memory_info = "\n".join([f"  {key}: {value}" for key, value in memory.variables.items()]) if memory.variables else "  (no variables set yet)"
    prompt = prompts.get_conditional_with_message_prompt(
        condition_str, 
        memory_info, 
        conv_text,
        tone_text,
        message_on_true=message_on_true,
        message_on_false=message_on_false
    )
    
    if DEBUG_MODE:
        print("--- Conditional with Message Prompt ---")
        print(prompt)
        print("--------------------------------")
        
    response = litellm.completion(model=llm_model, messages=[{"role": "user", "content": prompt}])
    content = response.choices[0].message.content.strip()
    
    if DEBUG_MODE:
        print("---agent output---")
        print(content)
        print("--------------------------------")
    
    # Parse YAML response
    try:
        import yaml
        cleaned_content = clean_json_response(content)
        result = yaml.safe_load(cleaned_content)
        
        if not result or 'condition_result' not in result:
            logger.error(f"invalid response format from conditional_with_message: {content}")
            return StepExecutionResult("failed", message="Failed to parse condition evaluation.")
        
        condition_result = result.get('condition_result')
        if isinstance(condition_result, str):
            is_true = condition_result.lower() == 'true'
        else:
            is_true = bool(condition_result)
        
        message = result.get('message')
        
        # If message was generated, send it and block
        if message and message.strip() and message.lower() != 'null':
            if DEBUG_MODE:
                logger.info(f"conditional_with_message: condition is {is_true}, message generated, blocking")
            
            # Return blocking - step will be re-executed on next cycle
            # The orchestrator will keep the step at the same index when blocking
            return StepExecutionResult("blocking", message=message.strip(), result={"condition": is_true})
        
        # No message for this condition result - we're done, continue to next step
        if DEBUG_MODE:
            logger.info(f"conditional_with_message: condition is {is_true}, no message needed, continuing to next step")
        
        return StepExecutionResult("completed", result={"condition": is_true})
        
    except Exception as e:
        logger.error(f"error parsing conditional_with_message response: {e}")
        return StepExecutionResult("failed", message="Failed to parse condition evaluation.")

def execute_use_tool(step, memory, tools):
    """
    Calls an external tool (e.g., airline tools) and handles the output.
    Uses ToolExecutor to handle workflow syntax (input lists) to tool parameters.
    """
    tool_name = step.get('tool_name')
    
    # Check if tool exists
    if not tools.has_tool(tool_name):
        return StepExecutionResult("failed", message=f"Tool {tool_name} not found")
    
    # Special handling for calculate
    if tool_name == 'calculate':
        # Support both 'expression' and 'input' fields
        expression = step.get('expression')
        if expression is None and 'input' in step:
            input_value = step.get('input')
            if isinstance(input_value, list) and len(input_value) > 0:
                # Extract expression from input list (first element)
                expression = input_value[0]
            elif isinstance(input_value, str):
                expression = input_value
        
        if expression is None:
            logger.error("calculate tool missing 'expression' or 'input' field")
            return StepExecutionResult("failed", message="calculate tool missing 'expression' or 'input' field")
        
        resolved_expr = memory.resolve_templates(expression)
        try:
            result = tools.execute('calculate', **{'expression': resolved_expr})
            
            # Handle set_variables for calculate (result is a simple value, not an object)
            set_vars = step.get('set_variables', [])
            if set_vars:
                # For calculate, the result is a simple value (string/number)
                # Store it directly in the variable name(s) specified
                if isinstance(set_vars, dict):
                    # Dict format: {"new_name": "old_name"} - but for calculate, just use new_name
                    for new_name in set_vars.keys():
                        memory.set_variable(new_name, result)
                else:
                    # List format: ["var1", "var2"] - store result in each variable
                    for item in set_vars:
                        if isinstance(item, dict):
                            # Dictionary mapping: {"new_name": "old_name"} - use new_name
                            for new_name in item.keys():
                                memory.set_variable(new_name, result)
                        else:
                            # String: store result directly in this variable name
                            var_name = item
                            memory.set_variable(var_name, result)
            else:
                # Default storage if no set_variables specified
                memory.set_variable(f"{tool_name}_result", result)
                # Also store as calculate_result as per some workflow examples
                memory.set_variable("calculate_result", result)
            
            return StepExecutionResult("completed")
        except Exception as e:
            logger.error(f"calculation failed: {e}")
            return StepExecutionResult("failed")
    
    # Prepare arguments from step
    # Extract 'input' if present (workflow syntax for positional args)
    input_list = None
    if 'input' in step:
        input_value = step['input']
        if isinstance(input_value, list):
            # Resolve templates in input list
            input_list = [memory.resolve_templates(v) if isinstance(v, str) else v for v in input_value]
        else:
            # Single value, wrap in list
            input_list = [memory.resolve_templates(input_value) if isinstance(input_value, str) else input_value]
    
    # Prepare keyword arguments (all other fields except reserved ones)
    kwargs = {}
    reserved_keys = ['id', 'action', 'tool_name', 'set_variables', 'filter', 'then', 'else', 'input']
    for key, value in step.items():
        if key in reserved_keys:
            continue
        # Resolve templates in argument values
        if isinstance(value, str):
            kwargs[key] = memory.resolve_templates(value)
        elif isinstance(value, list):
            # Resolve list of strings
            kwargs[key] = [memory.resolve_templates(v) if isinstance(v, str) else v for v in value]
        else:
            kwargs[key] = value
    
    # Execute tool using ToolExecutor
    try:
        if input_list is not None:
            # Use input list (workflow syntax)
            logger.info(f"calling tool {tool_name} with input_list: {input_list}")
            result = tools.execute(tool_name, input_list=input_list)
        elif kwargs:
            # Use keyword arguments
            logger.info(f"calling tool {tool_name} with kwargs: {kwargs}")
            result = tools.execute(tool_name, **kwargs)
        else:
            # No arguments provided
            logger.info(f"calling tool {tool_name} with no arguments")
            result = tools.execute(tool_name, input_list=[])
        logger.info(f"tool {tool_name} returned: {result} (type: {type(result)})")
    except Exception as e:
        logger.error(f"tool call {tool_name} failed: {e}")
        return StepExecutionResult("failed", message=str(e))
    
    # Handle set_variables mapping
    # Supports multiple formats:
    # - List format: ["var1", "var2"] -> map from result.var1 to var1, result.var2 to var2
    # - Dict format: {"new_name": "old_name"} -> map from result.old_name to new_name
    # - Mixed: ["var1", {"new_name": "old_name"}] -> supports both formats
    set_vars = step.get('set_variables', [])
    if set_vars:
        # If set_variables is specified, only store the extracted variables (not the full result)
        # result can be Object or Dict
        
        # Helper function to extract value from result
        def get_value_from_result(source_name):
            if isinstance(result, dict):
                return result.get(source_name)
            elif hasattr(result, source_name):
                return getattr(result, source_name)
            return None
        
        # Handle set_vars - can be a list or a dict
        if isinstance(set_vars, dict):
            # Dict format: {"new_name": "old_name"}
            for new_name, old_name in set_vars.items():
                val = get_value_from_result(old_name)
                if val is not None:
                    memory.set_variable(new_name, val)
        else:
            # List format: ["var1", "var2"] or [{"new_name": "old_name"}]
            for item in set_vars:
                if isinstance(item, dict):
                    # Dictionary mapping: {"new_name": "old_name"}
                    for new_name, old_name in item.items():
                        val = get_value_from_result(old_name)
                        if val is not None:
                            memory.set_variable(new_name, val)
                else:
                    # String: direct mapping from result.var_name to var_name
                    var_name = item
                    val = get_value_from_result(var_name)
                    if val is not None:
                        memory.set_variable(var_name, val)
    else:
        # If set_variables is not specified, store the full result
        # Default: {tool_name}_result
        result_var_name = f"{tool_name}_result"
        logger.info(f"storing tool result in {result_var_name}: {result} (type: {type(result)})")
        memory.set_variable(result_var_name, result)
                
    return StepExecutionResult("completed")

def execute_instruction(step, memory, conversation, tone_text, llm_model, tools):
    """
    Executes an instruction action where the LLM performs a complex task.
    The LLM is given an instruction, available tools, and memory context,
    and should return a value to be stored in a variable.
    """
    instruction_template = step.get('instruction')
    if not instruction_template:
        logger.error("instruction action missing 'instruction' field")
        return StepExecutionResult("failed", message="Instruction action missing 'instruction' field")
    
    # Resolve templates in instruction
    instruction_text = memory.resolve_templates(instruction_template)
    
    # Get available tools
    tools_available = step.get('tools_available', [])
    
    # Get variable name to set
    set_variable = step.get('set_variable')
    if not set_variable:
        logger.error("instruction action missing 'set_variable' field")
        return StepExecutionResult("failed", message="Instruction action missing 'set_variable' field")
    
    # Get current memory variables (for context)
    memory_variables = memory.variables
    
    # Get conversation context
    conv_text = memory.get_history_as_text()
    
    # Build prompt
    prompt = prompts.get_instruction_prompt(
        instruction_text,
        tools_available,
        memory_variables,
        conv_text,
        tone_text
    )
    
    if DEBUG_MODE:
        print("--- Instruction Prompt ---")
        print(prompt)
        print("--------------------------------")
    
    # Call LLM
    response = litellm.completion(
        model=llm_model,
        messages=[{"role": "user", "content": prompt}]
    )
    
    content = clean_json_response(response.choices[0].message.content)
    
    if DEBUG_MODE:
        print("---agent yaml output---")
        print(content)
    
    try:
        # Parse YAML response
        import yaml
        try:
            result = yaml.safe_load(content)
        except Exception:
            # Option 3: Fallback "dumb" parser if YAML fails (e.g., due to unquoted colons in values)
            result = {}
            for key in ['result', 'reasoning']:
                # Capture everything after the key until the next key or end of string
                match = re.search(fr'{key}:\s*(.*?)(?=\n\s*(?:result|reasoning)\s*:|$)', content, re.DOTALL | re.IGNORECASE)
                if match:
                    val = match.group(1).strip()
                    # Strip colons from the value as requested by the user
                    val = val.replace(':', '')
                    
                    if key == 'result':
                        if val.lower() == 'false': val = False
                        elif val.lower() == 'true': val = True
                        elif val.lower() == 'null': val = None
                    result[key] = val
        
        # Extract the result value
        result_value = result.get('result')
        
        # Store in memory
        if result_value is not None:
            memory.set_variable(set_variable, result_value)
            return StepExecutionResult("completed")
        else:
            # Task couldn't be completed
            logger.warning(f"instruction task returned null result")
            memory.set_variable(set_variable, None)
            return StepExecutionResult("completed")  # Still completed, just with null value
            
    except Exception as e:
        logger.error(f"error parsing instruction response: {e}")
        return StepExecutionResult("failed", message=f"Failed to parse instruction result: {e}")

def handle_fallback(memory, tools):
    """
    Executes the fallback action (transfer to human) when data or logic path is missing.
    """
    result = tools.execute('transfer_to_human_agents', **{'summary': "Workflow fallback triggered"})
    return StepExecutionResult("blocking", message=result)

def execute_step(step, memory, conversation, tone_text, llm_model, tools):
    """
    Main entry point for executing an individual step based on its action type.
    """

    action = step.get('action')
    
    if action == 'fetch':
        return execute_fetch(step, memory, conversation, tone_text, llm_model)
    elif action == 'fetch_with_condition':
        return execute_fetch_with_condition(step, memory, conversation, tone_text, llm_model)
    elif action == 'fetch_with_message':
        return execute_fetch_with_message(step, memory, conversation, tone_text, llm_model)
    elif action == 'reply':
        return execute_reply(step, memory, conversation, tone_text, llm_model)
    elif action == 'reply_exact_message':
        return execute_reply_exact_message(step, memory, conversation, tone_text, llm_model)
    elif action == 'set_variable':
        return execute_set_variable(step, memory)
    elif action == 'conditional' or action == 'condition':
        return execute_condition(step, memory, conversation, tone_text, llm_model)
    elif action == 'conditional_with_message':
        return execute_conditional_with_message(step, memory, conversation, tone_text, llm_model)
    elif action == 'use_tool':
        return execute_use_tool(step, memory, tools)
    elif action == 'instruction':
        return execute_instruction(step, memory, conversation, tone_text, llm_model, tools)
    elif action == 'loop':
        return execute_loop(step, memory, conversation, tone_text, llm_model, tools)
    elif action == 'use_subworkflow':
        # Handled by orchestrator usually, or we treat it as completed so orchestrator can push stack
        return StepExecutionResult("completed") # Orchestrator will see action type
        
    return StepExecutionResult("failed", message=f"Unknown action: {action}")

def execute_loop(step, memory, conversation, tone_text, llm_model, tools):
    """
    Iterates over a list, sets a loop variable, and executes a subaction for each item.
    Collects results into a list.
    """
    loop_over_var = step.get('loop_over')
    loop_variable_name = step.get('loop_variable')
    subaction = step.get('subaction')
    set_variable_name = step.get('set_variable')
    
    if not loop_over_var or not loop_variable_name or not subaction or not set_variable_name:
         return StepExecutionResult("failed", message="Loop action missing required fields (loop_over, loop_variable, subaction, set_variable)")

    # Get the list from memory
    items = []
    if isinstance(loop_over_var, list):
        items = loop_over_var
    else:
        # Try getting directly first (if it's a variable name)
        items = memory.get_variable(loop_over_var)
        
        # If not found or if it looks like a template
        if items is None and isinstance(loop_over_var, str) and "{{" in loop_over_var:
             items = memory.resolve_templates(loop_over_var)

    if not isinstance(items, (list, tuple)):
         logger.warning(f"Loop target {loop_over_var} is not a list/tuple: {items}")
         items = []

    logger.info(f"loop starting: iterating over {len(items)} items, loop_over={loop_over_var}, set_variable={set_variable_name}")

    results = []
    original_val = memory.get_variable(loop_variable_name)
    
    for item in items:
        # Set loop variable
        memory.set_variable(loop_variable_name, item)
        
        # Execute subaction
        result = execute_step(subaction, memory, conversation, tone_text, llm_model, tools)
        
        if result.status == "failed":
            logger.error(f"Loop subaction failed for item {item}: {result.message}")
            return StepExecutionResult("failed", message=f"Loop failed on item {item}: {result.message}")
        
        if result.status == "blocking":
             return result
             
        # Collection strategy
        sub_tool_name = subaction.get('tool_name')
        if sub_tool_name:
             # Check if set_variables was used in subaction
             sub_set_vars = subaction.get('set_variables')
             
             if sub_set_vars:
                 # Collect specific extracted variables into a dictionary
                 # Handle both list format ["var1"] and dict format {"new_name": "old_name"}
                 item_result = {}
                 
                 # Extract target variable names (keys for dict format, values for list format)
                 if isinstance(sub_set_vars, dict):
                     # Dict format: {"new_name": "old_name"} - collect new_name
                     target_vars = list(sub_set_vars.keys())
                 else:
                     # List format: ["var1", "var2"] or [{"new_name": "old_name"}]
                     target_vars = []
                     for item in sub_set_vars:
                         if isinstance(item, dict):
                             # Dictionary mapping: {"new_name": "old_name"} - collect new_name
                             target_vars.extend(item.keys())
                         else:
                             # String: direct variable name
                             target_vars.append(item)
                 
                 for var_name in target_vars:
                     item_result[var_name] = memory.get_variable(var_name)
                 logger.info(f"loop collected item result (with set_variables): {item_result}")
                 results.append(item_result)
             else:
                 # Default: collect the full result object
                 result_var_name = f"{sub_tool_name}_result"
                 val = memory.get_variable(result_var_name)
                 logger.info(f"loop collected tool result: {result_var_name}={val} (type: {type(val)})")
                 results.append(val)
                 
             # Clear the tool result for next iteration to prevent stale data if next call fails
             # (Though execute_use_tool usually overwrites or errors)
             if f"{sub_tool_name}_result" in memory.variables:
                  pass # Actually memory.set_variable doesn't easily support delete, just overwrite is fine.
        elif subaction.get('action') == 'set_variable':
             var_name = subaction.get('variable')
             val = memory.get_variable(var_name)
             results.append(val)
        elif subaction.get('action') == 'fetch_with_message' or subaction.get('action') == 'fetch':
             # For fetch, we can check the field
             field = subaction.get('field')
             if field:
                 val = memory.get_variable(field)
                 results.append(val)
             else:
                 # Fallback
                 results.append(None)
        else:
             results.append(None)
    
    # Restore original variable if it existed
    if original_val is not None:
        memory.set_variable(loop_variable_name, original_val)
        
    # Store aggregated results
    logger.info(f"loop completed: collected {len(results)} results, storing in {set_variable_name}")
    memory.set_variable(set_variable_name, results)
    
    return StepExecutionResult("completed")
