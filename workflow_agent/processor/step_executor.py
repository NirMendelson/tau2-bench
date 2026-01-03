import json
import litellm
import os
from loguru import logger
from ..actions import prompts
from .action_config import is_action_blocking
import re
import yaml
from yaml.resolver import Resolver

# Custom YAML loader that doesn't automatically parse strings as dates/times
class NoDatesSafeLoader(yaml.SafeLoader):
    pass

# Remove the implicit resolver for timestamps
# This prevents 2024-05-26 from becoming a datetime.date object
NoDatesSafeLoader.yaml_implicit_resolvers = {
    k: [r for r in v if r[0] != 'tag:yaml.org,2002:timestamp']
    for k, v in yaml.SafeLoader.yaml_implicit_resolvers.items()
}

def custom_safe_load(content):
    return yaml.load(content, Loader=NoDatesSafeLoader)


DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

def _create_result_with_blocking_check(action_name: str, message: str, memory, result_data=None):
    """
    Helper function to create StepExecutionResult based on action blocking config.
    
    Args:
        action_name: Name of the action to check blocking config
        message: Message to send (if any)
        memory: Memory object to add message to history if non-blocking
        result_data: Optional additional result data
        
    Returns:
        StepExecutionResult with appropriate status (blocking or completed)
    """
    if is_action_blocking(action_name):
        return StepExecutionResult("blocking", message=message, result=result_data)
    else:
        # Non-blocking: add message to history and continue
        if message:
            memory.add_to_history("assistant", message)
        return StepExecutionResult("completed", message=message, result=result_data)

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
    Ensures primary keys are correctly formatted and nested content is indented
    to prevent YAML parsing errors with colons and lists.
    """
    response_text = response_text.strip()
    
    # Robust extraction of content from markdown code blocks
    code_block_match = re.search(r'```(?:yaml|json)?\n(.*?)\n```', response_text, re.DOTALL)
    if code_block_match:
        response_text = code_block_match.group(1).strip()
    elif response_text.startswith("```"):
        # Fallback for code blocks missing the closing newline
        lines = response_text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        response_text = "\n".join(lines).strip()
    
    # If the response is valid JSON, we don't want to touch it as colons are part of the syntax
    try:
        json.loads(response_text)
        return response_text
    except:
        pass

    # The "YAML Surgeon" Logic:
    # 1. Identifies known primary keys to orient the structure.
    # 2. Forces indentation on content within block scalars (|-) even if the LLM forgets.
    # 3. Automatically quotes values containing colons to prevent YAML parsing breakage.
    primary_keys = {
        "found", "value", "question", "condition_result", "fields", "questions", 
        "all_found", "combined_question", "result", "reasoning", "arguments"
    }
    
    lines = response_text.split("\n")
    cleaned_lines = []
    block_mode = False
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append(line)
            continue
            
        # Check if this line looks like a key definition: "key:", "  key:", or "key: |-"
        key_match = re.match(r'^(\s*)([\w_-]+):\s*(.*)$', line)
        
        if key_match:
            indent, key, value = key_match.groups()
            
            # Reset block mode if we see a key at level 0 or a known primary key at shallow level
            if not indent or (key in primary_keys and len(indent) <= 2):
                block_mode = False
            
            # If not in block mode, check for unquoted values containing colons
            # We ONLY check the value part for colons to avoid quoting booleans/numbers
            if not block_mode and not "|-" in value and ":" in value:
                v_strip = value.strip()
                # If the value contains colons and isn't already quoted
                if v_strip and not (v_strip.startswith('"') or v_strip.startswith("'")):
                    # Skip quoting for boolean-like values just in case
                    if v_strip.lower() not in ["true", "false", "null", "none"]:
                        # Wrap the value in double quotes and escape existing quotes
                        escaped_v = v_strip.replace('"', '\\"')
                        line = f"{indent}{key}: \"{escaped_v}\""
            
            # If this line starts a block scalar, enter block mode
            if "|-" in value:
                block_mode = True
            elif block_mode:
                # If we are in block mode, ensure this line (which looks like a key) is indented
                if not line.startswith("  "):
                    line = "  " + line
            
            cleaned_lines.append(line)
        else:
            # Literal content line (e.g., part of a block scalar or a list item)
            if block_mode:
                # Ensure all block content has at least 2 spaces of indentation
                if not line.startswith("  "):
                    line = "  " + line
            cleaned_lines.append(line)
            
    return "\n".join(cleaned_lines)

def is_null_value(val):
    """
    Checks if a value from an LLM response should be treated as null.
    Handles None, empty strings, and string literals like "null", "none", etc.
    """
    if val is None:
        return True
    if isinstance(val, str):
        normalized = val.strip().lower()
        # Remove trailing/leading quotes that LLM might add in block scalars
        normalized = normalized.strip("'\" \n")
        if normalized in ["null", "none", "n/a", "unknown", ""]:
            return True
    return False

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
    missing_fields = [f for f in target_fields if memory.get_variable(f) is None]
    
    # If all fields are found, we're done
    if not missing_fields:
        return StepExecutionResult("completed")
    
    # Get conversation text
    conv_text = memory.get_history_as_text()
    
    # Format memory info for prompts
    memory_info = memory.get_variables_as_json()
    
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
        result = custom_safe_load(content)
        
        # Handle response format - check if it's multi-field format or single field format
        if 'fields' in result:
            # Multi-field response format
            fields_data = result.get('fields', {})
            questions_data = result.get('questions', {})
            
            # Store found fields in memory
            for field_name in target_fields:
                val = fields_data.get(field_name)
                if not is_null_value(val):
                    memory.set_variable(field_name, val)
            
            # Check if we now have all fields
            still_missing = [f for f in target_fields if memory.get_variable(f) is None]
            
            if not still_missing:
                # All fields found - we're done
                return StepExecutionResult("completed")
            else:
                # Some or all fields still missing - ask user
                # Prefer combined question if available
                combined_question = result.get('combined_question')
                if combined_question:
                    return _create_result_with_blocking_check("fetch", combined_question, memory)
                else:
                    # Combine individual questions for missing fields
                    questions = [q for f, q in questions_data.items() if f in still_missing and q]
                    if questions:
                        if len(questions) == 1:
                            return _create_result_with_blocking_check("fetch", questions[0], memory)
                        else:
                            # Combine multiple questions naturally
                            combined = " ".join(questions)
                            return _create_result_with_blocking_check("fetch", combined, memory)
                    else:
                        # Fallback if no questions provided
                        missing_list = ", ".join(still_missing)
                        return _create_result_with_blocking_check("fetch", f"Please provide: {missing_list}", memory)
        else:
            # Single field response format (backward compatible)
            if result.get('found'):
                val = result.get('value')
                if not is_null_value(val):
                    memory.set_variable(target_fields[0], val)
                # After setting, check if we should continue
                if memory.get_variable(target_fields[0]) is not None:
                     # For single field fetch, if we found it, we might be done or need to check next segment
                     # But most importantly, don't recurse if the value is just Falsy
                     return StepExecutionResult("completed")
                return execute_fetch(step, memory, conversation, tone_text, llm_model)
            else:
                return _create_result_with_blocking_check("fetch", result.get('question'), memory)
            
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
    memory_info = memory.get_variables_as_json()
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
        result = custom_safe_load(content)
        
        # Use the LLM's evaluation of the condition
        condition_met = result.get('condition_result')
        
        # If explicit 'true'/'false' string, convert to boolean
        if isinstance(condition_met, str):
            condition_met = condition_met.lower() == 'true'

        if result.get('found'):
            val = result.get('value')
            if not is_null_value(val):
                memory.set_variable(field, val)
        
        if condition_met:
            # Condition met -> execute 'then' steps
            return StepExecutionResult("completed", result={"condition": True})
        
        if result.get('found'):
            # Found value but condition false
            return StepExecutionResult("completed", result={"condition": False})
        else:
            # Not found and condition false -> ask question
            return _create_result_with_blocking_check("fetch_with_condition", result.get('question'), memory)
            
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
    missing_fields = [f for f in target_fields if memory.get_variable(f) is None]
    
    # If all fields are found, we're done
    if not missing_fields:
        return StepExecutionResult("completed")
    
    # Resolve templates in message
    message_template = step.get('message')
    resolved_message = memory.resolve_templates(message_template)
    
    # Get conversation text
    conv_text = memory.get_history_as_text()
    
    # Format memory info for prompts
    memory_info = memory.get_variables_as_json()
    
    # Get comment if provided
    comment = step.get('comment')
    
    # Call prompt with field names
    prompt = prompts.get_fetch_with_message_prompt(target_fields, resolved_message, conv_text, tone_text, memory_info, comment)
    
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
        result = custom_safe_load(content)
        
        # Handle response format
        if 'fields' in result:
            # Multi-field response format
            fields_data = result.get('fields', {})
            questions_data = result.get('questions', {})
            
            # Store found fields in memory
            for field_name in target_fields:
                val = fields_data.get(field_name)
                if not is_null_value(val):
                    memory.set_variable(field_name, val)
            
            # Check if we now have all fields
            still_missing = [f for f in target_fields if memory.get_variable(f) is None]
            
            if not still_missing:
                # All fields found - we're done
                return StepExecutionResult("completed")
            else:
                # Some or all fields still missing - use the question from YAML
                # Get question for the first missing field (or combine if multiple)
                questions = [q for f, q in questions_data.items() if f in still_missing and q]
                if questions:
                    if len(questions) == 1:
                        return _create_result_with_blocking_check("fetch_with_message", questions[0], memory)
                    else:
                        # Combine multiple questions naturally
                        combined = " ".join(questions)
                        return _create_result_with_blocking_check("fetch_with_message", combined, memory)
                else:
                    # Fallback to the provided message if no questions in response
                    return _create_result_with_blocking_check("fetch_with_message", resolved_message, memory)
        else:
            # Fallback if response format is unexpected
            logger.warning(f"unexpected response format from fetch_with_message: {result}")
            return _create_result_with_blocking_check("fetch_with_message", resolved_message, memory)
            
    except Exception as e:
        # Fallback if parsing fails
        logger.error(f"error parsing fetch_with_message response: {e}")
        return _create_result_with_blocking_check("fetch_with_message", resolved_message, memory)

def execute_reply(step, memory, conversation, tone_text, llm_model):
    """
    Sends a message to the user based on the reply action.
    Blocking behavior is controlled by action_config.
    """
    message_template = step.get('message')
    resolved_message = memory.resolve_templates(message_template)
    
    conv_text = memory.get_history_as_text()
    # Format memory info for prompts
    memory_info = memory.get_variables_as_json()
    # Get comment if provided
    comment = step.get('comment')
    prompt = prompts.get_reply_prompt(resolved_message, tone_text, conv_text, memory_info, comment)
    
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
    
    # Check blocking config for reply action
    return _create_result_with_blocking_check("reply", final_message, memory)

def execute_reply_exact_message(step, memory, conversation, tone_text, llm_model):
    """
    Sends a message to the user based on the reply_exact_message action.
    Blocking behavior is controlled by action_config.
    """
    message_template = step.get('message')
    resolved_message = memory.resolve_templates(message_template)
    
    conv_text = memory.get_history_as_text()
    # Get comment if provided
    comment = step.get('comment')
    prompt = prompts.get_reply_exact_message_prompt(resolved_message, tone_text, conv_text, comment)
    
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
    
    # Check blocking config for reply_exact_message action
    return _create_result_with_blocking_check("reply_exact_message", final_message, memory)

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
    memory_info = memory.get_variables_as_json()
    # Get comment if provided
    comment = step.get('comment')
    prompt = prompts.get_condition_eval_prompt(condition_str, memory_info, conv_text, comment)
    
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
    memory_info = memory.get_variables_as_json()
    prompt = prompts.get_conditional_with_message_prompt(
        condition_str, 
        memory_info, 
        conv_text,
        tone_text,
        message_on_true=message_on_true,
        message_on_false=message_on_false,
        comment=step.get('comment')
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
        cleaned_content = clean_json_response(content)
        result = custom_safe_load(cleaned_content)
        
        if not result or 'condition_result' not in result:
            logger.error(f"invalid response format from conditional_with_message: {content}")
            return StepExecutionResult("failed", message="Failed to parse condition evaluation.")
        
        condition_result = result.get('condition_result')
        if isinstance(condition_result, str):
            is_true = condition_result.lower() == 'true'
        else:
            is_true = bool(condition_result)
        
        message = result.get('message')
        
        # If message was generated, send it (blocking behavior based on config)
        if message and message.strip() and message.lower() != 'null':
            if DEBUG_MODE:
                logger.info(f"conditional_with_message: condition is {is_true}, message generated")
            
            # Check blocking config for conditional_with_message action
            return _create_result_with_blocking_check("conditional_with_message", message.strip(), memory, result={"condition": is_true})
        
        # No message for this condition result - we're done, continue to next step
        if DEBUG_MODE:
            logger.info(f"conditional_with_message: condition is {is_true}, no message needed, continuing to next step")
        
        return StepExecutionResult("completed", result={"condition": is_true})
        
    except Exception as e:
        logger.error(f"error parsing conditional_with_message response: {e}")
        return StepExecutionResult("failed", message="Failed to parse condition evaluation.")

def execute_use_tool(step, memory, tools, llm_model, tone_text):
    """
    Calls an external tool (e.g., airline tools) and handles the output.
    Uses ToolExecutor to handle workflow syntax (input lists) to tool parameters.
    """
    tool_name = step.get('tool_name')
    
    # Check if tool exists
    if not tools.has_tool(tool_name):
        return StepExecutionResult("failed", message=f"Tool {tool_name} not found")

    # Prepare positional inputs if present (used as hints for smart_tool and as args for normal tool)
    input_list = None
    if 'input' in step:
        input_value = step['input']
        if isinstance(input_value, list):
            input_list = [memory.resolve_templates(v) if isinstance(v, str) else v for v in input_value]
        else:
            input_list = [memory.resolve_templates(input_value) if isinstance(input_value, str) else input_value]

    skip_post_filter = False

    # Smart Tool Resolver Logic
    if step.get('smart_tool'):
        logger.info(f"Using smart tool resolver for tool: {tool_name}")
        tool_obj = tools.get_tool(tool_name)
        if not tool_obj:
            return StepExecutionResult("failed", message=f"Tool object for {tool_name} not found")
        
        tool_description = tool_obj._get_description()
        tool_parameters = json.dumps(tool_obj.params.model_json_schema(), indent=2)
        memory_json = memory.get_variables_as_json()
        conv_text = memory.get_history_as_text()
        
        prompt = prompts.get_smart_tool_resolver_prompt(
            tool_name, tool_description, tool_parameters, memory_json, tone_text, conv_text, 
            step.get('comment'), input_data=input_list
        )
        
        if DEBUG_MODE:
            print("--- Smart Tool Resolver Prompt ---")
            print(prompt)
            print("--------------------------------")
            
        try:
            response = litellm.completion(
                model=llm_model,
                messages=[{"role": "user", "content": prompt}]
            )
            
            content = clean_json_response(response.choices[0].message.content)
            
            if DEBUG_MODE:
                print("---agent smart tool output---")
                print(content)
                
            resolve_data = custom_safe_load(content)
            resolved_args = resolve_data.get('arguments', {})
            logger.info(f"Smart tool resolver reasoning: {resolve_data.get('reasoning')}")
            
            # Execute tool with resolved arguments
            logger.info(f"calling tool {tool_name} with smart resolved arguments: {resolved_args}")
            result = tools.execute(tool_name, **resolved_args)
            logger.info(f"tool {tool_name} returned: {result} (type: {type(result)})")
            
            # If we used the smart tool resolver, we skip the post-filter prompt because 
            # the comment was already incorporated into the resolver prompt.
            skip_post_filter = True
            
        except Exception as e:
            logger.error(f"Smart tool resolver failed: {e}")
            return StepExecutionResult("failed", message=f"Smart tool resolver failed: {str(e)}")
    
    else:
        # Normal tool resolution (original logic)
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
        
        
        # Prepare keyword arguments (all other fields except reserved ones)
        kwargs = {}
        reserved_keys = ['id', 'action', 'tool_name', 'set_variables', 'comment', 'then', 'else', 'input', 'smart_tool']
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
    
    # Handle LLM commenting/filtering if 'comment' instruction is provided
    comment = step.get('comment')
    if comment and not skip_post_filter:
        logger.info(f"Applying comment to tool {tool_name} results: {comment}")
        
        # Resolve templates in the comment instruction (e.g. {{ cabin }})
        resolved_comment = memory.resolve_templates(str(comment))
        
        # Prepare context for the LLM
        memory_vars_json = memory.get_variables_as_json()
        
        # Serialize result for the prompt
        def serialize_for_prompt(obj):
            from pydantic import BaseModel
            import datetime
            if isinstance(obj, BaseModel):
                return obj.model_dump()
            if isinstance(obj, (datetime.date, datetime.datetime)):
                return obj.isoformat()
            if isinstance(obj, list):
                return [serialize_for_prompt(item) for item in obj]
            if isinstance(obj, dict):
                return {k: serialize_for_prompt(v) for k, v in obj.items()}
            return obj
            
        serialized_result = serialize_for_prompt(result)
        
        prompt = prompts.get_comment_on_tool_result_prompt(
            json.dumps(serialized_result, indent=2, ensure_ascii=False),
            resolved_comment,
            memory_vars_json
        )
        
        if DEBUG_MODE:
            print("--- Comment/Filter Prompt ---")
            print(prompt)
            print("--------------------------------")
            
        try:
            response = litellm.completion(
                model=llm_model,
                messages=[{"role": "user", "content": prompt}]
            )
            
            comment_content = clean_json_response(response.choices[0].message.content)
            
            if DEBUG_MODE:
                print("---agent comment output---")
                print(comment_content)
                
            comment_data = custom_safe_load(comment_content)
            
            # Update the result with the filtered version
            # If the LLM returned a null result, we keep the original or set to empty list?
            # User said "only then insert it to memory", so we should use the filtered result.
            if comment_data and 'result' in comment_data:
                result = comment_data['result']
                logger.info(f"Comment reasoning: {comment_data.get('reasoning', 'No reasoning provided')}")
            else:
                logger.warning(f"Comment action did not return a 'result' field. Response: {comment_content}")
                
        except Exception as e:
            logger.error(f"Error during tool result commenting: {e}")
            # In case of LLM failure, we can either fail the whole step or continue with original results.
            # Usually better to fail if filtering was required for safety/logic.
            # But here let's continue with a warning to be robust, or should we fail?
            # User said "only then insert it to memory", suggesting filtering is crucial.
            # Let's fail for now to be safe.
            return StepExecutionResult("failed", message=f"Failed to process comment on tool results: {str(e)}")
    
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
            if source_name == 'result':
                return result
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

def execute_instruction(step, memory, conversation, tone_text, llm_model, tools, workflows):
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
    
    # Get variable name(s) to set
    set_variable = step.get('set_variable')
    set_variables = step.get('set_variables')
    
    if not set_variable and not set_variables:
        logger.error("instruction action missing 'set_variable' or 'set_variables' field")
        return StepExecutionResult("failed", message="Instruction action missing 'set_variable' or 'set_variables' field")
    
    # Get current memory variables (for context)
    memory_variables_json = memory.get_variables_as_json()
    
    # Get conversation context
    conv_text = memory.get_history_as_text()
    
    # Build prompt
    prompt = prompts.get_instruction_prompt(
        instruction_text,
        tools_available,
        memory_variables_json,
        conv_text,
        tone_text,
        step.get('comment')
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
        if set_variable and not is_null_value(result_value):
            memory.set_variable(set_variable, result_value)
            
        if set_variables:
            # Handle set_variables mappings (similar to calculate tool or use_tool)
            if isinstance(set_variables, dict):
                # Dict format: {"new_name": "old_name"} - for instruction, we map result_value to new_name
                for new_name in set_variables.keys():
                    if not is_null_value(result_value):
                        memory.set_variable(new_name, result_value)
            elif isinstance(set_variables, list):
                # List format: ["var1", "var2"] or [{"new_name": "old_name"}]
                for item in set_variables:
                    if isinstance(item, dict):
                        for new_name in item.keys():
                            if not is_null_value(result_value):
                                memory.set_variable(new_name, result_value)
                    else:
                        if not is_null_value(result_value):
                            memory.set_variable(item, result_value)
            elif isinstance(set_variables, str):
                if not is_null_value(result_value):
                    memory.set_variable(set_variables, result_value)
                
        if result_value is None:
            logger.warning(f"instruction task returned null result")
            
        return StepExecutionResult("completed")
            
    except Exception as e:
        logger.error(f"error parsing instruction response: {e}")
        return StepExecutionResult("failed", message=f"Failed to parse instruction result: {e}")

def handle_fallback(memory, tools):
    """
    Executes the fallback action (transfer to human) when data or logic path is missing.
    """
    result = tools.execute('transfer_to_human_agents', **{'summary': "Workflow fallback triggered"})
    return StepExecutionResult("blocking", message=result)

def _get_subworkflow_steps(sub_name, workflows):
    """Helper to find subworkflow steps by name."""
    for w in workflows:
        if isinstance(w, list) and len(w) > 0 and w[0].get('subworkflow') == sub_name:
            return w[1:]
        elif isinstance(w, dict) and w.get('subworkflow') == sub_name:
            return w.get('steps', [])
    return None
    
def _get_subworkflow_definition(sub_name, workflows):
    """Helper to find full subworkflow definition (metadata + steps)."""
    for w in workflows:
        if isinstance(w, list) and len(w) > 0 and w[0].get('subworkflow') == sub_name:
            return w
        elif isinstance(w, dict) and w.get('subworkflow') == sub_name:
            return w
    return None

def execute_subworkflow_recursive(sub_name, memory, conversation, tone_text, llm_model, tools, workflows):
    """Executes a subworkflow recursively (for non-root contexts)."""
    sub_def = _get_subworkflow_definition(sub_name, workflows)
    if not sub_def:
        logger.error(f"Subworkflow {sub_name} not found")
        return StepExecutionResult("failed", message=f"Subworkflow {sub_name} not found")
        
    metadata = sub_def[0] if isinstance(sub_def, list) else sub_def
    # Support return vars from metadata, or call-site set_variables/set_variable
    return_vars = metadata.get('return') or step.get('set_variables') or step.get('set_variable')
    
    if isinstance(sub_def, list):
        sub_steps = sub_def[1:]
    else:
        sub_steps = sub_def.get('steps', [])
        
    if not sub_steps:
        logger.error(f"Subworkflow {sub_name} is empty")
        return StepExecutionResult("failed", message=f"Subworkflow {sub_name} is empty")

    # If functional scoping is requested, take a snapshot
    snapshot = None
    if return_vars:
        snapshot = memory.variables.copy()
        logger.info(f"Recursive: Entering subworkflow {sub_name} with functional scoping. Will return: {return_vars}")
        
    for s_step in sub_steps:
        result = execute_step(s_step, memory, conversation, tone_text, llm_model, tools, workflows, is_root=False)
        if result.status != "completed":
            # If blocking or failed, we don't restore yet as we'll resume later
            # (Note: resume in recursive subworkflows is tricky, but following current pattern)
            return result
            
    # Subworkflow completed - handle memory restoration if scoping was used
    if snapshot and return_vars:
        if isinstance(return_vars, str):
            return_vars = [return_vars]
            
        results_to_keep = {}
        for var in return_vars:
            val = memory.get_variable(var)
            if val is not None:
                results_to_keep[var] = val
        
        # Restore memory to snapshot
        memory.variables = snapshot
        
        # Inject return values back
        for var, val in results_to_keep.items():
            memory.set_variable(var, val)
            
        logger.info(f"Recursive: Subworkflow {sub_name} completed. Restored memory and kept: {list(results_to_keep.keys())}")
        
    return StepExecutionResult("completed")

def execute_step(step, memory, conversation, tone_text, llm_model, tools, workflows, is_root=False):
    """
    Main entry point for executing an individual step based on its action type.
    """

    action = step.get('action')
    
    result = None
    if action == 'fetch':
        result = execute_fetch(step, memory, conversation, tone_text, llm_model)
    elif action == 'fetch_with_condition':
        result = execute_fetch_with_condition(step, memory, conversation, tone_text, llm_model)
    elif action == 'fetch_with_message':
        result = execute_fetch_with_message(step, memory, conversation, tone_text, llm_model)
    elif action == 'reply':
        result = execute_reply(step, memory, conversation, tone_text, llm_model)
    elif action == 'reply_exact_message':
        result = execute_reply_exact_message(step, memory, conversation, tone_text, llm_model)
    elif action == 'set_variable':
        result = execute_set_variable(step, memory)
    elif action == 'conditional' or action == 'condition':
        result = execute_condition(step, memory, conversation, tone_text, llm_model)
    elif action == 'conditional_with_message':
        result = execute_conditional_with_message(step, memory, conversation, tone_text, llm_model)
    elif action == 'use_tool':
        result = execute_use_tool(step, memory, tools, llm_model, tone_text)
    elif action == 'instruction':
        result = execute_instruction(step, memory, conversation, tone_text, llm_model, tools, workflows)
    elif action == 'loop':
        result = execute_loop(step, memory, conversation, tone_text, llm_model, tools, workflows)
    elif action == 'use_subworkflow':
        if not is_root:
            sub_name = step.get('subworkflow')
            return execute_subworkflow_recursive(sub_name, memory, conversation, tone_text, llm_model, tools, workflows)
        # Root calls are handled by the orchestrator to push to stack
        return StepExecutionResult("completed")
    else:
        return StepExecutionResult("failed", message=f"Unknown action: {action}")

    # Handle automatic branching ONLY IF NOT ROOT
    if not is_root and result.status == "completed" and hasattr(result, 'result') and result.result and 'condition' in result.result:
        is_true = result.result['condition']
        branch_block = step.get('then' if is_true else 'else')
        branch_steps = []
        if isinstance(branch_block, list):
            branch_steps = branch_block
        elif isinstance(branch_block, dict):
            if 'steps' in branch_block:
                branch_steps = branch_block['steps']
            elif 'id' in branch_block or 'action' in branch_block:
                branch_steps = [branch_block]
        
        if branch_steps:
            for b_step in branch_steps:
                b_result = execute_step(b_step, memory, conversation, tone_text, llm_model, tools, workflows, is_root=False)
                if b_result.status != "completed":
                    return b_result
                    
    return result

def execute_loop(step, memory, conversation, tone_text, llm_model, tools, workflows):
    """
    Iterates over a list, sets a loop variable, and executes steps for each item.
    Supports both loop_steps (list of steps) and subaction (single step) for backward compatibility.
    Collects results into a list.
    """
    loop_over_var = step.get('loop_over')
    loop_variable_name = step.get('loop_variable')
    loop_steps = step.get('loop_steps')
    subaction = step.get('subaction')
    set_variable_name = step.get('set_variable') or step.get('set_variables')
    
    # Normalize set_variable_name if it's a list (take first one for loop collection)
    if isinstance(set_variable_name, list) and len(set_variable_name) > 0:
        if isinstance(set_variable_name[0], str):
            set_variable_name = set_variable_name[0]
        elif isinstance(set_variable_name[0], dict):
            set_variable_name = list(set_variable_name[0].keys())[0]
    
    if not loop_over_var or not loop_variable_name:
         return StepExecutionResult("failed", message="Loop action missing required fields (loop_over, loop_variable)")
    
    # Must have either loop_steps or subaction
    if not loop_steps and not subaction:
         return StepExecutionResult("failed", message="Loop action missing required fields (loop_steps or subaction)")

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
        # Set loop variable and context key for nesting
        item_str = str(item) if item is not None else None
        old_context = getattr(memory, 'context_key', None)
        memory.context_key = item_str
        
        memory.set_variable(loop_variable_name, item)
        
        # Execute either loop_steps (list of steps) or subaction (single step)
        if loop_steps:
            # Execute multiple steps in sequence
            for sub_step in loop_steps:
                result = execute_step(sub_step, memory, conversation, tone_text, llm_model, tools, workflows, is_root=False)
                
                if result.status == "failed":
                    logger.error(f"Loop step {sub_step.get('id', 'unknown')} failed for item {item}: {result.message}")
                    return StepExecutionResult("failed", message=f"Loop failed on item {item} at step {sub_step.get('id', 'unknown')}: {result.message}")
                
                if result.status == "blocking":
                    return result
                
                # Continue to next step if completed
        else:
            # Execute single subaction (backward compatibility)
            result = execute_step(subaction, memory, conversation, tone_text, llm_model, tools, workflows, is_root=False)
            
            if result.status == "failed":
                logger.error(f"Loop subaction failed for item {item}: {result.message}")
                return StepExecutionResult("failed", message=f"Loop failed on item {item}: {result.message}")
            
            if result.status == "blocking":
                return result
                 
            # Collection strategy for single subaction (backward compatibility)
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
        
        # Restore context key
        memory.context_key = old_context
        
        # For loop_steps, we just append None or could collect a summary
        # The individual steps will have set their own variables in memory
        if loop_steps:
            results.append(None)  # Or could collect a summary dict if needed
    
    # Restore original variable if it existed
    if original_val is not None:
        memory.set_variable(loop_variable_name, original_val)
        
    # Store aggregated results
    if set_variable_name:
        logger.info(f"loop completed: collected {len(results)} results, storing in {set_variable_name}")
        memory.set_variable(set_variable_name, results)
    else:
        logger.info(f"loop completed: collected {len(results)} results (not stored)")
    
    return StepExecutionResult("completed")
