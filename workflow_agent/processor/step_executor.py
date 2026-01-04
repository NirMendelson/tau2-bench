import os
from .handlers import reply_handlers, fetch_handlers, condition_handlers, tool_handlers, flow_handlers
from ..utils.execution_utils import StepExecutionResult

DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

# Main entry point for executing an individual step based on its action type.
def execute_step(step, memory, conversation, tone_text, llm_model, tools, workflows, is_root=False):
    action = step.get('action')
    result = None
    
    if action == 'fetch':
        result = fetch_handlers.execute_fetch(step, memory, conversation, tone_text, llm_model)
    elif action == 'fetch_with_condition':
        result = fetch_handlers.execute_fetch_with_condition(step, memory, conversation, tone_text, llm_model)
    elif action == 'fetch_with_message':
        result = fetch_handlers.execute_fetch_with_message(step, memory, conversation, tone_text, llm_model)
    elif action == 'reply':
        result = reply_handlers.execute_reply(step, memory, conversation, tone_text, llm_model)
    elif action == 'reply_exact_message':
        result = reply_handlers.execute_reply_exact_message(step, memory, conversation, tone_text, llm_model)
    elif action == 'set_variable':
        result = flow_handlers.execute_set_variable(step, memory)
    elif action == 'conditional' or action == 'condition':
        result = condition_handlers.execute_condition(step, memory, conversation, tone_text, llm_model)
    elif action == 'conditional_with_message':
        result = condition_handlers.execute_conditional_with_message(step, memory, conversation, tone_text, llm_model)
    elif action == 'use_tool':
        result = tool_handlers.execute_use_tool(step, memory, tools, llm_model, tone_text)
    elif action == 'instruction':
        result = flow_handlers.execute_instruction(step, memory, conversation, tone_text, llm_model, tools, workflows)
    elif action == 'loop':
        result = flow_handlers.execute_loop(step, memory, conversation, tone_text, llm_model, tools, workflows)
    elif action == 'use_subworkflow':
        if not is_root:
            sub_name = step.get('subworkflow')
            return flow_handlers.execute_subworkflow_recursive(sub_name, memory, conversation, tone_text, llm_model, tools, workflows, step=step)
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
            if 'steps' in branch_block: branch_steps = branch_block['steps']
            elif 'id' in branch_block or 'action' in branch_block: branch_steps = [branch_block]
        
        if branch_steps:
            for b_step in branch_steps:
                b_result = execute_step(b_step, memory, conversation, tone_text, llm_model, tools, workflows, is_root=False)
                if b_result.status != "completed": return b_result
                    
    return result
