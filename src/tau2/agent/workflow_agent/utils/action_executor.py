import os
import uuid
from typing import Dict, List, Any, Optional
import yaml
from .litellm_configuration import call_llm
from loguru import logger

# This file contains the functions to execute the different actions in the workflow- Fetch, Conditional, Reply, Use Tool, Include


def _is_debugging_enabled():
    """Check if DEBUGGING_MODE is enabled from environment variables."""
    return os.environ.get("DEBUGGING_MODE", "").lower() in ("true", "1", "yes")


def execute_fetch(
    step: Dict[str, Any], 
    conversation_history: List[Dict[str, str]], 
    model: str, 
    llm_args: Dict[str, Any]
) -> Dict[str, Any]:
    field_name = step.get('field', '')
    fields = step.get('fields', [])
    if field_name and not fields:
        fields = [field_name]
    elif isinstance(fields, str):
        # Handle cases like "passengers_details (first_name, last_name, date_of_birth)"
        fields = [fields]

    fields_str = ", ".join([f"'{f}'" for f in fields])
    
    # Format conversation for LLM
    conv_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation_history])
    
    prompt = f"""You are an intelligence agent. You have great capabilities to read between the lines and infer information. 
Read the conversation carefully and check if you have the following fields in the conversation, or can infer them from the conversation: {fields_str}

You should infer information whenever possible, even if it is only implied indirectly.
Treat the conversation like a detective: if a human could reasonably infer the answer, you should too.

TASK:
1. For each field, check if the information was mentioned in the conversation history.
2. You are intelligence agent. Think like a human reading between the lines: infer information whenever it is implied, even if not stated directly.
3. PRIORITY:
   (1) Prefer explicit statements.
   (2) If not explicit, infer the value from context if a reasonable human would.
   (3) Only if it is neither explicit nor inferable, mark it as not found and provide a question to ask the user.
4. Normalize the user's meaning into the most appropriate value for this field — the wording does not need to match exactly.
5. If multiple fields are missing, provide a single combined question to ask the user for all missing information.

EXAMPLES OF INFERENCE:
- "I sent the package yesterday." → They have a tracking number or proof of shipment.
- "I'll reboot the server." → They have admin access to that server.
- "I'll check the security camera." → They have a camera system installed.
- "The landlord raised the price again." → They're renting (not owning).
- "I'm not been able to enter the YouTube app, and the rest of my apps work fine." → They have a problem with the YouTube app and its not a WIFI or hardware issue, because the rest work well.


Conversation:
{conv_text}


Respond in this format:
```yaml
fields:
  field_name_1:
    found: true/false
    value: <extracted value if found>
  field_name_2:
    found: true/false
    value: <extracted value if found>
question: <single question to ask for all missing fields, null if all found>
```"""

    if _is_debugging_enabled():
        print(f"[DEBUG] fetch prompt:\n{prompt}\n")
    
    response = call_llm(prompt, model=model, **llm_args)
    
    if _is_debugging_enabled():
        print(f"[DEBUG] fetch response:\n{response}\n")
    
    # Parse YAML response
    try:
        yaml_start = response.find('```yaml')
        yaml_end = response.find('```', yaml_start + 7)
        if yaml_start != -1 and yaml_end != -1:
            yaml_str = response[yaml_start + 7:yaml_end].strip()
            result = yaml.safe_load(yaml_str)
        else:
            # Try to parse without code fences
            result = yaml.safe_load(response)
        
        extracted_fields_result = result.get('fields', {}) if isinstance(result, dict) else {}
        question = result.get('question', '') if isinstance(result, dict) else ''
        
        # If any field is missing, add question to conversation history
        all_found = True
        for f in fields:
            if not extracted_fields_result.get(f, {}).get('found', False):
                all_found = False
                break
        
        if not all_found and question:
            # Add question to conversation history
            conversation_history.append({
                "role": "assistant",
                "content": question
            })
        
        result_dict = {
            "fields": extracted_fields_result,
            "found": all_found,
            "question": question
        }
        
        # For backward compatibility with single field
        if field_name and field_name in extracted_fields_result:
            result_dict["field_name"] = field_name
            result_dict["found"] = extracted_fields_result[field_name].get("found", False)
            result_dict["value"] = extracted_fields_result[field_name].get("value", "")
            
        if _is_debugging_enabled():
            print(f"[DEBUG] fetch result: {result_dict}\n")
        return result_dict
    except Exception as e:
        print(f"error parsing fetch response: {e}")
        # Fallback: ask for the fields
        question = f"Could you please provide: {', '.join(fields)}?"
        conversation_history.append({
            "role": "assistant",
            "content": question
        })
        fallback_fields = {f: {"found": False, "value": ""} for f in fields}
        return {
            "fields": fallback_fields,
            "found": False,
            "question": question,
            "field_name": field_name,
            "value": ""
        }


def execute_fetch_with_condition(
    fetch_step: Dict[str, Any],
    condition_step: Dict[str, Any],
    conversation_history: List[Dict[str, str]],
    extracted_fields: Dict[str, str],
    model: str,
    llm_args: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Combined fetch and condition evaluation in a single LLM prompt.
    This is more efficient when fetch is immediately followed by a condition check.
    """
    field_name = fetch_step.get('field', '')
    fields = fetch_step.get('fields', [])
    if field_name and not fields:
        fields = [field_name]
    elif isinstance(fields, str):
        fields = [fields]
        
    condition = condition_step.get('condition', {})
    
    # Format conversation for LLM
    conv_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation_history])
    
    # Format condition for LLM
    operator = condition.get('operator', '')
    left = condition.get('left', '')
    right = condition.get('right', '')
    field = condition.get('field', '')
    
    # Extract field name from template variable in left if it's a template
    field_names_from_left = []
    left_str = str(left).strip()
    if left_str.startswith("{{") and left_str.endswith("}}"):
        # Extract field name from template like "{{ field_name }}"
        field_names_from_left.append(left_str.replace("{{", "").replace("}}", "").strip())
    
    # Resolve template variables in left and right (using already extracted fields)
    resolved_left = str(left)
    for f_name, field_val in extracted_fields.items():
        resolved_left = resolved_left.replace(f"{{{{ {f_name} }}}}", str(field_val))
        resolved_left = resolved_left.replace(f"{{{{{ {f_name} }}}}}", str(field_val))
        right = str(right).replace(f"{{{{ {f_name} }}}}", str(field_val))
        right = str(right).replace(f"{{{{{ {f_name} }}}}}", str(field_val))
    
    # Determine the field name and value to display
    condition_str = f"{resolved_left} {operator} {right}"
    if field:
        condition_str = f"{field} {operator} {right}"
    
    fields_str = ", ".join([f"'{f}'" for f in fields])
    
    prompt = f"""You are an intelligence agent. You have great capabilities to read between the lines and infer information. 

TASK 1: FETCH FIELDS
Read the conversation carefully and check if you have the following fields in the conversation, or can infer them from the conversation: {fields_str}

You should infer information whenever possible, even if it is only implied indirectly.
Treat the conversation like a detective: if a human could reasonably infer the answer, you should too.

PRIORITY:
(1) Prefer explicit statements.
(2) If not explicit, infer the value from context if a reasonable human would.
(3) Only if it is neither explicit nor inferable, mark it as not found and provide a question to ask the user.

Normalize the user's meaning into the most appropriate value for this field — the wording does not need to match exactly.

TASK 2: EVALUATE CONDITION (only if all required fields for the condition are found)
Evaluate this condition: {condition_str}

IMPORTANT INSTRUCTIONS FOR CONDITION EVALUATION:
- The condition "{condition_str}" may reference the fields that you just extracted.
- Use the actual values you extracted in TASK 1 when evaluating the condition.
- Use your intelligence to determine if the condition is true or false, don't do a simple string comparison.
- Examples: California = CA is true, yes = yeah = I think so = any other phrase with basic meaning of yes

Conversation:
{conv_text}

Respond in this format:
```yaml
fields:
  field_name_1:
    found: true/false
    value: <extracted value if found>
  field_name_2:
    found: true/false
    value: <extracted value if found>
question: <single question to ask for all missing fields, null if all found>
condition_result: <true/false if required fields found, null otherwise>
```"""

    if _is_debugging_enabled():
        print(f"[DEBUG] fetch_with_condition prompt:\n{prompt}\n")
    
    response = call_llm(prompt, model=model, **llm_args)
    
    if _is_debugging_enabled():
        print(f"[DEBUG] fetch_with_condition response:\n{response}\n")
    
    # Parse YAML response
    try:
        yaml_start = response.find('```yaml')
        yaml_end = response.find('```', yaml_start + 7)
        if yaml_start != -1 and yaml_end != -1:
            yaml_str = response[yaml_start + 7:yaml_end].strip()
            result = yaml.safe_load(yaml_str)
        else:
            # Try to parse without code fences
            result = yaml.safe_load(response)
        
        extracted_fields_result = result.get('fields', {}) if isinstance(result, dict) else {}
        question = result.get('question', '') if isinstance(result, dict) else ''
        condition_result = result.get('condition_result') if isinstance(result, dict) else None
        
        # Convert condition_result to boolean if it's a string
        if isinstance(condition_result, str):
            condition_result = condition_result.lower() == "true"
        
        # If any field is missing, add question to conversation history
        all_found = True
        for f in fields:
            if not extracted_fields_result.get(f, {}).get('found', False):
                all_found = False
                break
        
        if not all_found and question:
            # Add question to conversation history
            conversation_history.append({
                "role": "assistant",
                "content": question
            })
        
        result_dict = {
            "fields": extracted_fields_result,
            "found": all_found,
            "question": question,
            "condition_result": condition_result
        }
        
        # For backward compatibility
        if field_name and field_name in extracted_fields_result:
            result_dict["field_name"] = field_name
            result_dict["found"] = extracted_fields_result[field_name].get("found", False)
            result_dict["value"] = extracted_fields_result[field_name].get("value", "")
            
        if _is_debugging_enabled():
            print(f"[DEBUG] fetch_with_condition result: {result_dict}\n")
        return result_dict
    except Exception as e:
        print(f"error parsing fetch_with_condition response: {e}")
        # Fallback: ask for the fields
        question = f"Could you please provide: {', '.join(fields)}?"
        conversation_history.append({
            "role": "assistant",
            "content": question
        })
        fallback_fields = {f: {"found": False, "value": ""} for f in fields}
        return {
            "fields": fallback_fields,
            "found": False,
            "question": question,
            "condition_result": None,
            "field_name": field_name,
            "value": ""
        }



def evaluate_condition(
    condition: Dict[str, Any], 
    conversation_history: List[Dict[str, str]], 
    extracted_fields: Dict[str, str],
    model: str,
    llm_args: Dict[str, Any]
) -> bool:
    # Format conversation for LLM
    conv_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation_history])
    
    # Format condition for LLM
    operator = condition.get('operator', '')
    left = condition.get('left', '')
    right = condition.get('right', '')
    field = condition.get('field', '')
    
    # Extract field name from template variable in left if it's a template
    field_name_from_left = None
    left_str = str(left).strip()
    if left_str.startswith("{{") and left_str.endswith("}}"):
        # Extract field name from template like "{{ field_name }}"
        field_name_from_left = left_str.replace("{{", "").replace("}}", "").strip()
    
    # Resolve template variables in left and right
    resolved_left = str(left)
    for field_name, field_val in extracted_fields.items():
        resolved_left = resolved_left.replace(f"{{{{ {field_name} }}}}", str(field_val))
        resolved_left = resolved_left.replace(f"{{{{{ {field_name} }}}}}", str(field_val))
        right = str(right).replace(f"{{{{ {field_name} }}}}", str(field_val))
        right = str(right).replace(f"{{{{{ {field_name} }}}}}", str(field_val))
    
    # Determine the field name and value to display
    display_field_name = field or field_name_from_left
    field_value = None
    if display_field_name and display_field_name in extracted_fields:
        field_value = extracted_fields[display_field_name]
    elif field_name_from_left and field_name_from_left in extracted_fields:
        field_value = extracted_fields[field_name_from_left]
    
    # Build condition string and field info
    if display_field_name and field_value is not None:
        condition_str = f"{display_field_name} {operator} {right}"
        field_info = f"Field '{display_field_name}' has value: {field_value}"
    else:
        condition_str = f"{resolved_left} {operator} {right}"
        field_info = f"Left side value: {resolved_left}"
    
    prompt = f"""You are an intelligence agent. Evaluate this condition based on the field value and conversation context.

{field_info}

Condition to evaluate: {condition_str}

Conversation history (for context):
{conv_text}

TASK: Determine if the condition "{condition_str}" is true or false.

CRITICAL: Use your intelligence to determine if the condition is true or false, don't do a simple string comparison.
- California = CA is true
- yes = yeah = I think so = any other phrase with basic meaning of yes


Evaluate the condition and return ONLY "true" or "false" (lowercase, no quotes, no explanation)."""

    if _is_debugging_enabled():
        print(f"[DEBUG] condition prompt:\n{prompt}\n")
    
    response = call_llm(prompt, model=model, **llm_args).strip().lower()
    
    if _is_debugging_enabled():
        print(f"[DEBUG] condition response: {response}\n")
    
    result = response == "true"
    
    if _is_debugging_enabled():
        print(f"[DEBUG] condition result: {result}\n")
    
    return result


def execute_reply(
    step: Dict[str, Any], 
    conversation_history: List[Dict[str, str]], 
    tone_config: Dict[str, Any], 
    extracted_fields: Dict[str, str],
    model: str,
    llm_args: Dict[str, Any]
) -> str:
    message_template = step.get('message', '')
    
    # Replace template variables with extracted values
    for field_name, field_value in extracted_fields.items():
        message_template = message_template.replace(f"{{{{ {field_name} }}}}", str(field_value))
        message_template = message_template.replace(f"{{{{{ {field_name} }}}}}", str(field_value))
    
    # Format entire tone config into a single tone_text string
    tone_parts = []
    
    # Add identity section
    identity = tone_config.get('identity', {})
    if identity:
        tone_parts.append("Identity:")
        if identity.get('role'):
            tone_parts.append(f"  Role: {identity.get('role')}")
        if identity.get('positioning'):
            tone_parts.append(f"  Positioning: {identity.get('positioning')}")
        tone_parts.append("")
    
    # Add tone section
    tone_list = tone_config.get('tone', [])
    if tone_list:
        tone_parts.append("Tone:")
        for t in tone_list:
            tone_parts.append(f"  - {t}")
        tone_parts.append("")
    
    # Add guidelines section
    guidelines = tone_config.get('guidelines', [])
    if guidelines:
        tone_parts.append("Guidelines:")
        for g in guidelines:
            tone_parts.append(f"  - {g}")
    
    tone_text = "\n".join(tone_parts)
    
    # Format conversation history
    conversation_context = chr(10).join([f"{msg['role']}: {msg['content']}" for msg in conversation_history[-3:]])
    
    prompt = f"""You need to tell the user this reply message: {message_template}

Generate the response using the tone below:
{tone_text}

Read the conversation history to answer correctly in context:
{conversation_context}

CRITICAL:
- Keep the reply message as is, don't change it.
- Do not change the reply message, just apply the tone and make the message fit the conversation history.
- Apply the tone and make the message fit the conversation history. 
- Don't add information that is not in the reply message.
- Don't leave out any information that is in the reply message.
Return ONLY the reply message, nothing else."""

    if _is_debugging_enabled():
        print(f"[DEBUG] reply prompt:\n{prompt}\n")
    
    reply = call_llm(prompt, model=model, **llm_args).strip()
    
    if _is_debugging_enabled():
        print(f"[DEBUG] reply response:\n{reply}\n")
    
    # Add reply to conversation history
    conversation_history.append({
        "role": "assistant",
        "content": reply
    })
    
    if _is_debugging_enabled():
        print(f"[DEBUG] reply result: {reply}\n")
    
    return reply


def prepare_tool_call(
    step: Dict[str, Any],
    extracted_fields: Optional[Dict[str, str]] = None,
    tools: Optional[List] = None
) -> Dict[str, Any]:
    """
    Prepare a tool call without executing it.
    Returns tool call information that can be added to conversation_history.
    
    Args:
        step: Workflow step with action="use_tool"
        extracted_fields: Fields extracted during workflow execution
        tools: List of available tools
        
    Returns:
        Dict with tool call information:
        {
            "tool_name": str,
            "tool_arguments": dict,
            "tool_call_id": str,
            "prepared": bool,
            "error": Optional[str]
        }
    """
    tool_name = step.get('tool_name', '')
    
    # Check if tool exists
    if tools is None:
        return {
            "tool_name": tool_name,
            "tool_arguments": {},
            "tool_call_id": "",
            "prepared": False,
            "error": "no tools provided"
        }
    
    # Find the tool
    tool = None
    for t in tools:
        if t.name == tool_name:
            tool = t
            break
    
    if tool is None:
        return {
            "tool_name": tool_name,
            "tool_arguments": {},
            "tool_call_id": "",
            "prepared": False,
            "error": f"tool '{tool_name}' not found"
        }
    
    # Extract tool arguments from step
    from ..convert_to_tau_utils.tool_converter import extract_tool_arguments_from_step
    
    if extracted_fields is None:
        extracted_fields = {}
    
    tool_arguments = extract_tool_arguments_from_step(step, extracted_fields)
    
    # Generate unique tool call ID
    tool_call_id = f"call_{uuid.uuid4().hex[:8]}"
    
    return {
        "tool_name": tool_name,
        "tool_arguments": tool_arguments,
        "tool_call_id": tool_call_id,
        "prepared": True,
        "error": None
    }


def execute_tool(
    step: Dict[str, Any],
    conversation_history: Optional[List[Dict[str, str]]] = None,
    tone_config: Optional[Dict[str, Any]] = None,
    tools: Optional[List] = None,
    extracted_fields: Optional[Dict[str, str]] = None,
    model: Optional[str] = None,
    llm_args: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Prepare a tool call for orchestrator execution (does not execute synchronously).
    For escalation tool, generates a message directly.
    
    Args:
        step: Workflow step with action="use_tool"
        conversation_history: Conversation history (used for escalation tool)
        tone_config: Tone configuration (used for escalation tool)
        tools: List of available tools
        extracted_fields: Fields extracted during workflow execution
        
    Returns:
        Dict with tool call preparation result:
        {
            "tool_name": str,
            "prepared": bool,
            "tool_call_info": Optional[dict],  # Tool call info if prepared
            "executed": bool,  # True only for escalation tool
            "result": Optional[Any],  # Result only for escalation tool
            "error": Optional[str]
        }
    """
    tool_name = step.get('tool_name', '')
    reason = step.get('reason', '')
    
    # If escalation tool, generate a message about transferring to human agent
    # (This is a special case that doesn't use actual τ²-bench tools)
    if tool_name == "escalation" and conversation_history is not None and tone_config is not None:
        # Format entire tone config into a single tone_text string (same as execute_reply)
        tone_parts = []
        
        # Add identity section
        identity = tone_config.get('identity', {})
        if identity:
            tone_parts.append("Identity:")
            if identity.get('role'):
                tone_parts.append(f"  Role: {identity.get('role')}")
            if identity.get('positioning'):
                tone_parts.append(f"  Positioning: {identity.get('positioning')}")
            tone_parts.append("")
        
        # Add tone section
        tone_list = tone_config.get('tone', [])
        if tone_list:
            tone_parts.append("Tone:")
            for t in tone_list:
                tone_parts.append(f"  - {t}")
            tone_parts.append("")
        
        # Add guidelines section
        guidelines = tone_config.get('guidelines', [])
        if guidelines:
            tone_parts.append("Guidelines:")
            for g in guidelines:
                tone_parts.append(f"  - {g}")
        
        tone_text = "\n".join(tone_parts)
        
        # Format conversation history (same as execute_reply)
        conversation_context = chr(10).join([f"{msg['role']}: {msg['content']}" for msg in conversation_history[-3:]])
        
        prompt = f"""You need to inform the user that you are escalating their request to a human agent for review and approval.

Reason for escalation: {reason}

Generate the response using the tone below:
{tone_text}

Read the conversation history to answer correctly in context:
{conversation_context}

CRITICAL:
- Apply the tone and make the message fit the conversation history.
- Use phrases like "I'll need to escalate your request" or "I'm transferring you to a human agent".
- Generate a natural, friendly message informing the user that you're escalating/transferring their request to a human agent.

Return ONLY the reply message, nothing else."""

        escalation_message = call_llm(prompt, model=model, **(llm_args or {})).strip()
        
        # Add escalation message to conversation history
        conversation_history.append({
            "role": "assistant",
            "content": escalation_message
        })
        
        return {
            "tool_name": tool_name,
            "reason": reason,
            "prepared": False,
            "executed": True,
            "result": escalation_message,
            "error": None
        }
    
    # Prepare tool call for orchestrator (don't execute synchronously)
    tool_call_info = prepare_tool_call(step, extracted_fields, tools)
    
    if not tool_call_info["prepared"]:
        # Tool call preparation failed
        error_msg = tool_call_info.get("error", "unknown error")
        logger.error(f"failed to prepare tool call for '{tool_name}': {error_msg}")
        
        return {
            "tool_name": tool_name,
            "reason": reason,
            "prepared": False,
            "tool_call_info": None,
            "executed": False,
            "error": error_msg
        }
    
    # Tool call prepared successfully
    return {
        "tool_name": tool_name,
        "reason": reason,
        "prepared": True,
        "tool_call_info": tool_call_info,
        "executed": False,
        "error": None
    }


def execute_include(
    step: Dict[str, Any], 
    conversation_history: List[Dict[str, str]], 
    tone_config: Dict[str, Any],
    model: str,
    llm_args: Dict[str, Any]
) -> str:
    information = step.get('information', '')
    
    # Format tone config for prompt
    identity = tone_config.get('identity', {})
    tone_list = tone_config.get('tone', [])
    guidelines = tone_config.get('guidelines', [])
    
    tone_text = "\n".join([f"- {t}" for t in tone_list])
    guidelines_text = "\n".join([f"- {g}" for g in guidelines])
    
    prompt = f"""You are an AI assistant providing support.

Identity:
- Role: {identity.get('role', 'AI assistant')}
- Positioning: {identity.get('positioning', 'helpful companion')}

Tone Guidelines:
{tone_text}

Additional Guidelines:
{guidelines_text}

The user has asked a question, and you need to provide a helpful response that includes this information/link: {information}

Conversation context:
{chr(10).join([f"{msg['role']}: {msg['content']}" for msg in conversation_history[-3:]])}

Generate a natural, friendly reply that:
1. Acknowledges the user's question/concern
2. Includes the information/link naturally in your response
3. Follows the tone guidelines

Return ONLY the reply message, nothing else."""

    if _is_debugging_enabled():
        print(f"[DEBUG] include prompt:\n{prompt}\n")
    
    reply = call_llm(prompt, model=model, **llm_args).strip()
    
    if _is_debugging_enabled():
        print(f"[DEBUG] include response:\n{reply}\n")
    
    # Add reply to conversation history
    conversation_history.append({
        "role": "assistant",
        "content": reply
    })
    
    if _is_debugging_enabled():
        print(f"[DEBUG] include result: {reply}\n")
    
    return reply

