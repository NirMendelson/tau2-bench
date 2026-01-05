import os
import litellm
import re
import yaml
from loguru import logger
from ...actions import prompts
from ...utils.json_utils import clean_json_response, is_null_value, custom_safe_load
from ...utils.execution_utils import StepExecutionResult
from ...utils.workflow_utils import get_subworkflow_definition

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
        sub_set_vars = subaction.get('set_variables')
        if sub_set_vars:
            item_result = {}
            target_vars = []
            if isinstance(sub_set_vars, dict): target_vars = list(sub_set_vars.keys())
            else:
                for item in sub_set_vars:
                    if isinstance(item, dict): target_vars.extend(item.keys())
                    else: target_vars.append(item)
            for var_name in target_vars: item_result[var_name] = memory.get_variable(var_name)
            return item_result
        return memory.get_variable(f"{sub_tool_name}_result")
    elif subaction.get('action') == 'set_variable':
        return memory.get_variable(subaction.get('variable'))
    elif subaction.get('action') in ['fetch', 'fetch_with_message']:
        return memory.get_variable(subaction.get('field'))
    return None

# Executes an instruction action where the LLM performs a complex task using available tools
def execute_instruction(step, memory, conversation, tone_text, llm_model, tools, workflows):
    instruction_text = memory.resolve_templates(step.get('instruction'))
    set_variable = step.get('set_variable')
    set_variables = step.get('set_variables')
    
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

        if set_variable and not is_null_value(val): memory.set_variable(set_variable, val)
        if set_variables:
            target_keys = set_variables.keys() if isinstance(set_variables, dict) else (
                [list(i.keys())[0] if isinstance(i, dict) else i for i in set_variables] if isinstance(set_variables, list) else [set_variables]
            )
            for k in target_keys:
                if not is_null_value(val): memory.set_variable(k, val)
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

# Executes a subworkflow recursively, taking a memory snapshot for functional scoping if needed
def execute_subworkflow_recursive(sub_name, memory, conversation, tone_text, llm_model, tools, workflows, step=None):
    sub_def = get_subworkflow_definition(sub_name, workflows)
    if not sub_def: return StepExecutionResult("failed", message=f"Subworkflow {sub_name} not found")
        
    metadata = sub_def[0] if isinstance(sub_def, list) else sub_def
    return_vars = metadata.get('return') or (step.get('set_variables') or step.get('set_variable') if step else None)
    
    sub_steps = sub_def[1:] if isinstance(sub_def, list) else sub_def.get('steps', [])
    if not sub_steps: return StepExecutionResult("failed", message=f"Subworkflow {sub_name} is empty")

    snapshot = memory.variables.copy() if return_vars else None
    from ..step_executor import execute_step
    for s_step in sub_steps:
        res = execute_step(s_step, memory, conversation, tone_text, llm_model, tools, workflows, is_root=False)
        if res.status != "completed": return res
            
    if snapshot and return_vars:
        _restore_with_return_vars(memory, snapshot, return_vars)
    return StepExecutionResult("completed")

# Restores memory to a snapshot while preserving specified return variables
def _restore_with_return_vars(memory, snapshot, return_vars):
    if isinstance(return_vars, str): return_vars = [return_vars]
    results_to_keep = {var: memory.get_variable(var) for var in return_vars if memory.get_variable(var) is not None}
    memory.variables = snapshot
    for var, val in results_to_keep.items(): memory.set_variable(var, val)
