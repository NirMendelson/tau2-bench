from rapidfuzz import fuzz

# Calculates the fuzzy match score for a single keyword against the query
def calculate_keyword_score(keyword, query):
    k_lower, q_lower = keyword.lower(), query.lower()
    scores = [fuzz.partial_ratio(k_lower, q_lower)]
    
    words = k_lower.split()
    if len(words) > 1:
        for word in words: scores.append(fuzz.partial_ratio(word, q_lower))
    
    return max(scores) / 100.0

# Calculates fuzzy keyword scores for each workflow
def calculate_bm25_scores(query, workflows):
    scores = {}
    for wf in workflows:
        name = wf.get('workflow')
        keywords = wf.get('keywords', [])
        if not keywords:
            scores[name] = 0.0
            continue
        scores[name] = max(calculate_keyword_score(k, query) for k in keywords)
    return scores
