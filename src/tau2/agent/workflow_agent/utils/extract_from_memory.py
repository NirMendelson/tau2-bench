# Utility functions for extracting data from shared store/memory

from typing import Dict, Any, List, Optional


def get_workflow_context(shared: Dict[str, Any]) -> Dict[str, Any]:
    selected_workflow = shared.get("selected_workflow")
    current_step = shared.get("current_step", {})
    conversation_history = shared.get("conversation_history", [])
    constants = shared.get("constants", {})
    tone_config = shared.get("tone_config", {})
    extracted_fields = shared.get("extracted_fields", {})
    tools = shared.get("tools", [])
    llm = shared.get("llm")
    llm_args = shared.get("llm_args", {})
    
    return {
        "selected_workflow": selected_workflow,
        "current_step": current_step,
        "conversation_history": conversation_history,
        "constants": constants,
        "tone_config": tone_config,
        "extracted_fields": extracted_fields,
        "tools": tools,
        "llm": llm,
        "llm_args": llm_args
    }


def extract_user_input(shared: Dict[str, Any]) -> str:
    context = get_workflow_context(shared)
    conversation_history = context.get("conversation_history", [])
    
    for msg in reversed(conversation_history):
        if msg.get("role") == "user":
            return msg.get("content", "")
    return ""


def extract_workflows(shared: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return shared.get("workflows", {})


def extract_conversation_history(shared: Dict[str, Any]) -> List[Dict[str, Any]]:
    context = get_workflow_context(shared)
    return context.get("conversation_history", [])


def extract_result(exec_res: Optional[Dict[str, Any]]) -> Optional[str]:
    if exec_res is None:
        return None
    return exec_res.get("result")


def extract_scored_workflows(exec_res: Optional[Dict[str, Any]]) -> Optional[List]:
    if exec_res is None:
        return None
    return exec_res.get("scored_workflows")


def extract_candidate_workflows(exec_res: Optional[Dict[str, Any]]) -> Optional[Dict[str, Dict[str, Any]]]:
    if exec_res is None:
        return None
    return exec_res.get("candidate_workflows")


def extract_user_input_from_exec(exec_res: Optional[Dict[str, Any]]) -> Optional[str]:
    if exec_res is None:
        return None
    return exec_res.get("user_input")


def extract_workflow_definition(workflows: Dict[str, Dict[str, Any]], workflow_name: str) -> Dict[str, Any]:
    return workflows.get(workflow_name, {})


def extract_when_text(workflow_def: Dict[str, Any]) -> str:
    return workflow_def.get('when', 'N/A')

