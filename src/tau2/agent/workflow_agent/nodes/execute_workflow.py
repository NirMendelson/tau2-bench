from pocketflow import Node
from ..utils.extract_from_memory import get_workflow_context
from ..utils.workflow_executor import execute_workflow_step


class ExecuteWorkflowNode(Node):
    
    def prep(self, shared):
        return get_workflow_context(shared)
    
    def exec(self, prep_res):
        return execute_workflow_step(prep_res)
    
    def post(self, shared, prep_res, exec_res):
        if exec_res.get("status") == "complete":
            # Workflow complete
            shared["current_step"] = None
        elif exec_res.get("status") == "no_workflow":
            # No workflow matched
            shared["current_step"] = None
        elif exec_res.get("status") == "waiting_for_input":
            # Waiting for user input - keep current step so workflow can resume
            # next_step_id will be the same as current_step_id for fetch actions
            # or the actual next step for reply actions
            next_step_id = exec_res.get("next_step_id")
            if next_step_id:
                shared["current_step"] = {"step_id": next_step_id}
            else:
                shared["current_step"] = None
        elif exec_res.get("status") == "tool_call_needed":
            # Tool call prepared - add tool_calls to conversation_history
            tool_call_info = exec_res.get("tool_call_info")
            if tool_call_info:
                # Add assistant message with tool_calls to conversation_history
                shared["conversation_history"].append({
                    "role": "assistant",
                    "content": None,  # No text content when making tool call
                    "tool_calls": [{
                        "id": tool_call_info["tool_call_id"],
                        "name": tool_call_info["tool_name"],
                        "arguments": tool_call_info["tool_arguments"],
                        "requestor": "assistant"
                    }]
                })
            
            # Keep current step so workflow can resume after tool result arrives
            current_step_id = shared.get("current_step", {}).get("step_id")
            if current_step_id:
                shared["current_step"] = {"step_id": current_step_id}
            else:
                shared["current_step"] = None
        else:
            # Update to next step ID (status is "continue")
            next_step_id = exec_res.get("next_step_id")
            if next_step_id:
                shared["current_step"] = {"step_id": next_step_id}
            else:
                shared["current_step"] = None
        
        # Update extracted fields
        if "extracted_fields" in exec_res:
            shared["extracted_fields"] = exec_res["extracted_fields"]
        
        # Determine action for flow
        if exec_res.get("status") == "complete":
            # Workflow complete - return None to end flow naturally
            return None
        elif exec_res.get("status") == "no_workflow":
            # No workflow matched - return None to end flow naturally
            return None
        elif exec_res.get("status") == "waiting_for_input":
            # Waiting for user input - end flow, will resume when new input arrives
            return None
        elif exec_res.get("status") == "tool_call_needed":
            # Tool call needed - end flow, will resume when tool result arrives
            return None
        elif exec_res.get("next_step_id"):
            # Continue executing workflow
            return "continue"
        else:
            # No next step - return None to end flow naturally
            return None

