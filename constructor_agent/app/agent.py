import litellm
import os
import json
import yaml
import io
from ruamel.yaml import YAML
from typing import List, Dict, Any, Tuple, Optional
from constructor_agent.app.processor import WorkflowProcessor
from constructor_agent.app.validator import WorkflowValidator

# System Prompt for the Architect Agent
SYSTEM_PROMPT = """You are the 'Antigravity' Workflow Architect. Your job is to modify CSPL (Customer Service Process Language) workflows based on user requests.

### PRINCIPLES:
1. **Explore First**: You start with zero knowledge of the workflows. ALWAYS call `list_workflows` as your first step to see the architecture.
2. **Never Guess**: If a user mentions a workflow, verify its existence and content using tools. NEVER ask the user "Does this exist?" if you haven't checked yourself.
3. **Think Like a Senior Engineer**: Use a "Grep-then-Read-then-Edit" workflow. Use tools to find the relevant section, read the full logic, and only then propose an edit.
4. **Preservation**: You are an architect, not a rewriter. Keep 100% of existing logic unless the user explicitly tells you to delete it.
5. **Validation**: Use `validate_proposed_workflow` as a mandatory step before any final submission.

### CSPL RULES:
{cspl_rules}

### PROCESS:
1. `list_workflows` to orient yourself.
2. `read_workflow` for the specific targets.
3. Analyze and formulate a clean edit.
4. `validate_proposed_workflow` to catch syntax or rule errors.
5. `submit_final_proposal` with a clear explanation of *how* you modified the file while keeping it safe.
"""

class ConstructorAgent:
    def __init__(self, workflow_path: str, rules_path: str, model: str = "gpt-4o"):
        self.processor = WorkflowProcessor(workflow_path)
        self.validator = WorkflowValidator(workflow_path)
        self.rules_path = rules_path
        self.model = model
        
        with open(rules_path, 'r') as f:
            self.rules = f.read()

    def _get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "list_workflows",
                    "description": "List all workflow and subworkflow names available in the system.",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "read_workflow",
                    "description": "Read the full YAML content of a specific workflow or subworkflow.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "The name of the workflow/subworkflow."}
                        },
                        "required": ["name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "validate_proposed_workflow",
                    "description": "Validate a proposed YAML change for a workflow. Use this before proposing final edits.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Workflow name"},
                            "content": {"type": "object", "description": "The FULL dictionary object for the workflow (as JSON)."}
                        },
                        "required": ["name", "content"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "submit_final_proposal",
                    "description": "Submit your final explanation and the list of edits for the user to approve. This ends your task.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "explanation": {"type": "string", "description": "Natural language explanation of the changes."},
                            "edits": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "new_content": {"type": "object"}
                                    }
                                }
                            },
                            "clarification": {"type": "string", "description": "A question if you still need info, otherwise leave empty."}
                        },
                        "required": ["explanation", "edits"]
                    }
                }
            }
        ]

    def process_request(self, user_instruction: str) -> Dict[str, Any]:
        """Runs the agentic loop to handle the user instruction."""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT.format(cspl_rules=self.rules)},
            {"role": "user", "content": user_instruction}
        ]
        
        # Load the latest state from disk
        self.processor.load()
        
        # Guard for final result
        final_result = None
        
        # Limit the loop to prevent infinite recursion
        from loguru import logger
        
        for i in range(15):
            logger.info(f"Loop iteration {i}...")
            response = litellm.completion(
                model=self.model,
                messages=messages,
                tools=self._get_tools(),
                tool_choice="auto"
            )
            
            resp_message = response.choices[0].message
            # Ensure we track the message correctly for the conversation history
            # Convert tool_calls to dict for serialization safety if necessary
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
            
            for tool_call in resp_message.tool_calls:
                name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)
                logger.info(f"Calling tool: {name} with args: {args}")
                
                tool_result = ""
                
                if name == "list_workflows":
                    self.processor.load()
                    tool_result = json.dumps(self.processor.list_workflows())
                
                elif name == "read_workflow":
                    wf = self.processor.get_document_by_name(args.get("name", ""))
                    if wf:
                        s = io.StringIO()
                        y = YAML()
                        y.indent(mapping=2, sequence=4, offset=2)
                        y.dump(wf, s)
                        tool_result = s.getvalue()
                    else:
                        tool_result = f"Workflow '{args.get('name')}' not found."
                
                elif name == "validate_proposed_workflow":
                    workflow_name = args.get("name")
                    content = args.get("content")
                    if not workflow_name or not content:
                        tool_result = "Error: Both 'name' and 'content' are required for validation."
                    else:
                        logger.info(f"Validating workflow: {workflow_name}")
                        original = self.processor.get_document_by_name(workflow_name)
                        if not original:
                             tool_result = f"Error: Workflow '{workflow_name}' not found."
                        else:
                            try:
                                self.processor.update_document(workflow_name, content)
                                self.processor.save()
                                errors = self.validator.validate()
                                # Revert
                                self.processor.update_document(workflow_name, original)
                                self.processor.save()
                                tool_result = "Valid!" if not errors else f"Errors: {json.dumps(errors)}"
                            except Exception as e:
                                tool_result = f"Error during validation: {str(e)}"
                
                elif name == "submit_final_proposal":
                    logger.info("Agent submitted final proposal.")
                    final_result = args
                    tool_result = "Proposal received."
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": name,
                    "content": tool_result
                })
                logger.info(f"Tool {name} result: {tool_result[:100]}...")
            
            if final_result:
                return final_result

        return {"clarification": "Agent exceeded loop limit.", "explanation": None, "edits": None}

    def apply_edits(self, edits: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
        """Apply the proposed edits and validate."""
        self.processor.load()
        for edit in edits:
            self.processor.update_document(edit['name'], edit['new_content'])
        self.processor.save()
        errors = self.validator.validate()
        return (not errors, errors)
