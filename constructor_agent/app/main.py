from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from fastapi.middleware.cors import CORSMiddleware
from constructor_agent.app.agent import ConstructorAgent
import os
import sys
import traceback
import constructor_agent.app.agent as agent_module
print(f"DEBUG: sys.path = {sys.path}")
print(f"DEBUG: agent_module file = {agent_module.__file__}")

app = FastAPI(title="Constructor Agent API")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Paths
WORKFLOW_PATH = "/Users/nirmendelson/quack/tau2-bench/data/tau2/domains/airline/codebase/workflow.yaml"
RULES_PATH = "/Users/nirmendelson/quack/tau2-bench/constructor_agent/cspl-rules.md"

# Global agent instance
agent = ConstructorAgent(WORKFLOW_PATH, RULES_PATH)

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    clarification: Optional[str] = None
    explanation: Optional[str] = None
    edits: Optional[List[Dict[str, Any]]] = None

class ApproveRequest(BaseModel):
    edits: List[Dict[str, Any]]

class ApproveResponse(BaseModel):
    success: bool
    errors: Optional[List[str]]

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        result = agent.process_request(request.message)
        return result
    except Exception as e:
        error_traceback = traceback.format_exc()
        print(f"ERROR in /chat endpoint: {str(e)}")
        print(f"Traceback:\n{error_traceback}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/approve", response_model=ApproveResponse)
async def approve(request: ApproveRequest):
    try:
        success, errors = agent.apply_edits(request.edits)
        return {"success": success, "errors": errors}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/workflows")
async def get_workflows():
    try:
        agent.processor.load()
        return agent.processor.list_workflows()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
