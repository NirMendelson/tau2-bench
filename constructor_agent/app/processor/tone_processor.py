from typing import Any, Dict, List, Optional
import os
from constructor_agent.app.utils.yaml_manager import get_yaml_instance

# Handles reading and editing tone.yaml with surgical precision
class ToneProcessor:
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

    def set_role(self, role: str) -> bool:
        if 'identity' not in self.data:
            self.data['identity'] = {}
        self.data['identity']['role'] = role
        return True

    def set_tone(self, tone: str) -> bool:
        self.data['tone'] = tone
        return True

    def add_guideline(self, guideline: str) -> bool:
        if 'guidelines' not in self.data:
            self.data['guidelines'] = []
        if guideline not in self.data['guidelines']:
            self.data['guidelines'].append(guideline)
            return True
        return False

    def remove_guideline(self, guideline: str) -> bool:
        if 'guidelines' in self.data and guideline in self.data['guidelines']:
            self.data['guidelines'].remove(guideline)
            return True
        return False
