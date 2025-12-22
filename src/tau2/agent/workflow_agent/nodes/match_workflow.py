# Node for matching user input to workflows

import os
from pocketflow import Node
from ..utils.workflow_matcher import (
    match_workflows,
    score_workflows_llm,
    meets_selection_criteria,
    generate_clarification_question,
    print_matching_debug
)
from ..utils.extract_from_memory import (
    extract_user_input,
    extract_workflows,
    extract_result,
    extract_scored_workflows,
    extract_candidate_workflows,
    extract_user_input_from_exec,
    extract_workflow_definition,
    extract_when_text
)


# Check if DEBUGGING_MODE is enabled from environment variables
def _is_debugging_enabled():
    return os.environ.get("DEBUGGING_MODE", "").lower() in ("true", "1", "yes")


# Node that matches user input to workflows via keyword fuzzy matching, semantic example matching, and LLM scoring
class MatchWorkflowNode(Node):
    
    # Get user input from conversation_history and workflows
    def prep(self, shared):
        user_input = extract_user_input(shared)
        workflows = extract_workflows(shared)
        model = shared.get("llm")
        llm_args = shared.get("llm_args", {})
        return user_input, workflows, model, llm_args
    
    # Match workflows using keyword and semantic matching, LLM score if multiple
    def exec(self, prep_res):
        user_input, workflows, model, llm_args = prep_res
        
        if not workflows:
            return {"result": None, "scored_workflows": None, "candidate_workflows": None}
        
        # Match workflows using keyword fuzzy matching and semantic example matching
        debug_enabled = _is_debugging_enabled()
        matches, all_combined_results, debug_info = match_workflows(
            user_input, 
            workflows,
            debug=debug_enabled
        )
        
        # Debug: print detailed matching information
        if debug_enabled and debug_info is not None:
            # Get keyword matches for debug output
            from utils.matching.workflow_filter import filter_workflows_by_keywords
            keyword_matches = filter_workflows_by_keywords(user_input, workflows)
            from utils.matching.workflow_filter import filter_workflows_by_examples
            semantic_matches = filter_workflows_by_examples(user_input, workflows)
            
            print_matching_debug(
                user_input,
                keyword_matches,
                semantic_matches,
                debug_info,
                workflows
            )
        
        # Debug: show matched workflows summary
        if debug_enabled:
            if len(matches) == 0:
                print(f"[DEBUG] matching found 0 matching workflows above threshold")
                if len(all_combined_results) > 0:
                    top_candidates = all_combined_results[:5]
                    print(f"[DEBUG] top 5 candidates below threshold: {[(name, f'{score:.3f}') for name, score in top_candidates]}")
            else:
                match_names = [name for name, score in matches]
                print(f"[DEBUG] matching found {len(matches)} matching workflow(s): {', '.join(match_names)}")
                print(f"[DEBUG] scores: {[(name, f'{score:.3f}') for name, score in matches]}")
        
        if len(matches) == 0:
            # No matches above threshold - fallback to LLM with top 5 candidates
            if len(all_combined_results) > 0:
                top_5_candidates = all_combined_results[:5]
                candidate_names = [name for name, score in top_5_candidates]
                candidate_workflows = {name: workflows[name] for name in candidate_names}
                
                if _is_debugging_enabled():
                    print(f"[DEBUG] no matches above threshold, sending top 5 to LLM: {candidate_names}")
                
                scored_workflows = score_workflows_llm(user_input, candidate_workflows, model, llm_args)
                
                # Debug: show LLM confidence scores
                if _is_debugging_enabled():
                    print(f"[DEBUG] LLM confidence scores (fallback): {[(name, f'{score:.3f}') for name, score in scored_workflows]}")
                
                return {
                    "result": scored_workflows[0][0] if scored_workflows else None,
                    "scored_workflows": scored_workflows,
                    "candidate_workflows": candidate_workflows,
                    "user_input": user_input,
                    "is_fallback": True  # Flag to indicate this was a fallback
                }
            else:
                return {"result": None, "scored_workflows": None, "candidate_workflows": None}
        elif len(matches) == 1:
            return {"result": matches[0][0], "scored_workflows": None, "candidate_workflows": None}
        else:
            # Multiple matches - use LLM to score all candidates
            match_names = [name for name, score in matches]
            candidate_workflows = {name: workflows[name] for name in match_names}
            scored_workflows = score_workflows_llm(user_input, candidate_workflows, model, llm_args)
            
            # Debug: show LLM confidence scores
            if _is_debugging_enabled():
                print(f"[DEBUG] LLM confidence scores: {[(name, f'{score:.3f}') for name, score in scored_workflows]}")
            
            return {
                "result": scored_workflows[0][0] if scored_workflows else None,
                "scored_workflows": scored_workflows,
                "candidate_workflows": candidate_workflows,
                "user_input": user_input,
                "model": model,
                "llm_args": llm_args
            }
    
    # Store selected_workflow or trigger clarification
    def post(self, shared, prep_res, exec_res):
        workflows = extract_workflows(shared)
        
        # Handle case where no matches found
        result = extract_result(exec_res)
        if result is None:
            shared["selected_workflow"] = None
            if _is_debugging_enabled():
                print(f"[DEBUG] no workflow selected (no matches found)")
            return "default"
        
        # Handle case with single match (no LLM scoring needed)
        scored_workflows = extract_scored_workflows(exec_res)
        if scored_workflows is None:
            workflow_name = result
            workflow_def = extract_workflow_definition(workflows, workflow_name)
            shared["selected_workflow"] = {
                "name": workflow_name,
                "definition": workflow_def
            }
            if _is_debugging_enabled():
                when_text = extract_when_text(workflow_def)
                print(f"[DEBUG] selected workflow: '{workflow_name}' (when: {when_text})")
            return "default"
        
        # Handle case with multiple matches - check confidence criteria
        candidate_workflows = extract_candidate_workflows(exec_res)
        user_input = extract_user_input_from_exec(exec_res)
        
        # Check if confidence scores meet selection criteria
        # For LLM: only check gap (0.0), no min confidence threshold
        if meets_selection_criteria(scored_workflows, min_confidence_gap=0.0):
            # Criteria met - select top workflow
            workflow_name = scored_workflows[0][0]
            workflow_def = extract_workflow_definition(workflows, workflow_name)
            shared["selected_workflow"] = {
                "name": workflow_name,
                "definition": workflow_def
            }
            if _is_debugging_enabled():
                when_text = extract_when_text(workflow_def)
                print(f"[DEBUG] selected workflow: '{workflow_name}' (when: {when_text})")
            return "default"
        else:
            # Criteria not met - generate clarification question
            model = exec_res.get("model")
            llm_args = exec_res.get("llm_args", {})
            clarification_question = generate_clarification_question(user_input, candidate_workflows, model, llm_args)
            shared["clarification_question"] = clarification_question
            shared["selected_workflow"] = None
            
            # Add clarification question to conversation history
            conversation_history = shared.get("conversation_history", [])
            conversation_history.append({
                "role": "assistant",
                "content": clarification_question
            })
            
            if _is_debugging_enabled():
                top_confidence = scored_workflows[0][1] if scored_workflows else 0.0
                second_confidence = scored_workflows[1][1] if len(scored_workflows) > 1 else 0.0
                gap = top_confidence - second_confidence
                print(f"[DEBUG] confidence criteria not met (top: {top_confidence:.3f}, gap: {gap:.3f})")
                print(f"[DEBUG] clarification question: {clarification_question}")
            
            return "clarify"

