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
            metadata = doc[0] if isinstance(doc, list) and len(doc) > 0 else doc
            if isinstance(metadata, dict) and (metadata.get('workflow') == name or metadata.get('subworkflow') == name):
                return doc
        return None

    def list_workflows(self) -> List[str]:
        """List all workflow and subworkflow names."""
        names = []
        for doc in self.documents:
            metadata = doc[0] if isinstance(doc, list) and len(doc) > 0 else doc
            if not isinstance(metadata, dict):
                continue
            if 'workflow' in metadata:
                names.append(metadata['workflow'])
            elif 'subworkflow' in metadata:
                names.append(metadata['subworkflow'])
        return names

    def get_full_content(self) -> str:
        """Get the full raw content of the workflow file."""
        with open(self.file_path, 'r') as f:
            return f.read()

    def update_document(self, name: str, new_doc: Any):
        """Update a specific workflow or subworkflow."""
        for i, doc in enumerate(self.documents):
            metadata = doc[0] if isinstance(doc, list) and len(doc) > 0 else doc
            if metadata.get('workflow') == name or metadata.get('subworkflow') == name:
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
            
            metadata = doc[0] if isinstance(doc, list) and len(doc) > 0 else doc
            wf_name = metadata.get('workflow') or metadata.get('subworkflow')
            if not wf_name:
                continue
                
            # Search in steps recursively
            def search_steps(steps, path="steps"):
                if not isinstance(steps, list):
                    return
                for i, step in enumerate(steps):
                    if not isinstance(step, dict):
                        continue
                    # Adjust path for search preview (index if list)
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
                    for key in ['then', 'else']:
                        if key in step:
                            block = step[key]
                            if isinstance(block, list):
                                search_steps(block, f"{step_path}.{key}")
                            elif isinstance(block, dict):
                                if 'steps' in block:
                                    search_steps(block['steps'], f"{step_path}.{key}.steps")
                                else:
                                    # Single step
                                    search_steps([block], f"{step_path}.{key}")
            
            if isinstance(doc, list):
                # Metadata is at [0], steps start at [1]
                search_steps(doc[1:], path="")
            elif 'steps' in doc:
                search_steps(doc['steps'])
        
        return results
    
    def get_step_by_id(self, workflow_name: str, step_id: str) -> dict:
        """Get a specific step by its ID from a workflow."""
        doc = self.get_document_by_name(workflow_name)
        def find_step(steps):
            if not isinstance(steps, list):
                return None
            for step in steps:
                if not isinstance(step, dict):
                    continue
                if step.get('id') == step_id:
                    return step
                
                # Search in nested steps
                for key in ['then', 'else']:
                    if key in step:
                        block = step[key]
                        if isinstance(block, list):
                            result = find_step(block)
                            if result:
                                return result
                        elif isinstance(block, dict):
                            if 'steps' in block:
                                result = find_step(block['steps'])
                                if result:
                                    return result
                            elif block.get('id') == step_id:
                                return block
            return None
        
        if isinstance(doc, list):
            return find_step(doc[1:])
        elif 'steps' in doc:
            return find_step(doc['steps'])
        return None
    
    def modify_step(self, workflow_name: str, step_id: str, new_step: dict) -> bool:
        """Modify a specific step in a workflow by its ID."""
        doc = self.get_document_by_name(workflow_name)
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
                for key in ['then', 'else']:
                    if key in step:
                        block = step[key]
                        if isinstance(block, list):
                            if replace_step(block):
                                return True
                        elif isinstance(block, dict):
                            if 'steps' in block:
                                if replace_step(block['steps']):
                                    return True
                            elif block.get('id') == step_id:
                                step[key] = new_step
                                return True
            return False
        
        if isinstance(doc, list):
            return replace_step(doc) # Include [0] just in case though steps start at [1]
        elif 'steps' in doc:
            return replace_step(doc['steps'])
        return False
    
    def insert_step(self, workflow_name: str, position: dict, new_step: dict) -> bool:
        """Insert a step at a specific position (before/after a step_id or at index)."""
        doc = self.get_document_by_name(workflow_name)
        if not doc:
            return False
        
        insert_type = position.get('type')  # 'before', 'after', 'at_index'
        reference = position.get('reference')  # step_id or index
        
        def insert_in_steps(steps):
            if not isinstance(steps, list):
                return False
            
            if insert_type == 'at_index':
                try:
                    idx = int(reference)
                    if 0 <= idx <= len(steps):
                        steps.insert(idx, new_step)
                        return True
                except (ValueError, TypeError):
                    return False
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
                for key in ['then', 'else']:
                    if key in step:
                        block = step[key]
                        if isinstance(block, list):
                            if insert_in_steps(block):
                                return True
                        elif isinstance(block, dict):
                            if 'steps' in block:
                                if insert_in_steps(block['steps']):
                                    return True
            return False
        
        if isinstance(doc, list):
            # If inserting at index, we must respect metadata at [0]
            if insert_type == 'at_index':
                try:
                    idx = int(reference)
                    if idx == 0:
                        doc.insert(1, new_step)
                        return True
                except (ValueError, TypeError):
                    pass
            return insert_in_steps(doc)
        elif 'steps' in doc:
            return insert_in_steps(doc['steps'])
        return False
    
    def delete_step(self, workflow_name: str, step_id: str) -> bool:
        """Delete a specific step by its ID."""
        doc = self.get_document_by_name(workflow_name)
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
                for key in ['then', 'else']:
                    if key in step:
                        block = step[key]
                        if isinstance(block, list):
                            if remove_step(block):
                                return True
                        elif isinstance(block, dict):
                            if 'steps' in block:
                                if remove_step(block['steps']):
                                    return True
                            elif block.get('id') == step_id:
                                del step[key]
                                return True
            return False
        
        if isinstance(doc, list):
            return remove_step(doc)
        elif 'steps' in doc:
            return remove_step(doc['steps'])
        return False
