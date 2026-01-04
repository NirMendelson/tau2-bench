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

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    clarification: Optional[str] = None
    explanation: Optional[str] = None
    edits: Optional[List[Dict[str, Any]]] = None

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        result = orchestrator.process_request(request.message)
        return result
    except Exception as e:
        print(f"ERROR in /chat: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/approve")
async def approve():
    try:
        # Saving all three files in memory back to disk
        workflow_processor.save()
        constants_processor.save()
        tone_processor.save()
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
