from . import bm25, semantic
from ..actions import prompts
import litellm
import os
import yaml
import re
from loguru import logger

DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"


def combine_scores(bm25_scores, semantic_scores):
    """
    Combines BM25 and semantic scores using weighted average.
    Weights: 0.3 for BM25/Fuzzy, 0.7 for Semantic.
    """
    combined = {}
    all_workflows = set(bm25_scores.keys()) | set(semantic_scores.keys())
    
    for wf in all_workflows:
        s_bm25 = bm25_scores.get(wf, 0.0)
        s_sem = semantic_scores.get(wf, 0.0)
        combined[wf] = 0.3 * s_bm25 + 0.7 * s_sem
        
    return combined


def filter_workflows(workflows_with_scores, min_score):
    """
    Filters out workflows that do not meet the minimum score threshold.
    Returns a dict of workflow: score.
    """
    return {wf: score for wf, score in workflows_with_scores.items() if score > min_score}


def resolve_workflow_conflict(conversation, candidate_workflows, tone_text, llm_model):
    """
    Calls an LLM to decide between multiple workflows.
    candidate_workflows is a list of workflow dicts (full objects).
    Returns the workflow name with the highest score.
    """
    # Extract last user message
    last_message = ""
    for msg in reversed(conversation):
        if msg['role'] == 'user':
            last_message = msg['content']
            break
    
    # Prepare conversation string (last 6 messages, excluding the last message if it's already shown separately)
    history_slice = conversation[-6:] if len(conversation) > 6 else conversation
    # Exclude the last message from history since we show it separately
    history_without_last = [msg for msg in history_slice if not (msg['role'] == 'user' and msg['content'] == last_message)]
    conv_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history_without_last])
    
    prompt = prompts.get_workflow_selection_prompt(conv_text, last_message, candidate_workflows, tone_text)

    if DEBUG_MODE:
        print("--- Get Workflow Prompt ---")
        print(prompt)
        print("--------------------------------")

    response = litellm.completion(
        model=llm_model,
        messages=[{"role": "user", "content": prompt}]
    )
    
    response_text = response.choices[0].message.content.strip()

    if DEBUG_MODE:
        print("---agent yaml output---")
        print(response_text)
    
    # Parse YAML response
    try:
        # Extract YAML block if it's wrapped in code fences
        yaml_match = re.search(r'```yaml\s*\n(.*?)\n```', response_text, re.DOTALL)
        if yaml_match:
            yaml_content = yaml_match.group(1)
        else:
            # Try to find YAML without code fences
            yaml_content = response_text
        
        parsed = yaml.safe_load(yaml_content)
        
        if parsed and 'workflows' in parsed and isinstance(parsed['workflows'], list):
            # Find workflow with highest score
            best_workflow = None
            best_score = -1.0
            
            for wf_entry in parsed['workflows']:
                if isinstance(wf_entry, dict) and 'name' in wf_entry and 'score' in wf_entry:
                    score = float(wf_entry['score'])
                    if score > best_score:
                        best_score = score
                        best_workflow = wf_entry['name']
            
            if best_workflow:
                if DEBUG_MODE:
                    print(f"parsed LLM scores: {[(w.get('name'), w.get('score')) for w in parsed['workflows']]}")
                    print(f"selected workflow with highest score: {best_workflow} (score: {best_score:.4f})")
                return best_workflow
    except (yaml.YAMLError, ValueError, KeyError, TypeError) as e:
        if DEBUG_MODE:
            print(f"WARNING: failed to parse YAML response, falling back to text extraction: {e}")
    
    # Fallback: try to extract workflow name from text if YAML parsing failed
    # This handles cases where LLM doesn't follow the format exactly
    for wf in candidate_workflows:
        wf_name = wf['workflow']
        if wf_name in response_text:
            return wf_name
    
    # Last resort: return first candidate
    if candidate_workflows:
        return candidate_workflows[0]['workflow']
    
    return None


def match_workflow(conversation, workflows, tone_text, llm_model, min_score=0.51):
    """
    Orchestrates the full matching process: BM25, Semantic, Filter, and Conflict Resolution.
    Returns the selected workflow object (not just ID) or None.
    """
    # 1. Extract query (last user message)
    # We really only care about the latest user message for the search query, 
    # but semantic search might benefit from context? 
    # Usually search is done on the latest user input.
    # Finding the last user message:
    last_message = ""
    for msg in reversed(conversation):
        if msg['role'] == 'user':
            last_message = msg['content']
            break
            
    if not last_message:
        return None

    # 2. Calculate scores
    bm25_scores = bm25.calculate_bm25_scores(last_message, workflows)
    semantic_scores = semantic.calculate_semantic_scores(last_message, workflows)
    
    # 3. Combine
    combined = combine_scores(bm25_scores, semantic_scores)
    
    if DEBUG_MODE:
        # Log detailed scores for all workflows
        print("--- Workflow Matching Scoring ---")
        all_workflow_names = sorted(set(bm25_scores.keys()) | set(semantic_scores.keys()) | set(combined.keys()))
        for wf_name in all_workflow_names:
            bm25_val = bm25_scores.get(wf_name, 0.0)
            sem_val = semantic_scores.get(wf_name, 0.0)
            final_val = combined.get(wf_name, 0.0)
            print(f"{wf_name}: BM25={bm25_val:.4f}, Semantic={sem_val:.4f}, Final={final_val:.4f}")
        print("-------------------------------------")
    
    # 4. Filter
    passed_threshold = filter_workflows(combined, min_score)
    
    if DEBUG_MODE:
        print(f"{len(passed_threshold)} workflow(s) above threshold (min={min_score})")
    
    candidates = []
    
    if len(passed_threshold) == 1:
        # Exactly one match > threshold
        wf_name = list(passed_threshold.keys())[0]
        if DEBUG_MODE:
            print(f"single match above threshold, selected workflow: {wf_name}")
        return next((w for w in workflows if w['workflow'] == wf_name), None)
        
    elif len(passed_threshold) > 1:
        # Multiple matches > threshold -> LLM decides
        if DEBUG_MODE:
             print(f"multiple matches above threshold: {list(passed_threshold.keys())}")
        candidate_names = list(passed_threshold.keys())
        candidates = [w for w in workflows if w['workflow'] in candidate_names]
        
    else:
        # No matches > threshold -> Fallback: take top 5 highest scorers
        if DEBUG_MODE:
             print(f"no match above threshold (min={min_score}). Using Top 5 fallback.")
        # Sort by score desc
        sorted_by_score = sorted(combined.items(), key=lambda x: x[1], reverse=True)
        top_5 = sorted_by_score[:5]
        candidate_names = [x[0] for x in top_5]
        # Only consider them if they have a non-zero score? 
        # The prompt will handle "none of these" if we allow it, but requirement says "highest scoring one gets selected"
        candidates = [w for w in workflows if w['workflow'] in candidate_names]
        
    # Call LLM for conflict resolution or top-5 selection
    if candidates:
        selected_name = resolve_workflow_conflict(conversation, candidates, tone_text, llm_model)
        
        if DEBUG_MODE:
            print(f"LLM selected workflow: {selected_name}")
        
        # Find the workflow object
        selected_workflow = next((w for w in workflows if w['workflow'] == selected_name), None)
        
        # Validation: check if the name returned by LLM is actually one of the candidates
        # (Fuzzy check or exact check)
        if not selected_workflow:
            # Try to find partial match if LLM messed up exact name
            for cand in candidates:
                if cand['workflow'] in selected_name or selected_name in cand['workflow']:
                    selected_workflow = cand
                    break
        
        return selected_workflow

    return None
