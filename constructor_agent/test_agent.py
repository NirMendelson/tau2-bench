from constructor_agent.app.agent import ConstructorAgent
import os
import sys

def test():
    workflow_path = "/Users/nirmendelson/quack/tau2-bench/data/tau2/domains/airline/codebase/workflow.yaml"
    rules_path = "/Users/nirmendelson/quack/tau2-bench/constructor_agent/cspl-rules.md"
    
    agent = ConstructorAgent(workflow_path, rules_path)
    
    instruction = "On canceling flight, after getting the reservation id, if the reservation id is missing, you have to use the escalation tool."
    
    print(f"Processing instruction: {instruction}")
    result = agent.process_request(instruction)
    
    if result.get('clarification'):
        print(f"CLARIFICATION NEEDED: {result['clarification']}")
    else:
        print(f"EXPLANATION: {result['explanation']}")
        if result.get('edits'):
            print(f"\nProposed {len(result['edits'])} edit(s):")
            for i, edit in enumerate(result['edits'], 1):
                print(f"\n  Edit {i}:")
                print(f"    Workflow: {edit.get('workflow_name', 'unknown')}")
                print(f"    Type: {edit.get('edit_type', 'unknown')}")
                print(f"    Step ID: {edit.get('step_id', 'unknown')}")
                print(f"    Reason: {edit.get('reason', 'N/A')}")

if __name__ == "__main__":
    test()
