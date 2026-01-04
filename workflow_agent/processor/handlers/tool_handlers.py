import os
import json
import litellm
from loguru import logger
from ...actions import prompts
from ...utils.json_utils import clean_json_response, custom_safe_load
from ...utils.execution_utils import StepExecutionResult

DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

# Serializes objects (including Pydantic models and dates) for use in prompts
def _serialize_for_prompt(obj):
    from pydantic import BaseModel
    import datetime
    if isinstance(obj, BaseModel):
        return obj.model_dump()
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    if isinstance(obj, list):
        return [_serialize_for_prompt(item) for item in obj]
    if isinstance(obj, dict):
        return {k: _serialize_for_prompt(v) for k, v in obj.items()}
    return obj

# Extracts a value from a tool result object or dictionary
def _get_value_from_result(result, source_name):
    if source_name == 'result':
        return result
    if isinstance(result, dict):
        return result.get(source_name)
    elif hasattr(result, source_name):
        return getattr(result, source_name)
    return None

# Calls an external tool and handles its output, including smart resolution and filtering
def execute_use_tool(step, memory, tools, llm_model, tone_text):
    tool_name = step.get('tool_name')
    if not tools.has_tool(tool_name):
        return StepExecutionResult("failed", message=f"Tool {tool_name} not found")

    input_list = None
    if 'input' in step:
        input_value = step['input']
        input_list = [memory.resolve_templates(v) if isinstance(v, str) else v for v in (input_value if isinstance(input_value, list) else [input_value])]

    skip_post_filter = False
    result = None

    if step.get('smart_tool'):
        result, skip_post_filter = _execute_smart_tool(step, tool_name, memory, tools, llm_model, tone_text, input_list)
        if isinstance(result, StepExecutionResult): return result
    else:
        result = _execute_normal_tool(step, tool_name, memory, tools, input_list)
        if isinstance(result, StepExecutionResult): return result

    if step.get('comment') and not skip_post_filter:
        result = _apply_tool_output_filter(step, result, memory, llm_model)
        if isinstance(result, StepExecutionResult): return result

    _store_tool_result(step, tool_name, result, memory)
    return StepExecutionResult("completed")

# Handles smart tool resolution using LLM to determine arguments
def _execute_smart_tool(step, tool_name, memory, tools, llm_model, tone_text, input_list):
    logger.info(f"Using smart tool resolver for tool: {tool_name}")
    tool_obj = tools.get_tool(tool_name)
    if not tool_obj:
        return StepExecutionResult("failed", message=f"Tool object for {tool_name} not found"), False
    
    prompt = prompts.get_smart_tool_resolver_prompt(
        tool_name, tool_obj._get_description(), 
        json.dumps(tool_obj.params.model_json_schema(), indent=2),
        memory.get_variables_as_json(), tone_text, memory.get_history_as_text(),
        step.get('comment'), input_data=input_list
    )
    
    if DEBUG_MODE:
        print(f"--- Smart Tool Resolver Prompt ---\n{prompt}\n--------------------------------")
        
    try:
        response = litellm.completion(model=llm_model, messages=[{"role": "user", "content": prompt}])
        content = clean_json_response(response.choices[0].message.content)
        resolve_data = custom_safe_load(content)
        resolved_args = resolve_data.get('arguments', {})
        logger.info(f"Smart tool resolver reasoning: {resolve_data.get('reasoning')}")
        
        result = tools.execute(tool_name, **resolved_args)
        return result, True
    except Exception as e:
        logger.error(f"Smart tool resolver failed: {e}")
        return StepExecutionResult("failed", message=f"Smart tool resolver failed: {str(e)}"), False

# Handles normal tool execution logic, including special handling for calculate
def _execute_normal_tool(step, tool_name, memory, tools, input_list):
    if tool_name == 'calculate':
        return _execute_calculate_tool(step, memory, tools)
    
    kwargs = {}
    reserved = ['id', 'action', 'tool_name', 'set_variables', 'comment', 'then', 'else', 'input', 'smart_tool']
    for key, value in step.items():
        if key not in reserved:
            kwargs[key] = memory.resolve_templates(value) if isinstance(value, str) else (
                [memory.resolve_templates(v) if isinstance(v, str) else v for v in value] if isinstance(value, list) else value
            )
    
    try:
        if input_list is not None:
            return tools.execute(tool_name, input_list=input_list)
        return tools.execute(tool_name, **kwargs) if kwargs else tools.execute(tool_name, input_list=[])
    except Exception as e:
        logger.error(f"tool call {tool_name} failed: {e}")
        return StepExecutionResult("failed", message=str(e))

# Special execution logic for the calculate tool
def _execute_calculate_tool(step, memory, tools):
    expression = step.get('expression') or (step.get('input')[0] if 'input' in step and isinstance(step.get('input'), list) else step.get('input'))
    if expression is None:
        return StepExecutionResult("failed", message="calculate tool missing expression")
    
    try:
        result = tools.execute('calculate', expression=memory.resolve_templates(expression))
        _store_tool_result(step, 'calculate', result, memory)
        return result
    except Exception as e:
        logger.error(f"calculation failed: {e}")
        return StepExecutionResult("failed")

# Applies an LLM-based filter/comment to tool output before storing
def _apply_tool_output_filter(step, result, memory, llm_model):
    comment = step.get('comment')
    resolved_comment = memory.resolve_templates(str(comment))
    serialized_result = _serialize_for_prompt(result)
    
    prompt = prompts.get_comment_on_tool_result_prompt(
        json.dumps(serialized_result, indent=2, ensure_ascii=False),
        resolved_comment, memory.get_variables_as_json()
    )
    
    try:
        response = litellm.completion(model=llm_model, messages=[{"role": "user", "content": prompt}])
        comment_data = custom_safe_load(clean_json_response(response.choices[0].message.content))
        if comment_data and 'result' in comment_data:
            return comment_data['result']
        return result
    except Exception as e:
        logger.error(f"Error during tool result commenting: {e}")
        return StepExecutionResult("failed", message=f"Failed to process comment: {str(e)}")

# Stores tool results in memory according to set_variables configuration
def _store_tool_result(step, tool_name, result, memory):
    set_vars = step.get('set_variables', [])
    if not set_vars:
        memory.set_variable(f"{tool_name}_result", result)
        if tool_name == 'calculate': memory.set_variable("calculate_result", result)
        return

    if isinstance(set_vars, dict):
        for new_name, old_name in set_vars.items():
            val = _get_value_from_result(result, old_name)
            if val is not None: memory.set_variable(new_name, val)
    else:
        for item in set_vars:
            if isinstance(item, dict):
                for new_name, old_name in item.items():
                    val = _get_value_from_result(result, old_name)
                    if val is not None: memory.set_variable(new_name, val)
            else:
                val = _get_value_from_result(result, item)
                if val is not None: memory.set_variable(item, val)
