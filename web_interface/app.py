import sys
import os
import asyncio
import subprocess
import signal
import random
import logging
import time
import json
from datetime import datetime
from typing import List, Dict, Optional
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn
import matplotlib.pyplot as plt
from dotenv import load_dotenv

load_dotenv()

# Add werewolf-agent/src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../werewolf-agent/src")))

try:
    from werewolf.game_manager import GameManager
    from werewolf.models import PlayerProfile, FinalResult
    from werewolf.elo_system import create_elo_calculator, EloCalculator
except ImportError as e:
    print(f"Error importing werewolf modules: {e}")
    sys.exit(1)

app = FastAPI()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

class AgentConfig(BaseModel):
    name: str
    api_key: str

class StartGameRequest(BaseModel):
    agents: List[AgentConfig]

class GameState:
    is_running = False
    logs: List[str] = []
    players: List[Dict] = []
    processes: List[subprocess.Popen] = []
    game_task: Optional[asyncio.Task] = None
    manager: Optional[GameManager] = None

state = GameState()

ELO_FILE = os.path.join(os.path.dirname(__file__), "elo_ratings.json")
elo_calculator = create_elo_calculator()

def load_elo():
    if os.path.exists(ELO_FILE):
        try:
            with open(ELO_FILE, "r") as f:
                data = json.load(f)
                for pid, rating_data in data.items():
                    rating = elo_calculator.get_or_create_rating(pid)
                    rating.overall_rating = rating_data.get("overall", 1500.0)
                    rating.wolf_rating = rating_data.get("wolf", 1500.0)
                    rating.villager_rating = rating_data.get("villager", 1500.0)
                    rating.games_played = rating_data.get("games_played", 0)
                    rating.wins = rating_data.get("wins", 0)
                    rating.losses = rating_data.get("losses", 0)
        except Exception as e:
            print(f"Error loading ELO: {e}")

def save_elo():
    data = {}
    for pid, rating in elo_calculator.ratings.items():
        data[pid] = {
            "overall": rating.overall_rating,
            "wolf": rating.wolf_rating,
            "villager": rating.villager_rating,
            "games_played": rating.games_played,
            "wins": rating.wins,
            "losses": rating.losses
        }
    try:
        with open(ELO_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving ELO: {e}")

def generate_plots():
    rankings = elo_calculator.get_rankings("overall")
    if not rankings:
        return
    
    names = [r["player_id"] for r in rankings]
    ratings = [r["overall_rating"] for r in rankings]
    
    plt.figure(figsize=(10, 6))
    plt.bar(names, ratings, color='skyblue')
    plt.title("Agent ELO Ratings")
    plt.xlabel("Agent")
    plt.ylabel("ELO")
    plt.ylim(min(ratings) - 50, max(ratings) + 50)
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    os.makedirs(static_dir, exist_ok=True)
    plt.savefig(os.path.join(static_dir, "elo_ratings.png"))
    plt.close()

# Load ELO on startup
load_elo()

def kill_processes():
    for p in state.processes:
        if p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=1)
            except subprocess.TimeoutExpired:
                p.kill()
    state.processes = []

def assign_roles(count: int) -> List[Dict]:
    roles = ["werewolf", "doctor", "detective"] + ["villager"] * (count - 3)
    random.shuffle(roles)
    assignments = []
    for i, role in enumerate(roles):
        alignment = "wolves" if role == "werewolf" else "town"
        assignments.append({
            "id": f"p{i+1}",
            "role": role,
            "alignment": alignment
        })
    return assignments

async def run_game_logic(agent_configs: List[AgentConfig]):
    state.is_running = True
    state.logs.append("Starting game logic...")
    
    try:
        # 1. Start Agent Processes
        base_port = 8011
        player_profiles = []
        
        assignments = assign_roles(len(agent_configs))
        
        for i, config in enumerate(agent_configs):
            port = base_port + i
            role_info = assignments[i]
            
            # Start process
            env = os.environ.copy()
            
            # API Key handling
            if config.api_key:
                env["OPENAI_API_KEY"] = config.api_key
            elif os.getenv("OPENAI_API_KEY"):
                env["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
                
            # Memory file handling
            memory_file = os.path.abspath(os.path.join(os.path.dirname(__file__), f"../agent_memory_{config.name}.log"))
            env["AGENT_MEMORY_FILE"] = memory_file
            # Clear/Init memory file
            with open(memory_file, "w") as f:
                f.write(f"Memory log for {config.name} started at {datetime.now()}\n")
            
            cmd = [
                "uvicorn", 
                "werewolf.agent_white:app", 
                "--host", "0.0.0.0", 
                "--port", str(port)
            ]
            
            state.logs.append(f"Starting agent {config.name} ({role_info['role']}) on port {port}...")
            
            # We need to run this from the werewolf-agent directory so it finds the module
            cwd = os.path.abspath(os.path.join(os.path.dirname(__file__), "../werewolf-agent"))
            
            proc = subprocess.Popen(
                cmd,
                cwd=cwd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            state.processes.append(proc)
            
            # Create profile
            profile = PlayerProfile(
                id=role_info["id"],
                alias=config.name,
                role_private=role_info["role"],
                alignment=role_info["alignment"],
                alive=True
            )
            profile.url = f"http://localhost:{port}"
            player_profiles.append(profile)
            
            state.players.append({
                "id": role_info["id"],
                "name": config.name,
                "role": role_info["role"],
                "alive": True,
                "port": port
            })

        # Wait for agents to start
        await asyncio.sleep(3)
        
        # 2. Initialize Game Manager
        state.logs.append("Initializing Game Manager...")
        manager = GameManager(player_profiles, config={"max_words_day_talk": 100})
        state.manager = manager
        
        # 3. Run Game
        state.logs.append("Game Started!")
        record = await manager.run_game()
        
        state.logs.append("Game Over!")
        state.logs.append(f"Result: {record.final_result.winning_side} wins!")
        
        # 4. Update ELO
        winner_alignment = record.final_result.winning_side
        
        # Identify winners and losers
        for p in player_profiles:
            is_winner = p.alignment == winner_alignment
            # We need to find opponents to update ELO against?
            # The EloCalculator.process_game_result expects a winner and loser pair.
            # For multiplayer, we can update each winner against each loser, or use average.
            # A simple approach: Update each player based on win/loss.
            # Actually, EloCalculator.process_game_result takes winner_id, loser_id.
            # We can iterate all pairs of (winner, loser).
            pass
            
        # Let's do a simplified ELO update: All winners beat all losers
        winners = [p for p in player_profiles if p.alignment == winner_alignment]
        losers = [p for p in player_profiles if p.alignment != winner_alignment]
        
        for w in winners:
            for l in losers:
                elo_calculator.process_game_result(
                    winner_id=w.alias, # Use alias (Name) for ELO tracking, not temporary ID
                    loser_id=l.alias,
                    winner_role=w.role_private,
                    loser_role=l.role_private,
                    game_id=record.game_id
                )
        
        save_elo()
        generate_plots()
        state.logs.append("ELO Ratings updated and plots generated.")
        
    except Exception as e:
        state.logs.append(f"Error: {str(e)}")
        import traceback
        state.logs.append(traceback.format_exc())
    finally:
        state.is_running = False
        kill_processes()
        state.logs.append("Processes cleaned up.")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/start")
async def start_game(request: StartGameRequest, background_tasks: BackgroundTasks):
    if state.is_running:
        return JSONResponse({"status": "error", "message": "Game already running"})
    
    state.logs = []
    state.players = []
    kill_processes()
    
    background_tasks.add_task(run_game_logic, request.agents)
    return {"status": "ok"}

@app.post("/stop")
async def stop_game():
    kill_processes()
    state.is_running = False
    state.logs.append("Game stopped by user.")
    return {"status": "ok"}

@app.get("/state")
async def get_state():
    # Update player alive status from manager if available
    if state.manager:
        for p in state.players:
            if state.manager.state:
                p["alive"] = state.manager.state.is_alive(p["id"])
    
    return {
        "is_running": state.is_running,
        "logs": state.logs[-50:], # Last 50 logs
        "players": state.players
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
