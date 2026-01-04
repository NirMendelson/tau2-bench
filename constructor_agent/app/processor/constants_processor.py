from typing import Any, Dict, List, Optional
import os
from constructor_agent.app.utils.yaml_manager import get_yaml_instance

# Handles reading and editing constants.yaml with surgical precision
class ConstantsProcessor:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.yaml = get_yaml_instance()
        self.data = {}

    def load(self) -> dict:
        if not os.path.exists(self.file_path):
            return {}
        with open(self.file_path, 'r') as f:
            self.data = self.yaml.load(f) or {}
        return self.data

    def save(self):
        with open(self.file_path, 'w') as f:
            self.yaml.dump(self.data, f)

    def get(self, key: str) -> Any:
        return self.data.get(key)

    def set(self, key: str, value: Any) -> bool:
        self.data[key] = value
        return True

    def delete(self, key: str) -> bool:
        if key in self.data:
            del self.data[key]
            return True
        return False

    def add_prerequisite(self, field: str) -> bool:
        if 'default_prerequisites' not in self.data:
            self.data['default_prerequisites'] = []
        if field not in self.data['default_prerequisites']:
            self.data['default_prerequisites'].append(field)
            return True
        return False

    def remove_prerequisite(self, field: str) -> bool:
        if 'default_prerequisites' in self.data and field in self.data['default_prerequisites']:
            self.data['default_prerequisites'].remove(field)
            return True
        return False
