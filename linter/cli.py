"""Command line interface for the linter."""

import sys
import argparse
from pathlib import Path

from linter.core import lint_workflow_file


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='CSPL Workflow Linter - Validates workflow.yaml files'
    )
    parser.add_argument(
        'workflow_file',
        type=str,
        help='Path to workflow.yaml file to lint'
    )
    parser.add_argument(
        '--format',
        choices=['text', 'json'],
        default='text',
        help='Output format (default: text)'
    )
    
    args = parser.parse_args()
    
    # Resolve path
    workflow_path = Path(args.workflow_file)
    if not workflow_path.is_absolute():
        workflow_path = Path.cwd() / workflow_path
    
    # Run linter
    errors = lint_workflow_file(str(workflow_path))
    
    # Output results
    if args.format == 'json':
        import json
        errors_dict = [
            {
                'step_id': e.step_id,
                'tool_name': e.tool_name,
                'message': e.message,
                'line_number': e.line_number,
                'column_number': e.column_number,
            }
            for e in errors
        ]
        print(json.dumps(errors_dict, indent=2))
    else:
        # Text format
        if errors:
            print(f"Found {len(errors)} error(s):\n")
            for error in errors:
                print(f"  {error}")
            sys.exit(1)
        else:
            print("No errors found!")
            sys.exit(0)


if __name__ == '__main__':
    main()

