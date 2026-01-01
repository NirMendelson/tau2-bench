import sys
import os
from pathlib import Path

# Add project root to path to import linter
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.append(project_root)

from linter.core import lint_workflow_file

class WorkflowValidator:
    def __init__(self, file_path: str):
        self.file_path = file_path

    def validate(self):
        """Run the existing linter and return errors."""
        errors = lint_workflow_file(self.file_path)
        return [str(e) for e in errors]

    def check_syntax(self, content: str):
        """Perform a basic syntax check on a YAML snippet."""
        from ruamel.yaml import YAML
        yaml = YAML()
        try:
            list(yaml.load_all(content))
            return True, None
        except Exception as e:
            return False, str(e)
