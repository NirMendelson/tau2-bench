# Utility functions for matching user input to workflows

import os
from typing import List, Dict, Any, Tuple, Optional
import yaml
from .litellm_configuration import call_llm
from .matching.workflow_filter import (
    filter_workflows_by_keywords,
    filter_workflows_by_examples,
    combine_matching_results,
    combine_matching_results_with_debug,
    filter_low_combined_scores
)


def match_workflows(
    user_input: str,
    workflows: Dict[str, Dict[str, Any]],
    fuzzy_threshold: float = 0.6,
    semantic_k: int = 5,
    semantic_min_score: float = 0.35,
    min_combined_score: float = 0.0,
    debug: bool = False
) -> Tuple[List[Tuple[str, float]], List[Tuple[str, float]], Optional[Dict[str, Dict[str, Any]]]]:
    # Step 1: Keyword fuzzy matching
    keyword_matches = filter_workflows_by_keywords(
        user_input,
        workflows,
        fuzzy_threshold=fuzzy_threshold
    )
    
    # Step 2: Semantic matching on examples
    semantic_matches = filter_workflows_by_examples(
        user_input,
        workflows,
        k=semantic_k,
        min_score=semantic_min_score
    )
    
    # Step 3: Combine results (with or without debug info)
    if debug:
        all_combined_results, debug_info = combine_matching_results_with_debug(
            keyword_matches,
            semantic_matches,
            min_combined_score=0.0  # Don't filter here, filter explicitly below
        )
    else:
        all_combined_results = combine_matching_results(
            keyword_matches,
            semantic_matches,
            min_combined_score=0.0  # Don't filter here, filter explicitly below
        )
        debug_info = None
    
    # Step 4: Filter by low combined scores
    filtered_results = filter_low_combined_scores(
        all_combined_results,
        min_score_threshold=min_combined_score
    )
    
    return filtered_results, all_combined_results, debug_info


# Format workflows for LLM prompt
def _format_workflows_for_llm(candidate_workflows: Dict[str, Dict[str, Any]]) -> Tuple[List[str], List[str]]:
    workflows_text = []
    workflow_names = []
    for name, workflow_def in candidate_workflows.items():
        when_text = workflow_def.get('when', '')
        if when_text:
            workflows_text.append(f"- {name}: {when_text}")
            workflow_names.append(name)
    return workflows_text, workflow_names


# Parse YAML response from LLM with confidence scores
def _parse_confidence_scores_yaml(response: str, workflow_names: List[str]) -> List[Tuple[str, float]]:
    try:
        yaml_start = response.find('```yaml')
        yaml_end = response.find('```', yaml_start + 7)
        if yaml_start != -1 and yaml_end != -1:
            yaml_str = response[yaml_start + 7:yaml_end].strip()
        else:
            yaml_str = response.strip()
        
        data = yaml.safe_load(yaml_str)
        
        if isinstance(data, list):
            scores = []
            for item in data:
                if isinstance(item, dict):
                    workflow_id = item.get('workflow_id', '')
                    confidence = item.get('confidence', 0.0)
                    if workflow_id in workflow_names:
                        scores.append((workflow_id, float(confidence)))
            return scores
        elif isinstance(data, dict):
            scores = []
            for workflow_id, conf_value in data.items():
                if workflow_id in workflow_names:
                    if isinstance(conf_value, dict):
                        confidence = conf_value.get('confidence', 0.0)
                    else:
                        confidence = float(conf_value) if isinstance(conf_value, (int, float)) else 0.0
                    scores.append((workflow_id, confidence))
            return scores
    except Exception as e:
        print(f"error parsing yaml response: {e}")
    
    return []


# Get confidence scores for all candidate workflows from LLM
def score_workflows_llm(
    user_input: str,
    candidate_workflows: Dict[str, Dict[str, Any]],
    model: str,
    llm_args: Dict[str, Any]
) -> List[Tuple[str, float]]:
    workflows_text, workflow_names = _format_workflows_for_llm(candidate_workflows)
    
    prompt = f"""Given the user input below, assign a confidence score (0.0 to 1.0) to each candidate workflow indicating how relevant it is to the user's request.

User Input: {user_input}

Available Workflows:
{chr(10).join(workflows_text)}

Return your response in YAML format with confidence scores for each workflow:

```yaml
- workflow_id: <workflow_name>
  confidence: <score between 0.0 and 1.0>
- workflow_id: <workflow_name>
  confidence: <score between 0.0 and 1.0>
```

Score all workflows, even if some have low confidence."""

    response = call_llm(prompt, model=model, **llm_args).strip()
    scores = _parse_confidence_scores_yaml(response, workflow_names)
    
    # If parsing failed, return default scores
    if not scores:
        default_score = 0.5
        scores = [(name, default_score) for name in candidate_workflows.keys()]
    
    # Sort by confidence descending
    scores.sort(key=lambda x: x[1], reverse=True)
    
    return scores


# Check if confidence scores meet selection criteria
# For LLM matching: only check gap (no min confidence threshold)
def meets_selection_criteria(
    scored_workflows: List[Tuple[str, float]],
    min_confidence_gap: float = 0.0
) -> bool:
    if not scored_workflows:
        return False
    
    # If only one workflow, it's automatically selected
    if len(scored_workflows) == 1:
        return True
    
    # Check if there's a clear winner (gap between top and second)
    top_confidence = scored_workflows[0][1]
    second_confidence = scored_workflows[1][1]
    confidence_gap = top_confidence - second_confidence
    
    if confidence_gap < min_confidence_gap:
        return False
    
    return True


# Generate clarification question when confidence is low
def generate_clarification_question(
    user_input: str,
    candidate_workflows: Dict[str, Dict[str, Any]],
    model: str,
    llm_args: Dict[str, Any]
) -> str:
    workflows_text = []
    for name, workflow_def in candidate_workflows.items():
        when_text = workflow_def.get('when', '')
        if when_text:
            workflows_text.append(f"- {when_text}")
    
    prompt = f"""The user's request is unclear and could match multiple workflows. Generate a natural, friendly clarification question to help understand what they need.

User Input: {user_input}

Possible workflows:
{chr(10).join(workflows_text)}

Generate a single, concise clarification question that helps identify which workflow the user needs. Examples:
- "Are you asking about our plans, or something else?"
- "Would you like help with coverage details or something else?"

Return ONLY the clarification question, nothing else."""

    response = call_llm(prompt, model=model, **llm_args).strip()
    return response


# Print debug information for workflow matching
def print_matching_debug(
    user_input: str,
    keyword_matches: List[str],
    semantic_matches: List[Tuple[str, float]],
    debug_info: Dict[str, Dict[str, Any]],
    all_workflows: Dict[str, Dict[str, Any]]
) -> None:
    print("\n" + "="*80)
    print("WORKFLOW MATCHING DEBUG")
    print("="*80)
    print(f"\nUser Input: {user_input}\n")
    
    # Show keyword matches
    print(f"Keyword Matches ({len(keyword_matches)} workflows):")
    for workflow_name in keyword_matches:
        keywords = all_workflows.get(workflow_name, {}).get('keywords', [])
        print(f"  ✓ {workflow_name}: keywords={keywords}")
    if not keyword_matches:
        print("  (none)")
    
    # Show semantic matches
    print(f"\nSemantic Matches ({len(semantic_matches)} workflows):")
    semantic_dict = {name: score for name, score in semantic_matches}
    for workflow_name, score in sorted(semantic_matches, key=lambda x: x[1], reverse=True):
        examples = all_workflows.get(workflow_name, {}).get('examples', [])
        print(f"  ✓ {workflow_name}: score={score:.3f}")
        if examples:
            print(f"    Examples: {examples[:2]}")  # Show first 2 examples
    if not semantic_matches:
        print("  (none)")
    
    # Show combined scores with breakdown
    print(f"\nCombined Scores (all workflows):")
    print("-" * 80)
    
    # Sort workflows by combined score
    sorted_workflows = sorted(
        debug_info.items(),
        key=lambda x: x[1]['combined_score'],
        reverse=True
    )
    
    for workflow_name, info in sorted_workflows:
        keyword_status = "YES" if info['keyword_match'] else "NO"
        semantic_str = f"{info['semantic_score']:.3f}" if info['semantic_score'] is not None else "N/A"
        combined_str = f"{info['combined_score']:.3f}"
        
        print(f"\n{workflow_name}:")
        print(f"  Combined Score: {combined_str}")
        print(f"  Keyword Match: {keyword_status}")
        print(f"  Semantic Score: {semantic_str}")
        print(f"  Calculation: {info['explanation']}")
    
    print("\n" + "="*80 + "\n")

