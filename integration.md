# CSPL Integration Plan for τ²-Bench

This document outlines the step-by-step plan to integrate CSPL (Codebase Structured Prompt Language) workflow-agent into τ²-bench for the airline domain.

## Overview

**Goal:** Replace the standard LLM agent in τ²-bench with the CSPL workflow-agent, which uses structured workflows from YAML files instead of raw policy text.

**Key Changes:**
- Instead of passing `policy.md` directly to the agent, we convert it to structured YAML workflows
- The workflow-agent's 3 nodes (LoadCodebaseNode, MatchWorkflowNode, ExecuteWorkflowNode) will be wrapped in a τ²-bench compatible agent
- Tools from τ²-bench's airline domain will be used instead of `tools.yaml`
- Only airline domain will be supported initially

## Architecture Overview

```
tau2-bench run_task()
  ↓
Creates WorkflowAgent (new agent type)
  ↓
WorkflowAgent wraps workflow-agent flow
  ↓
Converts tau2 messages ↔ workflow-agent format
  ↓
Runs: LoadCodebaseNode → MatchWorkflowNode → ExecuteWorkflowNode
  ↓
Uses codebase/ YAML files (workflow.yaml, tone.yaml, constants.yaml)
  ↓
Maps tau2 tools to workflow tool calls
```

## File Structure

```
tau2-bench/
├── data/tau2/domains/airline/
│   ├── policy.md                    # Original policy (will be converted to codebase/)
│   └── codebase/                    # NEW: CSPL codebase folder
│       ├── workflow.yaml            # Converted from policy.md
│       ├── tone.yaml                # Communication style
│       └── constants.yaml           # Default values
├── src/tau2/domains/airline/
│   └── ... (existing files)
└── src/tau2/agent/
    └── workflow_agent.py            # NEW: WorkflowAgent wrapper
```

## Integration Phases

### Phase 1: Setup Codebase Structure and Files

**Goal:** Create the codebase folder structure and prepare YAML files for airline domain.

#### Tasks:
- [x] Create `data/tau2/domains/airline/codebase/` directory
- [x] Copy workflow-agent code structure to tau2-bench (or create symlink/reference)
  - [x] Copy `workflow-agent/nodes/` to `src/tau2/agent/workflow_agent/nodes/`
  - [x] Copy `workflow-agent/utils/` to `src/tau2/agent/workflow_agent/utils/`
  - [x] Copy `workflow-agent/flow.py` to `src/tau2/agent/workflow_agent/flow.py`
- [x] Create initial `workflow.yaml` file (can start with empty or placeholder)
- [x] Create `tone.yaml` file with airline customer service tone
- [x] Create `constants.yaml` file with airline-specific defaults
- [x] Update `.gitignore` if needed for codebase files

**Files to create:**
- `data/tau2/domains/airline/codebase/workflow.yaml`
- `data/tau2/domains/airline/codebase/tone.yaml`
- `data/tau2/domains/airline/codebase/constants.yaml`

**Notes:**
- We will NOT create `tools.yaml` - we'll use tau2-bench's tools directly
- The YAML files will be manually written/updated (conversion from policy.md is out of scope for this phase)

---

### Phase 2: Create WorkflowAgent Wrapper Class

**Goal:** Create a new agent class that implements τ²-bench's `BaseAgent` interface and wraps the workflow-agent flow.

#### Tasks:
- [x] Create `src/tau2/agent/workflow_agent.py`
- [x] Implement `WorkflowAgent` class extending `LocalAgent[dict]` (using dict as state to match workflow-agent's shared store)
- [x] Implement `get_init_state()` method:
  - [x] Convert τ²-bench `Message` history to workflow-agent `conversation_history` format (basic - handles UserMessage/AssistantMessage, ToolMessage handling deferred to Phase 3)
  - [x] Initialize state with only mutable conversation state:
    - `conversation_history`: converted from message history
    - `selected_workflow`: None
    - `current_step`: None
    - `extracted_fields`: {}
- [x] Implement `generate_next_message()` method (basic structure - message conversion in Phase 3):
  - [x] Basic message conversion (full conversion in Phase 3)
  - [x] Update conversation_history in state
  - [x] Create shared store for flow (add static config from agent instance)
  - [x] Run workflow-agent flow (LoadCodebaseNode → MatchWorkflowNode → ExecuteWorkflowNode)
  - [x] Update state from shared store (only mutable fields)
  - [x] Extract assistant response from conversation_history
  - [x] Convert response back to τ²-bench `AssistantMessage` format
  - [ ] Handle tool calls if workflow step calls a tool (Phase 4)
- [x] Implement `stop()` method (can be empty for now)
- [x] Implement `set_seed()` method (logs warning, not implemented)

**Key Implementation Details:**
```python
# State is a dictionary (only mutable conversation state)
state = {
    "conversation_history": list[dict],  # Converted from Message history
    "selected_workflow": Optional[dict],  # Selected workflow name and definition
    "current_step": Optional[dict],  # Current step in workflow execution
    "extracted_fields": dict,  # Fields extracted during workflow execution
}

# Static configuration stored in agent instance (not in state):
# - workflows: dict (loaded from workflow.yaml)
# - constants: dict (loaded from constants.yaml)
# - tone_config: dict (loaded from tone.yaml)
# - tools: list[Tool] (tau2 tools)
```

**Location:** `src/tau2/agent/workflow_agent.py`

---

### Phase 3: Message Format Conversion

**Goal:** Create utilities to convert between τ²-bench message format and workflow-agent format.

#### Tasks:
- [x] Create message conversion utilities in `src/tau2/agent/workflow_agent/convert_to_tau_utils/`
- [x] Implement `tau2_to_workflow_message()` function:
  - [x] Convert `UserMessage` → `{"role": "user", "content": "..."}`
  - [x] Convert `ToolMessage` → workflow-agent tool result format
  - [x] Convert `AssistantMessage` → `{"role": "assistant", "content": "..."}`
  - [x] Handle `MultiToolMessage` (multiple tool results)
- [x] Implement `workflow_to_tau2_message()` function:
  - [x] Convert workflow-agent response → `AssistantMessage`
  - [x] Handle text responses
  - [x] Handle tool calls (convert to τ²-bench `ToolCall` format)
- [x] Handle edge cases:
  - [x] Empty messages
  - [x] Messages with both text and tool calls
  - [x] Tool call errors

**Key Functions:**
```python
def tau2_to_workflow_message(message: Message) -> Optional[dict]
def workflow_to_tau2_message(workflow_response: dict, tools: Optional[list[Tool]] = None) -> AssistantMessage
def convert_message_history(messages: list[Message]) -> list[dict]
```

**Location:** `src/tau2/agent/workflow_agent/convert_to_tau_utils/`

---

### Phase 4: Tool Integration

**Goal:** Integrate τ²-bench's airline tools with workflow-agent's tool execution.

#### Tasks:
- [x] Create tool mapping utilities in `src/tau2/agent/workflow_agent/convert_to_tau_utils/tool_converter.py`
- [x] Implement `convert_tau2_tools_to_workflow_format()`:
  - [x] Convert τ²-bench `Tool` objects to workflow-agent tool format
  - [x] Map tool names and parameters
  - [x] Create tool descriptions for workflow matching
- [x] Implement `execute_workflow_tool_call()`:
  - [x] Take workflow tool call (from `use_tool` action)
  - [x] Find corresponding τ²-bench tool
  - [x] Execute tool with parameters
  - [x] Convert result back to workflow format
- [x] Update `ExecuteWorkflowNode` integration:
  - [x] When workflow step has `use_tool` action, call tool converter
  - [x] Pass tool results back to workflow executor
  - [x] Handle tool errors appropriately

**Key Functions:**
```python
def convert_tau2_tools_to_workflow_format(tools: list[Tool]) -> dict
def execute_workflow_tool_call(tool_name: str, arguments: dict, tools: list[Tool], extracted_fields: Optional[dict] = None) -> dict
def extract_tool_arguments_from_step(step: dict, extracted_fields: dict) -> dict
```

**Location:** `src/tau2/agent/workflow_agent/convert_to_tau_utils/tool_converter.py`

**Implementation Details:**
- `execute_tool()` in `action_executor.py` now accepts `tools` and `extracted_fields` parameters
- Tool arguments can be specified in workflow step `arguments` field or extracted from `extracted_fields`
- Template variables in tool arguments (e.g., `{{ field_name }}`) are resolved using `extracted_fields`
- Tool results are added to conversation history for workflow context
- Tool execution errors are logged and added to conversation history

**Important:** 
- We skip `tools.yaml` - tools come directly from `environment.get_tools()`
- Tool names in workflows must match τ²-bench tool names
- Tool parameters must match τ²-bench tool signatures
- Tool arguments can use template variables that reference `extracted_fields`

---

### Phase 5: Codebase File Loading

**Goal:** Load YAML files from airline domain's codebase folder and integrate with workflow-agent.

#### Tasks:
- [x] Create codebase loader (renamed `load_benchmark.py` to `load_codebase.py` and implemented loading logic in `LoadCodebaseNode`)
- [x] Implement codebase loading in `LoadCodebaseNode`:
  - [x] Load `workflow.yaml` from `data/tau2/domains/{domain}/codebase/workflow.yaml`
  - [x] Load `tone.yaml` from `data/tau2/domains/{domain}/codebase/tone.yaml`
  - [x] Load `constants.yaml` from `data/tau2/domains/{domain}/codebase/constants.yaml`
  - [x] Parse YAML files (using `workflow_parser.load_workflows()` and `load_file()`)
  - [x] Store structured dict with all codebase data in shared store
- [x] Update `WorkflowAgent.__init__()`:
  - [x] Pass domain to shared store for `LoadCodebaseNode` to use
  - [x] Initialize workflows, tone_config, constants as empty (loaded by node)
- [x] Update `WorkflowAgent.generate_next_message()`:
  - [x] Pass domain to shared store
  - [x] Cache loaded codebase data in agent instance after first load
- [x] Add error handling:
  - [x] Handle missing codebase folder
  - [x] Handle invalid YAML files
  - [x] Handle missing required files

**Key Implementation:**
- `LoadCodebaseNode` loads codebase files and stores them in shared store
- Uses existing `workflow_parser.load_workflows()` for workflow.yaml (handles multiple workflows separated by `---`)
- Uses `workflow_parser.load_constants()` for constants.yaml
- Uses `load_file()` for tone.yaml
- All files are loaded with proper error handling and logging

**Location:** `src/tau2/agent/workflow_agent/nodes/load_codebase.py`

---

### Phase 6: Registry Integration

**Goal:** Register WorkflowAgent in τ²-bench's registry so it can be used with `--agent workflow_agent`.

#### Tasks:
- [x] Import `WorkflowAgent` in `src/tau2/registry.py`
- [x] Register `WorkflowAgent` in the registry:
  - [x] Add `registry.register_agent(WorkflowAgent, "workflow_agent")`
- [x] Update `run_task()` in `src/tau2/run.py`:
  - [x] Add handling for `WorkflowAgent` type (similar to `LLMAgent`)
  - [x] Pass tools and domain_policy (even though policy won't be used directly)
  - [x] Pass domain name so agent can load codebase
- [x] Test agent registration:
  - [x] Verify `tau2 run --domain airline --agent workflow_agent` works (registration verified)
  - [x] Verify agent appears in registry options

**Code Changes:**
```python
# In src/tau2/registry.py
from tau2.agent.workflow_agent import WorkflowAgent
registry.register_agent(WorkflowAgent, "workflow_agent")

# In src/tau2/run.py
elif issubclass(AgentConstructor, WorkflowAgent):
    agent = AgentConstructor(
        tools=environment.get_tools(),
        domain_policy=environment.get_policy(),  # For compatibility
        domain=domain,  # NEW: to load codebase
        llm=llm_agent,
        llm_args=llm_args_agent,
    )
```

**Location:** 
- `src/tau2/registry.py`
- `src/tau2/run.py`

---

### Phase 7: Workflow Execution Integration

**Goal:** Ensure workflow-agent's flow runs correctly within τ²-bench's orchestrator.

#### Tasks:
- [x] Update `WorkflowAgent.generate_next_message()`:
  - [x] Handle case when workflow needs user input (fetch action)
  - [x] Return appropriate response (ask user or wait)
  - [x] Handle workflow completion
  - [x] Handle workflow not found case
- [ ] Integrate with orchestrator:
  - [ ] Ensure workflow-agent responses are compatible with orchestrator expectations
  - [ ] Handle tool calls from workflows correctly
  - [ ] Ensure conversation history stays in sync
- [ ] Handle multi-turn conversations:
  - [ ] Workflow can span multiple orchestrator steps
  - [ ] Maintain workflow state across turns
  - [ ] Resume workflow execution from correct step

**Key Considerations:**
- Workflow-agent expects to control the full conversation flow
- τ²-bench orchestrator manages turn-by-turn conversation
- Need to bridge these two models

**Implementation Details:**
- **Fetch action (waiting_for_input)**: When workflow needs user input, the question is already added to `conversation_history` by the workflow executor. `generate_next_message()` simply returns the last assistant message.
- **Workflow completion**: When workflow completes, the final reply is already added to `conversation_history`. `generate_next_message()` returns the last assistant message.
- **No workflow found**: When `selected_workflow` is None and there's no clarification question, `generate_next_message()` calls the `transfer_to_human_agents` tool and adds the result to `conversation_history`, then returns it.

**Location:** `src/tau2/agent/workflow_agent.py`

---

### Phase 8: Testing and Validation

**Goal:** Test the integration end-to-end and fix any issues.

#### Tasks:
- [ ] Create test script to run single task:
  - [ ] `tau2 run --domain airline --agent workflow_agent --num-tasks 1`
- [ ] Verify basic flow:
  - [ ] Agent loads codebase files
  - [ ] User message triggers workflow matching
  - [ ] Workflow executes correctly
  - [ ] Agent responds appropriately
- [ ] Test tool calls:
  - [ ] Verify workflow can call τ²-bench tools
  - [ ] Verify tool results are handled correctly
- [ ] Test multi-turn conversations:
  - [ ] Verify workflow state persists across turns
  - [ ] Verify fetch actions work (asking user for info)
- [ ] Test edge cases:
  - [ ] No matching workflow
  - [ ] Workflow clarification needed
  - [ ] Tool call errors
  - [ ] Workflow completion
- [ ] Compare results with standard LLMAgent:
  - [ ] Run same task with both agents
  - [ ] Compare conversation quality
  - [ ] Compare success rates

**Test Command:**
```bash
tau2 run --domain airline --agent workflow_agent --agent-llm gpt-4o-mini --num-tasks 5
```

---

## Key Integration Points

### 1. Agent Interface
- **τ²-bench expects:** `BaseAgent` with `generate_next_message(message, state) -> (AssistantMessage, state)`
- **Workflow-agent provides:** Flow with nodes that use shared store
- **Solution:** Wrap workflow-agent flow in `WorkflowAgent` class

### 2. Message Format
- **τ²-bench uses:** `Message` objects (UserMessage, AssistantMessage, ToolMessage)
- **Workflow-agent uses:** Dict format `{"role": "user", "content": "..."}`
- **Solution:** Convert between formats in `generate_next_message()`

### 3. Tools
- **τ²-bench provides:** `Tool` objects from `environment.get_tools()`
- **Workflow-agent expects:** Tools from `tools.yaml` or tool registry
- **Solution:** Map τ²-bench tools to workflow format, execute directly

### 4. Policy/Codebase
- **τ²-bench provides:** `policy.md` text file
- **Workflow-agent expects:** `workflow.yaml`, `tone.yaml`, `constants.yaml`
- **Solution:** Load codebase from domain folder, ignore policy.md for workflow-agent

### 5. Conversation Flow
- **τ²-bench orchestrator:** Manages turn-by-turn conversation
- **Workflow-agent flow:** Manages full workflow execution
- **Solution:** Run workflow flow within each `generate_next_message()` call, maintain state

---

## File Locations Summary

### New Files to Create:
```
src/tau2/agent/
├── workflow_agent.py              # Main WorkflowAgent class
└── workflow_agent/
    ├── __init__.py
    ├── nodes/                     # Copied from PocketFlow/workflow-agent
    │   ├── load_codebase.py
    │   ├── match_workflow.py
    │   └── execute_workflow.py
    ├── utils/                     # Copied from PocketFlow/workflow-agent
    │   ├── workflow_parser.py
    │   ├── workflow_matcher.py
    │   ├── workflow_executor.py
    │   └── ...
    ├── flow.py                    # Copied from PocketFlow/workflow-agent
    ├── codebase_loader.py         # NEW: Load YAML files
    └── convert_to_tau_utils/     # NEW: Conversion utilities
        ├── __init__.py
        ├── message_converter.py   # Message format conversion
        └── tool_converter.py      # Tool format conversion

data/tau2/domains/airline/
└── codebase/                      # NEW: CSPL codebase folder
    ├── workflow.yaml
    ├── tone.yaml
    └── constants.yaml
```

### Files to Modify:
```
src/tau2/registry.py               # Register WorkflowAgent
src/tau2/run.py                    # Handle WorkflowAgent creation
```

---

## Dependencies

### Required Python Packages:
- `pocketflow` (for workflow-agent nodes)
- `yaml` (for parsing codebase files)
- All existing τ²-bench dependencies

### Required Files from PocketFlow:
- `workflow-agent/nodes/*` - The 3 nodes
- `workflow-agent/utils/*` - Utility functions
- `workflow-agent/flow.py` - Flow definition

---

## Success Criteria

The integration is successful when:
1. ✅ `tau2 run --domain airline --agent workflow_agent` runs without errors
2. ✅ Agent loads codebase YAML files correctly
3. ✅ Agent matches user messages to workflows
4. ✅ Agent executes workflows and responds to users
5. ✅ Agent can call τ²-bench tools from workflows
6. ✅ Multi-turn conversations work correctly
7. ✅ Results are saved in same format as standard agents

---

## Next Steps After Integration

Once basic integration is complete:
1. Convert `policy.md` to `workflow.yaml` (manual or automated)
2. Test on full airline task set
3. Compare performance with standard LLMAgent
4. Optimize workflow matching and execution
5. Extend to other domains (retail, telecom)

---

## Notes

- **No tools.yaml:** We use τ²-bench's tools directly, so workflows must reference tool names that match τ²-bench tool names
- **Airline only:** Initial implementation focuses on airline domain only
- **Policy conversion:** Converting `policy.md` to `workflow.yaml` is a separate task (manual or future automation)
- **State management:** Workflow state must persist across orchestrator turns, stored in `WorkflowAgentState`

