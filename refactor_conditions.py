import yaml
import re

def convert_condition(condition):
    if not isinstance(condition, dict):
        return condition
    
    op = condition.get('operator')
    left = condition.get('left', '')
    right = condition.get('right', '')
    
    # Remove {{ and }} from left and right
    if isinstance(left, str):
        left = left.replace('{{ ', '{').replace(' }}', '}')
    if isinstance(right, str):
        right = right.replace('{{ ', '{').replace(' }}', '}')
    
    if op == 'eq' or op == 'equal' or op == 'equals':
        if right is None:
            return f"{left} is null"
        if isinstance(right, list) and len(right) == 1:
            return f"{left} is {right[0]}"
        return f"{left} is {right}"
    elif op == 'neq' or op == 'not_equal':
        return f"{left} is not {right}"
    elif op == 'gt' or op == 'greater_than':
        return f"{left} is greater than {right}"
    elif op == 'lt' or op == 'less_than':
        return f"{left} is less than {right}"
    elif op == 'gte' or op == 'greater_equal':
        return f"{left} is greater than or equal to {right}"
    elif op == 'lte' or op == 'less_equal':
        return f"{left} is less than or equal to {right}"
    elif op == 'contains':
        if right == "cancelled OR landed":
            return f"{left} is either cancelled or landed"
        if isinstance(right, list):
            return f"{left} contains {' or '.join(map(str, right))}"
        return f"{left} contains {right}"
    elif op == 'and':
        conds = condition.get('conditions', [])
        return " and ".join([convert_condition(c) for c in conds])
    elif op == 'or':
        conds = condition.get('conditions', [])
        return " or ".join([convert_condition(c) for c in conds])
    
    return str(condition)

def process_steps(steps):
    for step in steps:
        if 'condition' in step:
            step['condition'] = convert_condition(step['condition'])
        
        if 'then' in step and 'steps' in step['then']:
            process_steps(step['then']['steps'])
        if 'else' in step and 'steps' in step['else']:
            process_steps(step['else']['steps'])
        
        # for fetch_with_condition
        if step.get('action') == 'fetch_with_condition' and 'condition' in step:
             step['condition'] = convert_condition(step['condition'])

def main():
    path = '/Users/nirmendelson/quack/tau2-bench/data/tau2/domains/airline/codebase/workflow.yaml'
    
    # We can't use a simple yaml.load because it might lose comments or formatting.
    # But since the goal is just requested change, I will try to use regex for replacements to keep formatting.
    
    with open(path, 'r') as f:
        content = f.read()

    # Regex to find condition blocks
    # This is tricky because of indentation.
    
    # Instead of full YAML parsing, let's find 'condition:' and the following lines
    
    lines = content.split('\n')
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip() == 'condition:':
            # Check if it's a block condition
            if i + 1 < len(lines) and lines[i+1].strip().startswith('operator:'):
                indent = len(line) - len(line.lstrip())
                block = []
                j = i + 1
                while j < len(lines) and (not lines[j].strip() or len(lines[j]) - len(lines[j].lstrip()) > indent):
                    block.append(lines[j])
                    j += 1
                
                # Try to parse the block
                block_str = '\n'.join(block)
                try:
                    cond_dict = yaml.safe_load(block_str)
                    new_cond = convert_condition(cond_dict)
                    new_lines.append(f"{' ' * indent}condition: {new_cond}")
                    i = j
                    continue
                except:
                    pass
        new_lines.append(line)
        i += 1
    
    with open(path, 'w') as f:
        f.write('\n'.join(new_lines))

if __name__ == "__main__":
    main()
