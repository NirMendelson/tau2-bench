import sys

def fix_yaml_indentation_v2(filepath):
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        
        if line.strip().startswith('- id:'):
            indent = len(line) - len(line.lstrip())
            new_lines.append(line)
            
            # The mapping keys should be at indent + 2
            expected_key_indent = indent + 2
            
            j = i + 1
            while j < len(lines):
                curr_line = lines[j]
                
                # Stop if we hit a new list item or a less-indented line
                if curr_line.strip().startswith('-') or (curr_line.strip() and len(curr_line) - len(curr_line.lstrip()) < indent):
                    break
                
                if curr_line.strip():
                    curr_indent = len(curr_line) - len(curr_line.lstrip())
                    
                    # If this is a top-level key in the mapping (not a continuation of a scalar/list/dict value)
                    # We can detect this if it has a colon and isn't preceded by '- ' at a deeper level
                    # But it's easier to just check if it's at expected_key_indent + something
                    if curr_indent > expected_key_indent and ':' in curr_line and not curr_line.strip().startswith('#'):
                        # Check if it's likely a misaligned key
                        # Usually keys are simple words
                        key_part = curr_line.split(':')[0].strip()
                        if ' ' not in key_part and not key_part.startswith('-'):
                            print(f"Fixing misaligned key at line {j+1}: '{curr_line.strip()}'")
                            # Shift the whole block starting here by (curr_indent - expected_key_indent)
                            shift = curr_indent - expected_key_indent
                            
                            while j < len(lines):
                                k_line = lines[j]
                                k_indent = len(k_line) - len(k_line.lstrip())
                                if k_indent < curr_indent and k_line.strip():
                                    break
                                
                                # Move to new_lines with fixed indentation
                                fixed_line = k_line[shift:]
                                new_lines.append(fixed_line)
                                j += 1
                            continue
                            
                new_lines.append(curr_line)
                j += 1
            i = j
        else:
            new_lines.append(line)
            i += 1
            
    return new_lines

if __name__ == "__main__":
    filepath = '/Users/nirmendelson/quack/tau2-bench/data/tau2/domains/airline/codebase/workflow.yaml'
    fixed_lines = fix_yaml_indentation_v2(filepath)
    with open(filepath + '.fixed', 'w') as f:
        f.writelines(fixed_lines)
