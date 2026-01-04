# Constructor Agent — Functionalities & Principles

## Purpose
Constructor Agent allows non-technical users to **change an AI agent’s behavior** using plain language.
The experience is similar to Cursor / Antigravity, but instead of general code, it operates on a **small, controlled YAML codebase**.

The agent translates conversational instructions into safe, structured updates to:
- `workflow.yaml` — business logic and flows (custom syntax)
- `constants.yaml` — fixed facts and global rules (date, time, default prerequisites)
- `tone.yaml` — communication style and personality rules

---

## Product Vision
A user can describe behavior in natural language, have a short back-and-forth conversation to refine intent, approve a clear plan, and then let the agent update the YAML files correctly.

No YAML knowledge required.
No silent changes.
No surprises.

---

## Scope
### Editable Files (Only)
- **workflow.yaml**  
  Defines workflows, conditions, branching, escalation, and step order.
- **constants.yaml**  
  Holds global constants and rules that apply everywhere (e.g. always-ask questions, default prerequisites).
- **tone.yaml**  
  Defines how the agent speaks (politeness, emojis, brevity, style).

The agent must not modify anything outside these files.

---

## Core User Flow

### 1. User Prompt
The user writes a natural-language instruction in the web app.

Example:  
> “If the user wants to buy shoes, first ask for size and gender. If it’s male, escalate.”

---

### 2. Intent Understanding
The agent identifies:
- This is a **workflow change**
- Which file(s) are likely affected
- Whether this is a new workflow or a modification of an existing one

The agent explicitly states its understanding.

---

### 3. Clarification (If Needed)
If something is unclear or incomplete, the agent asks **targeted clarification questions**.

Examples:
- “What should happen if the user is female?”
- “What does ‘escalate’ mean in this case?”

The agent does **not** guess silently.

---

### 4. Proposal
Once intent is clear, the agent presents:
- What it will change
- Which files will be updated
- A human-readable explanation of the new behavior
- A clear summary of additions, updates, or removals

This is a **preview**, not execution.

---

### 5. Approval Gate
The user can:
- Approve
- Ask for changes
- Cancel

No changes are applied without approval.

---

### 6. Apply Changes
After approval, the agent:
- Updates the relevant YAML files
- Makes only the necessary edits
- Preserves unrelated content

---

### 7. Confirmation
The agent confirms:
- What changed
- Where it changed (file + workflow/section)
- What behavior is now expected

---

## Conversation-Driven Editing
- The interaction is **iterative**, not one-shot
- Each user message can refine, extend, or correct previous intent
- The agent maintains context across the conversation
- Multiple clarification → proposal → approval cycles are expected

This should feel like **pair-editing behavior**, not form-filling.

---

## Change Types the Agent Must Handle
- Create a new workflow
- Modify an existing workflow
- Add or update global prerequisites
- Adjust tone rules
- Apply multiple coordinated changes from a single prompt

---

## Safety & Control Rules
- No automatic changes
- No guessing missing logic
- No rewriting unrelated YAML
- Always explain before acting
- Always confirm after acting

---

## Web App Responsibilities
- Prompt input and conversation history
- Clear display of proposed changes
- Simple approval controls
- Visibility into current file contents (read-only until approved)

---

## Agent Responsibilities
- Understand user intent in context
- Know the YAML structure and rules
- Ask good clarification questions
- Generate valid, consistent YAML
- Apply multiple related edits when required
- Keep changes minimal and readable

---

## Example Outcome
After approval, the system correctly adds or updates a workflow that:
- Detects shoe-purchase intent
- Asks size and gender
- Routes male users to escalation
- Handles female users according to clarified rules
- Obeys global prerequisites and tone rules

---

## Core Principles

### 1. YAML-Aware by Design
The agent **must understand the YAML syntax and structure** deeply.
It should know what is valid, what is required, and what patterns already exist.
This is not free-form text generation — it is structured behavior editing.

---

### 2. Conversation Is the Interface
Changes are created through **dialog**, not commands.
The agent refines intent through questions and feedback, just like Cursor or Antigravity.
Understanding evolves across turns.

---

### 3. One Prompt → Multiple Edits
A single user instruction may require:
- Several workflow changes
- Updates to constants
- Alignment with tone rules

The agent must coordinate **multiple edits as one logical change**, and present them as such.

---

## Definition of “Done”
- User intent is clearly understood
- Changes are reviewed and approved
- YAML files are updated correctly
- Resulting behavior matches expectations
- User never touched YAML