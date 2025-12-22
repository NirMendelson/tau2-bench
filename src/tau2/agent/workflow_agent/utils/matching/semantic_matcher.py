# Semantic matching utilities for example-based workflow filtering

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from typing import List, Tuple, Dict


# Matches queries against examples using semantic similarity
class SemanticMatcher:
    # Initialize the semantic matcher
    def __init__(self, examples: List[str], workflow_names: List[str], model_name: str = "all-mpnet-base-v2"):
        self.model = SentenceTransformer(model_name)
        self.examples = examples
        self.workflow_names = workflow_names
        
        # Pre-encode all examples for efficient matching
        if examples:
            self.emb = self.model.encode(
                examples,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
        else:
            self.emb = np.array([])
    
    # Match a query against examples using semantic similarity
    def match(self, query: str, k: int = 5, min_score: float = 0.35) -> List[Tuple[str, float]]:
        if len(self.examples) == 0:
            return []
        
        # Encode the query
        q = self.model.encode([query], convert_to_numpy=True, normalize_embeddings=True)
        
        # Calculate cosine similarity
        scores = cosine_similarity(q, self.emb)[0]
        
        # Get top k indices
        top_idx = np.argsort(scores)[::-1][:k]
        
        # Build results list and filter by min_score
        results = []
        for i in top_idx:
            score = float(scores[i])
            if score >= min_score:
                workflow_name = self.workflow_names[i]
                results.append((workflow_name, score))
        
        # Reject if nothing is really relevant (best score check)
        if not results:
            return []
        
        best_score = results[0][1]
        if best_score < min_score:
            return []
        
        # Aggregate scores by workflow (take max score per workflow)
        workflow_scores = {}
        for workflow_name, score in results:
            if workflow_name not in workflow_scores or score > workflow_scores[workflow_name]:
                workflow_scores[workflow_name] = score
        
        # Convert back to sorted list
        aggregated_results = sorted(
            workflow_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return aggregated_results


# Extract examples from all workflows
def extract_examples_from_workflows(workflows: Dict) -> Dict[str, List[str]]:
    workflow_examples = {}
    
    for workflow_name, workflow_def in workflows.items():
        examples = workflow_def.get('examples', [])
        if examples:
            workflow_examples[workflow_name] = examples
    
    return workflow_examples


# Create a semantic matcher from workflow examples
def create_semantic_matcher(workflow_examples: Dict[str, List[str]], model_name: str = "all-mpnet-base-v2") -> SemanticMatcher:
    examples = []
    workflow_names = []
    
    for workflow_name, example_list in workflow_examples.items():
        for example in example_list:
            examples.append(example)
            workflow_names.append(workflow_name)
    
    return SemanticMatcher(examples, workflow_names, model_name=model_name)


# Match user input against workflow examples using semantic similarity
def semantic_match_examples(
    user_input: str,
    matcher: SemanticMatcher,
    k: int = 5,
    min_score: float = 0.35
) -> List[Tuple[str, float]]:
    return matcher.match(user_input, k=k, min_score=min_score)

