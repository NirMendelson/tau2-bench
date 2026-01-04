from typing import List, Dict, Any

# Discovery phase prompt for understanding user intent with on-demand knowledge retrieval
def get_planner_prompt() -> str:
    return """You are the 'Planner' for the Constructor Agent. Your goal is to understand the user's intent and confirm your plan.

### CORE PRINCIPLES:
1. **Conversational Intelligence**: You are talking to a non-technical user. Do NOT use technical jargon like "YAML", "fetch step", "schema", or "prerequisites".
2. **Brevity is Key**: Your response should be a SINGLE, short, and friendly sentence confirming what you will do. 
3. **No Tech Plans**: Do not provide "Technical States", "Option 1/2", or detailed implementation breakdowns in your final response. 
4. **Domain Focus**: You are restricted to searching and reading tools within your assigned domain (e.g., airline). Ignore results from other domains (e.g., retail).
5. **Logic as Instructions**: If the user asks for complex logic, summaries, or calculations, always plan to use the `instruction` action.
6. **High-Level Thinking**: Think in whole workflows. If a new process is needed, plan to create a new workflow rather than patching existing ones.

### EXAMPLE RESPONSES:
- "No problem, I will update the flight booking process to ask for the passenger's gender right at the start. Shall I proceed?"
- "I understand. I'll add a check to make sure the user is a premium member before offering the discount. Is that okay?"

### YOUR WORKFLOW:
1. Use tools to find context.
2. Confirm the plan in a simple, conversational way.
"""

# Tools for the Planner, including the new on-demand knowledge retrieval
def get_planner_tools() -> List[Dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "list_workflows",
                "description": "List all workflow and subworkflow names.",
                "parameters": {"type": "object", "properties": {}}
            }
        },
        {
            "type": "function",
            "function": {
                "name": "search_workflow_content",
                "description": "Search for specific text across workflows. Returns step IDs and locations.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Text to search for"},
                        "workflow_name": {"type": "string", "description": "Optional: limit search"}
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "read_knowledge",
                "description": "Retrieve CSPL rules, examples, or specific action schemas on-demand.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string", "description": "One of: 'rules', 'examples', or an action name (e.g., 'fetch')"}
                    },
                    "required": ["topic"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "grep_search",
                "description": "Search across your specific domain's tools and knowledge.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Text to search for"}
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read content of a file on disk (e.g., Python tool definitions).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative path from project root"}
                    },
                    "required": ["path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "read_workflow",
                "description": "Read the FULL content of a workflow. Use sparingly.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Workflow name"}
                    },
                    "required": ["name"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "read_workflow_step",
                "description": "Read a specific step by its ID.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "workflow_name": {"type": "string"},
                        "step_id": {"type": "string"}
                    },
                    "required": ["workflow_name", "step_id"]
                }
            }
        }
    ]
