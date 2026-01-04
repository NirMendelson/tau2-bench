import litellm
import json
from typing import List, Dict, Any, Tuple
from constructor_agent.app.agent.planner_prompt import get_planner_prompt, get_planner_tools
from constructor_agent.app.agent.executor_logic import ExecutorLogic
from constructor_agent.app.agent.knowledge_retrieval import read_knowledge
from constructor_agent.app.agent.explanation_generator import ExplanationGenerator

# Manages the Planner-Executor-Validator loop (Trinity Loop) with auto-retry capability
class TrinityOrchestrator:
    def __init__(self, workflow_processor, constants_processor, tone_processor, validator, rules_path: str, model: str = "claude-haiku-4-5-20251001"):
        self.workflow_processor = workflow_processor
        self.constants_processor = constants_processor
        self.tone_processor = tone_processor
        self.validator = validator
        self.model = model
        self.explanation_generator = ExplanationGenerator()

    # Main entry point for the user request
    def process_request(self, user_message: str) -> Dict[str, Any]:
        self.workflow_processor.load()
        self.constants_processor.load()
        self.tone_processor.load()

        # Phase 1: Planner
        plan_result = self._run_planner(user_message)
        if "clarification" in plan_result:
            return plan_result
        
        plan = plan_result["plan"]
        
        # Phase 2 & 3: Executor & Validator (with auto-retry)
        return self._run_execution_loop(plan)

    # Discovery phase: Ask the LLM to understand intent and search the codebase
    def _run_planner(self, user_message: str) -> Dict[str, Any]:
        messages = [
            {"role": "system", "content": get_planner_prompt()},
            {"role": "user", "content": user_message}
        ]
        
        for _ in range(10):  # Allow up to 10 tool turns for exploration
            response = litellm.completion(model=self.model, messages=messages, tools=get_planner_tools())
            msg = response.choices[0].message
            messages.append(msg)
            
            if not msg.tool_calls:
                content = msg.content or ""
                # Simple detection for clarification questions vs finalized plans
                if "?" in content and any(word in content.lower() for word in ["should", "would", "which", "how", "please"]):
                    return {"clarification": content}
                return {"plan": content}
            
            for tc in msg.tool_calls:
                res = self._execute_planner_tool(tc.function.name, json.loads(tc.function.arguments))
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": res})
        
        return {"plan": messages[-1].content}

    # Execute exploration tools for the Planner
    def _execute_planner_tool(self, name: str, args: dict) -> str:
        if name == "list_workflows":
            return json.dumps(self.workflow_processor.list_workflows())
        elif name == "search_workflow_content":
            return json.dumps(self.workflow_processor.search_content(args["query"], args.get("workflow_name")))
        elif name == "read_knowledge":
            return read_knowledge(args["topic"])
        elif name == "read_workflow":
            wf = self.workflow_processor.get_document_by_name(args["name"])
            return json.dumps(wf) if wf else "Error: Not found."
        elif name == "read_workflow_step":
            step = self.workflow_processor.get_step_by_id(args["workflow_name"], args["step_id"])
            return json.dumps(step) if step else "Error: Not found."
        elif name == "grep_search":
            return json.dumps(self.workflow_processor.grep_codebase(args["query"], args.get("include")))
        elif name == "read_file":
            # Basic implementation for planning phase
            import os
            root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            abs_path = os.path.join(root_dir, args["path"])
            if os.path.exists(abs_path) and os.path.isfile(abs_path):
                with open(abs_path, 'r') as f: return f.read()
            return "Error: File not found."
        return f"Error: Tool '{name}' not found."

    # Engineering & Verification phase: Translate plan to edits and validate (retry if needed)
    def _run_execution_loop(self, plan: str, retries: int = 3) -> Dict[str, Any]:
        executor = ExecutorLogic(self.workflow_processor, self.constants_processor, self.tone_processor)
        messages = [
            {"role": "system", "content": executor.get_executor_prompt(plan)}
        ]
        
        for attempt in range(retries):
            # Run Executor
            response = litellm.completion(model=self.model, messages=messages, tools=executor.get_executor_tools())
            msg = response.choices[0].message
            messages.append(msg)
            
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    res = executor.execute_tool(tc.function.name, json.loads(tc.function.arguments))
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": res})
                
                # Check for final text explanation after tools
                response = litellm.completion(model=self.model, messages=messages)
                msg = response.choices[0].message
                messages.append(msg)

            # Phase 3: Validator
            change_set = executor.get_change_set()
            is_valid, errors = self.validator.validate_change_set(change_set)
            
            if is_valid:
                return {
                    "explanation": self.explanation_generator.generate_explanation(change_set),
                    "edits": change_set
                }
            
            messages.append({"role": "user", "content": f"Validation failed. Please fix these errors and try again:\n" + "\n".join(errors)})

        return {"error": "Failed to generate valid changes after multiple attempts.", "details": errors}
