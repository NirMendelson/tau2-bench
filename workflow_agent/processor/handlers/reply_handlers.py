import os
import litellm
from ...actions import prompts
from ...utils.execution_utils import create_result_with_blocking_check

DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

# Sends a message to the user based on the reply action template
def execute_reply(step, memory, conversation, tone_text, llm_model):
    message_template = step.get('message')
    resolved_message = memory.resolve_templates(message_template)
    conv_text = memory.get_history_as_text()
    memory_info = memory.get_variables_as_json()
    comment = step.get('comment')
    
    prompt = prompts.get_reply_prompt(resolved_message, tone_text, conv_text, memory_info, comment)
    
    if DEBUG_MODE:
        print(f"--- Reply Prompt ---\n{prompt}\n--------------------------------")

    response = litellm.completion(
        model=llm_model,
        messages=[{"role": "user", "content": prompt}]
    )
    
    final_message = response.choices[0].message.content.strip()

    if DEBUG_MODE:
        print(f"---agent output---\n{final_message}")
    
    return create_result_with_blocking_check("reply", final_message, memory)

# Sends an exact message to the user without template modification
def execute_reply_exact_message(step, memory, conversation, tone_text, llm_model):
    message_template = step.get('message')
    resolved_message = memory.resolve_templates(message_template)
    conv_text = memory.get_history_as_text()
    comment = step.get('comment')
    
    prompt = prompts.get_reply_exact_message_prompt(resolved_message, tone_text, conv_text, comment)
    
    if DEBUG_MODE:
        print(f"--- Reply Exact Message Prompt ---\n{prompt}\n--------------------------------")

    response = litellm.completion(
        model=llm_model,
        messages=[{"role": "user", "content": prompt}]
    )
    
    final_message = response.choices[0].message.content.strip()

    if DEBUG_MODE:
        print(f"---agent output---\n{final_message}")
    
    return create_result_with_blocking_check("reply_exact_message", final_message, memory)
