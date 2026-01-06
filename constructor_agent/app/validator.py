from typing import List, Dict, Any, Tuple
import yaml
import tempfile
import os
from constructor_agent.app.processor.workflow_processor import WorkflowProcessor

SUPPORTED_ACTIONS = {
    "fetch": ["field"],
    "fetch_with_condition": ["field", "condition"],
    "fetch_with_message": ["field", "message"],
    "reply": ["message"],
    "reply_exact_message": ["message"],
    "set_variable": ["variable", "value"],
    "conditional": ["condition", "then"],
    "condition": ["condition", "then"],
    "conditional_with_message": ["condition"],
    "use_tool": ["tool_name", "input"],
    "instruction": ["instruction"],
    "loop": ["loop_over", "loop_variable"],
    "use_function": ["function"],
    "use_subworkflow": ["subworkflow"]  # Backward compatibility
}

# Enhanced validator to support the Trinity Loop's auto-retry and multi-file checks
class WorkflowValidator:
    def __init__(self, workflow_path: str):
        self.workflow_path = workflow_path

    # Main entry point for validating a full set of proposed changes
    def validate_change_set(self, change_set: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
        errors = []
        
        for edit in change_set:
            if edit["file"] == "workflow.yaml":
                wf_errors = self._validate_workflow_edit(edit)
                errors.extend(wf_errors)
            elif edit["file"] == "constants.yaml":
                errors.extend(self._validate_constants_edit(edit))
            elif edit["file"] == "tone.yaml":
                errors.extend(self._validate_tone_edit(edit))
        
        return len(errors) == 0, errors

    # Check for CSPL rule violations in workflow edits
    def _validate_workflow_edit(self, edit: Dict[str, Any]) -> List[str]:
        errors = []
        step = edit.get("after") or edit.get("content")
        if not step: return []
        
        if not isinstance(step, dict):
            return ["Step must be a dictionary"]
            
        if "id" not in step:
            errors.append("Step missing 'id' field")
        
        action = step.get("action")
        if not action:
            errors.append("Step missing 'action' field")
            return errors

        if action not in SUPPORTED_ACTIONS:
            errors.append(f"Invalid action '{action}'. Supported actions are: {', '.join(SUPPORTED_ACTIONS.keys())}")
            return errors

        # Check required fields for the specific action
        required_fields = SUPPORTED_ACTIONS[action]
        for field in required_fields:
            if field not in step:
                errors.append(f"Action '{action}' is missing required field: '{field}'")
        
        return errors

    # Check for validity in constants edits
    def _validate_constants_edit(self, edit: Dict[str, Any]) -> List[str]:
        # Simple key validation for now
        if not edit.get("key"):
            return ["Constants edit missing key"]
        return []

    # Check for validity in tone edits
    def _validate_tone_edit(self, edit: Dict[str, Any]) -> List[str]:
        # Tone instructions usually just need to be present
        return []

    # Legacy method for full file validation (used by apply_edits)
    def validate(self) -> List[str]:
        try:
            with open(self.workflow_path, 'r') as f:
                # Basic YAML syntax check
                yaml.safe_load_all(f)
            return []
        except Exception as e:
            return [f"YAML syntax error: {str(e)}"]
