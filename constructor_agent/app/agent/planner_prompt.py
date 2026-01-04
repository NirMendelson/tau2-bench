from typing import List, Dict, Any

# Discovery phase prompt for understanding user intent with on-demand knowledge retrieval
def get_planner_prompt() -> str:
    return """You are the 'Planner' for the Constructor Agent. Your goal is to understand the user's intent and formulate a concrete strategy for modifying the AI agent's behavior.

You operate in the 'Discovery' phase of the Trinity Loop. You MUST NOT propose actual code changes yet.

### CORE PRINCIPLES:
1. **Search Before You Act**: NEVER assume you know where logic is.
2. **Read Precisely**: Read specific steps or files before planning.
3. **On-Demand Knowledge**: Do not guess syntax. Use the `read_knowledge` tool to retrieve rules or examples whenever needed.
4. **Lean Planning**: Formulate a natural language plan explaining what needs to be changed and why.

### YOUR WORKFLOW:
1. Search for relevant context using `search_workflow_content` or `grep_search`.
2. Read the specific code or steps you identified.
3. If unsure about how to implement a change in CSPL, call `read_knowledge(topic='rules')` or `read_knowledge(topic='examples')`.
4. Provide a clear natural language plan or ask for clarification.
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
                "description": "Search across the entire codebase (e.g., for tool definitions).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Text to search for"},
                        "include": {"type": "string", "description": "Optional glob pattern (e.g., '*.py')"}
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
