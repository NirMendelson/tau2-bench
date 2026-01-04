from typing import List, Dict, Any

# Flexible executor that trusts the LLM to structure edits intelligently
class ExecutorLogic:
    def __init__(self, workflow_processor, constants_processor, tone_processor):
        self.workflow_processor = workflow_processor
        self.constants_processor = constants_processor
        self.tone_processor = tone_processor
        self.proposed_changes = []

    # System prompt for the Executor phase
    def get_executor_prompt(self, plan: str) -> str:
        return f"""You are the 'Executor' for the Constructor Agent. Translate this plan into precise YAML edits.

### THE PLAN:
{plan}

### TECHNICAL LEXICON (Workflow Actions):
You MUST only use these actions. Do NOT hallucinate names.

- `fetch`: {{"field": "name"}} (Fetch/Ask for info)
- `fetch_with_message`: {{"field": "name", "message": "exact text"}}
- `fetch_with_condition`: {{"field": "name", "condition": "{name} = value"}}
- `reply`: {{"message": "text template"}}
- `set_variable`: {{"variable": "name", "value": "val"}}
- `conditional`: {{"condition": "natural language", "then": [steps]}}
- `use_tool`: {{"tool_name": "name", "input": ["{{var}}"]}}
- `instruction`: {{"instruction": "logic", "set_variables": ["name"]}}
- `loop`: {{"loop_over": "list", "loop_variable": "item", "subaction": {...}}}
- `use_subworkflow`: {{"subworkflow": "Name"}}

### YOUR TASK:
Utilize `apply_edit` with `update_workflow_steps` to rewrite a workflow's logic. This is the preferred way to modify existing processes—just provide the complete, updated list of steps for that workflow. 

### RULES:
1. **Whole-Workflow Edits**: Use `update_workflow_steps` to rewrite the entire step list for a workflow. It is more reliable than granular patching.
2. **Create New Processes**: Use `create_workflow` to add entirely new workflows/subworkflows.
3. **Logic as Logic**: Use the `instruction` action for complex summaries, data processing, or multi-step calculations.
4. **Coordinate**: If a change affects constants or tone, update those files in the same turn.
5. **Strict Syntax**: Follow the TECHNICAL LEXICON exactly. No `ask` or `choice`.
"""

    # Single flexible tool - LLM decides the edit structure
    def get_executor_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "apply_edit",
                    "description": "Apply a change to workflow.yaml, constants.yaml, or tone.yaml.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file": {
                                "type": "string",
                                "enum": ["workflow.yaml", "constants.yaml", "tone.yaml"],
                                "description": "Which file to edit"
                            },
                            "edit_type": {
                                "type": "string",
                                "enum": ["create_workflow", "update_workflow_steps", "set_constant", "delete_constant", "add_prerequisite", "remove_prerequisite", "set_role", "set_tone", "add_guideline", "remove_guideline"],
                                "description": "What kind of edit to make. Use update_workflow_steps to rewrite a workflow's steps."
                            },
                            "target": {
                                "type": "object",
                                "description": "Identifies what to edit. For workflows: {workflow: 'Name'}. For constants: {key: 'Name'}."
                            },
                            "content": {
                                "description": "The new content. For update_workflow_steps, this MUST be the FULL list of steps for that workflow. For create_workflow, {name: 'Name', description: 'When to use', steps: [...], is_subworkflow: bool}"
                            },
                            "reason": {
                                "type": "string",
                                "description": "Human-readable explanation of why this change is needed"
                            }
                        },
                        "required": ["file", "edit_type", "reason"]
                    }
                }
            }
        ]

    # Process the flexible edit tool
    def execute_tool(self, name: str, args: dict) -> str:
        if name != "apply_edit":
            return f"Error: Unknown tool '{name}'"

        file = args["file"]
        edit_type = args["edit_type"]
        target = args.get("target", {})
        content = args.get("content")
        reason = args["reason"]

        try:
            if file == "workflow.yaml":
                return self._handle_workflow_edit(edit_type, target, content, reason)
            elif file == "constants.yaml":
                return self._handle_constants_edit(edit_type, target, content, reason)
            elif file == "tone.yaml":
                return self._handle_tone_edit(edit_type, content, reason)
        except Exception as e:
            return f"Error: {str(e)}"

        return "Error: Invalid file specified"

    # Handle workflow edits with flexible structure
    def _handle_workflow_edit(self, edit_type: str, target: dict, content: Any, reason: str) -> str:
        workflow = target.get("workflow")

        if edit_type == "create_workflow":
            if not isinstance(content, dict):
                return "Error: create_workflow content must be a dict with name, description, and steps"
            
            name = content.get("name")
            desc = content.get("description")
            steps = content.get("steps")
            is_sub = content.get("is_subworkflow", False)
            
            if not name or not desc or not steps:
                return "Error: create_workflow requires name, description, and steps"
                
            if self.workflow_processor.create_workflow(name, desc, steps, is_sub):
                self.proposed_changes.append({
                    "file": "workflow.yaml",
                    "type": "create",
                    "workflow": name,
                    "reason": reason
                })
                return f"Success: Created new workflow '{name}'"
            return f"Error: Workflow '{name}' already exists"

        elif edit_type == "update_workflow_steps":
            if not workflow or not isinstance(content, list):
                return "Error: update_workflow_steps requires workflow name in target and a list of steps in content"
            
            if self.workflow_processor.update_workflow_steps(workflow, content):
                self.proposed_changes.append({
                    "file": "workflow.yaml",
                    "type": "update",
                    "workflow": workflow,
                    "reason": reason
                })
                return f"Success: Updated all steps for workflow '{workflow}'"
            return f"Error: Workflow '{workflow}' not found"

        return f"Error: Unknown workflow edit_type '{edit_type}'"

    # Handle constants edits
    def _handle_constants_edit(self, edit_type: str, target: dict, content: Any, reason: str) -> str:
        key = target.get("key")

        if edit_type == "set_constant":
            if not key:
                return "Error: set_constant requires key in target"
            if self.constants_processor.set(key, content):
                self.proposed_changes.append({
                    "file": "constants.yaml",
                    "type": "set",
                    "key": key,
                    "value": content,
                    "reason": reason
                })
                return f"Success: Set constant '{key}'"

        elif edit_type == "delete_constant":
            if not key:
                return "Error: delete_constant requires key in target"
            if self.constants_processor.delete(key):
                self.proposed_changes.append({
                    "file": "constants.yaml",
                    "type": "delete",
                    "key": key,
                    "reason": reason
                })
                return f"Success: Deleted constant '{key}'"

        elif edit_type == "add_prerequisite":
            if not key:
                return "Error: add_prerequisite requires key in target"
            if self.constants_processor.add_prerequisite(key):
                self.proposed_changes.append({
                    "file": "constants.yaml",
                    "type": "add_prerequisite",
                    "key": key,
                    "reason": reason
                })
                return f"Success: Added '{key}' to prerequisites"

        elif edit_type == "remove_prerequisite":
            if not key:
                return "Error: remove_prerequisite requires key in target"
            if self.constants_processor.remove_prerequisite(key):
                self.proposed_changes.append({
                    "file": "constants.yaml",
                    "type": "remove_prerequisite",
                    "key": key,
                    "reason": reason
                })
                return f"Success: Removed '{key}' from prerequisites"

        return f"Error: Unknown constants edit_type '{edit_type}'"

    # Handle tone edits
    def _handle_tone_edit(self, edit_type: str, content: Any, reason: str) -> str:
        if edit_type == "set_role":
            self.tone_processor.set_role(content)
            self.proposed_changes.append({
                "file": "tone.yaml",
                "type": "set_role",
                "value": content,
                "reason": reason
            })
            return "Success: Updated agent role"

        elif edit_type == "set_tone":
            self.tone_processor.set_tone(content)
            self.proposed_changes.append({
                "file": "tone.yaml",
                "type": "set_tone",
                "value": content,
                "reason": reason
            })
            return "Success: Updated agent tone"

        elif edit_type == "add_guideline":
            self.tone_processor.add_guideline(content)
            self.proposed_changes.append({
                "file": "tone.yaml",
                "type": "add_guideline",
                "value": content,
                "reason": reason
            })
            return "Success: Added guideline"

        elif edit_type == "remove_guideline":
            self.tone_processor.remove_guideline(content)
            self.proposed_changes.append({
                "file": "tone.yaml",
                "type": "remove_guideline",
                "value": content,
                "reason": reason
            })
            return "Success: Removed guideline"

        return f"Error: Unknown tone edit_type '{edit_type}'"

    # Return the accumulation of changes made during Phase 2
    def get_change_set(self) -> List[Dict[str, Any]]:
        return self.proposed_changes
