from ruamel.yaml import YAML
from typing import List, Any
import os

class WorkflowProcessor:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.yaml = YAML()
        self.yaml.preserve_quotes = True
        self.yaml.indent(mapping=2, sequence=4, offset=2)
        self.documents = []

    def load(self):
        """Load all documents from the yaml file."""
        with open(self.file_path, 'r') as f:
            self.documents = [doc for doc in self.yaml.load_all(f) if doc is not None]
        return self.documents

    def save(self):
        """Save all documents back to the yaml file."""
        with open(self.file_path, 'w') as f:
            self.yaml.dump_all(self.documents, f)

    def get_document_by_name(self, name: str):
        """Find a workflow or subworkflow by its name."""
        for doc in self.documents:
            if isinstance(doc, dict) and (doc.get('workflow') == name or doc.get('subworkflow') == name):
                return doc
        return None

    def list_workflows(self) -> List[str]:
        """List all workflow and subworkflow names."""
        names = []
        for doc in self.documents:
            if not isinstance(doc, dict):
                continue
            if 'workflow' in doc:
                names.append(doc['workflow'])
            elif 'subworkflow' in doc:
                names.append(doc['subworkflow'])
        return names

    def get_full_content(self) -> str:
        """Get the full raw content of the workflow file."""
        with open(self.file_path, 'r') as f:
            return f.read()

    def update_document(self, name: str, new_doc: Any):
        """Update a specific workflow or subworkflow."""
        for i, doc in enumerate(self.documents):
            if doc.get('workflow') == name or doc.get('subworkflow') == name:
                self.documents[i] = new_doc
                return True
        return False
    
    def search_content(self, query: str, workflow_name: str = None) -> List[dict]:
        """Search for text across workflows and return matching locations."""
        results = []
        docs_to_search = self.documents if not workflow_name else [self.get_document_by_name(workflow_name)]
        
        for doc in docs_to_search:
            if not doc:
                continue
            wf_name = doc.get('workflow') or doc.get('subworkflow')
            if not wf_name:
                continue
                
            # Search in steps recursively
            def search_steps(steps, path="steps"):
                if not isinstance(steps, list):
                    return
                for i, step in enumerate(steps):
                    if not isinstance(step, dict):
                        continue
                    step_path = f"{path}[{i}]"
                    step_id = step.get('id', f'step_{i}')
                    
                    # Convert step to string for searching
                    import io
                    s = io.StringIO()
                    y = YAML()
                    y.dump(step, s)
                    step_str = s.getvalue()
                    
                    if query.lower() in step_str.lower():
                        results.append({
                            'workflow': wf_name,
                            'step_id': step_id,
                            'path': step_path,
                            'step': step
                        })
                    
                    # Search in nested steps (then/else branches)
                    if 'then' in step:
                        then_block = step['then']
                        if isinstance(then_block, dict) and 'steps' in then_block:
                            search_steps(then_block['steps'], f"{step_path}.then.steps")
                        elif isinstance(then_block, dict):
                            # Single step in then
                            search_steps([then_block], f"{step_path}.then")
                    
                    if 'else' in step:
                        else_block = step['else']
                        if isinstance(else_block, dict) and 'steps' in else_block:
                            search_steps(else_block['steps'], f"{step_path}.else.steps")
                        elif isinstance(else_block, dict):
                            search_steps([else_block], f"{step_path}.else")
            
            if 'steps' in doc:
                search_steps(doc['steps'])
        
        return results
    
    def get_step_by_id(self, workflow_name: str, step_id: str) -> dict:
        """Get a specific step by its ID from a workflow."""
        doc = self.get_document_by_name(workflow_name)
        if not doc or 'steps' not in doc:
            return None
        
        def find_step(steps):
            if not isinstance(steps, list):
                return None
            for step in steps:
                if not isinstance(step, dict):
                    continue
                if step.get('id') == step_id:
                    return step
                
                # Search in nested steps
                if 'then' in step:
                    then_block = step['then']
                    if isinstance(then_block, dict) and 'steps' in then_block:
                        result = find_step(then_block['steps'])
                        if result:
                            return result
                    elif isinstance(then_block, dict) and then_block.get('id') == step_id:
                        return then_block
                
                if 'else' in step:
                    else_block = step['else']
                    if isinstance(else_block, dict) and 'steps' in else_block:
                        result = find_step(else_block['steps'])
                        if result:
                            return result
                    elif isinstance(else_block, dict) and else_block.get('id') == step_id:
                        return else_block
            return None
        
        return find_step(doc['steps'])
    
    def modify_step(self, workflow_name: str, step_id: str, new_step: dict) -> bool:
        """Modify a specific step in a workflow by its ID."""
        doc = self.get_document_by_name(workflow_name)
        if not doc or 'steps' not in doc:
            return False
        
        def replace_step(steps):
            if not isinstance(steps, list):
                return False
            for i, step in enumerate(steps):
                if not isinstance(step, dict):
                    continue
                if step.get('id') == step_id:
                    steps[i] = new_step
                    return True
                
                # Search in nested steps
                if 'then' in step:
                    then_block = step['then']
                    if isinstance(then_block, dict) and 'steps' in then_block:
                        if replace_step(then_block['steps']):
                            return True
                    elif isinstance(then_block, dict) and then_block.get('id') == step_id:
                        step['then'] = new_step
                        return True
                
                if 'else' in step:
                    else_block = step['else']
                    if isinstance(else_block, dict) and 'steps' in else_block:
                        if replace_step(else_block['steps']):
                            return True
                    elif isinstance(else_block, dict) and else_block.get('id') == step_id:
                        step['else'] = new_step
                        return True
            return False
        
        return replace_step(doc['steps'])
    
    def insert_step(self, workflow_name: str, position: dict, new_step: dict) -> bool:
        """Insert a step at a specific position (before/after a step_id or at index)."""
        doc = self.get_document_by_name(workflow_name)
        if not doc or 'steps' not in doc:
            return False
        
        insert_type = position.get('type')  # 'before', 'after', 'at_index'
        reference = position.get('reference')  # step_id or index
        
        def insert_in_steps(steps):
            if not isinstance(steps, list):
                return False
            
            if insert_type == 'at_index':
                idx = int(reference)
                if 0 <= idx <= len(steps):
                    steps.insert(idx, new_step)
                    return True
                return False
            
            for i, step in enumerate(steps):
                if not isinstance(step, dict):
                    continue
                if step.get('id') == reference:
                    if insert_type == 'before':
                        steps.insert(i, new_step)
                    elif insert_type == 'after':
                        steps.insert(i + 1, new_step)
                    return True
                
                # Search in nested steps
                if 'then' in step:
                    then_block = step['then']
                    if isinstance(then_block, dict) and 'steps' in then_block:
                        if insert_in_steps(then_block['steps']):
                            return True
                
                if 'else' in step:
                    else_block = step['else']
                    if isinstance(else_block, dict) and 'steps' in else_block:
                        if insert_in_steps(else_block['steps']):
                            return True
            return False
        
        return insert_in_steps(doc['steps'])
    
    def delete_step(self, workflow_name: str, step_id: str) -> bool:
        """Delete a specific step by its ID."""
        doc = self.get_document_by_name(workflow_name)
        if not doc or 'steps' not in doc:
            return False
        
        def remove_step(steps):
            if not isinstance(steps, list):
                return False
            for i, step in enumerate(steps):
                if not isinstance(step, dict):
                    continue
                if step.get('id') == step_id:
                    steps.pop(i)
                    return True
                
                # Search in nested steps
                if 'then' in step:
                    then_block = step['then']
                    if isinstance(then_block, dict) and 'steps' in then_block:
                        if remove_step(then_block['steps']):
                            return True
                    elif isinstance(then_block, dict) and then_block.get('id') == step_id:
                        del step['then']
                        return True
                
                if 'else' in step:
                    else_block = step['else']
                    if isinstance(else_block, dict) and 'steps' in else_block:
                        if remove_step(else_block['steps']):
                            return True
                    elif isinstance(else_block, dict) and else_block.get('id') == step_id:
                        del step['else']
                        return True
            return False
        
        return remove_step(doc['steps'])
