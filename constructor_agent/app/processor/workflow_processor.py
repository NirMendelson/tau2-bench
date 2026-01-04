from typing import List, Any, Optional
import os
import subprocess
import io
from constructor_agent.app.utils.yaml_manager import get_yaml_instance, enforce_flow_style

# Handles reading, searching, and editing workflow.yaml with surgical precision
class WorkflowProcessor:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.yaml = get_yaml_instance()
        self.documents = []

    def load(self) -> List[Any]:
        if not os.path.exists(self.file_path):
            return []
        with open(self.file_path, 'r') as f:
            self.documents = [doc for doc in self.yaml.load_all(f) if doc is not None]
        return self.documents

    def save(self):
        enforce_flow_style(self.documents)
        with open(self.file_path, 'w') as f:
            self.yaml.dump_all(self.documents, f)

    def get_document_by_name(self, name: str):
        for doc in self.documents:
            metadata = doc[0] if isinstance(doc, list) and len(doc) > 0 else doc
            if isinstance(metadata, dict) and (metadata.get('workflow') == name or metadata.get('subworkflow') == name):
                return doc
        return None

    def list_workflows(self) -> List[str]:
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

    def search_content(self, query: str, workflow_name: str = None) -> List[dict]:
        results = []
        docs_to_search = self.documents if not workflow_name else [self.get_document_by_name(workflow_name)]
        
        for doc in docs_to_search:
            if not doc: continue
            
            metadata = doc[0] if isinstance(doc, list) and len(doc) > 0 else doc
            wf_name = metadata.get('workflow') or metadata.get('subworkflow')
            if not wf_name: continue
                
            def search_steps(steps, path="steps"):
                if not isinstance(steps, list): return
                for i, step in enumerate(steps):
                    if not isinstance(step, dict): continue
                    step_path = f"{path}[{i}]"
                    step_id = step.get('id', f'step_{i}')
                    
                    line_no = step.lc.line + 1 if hasattr(step, 'lc') else None
                    
                    s = io.StringIO()
                    self.yaml.dump(step, s)
                    if query.lower() in s.getvalue().lower():
                        results.append({
                            'workflow': wf_name,
                            'step_id': step_id,
                            'path': step_path,
                            'line': line_no,
                            'step': step
                        })
                    
                    for key in ['then', 'else']:
                        if key in step:
                            block = step[key]
                            if isinstance(block, list):
                                search_steps(block, f"{step_path}.{key}")
                            elif isinstance(block, dict):
                                if 'steps' in block:
                                    search_steps(block['steps'], f"{step_path}.{key}.steps")
                                else:
                                    search_steps([block], f"{step_path}.{key}")
            
            if isinstance(doc, list):
                search_steps(doc[1:], path="")
            elif 'steps' in doc:
                search_steps(doc['steps'])
        
        return results

    def get_step_by_id(self, workflow_name: str, step_id: str) -> Optional[dict]:
        doc = self.get_document_by_name(workflow_name)
        if not doc: return None

        def find_step(steps):
            if not isinstance(steps, list): return None
            for step in steps:
                if not isinstance(step, dict): continue
                if step.get('id') == step_id: return step
                for key in ['then', 'else']:
                    if key in step:
                        block = step[key]
                        if isinstance(block, list):
                            res = find_step(block)
                            if res: return res
                        elif isinstance(block, dict):
                            if 'steps' in block:
                                res = find_step(block['steps'])
                                if res: return res
                            elif block.get('id') == step_id: return block
            return None
        
        return find_step(doc[1:] if isinstance(doc, list) else doc.get('steps', []))

    def update_workflow_steps(self, workflow_name: str, steps: List[dict]) -> bool:
        """Overwrites all steps in a workflow/subworkflow with a new list."""
        doc = self.get_document_by_name(workflow_name)
        if not doc: return False
        
        if isinstance(doc, list):
            # doc[0] is metadata, doc[1:] are steps
            doc[1:] = steps
            return True
        elif 'steps' in doc:
            doc['steps'] = steps
            return True
        return False

    def create_workflow(self, name: str, description: str, steps: List[dict], is_subworkflow: bool = False) -> bool:
        """Creates a new workflow or subworkflow document."""
        if self.get_document_by_name(name):
            return False # Already exists
            
        metadata_key = "subworkflow" if is_subworkflow else "workflow"
        new_doc = [
            {metadata_key: name, "when": description}
        ]
        new_doc.extend(steps)
        self.documents.append(new_doc)
        return True

    def grep_codebase(self, query: str, domain: str = "airline") -> List[dict]:
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        
        # Restrict search to domain-specific tools and the constructor knowledge
        search_paths = [
            os.path.join(root_dir, "src/tau2/domains", domain),
            os.path.join(root_dir, "constructor_agent/knowledge")
        ]
        
        matches = []
        for path in search_paths:
            if not os.path.exists(path): continue
            cmd = ["grep", "-rnI", query, path]
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                for line in result.stdout.splitlines():
                    if ":" in line:
                        parts = line.split(":", 2)
                        if len(parts) >= 3:
                            file_path, line_no, content = parts
                            matches.append({
                                "file": os.path.relpath(file_path, root_dir),
                                "line": int(line_no),
                                "content": content.strip()
                            })
            except Exception: continue
            
        return matches[:50]
