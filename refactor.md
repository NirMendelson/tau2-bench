# Refactoring Plan - Workflow Agent

The goal of this refactor is to improve the readability, organization, and maintainability of the `workflow_agent` codebase by following the core principles of clear function goals, modularity, and strict line limits.

## Core Principles
1. **Clear Goals**: Every function must have a clear, single responsibility.
2. **Modular Utils**: Helper functions will be moved to a `utils/` directory, categorized by subject.
3. **Line Limit**: Files will be kept under 400 lines of code.
4. **Clean Comments**: No docstrings (`"""..."""`). Single comment above functions. no need for many comments inside the function
5. **Purposeful Files**: Each file will have a clear, documented purpose.
6. **DRY (Don't Repeat Yourself)**: Shared functionality will be moved to helpers and imported.
7. **Think on other devs**: You need to think how to make it easier for other developers to understand and maintain the code.


## Proposed Structure

```
workflow_agent/
├── main.py
├── processor/
│   ├── orchestrator.py
│   ├── step_executor.py
│   ├── action_config.py
│   └── handlers/
│       ├── __init__.py
│       ├── fetch_handlers.py      # fetch, fetch_with_condition, fetch_with_message
│       ├── condition_handlers.py  # condition, conditional_with_message
│       ├── tool_handlers.py       # use_tool, smart_tool logic
│       ├── reply_handlers.py      # reply, reply_exact_message
│       └── flow_handlers.py       # loop, instruction, subworkflow logic
├── utils/
│   ├── __init__.py
│   ├── json_utils.py              # cleaning, null checks, YAML loading
│   ├── memory_utils.py            # variable resolution templates, memory formatters
│   ├── workflow_utils.py          # subworkflow lookup and metadata helpers
│   └── execution_utils.py         # StepExecutionResult class, blocking checks
├── actions/
│   └── prompts.py                 # LLM prompts
├── tools/
│   └── tool_executor.py           # Tool execution logic
└── matching/
    └── matcher.py                 # Workflow matching logic
```

## Detailed File Refactoring Plan

### 1. `workflow_agent/utils/`
This directory will contain specialized utility files to keep the main logic files clean.

- **`json_utils.py`**:
    - `clean_json_response`: Moves from `step_executor.py`.
    - `is_null_value`: Moves from `step_executor.py`.
    - `custom_safe_load`: Moves from `step_executor.py`.
    - `NoDatesSafeLoader`: Moves from `step_executor.py`.

- **`memory_utils.py`**:
    - `resolve_templates`: Logic for resolving `{{ var }}` strings (currently inside `MemoryManager` or ad-hoc).
    - `get_variables_as_json`: Standardized memory serialization for prompts.

- **`workflow_utils.py`**:
    - `get_subworkflow_steps`: Moves from `step_executor.py`.
    - `get_subworkflow_definition`: Moves from `step_executor.py`.
    - Logic for checking subworkflow existence.

- **`execution_utils.py`**:
    - `StepExecutionResult`: The result class for step execution.
    - `create_result_with_blocking_check`: Standard helper for blocking logic.
    - `handle_fallback`: Standard fallback logic.

### 2. `workflow_agent/processor/handlers/`
This directory will hold the individual action executors to keep `step_executor.py` small.

- **`fetch_handlers.py`**: `execute_fetch`, `execute_fetch_with_condition`, `execute_fetch_with_message`.
- **`condition_handlers.py`**: `execute_condition`, `execute_conditional_with_message`.
- **`tool_handlers.py`**: `execute_use_tool` and internal smart tool resolution logic.
- **`reply_handlers.py`**: `execute_reply`, `execute_reply_exact_message`.
- **`flow_handlers.py`**: `execute_instruction`, `execute_loop`, `execute_subworkflow_recursive`.

### 3. `workflow_agent/processor/step_executor.py`
- **Purpose**: Entry point for step execution and dispatching to specific handlers.
- **Changes**:
    - Remove all helper functions (moved to utils).
    - Remove all specific `execute_X` functions (moved to handlers/).
    - Keep `execute_step` as the main dispatcher.
    - Keep automatic branching logic (for non-root contexts).

### 4. `workflow_agent/processor/orchestrator.py`
- **Purpose**: Manage the workflow stack and main loop.
- **Changes**:
    - Extract stack management logic into minor helper functions.
    - Clean up comments and remove docstrings.
    - Ensure it stays well under 400 lines (currently it is ~250 lines).

### 5. `workflow_agent/main.py`
- **Purpose**: Entry point for the agent, loading resources and managing state.
- **Changes**:
    - Convert docstrings to single comments.
    - Ensure it stays under 400 lines (currently ~170 lines).

## Execution Steps

1. **Setup Utils**: Create all files in `workflow_agent/utils` and move helper functions there.
2. **Setup Handlers**: Create `workflow_agent/processor/handlers/` and migrate `execute_` functions.
3. **Refactor `step_executor.py`**: Update imports and clean up the file to only contain the dispatcher.
4. **Refactor `orchestrator.py`**: Clean up comments and apply modularity.
5. **Refactor `main.py`**: Clean up comments.
6. **Final Cleanup**: Verify all imports are correct and internal comments are minimized.

---
*Note: This plan ensures that the massive `step_executor.py` (currently > 1300 lines) is broken down into logically separated files each under 400 lines.*
