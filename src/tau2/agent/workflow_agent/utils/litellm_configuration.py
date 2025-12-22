from typing import Any, Optional
from loguru import logger
from tau2.data_model.message import UserMessage
from tau2.utils.llm_utils import generate


def call_llm(prompt: str, model: str, **llm_args) -> str:
    """
    Call LLM using tau2's standard generate utility.
    
    Args:
        prompt: The prompt to send to the LLM
        model: Model name to use
        **llm_args: Additional arguments for the LLM (temperature, etc.)
        
    Returns:
        The text response from the LLM
    """
    if not model:
        logger.error("No model specified for LLM call")
        return ""
        
    # Create simple user message from prompt
    messages = [UserMessage(role="user", content=prompt)]
    
    try:
        # Use tau2's standard generation mechanism which handles LiteLLM internally
        # but with tau2-specific features like caching and error handling
        response_msg = generate(model=model, messages=messages, **llm_args)
        return response_msg.content or ""
    except Exception as e:
        logger.error(f"Error in LLM call: {e}")
        return ""


def call_litellm(prompt: str, model: Optional[str] = None) -> str:
    """
    Backward compatibility wrapper for call_litellm.
    WARNING: This should be phased out in favor of call_llm that takes explicit model.
    """
    if model is None:
        import os
        model = os.environ.get("LITELLM_MODEL", "").strip()
        
    return call_llm(prompt, model or "unknown")
