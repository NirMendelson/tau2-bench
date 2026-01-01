import litellm
import os
import json
import yaml
import io
import difflib
from ruamel.yaml import YAML
from typing import List, Dict, Any, Tuple, Optional
from constructor_agent.app.processor import WorkflowProcessor
from constructor_agent.app.validator import WorkflowValidator

# System Prompt for the Constructor Agent (Cursor-style)
SYSTEM_PROMPT = """You are the 'Constructor Agent' - a precise workflow architect that modifies CSPL (Customer Service Process Language) workflows.

You work EXACTLY like Cursor or Antigravity: you search first, read carefully, make surgical edits, and validate before proposing.

### CORE PRINCIPLES (CURSOR MINDSET):
1. **Search Before You Act**: NEVER assume you know the structure. Always use `search_workflow_content` or `list_workflows` first.
2. **Read Precisely**: Use `read_workflow_step` to examine specific steps, not entire workflows unless necessary.
3. **Surgical Edits Only**: Modify ONLY what needs to change. Use `propose_step_modification` for targeted changes.
4. **Validate Incrementally**: Use `validate_step` to check individual steps, then `validate_proposed_workflow` for the full workflow.
5. **Never Delete Accidentally**: Preserve 100% of existing logic unless explicitly asked to remove it.
6. **Show Clear Diffs**: When proposing changes, always explain what changed and why.

### YOUR WORKFLOW (FOLLOW THIS EXACTLY):
For ANY user request:
1. **Explore**: Use `search_workflow_content` to find relevant workflows/steps
2. **Read**: Use `read_workflow_step` to examine the specific area you'll modify
3. **Plan**: Think about the minimal change needed
4. **Validate Step**: Use `validate_step` to check your proposed step is valid CSPL
5. **Propose**: Use `propose_step_modification` or `propose_step_insertion` with clear explanation
6. **Final Validation**: Use `validate_proposed_workflow` to ensure the whole workflow is still valid
7. **Submit**: Use `submit_final_proposal` with a clear diff showing before/after

### YOU WILL BE WRITING IN CSPL, HERE ARE THE LANGUAGE RULES:
{cspl_rules}

### EXAMPLES OF GOOD WORKFLOW:

**Example 1: Adding a new step**
User: "Add age validation after fetching user_id in BookFlight"
Your process:
1. `search_workflow_content(query="fetch_user_id", workflow_name="BookFlight")`
2. `read_workflow_step(workflow_name="BookFlight", step_id="fetch_user_id")`
3. `validate_step(step_content={"id": "check_age", "action": "conditional", "condition": "user.age < 18", "then": [{"id": "deny_booking", "action": "reply", "message": "Sorry, you must be 18 or older."}]})`
4. `propose_step_insertion(workflow_name="BookFlight", position={"type": "after", "reference": "fetch_user_id"}, new_step={"id": "check_age", "action": "conditional", "condition": "user.age < 18", "then": [{"id": "deny_booking", "action": "reply", "message": "Sorry, you must be 18 or older."}]})`
5. `validate_proposed_workflow(workflow_name="BookFlight")`
6. `submit_final_proposal(explanation="Added age validation step...", edits=[...])`

**Example 2: Modifying a comment**
User: "Add a comment about valid values in the flight preference step"
Your process:
1. `search_workflow_content(query="flight_preference", workflow_name="BookFlight")`
   → Returns: step_id="fetch_flight_preference" (use THIS exact ID, not a parent step!)
2. `read_workflow_step(workflow_name="BookFlight", step_id="fetch_flight_preference")`
3. `propose_step_modification(workflow_name="BookFlight", step_id="fetch_flight_preference", modification_type="replace", new_step_content={{...with updated comment...}})`
4. `validate_proposed_workflow(workflow_name="BookFlight")`
5. `submit_final_proposal(...)`

**Example 3: Modifying a condition branch**
User: "Add a log step to the then branch of membership check"
Your process:
1. `search_workflow_content(query="membership")`
2. `read_workflow_step(workflow_name="BookFlight", step_id="check_membership")`
3. `propose_step_modification(workflow_name="BookFlight", step_id="check_membership", modification_type="replace", new_step_content={"id": "check_membership", "action": "conditional", "condition": "user.is_member", "then": [{"id": "log_gold", "action": "log", "message": "Gold member detected"}, {"id": "offer_discount", "action": "reply", "message": "Here's your member discount!"}], "else": [{"id": "offer_signup", "action": "reply", "message": "Join our membership program!"}]})`
4. `validate_proposed_workflow(workflow_name="BookFlight")`
5. `submit_final_proposal(...)`

### CRITICAL RULES:
- ❌ NEVER use 'steps:' key for branches or top-level workflows. Steps are direct lists.
- ❌ NEVER call `read_workflow` for the entire workflow unless you need to see the full structure
- ❌ NEVER propose changes without validating first
- ❌ NEVER delete steps unless explicitly asked
- ❌ **NEVER pass YAML content as strings** - this corrupts formatting!
- ❌ **NEVER call validate_proposed_workflow with 'content' parameter** - it only needs workflow_name!
- ❌ **NEVER modify a parent step when you mean to modify a nested step** - use the EXACT step_id from search results!
- ✅ ALWAYS search before reading
- ✅ ALWAYS read before modifying
- ✅ ALWAYS use the EXACT step_id returned by search_workflow_content
- ✅ ALWAYS use `propose_step_modification` or `propose_step_insertion` to make changes
- ✅ ALWAYS call `validate_proposed_workflow(workflow_name="X")` with ONLY the workflow name
- ✅ ALWAYS validate before proposing
- ✅ ALWAYS explain your changes clearly

### VALIDATION RULES:
- `validate_step` - Pass the step as a JSON object
- `validate_proposed_workflow` - Pass ONLY the workflow_name (string), NOT the content!
  - ✅ CORRECT: `validate_proposed_workflow(workflow_name="BookFlight")`
  - ❌ WRONG: `validate_proposed_workflow(name="BookFlight", content="...")`
- The system tracks changes in memory automatically - you don't need to pass content!

### IF VALIDATION FAILS:
1. Read the error message carefully
2. Use `read_workflow_step` to re-examine the problematic step
3. Fix the issue (check CSPL rules above)
4. Validate again
5. Only submit when validation passes

### REMEMBER:
You are a SURGICAL editor, not a rewriter. Make the smallest possible change that accomplishes the user's goal.
**CRITICAL: All modifications happen in memory. NEVER pass YAML content as strings - this breaks formatting!**
"""

class ConstructorAgent:
    def __init__(self, workflow_path: str, rules_path: str, model: str = "claude-haiku-4-5-20251001"):
        self.processor = WorkflowProcessor(workflow_path)
        self.validator = WorkflowValidator(workflow_path)
        self.rules_path = rules_path
        self.model = model
        
        with open(rules_path, 'r') as f:
            self.rules = f.read()

    def _get_tools(self) -> List[Dict[str, Any]]:
        """Define all tools available to the agent (Cursor-style granular tools)."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "list_workflows",
                    "description": "List all workflow and subworkflow names. Use this first to orient yourself.",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_workflow_content",
                    "description": "Search for specific text/patterns across workflows. Returns matching steps with their IDs and locations. Use this to find where specific logic exists.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Text to search for (case-insensitive)"},
                            "workflow_name": {"type": "string", "description": "Optional: limit search to specific workflow"}
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "read_workflow",
                    "description": "Read the FULL YAML content of a workflow. Use sparingly - prefer read_workflow_step for targeted reading.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Workflow/subworkflow name"}
                        },
                        "required": ["name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "read_workflow_step",
                    "description": "Read a SPECIFIC step by its ID. More efficient than reading the entire workflow.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "workflow_name": {"type": "string", "description": "Workflow/subworkflow name"},
                            "step_id": {"type": "string", "description": "The ID of the step to read"}
                        },
                        "required": ["workflow_name", "step_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "validate_step",
                    "description": "Validate a single step definition against CSPL rules. Use this before proposing changes.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "step_content": {"type": "object", "description": "The step object to validate"},
                            "context": {"type": "string", "description": "Optional: workflow name for context"}
                        },
                        "required": ["step_content"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "validate_proposed_workflow",
                    "description": "Validate the ENTIRE workflow after your proposed changes. IMPORTANT: Only pass workflow_name - changes are tracked in memory automatically. DO NOT pass 'content' parameter!",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "workflow_name": {"type": "string", "description": "Name of the workflow to validate (changes already in memory)"}
                        },
                        "required": ["workflow_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "propose_step_modification",
                    "description": "Propose a modification to an existing step. This is a SURGICAL edit - only the specified step changes.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "workflow_name": {"type": "string"},
                            "step_id": {"type": "string", "description": "ID of step to modify"},
                            "modification_type": {
                                "type": "string",
                                "enum": ["replace", "delete"],
                                "description": "replace: replace the step with new content, delete: remove the step"
                            },
                            "new_step_content": {"type": "object", "description": "New step definition (required for 'replace')"},
                            "reason": {"type": "string", "description": "Why you're making this change"}
                        },
                        "required": ["workflow_name", "step_id", "modification_type", "reason"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "propose_step_insertion",
                    "description": "Propose inserting a NEW step at a specific position.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "workflow_name": {"type": "string"},
                            "position": {
                                "type": "object",
                                "description": "Where to insert: {type: 'before'|'after'|'at_index', reference: step_id or index}",
                                "properties": {
                                    "type": {"type": "string", "enum": ["before", "after", "at_index"]},
                                    "reference": {"type": "string", "description": "step_id or numeric index"}
                                }
                            },
                            "new_step": {"type": "object", "description": "The step to insert"},
                            "reason": {"type": "string", "description": "Why you're adding this step"}
                        },
                        "required": ["workflow_name", "position", "new_step", "reason"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "submit_final_proposal",
                    "description": "Submit your final proposal with all changes. This ends your task. Include clear explanation and diffs.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "explanation": {"type": "string", "description": "Natural language summary of ALL changes made"},
                            "edits": {
                                "type": "array",
                                "description": "List of all proposed edits with diffs",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "workflow_name": {"type": "string"},
                                        "edit_type": {"type": "string", "enum": ["modify_step", "insert_step", "delete_step"]},
                                        "step_id": {"type": "string", "description": "ID of affected step"},
                                        "before": {"type": "string", "description": "YAML of step before change (if modify/delete)"},
                                        "after": {"type": "string", "description": "YAML of step after change (if modify/insert)"},
                                        "reason": {"type": "string"}
                                    }
                                }
                            },
                            "clarification": {"type": "string", "description": "Question if you need more info, otherwise leave empty"}
                        },
                        "required": ["explanation", "edits"]
                    }
                }
            }
        ]

    def _step_to_yaml(self, step: dict) -> str:
        """Convert a step dict to YAML string."""
        s = io.StringIO()
        y = YAML()
        y.indent(mapping=2, sequence=4, offset=2)
        y.dump(step, s)
        return s.getvalue()

    def _generate_diff(self, before: str, after: str) -> str:
        """Generate a human-readable diff."""
        before_lines = before.splitlines(keepends=True)
        after_lines = after.splitlines(keepends=True)
        diff = difflib.unified_diff(before_lines, after_lines, lineterm='', fromfile='before', tofile='after')
        return ''.join(diff)

    def process_request(self, user_instruction: str) -> Dict[str, Any]:
        """Runs the agentic loop to handle the user instruction."""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT.format(cspl_rules=self.rules)},
            {"role": "user", "content": user_instruction}
        ]
        
        # Load the latest state from disk
        self.processor.load()
        
        # Track proposed changes for final submission
        proposed_changes = []
        
        # Guard for final result
        final_result = None
        
        # Limit the loop to prevent infinite recursion
        from loguru import logger
        
        for i in range(30):  # Increased limit for complex workflows
            logger.info(f"🔄 Loop iteration {i}...")
            response = litellm.completion(
                model=self.model,
                messages=messages,
                tools=self._get_tools(),
                tool_choice="auto"
            )
            
            resp_message = response.choices[0].message
            
            # Add assistant message to history
            message_to_add = {
                "role": "assistant",
                "content": resp_message.content if resp_message.content else ""
            }
            if resp_message.tool_calls:
                 message_to_add["tool_calls"] = [
                     {
                         "id": tc.id,
                         "type": tc.type,
                         "function": {
                             "name": tc.function.name,
                             "arguments": tc.function.arguments
                         }
                     } for tc in resp_message.tool_calls
                 ]
            
            messages.append(message_to_add)
            
            if not resp_message.tool_calls:
                logger.info("Agent provided final text response.")
                return {
                    "clarification": resp_message.content,
                    "explanation": None,
                    "edits": None
                }
            
            # Process each tool call
            for tool_call in resp_message.tool_calls:
                name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)
                logger.info(f"🔧 Calling tool: {name}")
                logger.debug(f"   Args: {args}")
                
                tool_result = ""
                
                try:
                    if name == "list_workflows":
                        self.processor.load()
                        workflows = self.processor.list_workflows()
                        tool_result = json.dumps({"workflows": workflows, "count": len(workflows)})
                    
                    elif name == "search_workflow_content":
                        query = args.get("query", "")
                        workflow_name = args.get("workflow_name")
                        results = self.processor.search_content(query, workflow_name)
                        
                        # Format results nicely
                        formatted_results = []
                        for r in results:
                            formatted_results.append({
                                "workflow": r["workflow"],
                                "step_id": r["step_id"],
                                "path": r["path"],
                                "step_preview": self._step_to_yaml(r["step"])[:200] + "..." if len(self._step_to_yaml(r["step"])) > 200 else self._step_to_yaml(r["step"])
                            })
                        tool_result = json.dumps({"query": query, "matches": formatted_results, "count": len(formatted_results)})
                    
                    elif name == "read_workflow":
                        wf_name = args.get("name", "")
                        wf = self.processor.get_document_by_name(wf_name)
                        if wf:
                            s = io.StringIO()
                            y = YAML()
                            y.indent(mapping=2, sequence=4, offset=2)
                            y.dump(wf, s)
                            tool_result = s.getvalue()
                        else:
                            tool_result = f"❌ Workflow '{wf_name}' not found."
                    
                    elif name == "read_workflow_step":
                        wf_name = args.get("workflow_name", "")
                        step_id = args.get("step_id", "")
                        step = self.processor.get_step_by_id(wf_name, step_id)
                        if step:
                            tool_result = self._step_to_yaml(step)
                        else:
                            tool_result = f"❌ Step '{step_id}' not found in workflow '{wf_name}'."
                    
                    elif name == "validate_step":
                        step_content = args.get("step_content")
                        context = args.get("context", "")
                        
                        # Basic validation checks
                        errors = []
                        if not isinstance(step_content, dict):
                            errors.append("Step must be a dictionary/object")
                        else:
                            if 'id' not in step_content:
                                errors.append("Step must have an 'id' field")
                            if 'action' not in step_content:
                                errors.append("Step must have an 'action' field")
                            
                            # Validate action-specific requirements
                            action = step_content.get('action')
                            if action == 'fetch' and 'field' not in step_content and 'fields' not in step_content:
                                errors.append("fetch action requires 'field' or 'fields'")
                            elif action == 'fetch_with_message' and ('field' not in step_content or 'message' not in step_content):
                                errors.append("fetch_with_message requires 'field' and 'message'")
                            elif action == 'conditional' and ('condition' not in step_content or 'then' not in step_content):
                                errors.append("conditional requires 'condition' and 'then'")
                            elif action == 'use_tool' and ('tool_name' not in step_content or 'input' not in step_content):
                                errors.append("use_tool requires 'tool_name' and 'input'")
                            elif action == 'reply' and 'message' not in step_content:
                                errors.append("reply requires 'message'")
                            elif action == 'use_subworkflow' and 'subworkflow' not in step_content:
                                errors.append("use_subworkflow requires 'subworkflow'")
                            elif action == 'set_variable' and ('variable' not in step_content or 'value' not in step_content):
                                errors.append("set_variable requires 'variable' and 'value'")
                        
                        if errors:
                            tool_result = json.dumps({"valid": False, "errors": errors})
                        else:
                            tool_result = json.dumps({"valid": True, "message": "✅ Step is valid CSPL"})
                    
                    elif name == "validate_proposed_workflow":
                        wf_name = args.get("workflow_name")
                        logger.info(f"🔍 Validating workflow: {wf_name}")
                        
                        # CRITICAL: Do NOT save to the actual file!
                        # Instead, save to a temporary file for validation only
                        import tempfile
                        import shutil
                        
                        # Create a temporary copy of the workflow file
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp_file:
                            tmp_path = tmp_file.name
                            # Write current in-memory state to temp file
                            y = YAML()
                            y.preserve_quotes = True
                            y.indent(mapping=2, sequence=4, offset=2)
                            y.dump_all(self.processor.documents, tmp_file)
                        
                        try:
                            # Validate the temporary file
                            temp_validator = WorkflowValidator(tmp_path)
                            errors = temp_validator.validate()
                            
                            if errors:
                                tool_result = json.dumps({"valid": False, "errors": errors})
                            else:
                                tool_result = json.dumps({"valid": True, "message": f"✅ Workflow '{wf_name}' is valid"})
                        finally:
                            # Clean up temp file
                            import os
                            os.unlink(tmp_path)
                    
                    elif name == "propose_step_modification":
                        wf_name = args.get("workflow_name")
                        step_id = args.get("step_id")
                        mod_type = args.get("modification_type")
                        new_step = args.get("new_step_content")
                        reason = args.get("reason", "")
                        
                        # Get the old step for diff
                        old_step = self.processor.get_step_by_id(wf_name, step_id)
                        if not old_step:
                            tool_result = f"❌ Step '{step_id}' not found in '{wf_name}'"
                        else:
                            old_yaml = self._step_to_yaml(old_step)
                            
                            if mod_type == "replace":
                                success = self.processor.modify_step(wf_name, step_id, new_step)
                                if success:
                                    new_yaml = self._step_to_yaml(new_step)
                                    diff = self._generate_diff(old_yaml, new_yaml)
                                    
                                    proposed_changes.append({
                                        "workflow_name": wf_name,
                                        "edit_type": "modify_step",
                                        "step_id": step_id,
                                        "before": old_yaml,
                                        "after": new_yaml,
                                        "reason": reason
                                    })
                                    
                                    tool_result = f"✅ Step '{step_id}' modified in memory.\n\nDiff:\n{diff}\n\nReason: {reason}"
                                else:
                                    tool_result = f"❌ Failed to modify step '{step_id}'"
                            
                            elif mod_type == "delete":
                                success = self.processor.delete_step(wf_name, step_id)
                                if success:
                                    proposed_changes.append({
                                        "workflow_name": wf_name,
                                        "edit_type": "delete_step",
                                        "step_id": step_id,
                                        "before": old_yaml,
                                        "after": "",
                                        "reason": reason
                                    })
                                    tool_result = f"✅ Step '{step_id}' deleted from memory.\n\nDeleted:\n{old_yaml}\n\nReason: {reason}"
                                else:
                                    tool_result = f"❌ Failed to delete step '{step_id}'"
                    
                    elif name == "propose_step_insertion":
                        wf_name = args.get("workflow_name")
                        position = args.get("position")
                        new_step = args.get("new_step")
                        reason = args.get("reason", "")
                        
                        # Validate that new_step is provided
                        if not new_step:
                            tool_result = "❌ Error: 'new_step' parameter is required for step insertion"
                        else:
                            success = self.processor.insert_step(wf_name, position, new_step)
                            if success:
                                new_yaml = self._step_to_yaml(new_step)
                                
                                proposed_changes.append({
                                    "workflow_name": wf_name,
                                    "edit_type": "insert_step",
                                    "step_id": new_step.get("id", "unknown"),
                                    "before": "",
                                    "after": new_yaml,
                                    "reason": reason,
                                    "position": position
                                })
                                
                                tool_result = f"✅ Step inserted at {position} in memory.\n\nInserted:\n{new_yaml}\n\nReason: {reason}"
                            else:
                                tool_result = f"❌ Failed to insert step at {position}"
                    
                    elif name == "submit_final_proposal":
                        logger.info("📝 Agent submitted final proposal.")
                        final_result = args
                        tool_result = "✅ Proposal received. Task complete."
                
                except Exception as e:
                    logger.error(f"❌ Error in tool {name}: {str(e)}")
                    tool_result = f"❌ Error: {str(e)}"
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": name,
                    "content": tool_result
                })
                logger.debug(f"   Result: {tool_result[:200]}...")
            
            if final_result:
                return final_result

        return {"clarification": "Agent exceeded loop limit. Please simplify your request.", "explanation": None, "edits": None}

    def apply_edits(self, edits: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
        """Apply the proposed edits and validate.
        
        IMPORTANT: The in-memory state (self.processor.documents) already contains
        all the changes from the agent's proposal phase. We just need to save it.
        DO NOT reload from disk as that would wipe out all changes!
        """
        from loguru import logger
        logger.info(f"📝 Applying {len(edits)} edit(s) to disk...")
        
        # CRITICAL: Do NOT call self.processor.load() here!
        # The in-memory state already has all the changes from the proposal phase.
        # Loading from disk would wipe them out!
        
        # Simply save the current in-memory state to disk
        self.processor.save()
        logger.info(f"  ✅ Saved changes to {self.processor.file_path}")
        
        # Validate the saved file
        errors = self.validator.validate()
        
        if errors:
            logger.error(f"❌ Validation failed with {len(errors)} errors")
            # Optionally: reload from disk to revert changes
            # self.processor.load()
        else:
            logger.info("✅ All edits applied and validated successfully")
        
        return (not errors, errors)
