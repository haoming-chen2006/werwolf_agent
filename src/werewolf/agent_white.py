from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
import random

import os
import datetime

app = FastAPI(title="Baseline White Agent", description="Simple baseline agent")

def log_to_memory(content: str):
    memory_file = os.environ.get("AGENT_MEMORY_FILE")
    if memory_file:
        with open(memory_file, "a") as f:
            timestamp = datetime.datetime.now().isoformat()
            f.write(f"[{timestamp}] {content}\n")

@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Log incoming request
    body = await request.body()
    log_to_memory(f"Request: {request.method} {request.url} Body: {body.decode()}")
    
    response = await call_next(request)
    
    # Log response (we can't easily read response body in middleware without consuming it, 
    # but we can log status)
    log_to_memory(f"Response Status: {response.status_code}")
    return response


class NightRolePrompt(BaseModel):
    phase: str
    night_number: int
    role: str
    you: Dict[str, Any]
    options: Dict[str, Any]
    public_history_summary: str
    constraints: Dict[str, Any]

class DayDiscussionPrompt(BaseModel):
    phase: str
    day_number: int
    you: Dict[str, Any]
    players: List[Dict[str, Any]]
    public_history: List[Dict[str, Any]]
    constraints: Dict[str, Any]

class DayVotePrompt(BaseModel):
    phase: str
    day_number: int
    you: Dict[str, Any]
    options: List[str]
    public_summary: str
    constraints: Dict[str, Any]

@app.post("/agent/night_action")
def night_action(prompt: NightRolePrompt) -> Dict[str, Any]:
    role = prompt.role
    if role == "werewolf":
        options = prompt.options.get("kill_options", [])
        target = random.choice(options) if options else None
        return {"kill_vote": target, "reason": "I want to win."}
    elif role == "detective":
        options = prompt.options.get("inspect_options", [])
        target = random.choice(options) if options else None
        return {"inspect": target}
    elif role == "doctor":
        options = prompt.options.get("protect_options", [])
        target = random.choice(options) if options else None
        return {"protect": target}
    return {"sleep": True}

@app.post("/agent/discussion")
def discussion(prompt: DayDiscussionPrompt) -> Dict[str, str]:
    return {"talk": "I am a villager. I trust everyone."}

@app.post("/agent/vote")
def vote(prompt: DayVotePrompt) -> Dict[str, str]:
    options = prompt.options
    # Don't vote for self if possible
    my_id = prompt.you["id"]
    valid_options = [o for o in options if o != my_id]
    if not valid_options:
        valid_options = options
        
    target = random.choice(valid_options) if valid_options else None
    return {"vote": target, "reason": "He seems suspicious."}

@app.get("/health")
def health():
    return {"status": "ok"}
