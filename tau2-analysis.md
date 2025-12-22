# How τ²-Bench Works: A Simple Explanation

This document explains how τ²-bench (tau2-bench) works in simple terms, perfect for understanding the system before integrating it with new methods.

## Overview

τ²-bench is a framework for testing AI agents in customer service scenarios. Think of it like a video game where:
- **The Agent** is the player (a customer service AI)
- **The User** is an NPC (simulated customer) 
- **The Environment** is the game world (with tools like databases and APIs)
- **Tasks** are the missions/quests the agent needs to complete

## The Three Main Components

### 1. Instructions (Policy)

**What it is:** The rules and guidelines that tell the agent how to behave.

**Where it comes from:**
- Each domain (like `airline`, `retail`, `telecom`) has a **policy file** (usually `policy.md`)
- Located in: `data/tau2/domains/{domain_name}/policy.md`
- Example: `data/tau2/domains/airline/policy.md`

**How it's used:**
1. When you run a benchmark, the system loads the policy file for the chosen domain
2. The policy text is read from the file
3. This policy is then given to the agent as part of its system prompt
4. The agent uses these instructions to know what it can/cannot do

**Example flow:**
```
User runs: tau2 run --domain airline
  ↓
System calls: airline_domain_get_environment()
  ↓
Environment reads: data/tau2/domains/airline/policy.md
  ↓
Policy text is stored in: environment.policy
  ↓
Agent is created with: LLMAgent(tools=..., domain_policy=environment.policy)
  ↓
Agent's system prompt includes: <policy>{policy text}</policy>
```

### 2. Tasks (Questions/Scenarios)

**What it is:** The specific scenarios or problems the agent needs to solve. Each task represents one customer service interaction.

**Where it comes from:**
- Tasks are stored in **JSON files** in each domain's data directory
- Located in: `data/tau2/domains/{domain_name}/tasks.json`
- Example: `data/tau2/domains/airline/tasks.json`

**What a task contains:**
Each task in the JSON file has:
- `id`: Unique identifier (e.g., "task_001")
- `user_scenario`: Describes what the customer wants/needs
  - Contains `instructions` that tell the user simulator what to do
  - Example: "You want to book a flight from NYC to LAX"
- `evaluation_criteria`: Defines what the agent should do to succeed
  - Contains `actions` the agent should take
  - Contains assertions to check if the task was completed correctly
- `initial_state` (optional): Starting state of the conversation

**How it's used:**
1. When you run a benchmark, the system loads tasks from the JSON file
2. You can filter tasks by:
   - Task split (e.g., `--task-split-name base` for all tasks, or `train`/`test` for specific splits)
   - Task IDs (e.g., `--task-ids task_001 task_002`)
   - Number of tasks (e.g., `--num-tasks 5` for just 5 tasks)
3. For each task:
   - The `user_scenario` is given to the user simulator (tells the "customer" what to do)
   - The `evaluation_criteria` is used later to check if the agent succeeded
   - The `initial_state` (if present) sets up the starting conversation state

**Example flow:**
```
User runs: tau2 run --domain airline --num-tasks 3
  ↓
System calls: load_tasks(task_set_name="airline", task_split_name="base")
  ↓
System reads: data/tau2/domains/airline/tasks.json
  ↓
JSON is parsed into Task objects
  ↓
First 3 tasks are selected
  ↓
For each task:
  - User simulator gets: task.user_scenario
  - Agent conversation starts
  - After conversation ends, evaluator checks: task.evaluation_criteria
```

**Example task structure:**
```json
{
  "id": "airline_task_001",
  "user_scenario": {
    "instructions": "You want to book a flight from New York to Los Angeles for next week"
  },
  "evaluation_criteria": {
    "actions": [
      {
        "action_id": "search_1",
        "requestor": "assistant",
        "name": "search_flights",
        "arguments": {"origin": "NYC", "destination": "LAX"}
      }
    ]
  }
}
```

### 3. Tools

**What it is:** Functions the agent can call to interact with the environment (like searching a database, booking a flight, etc.).

**Where it comes from:**
- Each domain defines its tools in Python code
- Tools are classes that inherit from `ToolKitBase`
- Example: `AirlineTools` class in `src/tau2/domains/airline/tools.py`

**What tools do:**
- Tools are functions the agent can call during the conversation
- Examples:
  - `search_flights(origin, destination, date)` - searches for available flights
  - `get_user_details(user_id)` - retrieves customer information
  - `book_ticket(flight_id, passenger_name)` - books a flight

**How it's used:**
1. When the environment is created, it loads the domain's tools
2. Tools are converted into a format the LLM can understand (function definitions)
3. The agent receives these tools as part of its system prompt
4. During the conversation, the agent can call these tools
5. When the agent calls a tool:
   - The orchestrator sends the tool call to the environment
   - The environment executes the tool function
   - The result is sent back to the agent

**Example flow:**
```
Environment is created for "airline" domain
  ↓
System creates: AirlineTools(db)
  ↓
Tools are registered: environment.tools = AirlineTools
  ↓
Agent is created with: LLMAgent(tools=environment.get_tools(), ...)
  ↓
Agent's system prompt includes tool definitions
  ↓
Agent decides to call: search_flights(origin="NYC", destination="LAX")
  ↓
Orchestrator sends tool call to environment
  ↓
Environment executes: tools.search_flights("NYC", "LAX")
  ↓
Result is sent back to agent as a ToolMessage
```

## The Complete Flow

Here's how everything works together when you run a benchmark:

```
1. USER RUNS COMMAND
   tau2 run --domain airline --agent-llm gpt-4 --num-tasks 5
   
2. SYSTEM LOADS DOMAIN
   - Reads policy from: data/tau2/domains/airline/policy.md
   - Creates environment with tools from: AirlineTools class
   - Loads tasks from: data/tau2/domains/airline/tasks.json
   
3. FOR EACH TASK:
   a. Initialize:
      - Create agent with: tools + policy
      - Create user simulator with: task.user_scenario
      - Create orchestrator to manage conversation
   
   b. Run conversation:
      - User sends message (based on user_scenario)
      - Agent responds (can call tools or send text)
      - Environment executes tool calls
      - Repeat until task is complete or max steps reached
   
   c. Evaluate:
      - Check if agent completed task.evaluation_criteria
      - Calculate reward/score
   
4. SAVE RESULTS
   - Save all conversations to: data/tau2/simulations/{run_name}.json
   - Calculate metrics (success rate, etc.)
```

## Key Files and Locations

### Policy Files
- **Location:** `data/tau2/domains/{domain}/policy.md`
- **Example:** `data/tau2/domains/airline/policy.md`
- **Contains:** Text instructions for the agent

### Task Files
- **Location:** `data/tau2/domains/{domain}/tasks.json`
- **Example:** `data/tau2/domains/airline/tasks.json`
- **Contains:** Array of task objects with user scenarios and evaluation criteria

### Tool Definitions
- **Location:** `src/tau2/domains/{domain}/tools.py`
- **Example:** `src/tau2/domains/airline/tools.py`
- **Contains:** Python classes that define available tools

### Domain Environment
- **Location:** `src/tau2/domains/{domain}/environment.py`
- **Example:** `src/tau2/domains/airline/environment.py`
- **Contains:** `get_environment()` function that loads policy and tools

## Summary

- **Instructions (Policy)**: Text file (`policy.md`) with rules → loaded by environment → given to agent
- **Tasks (Questions)**: JSON file (`tasks.json`) with scenarios → loaded by system → given to user simulator
- **Tools**: Python classes with functions → loaded by environment → given to agent as callable functions

The agent receives the policy and tools at the start, then uses them throughout the conversation to help the user complete their task!

