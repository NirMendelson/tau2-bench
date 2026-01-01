import litellm
import os
import json
from typing import List, Dict, Any, Tuple
from constructor_agent.app.processor import WorkflowProcessor
from constructor_agent.app.validator import WorkflowValidator

PROMPT_TEMPLATE = """You are a Workflow Construction Agent (Constructor Agent). Your goal is to edit a `workflow.yaml` file based on a tenant's instructions.

The system uses CSPL (Customer Service Process Language). You MUST adhere to the rules defined below.

### CSPL RULES:
{cspl_rules}

### CURRENT WORKFLOW STATE:
{current_workflows}

### TENANT INSTRUCTIONS:
{user_instruction}

### YOUR TASK:
1. Analyze the user's request.
2. If the request is unclear, ask clarification questions.
3. If clear, explain what you are going to change in natural language.
4. Provide the exact YAML changes needed.

### OUTPUT FORMAT:
Your response MUST be a YAML object with the following fields:
- `clarification`: (String) A question if you are unsure, otherwise null.
- `explanation`: (String) Natural language explanation of the changes you plan to make.
- `edits`: (List of Objects) Each object represents a change to a workflow or subworkflow:
    - `name`: The name of the workflow or subworkflow to edit.
    - `new_content`: (Object) The FULL new content of that workflow/subworkflow doc.

If you are asking a clarification question, `explanation` and `edits` should be null.

Example:
```yaml
clarification: null
explanation: "I will add a check for reservation ID during flight cancellation. If missing, I'll use the escalation tool."
edits:
  - name: "CancelFlight"
    new_content:
      workflow: "CancelFlight"
      when: "user wants to cancel..."
      steps:
        - id: ...
          ...
```
"""

class ConstructorAgent:
    def __init__(self, workflow_path: str, rules_path: str, model: str = "gpt-4o"):
        self.processor = WorkflowProcessor(workflow_path)
        self.validator = WorkflowValidator(workflow_path)
        self.rules_path = rules_path
        self.model = model
        
        with open(rules_path, 'r') as f:
            self.rules = f.read()

    def _get_current_state_summary(self) -> str:
        self.processor.load()
        summary = "Available workflows/subworkflows:\n"
        for name in self.processor.list_workflows():
            summary += f"- {name}\n"
        return summary

    def process_request(self, user_instruction: str) -> Dict[str, Any]:
        """Process user instruction and return proposed changes or clarification."""
        current_state = self._get_current_state_summary()
        
        prompt = PROMPT_TEMPLATE.format(
            cspl_rules=self.rules,
            current_workflows=current_state,
            user_instruction=user_instruction
        )

        response = litellm.completion(
            model=self.model,
            messages=[{"role": "user", "content": prompt}]
        )
        
        content = response.choices[0].message.content
        return self._parse_response(content)

    def _parse_response(self, content: str) -> Dict[str, Any]:
        """Parse the LLM response (handling potential markdown blocks)."""
        import yaml
        # Remove markdown blocks if present
        if content.strip().startswith("```"):
            lines = content.strip().split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines[-1].strip() == "```":
                lines = lines[:-1]
            content = "\n".join(lines)
            
        try:
            return yaml.safe_load(content)
        except Exception as e:
            return {
                "clarification": f"Error parsing my own internal response: {str(e)}",
                "explanation": None,
                "edits": None
            }

    def apply_edits(self, edits: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
        """Apply the proposed edits and validate."""
        # We should reload to ensure we have the latest
        self.processor.load()
        
        for edit in edits:
            name = edit['name']
            new_content = edit['new_content']
            self.processor.update_document(name, new_content)
            
        # Save to temp or directly? Requirement says "then the agent will do the changes" after approval.
        # But we should validate FIRST.
        
        # For now, let's save and then validate. We can always revert if the processor keeps a backup (not yet implemented).
        self.processor.save()
        
        errors = self.validator.validate()
        if errors:
            return False, errors
        return True, []
