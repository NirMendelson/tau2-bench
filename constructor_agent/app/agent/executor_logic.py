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
You MUST only use these actions and fields. Do NOT hallucinate new action names (like 'ask' or 'choice').

- `fetch`: {{"field": "name"}} (Check/ask for info)
- `fetch_with_message`: {{"field": "name", "message": "exact text"}} (Ask with specific prompt)
- `fetch_with_condition`: {{"field": "name", "condition": "{{{{name}}}} = value"}} (Fetch then branch)
- `reply`: {{"message": "text template"}} (Send natural response)
- `set_variable`: {{"variable": "name", "value": "val"}} (Store data)
- `conditional`: {{"condition": "natural language", "then": [steps]}} (Branching)
- `use_tool`: {{"tool_name": "name", "input": ["{{{{var}}}}"]}} (Call backend)
- `instruction`: {{"instruction": "logic", "set_variables": ["name"]}} (Complex logic)
- `loop`: {{"loop_over": "list", "loop_variable": "item", "subaction": {{...}}}} (Iteration)
- `use_subworkflow`: {{"subworkflow": "Name"}} (Jump to subworkflow)

### YOUR TASK:
Use the `apply_edit` tool to make changes. You decide the structure - insert, modify, or delete steps as needed.

### RULES:
1. **Be Surgical**: Only change what's necessary
2. **Strict Syntax**: Follow the TECHNICAL LEXICON above exactly
3. **Coordinate**: If a change affects multiple files, make all related edits
4. **Explain**: Always provide a clear reason for each edit

The processors will handle the YAML formatting - you focus on the logic.
"""

    # Single flexible tool - LLM decides the edit structure
    def get_executor_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "apply_edit",
                    "description": "Apply a change to workflow.yaml, constants.yaml, or tone.yaml. You decide the structure based on what needs to change.",
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
                                "enum": ["insert_step", "modify_step", "delete_step", "set_constant", "delete_constant", "add_prerequisite", "remove_prerequisite", "set_role", "set_tone", "add_guideline", "remove_guideline"],
                                "description": "What kind of edit to make"
                            },
                            "target": {
                                "type": "object",
                                "description": "Identifies what to edit (e.g., {workflow: 'BookFlight', step_id: 'ask_date'} or {key: 'default_timeout'})"
                            },
                            "content": {
                                "description": "The new/updated content. Structure depends on edit_type. Can be a step object, a value, or a string."
                            },
                            "position": {
                                "type": "object",
                                "description": "For inserts: {type: 'before'|'after'|'at_index', reference: step_id or index}"
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
        position = args.get("position")
        reason = args["reason"]

        try:
            if file == "workflow.yaml":
                return self._handle_workflow_edit(edit_type, target, content, position, reason)
            elif file == "constants.yaml":
                return self._handle_constants_edit(edit_type, target, content, reason)
            elif file == "tone.yaml":
                return self._handle_tone_edit(edit_type, content, reason)
        except Exception as e:
            return f"Error: {str(e)}"

        return "Error: Invalid file specified"

    # Handle workflow edits with flexible structure
    def _handle_workflow_edit(self, edit_type: str, target: dict, content: Any, position: dict, reason: str) -> str:
        workflow = target.get("workflow")
        step_id = target.get("step_id")

        if edit_type == "insert_step":
            if not workflow or not content or not position:
                return "Error: insert_step requires workflow, content, and position"
            
            if self.workflow_processor.insert_step(workflow, position, content):
                self.proposed_changes.append({
                    "file": "workflow.yaml",
                    "type": "insert",
                    "workflow": workflow,
                    "after": content,
                    "reason": reason
                })
                return f"Success: Inserted new step into '{workflow}'"

        elif edit_type == "modify_step":
            if not workflow or not step_id or not content:
                return "Error: modify_step requires workflow, step_id, and content"
            
            old_step = self.workflow_processor.get_step_by_id(workflow, step_id)
            if not old_step:
                return f"Error: Step '{step_id}' not found in '{workflow}'"
            
            if self.workflow_processor.modify_step(workflow, step_id, content):
                self.proposed_changes.append({
                    "file": "workflow.yaml",
                    "type": "modify",
                    "workflow": workflow,
                    "step_id": step_id,
                    "before": old_step,
                    "after": content,
                    "reason": reason
                })
                return f"Success: Modified step '{step_id}' in '{workflow}'"

        elif edit_type == "delete_step":
            if not workflow or not step_id:
                return "Error: delete_step requires workflow and step_id"
            
            old_step = self.workflow_processor.get_step_by_id(workflow, step_id)
            if not old_step:
                return f"Error: Step '{step_id}' not found"
            
            if self.workflow_processor.delete_step(workflow, step_id):
                self.proposed_changes.append({
                    "file": "workflow.yaml",
                    "type": "delete",
                    "workflow": workflow,
                    "step_id": step_id,
                    "before": old_step,
                    "reason": reason
                })
                return f"Success: Deleted step '{step_id}' from '{workflow}'"

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
