from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
import random

import os
import datetime
import json
from litellm import completion

app = FastAPI(title="Baseline White Agent", description="Simple baseline agent")

def log_to_memory(content: str):
    memory_file = os.environ.get("AGENT_MEMORY_FILE")
    if memory_file:
        with open(memory_file, "a") as f:
            timestamp = datetime.datetime.now().isoformat()
            f.write(f"[{timestamp}] {content}\n")
    
    # Also log to a specific history folder if PUBLIC_HISTORY_DIR is set
    # This is the "little check" requested by the user
    history_dir = os.environ.get("PUBLIC_HISTORY_DIR")
    agent_id = os.environ.get("AGENT_SESSION_ID", "unknown_agent")
    if history_dir and os.path.exists(history_dir):
        # Create a file specific to this agent in the public dir (just for debug/check)
        check_file = os.path.join(history_dir, f"{agent_id}_check.log")
        with open(check_file, "a") as f:
            timestamp = datetime.datetime.now().isoformat()
            f.write(f"[{timestamp}] Agent {agent_id} active: {content[:50]}...\n")

@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Log incoming request
    body = await request.body()
    body_str = body.decode()
    if len(body_str) > 500:
        body_str = body_str[:500] + "... (truncated)"
    log_to_memory(f"Request: {request.method} {request.url} Body: {body_str}")
    
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
    role_statement: Optional[str] = None
    private_thoughts_history: Optional[List[Dict[str, Any]]] = None
    public_speech_history: Optional[List[Dict[str, Any]]] = None
    history_text: Optional[str] = None
    constraints: Dict[str, Any]

class DayDiscussionPrompt(BaseModel):
    phase: str
    day_number: int
    you: Dict[str, Any]
    players: List[Dict[str, Any]]
    public_history: List[Dict[str, Any]]
    role_statement: Optional[str] = None
    private_thoughts_history: Optional[List[Dict[str, Any]]] = None
    public_speech_history: Optional[List[Dict[str, Any]]] = None
    history_text: Optional[str] = None
    instruction: Optional[str] = None
    constraints: Dict[str, Any]

class DayVotePrompt(BaseModel):
    phase: str
    day_number: int
    you: Dict[str, Any]
    options: List[str]
    public_summary: str
    public_history: Optional[List[Dict[str, Any]]] = None
    private_thoughts_history: Optional[List[Dict[str, Any]]] = None
    public_speech_history: Optional[List[Dict[str, Any]]] = None
    history_text: Optional[str] = None
    constraints: Dict[str, Any]

@app.post("/night_action")
def night_action(prompt: NightRolePrompt) -> Dict[str, Any]:
    role = prompt.role
    
    # LLM Logic
    if os.environ.get("OPENAI_API_KEY"):
        try:
            # Use the role_statement directly as it contains all necessary context and instructions
            history_section = prompt.history_text if prompt.history_text else f"Public History Summary: {prompt.public_history_summary}"
            system_prompt = f"{prompt.role_statement}\n\nFULL GAME HISTORY:\n{history_section}\n"
            
            response = completion(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a player in a Werewolf game. Follow the instructions exactly."},
                    {"role": "user", "content": system_prompt}
                ]
            )
            content = response.choices[0].message.content.strip()
            
            # Return the raw response wrapped in a dict
            return {"raw_response": content}
        except Exception as e:
            print(f"LLM night action failed: {e}")

    # Fallback Logic
    result = {"thought": f"I am playing as {role} and deciding my night action."}
    
    if role == "werewolf":
        options = prompt.options.get("kill_options", [])
        target = random.choice(options) if options else None
        result.update({"action": "kill", "target": target})
    elif role == "detective":
        options = prompt.options.get("inspect_options", [])
        target = random.choice(options) if options else None
        result.update({"action": "inspect", "target": target})
    elif role == "doctor":
        options = prompt.options.get("protect_options", [])
        target = random.choice(options) if options else None
        result.update({"action": "protect", "target": target})
    else:
        result.update({"action": "sleep"})
        
    return result

@app.post("/discussion")
def discussion(prompt: DayDiscussionPrompt) -> Dict[str, str]:
    # Try to surface recent public speeches (shared) and the agent's own private memory
    public_dir = os.environ.get("PUBLIC_HISTORY_DIR")
    public_text = []
    if public_dir:
        try:
            with open(os.path.join(public_dir, "public_speeches.json"), "r") as f:
                public_text = json.load(f)
        except Exception:
            public_text = []

    # Basic baseline reply that references public and private snippets for traceability
    # If OPENAI_API_KEY is present, use LLM to generate response
    if os.environ.get("OPENAI_API_KEY"):
        try:
            # Construct prompt for LLM
            history_section = prompt.history_text if prompt.history_text else f"Public History: {json.dumps(prompt.public_history)}\nPrivate Thoughts: {json.dumps(prompt.private_thoughts_history)}\nPublic Speech History: {json.dumps(prompt.public_speech_history)}"
            
            system_prompt = (
                f"{prompt.role_statement}\n"
                f"Current Phase: {prompt.phase} {prompt.day_number}\n"
                f"Alive Players: {[p['id'] for p in prompt.players if p['alive']]}\n"
                f"GAME HISTORY:\n{history_section}\n"
                f"Instruction: {prompt.instruction or 'Act as your role.'}\n"
            )
            
            response = completion(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a player in a Werewolf game. Output strictly JSON."},
                    {"role": "user", "content": system_prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            # Strip markdown code blocks if present
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            data = json.loads(content)
            return {"thought": data.get("thought", "No thought"), "speech": data.get("speech", "I have nothing to say.")}
        except Exception as e:
            print(f"LLM generation failed: {e}")
            # Fallback to default behavior below

    reply = "I review public discussion and my private notes."
    if public_text:
        recent = public_text[-3:]
        # Clean up speech content to avoid dumping logs if they exist
        clean_speeches = []
        for p in recent:
            content = p.get('talk', '').strip()
            # Heuristic to detect log dump and truncate/ignore
            if "Request: POST" in content:
                content = "(technical log omitted)"
            clean_speeches.append(f"{p['player_id']}: {content}")
            
        reply += " Recent public: " + "; ".join(clean_speeches)
        
    return {"thought": "I am analyzing the situation.", "speech": reply}

@app.post("/vote")
def vote(prompt: DayVotePrompt) -> Dict[str, str]:
    # LLM Logic
    if os.environ.get("OPENAI_API_KEY"):
        try:
            history_section = prompt.history_text if prompt.history_text else f"Public History: {json.dumps(prompt.public_history)}\nPrivate Thoughts: {json.dumps(prompt.private_thoughts_history)}"
            
            system_prompt = (
                f"Phase: Vote Day {prompt.day_number}\n"
                f"You are: {prompt.you['id']}\n"
                f"Options: {prompt.options}\n"
                f"Public Summary: {prompt.public_summary}\n"
                f"GAME HISTORY:\n{history_section}\n"
                f"Instruction: Vote for one player to eliminate. Output JSON with 'speech'. 'speech' must be ONLY the player ID (e.g., 'p1')."
            )
            
            response = completion(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a player in a Werewolf game. Output strictly JSON."},
                    {"role": "user", "content": system_prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            # Strip markdown code blocks if present
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            data = json.loads(content)
            # Ensure speech is just the ID
            speech = data.get("speech", "")
            vote = speech if speech in prompt.options else None
            
            return {"thought": data.get("thought", "No thought"), "speech": speech, "vote": vote, "reason": "Vote based on thought."}
        except Exception as e:
            print(f"LLM vote failed: {e}")

    options = prompt.options
    # Don't vote for self if possible
    my_id = prompt.you["id"]
    valid_options = [o for o in options if o != my_id]
    if not valid_options:
        valid_options = options
        
    target = random.choice(valid_options) if valid_options else None
    return {"thought": "Random vote fallback", "speech": target, "vote": target, "reason": "He seems suspicious."}

@app.get("/health")
def health():
    return {"status": "ok"}
