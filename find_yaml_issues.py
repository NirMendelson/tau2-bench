import sys

def check_yaml_indentation(filepath):
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    issues = []
    for i in range(len(lines) - 1):
        line = lines[i]
        next_line = lines[i+1]
        
        if '- id:' in line:
            indent = len(line) - len(line.lstrip())
            next_indent = len(next_line) - len(next_line.lstrip())
            
            # For a mapping in a list:
            # - id: value
            #   action: value
            # The '-' is at 'indent'
            # 'id' is at 'indent + 2'
            # 'action' should be at 'indent + 2'
            
            if 'action:' in next_line:
                if next_indent != indent + 2:
                    issues.append((i+2, line.strip(), next_line.strip(), indent, next_indent))
            elif '  ' in next_line and not next_line.strip().startswith('#') and next_line.strip():
                # Check subsequent lines of the same mapping
                pass

    return issues

if __name__ == "__main__":
    filepath = '/Users/nirmendelson/quack/tau2-bench/data/tau2/domains/airline/codebase/workflow.yaml'
    issues = check_yaml_indentation(filepath)
    for line_num, line_text, next_text, indent, next_indent in issues:
        print(f"Line {line_num}: '{line_text}' has indent {indent}, next line '{next_text}' has indent {next_indent} (expected {indent+2})")
