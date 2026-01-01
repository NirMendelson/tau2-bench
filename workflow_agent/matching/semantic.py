from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np


# Initialize the model (will be loaded once when module is imported)
_model = None


def get_model():
    """Lazy load the sentence transformer model."""
    global _model
    if _model is None:
        _model = SentenceTransformer('all-mpnet-base-v2')
    return _model


def calculate_semantic_scores(query, workflows):
    """
    Calculates semantic similarity scores for each workflow based on the 'examples' field.
    Uses sentence-transformers with cosine similarity.
    Returns a dictionary of workflow_name: score (0-1 range).
    """
    model = get_model()
    scores = {}
    
    # Embed the query once
    query_embedding = model.encode([query])[0]
    
    for workflow in workflows:
        workflow_name = workflow.get('workflow')
        examples = workflow.get('examples', [])
        
        if not examples:
            scores[workflow_name] = 0.0
            continue
        
        # Embed all examples for this workflow
        example_embeddings = model.encode(examples)
        
        # Calculate cosine similarity between query and each example
        similarities = []
        for example_embedding in example_embeddings:
            # Reshape for sklearn cosine_similarity
            sim = cosine_similarity(
                query_embedding.reshape(1, -1),
                example_embedding.reshape(1, -1)
            )[0][0]
            similarities.append(sim)
        
        # Take the maximum similarity across all examples
        # Cosine similarity is already in [-1, 1] range, but typically [0, 1] for similar texts
        # We'll clip to [0, 1] to be safe
        max_similarity = max(similarities) if similarities else 0.0
        scores[workflow_name] = max(0.0, min(1.0, max_similarity))
    
    return scores
