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

from constructor_agent.app.agent.orchestrator import TrinityOrchestrator

# Paths
CODEBASE_DIR = "/Users/nirmendelson/quack/tau2-bench/data/tau2/domains/airline/codebase"
WORKFLOW_PATH = os.path.join(CODEBASE_DIR, "workflow.yaml")
CONSTANTS_PATH = os.path.join(CODEBASE_DIR, "constants.yaml")
TONE_PATH = os.path.join(CODEBASE_DIR, "tone.yaml")
RULES_PATH = "/Users/nirmendelson/quack/tau2-bench/constructor_agent/knowledge/cspl-rules.md"

# Initialize components
workflow_processor = WorkflowProcessor(WORKFLOW_PATH)
constants_processor = ConstantsProcessor(CONSTANTS_PATH)
tone_processor = ToneProcessor(TONE_PATH)
validator = WorkflowValidator(WORKFLOW_PATH)

orchestrator = TrinityOrchestrator(
    workflow_processor,
    constants_processor,
    tone_processor,
    validator,
    RULES_PATH
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

        # 1. Check if this is an approval of pending edits
        if session["pending_edits"] and await check_if_approval(request.message, session["messages"]):
            # Auto-approve
            workflow_processor.save()
            constants_processor.save()
            tone_processor.save()
            
            msg = "Changes applied successfully! ✅"
            session["messages"].append({"role": "user", "content": request.message})
            session["messages"].append({"role": "assistant", "content": msg})
            session["pending_edits"] = None
            
            return {
                "session_id": session_id,
                "explanation": msg
            }
        
        # 2. Otherwise process as a normal request
        # Add user message to history
        session["messages"].append({
            "role": "user",
            "content": request.message
        })
        
        # Process with full conversation history
        result = orchestrator.process_request(request.message, session["messages"])
        
        # Add assistant response to history
        if "clarification" in result:
            session["messages"].append({
                "role": "assistant",
                "content": result["clarification"]
            })
        elif "explanation" in result:
            session["messages"].append({
                "role": "assistant",
                "content": result["explanation"]
            })
            session["pending_edits"] = result.get("edits")
        
        return {
            "session_id": session_id,
            **result
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
