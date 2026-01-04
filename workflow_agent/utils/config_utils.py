import os
import sys
import yaml
from loguru import logger

# Configures the logger with a simple sink for cleaner output
def setup_logger():
    def simple_sink(message):
        sys.stderr.write(message.record["message"] + "\n")
        sys.stderr.flush()
    logger.remove()
    logger.add(simple_sink)

# Returns absolute paths for domain codebase files
def get_config_paths():
    domain_path = os.path.join(os.getcwd(), "data/tau2/domains/airline/codebase")
    return {
        "workflow": os.path.join(domain_path, "workflow.yaml"),
        "tone": os.path.join(domain_path, "tone.yaml"),
        "constants": os.path.join(domain_path, "constants.yaml")
    }

# Loads and filters workflow definitions from YAML
def load_workflows(file_path):
    with open(file_path, 'r') as f:
        return [w for w in yaml.safe_load_all(f) if w is not None]

# Loads tone configuration and formats it as a prompt string
def load_tone(file_path):
    with open(file_path, 'r') as f:
        data = yaml.safe_load(f)
        lines = []
        if 'identity' in data: lines.append(f"Identity: {data['identity'].get('role', '')}")
        if 'tone' in data: lines.append(f"Tone: {data['tone']}")
        if 'guidelines' in data:
            lines.append("Guidelines:")
            for g in data['guidelines']: lines.append(f"- {g}")
        return "\n".join(lines)

# Loads constants from YAML, returning an empty dict on failure
def load_constants(file_path):
    try:
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)
            return data if data is not None else {}
    except Exception:
        return {}
