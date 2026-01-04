from typing import List, Dict, Any, Optional
from constructor_agent.app.utils.yaml_manager import step_to_yaml

# Engineering phase logic for translating a plan into exact YAML modifications
class ExecutorLogic:
    def __init__(self, workflow_processor, constants_processor, tone_processor):
        self.workflow_processor = workflow_processor
        self.constants_processor = constants_processor
        self.tone_processor = tone_processor
        self.proposed_changes = []

    # System prompt for the Executor phase
    def get_executor_prompt(self, plan: str) -> str:
        return f"""You are the 'Executor' for the Constructor Agent. Your goal is to translate the following plan into exact, minimal YAML modifications across multiple files.

### THE PLAN TO EXECUTE:
{plan}

### CORE RULES:
1. **Surgical Edits Only**: Modify ONLY what needs to change. 
2. **Atomic Changes**: Track all related edits as a single Change Set.
3. **No Placeholders**: New steps must be complete and valid CSPL objects.

### COORDINATED EDITING:
- If a change affects multiple files (e.g., adding a prerequisite in constants.yaml and then using it in workflow.yaml), execute both edits.
"""

    # Tools for the Executor: Modify, Insert, Delete, and Update Constants/Tone
    def get_executor_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "propose_workflow_modification",
                    "description": "Replace or delete a specific step in workflow.yaml.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "workflow_name": {"type": "string"},
                            "step_id": {"type": "string"},
                            "action": {"type": "string", "enum": ["replace", "delete"]},
                            "new_step_content": {"type": "object", "description": "Required if replacing"},
                            "reason": {"type": "string"}
                        },
                        "required": ["workflow_name", "step_id", "action", "reason"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "propose_workflow_insertion",
                    "description": "Insert a new step into workflow.yaml.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "workflow_name": {"type": "string"},
                            "position": {
                                "type": "object",
                                "properties": {
                                    "type": {"type": "string", "enum": ["before", "after", "at_index"]},
                                    "reference": {"type": "string", "description": "step_id or index"}
                                }
                            },
                            "new_step": {"type": "object"},
                            "reason": {"type": "string"}
                        },
                        "required": ["workflow_name", "position", "new_step", "reason"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "update_constant",
                    "description": "Set or delete a global constant in constants.yaml.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "key": {"type": "string"},
                            "value": {"type": "any", "description": "If null, the key will be deleted"},
                            "is_prerequisite": {"type": "boolean", "description": "Whether to add/remove from default_prerequisites"}
                        },
                        "required": ["key"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "update_tone",
                    "description": "Update agent role, tone, or guidelines in tone.yaml.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "role": {"type": "string"},
                            "tone": {"type": "string"},
                            "add_guideline": {"type": "string"},
                            "remove_guideline": {"type": "string"}
                        }
                    }
                }
            }
        ]

    # Process specialized tool calls (in Phase 2, these modify in-memory state)
    def execute_tool(self, name: str, args: dict) -> str:
        if name == "propose_workflow_modification":
            wf = args["workflow_name"]
            sid = args["step_id"]
            action = args["action"]
            
            old_step = self.workflow_processor.get_step_by_id(wf, sid)
            if not old_step:
                return f"Error: Step '{sid}' not found in '{wf}'."
            
            if action == "delete":
                if self.workflow_processor.delete_step(wf, sid):
                    self.proposed_changes.append({"file": "workflow.yaml", "type": "delete", "workflow": wf, "step_id": sid, "before": old_step, "reason": args["reason"]})
                    return f"Success: Deleted step '{sid}' from '{wf}'."
            elif action == "replace":
                new_content = args["new_step_content"]
                if self.workflow_processor.modify_step(wf, sid, new_content):
                    self.proposed_changes.append({"file": "workflow.yaml", "type": "modify", "workflow": wf, "step_id": sid, "before": old_step, "after": new_content, "reason": args["reason"]})
                    return f"Success: Replaced step '{sid}' in '{wf}'."
                    
        elif name == "propose_workflow_insertion":
            wf = args["workflow_name"]
            new_step = args["new_step"]
            if self.workflow_processor.insert_step(wf, args["position"], new_step):
                self.proposed_changes.append({"file": "workflow.yaml", "type": "insert", "workflow": wf, "after": new_step, "reason": args["reason"]})
                return f"Success: Inserted new step into '{wf}'."

        elif name == "update_constant":
            key = args["key"]
            val = args.get("value")
            is_pre = args.get("is_prerequisite", False)
            
            if is_pre:
                if val is None:
                    if self.constants_processor.remove_prerequisite(key):
                        self.proposed_changes.append({"file": "constants.yaml", "type": "remove_prerequisite", "key": key})
                        return f"Success: Removed '{key}' from prerequisites."
                else:
                    if self.constants_processor.add_prerequisite(key):
                        self.proposed_changes.append({"file": "constants.yaml", "type": "add_prerequisite", "key": key})
                        return f"Success: Added '{key}' to prerequisites."
            else:
                if val is None:
                    if self.constants_processor.delete(key):
                        self.proposed_changes.append({"file": "constants.yaml", "type": "delete", "key": key})
                        return f"Success: Deleted constant '{key}'."
                elif self.constants_processor.set(key, val):
                    self.proposed_changes.append({"file": "constants.yaml", "type": "set", "key": key, "value": val})
                    return f"Success: Set constant '{key}' to '{val}'."

        elif name == "update_tone":
            if "role" in args:
                self.tone_processor.set_role(args["role"])
                self.proposed_changes.append({"file": "tone.yaml", "type": "set_role", "value": args["role"]})
            if "tone" in args:
                self.tone_processor.set_tone(args["tone"])
                self.proposed_changes.append({"file": "tone.yaml", "type": "set_tone", "value": args["tone"]})
            if "add_guideline" in args:
                self.tone_processor.add_guideline(args["add_guideline"])
                self.proposed_changes.append({"file": "tone.yaml", "type": "add_guideline", "value": args["add_guideline"]})
            if "remove_guideline" in args:
                self.tone_processor.remove_guideline(args["remove_guideline"])
                self.proposed_changes.append({"file": "tone.yaml", "type": "remove_guideline", "value": args["remove_guideline"]})
            return "Success: Tone configuration updated."

        return f"Error: Tool '{name}' implementation missing or failed."

    # Return the accumulation of changes made during Phase 2
    def get_change_set(self) -> List[Dict[str, Any]]:
        return self.proposed_changes
