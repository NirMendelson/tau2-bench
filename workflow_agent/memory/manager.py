import re
import json
from ..utils.json_utils import serialize_obj

# Manages variables, conversation history, and workflow execution state
class MemoryManager:
    def __init__(self):
        self.variables = {}
        self.conversation = []
        self.workflow_name = None
        self.step_id = None
        self.current_workflow = None
        self.stack = []
        self.context_key = None

    # Retrieves a variable from memory, checking context first
    def get_variable(self, name):
        if self.context_key and self.context_key in self.variables:
            ctx = self.variables[self.context_key]
            if isinstance(ctx, dict) and name in ctx: return ctx[name]
        return self.variables.get(name)

    # Stores a variable in memory, nesting it if context is set
    def set_variable(self, name, value):
        if self.context_key:
            if self.context_key not in self.variables or not isinstance(self.variables[self.context_key], dict):
                self.variables[self.context_key] = {"_val": self.variables.get(self.context_key)}
            self.variables[self.context_key][name] = value
        self.variables[name] = value

    # Stores multiple variables from a dictionary
    def set_variables(self, variables_dict):
        for name, value in variables_dict.items(): self.set_variable(name, value)

    # Adds a participant message to history
    def add_to_history(self, role, content):
        self.conversation.append({"role": role, "content": content})

    # Returns the conversation history list
    def get_history(self): return self.conversation

    # Returns the history as a formatted string for prompts
    def get_history_as_text(self):
        return "\n".join([f"{m['role']}: {m['content']}" for m in self.conversation])

    # Updates workflow tracking state
    def set_workflow_state(self, workflow_name=None, step_id=None, current_workflow=None):
        if workflow_name is not None: self.workflow_name = workflow_name
        if step_id is not None: self.step_id = step_id
        if current_workflow is not None: self.current_workflow = current_workflow

    # Resets workflow state for fresh execution
    def reset_workflow_state(self):
        self.workflow_name = None
        self.step_id = None
        self.current_workflow = None

    # Resolves nested paths like 'user.id' or 'list[0]' to values
    def _get_value_by_path(self, path):
        parts = re.split(r'\.|(?=\[)', path)
        if not parts: return None
        
        root = parts[0].strip()
        val = self.get_variable(root)
        
        for part in parts[1:]:
            part = part.strip()
            if not part: continue
            if part.startswith('['):
                match = re.match(r'\[\s*(.*)\s*\]', part)
                if not match: return None
                key = match.group(1).strip().strip("'\"")
                try: key = int(key)
                except ValueError: pass
                try: val = val[key]
                except: return None
            else:
                try: val = val.get(part) if isinstance(val, dict) else getattr(val, part)
                except: return None
        return val

    # Replaces {{ var }} placeholders in text with memory values
    def resolve_templates(self, text):
        if not isinstance(text, str): return text
        exact_match = re.match(r'^\{\{\s*([^}]+)\s*\}\}$', text.strip())
        if exact_match:
            res = self._get_value_by_path(exact_match.group(1).strip())
            return res if res is not None else text
        
        def repl(m):
            v = self._get_value_by_path(m.group(1).strip())
            return str(v) if v is not None else m.group(0)
        return re.sub(r'\{\{\s*([^}]+)\s*\}\}', repl, text)

    # Returns all memory variables as a formatted JSON string
    def get_variables_as_json(self):
        return json.dumps(serialize_obj(self.variables), indent=2, ensure_ascii=False)

    # Returns the full memory state as a dictionary
    def get_state(self):
        return {
            "conversation": self.conversation, "variables": self.variables,
            "workflow_name": self.workflow_name, "step_id": self.step_id,
            "current_workflow": self.current_workflow
        }
