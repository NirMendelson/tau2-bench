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
from constructor_agent.app.validator import WorkflowValidator
import uuid

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

@app.post("/approve")
async def approve(session_id: str = None):
    try:
        # Saving all three files in memory back to disk
        workflow_processor.save()
        constants_processor.save()
        tone_processor.save()
        
        # Clear pending edits for this session
        if session_id and session_id in sessions:
            sessions[session_id]["pending_edits"] = None
            sessions[session_id]["messages"].append({
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
