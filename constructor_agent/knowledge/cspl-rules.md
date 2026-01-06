# CSPL (Customer Service Process Language) Rules

CSPL consists of three YAML files that work together to define an AI agent's behavior:

1. **`workflow.yaml`** - The complex file containing business logic, workflows, and step-by-step processes
2. **`constants.yaml`** - Simple key-value pairs for constants and default prerequisites
3. **`tone.yaml`** - Short instructions for communication style and personality

The agent processes these files in order: first tone (how to communicate), then constants (what to always know), then workflow (what to do).

---

## 1. workflow.yaml - Main File

This is the main file containing all workflows and business logic. It defines step-by-step processes that the agent follows.

### General Structure
- A file contains multiple workflows/subworkflows separated by `---`.
- there should be one line of space between each step (for easy reading)
- Each workflow is a **list of objects**.
- The **first object** in the list defines the workflow metadata:
  - **Main Workflow**: `workflow: Name`.
  - **Subworkflow**: `subworkflow: Name`.
  - Both must have `when: "description of when to use"`.
- The **subsequent objects** in the list are the steps that define the process.

### Step Fields

Each step in a workflow MUST have:
- `id`: Unique identifier for the step (must be unique within the workflow).
- `action`: The type of action to perform (see Actions section below).

Each step MAY have:
- `comment`: (Optional) Additional context, rules, or instructions that go directly into the LLM prompt. Use this to provide domain-specific guidance or constraints for the step.

### Actions

Actions define what the agent does at each step. Each action has specific required and optional fields.

### 1. `fetch`
Used to get user information. Will check if it has the information in the conversation and if not will ask for it.
- `field`: Name of the variable(s) to store. Can be either:
  - A single string: `field: user_id` (for one variable)
  - A list: `field: [user_id, baggage_action]` (for multiple variables)
- **Examples**:
  ```yaml
  # Single field
  - id: get_user
    action: fetch
    field: user_id
  
  # Multiple fields
  - id: get_user_and_action
    action: fetch
    field: [user_id, baggage_action]
  ```

### 2. `fetch_with_message`
Used to get user input and show a SPECIFIC message before getting it. if the message is not specific, fetch with a comment field is a better option.
- `field`: Variable(s) to store input. Can be either:
  - A single string: `field: wants_insurance` (for one variable)
  - A list: `field: [origin, destination]` (for multiple variables)
- `message`: The text to show the user.
- **Examples**:
  ```yaml
  # Single field
  - id: ask_insurance
    action: fetch_with_message
    field: wants_insurance
    message: "Would you like travel insurance?"
  
  # Multiple fields
  - id: ask_flight_details
    action: fetch_with_message
    field: [origin, destination]
    message: "Please provide your origin and destination airports."
  ```

### 3. `conditional`
Used when we need to check a condition and execute different steps based on it.
- `condition`: String condition (e.g., `"{age} > 18"` or `"{name} = John"`).
- `then`: List of steps to execute if true.
- `else`: List of steps to execute if false.
- **Example**:
  ```yaml
  - id: check_gold
    action: conditional
    condition: "{membership} = gold"
    then:
      - id: apply_discount
        action: ...
    else:
      - id: show_regular_price
        action: ...
  ```

### 4. `fetch_with_condition`
Combines `fetch` and `conditional`, Fetching and then checking a condition.
- `field`: Field to fetch.
- `condition`: Condition evaluated AFTER fetching.
- `then` / `else`: List of branching steps.
- **Example**:
  ```yaml
  - id: check_gold
    action: fetch_with_condition
    field: membership
    condition: "{membership} = gold"
    then:
      - id: ...
    else:
      - id: ...
  ```

### 5. `use_tool`
Call a backend tool. 
- `tool_name`: Name of the tool.
- `input`: **MUST be an inline list** `["{{ var }}", "{{ vars }}"]`. NEVER use multiline format like `input:\n  - '{{ var }}'`.
- `set_variable`: (Optional) Field(s) to extract from tool output. Can be:
  - A single string: `set_variable: variable_name` (extracts `variable_name` from tool result)
  - A list: `set_variable: [var1, var2]` (extracts multiple fields)
  - Renaming format: `set_variable: new_name: original_name` (extracts `original_name` and stores as `new_name`)
  - List with renaming: `set_variable: [new1: orig1, new2: orig2]` (multiple renames)
- If not specified, the tool result will be stored as `{tool_name}_result`.
- **Examples**:
  ```yaml
  # Extract multiple fields with same names
  - id: get_reservation_details
    action: use_tool
    tool_name: get_reservation_details
    input: ["{{ reservation_id }}"]
    set_variable: [total_baggages, nonfree_baggages, cabin, passengers]
  
  # Rename a field
  - id: get_user_reservations
    action: use_tool
    tool_name: get_user_details
    input: ["{{ user_id }}"]
    set_variable: reservations_list: reservations
  
  # Single field
  - id: get_cabin
    action: use_tool
    tool_name: get_reservation_details
    input: ["{{ reservation_id }}"]
    set_variable: cabin
  ```

### 6. `reply`
Send a message to the user.
- `message`: Text to send.
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

### 9. `instruction`
Used when you need the LLM to perform complex logic, calculations, data processing, or other tasks that cannot be easily expressed with other action types. The LLM will execute the instruction and set variables based on the result.
- `instruction`: Required. Text instructions describing what the LLM should do. Can be multi-line using `|`.
- `set_variable`: (Optional) Variable(s) to set from the instruction result. Can be:
  - A single string: `set_variable: variable_name` (stores entire result as `variable_name`)
  - A list: `set_variable: [var1, var2]` (if result is a dict, extracts these keys)
  - Renaming format: `set_variable: new_name: original_name` (extracts `original_name` from result dict and stores as `new_name`)
- **Examples**:
  ```yaml
  # Single variable (stores entire result)
  - id: calculate_total_price
    action: instruction
    instruction: |
      you need to calculate the total price the user needs to pay for the reservation.
      1. find what cabin the user wants to book.
      2. sum the price of each flight in flight results BY CABIN.
      3. multiple the price by number of passengers

      Return the total price.
    set_variable: total_price
  
  # Multiple variables (if result is a dict)
  - id: extract_flight_info
    action: instruction
    instruction: Extract flight numbers and dates from the reservation.
    set_variable: [flight_numbers, flight_dates]
  ```

### Logic & Template Rules
- **Interpolation**: Use `{{ variable_name }}` to insert variable values into strings (e.g., in `message` or `input` fields).
- **Conditions**: Use `{variable_name}` inside condition strings (single braces, no spaces around variable name).
- **Operators**: `=`, `!=`, `>`, `<`, `>=`, `<=`, `contains`, `not contains`.
- **Natural Language**: Conditions can also be natural language strings which the LLM will evaluate (e.g., `"user is a premium member"`).

### CRITICAL RULES
- The `field` property can be either a single string or a list of strings. Always use `field` (not `fields`).
  - Single field: `field: user_id`
  - Multiple fields: `field: [user_id, baggage_action]`
- The `set_variable` property can be a string, list, or use renaming format. Always use `set_variable` (not `set_variables`).
  - Single variable: `set_variable: variable_name`
  - Multiple variables: `set_variable: [var1, var2, var3]`
  - Rename single: `set_variable: new_name: original_name` (extracts `original_name` from tool result and stores as `new_name`)
  - Rename multiple: `set_variable: [new1: orig1, new2: orig2]` (multiple renames)
- If `use_tool` doesn't have `set_variable`, the entire result will be stored as `{tool_name}_result`.
- If `use_tool` has `set_variable`, make sure you use the SAME names as the field names the tool returns (unless you're using the renaming format).
---

## 2. constants.yaml - Global Constants and Default Prerequisites

This file contains simple key-value pairs that apply globally across all workflows.

### Structure
- Simple YAML key-value pairs (no nested structures).
- Keys are variable names that will be available in all workflows.
- Values can be strings, numbers, or lists.

### Types of Constants

#### Time-Based Constants
These represent current date/time that the agent should use:
```yaml
now_date: 2024-05-15
now_time: 15:00:00 EST
```

#### Default Prerequisites
These are fields that the agent **always** needs to ask for before answering anything, regardless of which workflow is active. These are typically user identification or authentication fields that must be collected first:
```yaml
default_prerequisites:
  - user_id
  - account_number
```

**Important**: Default prerequisites are fetched automatically at the start of every conversation, before any workflow begins. They ensure the agent always has essential information before proceeding.

---

## 3. tone.yaml - Communication Style

This file defines how the agent communicates with users. It should be **short and concise** - these instructions are inserted into every prompt, so brevity is important.

### Structure
```yaml
identity:
  role: "AI assistant providing support for the airline domain"

tone: "Be polite, friendly, and use emojis when appropriate 😊"

guidelines:
  - "Before taking any actions that update the database, you must list the action details and obtain explicit user confirmation (yes) to proceed."
  - "You should not provide any information, knowledge, or procedures not provided by the user or available tools."
  - "You should only make one tool call at a time."
```

### Fields

- **`identity.role`**: A brief description of the agent's role and domain expertise.
- **`tone`**: Short instructions on communication style (e.g., "Be polite", "Use emojis", "Be concise"). Keep this to 1-2 sentences.
- **`guidelines`**: A list of behavioral rules that apply to all interactions. These are inserted into every LLM prompt to ensure consistent behavior across all workflows.

**Key Principle**: Tone should be **short** because it's prepended to every workflow prompt. The workflow file contains the complex logic; tone just sets the communication style.

---

## Critical Rules
- only use fetch_with_message if you need to show a SPECIFIC message, fetch on default send a message if it doesn't have the information.
- you can set name of a variable with this syntax (for example, if the instruction is use get_payment to get payment id and name it payment) 

  - id: get_payment
    action: use_tool
    tool_name: get_payment
    input: ['{{ payment_id }}']
    set_variable: payment: payment_id

- `else` blocks are OPTIONAL. If no `else` block is provided, execution continues to the next sequential step. Only add an `else` block if you need different logic than what follows naturally

## DO NOT DO
- else: []