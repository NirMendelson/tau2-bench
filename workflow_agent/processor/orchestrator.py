from . import step_executor
from ..matching import matcher
import os
from loguru import logger

DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"


def run_workflow_cycle(user_message, memory, workflows, tone_text, llm_model, tools):
    """
    Called on every user message.
    1. Update memory with new message.
    2. Check for workflow match/switch.
    3. Run or continue steps until blocking or completion.
    """
    # 1. Update history
    memory.add_to_history("user", user_message)

    # 2. Check for workflow match
    # We always check for a better match or if we are idle
    # If we are in a workflow but the user says "cancel" or "start over", we might need to switch.
    # The requirement says: "even if we are in the middle of a workflow there will be a check if we should switch a workflow after every message."
    
    # We should filter out subworkflows from matching candidates
    # "the agent cannot choose this workflow [subworkflow]"
    candidate_workflows = [w for w in workflows if 'subworkflow' not in w]
    
    matched_workflow = matcher.match_workflow(
        memory.get_history(), 
        candidate_workflows, 
        tone_text, 
        llm_model,
        current_workflow_name=memory.workflow_name
    )
    
    # Logic: 
    # - If matched_workflow is different from current -> Switch (clear stack)
    # - If None -> Continue current (if active)
    # - If matched same -> Continue current
    
    # Get current root workflow name
    current_root = memory.workflow_name
    
    if matched_workflow:
        new_wf_name = matched_workflow['workflow']
        if new_wf_name != current_root:
            # Switch workflow!
            memory.reset_workflow_state()
            memory.set_workflow_state(workflow_name=new_wf_name)
            memory.stack = [] # Clear stack
            
            # Push initial frame
            initial_steps = matched_workflow.get('steps', [])
            memory.stack.append({
                "steps": initial_steps,
                "index": 0,
                "name": new_wf_name
            })
            
            # Also reset relevant variables? 
            # Usually we might want to keep user_id etc. 
            # So we don't clear all variables, just the flow state.

    # 3. Execute Loop
    messages_to_return = []
    
    while memory.stack:
        # Get current frame
        frame = memory.stack[-1]
        steps = frame['steps']
        index = frame['index']
        
        # Check if done with this frame
        if index >= len(steps):
            # Frame is complete - pop it and continue with parent frame
            popped_frame = memory.stack.pop()
            # If we popped a branch frame (indicated by name containing '_condition' or being a subworkflow)
            # and there's still a parent frame, we don't clear messages_to_return
            # as they should be sent to the user
            continue
            
        current_step = steps[index]
        
        # Update step_id in memory for tracking (optional)
        if 'id' in current_step:
            memory.step_id = current_step['id']
            
        # Execute Step
        result = step_executor.execute_step(
            current_step, 
            memory, 
            memory.get_history(), # Pass raw list, executor calls get_as_text
            tone_text, 
            llm_model, 
            tools,
            workflows
        )
        
        if result.status == "blocking":
            # Stop execution, return accumulated messages + blocking message to user
            blocking_message = result.message
            if blocking_message:
                messages_to_return.append(blocking_message)
                memory.add_to_history("assistant", blocking_message)
            return "\n".join(messages_to_return)
            
        elif result.status == "failed":
            # Fallback
            fb_result = step_executor.handle_fallback(memory, tools)
            messages_to_return.append(fb_result.message)
            memory.add_to_history("assistant", fb_result.message)
            # Clear stack to stop?
            memory.stack = []
            return "\n".join(messages_to_return)
            
        elif result.status == "completed":
            # Check if there's a message from this completed step (e.g., non-blocking reply)
            if hasattr(result, 'message') and result.message:
                messages_to_return.append(result.message)
                # Message already added to history by the step executor for non-blocking actions
            
            # Check for special results (branching / subworkflow related)
            
            # 1. Condition Result
            if hasattr(result, 'result') and result.result and 'condition' in result.result:
                cond_true = result.result['condition']
                
                # Push new frame based on result
                branch_steps = []
                if cond_true:
                    then_block = current_step.get('then') or {}
                    if 'steps' in then_block:
                        branch_steps = then_block['steps']
                    elif 'id' in then_block or 'action' in then_block:
                        branch_steps = [then_block]
                else:
                    else_block = current_step.get('else') or {}
                    if 'steps' in else_block:
                        branch_steps = else_block['steps']
                    elif 'id' in else_block or 'action' in else_block:
                        branch_steps = [else_block]
                
                # If we have steps to execute, push them
                if branch_steps:
                    memory.stack.append({
                        "steps": branch_steps,
                        "index": 0,
                        "name": f"{frame['name']}_condition"
                    })
                    frame['index'] += 1
                    continue # Loop will pick up new top frame
                    
            # 2. Subworkflow
            elif current_step.get('action') == 'use_subworkflow':
                sub_name = current_step.get('subworkflow')
                sub_wf_obj = next((w for w in workflows if w.get('subworkflow') == sub_name), None)
                
                if sub_wf_obj and 'steps' in sub_wf_obj:
                    memory.stack.append({
                        "steps": sub_wf_obj['steps'],
                        "index": 0,
                        "name": sub_name
                    })
                    frame['index'] += 1
                    continue
            
            # Normal completion 
            frame['index'] += 1

    # Stack empty -> Workflow done (or idle)
    if not memory.stack:
        logger.info(f"Workflow stack is empty. Returning: {' '.join(messages_to_return) if messages_to_return else 'Task completed.'}")
    
    return "\n".join(messages_to_return) if messages_to_return else "Task completed."
