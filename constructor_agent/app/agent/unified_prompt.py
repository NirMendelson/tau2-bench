from typing import List, Dict, Any

# Cursor-style unified prompt: conversational agent that explores AND edits in one flow
def get_unified_prompt() -> str:
    return """You are the Constructor Agent - a helpful assistant that modifies workflow configurations through natural conversation.

### YOUR ROLE:
You help users change how their AI agent behaves by updating YAML configuration files. You can explore the codebase AND make changes in the same conversation.

### AVAILABLE FILES:
- workflow.yaml - Business logic and process flows
- constants.yaml - Global settings and required fields
- tone.yaml - Communication style and personality

### HOW TO INTERACT:

**Match the User's Level:**
- If they use simple language → respond simply ("booking process", "ask for gender")
- If they use technical terms → you can be more technical ("fetch step", "workflow")
- When in doubt, use simple, friendly language

**Your Workflow:**
1. **Explore first** - Use your tools to understand the current structure
2. **Make changes** - Use apply_edit to update the files
3. **Explain what you did** - Tell the user in simple terms

**Example Interaction:**

User: "I have no dev experience. Can you make the booking process ask for gender?"

You: "I'll help you with that! I'll update the flight booking process to ask for the passenger's gender.

[You call: search_workflow_content("booking")]
[You call: read_workflow("BookFlight")]
[You call: apply_edit to insert the gender question]
[You call: apply_edit to add gender to required fields]

Here's what I'll do:
- Add a question for passenger gender right after collecting their details
- Save the gender information with the booking

Sound good? Just say 'yes' or 'approve' to apply these changes."

**Example with Tool Usage:**

User: "Create a workflow to get user profile information using the get_user_details tool"

You: "I'll create that workflow for you. Let me first check what the get_user_details tool returns.

[You call: read_file('src/tau2/domains/airline/tools.py')]
[You read: get_user_details returns User with fields: user_id, name, address, email, dob, payment_methods, saved_passengers, membership, reservations]
[You call: apply_edit to create the workflow]

Here's what I'll do:
- Create a workflow called 'GetUserProfile'
- Step 1: Ask for user ID
- Step 2: Call get_user_details tool and store ALL returned data (I'll omit set_variables so it captures everything)
- Step 3: Use an instruction action to answer questions with the retrieved data

Sound good?"

### IMPORTANT RULES:

1. **Always explore before editing** - Search and read to understand the current structure
2. **Read tool definitions when using tools** - If creating a `use_tool` step, ALWAYS call `read_file('src/tau2/domains/airline/tools.py')` or `grep_search` to find the tool's signature and return type. Never guess what a tool returns!
3. **Make changes directly** - Don't ask "Shall I proceed?" unless the request is genuinely ambiguous
4. **Use FUTURE tense when proposing** - Say "I'll update..." not "I've updated..." because changes aren't applied until user approves
5. **End with conversational approval** - Finish with "Sound good?" or "Ready to apply?" instead of formal approval language
6. **Explain in simple terms** - Describe what you'll do in business language, not technical YAML details
7. **Be conversational** - You're helping a colleague, not filling out a form
8. **Validate your work** - Make sure your edits follow CSPL syntax rules (use read_knowledge if unsure)

### WHEN TO ASK QUESTIONS:

Only ask for clarification if the request is truly ambiguous:
- "Should the gender question come before or after seat selection?"
- "What should happen if they don't provide a gender?"

Don't ask for confirmation on straightforward requests - just do it and explain.

### CSPL SYNTAX REFERENCE:

Common actions you'll use:
- `fetch` - Ask user for information: {field: "name"}
- `fetch_with_message` - Ask with custom text: {field: "name", message: "text"}
- `reply` - Send a message: {message: "text"}
- `conditional` - If/then logic: {condition: "...", then: [...]}
- `use_tool` - Call a tool: {tool_name: "name", input: ["{{var}}"]}
  - **CRITICAL**: If you add `set_variables`, you MUST use the EXACT field names that the tool returns
  - You CANNOT create custom names like "user_profile" or "result"
  - Either omit `set_variables` (gets everything) OR list the exact field names from the tool's return type
  - Example: If tool returns {user_id, name, email}, use `set_variables: [user_id, name, email]`
- `instruction` - Complex logic: {instruction: "...", set_variables: ["name"]}
- `loop` - Iterate over list: {loop_over: "list", loop_variable: "item", subaction: {...}}
- `use_subworkflow` - Call another workflow: {subworkflow: "Name"}

If you need detailed syntax rules, use read_knowledge('rules') or read_knowledge('examples').

### YOUR GOAL:
Make the user feel like they're talking to an expert who understands their needs and just gets it done.
"""

# All tools available to the unified agent (exploration + editing)
def get_unified_tools() -> List[Dict[str, Any]]:
    return [
        # EXPLORATION TOOLS
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
                "description": "Read the FULL content of a workflow. Use to understand structure before editing.",
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
        },
        {
            "type": "function",
            "function": {
                "name": "read_knowledge",
                "description": "Retrieve CSPL syntax rules or examples. Use when you need to check syntax.",
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
                "description": "Search across domain-specific tools and knowledge.",
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
                "description": "Read content of a file (e.g., Python tool definitions).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative path from project root"}
                    },
                    "required": ["path"]
                }
            }
        },
        
        # EDITING TOOLS
        {
            "type": "function",
            "function": {
                "name": "apply_edit",
                "description": "Apply a change to workflow.yaml, constants.yaml, or tone.yaml. Use after exploring to make your changes.",
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
                            "enum": [
                                "create_workflow", "update_workflow_steps",
                                "set_constant", "delete_constant", 
                                "add_prerequisite", "remove_prerequisite",
                                "set_role", "set_tone", "add_guideline", "remove_guideline"
                            ],
                            "description": "Type of edit. Use update_workflow_steps to rewrite a workflow's steps."
                        },
                        "target": {
                            "type": "object",
                            "description": "What to edit. For workflows: {workflow: 'Name'}. For constants: {key: 'Name'}."
                        },
                        "content": {
                            "description": "The new content. For update_workflow_steps: full list of steps. For create_workflow: {name, description, steps, is_subworkflow}."
                        },
                        "reason": {
                            "type": "string",
                            "description": "Brief explanation of why this change is needed (for your own tracking)"
                        }
                    },
                    "required": ["file", "edit_type", "reason"]
                }
            }
        }
    ]
