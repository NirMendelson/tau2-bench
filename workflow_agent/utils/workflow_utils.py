from loguru import logger

# Helper to find subworkflow steps by name from the list of workflows
def get_subworkflow_steps(sub_name, workflows):
    for w in workflows:
        if isinstance(w, list) and len(w) > 0 and w[0].get('subworkflow') == sub_name:
            return w[1:]
        elif isinstance(w, dict) and w.get('subworkflow') == sub_name:
            return w.get('steps', [])
    return None

# Helper to find the full subworkflow definition (metadata + steps)
def get_subworkflow_definition(sub_name, workflows):
    for w in workflows:
        if isinstance(w, list) and len(w) > 0 and w[0].get('subworkflow') == sub_name:
            return w
        elif isinstance(w, dict) and w.get('subworkflow') == sub_name:
            return w
    return None

# Executes the fallback action (transfer to human) when a logic path is missing
def handle_fallback(memory, tools):
    result = tools.execute('transfer_to_human_agents', **{'summary': "Workflow fallback triggered"})
    from .execution_utils import StepExecutionResult
    return StepExecutionResult("blocking", message=result)

# Filters workflows to extract candidates suitable for matching (excluding subworkflows)
def get_match_candidates(workflows):
    candidates = []
    for w in workflows:
        if isinstance(w, list) and len(w) > 0 and 'subworkflow' not in w[0]:
            wf_obj = w[0].copy()
            wf_obj['full_wf'] = w
            candidates.append(wf_obj)
        elif isinstance(w, dict) and 'subworkflow' not in w:
            candidates.append(w)
    return candidates

# Extracts the list of steps to execute for a matching branch (then/else)
def get_branch_steps(step, condition_met):
    branch = step.get('then' if condition_met else 'else') or []
    if isinstance(branch, list): return branch
    if isinstance(branch, dict): return branch.get('steps', [branch])
    return []

# Restores memory to a snapshot while preserving specified return variables
def restore_memory_with_returns(memory, frame):
    snapshot = frame.get("snapshot")
    raw_return_vars = frame.get("return_vars")
    if not snapshot or not raw_return_vars: return
    
    # Handle list of strings, list of dicts [{var: key}], or single string
    return_vars = []
    if isinstance(raw_return_vars, list):
        for item in raw_return_vars:
            if isinstance(item, dict): return_vars.append(list(item.keys())[0])
            else: return_vars.append(item)
    else:
        return_vars = [raw_return_vars]
        
    results = {v: memory.get_variable(v) for v in return_vars if memory.get_variable(v) is not None}
    
    import os
    if os.getenv("DEBUG_MODE", "false").lower() == "true":
        print(f"Restored memory from {frame.get('name')}, kept: {list(results.keys())}")
        
    memory.variables = snapshot
    for v, val in results.items(): memory.set_variable(v, val)
    logger.info(f"Restored memory from {frame.get('name')}, kept: {list(results.keys())}")
