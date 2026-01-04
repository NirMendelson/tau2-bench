# Implementation Plan: Constructor Agent Rewrite

## Overview
This document outlines the architecture and implementation strategy for the Constructor Agent, transitioning from a basic prototype to a robust, conversational, and precise workflow architect. The design is inspired by **Cursor** and **Antigravity**, prioritizing surgical edits, safety, and iterative user feedback.

### Design Constraints
- **Single-user system**: Memory reset on page refresh is acceptable
- **Non-technical users**: Explanations in natural language, not technical diffs
- **Multi-file support**: Coordinated edits across `workflow.yaml`, `constants.yaml`, and `tone.yaml`
- **Auto-retry validation**: Validation failures trigger automatic fixes without user intervention
- **On-demand knowledge**: Agent retrieves syntax rules and examples only when needed

---

## 1. Architectural Blueprint: The Trinity Loop

To ensure accuracy and safety, the agent will operate in a three-phase "Trinity Loop" for every user interaction.

### Phase 1: The Planner (Discovery)
- **Goal**: Understand intent, map it to the codebase, and formulate a strategy.
- **Responsibilities**:
  - Search the codebase using `search_workflow_content` and `grep_search`.
  - Read relevant workflow steps and Python tool definitions.
  - **On-demand knowledge**: Use `read_knowledge(topic)` to retrieve:
    - `cspl-rules.md` - Core YAML syntax and action schemas
    - `examples.md` - Real user prompts and resulting changes
  - Formulate a clear plan in natural language.

### Phase 2: The Executor (Engineering)
- **Goal**: Translate the plan into exact, minimal YAML modifications across multiple files.
- **Responsibilities**:
  - Use granular tools (`propose_step_modification`, `propose_step_insertion`) to update the in-memory state.
  - Support coordinated edits across `workflow.yaml`, `constants.yaml`, and `tone.yaml`.
  - Track multiple related edits as a single logical "Change Set".
  - Maintain the existing formatting and comments (via `ruamel.yaml`).

### Phase 3: The Validator (Verification)
- **Goal**: Ensure the "Change Set" is logically sound and follows CSPL rules.
- **Responsibilities**:
  - Automatic background validation after every execution phase.
  - **Auto-retry loop**: If validation fails, the agent receives the error and loops back to **Phase 2** automatically without user intervention.
  - Once valid, generate a **natural language explanation** of the changes for user approval (no technical diffs).

---

## 2. State Management (Single-User)

The Constructor Agent maintains in-memory state for the current conversation.

- **In-Memory State**:
  - **Pending Change Set**: Unapplied edits across all three files (`workflow.yaml`, `constants.yaml`, `tone.yaml`)
  - **Conversation Context**: Current user message and agent's understanding
- **Iterative Refinement**:
  - Users can refine their request in follow-up messages
  - The agent updates the pending draft and re-runs the Trinity Loop
- **Approval Gate**: No file write happens until the `apply_edits` endpoint is triggered by an explicit "Approve" button in the UI
- **Memory Reset**: State resets on page refresh (acceptable for single-user system)

---

## 3. Agent Response Format (Non-Technical Users)

The agent communicates in **natural language only**, avoiding technical jargon or code diffs.

### Response Types:

#### **Clarification Request**
When the user's intent is unclear:
```json
{
  "clarification": "I understand you want to add a size check. Should this happen before or after the user selects the product?"
}
```

#### **Proposal (After Successful Planning & Validation)**
When ready to present changes:
```json
{
  "explanation": "I'll make the following changes:\n\n**Workflow: BookShoes**\n- Add a new step 'ask_shoe_size' that asks the user for their shoe size\n- This will happen right before the booking step\n- The size will be stored and used in the booking\n\n**Constants**\n- Add 'shoe_size' to the list of required fields\n\nWould you like me to apply these changes?",
  "edits": [
    {"file": "workflow.yaml", "workflow": "BookShoes", "action": "insert", ...},
    {"file": "constants.yaml", "action": "add_field", ...}
  ]
}
```

**Key Principles:**
- Explain **what** will change, **where**, and **why**
- Use workflow/step names, not line numbers or YAML paths
- Group related changes by file
- No code snippets or diffs (users don't need to see YAML)

---

## 4. Directory Structure & File Purpose

Following the **Modular Utils** and **Purposeful Files** principles:

```text
constructor_agent/
├── app/
│   ├── agent/
│   │   ├── orchestrator.py    # Manages the Planner-Executor-Validator loop with auto-retry
│   │   ├── planner_prompt.py  # System prompt & strategy for Phase 1
│   │   └── executor_logic.py  # Handles tool calls and draft state management
│   ├── processor/
│   │   ├── workflow_processor.py  # Read/write/edit workflow.yaml
│   │   ├── constants_processor.py # Read/write/edit constants.yaml
│   │   └── tone_processor.py      # Read/write/edit tone.yaml
│   ├── validator/
│   │   ├── schema.py          # CSPL schema definitions
│   │   └── logic_checks.py    # Semantic validation (e.g., missing variables)
│   ├── utils/
│   │   └── yaml_manager.py    # Formatting, ruamel.yaml configuration, style enforcement
│   └── main.py                # FastAPI entry point
├── knowledge/
│   ├── cspl-rules.md          # Core YAML syntax and action schemas
│   └── examples.md            # Real user prompts → changes examples
```

---

## 5. Implementation Principles

### 1. Minimal Surgical Edits
- **Rule**: Never replace a whole workflow if only one step changed.
- **Implementation**: The processor classes work on specific Step IDs and maintain the parent structure across all three files.

### 2. Formatting Preservation
- **Rule**: Comments and indentation must remain identical to the original file.
- **Implementation**: Exclusive use of `ruamel.yaml` with `fa.set_flow_style()` for specific inline lists (`input`).

### 3. File Size & Cleanliness
- **Rule**: Max 400 lines per file.
- **Implementation**: If any processor grows, logic will be split into sub-modules.
- **Rule**: Single-line comments for "Why", not "What". No docstrings.

### 4. Multi-File Coordination
- **Rule**: A single user request may require changes across multiple files.
- **Implementation**: The orchestrator coordinates edits to `workflow.yaml`, `constants.yaml`, and `tone.yaml` as a single atomic "Change Set".
- **Validation**: All files must validate successfully before presenting to the user.

### 5. Knowledge Retrieval
- **Rule**: Don't bloat the prompt.
- **Implementation**: The agent is given a `read_knowledge(topic)` tool with access to:
  - `cspl-rules.md` - Core YAML syntax and action schemas
  - `cspl-examples.md` - Real user prompts and resulting changes
- **Usage**: Agent retrieves knowledge on-demand when encountering complex requirements or unfamiliar patterns.

---

## 6. Development Roadmap

1. **Step 1: Multi-File Processors**: Create `workflow_processor.py`, `constants_processor.py`, and `tone_processor.py` with unified interface.
2. **Step 2: Trinity Loop Orchestrator**: Refactor `agent.py` into the three-phase model with auto-retry validation.
3. **Step 3: Knowledge Base**: Create `cspl-rules.md` and `examples.md` with the `read_knowledge()` tool.
4. **Step 4: Natural Language Explanations**: Build explanation generator that describes changes in plain English (no diffs).
5. **Step 5: Enhanced Validation**: Implement semantic validation and auto-retry loop in Phase 3.

---

## 7. Cursor/Antigravity Alignment

This implementation follows the core principles that make Cursor and Antigravity successful:

### **Surgical Precision**
- ✅ Never rewrite entire files when only a step needs to change
- ✅ Preserve formatting, comments, and style (via `ruamel.yaml`)
- ✅ Work with specific IDs and paths, not line numbers

### **Conversational Intelligence**
- ✅ Iterative refinement through natural dialog
- ✅ Ask clarifying questions instead of guessing
- ✅ Explain changes in plain language (no technical jargon)
- ✅ Approval gate before any file writes

### **Auto-Correction**
- ✅ Validation failures trigger automatic fixes (Phase 3 → Phase 2 loop)
- ✅ Users never see validation errors unless unfixable
- ✅ System self-corrects without user intervention

### **Knowledge Efficiency**
- ✅ Lean system prompt (no bloat)
- ✅ On-demand knowledge retrieval via `read_knowledge(topic)`
- ✅ Agent decides when it needs more context

### **Multi-File Coordination**
- ✅ Single user request → coordinated changes across multiple files
- ✅ Atomic "Change Set" validation (all or nothing)
- ✅ Clear explanation of cross-file impacts

**Result:** A system that feels like pair-programming with an expert, not filling out forms or debugging YAML syntax errors.