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
    # With the new format, workflows are lists of objects. Metadata is in the first object.
    candidate_workflows = []
    for w in workflows:
        if isinstance(w, list) and len(w) > 0:
            metadata = w[0]
            if 'subworkflow' not in metadata:
                # Construct a compatible object for the matcher
                wf_match_obj = metadata.copy()
                wf_match_obj['full_wf'] = w # Keep reference to full list
                candidate_workflows.append(wf_match_obj)
        elif isinstance(w, dict):
            # Fallback for old format if any exist
            if 'subworkflow' not in w:
                candidate_workflows.append(w)
    
    matched_metadata = matcher.match_workflow(
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
    
    if matched_metadata:
        new_wf_name = matched_metadata['workflow']
        if new_wf_name != current_root:
            # Switch workflow!
            memory.reset_workflow_state()
            memory.set_workflow_state(workflow_name=new_wf_name)
            memory.stack = [] # Clear stack
            
            # Push initial frame
            # Metadata is in the first object, steps are subsequent objects
            full_wf = matched_metadata.get('full_wf')
            if full_wf and isinstance(full_wf, list):
                initial_steps = full_wf[1:]
            else:
                initial_steps = matched_metadata.get('steps', [])
                
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
            
            # Implementation of "Subworkflows as Functions":
            # If the popped frame was a subworkflow and had a return/snapshot config,
            # we restore the memory state while keeping only the requested variables.
            if "snapshot" in popped_frame and popped_frame.get("return_vars"):
                snapshot = popped_frame["snapshot"]
                return_vars = popped_frame["return_vars"]
                if isinstance(return_vars, str):
                    return_vars = [return_vars]
                
                # Keep return values from the current (dirty) memory
                results_to_keep = {}
                for var in return_vars:
                    val = memory.get_variable(var)
                    if val is not None:
                        results_to_keep[var] = val
                
                # Restore memory to snapshot
                memory.variables = snapshot
                
                # Inject return values back into the clean state
                for var, val in results_to_keep.items():
                    memory.set_variable(var, val)
                
                logger.info(f"Subworkflow {popped_frame.get('name')} completed. Restored memory and kept: {list(results_to_keep.keys())}")

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
            workflows,
            is_root=True
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
                    then_block = current_step.get('then') or []
                    if isinstance(then_block, list):
                        branch_steps = then_block
                    elif isinstance(then_block, dict):
                        if 'steps' in then_block:
                            branch_steps = then_block['steps']
                        else:
                            # Single step
                            branch_steps = [then_block]
                else:
                    else_block = current_step.get('else') or []
                    if isinstance(else_block, list):
                        branch_steps = else_block
                    elif isinstance(else_block, dict):
                        if 'steps' in else_block:
                            branch_steps = else_block['steps']
                        else:
                            # Single step
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
                # Find subworkflow by searching first object of each list
                sub_wf_list = None
                for w in workflows:
                    if isinstance(w, list) and len(w) > 0 and w[0].get('subworkflow') == sub_name:
                        sub_wf_list = w
                        break
                    elif isinstance(w, dict) and w.get('subworkflow') == sub_name:
                        # Fallback for old format
                        sub_wf_list = w
                        break
                
                if sub_wf_list:
                    metadata = sub_wf_list[0] if isinstance(sub_wf_list, list) else sub_wf_list
                    return_vars = metadata.get('return')
                    
                    if isinstance(sub_wf_list, list):
                        sub_steps = sub_wf_list[1:]
                    else:
                        sub_steps = sub_wf_list.get('steps', [])
                        
                    frame_data = {
                        "steps": sub_steps,
                        "index": 0,
                        "name": sub_name
                    }
                    
                    # If this subworkflow has a return field, prepare for functional scoping
                    if return_vars:
                        frame_data["snapshot"] = memory.variables.copy()
                        frame_data["return_vars"] = return_vars
                        logger.info(f"Entering subworkflow {sub_name} with functional scoping. Will return: {return_vars}")
                        
                    memory.stack.append(frame_data)
                    frame['index'] += 1
                    continue
            
            # Normal completion 
            frame['index'] += 1

    # Stack empty -> Workflow done (or idle)
    if not memory.stack:
        logger.info(f"Workflow stack is empty. Returning: {' '.join(messages_to_return) if messages_to_return else 'Task completed.'}")
    
    return "\n".join(messages_to_return) if messages_to_return else "Task completed."
