# Constructor Agent Refactoring Plan

## Core Philosophy: Think Like Cursor/Antigravity

This refactoring transforms the Constructor Agent from a basic prototype into a **production-grade conversational workflow architect** that matches the quality bar of Cursor and Antigravity.

### Guiding Principles

**1. Conversational Intelligence**
- The agent should feel like pair-programming with an expert
- Ask clarifying questions instead of guessing
- Explain changes in natural language (no technical jargon)
- Iterative refinement through dialog

**2. Code Quality for Developers**
- **Clear function purpose**: Each function does ONE thing
- **No docstrings**: Simple comment above function is enough
- **File purpose**: Each file has a single, clear responsibility
- **Max 400 lines**: If a file grows, split it into sub-modules
- **Comments explain "why", not "what"**

**3. Surgical Precision**
- Never rewrite entire files when only one step needs to change
- Preserve formatting, comments, and indentation (via `ruamel.yaml`)
- Work with specific IDs and paths, not line numbers

**4. Auto-Correction**
- Validation failures trigger automatic fixes (Phase 3 → Phase 2 loop)
- Users never see validation errors unless unfixable
- System self-corrects without user intervention

---

## Current State Analysis

### What Exists
- ✅ `processor.py` - Basic YAML reading/writing with `ruamel.yaml`
- ✅ `agent.py` - Single-pass agentic loop with tools
- ✅ `validator.py` - Basic validation
- ✅ `main.py` - FastAPI endpoints

### What's Missing
- ❌ **Trinity Loop architecture** (Planner → Executor → Validator)
- ❌ **Multi-file support** (only handles `workflow.yaml`, not `constants.yaml` or `tone.yaml`)
- ❌ **Auto-retry validation loop** (validation errors are shown to user)
- ❌ **On-demand knowledge retrieval** (all rules are in the system prompt)
- ❌ **Natural language explanations** (no explanation generator)
- ❌ **Modular architecture** (everything is in monolithic files)

---

## Phase 1: Foundation - Multi-File Processors

**Goal**: Create a unified interface for editing all three YAML files with surgical precision.

### Why This Phase?
From IMPLEMENTATION.md:
- "Support coordinated edits across `workflow.yaml`, `constants.yaml`, and `tone.yaml`"
- "The processor classes work on specific Step IDs and maintain the parent structure across all three files"
- "A single user request may require changes across multiple files"

### What to Build

#### 1.1 Create `app/processor/` Directory
Split the monolithic `processor.py` into three specialized processors:

**`workflow_processor.py`** (~300 lines)
```python
# Handles reading, searching, and editing workflow.yaml
# Maintains the existing WorkflowProcessor functionality

class WorkflowProcessor:
    def load(self) -> List[Any]
    
    def search_content(self, query: str, workflow_name: str = None) -> List[dict]
    
    def get_step_by_id(self, workflow_name: str, step_id: str) -> dict
    
    def modify_step(self, workflow_name: str, step_id: str, new_step: dict) -> bool
    
    def insert_step(self, workflow_name: str, position: dict, new_step: dict) -> bool
    
    def delete_step(self, workflow_name: str, step_id: str) -> bool
    
    def save(self)
```

**`constants_processor.py`** (~150 lines)
```python
# Handles reading and editing constants.yaml
# Simple key-value pairs, no complex nesting

class ConstantsProcessor:
    def load(self) -> dict
    
    def get(self, key: str) -> Any
    
    def set(self, key: str, value: Any) -> bool
    
    def delete(self, key: str) -> bool
    
    def add_prerequisite(self, field: str) -> bool
    
    def remove_prerequisite(self, field: str) -> bool
    
    def save(self)
```

**`tone_processor.py`** (~150 lines)
```python
# Handles reading and editing tone.yaml
# Short file with identity, tone, and guidelines

class ToneProcessor:
    def load(self) -> dict
    
    def set_role(self, role: str) -> bool
    
    def set_tone(self, tone: str) -> bool
    
    def add_guideline(self, guideline: str) -> bool
    
    def remove_guideline(self, guideline: str) -> bool
    
    def save(self)
```

#### 1.2 Create `app/utils/yaml_manager.py`
Extract common YAML formatting logic to avoid duplication:

```python
# Shared YAML configuration and formatting utilities

def get_yaml_instance() -> YAML

def enforce_flow_style(data: Any)

def step_to_yaml(step: dict) -> str
```

### Deliverables
- ✅ Three processor classes with clear, single responsibilities
- ✅ Unified interface (all have `load()` and `save()`)
- ✅ Shared YAML utilities to avoid code duplication
- ✅ Delete old `processor.py` file
- ✅ Update imports in `agent.py` and `main.py`

### Success Criteria
- Each processor file is under 400 lines
- Functions have clear purpose with simple comments (no docstrings)
- All three files can be edited independently
- Formatting is preserved (via `ruamel.yaml`)

---

## Phase 2: Trinity Loop Architecture

**Goal**: Refactor the agent into a three-phase loop (Planner → Executor → Validator) with auto-retry.

### Why This Phase?
From IMPLEMENTATION.md:
- "To ensure accuracy and safety, the agent will operate in a three-phase 'Trinity Loop' for every user interaction"
- "If validation fails, the agent receives the error and loops back to Phase 2 automatically without user intervention"
- "Once valid, generate a natural language explanation of the changes for user approval"

### What to Build

#### 2.1 Create `app/agent/` Directory
Split the monolithic `agent.py` into three focused modules:

**`orchestrator.py`** (~200 lines)
```python
# Manages the Planner-Executor-Validator loop with auto-retry

class TrinityOrchestrator:
    def __init__(self, workflow_processor, constants_processor, tone_processor, validator)
    
    def process_request(self, user_message: str) -> dict
    
    def _run_planner(self, user_message: str) -> dict
    
    def _run_executor(self, plan: dict) -> dict
    
    def _run_validator(self, change_set: dict) -> dict
    
    def _generate_explanation(self, change_set: dict) -> str
```

**`planner_prompt.py`** (~150 lines)
```python
# System prompt and strategy for Phase 1 (Discovery)

def get_planner_prompt() -> str

def get_planner_tools() -> List[dict]

def parse_planner_response(response: str) -> dict
```

**`executor_logic.py`** (~250 lines)
```python
# Handles tool calls and draft state management for Phase 2

class ExecutorLogic:
    def __init__(self, workflow_processor, constants_processor, tone_processor)
    
    def get_executor_prompt(self, plan: dict) -> str
    
    def get_executor_tools(self) -> List[dict]
    
    def execute_tool(self, tool_name: str, args: dict) -> dict
    
    def get_change_set(self) -> dict
```

#### 2.2 Update `app/validator.py`
Enhance validation to support auto-retry:

```python
class WorkflowValidator:
    def validate_change_set(self, change_set: dict) -> Tuple[bool, List[str]]
    
    def validate_workflow_changes(self, changes: List[dict]) -> Tuple[bool, List[str]]
    
    def validate_constants_changes(self, changes: List[dict]) -> Tuple[bool, List[str]]
    
    def validate_tone_changes(self, changes: List[dict]) -> Tuple[bool, List[str]]
```

#### 2.3 Update `app/main.py`
Simplify to use the new orchestrator:

```python
from constructor_agent.app.agent.orchestrator import TrinityOrchestrator

workflow_processor = WorkflowProcessor(WORKFLOW_PATH)
constants_processor = ConstantsProcessor(CONSTANTS_PATH)
tone_processor = ToneProcessor(TONE_PATH)
validator = WorkflowValidator(...)
orchestrator = TrinityOrchestrator(
    workflow_processor,
    constants_processor,
    tone_processor,
    validator
)

@app.post("/chat")
async def chat(request: ChatRequest):
    result = orchestrator.process_request(request.message)
    return result
```

### Deliverables
- ✅ Trinity Loop orchestrator with auto-retry logic
- ✅ Separate planner, executor, and validator phases
- ✅ Natural language explanation generator
- ✅ Enhanced validation with detailed error messages
- ✅ Delete old monolithic `agent.py`

### Success Criteria
- Validation failures automatically trigger Phase 2 re-execution
- Users never see validation errors (unless unfixable after 3 retries)
- Each phase has a clear, single responsibility
- Code is easy to understand and debug

---

## Phase 3: Knowledge Base & On-Demand Retrieval

**Goal**: Create knowledge files and implement on-demand retrieval to keep the system prompt lean.

### Why This Phase?
From IMPLEMENTATION.md:
- "Don't bloat the prompt"
- "The agent is given a `read_knowledge(topic)` tool with access to `cspl-rules.md` and `cspl-examples.md`"
- "Agent retrieves knowledge on-demand when encountering complex requirements or unfamiliar patterns"

### What to Build

#### 3.1 Create `knowledge/` Directory

**`cspl-rules.md`**
Already exists! Contains:
- General YAML structure rules
- All action types with schemas (fetch, use_tool, conditional, etc.)
- Logic and template rules
- Critical rules and best practices

**`cspl-examples.md`** (new file, ~200 lines)
```markdown
# CSPL Examples: Real User Prompts → Changes

## Example 1: Add User Input Collection
**User prompt:** "Before booking shoes, ask the user for their size"

**Changes made:**
- **File:** workflow.yaml
- **Workflow:** BookShoes
- **Action:** Inserted step before `book_item`
- **New step:**
  ```yaml
  - id: ask_shoe_size
    action: fetch
    field: shoe_size
    comment: Required for inventory check
  ```

## Example 2: Add Conditional Routing
**User prompt:** "If the user is a premium member, skip the payment step"

**Changes made:**
- **File:** workflow.yaml
- **Workflow:** BookFlight
- **Action:** Wrapped `process_payment` in conditional
- **New structure:**
  ```yaml
  - id: check_premium
    action: conditional
    condition: "{user.membership} = premium"
    then:
      - id: skip_to_confirmation
        action: use_subworkflow
        subworkflow: SendConfirmation
    else:
      - id: process_payment
        action: use_tool
        tool: charge_card
  ```

## Example 3: Add Default Prerequisite
**User prompt:** "Always ask for the user's account number before doing anything"

**Changes made:**
- **File:** constants.yaml
- **Action:** Added to default_prerequisites
- **Change:**
  ```yaml
  default_prerequisites:
    - user_id
    - account_number  # NEW
  ```

## Example 4: Update Communication Tone
**User prompt:** "Make the agent more formal and don't use emojis"

**Changes made:**
- **File:** tone.yaml
- **Action:** Updated tone field
- **Change:**
  ```yaml
  tone: "Be professional, formal, and concise. Do not use emojis."
  ```

[... more examples covering all common patterns ...]
```

#### 3.2 Create `app/agent/knowledge_retrieval.py`
```python
# On-demand knowledge retrieval tool

# Read knowledge from a specific file
def read_knowledge(topic: str) -> str

# Available topics:
# - "rules" -> cspl-rules.md
# - "examples" -> cspl-examples.md
# - "action:<name>" -> specific action section from cspl-rules.md
```

#### 3.3 Update Planner Prompt
Add the `read_knowledge` tool to the planner's toolset:

```python
# In planner_prompt.py
def get_planner_tools():
    return [
        {
            "name": "search_workflow_content",
            "description": "Search for text in workflows",
            ...
        },
        {
            "name": "read_knowledge",
            "description": "Read CSPL syntax rules or examples on-demand",
            "parameters": {
                "topic": "One of: 'rules', 'examples', 'action:<name>'"
            }
        },
        ...
    ]
```

### Deliverables
- ✅ `cspl-examples.md` with 10+ real-world examples
- ✅ `knowledge_retrieval.py` with `read_knowledge()` function
- ✅ Updated planner prompt to include the knowledge tool
- ✅ Lean system prompt (no embedded rules)

### Success Criteria
- System prompt is under 1000 tokens
- Agent can retrieve rules/examples when needed
- Knowledge files are easy to update and maintain

---

## Phase 4: Natural Language Explanations & Polish

**Goal**: Build the explanation generator and polish the user experience.

### Why This Phase?
From IMPLEMENTATION.md:
- "Explain changes in natural language (no technical jargon)"
- "Use workflow/step names, not line numbers or YAML paths"
- "Group related changes by file"
- "No code snippets or diffs (users don't need to see YAML)"

### What to Build

#### 4.1 Create `app/agent/explanation_generator.py`
```python
class ExplanationGenerator:
    def generate_explanation(self, change_set: dict) -> str
    
    def _explain_workflow_changes(self, changes: List[dict]) -> str
    def _explain_constants_changes(self, changes: List[dict]) -> str
    def _explain_tone_changes(self, changes: List[dict]) -> str
    
    def _format_change(self, change: dict) -> str
```

Example output:
```
I'll make the following changes:

**Workflow: BookShoes**
- Add a new step 'ask_shoe_size' that asks the user for their shoe size
- This will happen right before the 'book_item' step
- The size will be stored in memory and used for inventory checking

**Constants**
- Add 'shoe_size' to the list of required fields

Would you like me to apply these changes?
```

#### 4.2 Update Response Format in Orchestrator
```python
# In orchestrator.py
def _run_validator(self, change_set: dict) -> dict:
    is_valid, errors = self.validator.validate_change_set(change_set)
    
    if not is_valid:
        return self._run_executor_with_fixes(errors)
    
    explanation = self.explanation_generator.generate_explanation(change_set)
    
    return {
        "explanation": explanation,
        "edits": change_set["edits"]
    }
```

#### 4.3 Add Clarification Logic
```python
# In orchestrator.py
def _run_planner(self, user_message: str) -> dict:
    plan = self._call_planner_llm(user_message)
    
    # Check if planner needs clarification
    if plan.get("needs_clarification"):
        return {
            "clarification": plan["question"]
        }
    
    return plan
```

#### 4.4 Polish Error Handling
```python
# In orchestrator.py
MAX_RETRIES = 3

def _run_validator(self, change_set: dict, retry_count: int = 0) -> dict:
    is_valid, errors = self.validator.validate_change_set(change_set)
    
    if not is_valid:
        if retry_count >= MAX_RETRIES:
            # Give up and show error to user
            return {
                "error": "I encountered validation errors that I couldn't fix automatically. Please rephrase your request.",
                "details": errors
            }
        
        # Auto-retry
        fixed_change_set = self._run_executor_with_fixes(errors)
        return self._run_validator(fixed_change_set, retry_count + 1)
    
    # Success!
    explanation = self.explanation_generator.generate_explanation(change_set)
    return {
        "explanation": explanation,
        "edits": change_set["edits"]
    }
```

### Deliverables
- ✅ Natural language explanation generator
- ✅ Clarification request handling
- ✅ Auto-retry with max retry limit
- ✅ User-friendly error messages
- ✅ Polished response format

### Success Criteria
- Explanations are in plain English (no YAML, no line numbers)
- Changes are grouped by file
- Users understand what will happen before approving
- System feels conversational, not robotic

---

## Final Directory Structure

After all phases are complete:

```text
constructor_agent/
├── app/
│   ├── agent/
│   │   ├── orchestrator.py           # Trinity Loop manager
│   │   ├── planner_prompt.py         # Phase 1 prompt & tools
│   │   ├── executor_logic.py         # Phase 2 execution
│   │   ├── explanation_generator.py  # Natural language explanations
│   │   └── knowledge_retrieval.py    # On-demand knowledge tool
│   ├── processor/
│   │   ├── workflow_processor.py     # Edit workflow.yaml
│   │   ├── constants_processor.py    # Edit constants.yaml
│   │   └── tone_processor.py         # Edit tone.yaml
│   ├── validator/
│   │   ├── schema.py                 # CSPL schemas
│   │   └── logic_checks.py           # Semantic validation
│   ├── utils/
│   │   └── yaml_manager.py           # Shared YAML utilities
│   └── main.py                       # FastAPI entry point
├── knowledge/
│   ├── cspl-rules.md                 # Syntax & action schemas
│   └── cspl-examples.md              # Real user prompts → changes
├── FUNCTIONALITIES.md                # Product requirements
├── IMPLEMENTATION.md                 # Architecture design
└── PLAN.md                           # This file
```

---

## Testing Strategy

After each phase, test:

### Phase 1 Tests
- Can edit workflow.yaml without breaking formatting?
- Can edit constants.yaml and tone.yaml?
- Are changes surgical (only modified parts change)?

### Phase 2 Tests
- Does the Trinity Loop run all three phases?
- Do validation failures trigger auto-retry?
- Does the system give up after 3 retries?

### Phase 3 Tests
- Can the agent retrieve knowledge on-demand?
- Is the system prompt under 1000 tokens?
- Does the agent use knowledge appropriately?

### Phase 4 Tests
- Are explanations in plain English?
- Do users understand what will change?
- Does the system feel conversational?

---

## Success Metrics

The refactoring is complete when:

✅ **Cursor/Antigravity Quality**
- System feels like pair-programming with an expert
- Surgical edits preserve formatting
- Auto-correction without user intervention

✅ **Developer Experience**
- Each file has a clear, single purpose
- Functions are under 50 lines with simple comments
- No file exceeds 400 lines
- Easy to understand and debug

✅ **User Experience**
- Natural language explanations (no YAML)
- Clarifying questions when needed
- Approval gate before any changes
- Multi-file coordination is seamless

✅ **Code Quality**
- No docstrings (simple comments only)
- Comments explain "why", not "what"
- Modular architecture with clear separation of concerns
- Easy to extend and maintain

---

## Migration Path

To minimize disruption:

1. **Phase 1**: Build new processors alongside old `processor.py`
2. **Phase 2**: Build new agent/ directory alongside old `agent.py`
3. **Phase 3**: Add knowledge/ directory (no conflicts)
4. **Phase 4**: Polish and test
5. **Cleanup**: Delete old `processor.py` and `agent.py` only after all tests pass

This allows incremental migration with rollback capability at each step.

---

## Conclusion

This plan transforms the Constructor Agent from a basic prototype into a **production-grade system** that matches the quality bar of Cursor and Antigravity. By following the Trinity Loop architecture, maintaining surgical precision, and prioritizing conversational intelligence, we create a system that feels like pair-programming with an expert, not debugging YAML syntax errors.

**The result**: Non-technical users can modify complex workflows through natural conversation, while developers maintain a clean, modular codebase that's easy to understand and extend.
