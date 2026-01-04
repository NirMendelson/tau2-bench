import litellm
import os
import yaml
import re
from loguru import logger
from . import bm25, semantic
from ..actions import prompts

DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

# Combines BM25 and semantic scores using weighted average (0.3/0.7)
def combine_scores(bm25_scores, semantic_scores):
    combined = {}
    all_workflows = set(bm25_scores.keys()) | set(semantic_scores.keys())
    for wf in all_workflows:
        s_bm25 = bm25_scores.get(wf, 0.0)
        s_sem = semantic_scores.get(wf, 0.0)
        combined[wf] = 0.3 * s_bm25 + 0.7 * s_sem
    return combined

# Filters out workflows that do not meet the minimum score threshold
def filter_workflows(workflows_with_scores, min_score):
    return {wf: score for wf, score in workflows_with_scores.items() if score > min_score}

# Calls an LLM to decide between multiple workflow candidates
def resolve_workflow_conflict(conversation, candidate_workflows, tone_text, llm_model, current_workflow_name=None):
    last_message = next((m['content'] for m in reversed(conversation) if m['role'] == 'user'), "")
    history = conversation[-6:] if len(conversation) > 6 else conversation
    history_text = "\n".join([f"{m['role']}: {m['content']}" for m in history if not (m['role'] == 'user' and m['content'] == last_message)])
    
    prompt = prompts.get_workflow_selection_prompt(history_text, last_message, candidate_workflows, tone_text, current_workflow_name)
    response = litellm.completion(model=llm_model, messages=[{"role": "user", "content": prompt}])
    text = response.choices[0].message.content.strip()

    try:
        match = re.search(r'```yaml\s*\n(.*?)\n```', text, re.DOTALL)
        content = match.group(1) if match else text
        parsed = yaml.safe_load(content)
        
        if parsed and 'workflows' in parsed:
            best_wf, best_score = None, -1.0
            scores = {}
            for wf in parsed['workflows']:
                wf_name = wf.get('name', '')
                score = float(wf.get('score', 0))
                scores[wf_name] = score
                if score > best_score:
                    best_score = score
                    best_wf = wf_name
            
            if best_wf: return best_wf
    except Exception:
        pass

    for wf in candidate_workflows:
        if wf['workflow'] in text: return wf['workflow']
    return candidate_workflows[0]['workflow'] if candidate_workflows else None

# Orchestrates full matching: BM25, Semantic search, filtering, and LLM resolution
def match_workflow(conversation, workflows, tone_text, llm_model, min_score=0, current_workflow_name=None):
    last_message = next((m['content'] for m in reversed(conversation) if m['role'] == 'user'), None)
    if not last_message: return None

    bm25_scores = bm25.calculate_bm25_scores(last_message, workflows)
    semantic_scores = semantic.calculate_semantic_scores(last_message, workflows)
    combined = combine_scores(bm25_scores, semantic_scores)
    
    # Log all workflow scores in one line
    scores_str = ", ".join([f"{wf_name}: {score:.3f}" for wf_name, score in sorted(combined.items(), key=lambda x: x[1], reverse=True)])
    logger.info(f"workflow scores: [{scores_str}]")
    
    passed = filter_workflows(combined, min_score)
    candidates = []

    if len(passed) == 1:
        wf_name = list(passed.keys())[0]
        if wf_name == "HandleGenericMessage":
            return next((w for w in workflows if w['workflow'] == wf_name), None)
        candidates = [next((w for w in workflows if w['workflow'] == wf_name))]
    elif len(passed) > 1:
        candidates = [w for w in workflows if w['workflow'] in passed]
    else:
        top_5 = sorted(combined.items(), key=lambda x: x[1], reverse=True)[:5]
        candidates = [w for w in workflows if w['workflow'] in [x[0] for x in top_5]]

    generic = next((w for w in workflows if w['workflow'] == "HandleGenericMessage"), None)
    if generic and not any(c['workflow'] == "HandleGenericMessage" for c in candidates):
        candidates.append(generic)

    if candidates:
        sel_name = resolve_workflow_conflict(conversation, candidates, tone_text, llm_model, current_workflow_name)
        res = next((w for w in workflows if w['workflow'] == sel_name), None)
        if not res: # Fallback to fuzzy match
            for c in candidates:
                if c['workflow'] in str(sel_name) or str(sel_name) in c['workflow']: return c
        if res:
            logger.info(f"chosen workflow: {res['workflow']}")
        return res
    return None
