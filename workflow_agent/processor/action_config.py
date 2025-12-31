ACTION_BLOCKING_CONFIG = {
    # Fetch actions
    "fetch": True,
    "fetch_with_condition": True,
    "fetch_with_message": True,
    
    # Reply actions
    "reply": True, 
    "reply_exact_message": True, 
    
    # Conditional actions
    "conditional": False,  
    "condition": False, 
    "conditional_with_message": False, 
    
    # Tool and workflow actions
    "use_tool": False,  
    "use_subworkflow": False, 
    "instruction": False,  
    
    # Variable and control actions
    "set_variable": False, 
    "loop": False,  
}

def is_action_blocking(action_name: str) -> bool:

    return ACTION_BLOCKING_CONFIG.get(action_name, True)  # Default to blocking for safety

