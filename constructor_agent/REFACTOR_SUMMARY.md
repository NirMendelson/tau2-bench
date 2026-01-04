# Constructor Agent Refactor: Cursor-Style Unified Agent

## What Changed

We refactored the Constructor Agent from a **Trinity Loop** (Planner → Executor → Validator) to a **Cursor-style unified agent** that combines exploration and editing in a single conversational flow.

---

## Before (Trinity Loop)

```
User Request
    ↓
[Planner Phase]
- Explores codebase
- Creates technical plan
- Asks "Shall I proceed?"
    ↓
[Executor Phase]
- Reads the plan
- Makes edits
    ↓
[Validator Phase]
- Validates changes
- Auto-retries if errors
    ↓
User Approval Required
```

**Issues:**
- Two separate LLM calls (Planner + Executor)
- Always asks for confirmation ("Shall I proceed?")
- Technical plan was separate from user-facing message
- More complex orchestration logic

---

## After (Cursor-Style Unified)

```
User Request
    ↓
[Unified Agent]
- Explores codebase (search, read workflows)
- Makes edits (apply_edit)
- Validates changes (auto-retry on errors)
- Explains what it did (conversational)
    ↓
User sees: "Done! I updated the booking process to ask for gender."
    ↓
Optional Approval (if changes were made)
```

**Benefits:**
- Single LLM call (faster, cheaper)
- More conversational (like talking to Cursor)
- Agent decides when to ask questions vs just do it
- Simpler codebase (less orchestration)

---

## Key Files

### 1. `unified_prompt.py` (NEW)
**What it does:** Defines the system prompt and tools for the unified agent

**Key features:**
- Matches user's technical level (simple vs technical language)
- Emphasizes "explore first, edit second"
- No confirmation required for straightforward requests
- Includes CSPL syntax reference in the prompt

**Example from prompt:**
```
User: "I have no dev experience. Can you make the booking process ask for gender?"

You: "I'll help you with that! Let me update the flight booking process...
[calls tools to explore and edit]
Done! The booking process now asks for gender right after collecting passenger details."
```

### 2. `unified_agent.py` (NEW)
**What it does:** Single agent that handles everything in one conversational flow

**Key methods:**
- `process_request()` - Main entry point
- `_run_agent_with_validation()` - Runs agent with auto-retry on validation errors
- `_execute_tool()` - Handles both exploration tools (search, read) and editing tools (apply_edit)

**How it works:**
1. Agent can make up to 20 tool calls in one turn
2. It explores (search_workflow_content, read_workflow) 
3. Then edits (apply_edit)
4. Validates changes automatically
5. If validation fails, sends errors back to agent to fix
6. Returns conversational message + edits (if any)

### 3. `main.py` (UPDATED)
**What changed:**
- Replaced `TrinityOrchestrator` with `UnifiedAgent`
- Simplified chat endpoint
- Agent response is always conversational (no separate "clarification" vs "explanation" logic)
- If agent made changes → return as "explanation" with edits
- If no changes → return as "clarification" (just conversation)

---

## How It Works Like Cursor

### 1. **Conversational Intelligence**
**Cursor:** Adapts language to user's level
**Our Agent:** Prompt says "Match the user's level - if they use simple language, respond simply"

### 2. **Direct Action**
**Cursor:** Makes changes without asking "Shall I proceed?" on straightforward requests
**Our Agent:** Prompt says "Make changes directly - don't ask 'Shall I proceed?' unless ambiguous"

### 3. **Interleaved Exploration + Editing**
**Cursor:** Can search, read, and edit in the same turn
**Our Agent:** All tools available simultaneously - agent decides when to explore vs edit

### 4. **Auto-Validation**
**Cursor:** Uses linters + auto-retry
**Our Agent:** Validates YAML syntax + auto-retry on errors (transparent to user)

### 5. **Explain After Doing**
**Cursor:** "I've updated the booking logic to include gender..."
**Our Agent:** "Done! The booking process now asks for gender right after collecting passenger details."

---

## Example Interaction

**User:** "I have no dev experience. Can you make the booking process ask for gender?"

**Agent's Internal Flow:**
1. Calls `search_workflow_content("booking")` → finds "BookFlight" workflow
2. Calls `read_workflow("BookFlight")` → understands current structure
3. Calls `apply_edit(file="workflow.yaml", edit_type="update_workflow_steps", ...)` → adds gender step
4. Calls `apply_edit(file="constants.yaml", edit_type="add_prerequisite", ...)` → makes gender required
5. Validates changes → success!

**Agent's Response to User:**
```
I'll help you with that! Let me update the flight booking process to ask for the passenger's gender.

Done! The booking process now asks for gender right after collecting passenger details. The gender information will be saved with the booking.
```

**User sees:**
- Simple, friendly explanation
- No technical jargon ("YAML", "step_003", "fetch action")
- Clear description of what changed
- Option to approve or ask for changes

---

## What We Kept

✅ **Auto-validation with retry** - Still validates YAML and auto-fixes errors
✅ **Multi-file coordination** - Can edit workflow.yaml, constants.yaml, tone.yaml together
✅ **Knowledge retrieval** - Agent can still call `read_knowledge('rules')` for CSPL syntax
✅ **Conversation history** - Session-based memory across turns
✅ **Approval gate** - User still approves before changes are written to disk

---

## What We Removed

❌ **Separate Planner/Executor phases** - Now one unified agent
❌ **Explicit technical plan object** - Plan is implicit in conversation
❌ **Always asking "Shall I proceed?"** - Only asks if genuinely ambiguous
❌ **ExplanationGenerator** - Agent explains naturally in its response

---

## Code Complexity Comparison

**Before:**
- `orchestrator.py` - 135 lines (3 phases)
- `planner_prompt.py` - 122 lines
- `executor_logic.py` - 249 lines
- `explanation_generator.py` - 33 lines
- **Total: ~540 lines**

**After:**
- `unified_agent.py` - 145 lines (everything)
- `unified_prompt.py` - 200 lines (prompt + tools)
- **Total: ~345 lines**

**Reduction: ~35% less code, much simpler logic**

---

## Testing the New System

Try these prompts to see the conversational style:

**Simple user:**
- "I have no dev experience. Can you make the booking ask for gender?"
- "Add a step to confirm the user's email address"

**Technical user:**
- "Add a fetch step for passenger_gender to the BookFlight workflow"
- "Create a new subworkflow for premium member validation"

**Ambiguous request:**
- "Make the booking process better" → Agent should ask clarifying questions

---

## Summary

We've successfully transformed the Constructor Agent to work like Cursor/Antigravity:

1. ✅ **Single conversational agent** (not separate Planner/Executor)
2. ✅ **Explores and edits in one turn** (all tools available)
3. ✅ **Adapts to user's technical level** (simple vs technical language)
4. ✅ **Makes changes directly** (no unnecessary confirmation)
5. ✅ **Auto-validates and retries** (transparent error handling)
6. ✅ **Explains naturally** (conversational, not technical)

The system is now simpler, faster, and more natural to use - just like Cursor!
