from loguru import logger
from . import step_executor
from ..matching import matcher
from ..utils import workflow_utils

# Main entry point for processing a user message against active or new workflows
def run_workflow_cycle(user_message, memory, workflows, tone_text, llm_model, tools):
    memory.add_to_history("user", user_message)
    _check_and_switch_workflow(memory, workflows, tone_text, llm_model)
    
    messages = []
    while memory.stack:
        frame = memory.stack[-1]
        if frame['index'] >= len(frame['steps']):
            workflow_utils.restore_memory_with_returns(memory, memory.stack.pop())
            continue
            
        step = frame['steps'][frame['index']]
        if 'id' in step: memory.step_id = step['id']
        
        import os
        if os.getenv("DEBUG_MODE", "false").lower() == "true":
            print(f"--- Executing Step in {frame.get('name')}: {step.get('id')} ({step.get('action')}) ---")
            
        result = step_executor.execute_step(
            step, memory, memory.get_history(), tone_text, llm_model, tools, workflows, is_root=True
        )
        
        status_handled = _handle_step_result(result, messages, memory, tools)
        if status_handled: return status_handled
            
        frame['index'] += 1
        _process_post_step_logic(step, result, memory, workflows, frame)
        
    return "\n".join(messages) if messages else "Task completed."

# Checks if a new workflow should be started or the current one switched
def _check_and_switch_workflow(memory, workflows, tone_text, llm_model):
    candidates = workflow_utils.get_match_candidates(workflows)
    matched = matcher.match_workflow(
        memory.get_history(), candidates, tone_text, llm_model, current_workflow_name=memory.workflow_name
    )
    
    if matched and matched['workflow'] != memory.workflow_name:
        memory.reset_workflow_state()
        memory.set_workflow_state(workflow_name=matched['workflow'])
        memory.stack = []
        
        full_wf = matched.get('full_wf')
        steps = full_wf[1:] if isinstance(full_wf, list) else matched.get('steps', [])
        memory.stack.append({"steps": steps, "index": 0, "name": matched['workflow']})

# Handles the execution status (blocking/failed/completed) of a step
def _handle_step_result(result, messages, memory, tools):
    if result.status == "blocking":
        if result.message:
            messages.append(result.message)
            memory.add_to_history("assistant", result.message)
        return "\n".join(messages)
        
    if result.status == "failed":
        fb = workflow_utils.handle_fallback(memory, tools)
        messages.append(fb.message)
        memory.add_to_history("assistant", fb.message)
        memory.stack = []
        return "\n".join(messages)
        
    if hasattr(result, 'message') and result.message:
        messages.append(result.message)
    return None

# Manages branching and function transitions after a step completes
def _process_post_step_logic(step, result, memory, workflows, current_frame):
    if hasattr(result, 'result') and result.result and 'condition' in result.result:
        branch_steps = workflow_utils.get_branch_steps(step, result.result['condition'])
        if branch_steps:
            memory.stack.append({"steps": branch_steps, "index": 0, "name": f"{current_frame['name']}_branch"})
            
    elif step.get('action') == 'use_function':
        func_name = step.get('function')
        func_def = workflow_utils.get_function_definition(func_name, workflows)
        if func_def:
            meta = func_def[0] if isinstance(func_def, list) else func_def
            ret = meta.get('return') or step.get('set_variables') or step.get('set_variable')
            steps = func_def[1:] if isinstance(func_def, list) else func_def.get('steps', [])
            
            frame_data = {"steps": steps, "index": 0, "name": func_name}
            if ret:
                frame_data["snapshot"] = memory.variables.copy()
                frame_data["return_vars"] = ret
            memory.stack.append(frame_data)
        else:
            logger.warning(f"Function {func_name} not found in workflows")
    elif step.get('action') == 'use_subworkflow':  # Backward compatibility
        sub_name = step.get('subworkflow')
        sub_def = workflow_utils.get_subworkflow_definition(sub_name, workflows)
        if sub_def:
            meta = sub_def[0] if isinstance(sub_def, list) else sub_def
            ret = meta.get('return') or step.get('set_variables') or step.get('set_variable')
            steps = sub_def[1:] if isinstance(sub_def, list) else sub_def.get('steps', [])
            
            frame_data = {"steps": steps, "index": 0, "name": sub_name}
            if ret:
                frame_data["snapshot"] = memory.variables.copy()
                frame_data["return_vars"] = ret
            memory.stack.append(frame_data)
