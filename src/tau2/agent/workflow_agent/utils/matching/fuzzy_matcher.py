from typing import Dict, List
from rapidfuzz import fuzz, process


# Extract keywords from all workflows
def extract_keywords_from_workflows(workflows: Dict) -> Dict[str, List[str]]:
    workflow_keywords = {}
    
    for workflow_name, workflow_def in workflows.items():
        keywords = workflow_def.get('keywords', [])
        if keywords:
            # Strip whitespace from each keyword to handle YAML formatting issues
            cleaned_keywords = [keyword.strip() for keyword in keywords if keyword.strip()]
            if cleaned_keywords:
                workflow_keywords[workflow_name] = cleaned_keywords
    
    return workflow_keywords


# Match user input against workflow keywords using fuzzy matching
def fuzzy_match_keywords(
    user_input: str,
    workflow_keywords: Dict[str, List[str]],
    threshold: float = 0.6
) -> List[str]:
    if not workflow_keywords or not user_input:
        return []
    
    matched_workflows = []
    user_input_lower = user_input.lower()
    
    for workflow_name, keywords in workflow_keywords.items():
        # Check if any keyword matches the user input
        for keyword in keywords:
            keyword_lower = keyword.lower()
            
            # First, check for exact substring match (most reliable)
            if keyword_lower in user_input_lower:
                matched_workflows.append(workflow_name)
                break  # Only need one keyword match per workflow
            
            # Only use fuzzy matching if no exact match found
            # For multi-word keywords, check if all words appear in order
            if ' ' in keyword_lower:
                keyword_words = keyword_lower.split()
                # Check if all words appear (in any order)
                if all(word in user_input_lower for word in keyword_words):
                    # Use token_sort_ratio to verify words are close together
                    ratio = fuzz.token_sort_ratio(user_input_lower, keyword_lower)
                    if ratio >= (threshold * 100):
                        matched_workflows.append(workflow_name)
                        break
            else:
                # For single-word keywords, only use fuzzy matching with very high threshold
                # to avoid false positives (e.g., "falck" matching "afghanistan")
                # Require at least 90% similarity for single words
                ratio = fuzz.partial_ratio(user_input_lower, keyword_lower)
                if ratio >= 90.0:  # Very high threshold for single words
                    matched_workflows.append(workflow_name)
                    break
    
    return matched_workflows

