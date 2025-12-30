# CSPL Workflow Linter

A simple, modular linter for validating `workflow.yaml` files in the airline domain.

## Current Validations

### Rule 1: Required Tool Parameters
Validates that all required parameters are provided when calling tools via `use_tool` actions.

## Usage

### Command Line

```bash
python -m linter.cli data/tau2/domains/airline/codebase/workflow.yaml
```

### Python API

```python
from linter import lint_workflow_file

errors = lint_workflow_file('data/tau2/domains/airline/codebase/workflow.yaml')
for error in errors:
    print(error)
```

## Adding New Validation Rules

To add a new validation rule:

1. Create a new validator function in `linter/validators.py`:

```python
def validate_my_new_rule(tool_call: Dict[str, Any]) -> List[ValidationError]:
    """Validate my new rule."""
    errors = []
    # Your validation logic here
    if some_condition:
        errors.append(ValidationError(
            step_id=tool_call['step_id'],
            tool_name=tool_call.get('tool_name', ''),
            message="Your error message",
            line_number=tool_call.get('line_number')
        ))
    return errors
```

2. Add it to the `VALIDATORS` list in `linter/validators.py`:

```python
VALIDATORS = [
    validate_required_parameters,
    validate_my_new_rule,  # Add here
]
```

That's it! The linter will automatically run your new validator on all tool calls.

## Structure

- `core.py` - Core parsing and tool call discovery logic
- `tool_signatures.py` - Extracts tool signatures from AirlineTools
- `validators.py` - Validation rules (easy to extend)
- `cli.py` - Command line interface

## Future Enhancements

- Better line number tracking (using ruamel.yaml)
- VSCode/Cursor extension for real-time validation
- More validation rules (variable usage, field validation, etc.)

