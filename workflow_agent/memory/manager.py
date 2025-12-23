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

    def resolve_templates(self, text):
        """
        Replaces {{ variable_name }} placeholders in a string with values from memory.
        Returns the text with all templates replaced.
        """
        if not isinstance(text, str):
            return text
        
        def replace_var(match):
            var_name = match.group(1).strip()
            return str(self.variables.get(var_name, f"{{{{ {var_name} }}}}"))
        
        # Match {{ variable_name }} patterns
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
