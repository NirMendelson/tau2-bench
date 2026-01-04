from ..processor.action_config import is_action_blocking

# Data class to hold the result of a step execution
class StepExecutionResult:
    def __init__(self, status, message=None, next_step_id=None, result=None):
        self.status = status  # 'completed', 'blocking', 'failed'
        self.message = message
        self.next_step_id = next_step_id
        self.result = result

# Helper to create StepExecutionResult while checking if the action should block the flow
def create_result_with_blocking_check(action_name, message, memory, result_data=None):
    if is_action_blocking(action_name):
        return StepExecutionResult("blocking", message=message, result=result_data)
    else:
        if message:
            memory.add_to_history("assistant", message)
        return StepExecutionResult("completed", message=message, result=result_data)
