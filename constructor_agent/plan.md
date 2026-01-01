# Constructor Agent - Implementation Plan

## Objective
Create an agentic system that can edit `workflow.yaml` based on natural language instructions, ensuring all changes adhere to CSPL rules and pass validation.

## Phase 1: Core Logic (Backend)
1.  **Workflow Parser & Editor**:
    -   Build a utility to read `workflow.yaml` while preserving structure.
    -   Implement searching for specific workflows or step IDs.
2.  **Edit Agent**:
    -   Develop a prompt for the LLM that includes `cspl-rules.md`.
    -   The agent will:
        -   Identify relevant parts of the YAML.
        -   Formulate an edit plan.
        -   Explain the plan in natural language.
        -   Generate the new YAML snippet.
3.  **Validation Integration**:
    -   Integrate with the existing `linter` module.
    -   Implement "Self-Correction" loop: if validation fails, the agent re-edits the snippet based on the error message.

## Phase 2: Web Application
1.  **Backend (FastAPI)**:
    -   `/chat`: Stream user instructions and agent responses.
    -   `/approve`: Confirm and apply proposed changes.
    -   `/state`: Get current workflow status and pending edits.
2.  **Frontend (React + Vite)**:
    -   **Premium Dark Mode UI**: Using a sleek, modern aesthetic.
    -   **Chat Interface**: Real-time conversation with the agent.
    -   **Proposed Change View**: A clear visualization of what will be changed (Natural Language description).
    -   **Validation Feedback**: Real-time linting status.

## Phase 3: Testing & Refinement
1.  **Task Scenarios**:
    -   Adding new steps.
    -   Modifying conditions.
    -   Adding subworkflows.
    -   Handling "Escalation" logic as requested in the example.
2.  **Robustness**: Improve LLM's understanding of nested conditionals and tool input requirements.

## Directory Structure
```
constructor-agent/
├── app/
│   ├── main.py          # FastAPI Server
│   ├── agent.py         # Agent Logic
│   ├── processor.py     # YAML Utilities
│   └── validator.py     # Linter Integration
├── web/                 # React Frontend
├── cspl-rules.md        # Reference Rules
└── plan.md              # This file
```
