import os
import litellm
from loguru import logger
from ...actions import prompts
from ...utils.json_utils import clean_json_response, is_null_value, custom_safe_load
from ...utils.execution_utils import StepExecutionResult, create_result_with_blocking_check as _create_result_with_blocking_check

DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

# Checks if field(s) exist in conversation. If yes, sets variable(s). If no, asks user.
def execute_fetch(step, memory, conversation, tone_text, llm_model):
    field = step.get('field')
    fields = step.get('fields')
    target_fields = fields if fields else [field]
    
    missing_fields = [f for f in target_fields if memory.get_variable(f) is None]
    if not missing_fields:
        return StepExecutionResult("completed")
    
    conv_text = memory.get_history_as_text()
    memory_info = memory.get_variables_as_json()
    comment = step.get('comment')
    is_single_field = len(target_fields) == 1
    
    if is_single_field:
        prompt = prompts.get_fetch_single_prompt(target_fields[0], conv_text, tone_text, memory_info, comment)
    else:
        prompt = prompts.get_fetch_multi_prompt(target_fields, conv_text, tone_text, memory_info, comment)
    
    if DEBUG_MODE:
        print(f"--- Fetch Prompt ---\n{prompt}\n--------------------------------")

    response = litellm.completion(model=llm_model, messages=[{"role": "user", "content": prompt}])
    content = clean_json_response(response.choices[0].message.content)

    if DEBUG_MODE:
        print(f"---agent yaml output---\n{content}")
    
    try:
        result = custom_safe_load(content)
        if 'fields' in result:
            fields_data = result.get('fields', {})
            questions_data = result.get('questions', {})
            
            for field_name in target_fields:
                val = fields_data.get(field_name)
                if not is_null_value(val):
                    memory.set_variable(field_name, val)
            
            still_missing = [f for f in target_fields if memory.get_variable(f) is None]
            if not still_missing:
                return StepExecutionResult("completed")
            
            combined_question = result.get('combined_question')
            if combined_question:
                return _create_result_with_blocking_check("fetch", combined_question, memory)
            else:
                questions = [q for f, q in questions_data.items() if f in still_missing and q]
                if questions:
                    combined = " ".join(questions) if len(questions) > 1 else questions[0]
                    return _create_result_with_blocking_check("fetch", combined, memory)
                return _create_result_with_blocking_check("fetch", f"Please provide: {', '.join(still_missing)}", memory)
        else:
            if result.get('found'):
                val = result.get('value')
                if not is_null_value(val):
                    memory.set_variable(target_fields[0], val)
                if memory.get_variable(target_fields[0]) is not None:
                    return StepExecutionResult("completed")
                return execute_fetch(step, memory, conversation, tone_text, llm_model)
            return _create_result_with_blocking_check("fetch", result.get('question'), memory)
    except Exception as e:
        logger.error(f"error parsing fetch response: {e}")
        return StepExecutionResult("failed", message="Failed to extract information.")

# Checks if field exists and satisfies condition. If not, asks user or re-fetches.
def execute_fetch_with_condition(step, memory, conversation, tone_text, llm_model):
    field = step.get('field')
    condition = step.get('condition')
    conv_text = memory.get_history_as_text()
    memory_info = memory.get_variables_as_json()
    comment = step.get('comment')
    
    prompt = prompts.get_fetch_with_condition_prompt(field, condition, conv_text, tone_text, memory_info, comment)
    
    if DEBUG_MODE:
        print(f"--- Fetch with Condition Prompt ---\n{prompt}\n--------------------------------")

    response = litellm.completion(model=llm_model, messages=[{"role": "user", "content": prompt}])
    content = clean_json_response(response.choices[0].message.content)

    if DEBUG_MODE:
        print(f"---agent yaml output---\n{content}")
    
    try:
        result = custom_safe_load(content)
        condition_met = result.get('condition_result')
        if isinstance(condition_met, str):
            condition_met = condition_met.lower() == 'true'

        if result.get('found'):
            val = result.get('value')
            if not is_null_value(val):
                memory.set_variable(field, val)
        
        if condition_met:
            return StepExecutionResult("completed", result={"condition": True})
        
        if result.get('found'):
            return StepExecutionResult("completed", result={"condition": False})
        return _create_result_with_blocking_check("fetch_with_condition", result.get('question'), memory)
    except Exception as e:
        logger.error(f"Error parsing fetch_condition response: {e}")
        return StepExecutionResult("failed")

# Checks if field(s) exist and asks user with a specific message if not.
def execute_fetch_with_message(step, memory, conversation, tone_text, llm_model):
    field = step.get('field')
    fields = step.get('fields')
    target_fields = fields if fields else [field]
    
    missing_fields = [f for f in target_fields if memory.get_variable(f) is None]
    if not missing_fields:
        return StepExecutionResult("completed")
    
    message_template = step.get('message')
    resolved_message = memory.resolve_templates(message_template)
    conv_text = memory.get_history_as_text()
    memory_info = memory.get_variables_as_json()
    comment = step.get('comment')
    
    prompt = prompts.get_fetch_with_message_prompt(target_fields, resolved_message, conv_text, tone_text, memory_info, comment)
    
    if DEBUG_MODE:
        print(f"--- Fetch with Message Prompt ---\n{prompt}\n--------------------------------")
    
    response = litellm.completion(model=llm_model, messages=[{"role": "user", "content": prompt}])
    content = clean_json_response(response.choices[0].message.content)

    if DEBUG_MODE:
        print(f"---agent yaml output---\n{content}")
    
    try:
        result = custom_safe_load(content)
        if 'fields' in result:
            fields_data = result.get('fields', {})
            questions_data = result.get('questions', {})
            
            for field_name in target_fields:
                val = fields_data.get(field_name)
                if not is_null_value(val):
                    memory.set_variable(field_name, val)
            
            still_missing = [f for f in target_fields if memory.get_variable(f) is None]
            if not still_missing:
                return StepExecutionResult("completed")
            
            questions = [q for f, q in questions_data.items() if f in still_missing and q]
            if questions:
                combined = " ".join(questions) if len(questions) > 1 else questions[0]
                return _create_result_with_blocking_check("fetch_with_message", combined, memory)
            return _create_result_with_blocking_check("fetch_with_message", resolved_message, memory)
        else:
            logger.warning(f"unexpected response format from fetch_with_message: {result}")
            return _create_result_with_blocking_check("fetch_with_message", resolved_message, memory)
    except Exception as e:
        logger.error(f"error parsing fetch_with_message response: {e}")
        return _create_result_with_blocking_check("fetch_with_message", resolved_message, memory)
