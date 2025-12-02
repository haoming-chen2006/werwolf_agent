import asyncio
import yaml
import uvicorn
import httpx
import subprocess
import sys
import os
import signal
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse

# Load configuration
if not os.path.exists("agentbeats.yaml"):
    print("Error: agentbeats.yaml not found")
    sys.exit(1)

with open("agentbeats.yaml", "r") as f:
    config = yaml.safe_load(f)

AGENT_PORT = config.get("port", 8001)
ENTRYPOINT = config.get("entrypoint", "./run.sh")
CONTROLLER_PORT = int(os.getenv("PORT", 8000))

app = FastAPI(title="AgentBeats Controller")
agent_process = None

def start_agent():
    global agent_process
    if agent_process and agent_process.poll() is None:
        return # Already running
    
    print(f"Starting agent with: {ENTRYPOINT}")
    # Ensure the entrypoint is executable
    if ENTRYPOINT.endswith(".sh"):
        subprocess.run(["chmod", "+x", ENTRYPOINT])
        
    env = os.environ.copy()
    env["AGENT_PORT"] = str(AGENT_PORT)
    
    agent_process = subprocess.Popen(
        ENTRYPOINT, 
        shell=True, 
        env=env,
        preexec_fn=os.setsid # Create new process group
    )

def stop_agent():
    global agent_process
    if agent_process and agent_process.poll() is None:
        print("Stopping agent...")
        os.killpg(os.getpgid(agent_process.pid), signal.SIGTERM)
        agent_process.wait()
        agent_process = None

@app.on_event("startup")
async def startup_event():
    start_agent()

@app.on_event("shutdown")
async def shutdown_event():
    stop_agent()

@app.get("/.well-known/agent-card.json")
async def get_agent_card():
    return config

@app.get("/health")
async def health():
    agent_status = "running" if agent_process and agent_process.poll() is None else "stopped"
    return {"status": "ok", "agent_status": agent_status}

@app.post("/control/restart")
async def restart_agent():
    stop_agent()
    start_agent()
    return {"status": "restarted"}

@app.api_route("/{path_name:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(request: Request, path_name: str):
    # Skip controller endpoints
    if path_name.startswith(".well-known") or path_name.startswith("control") or path_name == "health":
        return
        
    url = f"http://localhost:{AGENT_PORT}/{path_name}"
    if request.query_params:
        url += f"?{request.query_params}"
        
    async with httpx.AsyncClient() as client:
        try:
            proxy_req = client.build_request(
                request.method,
                url,
                headers=request.headers.raw,
                content=await request.body()
            )
            response = await client.send(proxy_req)
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=response.headers
            )
        except httpx.RequestError:
            raise HTTPException(status_code=502, detail="Agent not reachable")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=CONTROLLER_PORT)
