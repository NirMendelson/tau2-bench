import yaml
import json
import re
import datetime
from pydantic import BaseModel

# Custom YAML loader that doesn't automatically parse strings as dates/times
class NoDatesSafeLoader(yaml.SafeLoader):
    pass

# Remove the implicit resolver for timestamps to avoid datetime.date conversion
NoDatesSafeLoader.yaml_implicit_resolvers = {
    k: [r for r in v if r[0] != 'tag:yaml.org,2002:timestamp']
    for k, v in yaml.SafeLoader.yaml_implicit_resolvers.items()
}

# Loads YAML content using the customized NoDatesSafeLoader
def custom_safe_load(content):
    return yaml.load(content, Loader=NoDatesSafeLoader)

# Cleans LLM response text to extract and sanitize JSON/YAML content
def clean_json_response(response_text):
    response_text = response_text.strip()
    
    code_block_match = re.search(r'```(?:yaml|json)?\n(.*?)\n```', response_text, re.DOTALL)
    if code_block_match:
        response_text = code_block_match.group(1).strip()
    elif response_text.startswith("```"):
        lines = response_text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        response_text = "\n".join(lines).strip()
    
    try:
        json.loads(response_text)
        return response_text
    except:
        pass

    primary_keys = {
        "found", "value", "question", "condition_result", "fields", "questions", 
        "all_found", "combined_question", "result", "reasoning", "arguments"
    }
    
    lines = response_text.split("\n")
    cleaned_lines = []
    block_mode = False
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append(line)
            continue
            
        key_match = re.match(r'^(\s*)([\w_-]+):\s*(.*)$', line)
        
        if key_match:
            indent, key, value = key_match.groups()
            
            if not indent or (key in primary_keys and len(indent) <= 2):
                block_mode = False
            
            if not block_mode and not "|-" in value and ":" in value:
                v_strip = value.strip()
                if v_strip and not (v_strip.startswith('"') or v_strip.startswith("'")):
                    if v_strip.lower() not in ["true", "false", "null", "none"]:
                        escaped_v = v_strip.replace('"', '\\"')
                        line = f"{indent}{key}: \"{escaped_v}\""
            
            if "|-" in value:
                block_mode = True
            elif block_mode:
                if not line.startswith("  "):
                    line = "  " + line
            
            cleaned_lines.append(line)
        else:
            if block_mode:
                if not line.startswith("  "):
                    line = "  " + line
            cleaned_lines.append(line)
            
    return "\n".join(cleaned_lines)

# Checks if a value from an LLM response should be treated as null
def is_null_value(val):
    if val is None:
        return True
    if isinstance(val, str):
        normalized = val.strip().lower()
        normalized = normalized.strip("'\" \n")
        if normalized in ["null", "none", "n/a", "unknown", ""]:
            return True
    return False

# Serializes objects (including Pydantic models and dates) into JSON-compatible formats
def serialize_obj(obj):
    if isinstance(obj, BaseModel): return obj.model_dump()
    if isinstance(obj, (datetime.date, datetime.datetime)): return obj.isoformat()
    if isinstance(obj, list): return [serialize_obj(i) for i in obj]
    if isinstance(obj, dict): return {k: serialize_obj(v) for k, v in obj.items()}
    return obj
