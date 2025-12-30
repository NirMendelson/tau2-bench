"""Core linter logic - parses workflow.yaml and finds tool calls."""

import yaml
from typing import List, Dict, Any, Optional
from pathlib import Path

from linter.validators import validate_tool_call, ValidationError


def find_all_tool_calls(workflow_data: Dict[str, Any], file_lines: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    Recursively find all 'use_tool' actions in workflow steps.
    
    Args:
        workflow_data: Parsed YAML workflow data
        file_lines: Optional list of file lines for line number tracking
        
    Returns:
        List of tool call dicts with: 'step_id', 'tool_name', 'input', 'line_number'
    """
    tool_calls: List[Dict[str, Any]] = []
    
    def get_line_number(key: str, parent_dict: Dict) -> Optional[int]:
        """Try to find line number for a key in the YAML."""
        if file_lines is None:
            return None
        
        # Simple heuristic: search for the key in file lines
        # This is approximate - for exact line numbers, use ruamel.yaml
        for i, line in enumerate(file_lines, 1):
            if key in line and (f": {key}" in line or f"- {key}" in line):
                return i
        return None
    
    def traverse_steps(steps: List[Dict], path: str = ""):
        """Recursively traverse workflow steps."""
        if not isinstance(steps, list):
            return
        
        for step in steps:
            if not isinstance(step, dict):
                continue
            
            step_id = step.get('id', 'unknown')
            action = step.get('action')
            
            if action == 'use_tool':
                tool_call = {
                    'step_id': step_id,
                    'tool_name': step.get('tool_name'),
                    'input': step.get('input', []),
                    'path': path,
                }
                
                # Try to find line number
                if file_lines:
                    # Search for step_id or tool_name in file
                    for i, line in enumerate(file_lines, 1):
                        if step_id in line or (step.get('tool_name') and step.get('tool_name') in line):
                            tool_call['line_number'] = i
                            break
                
                tool_calls.append(tool_call)
            
            # Recursively check nested steps in 'then', 'else', 'steps'
            for key in ['then', 'else', 'steps']:
                if key in step:
                    nested = step[key]
                    if isinstance(nested, list):
                        traverse_steps(nested, f"{path}.{step_id}.{key}")
                    elif isinstance(nested, dict):
                        # Handle case where 'then' directly contains a step (not wrapped in 'steps')
                        traverse_steps([nested], f"{path}.{step_id}.{key}")
    
    # Handle both 'workflow' and 'subworkflow' top-level keys
    if 'steps' in workflow_data:
        traverse_steps(workflow_data['steps'], 
                      workflow_data.get('workflow') or workflow_data.get('subworkflow', 'root'))
    
    return tool_calls


def lint_workflow_file(workflow_path: str) -> List[ValidationError]:
    """
    Main linter function that validates a workflow.yaml file.
    
    Args:
        workflow_path: Path to workflow.yaml file
        
    Returns:
        List of ValidationError objects
    """
    workflow_path = Path(workflow_path)
    
    if not workflow_path.exists():
        return [ValidationError(
            step_id='',
            tool_name='',
            message=f"File not found: {workflow_path}",
            line_number=None
        )]
    
    # Read file with line tracking
    with open(workflow_path, 'r') as f:
        file_lines = f.readlines()
    
    # Parse YAML
    try:
        with open(workflow_path, 'r') as f:
            workflows = list(yaml.safe_load_all(f))
    except yaml.YAMLError as e:
        return [ValidationError(
            step_id='',
            tool_name='',
            message=f"YAML parsing error: {e}",
            line_number=None
        )]
    
    all_errors: List[ValidationError] = []
    
    # Validate each workflow/subworkflow
    for workflow in workflows:
        if workflow is None:
            continue
        
        # Find all tool calls in this workflow
        tool_calls = find_all_tool_calls(workflow, file_lines)
        
        # Validate each tool call
        for tool_call in tool_calls:
            errors = validate_tool_call(tool_call)
            all_errors.extend(errors)
    
    return all_errors

