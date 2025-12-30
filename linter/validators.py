"""Validation rules for workflow.yaml files.

Each validator is a function that takes a tool_call dict and returns a list of ValidationError objects.
This makes it easy to add new validation rules later.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from linter.tool_signatures import get_required_parameters, tool_exists


@dataclass
class ValidationError:
    """Represents a validation error."""
    step_id: str
    tool_name: str
    message: str
    line_number: Optional[int] = None
    column_number: Optional[int] = None
    
    def __str__(self) -> str:
        location = f" (line {self.line_number})" if self.line_number else ""
        return f"[{self.step_id}] {self.message}{location}"


def validate_required_parameters(tool_call: Dict[str, Any]) -> List[ValidationError]:
    """
    Validate that all required parameters are provided for a tool call.
    
    This is Rule 1: Make sure we pass tools the required parameters.
    
    Args:
        tool_call: Dict with keys: 'step_id', 'tool_name', 'input', 'line_number'
        
    Returns:
        List of ValidationError objects (empty if no errors)
    """
    errors: List[ValidationError] = []
    
    step_id = tool_call.get('step_id', 'unknown')
    tool_name = tool_call.get('tool_name')
    input_list = tool_call.get('input', [])
    line_number = tool_call.get('line_number')
    
    if not tool_name:
        errors.append(ValidationError(
            step_id=step_id,
            tool_name='',
            message="Tool call missing 'tool_name' field",
            line_number=line_number
        ))
        return errors
    
    # Check if tool exists
    if not tool_exists(tool_name):
        errors.append(ValidationError(
            step_id=step_id,
            tool_name=tool_name,
            message=f"Unknown tool: '{tool_name}'",
            line_number=line_number
        ))
        return errors
    
    # Get required parameters
    required_params = get_required_parameters(tool_name)
    
    if required_params is None:
        # Tool exists but has no required parameters (all optional)
        return errors
    
    # Check if input list has enough parameters
    num_required = len(required_params)
    num_provided = len(input_list) if isinstance(input_list, list) else 0
    
    if num_provided < num_required:
        missing_params = required_params[num_provided:]
        errors.append(ValidationError(
            step_id=step_id,
            tool_name=tool_name,
            message=(
                f"Tool '{tool_name}' requires {num_required} parameters, "
                f"but only {num_provided} provided. "
                f"Missing: {', '.join(missing_params)}"
            ),
            line_number=line_number
        ))
    
    return errors


# Registry of all validators - easy to add more later
VALIDATORS = [
    validate_required_parameters,
]


def validate_tool_call(tool_call: Dict[str, Any]) -> List[ValidationError]:
    """
    Run all validators on a tool call.
    
    Args:
        tool_call: Dict with tool call information
        
    Returns:
        List of all ValidationError objects from all validators
    """
    all_errors: List[ValidationError] = []
    
    for validator in VALIDATORS:
        errors = validator(tool_call)
        all_errors.extend(errors)
    
    return all_errors

