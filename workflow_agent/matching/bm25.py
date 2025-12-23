from rapidfuzz import fuzz


def calculate_keyword_score(keyword, query):
    """
    Calculates the fuzzy match score for a single keyword against the query.
    If keyword has multiple words, tries both the full phrase and individual words.
    Returns the maximum score (0-1 range).
    """
    # Normalize to lowercase for comparison
    keyword_lower = keyword.lower()
    query_lower = query.lower()
    
    scores = []
    
    # Score for the full keyword phrase
    full_score = fuzz.partial_ratio(keyword_lower, query_lower)
    scores.append(full_score)
    
    # If keyword has multiple words, also try each word separately
    words = keyword_lower.split()
    if len(words) > 1:
        for word in words:
            word_score = fuzz.partial_ratio(word, query_lower)
            scores.append(word_score)
    
    # Return the maximum score normalized to 0-1
    return max(scores) / 100.0


def calculate_bm25_scores(query, workflows):
    """
    Calculates BM25-style scores for each workflow based on the 'keywords' field.
    Uses fuzzy matching instead of traditional BM25.
    Returns a dictionary of workflow_name: score (0-1 range).
    """
    scores = {}
    
    for workflow in workflows:
        workflow_name = workflow.get('workflow')
        keywords = workflow.get('keywords', [])
        
        if not keywords:
            scores[workflow_name] = 0.0
            continue
        
        # Calculate score for each keyword and take the maximum
        keyword_scores = []
        for keyword in keywords:
            score = calculate_keyword_score(keyword, query)
            keyword_scores.append(score)
        
        # The workflow score is the maximum score across all keywords
        scores[workflow_name] = max(keyword_scores) if keyword_scores else 0.0
    
    return scores
