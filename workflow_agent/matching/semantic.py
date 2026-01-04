from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

_model = None

# Lazy load the sentence transformer model
def get_model():
    global _model
    if _model is None: _model = SentenceTransformer('all-mpnet-base-v2')
    return _model

# Calculates semantic similarity scores for each workflow based on examples
def calculate_semantic_scores(query, workflows):
    model = get_model()
    q_emb = model.encode([query])[0].reshape(1, -1)
    scores = {}
    
    for wf in workflows:
        name = wf.get('workflow')
        examples = wf.get('examples', [])
        if not examples:
            scores[name] = 0.0
            continue
            
        ex_embs = model.encode(examples)
        sims = [cosine_similarity(q_emb, e.reshape(1, -1))[0][0] for e in ex_embs]
        scores[name] = max(0.0, min(1.0, max(sims) if sims else 0.0))
        
    return scores
