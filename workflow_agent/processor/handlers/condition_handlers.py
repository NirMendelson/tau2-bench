import os
import litellm
from loguru import logger
from ...actions import prompts
from ...utils.json_utils import clean_json_response, custom_safe_load
from ...utils.execution_utils import StepExecutionResult, create_result_with_blocking_check as _create_result_with_blocking_check

DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

# Evaluates a condition and determines logic flow.
def execute_condition(step, memory, conversation, tone_text, llm_model):
    condition = step.get('condition')
    condition_str = memory.resolve_templates(condition) if isinstance(condition, str) else str(condition)
    
    conv_text = memory.get_history_as_text()
    memory_info = memory.get_variables_as_json()
    comment = step.get('comment')
    prompt = prompts.get_condition_eval_prompt(condition_str, memory_info, conv_text, comment)
    
    if DEBUG_MODE:
        print(f"--- Condition Prompt ---\n{prompt}\n--------------------------------")
        
    response = litellm.completion(model=llm_model, messages=[{"role": "user", "content": prompt}])
    content = response.choices[0].message.content.strip()
    
    if DEBUG_MODE:
        print(f"---agent output---\n{content}")
        
    is_true = content.lower() == 'true'
    return StepExecutionResult("completed", result={"condition": is_true})

# Evaluates a condition and optionally sends a message based on the result.
def execute_conditional_with_message(step, memory, conversation, tone_text, llm_model):
    condition = step.get('condition')
    condition_str = memory.resolve_templates(condition) if isinstance(condition, str) else str(condition)
    
    message_on_true = memory.resolve_templates(step.get('message_on_true')) if step.get('message_on_true') else None
    message_on_false = memory.resolve_templates(step.get('message_on_false')) if step.get('message_on_false') else None
    
    conv_text = memory.get_history_as_text()
    memory_info = memory.get_variables_as_json()
    prompt = prompts.get_conditional_with_message_prompt(
        condition_str, memory_info, conv_text, tone_text,
        message_on_true=message_on_true, message_on_false=message_on_false,
        comment=step.get('comment')
    )
    
    if DEBUG_MODE:
        print(f"--- Conditional with Message Prompt ---\n{prompt}\n--------------------------------")
        
    response = litellm.completion(model=llm_model, messages=[{"role": "user", "content": prompt}])
    content = response.choices[0].message.content.strip()
    
    if DEBUG_MODE:
        print(f"---agent output---\n{content}\n--------------------------------")
    
    try:
        cleaned_content = clean_json_response(content)
        result = custom_safe_load(cleaned_content)
        
        if not result or 'condition_result' not in result:
            logger.error(f"invalid response format from conditional_with_message: {content}")
            return StepExecutionResult("failed", message="Failed to parse condition evaluation.")
        
        condition_result = result.get('condition_result')
        is_true = condition_result.lower() == 'true' if isinstance(condition_result, str) else bool(condition_result)
        message = result.get('message')
        
        if message and message.strip() and message.lower() != 'null':
            return _create_result_with_blocking_check("conditional_with_message", message.strip(), memory, result={"condition": is_true})
        
        return StepExecutionResult("completed", result={"condition": is_true})
    except Exception as e:
        logger.error(f"error parsing conditional_with_message response: {e}")
        return StepExecutionResult("failed", message="Failed to parse condition evaluation.")
