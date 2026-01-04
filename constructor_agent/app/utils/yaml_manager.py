from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedSeq
from typing import Any
import io

# Configure ruamel.yaml with consistent settings
def get_yaml_instance() -> YAML:
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=2, offset=0)
    return yaml

# Enforce flow style for specific fields (input, fields) to keep them compact
def enforce_flow_style(data: Any):
    if isinstance(data, dict):
        for k, v in data.items():
            if k in ['input', 'fields'] and isinstance(v, list) and len(v) > 0:
                if not isinstance(v, CommentedSeq):
                    data[k] = CommentedSeq(v)
                data[k].fa.set_flow_style()
            else:
                enforce_flow_style(v)
    elif isinstance(data, list):
        for item in data:
            enforce_flow_style(item)

# Convert a step dict to YAML string for display or logging
def step_to_yaml(step: dict) -> str:
    s = io.StringIO()
    y = get_yaml_instance()
    y.dump(step, s)
    return s.getvalue()
