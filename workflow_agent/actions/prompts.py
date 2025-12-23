def get_fetch_prompt(field_name, conv_text, tone_text):
    """
    Returns a prompt to extract a specific field from the conversation 
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

def get_fetch_with_condition_prompt(field_name, condition_str, conv_text, tone_text):
    """
    Returns a prompt to extract a field and verify it meets a specific condition.
    """
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

IMPORTANT INSTRUCTIONS FOR CONDITION EVALUATION:
- The condition "{condition_str}" may reference the field '{field_name}' that you just extracted.
- Use the actual value you extracted for '{field_name}' in TASK 1 when evaluating the condition.
- If the condition contains "{{ {field_name} }}", replace it with the value you found.
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
condition_result: <true/false if found, null if not found>
```"""

def get_fetch_with_message_prompt(message, conversation, tone_text):
    """
    Returns a prompt to send a specific message and fetch the answer to a variable.
    """
    return f"""You need to send this message to the user: {message}

Conversation history (for context):
{conversation}

Follow this tone when generating the message:
{tone_text}

Return ONLY the message to send to the user, nothing else."""

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

def get_workflow_selection_prompt(conversation, candidate_workflows, tone_text):
    """
    Returns a prompt for the LLM to choose the best workflow from multiple high-scoring candidates.
    """
    workflows_text = "\n\n".join([f"Workflow: {w['workflow']}\nDescription: {w['when']}" for w in candidate_workflows])
    
    return f"""You are an intelligence agent. Multiple workflows match the user's intent. You need to select the most appropriate one.

Conversation history:
{conversation}

Candidate workflows:
{workflows_text}

TASK: Determine which workflow best matches the user's current intent based on the conversation.

Follow this tone in your analysis:
{tone_text}

Respond with ONLY the workflow name, nothing else."""

def get_condition_eval_prompt(condition_str, field_info, conv_text):
    """
    Returns a prompt to evaluate a complex condition based on memory variables.
    """
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
