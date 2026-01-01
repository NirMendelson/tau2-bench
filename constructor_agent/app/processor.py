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
            if doc and (doc.get('workflow') == name or doc.get('subworkflow') == name):
                return doc
        return None

    def list_workflows(self) -> List[str]:
        """List all workflow and subworkflow names."""
        names = []
        for doc in self.documents:
            if not doc:
                continue
            if 'workflow' in doc:
                names.append(f"workflow: {doc['workflow']}")
            elif 'subworkflow' in doc:
                names.append(f"subworkflow: {doc['subworkflow']}")
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
