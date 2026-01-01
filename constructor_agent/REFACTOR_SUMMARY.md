# Constructor Agent - Cursor/Antigravity Mindset Refactor

## Summary

The Constructor Agent has been completely refactored to work exactly like Cursor and Antigravity - with a focus on **surgical, targeted edits** rather than full workflow replacements.

## Key Changes Made

### 1. Enhanced WorkflowProcessor (`processor.py`)

Added **granular operations** for precise workflow manipulation:

#### New Methods:
- **`search_content(query, workflow_name=None)`** - Search for text across workflows, returns matching steps with IDs and locations
- **`get_step_by_id(workflow_name, step_id)`** - Read a specific step by its ID (avoids loading entire workflow)
- **`modify_step(workflow_name, step_id, new_step)`** - Replace a specific step in place
- **`insert_step(workflow_name, position, new_step)`** - Insert a new step before/after another step or at an index
- **`delete_step(workflow_name, step_id)`** - Remove a specific step by ID

These methods work recursively through nested steps (then/else branches), making surgical edits possible.

### 2. Completely Rewritten Agent (`agent.py`)

#### New System Prompt (Cursor Mindset)
The system prompt now explicitly teaches the agent to work like Cursor:

**Core Principles:**
1. ✅ **Search Before You Act** - Never assume structure, always explore first
2. ✅ **Read Precisely** - Use targeted reads, not full workflow dumps
3. ✅ **Surgical Edits Only** - Modify ONLY what needs to change
4. ✅ **Validate Incrementally** - Check steps individually, then validate full workflow
5. ✅ **Never Delete Accidentally** - Preserve 100% of existing logic
6. ✅ **Show Clear Diffs** - Always explain what changed and why

**Workflow Pattern:**
```
Explore → Read → Plan → Validate Step → Propose → Final Validation → Submit
```

#### New Tools (Granular & Targeted)

**Exploration Tools:**
- `list_workflows` - List all available workflows
- `search_workflow_content` - Search for specific text/patterns across workflows
- `read_workflow` - Read full workflow (use sparingly)
- `read_workflow_step` - Read a SPECIFIC step by ID (preferred)

**Validation Tools:**
- `validate_step` - Validate a single step against CSPL rules
- `validate_proposed_workflow` - Validate entire workflow after changes

**Modification Tools:**
- `propose_step_modification` - Modify or delete an existing step
  - Types: `replace`, `delete`
  - Generates before/after diff
  - Requires reason for change
  
- `propose_step_insertion` - Insert a new step at a specific position
  - Position types: `before`, `after`, `at_index`
  - Requires reason for change

**Submission Tool:**
- `submit_final_proposal` - Submit all changes with:
  - Natural language explanation
  - List of edits with before/after YAML
  - Clear diffs showing what changed
  - Reason for each change

#### Diff Generation
Added `_generate_diff()` method using Python's `difflib` to create unified diffs showing exactly what changed.

#### Better Error Handling
- Each tool call wrapped in try/except
- Clear error messages with ❌/✅ emojis
- Validation errors returned as structured JSON

### 3. Updated Test Script (`test_agent.py`)

Modified to display the new edit format:
- Shows workflow name, edit type, step ID, and reason for each edit
- Properly handles the new structure

## How It Works (Example)

**User Request:** "On canceling flight, after getting the reservation id, if the reservation id is missing, you have to use the escalation tool."

**Agent's Cursor-Style Workflow:**

1. **🔍 List workflows** → Finds `CancelFlight` workflow
2. **🔎 Search** for "reservation id" in `CancelFlight`
3. **📖 Read** specific step `fetch_reservation_id`
4. **📖 Read** related steps to understand context
5. **✏️ Propose modification** to the escalation step
6. **✅ Validate** the proposed workflow
7. **📝 Submit** final proposal with clear diff

**Output:**
```
✅ Step 'reservation_id_missing' modified in memory.

Diff:
--- before
+++ after
@@ -1,5 +1,2 @@
-id: reservation_id_missing
-action: use_tool
-tool_name: escalate_issue
-input:
-  - missing reservation id
+id: reservation_id_missing
+action: use_tool
+tool_name: transfer_to_human_agents
+input:
+  - "Missing reservation id for flight cancellation"

Reason: Correct tool name for escalating missing reservation id to human agents.
```

## Comparison: Before vs After

### Before (Old Approach)
```python
# Agent would:
1. Read ENTIRE workflow (wasteful)
2. Modify the whole workflow object
3. Replace entire workflow in memory
4. No clear diff of what changed
5. Risk of accidentally deleting logic
```

### After (Cursor Mindset)
```python
# Agent now:
1. Search for relevant section
2. Read ONLY the specific step
3. Modify ONLY that step
4. Generate clear before/after diff
5. Validate incrementally
6. Preserve all existing logic
```

## Benefits

### 1. **Precision**
- Only modifies what needs to change
- No accidental deletions
- Clear audit trail of changes

### 2. **Efficiency**
- Reads less data (specific steps vs entire workflows)
- Faster validation (can validate individual steps)
- Lower token usage with LLM

### 3. **Transparency**
- Clear diffs show exactly what changed
- Reason provided for each modification
- Easy to review and approve changes

### 4. **Safety**
- Incremental validation catches errors early
- Changes are staged in memory before commit
- Full workflow validation before final submission

### 5. **Scalability**
- Can handle large workflows efficiently
- Nested step modifications work recursively
- Search across multiple workflows simultaneously

## Technical Details

### Recursive Step Navigation
All processor methods handle nested steps in `then`/`else` branches:
```python
def find_step(steps):
    for step in steps:
        if step.get('id') == step_id:
            return step
        # Recurse into then/else branches
        if 'then' in step:
            result = find_step(then_block['steps'])
            if result:
                return result
        # ... same for else
```

### YAML Preservation
Uses `ruamel.yaml` with:
- `preserve_quotes = True`
- `indent(mapping=2, sequence=4, offset=2)`

This ensures formatting is maintained when making edits.

### Validation Strategy
Two-level validation:
1. **Step-level**: Check individual step against CSPL rules
2. **Workflow-level**: Run full linter on entire workflow

## Loop Limit
Increased from 15 to 30 iterations to handle complex multi-step modifications while still preventing infinite loops.

## Files Modified

1. **`constructor_agent/app/processor.py`** - Added 5 new methods for granular operations
2. **`constructor_agent/app/agent.py`** - Complete rewrite with Cursor mindset
3. **`constructor_agent/test_agent.py`** - Updated to display new edit format

## Testing

The agent successfully:
- ✅ Lists workflows to orient itself
- ✅ Searches for relevant content
- ✅ Reads specific steps (not entire workflows)
- ✅ Makes surgical modifications
- ✅ Validates changes incrementally
- ✅ Generates clear diffs
- ✅ Submits proposals with explanations

## Next Steps

To use the updated agent:

```python
from constructor_agent.app.agent import ConstructorAgent

agent = ConstructorAgent(
    workflow_path="/path/to/workflow.yaml",
    rules_path="/path/to/cspl-rules.md"
)

result = agent.process_request("Your modification request here")

if result.get('edits'):
    # Review the proposed changes
    for edit in result['edits']:
        print(f"Workflow: {edit['workflow_name']}")
        print(f"Type: {edit['edit_type']}")
        print(f"Before:\n{edit['before']}")
        print(f"After:\n{edit['after']}")
        print(f"Reason: {edit['reason']}")
    
    # Apply if approved
    success, errors = agent.apply_edits(result['edits'])
```

## Conclusion

The Constructor Agent now operates with the **exact same mindset as Cursor and Antigravity**:
- 🎯 Targeted, surgical edits
- 🔍 Search-first approach
- ✅ Validate before proposing
- 📊 Clear diffs and explanations
- 🛡️ Preservation of existing logic

It follows CSPL rules while maintaining the precision and safety of modern AI code editors.
