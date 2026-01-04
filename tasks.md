# Implementation Tasks - Workflow Agent Refactor

# Refactoring Plan - Workflow Agent

The goal of this refactor is to improve the readability, organization, and maintainability of the `workflow_agent` codebase by following the core principles of clear function goals, modularity, and strict line limits.

## Core Principles
1. **Clear Goals**: Every function must have a clear, single responsibility.
2. **Modular Utils**: Helper functions will be moved to a `utils/` directory, categorized by subject.
3. **Line Limit**: Files will be kept under 400 lines of code.
4. **Clean Comments**: No docstrings (`"""..."""`). Single comment above functions.
5. **Purposeful Files**: Each file will have a clear, documented purpose.
6. **DRY (Don't Repeat Yourself)**: Shared functionality will be moved to helpers and imported.
7. **Think on other devs**: You need to think how to make it easier for other developers to understand and maintain the code.


The implementation is divided into 4 phases, focusing on modularizing the monolithic `step_executor.py` and cleaning up the core processing logic while moving helpers to a new `utils/` folder.

## Phase 1: Utils and Basic Handlers
Move the most common helper functions and basic action handlers out of `step_executor.py` into their new homes.

1.  **Create Utils Directory**: Initialize `workflow_agent/utils/` with `__init__.py`, `json_utils.py`, and `execution_utils.py`.
2.  **Migrate JSON & Execution Helpers**:
    *   Move `clean_json_response`, `is_null_value`, `custom_safe_load`, and `NoDatesSafeLoader` from `step_executor.py` to `utils/json_utils.py`.
    *   Move `StepExecutionResult` and `_create_result_with_blocking_check` to `utils/execution_utils.py`.
3.  **Refactor Reply Actions**: 
    *   Create `processor/handlers/reply_handlers.py`.
    *   Move `execute_reply` and `execute_reply_exact_message` there.
    *   Update `step_executor.py` to import and use these handlers.

## Phase 2: Fetch and Condition Handlers
Refactor the information gathering and logic branching actions.

1.  **Refactor Fetch Actions**:
    *   Create `processor/handlers/fetch_handlers.py`.
    *   Move `execute_fetch`, `execute_fetch_with_condition`, and `execute_fetch_with_message` there.
2.  **Refactor Condition Actions**:
    *   Create `processor/handlers/condition_handlers.py`.
    *   Move `execute_condition` and `execute_conditional_with_message` there.
3.  **Update Step Executor**: Remove the migrated functions and update the `execute_step` dispatcher with new imports.

## Phase 3: Tool, Flow, and Subworkflow Handlers
Handle the most complex logic (Tools and Instructions) and clean up workflow utilities.

1.  **Refactor Tool Actions**:
    *   Create `processor/handlers/tool_handlers.py`.
    *   Move `execute_use_tool` and its internal helper functions (`serialize_for_prompt`, `get_value_from_result`).
2.  **Refactor Flow Actions**:
    *   Create `processor/handlers/flow_handlers.py`.
    *   Move `execute_instruction`, `execute_loop`, and `execute_subworkflow_recursive`.
3.  **Workflow Utilities**:
    *   Create `utils/workflow_utils.py`.
    *   Move `_get_subworkflow_steps` and `_get_subworkflow_definition` from both `step_executor.py` AND `orchestrator.py` to this util file.
4.  **Finalize Step Executor**: The file should now only contain the `execute_step` dispatcher and be well under 400 lines.

## Phase 4: Core Orchestration and Global Cleanup
Refactor the main entry points and finalize formatting across the agent.

1.  **Refactor Orchestrator**:
    *   Clean up `orchestrator.py`: remove docstrings, use single-line comments.
    *   Update imports to use the new `utils/workflow_utils.py`.
    *   Ensure the file is under 400 lines.
2.  **Refactor Main Entry Point**:
    *   Clean up `main.py`: remove docstrings and use single-line comments.
    *   Ensure logic is concise.
3.  **Global Formatting Check**: 
    *   Ensure NO docstrings remain in any refactored file.
    *   Ensure every function has exactly ONE comment above it.
    *   Verify all files in `processor/` and `utils/` are under 400 lines.
