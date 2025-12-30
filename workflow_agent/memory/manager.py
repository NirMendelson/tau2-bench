import re


class MemoryManager:
    def __init__(self):
        """
        Initializes memory for variables, conversation history, and current workflow state.
        """
        self.variables = {}
        self.conversation = []
        self.workflow_name = None
        self.step_id = None
        self.current_workflow = None
        self.stack = []  # Stack of execution frames: {"steps": [], "index": 0, "name": "..."}

    def get_variable(self, name):
        """Retrieves a variable value from memory."""
        return self.variables.get(name)

    def set_variable(self, name, value):
        """Stores a variable value in memory."""
        self.variables[name] = value

    def set_variables(self, variables_dict):
        """Stores multiple variables at once from a dictionary."""
        self.variables.update(variables_dict)

    def add_to_history(self, role, content):
        """Adds a message to the conversation history."""
        self.conversation.append({"role": role, "content": content})

    def get_history(self):
        """Returns the full conversation history."""
        return self.conversation

    def get_history_as_text(self):
        """Returns the conversation history as a formatted text string."""
        lines = []
        for msg in self.conversation:
            lines.append(f"{msg['role']}: {msg['content']}")
        return "\n".join(lines)

    def set_workflow_state(self, workflow_name=None, step_id=None, current_workflow=None):
        """Updates the current workflow and step tracking."""
        if workflow_name is not None:
            self.workflow_name = workflow_name
        if step_id is not None:
            self.step_id = step_id
        if current_workflow is not None:
            self.current_workflow = current_workflow

    def reset_workflow_state(self):
        """Resets the workflow state (useful when switching workflows)."""
        self.workflow_name = None
        self.step_id = None
        self.current_workflow = None

    def _get_value_by_path(self, path):
        """
        Helper to resolve nested paths like 'var.attr' or 'var[0]'.
        """
        # Split by dots and handle bracket indexing
        parts = re.split(r'\.|(?=\[)', path)
        if not parts:
            return None
            
        # Start with the root variable
        root_var = parts[0].strip()
        if root_var not in self.variables:
            return None
            
        val = self.variables[root_var]
        
        for part in parts[1:]:
            part = part.strip()
            if not part:
                continue
            
            if part.startswith('['):
                # Handle bracket indexing: [0] or ['key']
                match = re.match(r'\[\s*(.*)\s*\]', part)
                if not match:
                    return None
                key_str = match.group(1).strip()
                
                # Remove quotes if present
                if (key_str.startswith("'") and key_str.endswith("'")) or \
                   (key_str.startswith('"') and key_str.endswith('"')):
                    key = key_str[1:-1]
                else:
                    # Try to convert to int for list/tuple indexing
                    try:
                        key = int(key_str)
                    except ValueError:
                        key = key_str
                
                try:
                    val = val[key]
                except (KeyError, IndexError, TypeError):
                    return None
            else:
                # Handle dot notation (attribute or dict key)
                if isinstance(val, dict):
                    val = val.get(part)
                else:
                    try:
                        val = getattr(val, part)
                    except (AttributeError, TypeError):
                        # Fallback for Pydantic models/standard objects that might not have the attribute
                        return None
        return val

    def resolve_templates(self, text):
        """
        Replaces {{ variable_name }} placeholders in a string with values from memory.
        Supports nested paths like {{ flight.flight_number }} or {{ list[0] }}.
        If the text is exactly one placeholder like "{{ var_name }}", returns the raw variable value.
        Otherwise, returns a string with all templates replaced by their string representations.
        """
        if not isinstance(text, str):
            return text
            
        # Check if it's exactly one template like "{{ var_name }}"
        # This allows returning raw objects (like lists or dicts) instead of strings
        exact_match_pattern = r'^\{\{\s*([^}]+)\s*\}\}$'
        match = re.match(exact_match_pattern, text.strip())
        if match:
            path = match.group(1).strip()
            val = self._get_value_by_path(path)
            if val is not None:
                return val
            # Fallback to returning the placeholder if not found
        
        def replace_var(match):
            path = match.group(1).strip()
            val = self._get_value_by_path(path)
            if val is None:
                return f"{{{{ {path} }}}}"
            return str(val)
        
        # Match {{ variable_name }} patterns for general string substitution
        pattern = r'\{\{\s*([^}]+)\s*\}\}'
        return re.sub(pattern, replace_var, text)

    def get_state(self):
        """Returns the complete memory state as a dictionary."""
        return {
            "conversation": self.conversation,
            "variables": self.variables,
            "workflow_name": self.workflow_name,
            "step_id": self.step_id,
            "current_workflow": self.current_workflow
        }
