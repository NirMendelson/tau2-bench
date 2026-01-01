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
            print(f"Proposed edits to: {[e['name'] for e in result['edits']]}")

if __name__ == "__main__":
    test()
