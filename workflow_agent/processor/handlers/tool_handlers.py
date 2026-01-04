import os
import json
import litellm
from loguru import logger
from ...actions import prompts
from ...utils.json_utils import clean_json_response, custom_safe_load, serialize_obj
from ...utils.execution_utils import StepExecutionResult

DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

# Extracts a value from a tool result object or dictionary
def _get_value_from_result(result, source_name):
    if source_name == 'result': return result
    if isinstance(result, dict): return result.get(source_name)
    return getattr(result, source_name, None)

# Calls an external tool and handles its output, including smart resolution and filtering
def execute_use_tool(step, memory, tools, llm_model, tone_text):
    tool_name = step.get('tool_name')
    if not tools.has_tool(tool_name):
        return StepExecutionResult("failed", message=f"Tool {tool_name} not found")

    inputs = step.get('input', [])
    input_list = [memory.resolve_templates(v) if isinstance(v, str) else v for v in (inputs if isinstance(inputs, list) else [inputs])]

    if step.get('smart_tool'):
        result, skip_filter = _execute_smart_tool(step, tool_name, memory, tools, llm_model, tone_text, input_list)
        if isinstance(result, StepExecutionResult): return result
    else:
        result = _execute_normal_tool(step, tool_name, memory, tools, input_list)
        skip_filter = False
        if isinstance(result, StepExecutionResult): return result

    if step.get('comment') and not skip_filter:
        result = _apply_tool_output_filter(step, result, memory, llm_model)
        if isinstance(result, StepExecutionResult): return result

    _store_tool_result(step, tool_name, result, memory)
    return StepExecutionResult("completed")

# Handles smart tool resolution using LLM to determine arguments
def _execute_smart_tool(step, tool_name, memory, tools, llm_model, tone_text, input_list):
    logger.info(f"Using smart tool resolver for tool: {tool_name}")
    tool_obj = tools.get_tool(tool_name)
    if not tool_obj: return StepExecutionResult("failed", message="Tool object missing"), False
    
    prompt = prompts.get_smart_tool_resolver_prompt(
        tool_name, tool_obj._get_description(), 
        json.dumps(tool_obj.params.model_json_schema(), indent=2),
        memory.get_variables_as_json(), tone_text, memory.get_history_as_text(),
        step.get('comment'), input_data=input_list
    )
    
    try:
        response = litellm.completion(model=llm_model, messages=[{"role": "user", "content": prompt}])
        data = custom_safe_load(clean_json_response(response.choices[0].message.content))
        logger.info(f"Smart reasoning: {data.get('reasoning')}")
        return tools.execute(tool_name, **data.get('arguments', {})), True
    except Exception as e:
        logger.error(f"Smart tool failed: {e}")
        return StepExecutionResult("failed", message=str(e)), False

# Handles normal tool execution logic, including special handling for calculate
def _execute_normal_tool(step, tool_name, memory, tools, input_list):
    if tool_name == 'calculate': return _execute_calculate_tool(step, memory, tools)
    
    reserved = {'id', 'action', 'tool_name', 'set_variables', 'comment', 'then', 'else', 'input', 'smart_tool'}
    kwargs = {k: (memory.resolve_templates(v) if isinstance(v, str) else v) for k, v in step.items() if k not in reserved}
    
    try:
        if input_list: return tools.execute(tool_name, input_list=input_list)
        return tools.execute(tool_name, **kwargs) if kwargs else tools.execute(tool_name, input_list=[])
    except Exception as e:
        logger.error(f"Tool {tool_name} failed: {e}")
        return StepExecutionResult("failed", message=str(e))

# Special execution logic for the calculate tool
def _execute_calculate_tool(step, memory, tools):
    expr = step.get('expression') or (step.get('input')[0] if 'input' in step and isinstance(step.get('input'), list) else step.get('input'))
    if expr is None: return StepExecutionResult("failed", message="Calculate missing expression")
    
    try:
        result = tools.execute('calculate', expression=memory.resolve_templates(expr))
        _store_tool_result(step, 'calculate', result, memory)
        return result
    except Exception as e:
        logger.error(f"Calculation failed: {e}")
        return StepExecutionResult("failed")

# Applies an LLM-based filter/comment to tool output before storing
def _apply_tool_output_filter(step, result, memory, llm_model):
    comment = memory.resolve_templates(str(step.get('comment')))
    prompt = prompts.get_comment_on_tool_result_prompt(
        json.dumps(serialize_obj(result), indent=2, ensure_ascii=False),
        comment, memory.get_variables_as_json()
    )
    
    try:
        response = litellm.completion(model=llm_model, messages=[{"role": "user", "content": prompt}])
        data = custom_safe_load(clean_json_response(response.choices[0].message.content))
        return data.get('result', result)
    except Exception as e:
        logger.error(f"Post-filter failed: {e}")
        return StepExecutionResult("failed", message=str(e))

# Stores tool results in memory according to set_variables configuration
def _store_tool_result(step, tool_name, result, memory):
    set_vars = step.get('set_variables', [])
    if not set_vars:
        memory.set_variable(f"{tool_name}_result", result)
        if tool_name == 'calculate': memory.set_variable("calculate_result", result)
        return

    mappings = set_vars if isinstance(set_vars, list) else [set_vars]
    for m in mappings:
        if isinstance(m, dict):
            for new_n, old_n in m.items():
                val = _get_value_from_result(result, old_n)
                if val is not None: memory.set_variable(new_n, val)
        else:
            val = _get_value_from_result(result, m)
            if val is not None: memory.set_variable(m, val)
