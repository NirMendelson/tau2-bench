import os
import litellm
import re
import yaml
from loguru import logger
from ...actions import prompts
from ...utils.json_utils import clean_json_response, is_null_value, custom_safe_load
from ...utils.execution_utils import StepExecutionResult
from ...utils.workflow_utils import get_function_definition, get_subworkflow_definition
from .tool_handlers import _parse_set_variable

DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

# Directly sets a variable in memory, resolving templates if necessary
def execute_set_variable(step, memory):
    variable = step.get('variable')
    value = step.get('value')
    if isinstance(value, str):
        var_ref_pattern = r'^\{\{\s*(\w+)\s*\}\}$'
        match = re.match(var_ref_pattern, value.strip())
        if match:
            value = memory.get_variable(match.group(1))
        else:
            value = memory.resolve_templates(value)
    memory.set_variable(variable, value)
    return StepExecutionResult("completed")

# Executes a loop action, iterating over items and running sub-steps
def execute_loop(step, memory, conversation, tone_text, llm_model, tools, workflows):
    loop_over_var = step.get('loop_over')
    loop_variable_name = step.get('loop_variable')
    loop_steps = step.get('loop_steps')
    subaction = step.get('subaction')
    set_variable_name = step.get('set_variable') or step.get('set_variables')
    
    if not loop_over_var or not loop_variable_name or (not loop_steps and not subaction):
         return StepExecutionResult("failed", message="Loop missing required fields")

    items = memory.get_variable(loop_over_var) if isinstance(loop_over_var, str) else loop_over_var
    if items is None and isinstance(loop_over_var, str) and "{{" in loop_over_var:
        items = memory.resolve_templates(loop_over_var)
    if not isinstance(items, (list, tuple)): items = []
    
    if DEBUG_MODE:
        print(f"--- Executing Loop: {step.get('id', 'unnamed')} over {len(items)} items ---")

    results = []
    original_val = memory.get_variable(loop_variable_name)
    
    from ..step_executor import execute_step
    for item in items:
        memory.set_variable(loop_variable_name, item)
        if loop_steps:
            for sub_step in loop_steps:
                res = execute_step(sub_step, memory, conversation, tone_text, llm_model, tools, workflows, is_root=False)
                if res.status != "completed": return res
        else:
            res = execute_step(subaction, memory, conversation, tone_text, llm_model, tools, workflows, is_root=False)
            if res.status != "completed": return res
            results.append(_collect_loop_result(subaction, memory))
    
    if original_val is not None: memory.set_variable(loop_variable_name, original_val)
    if set_variable_name: memory.set_variable(set_variable_name, results)
    return StepExecutionResult("completed")

# Helper to collect results from a single subaction loop
def _collect_loop_result(subaction, memory):
    sub_tool_name = subaction.get('tool_name')
    if sub_tool_name:
        sub_set_var = subaction.get('set_variable') or subaction.get('set_variables')
        if sub_set_var:
            item_result = {}
            mappings = _parse_set_variable(sub_set_var)
            for new_name, original_name in mappings:
                val = memory.get_variable(new_name)
                if val is not None:
                    item_result[new_name] = val
            return item_result if item_result else None
        return memory.get_variable(f"{sub_tool_name}_result")
    elif subaction.get('action') == 'set_variable':
        return memory.get_variable(subaction.get('variable'))
    elif subaction.get('action') in ['fetch', 'fetch_with_message']:
        field = subaction.get('field')
        if isinstance(field, str):
            return memory.get_variable(field)
        elif isinstance(field, list):
            return {f: memory.get_variable(f) for f in field if memory.get_variable(f) is not None}
    return None

# Executes an instruction action where the LLM performs a complex task using available tools
def execute_instruction(step, memory, conversation, tone_text, llm_model, tools, workflows):
    instruction_text = memory.resolve_templates(step.get('instruction'))
    set_var = step.get('set_variable') or step.get('set_variables')  # Support both for backward compatibility
    
    prompt = prompts.get_instruction_prompt(
        instruction_text, step.get('tools_available', []), 
        memory.get_variables_as_json(), memory.get_history_as_text(), tone_text, step.get('comment')
    )
    
    if DEBUG_MODE:
        print(f"--- Instruction Prompt ---\n{prompt}\n--------------------------------")
        
    response = litellm.completion(model=llm_model, messages=[{"role": "user", "content": prompt}])
    content = clean_json_response(response.choices[0].message.content)
    
    if DEBUG_MODE:
        print(f"---agent output---\n{content}\n--------------------------------")
    
    try:
        try: result_data = custom_safe_load(content)
        except: result_data = _dumb_instruction_parser(content)
        
        val = result_data.get('result')
        
        # If val is a string that looks like JSON, try to parse it
        if isinstance(val, str) and val.strip().startswith(('[', '{')):
            try:
                import json
                parsed_val = json.loads(val.strip())
                if isinstance(parsed_val, (list, dict)):
                    val = parsed_val
            except:
                pass

        # Handle set_variable - for instructions, we typically set the entire result
        if set_var and not is_null_value(val):
            mappings = _parse_set_variable(set_var)
            if mappings:
                # If multiple mappings, try to extract from result dict
                if isinstance(val, dict) and len(mappings) > 1:
                    for new_name, original_name in mappings:
                        extracted_val = val.get(original_name) if isinstance(val, dict) else val
                        if not is_null_value(extracted_val):
                            memory.set_variable(new_name, extracted_val)
                else:
                    # Single mapping or non-dict result - set the whole value
                    new_name, _ = mappings[0]
                    memory.set_variable(new_name, val)
        return StepExecutionResult("completed")
    except Exception as e:
        logger.error(f"error parsing instruction response: {e}")
        return StepExecutionResult("failed", message=f"Failed to parse instruction result: {e}")

# Fallback parser for instruction output if YAML loading fails
def _dumb_instruction_parser(content):
    result = {}
    for key in ['result', 'reasoning']:
        match = re.search(fr'{key}:\s*(.*?)(?=\n\s*(?:result|reasoning)\s*:|$)', content, re.DOTALL | re.IGNORECASE)
        if match:
            val = match.group(1).strip().replace(':', '')
            if key == 'result':
                if val.lower() == 'false': val = False
                elif val.lower() == 'true': val = True
                elif val.lower() == 'null': val = None
            result[key] = val
    return result

# Executes a function recursively, taking a memory snapshot for functional scoping if needed
def execute_function_recursive(func_name, memory, conversation, tone_text, llm_model, tools, workflows, step=None):
    func_def = get_function_definition(func_name, workflows)
    if not func_def: return StepExecutionResult("failed", message=f"Function {func_name} not found")
        
    metadata = func_def[0] if isinstance(func_def, list) else func_def
    return_vars = metadata.get('return') or (step.get('set_variable') or step.get('set_variables') if step else None)
    
    func_steps = func_def[1:] if isinstance(func_def, list) else func_def.get('steps', [])
    if not func_steps: return StepExecutionResult("failed", message=f"Function {func_name} is empty")

    if DEBUG_MODE:
        print(f"--- Entering Function: {func_name} (returning: {return_vars}) ---")

    snapshot = memory.variables.copy() if return_vars else None
    from ..step_executor import execute_step
    for f_step in func_steps:
        res = execute_step(f_step, memory, conversation, tone_text, llm_model, tools, workflows, is_root=False)
        if res.status != "completed": return res
            
    if snapshot and return_vars:
        _restore_with_return_vars(memory, snapshot, return_vars, func_name)
    
    if DEBUG_MODE:
        print(f"--- Exiting Function: {func_name} ---")
    return StepExecutionResult("completed")

# Backward compatibility: Executes a subworkflow recursively
def execute_subworkflow_recursive(sub_name, memory, conversation, tone_text, llm_model, tools, workflows, step=None):
    return execute_function_recursive(sub_name, memory, conversation, tone_text, llm_model, tools, workflows, step)

# Restores memory to a snapshot while preserving specified return variables
def _restore_with_return_vars(memory, snapshot, return_vars, name="Function"):
    if isinstance(return_vars, str): return_vars = [return_vars]
    results_to_keep = {var: memory.get_variable(var) for var in return_vars if memory.get_variable(var) is not None}
    
    if DEBUG_MODE:
        print(f"Restored memory from {name}, kept: {list(results_to_keep.keys())}")
        
    memory.variables = snapshot
    for var, val in results_to_keep.items(): memory.set_variable(var, val)
