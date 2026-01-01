# YAML Formatting Fix - Constructor Agent

## Problem

The agent was corrupting YAML formatting when making edits. The workflow.yaml file was getting `\n` escape sequences instead of actual newlines, breaking the file structure.

### Root Cause

The agent was calling `validate_proposed_workflow` with a **`content` parameter containing YAML as a string**, which caused:

1. YAML → String conversion (adding escape sequences)
2. String → Dict parsing (corrupting formatting)
3. Dict → YAML writing (wrong indentation and newlines)

Example of corrupted output:
```yaml
# Before (correct):
message: |
  Here are the available flights

# After (corrupted):
message: "Here are the available flights\n"
```

## Solution

### 1. Updated System Prompt

Added **explicit warnings** to prevent the agent from passing YAML content:

```python
### CRITICAL RULES:
- ❌ **NEVER pass YAML content as strings** - this corrupts formatting!
- ❌ **NEVER call validate_proposed_workflow with 'content' parameter** - it only needs workflow_name!
- ✅ ALWAYS use `propose_step_modification` or `propose_step_insertion` to make changes
- ✅ ALWAYS call `validate_proposed_workflow(workflow_name="X")` with ONLY the workflow name

### VALIDATION RULES:
- `validate_step` - Pass the step as a JSON object
- `validate_proposed_workflow` - Pass ONLY the workflow_name (string), NOT the content!
  - ✅ CORRECT: `validate_proposed_workflow(workflow_name="BookFlight")`
  - ❌ WRONG: `validate_proposed_workflow(name="BookFlight", content="...")`
- The system tracks changes in memory automatically - you don't need to pass content!
```

### 2. Updated Tool Description

Made the `validate_proposed_workflow` tool description more explicit:

```python
{
    "name": "validate_proposed_workflow",
    "description": "Validate the ENTIRE workflow after your proposed changes. IMPORTANT: Only pass workflow_name - changes are tracked in memory automatically. DO NOT pass 'content' parameter!",
    "parameters": {
        "type": "object",
        "properties": {
            "workflow_name": {
                "type": "string",
                "description": "Name of the workflow to validate (changes already in memory)"
            }
        },
        "required": ["workflow_name"]
    }
}
```

### 3. How It Works Now

**Correct Workflow:**
```
1. Agent calls: propose_step_insertion(workflow_name="BookFlight", position={...}, new_step={...})
   → Step is inserted into memory using ruamel.yaml (preserves formatting)

2. Agent calls: validate_proposed_workflow(workflow_name="BookFlight")
   → System saves current in-memory state to disk
   → Validator reads the file and checks it
   → No string conversion = no formatting corruption

3. Agent calls: submit_final_proposal(edits=[...])
   → User approves
   → apply_edits() writes changes to disk using ruamel.yaml
   → Formatting is preserved perfectly
```

**What Was Happening Before (WRONG):**
```
1. Agent calls: read_workflow(name="BookFlight")
   → Gets YAML as string

2. Agent calls: validate_proposed_workflow(name="BookFlight", content="workflow: BookFlight\nwhen: ...")
   → System tries to parse string as YAML
   → Formatting gets corrupted with escape sequences
   → Validation fails or produces wrong output
```

## Key Principles

### 1. In-Memory Tracking
All modifications are tracked in memory using `ruamel.yaml`, which preserves:
- Comments
- Indentation
- Quote styles
- Line breaks
- Formatting

### 2. No String Passing
The agent should **NEVER** pass YAML content as strings. Instead:
- Use `propose_step_modification` to modify steps (passes dict objects)
- Use `propose_step_insertion` to add steps (passes dict objects)
- Use `validate_proposed_workflow` with only the workflow name

### 3. Automatic Persistence
The system automatically:
- Loads workflows into memory on startup
- Tracks all changes in memory
- Saves to disk when validating or applying edits
- Preserves formatting throughout

## Testing

To verify the fix works:

1. **Start the server** (with updated code):
   ```bash
   cd /Users/nirmendelson/quack/tau2-bench
   source .venv/bin/activate
   cd constructor_agent
   python -m uvicorn app.main:app --reload --port 8000
   ```

2. **Make a request** through the web UI or API:
   ```
   "Add a step to fetch user age after fetching user_id in BookFlight"
   ```

3. **Verify the agent**:
   - ✅ Uses `search_workflow_content` to find the step
   - ✅ Uses `read_workflow_step` to examine it
   - ✅ Uses `propose_step_insertion` with a dict object
   - ✅ Uses `validate_proposed_workflow(workflow_name="BookFlight")` - NO content parameter!
   - ✅ Formatting is preserved in the output

## What Changed in Code

### File: `constructor_agent/app/agent.py`

1. **Lines 59-88**: Added explicit warnings in system prompt
2. **Lines 172-183**: Updated `validate_proposed_workflow` tool description
3. **Lines 424-435**: Implementation already correct (only uses workflow_name)

### Server Restart Required

After making these changes, the server **MUST be restarted** to load the new code:
```bash
# Kill old process
pkill -f "uvicorn app.main:app"

# Start new process
cd /Users/nirmendelson/quack/tau2-bench/constructor_agent
source ../.venv/bin/activate
python -m uvicorn app.main:app --reload --port 8000 &
```

## Prevention

The agent will now:
1. **Never** pass YAML content as strings
2. **Always** use the granular modification tools
3. **Always** validate using only workflow_name
4. **Always** preserve formatting through ruamel.yaml

## Summary

✅ **Fixed**: YAML formatting corruption
✅ **Method**: Explicit warnings + clearer tool descriptions
✅ **Result**: Agent uses in-memory tracking, never passes strings
✅ **Status**: Server restarted with updated code

The agent now works exactly like Cursor - making surgical edits while preserving all formatting!
