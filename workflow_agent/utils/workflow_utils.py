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
