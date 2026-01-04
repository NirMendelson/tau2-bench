from typing import List, Dict, Any

# Generates natural language explanations of changes for non-technical users
class ExplanationGenerator:
    # Main entry point to summarize all proposed changes in plain English
    def generate_explanation(self, change_set: List[Dict[str, Any]]) -> str:
        if not change_set:
            return "I've analyzed the request, and no changes are needed right now."

        # Collect unique descriptions of what was done
        summaries = []
        
        # Filter changes to unique high-level actions
        workflow_count = len([c for c in change_set if c["file"] == "workflow.yaml"])
        constant_count = len([c for c in change_set if c["file"] == "constants.yaml"])
        tone_count = len([c for c in change_set if c["file"] == "tone.yaml"])

        # Try to find a human-readable reason from the change set
        reasons = [c.get("reason") for c in change_set if c.get("reason")]
        main_reason = reasons[0] if reasons else "updated the logic to match your request"

        if workflow_count > 0:
            summaries.append(f"I've updated the workflow logic ({main_reason}).")
        if constant_count > 0:
            summaries.append("I've also updated some global settings.")
        if tone_count > 0:
            summaries.append("I've adjusted my personality and tone as requested.")

        summary_text = " ".join(summaries)
        return f"Sure! {summary_text} Would you like to approve these changes?"

    # Helper methods are now simplified or removed as the top-level method is concise enough
