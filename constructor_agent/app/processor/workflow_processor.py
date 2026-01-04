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

    def modify_step(self, workflow_name: str, step_id: str, new_step: dict) -> bool:
        doc = self.get_document_by_name(workflow_name)
        if not doc: return False

        def replace_step(steps):
            if not isinstance(steps, list): return False
            for i, step in enumerate(steps):
                if not isinstance(step, dict): continue
                if step.get('id') == step_id:
                    steps[i] = new_step
                    return True
                for key in ['then', 'else']:
                    if key in step:
                        block = step[key]
                        if isinstance(block, list):
                            if replace_step(block): return True
                        elif isinstance(block, dict):
                            if 'steps' in block:
                                if replace_step(block['steps']): return True
                            elif block.get('id') == step_id:
                                step[key] = new_step
                                return True
            return False
        
        return replace_step(doc if isinstance(doc, list) else doc.get('steps', []))

    def insert_step(self, workflow_name: str, position: dict, new_step: dict) -> bool:
        doc = self.get_document_by_name(workflow_name)
        if not doc: return False
        
        insert_type = position.get('type') # 'before', 'after', 'at_index'
        reference = position.get('reference') # step_id or index
        
        def insert_in_steps(steps):
            if not isinstance(steps, list): return False
            if insert_type == 'at_index':
                try:
                    idx = int(reference)
                    if 0 <= idx <= len(steps):
                        steps.insert(idx, new_step)
                        return True
                except (ValueError, TypeError): return False
                return False
            
            for i, step in enumerate(steps):
                if not isinstance(step, dict): continue
                if step.get('id') == reference:
                    if insert_type == 'before': steps.insert(i, new_step)
                    elif insert_type == 'after': steps.insert(i + 1, new_step)
                    return True
                for key in ['then', 'else']:
                    if key in step:
                        block = step[key]
                        if isinstance(block, list):
                            if insert_in_steps(block): return True
                        elif isinstance(block, dict):
                            if 'steps' in block:
                                if insert_in_steps(block['steps']): return True
            return False
        
        if isinstance(doc, list):
            if insert_type == 'at_index' and reference == 0:
                doc.insert(1, new_step)
                return True
            return insert_in_steps(doc)
        return insert_in_steps(doc.get('steps', []))

    def delete_step(self, workflow_name: str, step_id: str) -> bool:
        doc = self.get_document_by_name(workflow_name)
        if not doc: return False

        def remove_step(steps):
            if not isinstance(steps, list): return False
            for i, step in enumerate(steps):
                if not isinstance(step, dict): continue
                if step.get('id') == step_id:
                    steps.pop(i)
                    return True
                for key in ['then', 'else']:
                    if key in step:
                        block = step[key]
                        if isinstance(block, list):
                            if remove_step(block): return True
                        elif isinstance(block, dict):
                            if 'steps' in block:
                                if remove_step(block['steps']): return True
                            elif block.get('id') == step_id:
                                del step[key]
                                return True
            return False
        
        return remove_step(doc if isinstance(doc, list) else doc.get('steps', []))

    def grep_codebase(self, query: str, include: str = None) -> List[dict]:
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        cmd = ["grep", "-rnI", query, root_dir]
        if include: cmd.extend(["--include", include])
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            matches = []
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
            return matches[:50]
        except Exception: return []
