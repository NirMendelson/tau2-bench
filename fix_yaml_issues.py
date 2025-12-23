import sys

def fix_yaml_indentation(filepath):
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        
        if line.strip().startswith('- id:'):
            indent = len(line) - len(line.lstrip())
            new_lines.append(line)
            
            # Look at subsequent lines that should be part of this mapping
            j = i + 1
            expected_indent = indent + 2
            
            # Check if the next line is misaligned (e.g. action: is at indent + 4)
            if j < len(lines):
                next_line = lines[j]
                if not next_line.strip().startswith('-') and next_line.strip() and not next_line.strip().startswith('#'):
                    next_indent = len(next_line) - len(next_line.lstrip())
                    if next_indent == indent + 4:
                        # Found a misaligned block!
                        print(f"Fixing block starting at line {j+1}")
                        while j < len(lines):
                            curr_line = lines[j]
                            if curr_line.strip().startswith('-') or (curr_line.strip() and len(curr_line) - len(curr_line.lstrip()) < next_indent):
                                break
                            
                            # De-indent by 2
                            new_lines.append(curr_line[2:])
                            j += 1
                        i = j
                        continue
            i += 1
        else:
            new_lines.append(line)
            i += 1
            
    return new_lines

if __name__ == "__main__":
    filepath = '/Users/nirmendelson/quack/tau2-bench/data/tau2/domains/airline/codebase/workflow.yaml'
    fixed_lines = fix_yaml_indentation(filepath)
    with open(filepath + '.fixed', 'w') as f:
        f.writelines(fixed_lines)
