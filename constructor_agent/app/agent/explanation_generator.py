from typing import List, Dict, Any

# Generates natural language explanations of changes for non-technical users
class ExplanationGenerator:
    # Main entry point to summarize all proposed changes in plain English
    def generate_explanation(self, change_set: List[Dict[str, Any]]) -> str:
        if not change_set:
            return "I've analyzed the request but no changes were necessary."

        sections = []
        
        # Group by file type
        workflows = [c for c in change_set if c["file"] == "workflow.yaml"]
        constants = [c for c in change_set if c["file"] == "constants.yaml"]
        tone = [c for c in change_set if c["file"] == "tone.yaml"]

        if workflows:
            sections.append(self._explain_workflow_changes(workflows))
        if constants:
            sections.append(self._explain_constants_changes(constants))
        if tone:
            sections.append(self._explain_tone_changes(tone))

        header = "I've planned the following changes to achieve your goal:\n\n"
        footer = "\n\nWould you like me to apply these changes?"
        return header + "\n\n".join(sections) + footer

    # Explain modifications to workflows and steps
    def _explain_workflow_changes(self, changes: List[Dict[str, Any]]) -> str:
        lines = ["**Workflows**"]
        for c in changes:
            wf_name = c.get("workflow", "Unknown")
            action = c.get("type")
            step_id = c.get("step_id", "new step")
            reason = c.get("reason", "")
            
            if action == "insert":
                lines.append(f"- Add a new step '{step_id}' to the '{wf_name}' workflow. {reason}")
            elif action == "modify":
                lines.append(f"- Update the calculation or logic in the '{step_id}' step of the '{wf_name}' workflow. {reason}")
            elif action == "delete":
                lines.append(f"- Remove the '{step_id}' step from the '{wf_name}' workflow as it is no longer needed.")
        return "\n".join(lines)

    # Explain updates to global configuration settings
    def _explain_constants_changes(self, changes: List[Dict[str, Any]]) -> str:
        lines = ["**Configuration & Prerequisites**"]
        for c in changes:
            key = c.get("key")
            ctype = c.get("type")
            if "prerequisite" in ctype:
                lines.append(f"- Ensure the agent always asks for '{key}' before starting a conversation.")
            else:
                lines.append(f"- Update global setting for '{key}'.")
        return "\n".join(lines)

    # Explain updates to agent personality and guidelines
    def _explain_tone_changes(self, changes: List[Dict[str, Any]]) -> str:
        lines = ["**Tone & Personality**"]
        for c in changes:
            ctype = c.get("type")
            if ctype == "set_role":
                lines.append(f"- Update the agent's professional identity/role.")
            elif ctype == "set_tone":
                lines.append(f"- Adjust how the agent speaks to be more aligned with your instructions.")
            elif ctype == "add_guideline":
                lines.append(f"- Add a new behavioral rule to ensure consistent service.")
        return "\n".join(lines)
