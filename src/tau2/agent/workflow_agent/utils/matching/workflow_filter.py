# Workflow filtering utilities that combine fuzzy and semantic matching

from typing import List, Tuple, Dict, Optional, Any
from .fuzzy_matcher import extract_keywords_from_workflows, fuzzy_match_keywords
from .semantic_matcher import extract_examples_from_workflows, create_semantic_matcher, semantic_match_examples


# Filter workflows using fuzzy keyword matching
def filter_workflows_by_keywords(
    user_input: str,
    workflows: Dict,
    fuzzy_threshold: float = 0.6
) -> List[str]:
    workflow_keywords = extract_keywords_from_workflows(workflows)
    return fuzzy_match_keywords(user_input, workflow_keywords, fuzzy_threshold)


# Filter workflows using semantic example matching
def filter_workflows_by_examples(
    user_input: str,
    workflows: Dict,
    k: int = 5,
    min_score: float = 0.35
) -> List[Tuple[str, float]]:
    workflow_examples = extract_examples_from_workflows(workflows)
    
    if not workflow_examples:
        return []
    
    matcher = create_semantic_matcher(workflow_examples)
    return semantic_match_examples(user_input, matcher, k=k, min_score=min_score)


# Combine keyword and semantic matching results (workflows in both lists get higher priority)
def combine_matching_results(
    keyword_matches: List[str],
    semantic_matches: List[Tuple[str, float]],
    min_combined_score: float = 0.3
) -> List[Tuple[str, float]]:
    # Create a set of keyword-matched workflows for fast lookup
    keyword_set = set(keyword_matches)
    
    # Build combined results
    combined_scores = {}
    
    # Process semantic matches
    for workflow_name, score in semantic_matches:
        # Boost score if also matched by keywords
        if workflow_name in keyword_set:
            combined_score = min(1.0, score * 1.2)  # 20% boost
        else:
            combined_score = score
        
        combined_scores[workflow_name] = combined_score
    
    # Add keyword-only matches (workflows with keywords but no semantic match)
    for workflow_name in keyword_matches:
        if workflow_name not in combined_scores:
            # Give a base score for keyword-only matches
            combined_scores[workflow_name] = 0.5
    
    # Filter by min_combined_score and sort
    filtered_results = [
        (name, score)
        for name, score in combined_scores.items()
        if score >= min_combined_score
    ]
    
    filtered_results.sort(key=lambda x: x[1], reverse=True)
    
    return filtered_results


# Combine matching results with debug information
def combine_matching_results_with_debug(
    keyword_matches: List[str],
    semantic_matches: List[Tuple[str, float]],
    min_combined_score: float = 0.3
) -> Tuple[List[Tuple[str, float]], Dict[str, Dict[str, any]]]:
    keyword_set = set(keyword_matches)
    
    # Create a dict mapping workflow names to semantic scores
    semantic_score_dict = {name: score for name, score in semantic_matches}
    
    # Build combined results and debug info
    combined_scores = {}
    debug_info = {}
    
    # Process semantic matches
    for workflow_name, semantic_score in semantic_matches:
        has_keyword_match = workflow_name in keyword_set
        
        if has_keyword_match:
            combined_score = min(1.0, semantic_score * 1.2)  # 20% boost
            explanation = f"semantic_score={semantic_score:.3f} * 1.2 (keyword boost) = {combined_score:.3f}"
        else:
            combined_score = semantic_score
            explanation = f"semantic_score={semantic_score:.3f} (no keyword match)"
        
        combined_scores[workflow_name] = combined_score
        debug_info[workflow_name] = {
            'keyword_match': has_keyword_match,
            'semantic_score': semantic_score,
            'combined_score': combined_score,
            'explanation': explanation
        }
    
    # Add keyword-only matches (workflows with keywords but no semantic match)
    for workflow_name in keyword_matches:
        if workflow_name not in combined_scores:
            combined_score = 0.5
            combined_scores[workflow_name] = combined_score
            debug_info[workflow_name] = {
                'keyword_match': True,
                'semantic_score': None,
                'combined_score': combined_score,
                'explanation': "keyword_only_match = 0.5 (no semantic match above threshold)"
            }
    
    # Filter by min_combined_score and sort
    filtered_results = [
        (name, score)
        for name, score in combined_scores.items()
        if score >= min_combined_score
    ]
    
    filtered_results.sort(key=lambda x: x[1], reverse=True)
    
    return filtered_results, debug_info


# Filter out workflows with low combined scores
def filter_low_combined_scores(
    combined_results: List[Tuple[str, float]],
    min_score_threshold: float = 0.3
) -> List[Tuple[str, float]]:
    filtered = [
        (name, score)
        for name, score in combined_results
        if score >= min_score_threshold
    ]
    return filtered

