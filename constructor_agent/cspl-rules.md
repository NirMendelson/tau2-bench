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
Used to get user information. Will check if it has the information in the conversation and if not will ask for it.
- `field`: Name of the variable to store (e.g., `user_id`).
- `fields`: (Alternative) List of variables to store.
- 'comment': (Optional) comment to enter the prompt, can be additional rules or instructions.
- **Example**:
  ```yaml
  - id: get_user
    action: fetch
    field: user_id
  ```

### 2. `fetch_with_message`
Used to get user input and show a SPECIFIC message before getting it. 
- `field`: Variable to store input.
- `message`: The text to show the user.
- 'comment': (Optional) comment to enter the prompt, can be additional rules or instructions.
- **Example**:
  ```yaml
  - id: ask_insurance
    action: fetch_with_message
    field: wants_insurance
    message: "Would you like travel insurance?"
  ```

### 3. `conditional`
Used when we need to check a condition and execute different steps based on it.
- `condition`: String condition (e.g., `"{age} > 18"` or `"{name} = John"`).
- `then`: Steps to execute if true.
- `else`: Steps to execute if false.
- 'comment': (Optional) comment to enter the prompt, can be additional rules or instructions.
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
Combines `fetch` and `conditional`, Fetching and then checking a condition.
- `field`: Field to fetch.
- `condition`: Condition evaluated AFTER fetching.
- `then` / `else`: Branching steps.
- 'comment': (Optional) comment to enter the prompt, can be additional rules or instructions.
- **Example**:
  ```yaml
  - id: check_gold
    action: fetch_with_condition
    field: membership
    condition: "{membership} = gold"
    then:
      steps: [...]
    else:
      steps: [...]
  ```

### 5. `use_tool`
Call a backend tool. 
- `tool_name`: Name of the tool.
- `input`: List of arguments ["{{ var }}", "{{ vars }}"].
- `set_variables`: (Optional) List of fields to extract from tool output. If not specified, we will set all of the variables the tool returns.
- **Example**:
  ```yaml
    - id: get_reservation_details
      action: use_tool
      tool_name: get_reservation_details
      input: ["{{ origin }}", "{{ destination }}", "{{ date }}"]
      set_variables:
        - total_baggages
        - nonfree_baggages
        - cabin
        - passengers
  ```

### 6. `reply`
Send a message to the user .
- `message`: Text to send.
- 'comment': (Optional) comment to enter the prompt, can be additional rules or instructions.
- **Example**:
  ```yaml
    - id: inform_max_passengers
      action: reply
      message: "Each reservation can have at most five passengers. "
  ```

### 7. `use_subworkflow`
Jump to a subworkflow.
- `subworkflow`: Name of the subworkflow to call.
- **Example**:
  ```yaml
    - id: calculate_free_bags
      action: use_subworkflow
      subworkflow: GivingCheckedBagInformation
  ```
### 8. `set_variable`
Manually set a variable.
- `variable`: Name of the variable.
- `value`: Value to set (can use `{{ var }}`).
- **Example**:
  ```yaml
    - id: set_free_bags
      action: set_variable
      variable: free_checked_bags_per_passenger
      value: 0
  ```

## Logic & Template Rules
- **Interpolation**: Use `{{ variable_name }}` to insert variable values into strings.
- **Conditions**: Use `{variable_name}` inside condition strings.
- **Operators**: `=`, `!=`, `>`, `<`, `>=`, `<=`, `contains`, `not contains`.
- **Natural Language**: Conditions can also be natural language strings which the LLM will evaluate.

## Critical
- id is distint inside the same workflow
- only use fetch_with_message if you need to show a SPECIFIC message, fetch on default send a message if it doesn't have the information.
