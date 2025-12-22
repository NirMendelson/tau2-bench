from typing import Dict, List, Any, Optional, Tuple


def build_step_registry(steps: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    registry = {}
    
    def _process_step(step: Dict[str, Any], parent_id: Optional[str] = None):
        step_id = step.get("id")
        if not step_id:
            return
        
        # Store the step in registry
        registry[step_id] = step.copy()
        
        # Process conditional branches (for both "conditional" and "fetch_with_condition" actions)
        if step.get("action") == "conditional" or step.get("action") == "fetch_with_condition":
            # Process then branch
            then_branch = step.get("then")
            if then_branch:
                # Handle then branch with steps array (for fetch_with_condition)
                if isinstance(then_branch, dict) and "steps" in then_branch:
                    for branch_step in then_branch["steps"]:
                        _process_step(branch_step, step_id)
                elif isinstance(then_branch, list):
                    # Multiple steps in then branch
                    for branch_step in then_branch:
                        _process_step(branch_step, step_id)
                else:
                    # Single action in then branch
                    if then_branch.get("id"):
                        _process_step(then_branch, step_id)
            
            # Process else branch
            else_branch = step.get("else")
            if else_branch:
                # Handle else branch with steps array (for fetch_with_condition)
                if isinstance(else_branch, dict) and "steps" in else_branch:
                    for branch_step in else_branch["steps"]:
                        _process_step(branch_step, step_id)
                elif isinstance(else_branch, list):
                    # Multiple steps in else branch
                    for branch_step in else_branch:
                        _process_step(branch_step, step_id)
                else:
                    # Single action in else branch
                    if else_branch.get("id"):
                        _process_step(else_branch, step_id)
        
        # Process nested steps (for steps arrays in branches)
        if "steps" in step:
            for nested_step in step["steps"]:
                _process_step(nested_step, step_id)
    
    # Process all top-level steps
    for step in steps:
        _process_step(step)
    
    return registry


def get_next_step_id(
    current_step_id: str,
    steps: List[Dict[str, Any]],
    condition_result: Optional[bool] = None
) -> Optional[str]:
    def _find_step_and_get_next(step_id: str, step_list: List[Dict[str, Any]], 
                                 top_level_steps: List[Dict[str, Any]],
                                 conditional_step_idx: Optional[int] = None,
                                 condition_result: Optional[bool] = None) -> Optional[str]:
        for idx, step in enumerate(step_list):
            step_step_id = step.get("id")
            
            # Found the current step
            if step_step_id == step_id:
                # If this step has branches and condition_result is provided, check branches first
                if condition_result is not None and (step.get("action") == "conditional" or step.get("action") == "fetch_with_condition"):
                    if condition_result is True:
                        then_branch = step.get("then")
                        if then_branch:
                            # Handle then branch with steps array
                            if isinstance(then_branch, dict) and "steps" in then_branch:
                                steps_list = then_branch.get("steps", [])
                                if len(steps_list) > 0:
                                    return steps_list[0].get("id")
                            # Handle then branch as list
                            elif isinstance(then_branch, list) and len(then_branch) > 0:
                                return then_branch[0].get("id")
                            # Handle then branch as single step
                            elif isinstance(then_branch, dict) and then_branch.get("id"):
                                return then_branch.get("id")
                    else:
                        else_branch = step.get("else")
                        if else_branch:
                            # Handle else branch with steps array
                            if isinstance(else_branch, dict) and "steps" in else_branch:
                                steps_list = else_branch.get("steps", [])
                                if len(steps_list) > 0:
                                    return steps_list[0].get("id")
                            # Handle else branch as list
                            elif isinstance(else_branch, list) and len(else_branch) > 0:
                                return else_branch[0].get("id")
                            # Handle else branch as single step
                            elif isinstance(else_branch, dict) and else_branch.get("id"):
                                return else_branch.get("id")
                
                # Check if there's a next step in the same list
                if idx + 1 < len(step_list):
                    return step_list[idx + 1].get("id")
                # If we're in a branch, return next step after parent conditional
                if conditional_step_idx is not None:
                    # Find the parent conditional in top-level steps
                    if conditional_step_idx + 1 < len(top_level_steps):
                        return top_level_steps[conditional_step_idx + 1].get("id")
                return None
            
            # Check conditional branches (both conditional and fetch_with_condition)
            if step.get("action") == "conditional" or step.get("action") == "fetch_with_condition":
                conditional_idx = None
                # Find this conditional in top-level steps
                for top_idx, top_step in enumerate(top_level_steps):
                    if top_step.get("id") == step.get("id"):
                        conditional_idx = top_idx
                        break
                
                # Check then branch
                then_branch = step.get("then")
                if then_branch:
                    if isinstance(then_branch, list):
                        result = _find_step_and_get_next(step_id, then_branch, top_level_steps, conditional_idx, condition_result)
                        if result is not None:
                            return result
                    elif isinstance(then_branch, dict) and "steps" in then_branch:
                        # Handle then branch with steps array
                        result = _find_step_and_get_next(step_id, then_branch["steps"], top_level_steps, conditional_idx, condition_result)
                        if result is not None:
                            return result
                    elif then_branch.get("id") == step_id:
                        # Single action in then - next is after conditional
                        if conditional_idx is not None and conditional_idx + 1 < len(top_level_steps):
                            return top_level_steps[conditional_idx + 1].get("id")
                        return None
                
                # Check else branch
                else_branch = step.get("else")
                if else_branch:
                    if isinstance(else_branch, list):
                        result = _find_step_and_get_next(step_id, else_branch, top_level_steps, conditional_idx, condition_result)
                        if result is not None:
                            return result
                    elif isinstance(else_branch, dict) and "steps" in else_branch:
                        # Handle else branch with steps array
                        result = _find_step_and_get_next(step_id, else_branch["steps"], top_level_steps, conditional_idx, condition_result)
                        if result is not None:
                            return result
                    elif else_branch.get("id") == step_id:
                        # Single action in else - next is after conditional
                        if conditional_idx is not None and conditional_idx + 1 < len(top_level_steps):
                            return top_level_steps[conditional_idx + 1].get("id")
                        return None
            
            # Check nested steps (for steps arrays in branches)
            if "steps" in step:
                result = _find_step_and_get_next(step_id, step["steps"], top_level_steps, conditional_step_idx, condition_result)
                if result is not None:
                    return result
        
        return None
    
    # For conditional steps and fetch_with_condition steps, return first step in the selected branch
    for idx, step in enumerate(steps):
        if step.get("id") == current_step_id and (step.get("action") == "conditional" or step.get("action") == "fetch_with_condition"):
            if condition_result is True:
                then_branch = step.get("then")
                if then_branch:
                    # Handle then branch with steps array
                    if isinstance(then_branch, dict) and "steps" in then_branch:
                        steps_list = then_branch.get("steps", [])
                        if len(steps_list) > 0:
                            return steps_list[0].get("id")
                    # Handle then branch as list
                    elif isinstance(then_branch, list) and len(then_branch) > 0:
                        return then_branch[0].get("id")
                    # Handle then branch as single step
                    elif isinstance(then_branch, dict) and then_branch.get("id"):
                        return then_branch.get("id")
            else:
                else_branch = step.get("else")
                if else_branch:
                    # Handle else branch with steps array
                    if isinstance(else_branch, dict) and "steps" in else_branch:
                        steps_list = else_branch.get("steps", [])
                        if len(steps_list) > 0:
                            return steps_list[0].get("id")
                    # Handle else branch as list
                    elif isinstance(else_branch, list) and len(else_branch) > 0:
                        return else_branch[0].get("id")
                    # Handle else branch as single step
                    elif isinstance(else_branch, dict) and else_branch.get("id"):
                        return else_branch.get("id")
            # No branch selected, continue after conditional
            if idx + 1 < len(steps):
                return steps[idx + 1].get("id")
            return None
    
    # For other steps, find them in the structure
    return _find_step_and_get_next(current_step_id, steps, steps, None, condition_result)


def get_first_step_id(steps: List[Dict[str, Any]]) -> Optional[str]:
    if not steps:
        return None
    return steps[0].get("id")


def get_next_step(
    current_step_id: str,
    steps: List[Dict[str, Any]],
    step_registry: Dict[str, Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """Get the next step object (not just ID) after the current step."""
    next_step_id = get_next_step_id(current_step_id, steps)
    if next_step_id:
        return step_registry.get(next_step_id)
    return None

