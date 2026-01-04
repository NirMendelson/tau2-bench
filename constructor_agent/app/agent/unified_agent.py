import litellm
import json
from typing import List, Dict, Any

litellm.modify_params = True

from constructor_agent.app.agent.unified_prompt import get_unified_prompt, get_unified_tools
from constructor_agent.app.agent.executor_logic import ExecutorLogic
from constructor_agent.app.agent.knowledge_retrieval import read_knowledge

# Cursor-style unified agent: single conversational agent that explores and edits
class UnifiedAgent:
    def __init__(self, workflow_processor, constants_processor, tone_processor, validator, model: str = "claude-haiku-4-5-20251001"):
        self.workflow_processor = workflow_processor
        self.constants_processor = constants_processor
        self.tone_processor = tone_processor
        self.validator = validator
        self.model = model
        self.executor = ExecutorLogic(workflow_processor, constants_processor, tone_processor)
    
    def process_request(self, user_message: str, conversation_history: List[Dict[str, Any]] = []) -> Dict[str, Any]:
        # Load current state
        self.workflow_processor.load()
        self.constants_processor.load()
        self.tone_processor.load()
        
        # Build messages with system prompt + conversation history + new user message
        messages = self._build_messages(user_message, conversation_history)
        
        # Run the agent (with auto-retry for validation)
        return self._run_agent_with_validation(messages)
    
    def _build_messages(self, user_message: str, conversation_history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # Start with system prompt
        messages = [{"role": "system", "content": get_unified_prompt()}]
        
        # Add conversation history (excluding system prompts from previous turns)
        for msg in conversation_history:
            if msg.get("role") != "system":
                messages.append(msg)
        
        # Add new user message
        messages.append({"role": "user", "content": user_message})
        
        return messages
    
    def _run_agent_with_validation(self, messages: List[Dict[str, Any]], max_retries: int = 3) -> Dict[str, Any]:
        # Allow multiple tool-use turns for exploration + editing
        for turn in range(20):  # Max 20 turns for complex requests
            response = litellm.completion(
                model=self.model,
                messages=messages,
                tools=get_unified_tools()
            )
            
            msg = response.choices[0].message
            messages.append(msg)
            
            # If no tool calls, agent is done - return the conversational response
            if not msg.tool_calls:
                content = msg.content or ""
                
                # Check if there are pending edits to validate
                change_set = self.executor.get_change_set()
                if change_set:
                    # Validate the changes
                    is_valid, errors = self.validator.validate_change_set(change_set)
                    
                    if not is_valid:
                        # Auto-retry: send validation errors back to agent
                        error_msg = f"I made some changes, but there are validation errors. Please fix them:\n" + "\n".join(errors)
                        messages.append({"role": "user", "content": error_msg})
                        continue  # Loop again to let agent fix
                    
                    # Valid changes - return with explanation
                    return {
                        "message": content,
                        "edits": change_set,
                        "has_changes": True
                    }
                
                # No changes made - just conversational response
                return {
                    "message": content,
                    "has_changes": False
                }
            
            # Execute tool calls
            for tc in msg.tool_calls:
                tool_name = tc.function.name
                tool_args = json.loads(tc.function.arguments)
                
                result = self._execute_tool(tool_name, tool_args)
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result
                })
        
        # If we hit max turns, return what we have
        return {
            "message": "I've explored the request but need more information to complete it.",
            "has_changes": False
        }
    
    def _execute_tool(self, name: str, args: dict) -> str:
        # EXPLORATION TOOLS
        if name == "list_workflows":
            return json.dumps(self.workflow_processor.list_workflows())
        
        elif name == "search_workflow_content":
            return json.dumps(self.workflow_processor.search_content(
                args["query"], 
                args.get("workflow_name")
            ))
        
        elif name == "read_workflow":
            wf = self.workflow_processor.get_document_by_name(args["name"])
            return json.dumps(wf) if wf else "Error: Workflow not found."
        
        elif name == "read_workflow_step":
            step = self.workflow_processor.get_step_by_id(
                args["workflow_name"], 
                args["step_id"]
            )
            return json.dumps(step) if step else "Error: Step not found."
        
        elif name == "read_knowledge":
            return read_knowledge(args["topic"])
        
        elif name == "grep_search":
            # Determine domain from tone
            tone = self.tone_processor.data if hasattr(self.tone_processor, 'data') else self.tone_processor.load()
            role_desc = tone.get("identity", {}).get("role", "").lower()
            domain = "airline" if "airline" in role_desc else "retail" if "retail" in role_desc else "airline"
            return json.dumps(self.workflow_processor.grep_codebase(args["query"], domain=domain))
        
        elif name == "read_file":
            import os
            root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            abs_path = os.path.join(root_dir, args["path"])
            if os.path.exists(abs_path) and os.path.isfile(abs_path):
                with open(abs_path, 'r') as f:
                    return f.read()
            return "Error: File not found."
        
        # EDITING TOOLS
        elif name == "apply_edit":
            return self.executor.execute_tool(name, args)
        
        else:
            return f"Error: Unknown tool '{name}'"
