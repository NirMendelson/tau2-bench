# How CSPL Works: A Simple Explanation

This document explains how CSPL (Codebase Structured Prompt Language) works in simple terms. CSPL converts instructions into a structured codebase that an AI agent can follow.

## Overview

CSPL is a system that turns natural language instructions into executable workflows. Think of it like:
- **Instructions** = A recipe book (what to do)
- **Codebase** = The organized recipe book with clear steps
- **Agent** = The chef who follows the recipes

Instead of giving the AI agent a long, confusing instruction document, CSPL organizes everything into clear, structured files that the agent can easily understand and follow.

## The Four Configuration Files

CSPL uses **4 YAML files** in the `codebase/` folder to define how the system works:

### 1. `workflow.yaml` - The Main Recipe Book

**What it is:** This file contains all the workflows (recipes) that tell the agent what to do in different situations.

**What it contains:**
- Multiple workflows, each separated by `---`
- Each workflow has:
  - `workflow`: A unique name (e.g., "CheckAdventureSportsAvailability")
  - `when`: Description of when this workflow should be used
  - `keywords`: 3-8 important words for finding this workflow (used for keyword search)
  - `examples`: 3-8 example user questions that match this workflow (used for semantic search)
  - `steps`: The actual steps to execute (like a recipe)

**Example:**
```yaml
workflow: CheckAdventureSportsAvailability
when: "customer asks specifically about Adventure Sports add-on"

keywords:
  - extreme
  - adventure
  - sports

examples:
  - "Do you offer adventure sports coverage?"
  - "Is the adventure sports add-on available?"

steps:
  - id: check_restriction
    action: conditional
    condition:
      operator: in
      left: "{{ state }}"
      right: ["Washington", "Missouri"]
    then:
      action: reply
      message: "I'm sorry, but the Adventure Sports add-on is not available in your state."
    else:
      action: reply
      message: "The Adventure Sports add-on is available! Would you like to add it?"
```

**How it's used:**
- When a user asks a question, the agent searches through all workflows
- It matches the user's question to the best workflow using keywords and examples
- Then it executes the steps in that workflow one by one

### 2. `tools.yaml` - Reusable Tools

**What it is:** This file defines reusable tools (like helper functions) that workflows can call.

**What it contains:**
- `global_tools`: Tools available to all workflows
  - Each tool has:
    - `tool`: Tool name
    - `description`: What the tool does
    - `steps`: Optional mini-workflow to execute
    - `params`: Required parameters
- `custom_tools`: Customer-specific tools (optional)

**Example:**
```yaml
global_tools:
  - tool: escalation
    description: "sends the ticket to a human agent"
    steps:
      - id: fetch_email
        action: fetch
        field: email
      - id: fetch_full_name
        action: fetch
        field: full_name
    params:
      - reason
      - reply_message
```

**How it's used:**
- Workflows can call these tools when needed
- For example, if a workflow needs to escalate to a human, it can call the `escalation` tool
- Tools can have their own steps, so they're like mini-workflows

### 3. `tone.yaml` - Personality Settings

**What it is:** This file defines how the AI assistant should communicate - its personality and style.

**What it contains:**
- `identity`: The role and positioning of the assistant
- `tone`: List of tone characteristics (e.g., "warm, conversational")
- `guidelines`: Rules for how the assistant should communicate

**Example:**
```yaml
identity:
  role: AI assistant providing support
  positioning: friendly, helpful companion who's always ready to assist
tone:
  - warm, conversational while maintaining professionalism
  - clear and professional, avoiding slang and jargon
  - genuine empathy, especially during stressful situations
guidelines:
  - only provide information from approved responses
  - use bulleted lists or short paragraphs
  - add relevant emojis sparingly
```

**How it's used:**
- When the agent generates a reply to the user, it uses these tone guidelines
- This ensures all responses have a consistent personality and style
- It's like giving the agent a "communication style guide"

### 4. `constants.yaml` - Default Values

**What it is:** This file contains default values and system-wide settings.

**What it contains:**
- `default_reply_message`: Default message for escalations
- `default_opening_line`: Default greeting
- `default_closing_line`: Default closing
- `default_prerequisites`: Fields automatically fetched before workflows run

**Example:**
```yaml
default_reply_message: "I'm forwarding your request to a human agent"
default_opening_line: ""
default_closing_line: ""

default_prerequisites:
  - state  # user's home state - always available
```

**How it's used:**
- These are fallback values used when specific values aren't provided
- `default_prerequisites` are fields that are automatically fetched before any workflow runs
- This ensures the agent always has certain information available (like the user's state)

## The Three Nodes (The Agent's Brain)

The agent itself is built using **3 nodes** that work together to process user messages:

### 1. LoadBenchmarkNode - Get the User's Question

**What it does:** Takes the user's input and prepares it for processing.

**How it works:**
1. Reads the user's input from the shared store
2. Creates the initial conversation history with the user's message
3. Passes control to the next node

**Simple explanation:**
- This is like the receptionist who takes your question and writes it down
- It prepares everything so the next step can figure out what to do

**Code flow:**
```
User input: "Do you offer adventure sports coverage?"
  ↓
LoadBenchmarkNode creates:
  conversation_history = [
    {"role": "user", "content": "Do you offer adventure sports coverage?"}
  ]
  ↓
Passes to MatchWorkflowNode
```

### 2. MatchWorkflowNode - Find the Right Recipe

**What it does:** Matches the user's question to the best workflow from `workflow.yaml`.

**How it works:**
1. Takes the user's input and all available workflows
2. Uses two types of matching:
   - **Keyword matching (BM25)**: Searches for keywords from workflow definitions
   - **Semantic matching**: Uses AI to understand the meaning and find similar examples
3. If multiple workflows match, uses an LLM to score them and pick the best one
4. If confidence is too low, asks the user for clarification
5. Stores the selected workflow in the shared store

**Simple explanation:**
- This is like a librarian who finds the right book (workflow) for your question
- It searches through all the workflows and picks the one that best matches what you're asking

**Code flow:**
```
User input: "Do you offer adventure sports coverage?"
  ↓
MatchWorkflowNode searches workflows:
  - Keyword match: finds "adventure", "sports" in keywords
  - Semantic match: finds similar examples
  ↓
Finds: "CheckAdventureSportsAvailability" workflow
  ↓
Stores in shared store:
  selected_workflow = {
    "name": "CheckAdventureSportsAvailability",
    "definition": {...workflow steps...}
  }
  ↓
Passes to ExecuteWorkflowNode
```

### 3. ExecuteWorkflowNode - Follow the Recipe

**What it does:** Executes the steps in the selected workflow one by one.

**How it works:**
1. Gets the selected workflow and current step from shared store
2. Executes the current step (could be: fetch, conditional, reply, use_tool, include)
3. Updates the conversation history with any replies
4. Moves to the next step
5. Can loop back to itself to continue executing steps
6. Stops when the workflow is complete

**Simple explanation:**
- This is like the chef who actually follows the recipe (workflow)
- It does each step: check conditions, fetch information, send replies, etc.
- It keeps going until the recipe is complete

**Code flow:**
```
Selected workflow: "CheckAdventureSportsAvailability"
Current step: check_restriction (conditional)
  ↓
ExecuteWorkflowNode:
  1. Checks condition: Is state in ["Washington", "Missouri"]?
  2. If yes → reply: "Not available in your state"
  3. If no → reply: "Available! Would you like to add it?"
  ↓
Workflow complete!
  ↓
Updates conversation_history with reply
```

## How Everything Works Together

Here's the complete flow when a user asks a question:

```
1. USER ASKS QUESTION
   "Do you offer adventure sports coverage?"
   
2. LoadBenchmarkNode
   - Takes user input
   - Creates conversation_history
   - Passes to next node
   
3. MatchWorkflowNode
   - Searches all workflows in workflow.yaml
   - Uses keyword + semantic matching
   - Finds "CheckAdventureSportsAvailability"
   - Stores selected workflow
   - Passes to next node
   
4. ExecuteWorkflowNode
   - Gets the workflow steps
   - Executes step 1: check_restriction (conditional)
     - Checks if state is in restricted list
   - Executes step 2: reply (based on condition)
     - Generates reply using tone.yaml guidelines
     - Adds reply to conversation_history
   - Workflow complete!
   
5. RESULT
   - Conversation history contains:
     - User: "Do you offer adventure sports coverage?"
     - Assistant: "The Adventure Sports add-on is available! Would you like to add it?"
```

## Key Concepts

### Workflow Steps

Workflows can have different types of steps:
- **`fetch`**: Get a field from the system (e.g., user's email, state)
- **`fetch_with_condition`**: Get a field with conditional logic
- **`conditional`**: Branch based on a condition (if/then/else)
- **`reply`**: Send a message to the user (uses tone.yaml for style)
- **`include`**: Include another workflow or set of steps
- **`use_tool`**: Call a tool from tools.yaml

### Variables

Workflows use `{{ variable_name }}` syntax for variables:
- Example: `{{ state }}` gets the user's state
- Variables can come from:
  - Fetched fields
  - Extracted information from conversation
  - Default prerequisites

### Matching Strategy

The agent uses a two-stage matching process:
1. **Fast matching**: Keyword (BM25) + Semantic search to find candidates
2. **Smart selection**: If multiple matches, LLM scores them to pick the best one
3. **Clarification**: If confidence is too low, asks user to clarify

## Summary

- **4 Files**: `workflow.yaml` (recipes), `tools.yaml` (helpers), `tone.yaml` (personality), `constants.yaml` (defaults)
- **3 Nodes**: `LoadBenchmarkNode` (get question), `MatchWorkflowNode` (find recipe), `ExecuteWorkflowNode` (follow recipe)

The system converts instructions into structured workflows, then the agent matches user questions to workflows and executes them step by step, all while maintaining a consistent personality and style!

