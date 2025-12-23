def get_fetch_single_prompt(field_name, conv_text, tone_text):
    """
    Returns a prompt to extract a single field from the conversation 
    or generate a question to ask for it.
    """
    return f"""You are an intelligence agent. You have great capabilities to read between the lines and infer information. Read the conversation carefully and check if you have the field '{field_name}' in the conversation, or can infer it from the conversation.


You should infer information whenever possible, even if it is only implied indirectly.
Treat the conversation like a detective: if a human could reasonably infer the answer, you should too.

TASK:
1. Check if the information for this field was mentioned in the conversation history
2. You are intelligence agent. Think like a human reading between the lines: infer information whenever it is implied, even if not stated directly.
3. PRIORITY:
   (1) Prefer explicit statements.
   (2) If not explicit, infer the value from context if a reasonable human would.
   (3) Only if it is neither explicit nor inferable, ask the user for this specific missing information.
4. Normalize the user's meaning into the most appropriate value for this field — the wording does not need to match exactly.

EXAMPLES OF INFERENCE:
- "I sent the package yesterday." → They have a tracking number or proof of shipment.
- "I'll reboot the server." → They have admin access to that server.
- "I'll check the security camera." → They have a camera system installed.
- "The landlord raised the price again." → They're renting (not owning).
- "I'm not been able to enter the YouTube app, and the rest of my apps work fine." → They have a problem with the YouTube app and its not a WIFI or hardware issue, because the rest work well.


Conversation:
{conv_text}

Follow this tone when generating the question:
{tone_text}

Respond in this format:
```yaml
found: true/false
value: <extracted value if found>
question: <question to ask if not found>
```"""

def get_fetch_multi_prompt(field_names, conv_text, tone_text):
    """
    Returns a prompt to extract multiple fields from the conversation 
    or generate questions to ask for missing ones.
    """
    fields_list = ", ".join([f"'{f}'" for f in field_names])
    fields_yaml = "\n".join([f"  {f}: <extracted value if found, null if not found>" for f in field_names])
    questions_yaml = "\n".join([f"  {f}: <question to ask if not found>" for f in field_names])
    
    return f"""You are an intelligence agent. You have great capabilities to read between the lines and infer information. Read the conversation carefully and check if you have the fields {fields_list} in the conversation, or can infer them from the conversation.

You should infer information whenever possible, even if it is only implied indirectly.
Treat the conversation like a detective: if a human could reasonably infer the answer, you should too.

TASK:
1. Check if the information for each field was mentioned in the conversation history
2. You are an intelligence agent. Think like a human reading between the lines: infer information whenever it is implied, even if not stated directly.
3. PRIORITY:
   (1) Prefer explicit statements.
   (2) If not explicit, infer the value from context if a reasonable human would.
   (3) Only if it is neither explicit nor inferable, ask the user for the specific missing information.
4. Normalize the user's meaning into the most appropriate value for each field — the wording does not need to match exactly.

EXAMPLES OF INFERENCE:
- "I sent the package yesterday." → They have a tracking number or proof of shipment.
- "I'll reboot the server." → They have admin access to that server.
- "I'll check the security camera." → They have a camera system installed.
- "The landlord raised the price again." → They're renting (not owning).
- "I'm not been able to enter the YouTube app, and the rest of my apps work fine." → They have a problem with the YouTube app and its not a WIFI or hardware issue, because the rest work well.

IMPORTANT:
- Check ALL fields: {fields_list}
- For each field, determine if it's found or missing
- If ALL fields are found, return all values
- If SOME fields are missing, return values for found fields and questions for missing ones
- If ALL fields are missing, return questions for all missing fields
- When asking questions, you can combine them into a single question if it makes sense, or ask separately

Conversation:
{conv_text}

Follow this tone when generating the questions:
{tone_text}

Respond in this format:
```yaml
fields:
{fields_yaml}
questions:
{questions_yaml}
all_found: true/false
combined_question: <single question if all fields missing, or null if some/all found>
```"""

def get_fetch_prompt(field_name, conv_text, tone_text):
    """
    Backward compatibility wrapper for single field fetch.
    Use get_fetch_single_prompt or get_fetch_multi_prompt directly for better clarity.
    """
    return get_fetch_single_prompt(field_name, conv_text, tone_text)

def get_fetch_with_condition_prompt(field_name, condition, conv_text, tone_text):
    """
    Returns a prompt to extract a field and verify it meets a specific condition.
    """
    # Format condition string if it's a dict
    if isinstance(condition, dict):
        op = condition.get('operator')
        left = condition.get('left')
        right = condition.get('right')
        
        # Map operator to symbol
        op_map = {
            'eq': '=', 'equal': '=', 'equals': '=', 
            'gt': '>', 'greater_than': '>',
            'lt': '<', 'less_than': '<',
            'gte': '>=', 'greater_equal': '>=',
            'lte': '<=', 'less_equal': '<=',
            'neq': '!=', 'not_equal': '!='
        }
        op_sym = op_map.get(str(op).lower(), str(op))
        
        condition_str = f"{left} {op_sym} {right}"
    else:
        condition_str = str(condition)

    return f"""You are an intelligence agent. You have great capabilities to read between the lines and infer information. 

TASK 1: FETCH FIELD
Read the conversation carefully and check if you have the field '{field_name}' in the conversation, or can infer it from the conversation.

You should infer information whenever possible, even if it is only implied indirectly.
Treat the conversation like a detective: if a human could reasonably infer the answer, you should too.

PRIORITY:
(1) Prefer explicit statements.
(2) If not explicit, infer the value from context if a reasonable human would.
(3) Only if it is neither explicit nor inferable, ask the user for this specific missing information.

Normalize the user's meaning into the most appropriate value for this field — the wording does not need to match exactly.

EXAMPLES OF INFERENCE:
- "I sent the package yesterday." → They have a tracking number or proof of shipment.
- "I'll reboot the server." → They have admin access to that server.
- "I'll check the security camera." → They have a camera system installed.
- "The landlord raised the price again." → They're renting (not owning).
- "I'm not been able to enter the YouTube app, and the rest of my apps work fine." → They have a problem with the YouTube app and its not a WIFI or hardware issue, because the rest work well.

TASK 2: EVALUATE CONDITION (only if field is found)
If you found the field '{field_name}' in TASK 1, now evaluate this condition: {condition_str}
do not give weight to syntax, only to meaning.

IMPORTANT INSTRUCTIONS FOR CONDITION EVALUATION:
- The condition "{condition_str}" may reference the field '{field_name}' that you just extracted.
- Use the actual value you extracted for '{field_name}' in TASK 1 when evaluating the condition.
- If the condition contains "{{{{ {field_name} }}}}", replace it with the value you found.
- Use your intelligence to determine if the condition is true or false, don't do a simple string comparison.
- Examples: California = CA is true, yes = yeah = I think so = any other phrase with basic meaning of yes

Conversation:
{conv_text}

Follow this tone when generating the question:
{tone_text}

Respond in this format:
```yaml
found: true/false
value: <extracted value if found>
question: <question to ask if not found>
condition_result: <true/false/null>
```"""

def get_fetch_with_message_prompt(field_names, message, conversation, tone_text):
    """
    Returns a prompt to check for fields in conversation, and if not found, use the message as the question.
    """
    fields_list = ", ".join([f"'{f}'" for f in field_names])
    fields_yaml = "\n".join([f"  {f}: <extracted value if found, null if not found>" for f in field_names])
    questions_yaml = "\n".join([f"  {f}: <question to ask if not found>" for f in field_names])
    
    return f"""You are an intelligence agent. You have great capabilities to read between the lines and infer information. Read the conversation carefully and check if you have the fields {fields_list} in the conversation, or can infer them from the conversation.

You should infer information whenever possible, even if it is only implied indirectly.
Treat the conversation like a detective: if a human could reasonably infer the answer, you should too.

TASK:
1. Check if the information for each field was mentioned in the conversation history
2. You are an intelligence agent. Think like a human reading between the lines: infer information whenever it is implied, even if not stated directly.
3. PRIORITY:
   (1) Prefer explicit statements.
   (2) If not explicit, infer the value from context if a reasonable human would.
   (3) Only if it is neither explicit nor inferable, use the provided message as the question to ask for the missing information.
4. Normalize the user's meaning into the most appropriate value for each field — the wording does not need to match exactly.

EXAMPLES OF INFERENCE:
- "I sent the package yesterday." → They have a tracking number or proof of shipment.
- "I'll reboot the server." → They have admin access to that server.
- "I'll check the security camera." → They have a camera system installed.
- "The landlord raised the price again." → They're renting (not owning).
- "I'm not been able to enter the YouTube app, and the rest of my apps work fine." → They have a problem with the YouTube app and its not a WIFI or hardware issue, because the rest work well.

IMPORTANT:
- Check ALL fields: {fields_list}
- For each field, determine if it's found or missing
- If ALL fields are found, return all values
- If SOME or ALL fields are missing, return values for found fields and use the provided message exactly as the question for missing ones
- Use the provided message exactly as-is for the question - do not rephrase or modify it

Message to use as question (use exactly as provided if fields are not found):
{message}

Conversation:
{conversation}

Follow this tone when generating the questions:
{tone_text}

Respond in this format:
```yaml
fields:
{fields_yaml}
questions:
{questions_yaml}
all_found: true/false
```"""

def get_reply_prompt(message_template, tone_text, conversation_context):
    """
    Returns a prompt to generate a natural language reply based on a template message.
    """
    return f"""You need to tell the user this reply message: {message_template}

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

def get_workflow_selection_prompt(conversation, last_message, candidate_workflows, tone_text):
    """
    Returns a prompt for the LLM to choose the best workflow from multiple high-scoring candidates.
    """
    workflows_text = "\n\n".join([f"Workflow: {w['workflow']}\nDescription: {w['when']}" for w in candidate_workflows])
    
    return f"""You are an intelligence agent. Multiple workflows match the user's intent. You need to evaluate and score each one.

LATEST USER MESSAGE (this is the most important):
{last_message}

TASK: Score each candidate workflow based on how well it matches the user's intent expressed in the latest message above. Score each workflow from 0.0 to 1.0, where 1.0 is a perfect match.

CONVERSATION HISTORY (for context only):
{conversation}

IMPORTANT: While the conversation history provides context, the LATEST USER MESSAGE shown above is the primary source of intent. Give it the most weight when scoring workflows.

Candidate workflows:
{workflows_text}

Respond in YAML format with workflow name and score for each candidate:
```yaml
workflows:
  - name: <workflow_name>
    score: <score_0.0_to_1.0>
  - name: <workflow_name>
    score: <score_0.0_to_1.0>
  ...
```"""

def get_condition_eval_prompt(condition, field_info, conv_text):
    """
    Returns a prompt to evaluate a complex condition based on memory variables.
    """
    def _format_condition(cond):
        if not isinstance(cond, dict):
            return str(cond)
            
        op = cond.get('operator')
        
        # Handle nested conditions
        if 'conditions' in cond:
            sub_conds = [_format_condition(c) for c in cond.get('conditions', [])]
            joiner = " AND " if op == 'and' else " OR "
            return f"({joiner.join(sub_conds)})"
        
        # Handle simple comparison
        left = cond.get('left')
        right = cond.get('right')
        
        # Map operator to symbol
        op_map = {
            'eq': '=', 'equal': '=', 'equals': '=', 
            'gt': '>', 'greater_than': '>',
            'lt': '<', 'less_than': '<',
            'gte': '>=', 'greater_equal': '>=',
            'lte': '<=', 'less_equal': '<=',
            'neq': '!=', 'not_equal': '!',
            'contains': 'contains'
        }
        op_sym = op_map.get(str(op).lower(), str(op))
        
        return f"{left} {op_sym} {right}"

    condition_str = _format_condition(condition)

    return f"""You are an intelligence agent. Evaluate this condition based on the field value and conversation context.

{field_info}

Condition to evaluate: {condition_str}

Conversation history (for context):
{conv_text}

TASK: Determine if the condition "{condition_str}" is true or false.

CRITICAL: Use your intelligence to determine if the condition is true or false, don't do a simple string comparison.
- California = CA is true
- yes = yeah = I think so = any other phrase with basic meaning of yes


Evaluate the condition and return ONLY "true" or "false" (lowercase, no quotes, no explanation)."""

def get_instruction_prompt(instruction_text, tools_available, memory_variables, conversation_context, tone_text):
    """
    Returns a prompt for the LLM to execute an instruction task.
    
    Args:
        instruction_text: The instruction text (may contain templates)
        tools_available: List of tool names available for this instruction
        memory_variables: Dictionary of current memory variables
        conversation_context: Conversation history
        tone_text: Tone guidelines
    
    Returns:
        Formatted prompt string
    """
    tools_list = "\n".join([f"- {tool}" for tool in tools_available]) if tools_available else "No specific tools available (use standard reasoning)"
    
    # Format memory variables for context
    memory_info = "\n".join([f"  {key}: {value}" for key, value in memory_variables.items()])
    
    return f"""You are an intelligence agent executing a specific task. Follow the instructions below carefully.

TASK INSTRUCTION:
{instruction_text}

CURRENT MEMORY VARIABLES (you can use these in your reasoning):
{memory_info if memory_info else "  (no variables set yet)"}

CONVERSATION CONTEXT (for reference):
{conversation_context}

TONE GUIDELINES:
{tone_text}

IMPORTANT:
- Follow the instruction step by step
- Use the memory variables provided above
- If you need to use tools, reason about what tool calls would be needed, but return the final result value
- Return ONLY the result value that should be stored in the variable
- The result should be a simple value (string, number, null, etc.) - not a complex object
- If the task cannot be completed, return null

Respond in YAML format:
```yaml
result: <the value to store in the variable, or null if task cannot be completed>
reasoning: <brief explanation of how you arrived at the result>
```"""
