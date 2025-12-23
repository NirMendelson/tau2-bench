from . import bm25, semantic
from ..actions import prompts
import litellm
import os
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
    """
    # Prepare conversation string (last 6 messages)
    history_slice = conversation[-6:] if len(conversation) > 6 else conversation
    conv_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history_slice])
    
    prompt = prompts.get_workflow_selection_prompt(conv_text, candidate_workflows, tone_text)
    
    if DEBUG_MODE:
        logger.info(f"DEBUG PROMPT (workflow_selection): {prompt}")

    response = litellm.completion(
        model=llm_model,
        messages=[{"role": "user", "content": prompt}]
    )
    
    selected_name = response.choices[0].message.content.strip()
    return selected_name


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
        sorted_scores = dict(sorted(combined.items(), key=lambda x: x[1], reverse=True)[:10])
        logger.info(f"DEBUG MATCH SCORES (Top 10): {sorted_scores}")
    
    # 4. Filter
    passed_threshold = filter_workflows(combined, min_score)
    
    candidates = []
    
    if len(passed_threshold) == 1:
        # Exactly one match > threshold
        wf_name = list(passed_threshold.keys())[0]
        return next((w for w in workflows if w['workflow'] == wf_name), None)
        
    elif len(passed_threshold) > 1:
        # Multiple matches > threshold -> LLM decides
        if DEBUG_MODE:
             logger.info(f"Multiple matches above threshold: {list(passed_threshold.keys())}")
        candidate_names = list(passed_threshold.keys())
        candidates = [w for w in workflows if w['workflow'] in candidate_names]
        
    else:
        # No matches > threshold -> Fallback: take top 5 highest scorers
        if DEBUG_MODE:
             logger.info("No match above threshold. Using Top 5 fallback.")
        # Sort by score desc
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
