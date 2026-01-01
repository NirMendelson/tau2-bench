# CSPL (Customer Service Process Language) Rules

## General Structure
- A file contains multiple workflows/subworkflows separated by `---`.
- **Main Workflow**: Starts with `workflow: Name`.
- **Subworkflow**: Starts with `subworkflow: Name`.
- Both must have `when: "description of when to use"`.
- `steps`: A list of action objects that define the process.

workflow can be choosen by user input, subworkflows are like helper function that are called by the main workflow.

## Step Fields
Each step MUST have:
- `id`: Unique identifier for the step.
- `action`: The type of action to perform.

## Actions

### 1. `fetch`
Used to get user information.
- `field`: Name of the variable to store (e.g., `user_id`).
- `fields`: (Alternative) List of variables to store.
- **Example**:
  ```yaml
  - id: get_user
    action: fetch
    field: user_id
  ```

### 2. `fetch_with_message`
Display a custom message before getting input.
- `field`: Variable to store input.
- `message`: The text to show the user.
- **Example**:
  ```yaml
  - id: ask_insurance
    action: fetch_with_message
    field: wants_insurance
    message: "Would you like travel insurance?"
  ```

### 3. `conditional`
Branching logic.
- `condition`: String condition (e.g., `"{age} > 18"` or `"{name} = John"`).
- `then`: Steps to execute if true.
- `else`: Steps to execute if false.
- **Example**:
  ```yaml
  - id: check_gold
    action: conditional
    condition: "{membership} = gold"
    then:
      steps: [...]
    else:
      steps: [...]
  ```

### 4. `fetch_with_condition`
Combines `fetch` and `conditional`.
- `field`: Field to fetch.
- `condition`: Condition evaluated AFTER fetching.
- `then` / `else`: Branching steps.

### 5. `use_tool`
Call a backend tool.
- `tool_name`: Name of the tool.
- `input`: List of arguments (supports `{{ var }}`).
- `set_variables`: (Optional) List of fields to extract from tool output.
- `filter`: (Optional) List of filter objects (`field`, `operator`, `value`).

### 6. `reply`
Send a final message to the user (stops execution of the current flow path).
- `message`: Text to send.

### 7. `use_subworkflow`
Jump to a subworkflow.
- `subworkflow`: Name of the subworkflow to call.

### 8. `set_variable`
Manually set a variable.
- `variable`: Name of the variable.
- `value`: Value to set (can use `{{ var }}`).

## Logic & Template Rules
- **Interpolation**: Use `{{ variable_name }}` to insert variable values into strings.
- **Conditions**: Use `{variable_name}` inside condition strings.
- **Operators**: `=`, `!=`, `>`, `<`, `>=`, `<=`, `contains`, `not contains`.
- **Natural Language**: Conditions can also be natural language strings which the LLM will evaluate.
