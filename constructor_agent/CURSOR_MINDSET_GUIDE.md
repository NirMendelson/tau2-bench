# Constructor Agent - Quick Reference

## Cursor Mindset Principles

### ✅ DO:
- **Search first** - Use `search_workflow_content` before making assumptions
- **Read precisely** - Use `read_workflow_step` for targeted reading
- **Edit surgically** - Modify only the specific step that needs changing
- **Validate incrementally** - Check individual steps before full workflow
- **Show diffs** - Always provide clear before/after comparisons
- **Explain changes** - Include reason for every modification

### ❌ DON'T:
- Read entire workflows unless absolutely necessary
- Modify multiple steps when only one needs changing
- Delete steps accidentally
- Propose changes without validation
- Make assumptions about workflow structure

## Tool Usage Pattern

### 1. Exploration Phase
```
list_workflows()
  ↓
search_workflow_content(query="relevant_term")
  ↓
read_workflow_step(workflow_name="X", step_id="Y")
```

### 2. Modification Phase
```
validate_step(step_content={...})
  ↓
propose_step_modification() OR propose_step_insertion()
  ↓
validate_proposed_workflow(workflow_name="X")
```

### 3. Submission Phase
```
submit_final_proposal(
    explanation="What changed and why",
    edits=[{
        workflow_name, edit_type, step_id,
        before, after, reason
    }]
)
```

## Available Tools

### Exploration
| Tool | Use When | Returns |
|------|----------|---------|
| `list_workflows` | Starting any task | List of workflow names |
| `search_workflow_content` | Looking for specific logic | Matching steps with IDs |
| `read_workflow` | Need full context | Complete workflow YAML |
| `read_workflow_step` | Examining specific step | Single step YAML |

### Validation
| Tool | Use When | Returns |
|------|----------|---------|
| `validate_step` | Before proposing a step | Valid/Invalid + errors |
| `validate_proposed_workflow` | After modifications | Valid/Invalid + errors |

### Modification
| Tool | Use When | Effect |
|------|----------|--------|
| `propose_step_modification` | Changing existing step | Replaces or deletes step |
| `propose_step_insertion` | Adding new step | Inserts at position |

### Submission
| Tool | Use When | Effect |
|------|----------|--------|
| `submit_final_proposal` | Ready to submit | Ends task, returns proposal |

## Edit Types

### 1. Modify Step
```python
propose_step_modification(
    workflow_name="CancelFlight",
    step_id="fetch_user_id",
    modification_type="replace",  # or "delete"
    new_step_content={
        "id": "fetch_user_id",
        "action": "fetch",
        "field": "user_id"
    },
    reason="Updated to match new requirements"
)
```

### 2. Insert Step
```python
propose_step_insertion(
    workflow_name="BookFlight",
    position={
        "type": "after",  # or "before", "at_index"
        "reference": "fetch_user_id"  # step_id or index
    },
    new_step={
        "id": "validate_age",
        "action": "conditional",
        "condition": "{age} >= 18",
        "then": {...}
    },
    reason="Added age validation requirement"
)
```

### 3. Delete Step
```python
propose_step_modification(
    workflow_name="BookFlight",
    step_id="deprecated_step",
    modification_type="delete",
    reason="Step no longer needed"
)
```

## Example Workflow

**User Request:** "Add a step to check user membership after fetching user_id in BookFlight"

**Agent Process:**
```
1. list_workflows()
   → Confirms BookFlight exists

2. search_workflow_content(query="fetch_user_id", workflow_name="BookFlight")
   → Finds step at position steps[0]

3. read_workflow_step(workflow_name="BookFlight", step_id="fetch_user_id")
   → Examines current step

4. validate_step(step_content={new membership check step})
   → Confirms step is valid CSPL

5. propose_step_insertion(
     workflow_name="BookFlight",
     position={type: "after", reference: "fetch_user_id"},
     new_step={...membership check...},
     reason="Added membership validation"
   )
   → Step inserted in memory

6. validate_proposed_workflow(workflow_name="BookFlight")
   → Confirms workflow is still valid

7. submit_final_proposal(
     explanation="Added membership check after user_id fetch",
     edits=[{...with before/after diff...}]
   )
   → Task complete
```

## Diff Format

Every edit includes a clear diff:

```
✅ Step 'fetch_user_id' modified in memory.

Diff:
--- before
+++ after
@@ -1,3 +1,4 @@
 id: fetch_user_id
 action: fetch
 field: user_id
+validate: true

Reason: Added validation flag to ensure user_id is verified
```

## Common Patterns

### Pattern 1: Modify a Condition
```
search → read_step → modify_step → validate → submit
```

### Pattern 2: Add New Step
```
search → read_step (context) → validate_step → insert_step → validate → submit
```

### Pattern 3: Fix Tool Name
```
search → read_step → modify_step (replace) → validate → submit
```

### Pattern 4: Remove Deprecated Logic
```
search → read_step → modify_step (delete) → validate → submit
```

## CSPL Compliance

All modifications must follow CSPL rules:
- Every step needs `id` and `action`
- Action-specific fields must be present
- Conditions use proper syntax
- Tool names must be valid
- Variable references use `{{ var }}` syntax

The agent validates both individual steps and the full workflow to ensure CSPL compliance.

## Error Recovery

If validation fails:
1. Agent reads the error message
2. Re-examines the problematic step
3. Fixes the issue based on CSPL rules
4. Validates again
5. Only submits when validation passes

## Performance

**Token Efficiency:**
- Reading specific steps uses ~90% fewer tokens than reading entire workflows
- Search results include previews, not full content
- Validation is incremental

**Speed:**
- Targeted reads are faster
- Fewer LLM calls needed
- Parallel tool calls where possible

## Key Differences from Old Approach

| Aspect | Old | New (Cursor Mindset) |
|--------|-----|---------------------|
| Reading | Full workflow | Specific steps |
| Editing | Replace entire workflow | Modify specific step |
| Validation | All-or-nothing | Incremental |
| Transparency | No diff | Clear before/after |
| Safety | Risk of deletion | Surgical precision |
| Efficiency | High token usage | Optimized reads |

## Summary

The Constructor Agent now works **exactly like Cursor**:
- 🔍 Explores before acting
- 🎯 Makes surgical edits
- ✅ Validates incrementally
- 📊 Shows clear diffs
- 🛡️ Preserves existing logic
- 📝 Explains all changes

This ensures safe, precise, and transparent workflow modifications while following CSPL rules.
