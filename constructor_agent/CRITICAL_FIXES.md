# Critical Fixes - Constructor Agent

## Issues Fixed

### Issue 1: Changes Applied Before User Approval ❌ → ✅

**Problem:**
The agent was saving changes to the workflow.yaml file during validation, BEFORE the user clicked "Approve". This is a critical bug that bypasses the approval flow.

**Root Cause:**
In `validate_proposed_workflow`, the code was calling:
```python
self.processor.save()  # ❌ This writes to disk!
errors = self.validator.validate()
```

This meant that every time the agent validated its proposed changes, it would write them to the actual file.

**Fix Applied:**
Changed validation to use a **temporary file** instead:

```python
# Create a temporary copy for validation
with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp_file:
    tmp_path = tmp_file.name
    # Write current in-memory state to temp file
    y = YAML()
    y.preserve_quotes = True
    y.indent(mapping=2, sequence=4, offset=2)
    y.dump_all(self.processor.documents, tmp_file)

try:
    # Validate the temporary file (NOT the real one!)
    temp_validator = WorkflowValidator(tmp_path)
    errors = temp_validator.validate()
    # ... return results
finally:
    # Clean up temp file
    os.unlink(tmp_path)
```

**Result:**
- ✅ Changes stay in memory only during the agent's work
- ✅ Real file is ONLY modified when user clicks "Approve" and `apply_edits()` is called
- ✅ Validation still works correctly

### Issue 2: NoneType Error in propose_step_insertion ❌ → ✅

**Problem:**
The agent sometimes forgot to pass the `new_step` parameter when calling `propose_step_insertion`, causing:
```
ERROR: 'NoneType' object has no attribute 'get'
```

**Root Cause:**
The code assumed `new_step` would always be provided:
```python
success = self.processor.insert_step(wf_name, position, new_step)  # ❌ new_step could be None!
if success:
    new_yaml = self._step_to_yaml(new_step)  # ❌ Crashes if new_step is None
```

**Fix Applied:**
Added validation before attempting insertion:

```python
# Validate that new_step is provided
if not new_step:
    tool_result = "❌ Error: 'new_step' parameter is required for step insertion"
else:
    success = self.processor.insert_step(wf_name, position, new_step)
    if success:
        # ... proceed with insertion
```

**Result:**
- ✅ Clear error message if agent forgets the parameter
- ✅ No more NoneType crashes
- ✅ Agent can recover and retry with correct parameters

## Workflow Now

### Correct Flow (After Fixes)

```
1. User sends request: "Add age field to BookFlight"

2. Agent explores:
   - search_workflow_content(query="fetch_user_id")
   - read_workflow_step(workflow_name="BookFlight", step_id="fetch_user_id")

3. Agent proposes change:
   - validate_step(step_content={...new step...})  ✅ Valid
   - propose_step_insertion(workflow_name="BookFlight", position={...}, new_step={...})
   → Changes stored IN MEMORY only

4. Agent validates:
   - validate_proposed_workflow(workflow_name="BookFlight")
   → Validates using TEMPORARY file
   → Real workflow.yaml is NOT modified ✅

5. Agent submits:
   - submit_final_proposal(explanation="...", edits=[...])
   → Returns proposal to user

6. User reviews and clicks "Approve"

7. System applies:
   - apply_edits(edits)
   → NOW the real workflow.yaml is modified ✅
```

### What Was Happening Before (WRONG)

```
1-3. Same as above

4. Agent validates:
   - validate_proposed_workflow(workflow_name="BookFlight")
   → self.processor.save()  ❌ WRITES TO REAL FILE!
   → User hasn't approved yet!

5-7. User sees changes already applied before clicking approve
```

## Files Modified

### `/Users/nirmendelson/quack/tau2-bench/constructor_agent/app/agent.py`

**Change 1 (Lines 423-453):** `validate_proposed_workflow` implementation
- Removed: `self.processor.save()`
- Added: Temporary file validation approach
- Impact: Changes no longer written to disk during validation

**Change 2 (Lines 503-529):** `propose_step_insertion` implementation
- Added: Validation check for `new_step` parameter
- Impact: Clear error instead of NoneType crash

## Testing

To verify the fixes:

1. **Start the server** (already done):
   ```bash
   cd /Users/nirmendelson/quack/tau2-bench/constructor_agent
   source ../.venv/bin/activate
   python -m uvicorn app.main:app --reload --port 8000 &
   ```

2. **Send a request** through the UI:
   ```
   "Add a step to fetch user age in BookFlight"
   ```

3. **Verify behavior**:
   - ✅ Agent proposes changes
   - ✅ Agent validates (using temp file)
   - ✅ workflow.yaml is NOT modified yet
   - ✅ User sees proposal in UI
   - ✅ User clicks "Approve"
   - ✅ ONLY THEN is workflow.yaml modified

4. **Check for errors**:
   - ✅ No NoneType errors
   - ✅ No premature file writes
   - ✅ Clean validation process

## Prevention

These fixes ensure:

1. **Separation of Concerns**:
   - Validation = read-only operation (temp file)
   - Application = write operation (real file)

2. **Proper Approval Flow**:
   - Agent proposes → User reviews → User approves → System applies

3. **Better Error Handling**:
   - Validate parameters before using them
   - Clear error messages for missing parameters

## Summary

✅ **Fixed**: Premature file writes during validation
✅ **Fixed**: NoneType errors in step insertion
✅ **Method**: Temporary file validation + parameter validation
✅ **Result**: Proper approval flow maintained
✅ **Status**: Server restarted with fixes

The agent now properly waits for user approval before making any changes to the actual workflow files!
