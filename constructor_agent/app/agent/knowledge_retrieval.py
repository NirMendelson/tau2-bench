import os

# Read knowledge from the markdown files in the knowledge directory
def read_knowledge(topic: str) -> str:
    base_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "knowledge")
    
    if topic == "rules":
        file_path = os.path.join(base_path, "cspl-rules.md")
    elif topic == "examples":
        file_path = os.path.join(base_path, "cspl-examples.md")
    else:
        # Check if it's a specific action request
        rules_path = os.path.join(base_path, "cspl-rules.md")
        if os.path.exists(rules_path):
            with open(rules_path, 'r') as f:
                content = f.read()
                # Simple extraction of action section
                if f"### {topic}" in content:
                    sections = content.split("### ")
                    for s in sections:
                        if s.startswith(topic):
                            return "### " + s
        return f"Error: Topic '{topic}' not found."

    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            return f.read()
    return f"Error: Knowledge file for '{topic}' not found."
