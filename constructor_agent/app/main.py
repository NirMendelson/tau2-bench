from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from fastapi.middleware.cors import CORSMiddleware
from constructor_agent.app.processor.workflow_processor import WorkflowProcessor
from constructor_agent.app.processor.constants_processor import ConstantsProcessor
from constructor_agent.app.processor.tone_processor import ToneProcessor
from constructor_agent.app.validator import WorkflowValidator
import os
import sys
import traceback
import uuid
import litellm

app = FastAPI(title="Constructor Agent API")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from constructor_agent.app.agent.unified_agent import UnifiedAgent

# Paths
CODEBASE_DIR = "/Users/nirmendelson/quack/tau2-bench/data/tau2/domains/airline/codebase"
WORKFLOW_PATH = os.path.join(CODEBASE_DIR, "workflow.yaml")
CONSTANTS_PATH = os.path.join(CODEBASE_DIR, "constants.yaml")
TONE_PATH = os.path.join(CODEBASE_DIR, "tone.yaml")

# Initialize components
workflow_processor = WorkflowProcessor(WORKFLOW_PATH)
constants_processor = ConstantsProcessor(CONSTANTS_PATH)
tone_processor = ToneProcessor(TONE_PATH)
validator = WorkflowValidator(WORKFLOW_PATH)

# Cursor-style unified agent (exploration + editing in one conversational flow)
agent = UnifiedAgent(
    workflow_processor,
    constants_processor,
    tone_processor,
    validator
)

# Session-based conversation memory (in-memory for single-user system)
sessions = {}

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    session_id: str
    clarification: Optional[str] = None
    explanation: Optional[str] = None
    edits: Optional[List[Dict[str, Any]]] = None

async def check_if_approval(user_message: str, conversation_history: List[Dict[str, Any]]) -> bool:
    if not conversation_history:
        return False
    
    # Get the last assistant message
    last_assistant_msg = next((m["content"] for m in reversed(conversation_history) if m["role"] == "assistant"), "")
    if not last_assistant_msg:
        return False

    prompt = f"""
    The user is interacting with a coding agent.
    The agent proposed some changes: "{last_assistant_msg}"
    The user replied: "{user_message}"
    
    Does the user's reply mean "yes", "approve", "go ahead", "looks good", "do it", or any other conversational confirmation of the proposal?
    Reply with ONLY 'YES' or 'NO'.
    """
    try:
        response = litellm.completion(
            model="gpt-4o-mini", # Using a fast model for intent detection
            messages=[{"role": "user", "content": prompt}]
        )
        content = response.choices[0].message.content.strip().upper()
        return "YES" in content
    except Exception:
        # Fallback to simple keyword check if LLM fails
        keywords = ["yes", "approve", "go ahead", "do it", "sure", "ok", "yep", "looks good"]
        return any(k in user_message.lower() for k in keywords)

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        # Get or create session
        session_id = request.session_id or str(uuid.uuid4())
        
        if session_id not in sessions:
            sessions[session_id] = {
                "messages": [],
                "pending_edits": None
            }
        
        session = sessions[session_id]

        # Check if this is an approval of pending edits
        if session["pending_edits"] and await check_if_approval(request.message, session["messages"]):
            # Apply the changes
            workflow_processor.save()
            constants_processor.save()
            tone_processor.save()
            
            # Conversational confirmation (like Cursor)
            msg = "Done! Changes applied. ✅"
            session["messages"].append({"role": "user", "content": request.message})
            session["messages"].append({"role": "assistant", "content": msg})
            session["pending_edits"] = None
            
            # Return as clarification (just conversation, no special UI)
            return {
                "session_id": session_id,
                "clarification": msg
            }
        
        # Add user message to history
        session["messages"].append({
            "role": "user",
            "content": request.message
        })
        
        # Process with unified agent (Cursor-style: explore + edit + explain in one turn)
        result = agent.process_request(request.message, session["messages"])
        
        # Add agent's response to history
        agent_message = result.get("message", "")
        session["messages"].append({
            "role": "assistant",
            "content": agent_message
        })
        
        # If agent made changes, store them as pending (but don't send edits to frontend)
        if result.get("has_changes"):
            session["pending_edits"] = result.get("edits")
            
            # Return just the conversational message (no edits field = no special UI)
            return {
                "session_id": session_id,
                "clarification": agent_message  # Just conversation, frontend won't show "Proposed Edits" box
            }
        
        # No changes - just conversational response
        return {
            "session_id": session_id,
            "clarification": agent_message
        }
        
    except Exception as e:
        print(f"ERROR in /chat: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


class ApproveRequest(BaseModel):
    session_id: Optional[str] = None
    edits: Optional[List[Dict[str, Any]]] = None

@app.post("/approve")
async def approve(request: ApproveRequest = None):
    try:
        # Saving all three files in memory back to disk
        workflow_processor.save()
        constants_processor.save()
        tone_processor.save()
        
        # Clear pending edits for this session
        if request and request.session_id and request.session_id in sessions:
            sessions[request.session_id]["pending_edits"] = None
            sessions[request.session_id]["messages"].append({
                "role": "assistant",
                "content": "Changes applied successfully!"
            })
        
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/workflows")
async def get_workflows():
    try:
        workflow_processor.load()
        return workflow_processor.list_workflows()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
