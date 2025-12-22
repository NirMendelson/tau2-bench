import yaml
from typing import Dict, List, Any


def load_workflows(path: str) -> Dict[str, Dict[str, Any]]:
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split by '---' separator to get individual workflows
    workflow_sections = content.split('---')
    
    workflows = {}
    
    for section in workflow_sections:
        section = section.strip()
        if not section:
            continue
        
        # Skip sections that are ONLY comments (no actual content)
        # But allow sections that have comments followed by YAML content
        lines = [line.strip() for line in section.split('\n') if line.strip()]
        if not lines or all(line.startswith('#') for line in lines):
            continue
        
        try:
            workflow_data = yaml.safe_load(section)
            if workflow_data:
                workflow_name = workflow_data.get('workflow') or workflow_data.get('subworkflow')
                if workflow_name:
                    workflows[workflow_name] = workflow_data
        except yaml.YAMLError as e:
            print(f"error parsing workflow section: {e}")
            continue
    
    return workflows


def load_constants(path: str) -> Dict[str, Any]:
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def load_tools(path: str) -> Dict[str, Any]:
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


if __name__ == "__main__":
    # Test parsing
    workflows = load_workflows("../codebase/workflow.yaml")
    print(f"loaded {len(workflows)} workflows")
    for name in list(workflows.keys())[:3]:
        print(f"  - {name}")

