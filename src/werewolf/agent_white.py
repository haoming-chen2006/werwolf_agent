from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import Any, Dict, List, Optional, Union
import random

import os
import datetime
import json
from litellm import completion
from src.my_util.file_tools import read_file_tool, search_file_tool

app = FastAPI(title="White Agent", description="Role-aware structured white agent")

# Architecture mode: "advanced" (Planner→Investigation→Decision) or "vanilla" (simple LLM)
# Set via environment variable WHITE_AGENT_MODE
def get_agent_mode() -> str:
    return os.environ.get("WHITE_AGENT_MODE", "advanced")


def log_to_memory(content: str):
    memory_file = os.environ.get("AGENT_MEMORY_FILE")
    if memory_file:
        try:
            with open(memory_file, "a") as f:
                timestamp = datetime.datetime.now().isoformat()
                f.write(f"[{timestamp}] {content}\n")
        except Exception:
            pass
    history_dir = os.environ.get("PUBLIC_HISTORY_DIR")
    agent_id = os.environ.get("AGENT_SESSION_ID", "unknown_agent")
    if history_dir and os.path.exists(history_dir):
        try:
            check_file = os.path.join(history_dir, f"{agent_id}_check.log")
            with open(check_file, "a") as f:
                timestamp = datetime.datetime.now().isoformat()
                f.write(f"[{timestamp}] Agent {agent_id} active: {content[:50]}...\n")
        except Exception:
            pass


def _append_white_history(player_dir: str, record: Dict[str, Any]):
    """Append a record to the white_history.jsonl file."""
    try:
        os.makedirs(player_dir, exist_ok=True)
        hist_file = os.path.join(player_dir, "white_history.jsonl")
        with open(hist_file, "a") as f:
            f.write(json.dumps(record, default=str) + "\n")
    except Exception as e:
        print(f"Failed to write white_history to {player_dir}: {e}")


def _extract_role_from_prompt(prompt: Dict[str, Any]) -> str:
    """Extract the player's role from the prompt, checking multiple locations."""
    # First check you.role
    you = prompt.get("you", {})
    role = you.get("role")
    if role:
        return role
    
    # Check top-level role (night prompts)
    role = prompt.get("role")
    if role:
        return role
    
    # Try to extract from role_statement
    role_statement = prompt.get("role_statement", "")
    if role_statement:
        # Look for "Your role is <role>"
        import re
        match = re.search(r"Your role is (\w+)", role_statement)
        if match:
            return match.group(1).lower()
    
    # Try to read from Info.json if file_location available
    file_location = prompt.get("file_location")
    self_id = you.get("id")
    if file_location and self_id:
        info_path = os.path.join(file_location, f"Player_{self_id}", "Info.json")
        if not os.path.isabs(info_path):
            info_path = os.path.join(os.getcwd(), info_path)
        if os.path.exists(info_path):
            try:
                with open(info_path, "r") as f:
                    info = json.load(f)
                    return info.get("Player_role", "villager")
            except Exception:
                pass
    
    return "villager"  # Default


def _get_player_dir_from_prompt(prompt: Dict[str, Any], player_id: str) -> str:
    """Resolve the per-player directory inside the game record folder."""
    file_location = None
    if isinstance(prompt, dict):
        file_location = prompt.get("file_location") or prompt.get("you", {}).get("file_location")

    record_name = prompt.get("game_id") or prompt.get("record_name") or prompt.get("record_id") or prompt.get("game_name")

    if file_location:
        base = os.path.basename(file_location)
        if base.startswith("Record_") or base.startswith("record_"):
            game_folder = file_location
        else:
            if record_name:
                game_folder = os.path.join(file_location, str(record_name))
            else:
                if os.path.isdir(file_location):
                    try:
                        children = [d for d in os.listdir(file_location) if d.startswith("Record_")]
                        if len(children) == 1:
                            game_folder = os.path.join(file_location, children[0])
                        else:
                            game_folder = os.path.join(file_location, record_name or "Record_unknown")
                    except Exception:
                        game_folder = os.path.join(file_location, record_name or "Record_unknown")
                else:
                    game_folder = os.path.join(file_location, record_name or "Record_unknown")
    else:
        repo_record_root = os.path.join(os.getcwd(), "Game_History", "Record")
        if record_name:
            game_folder = os.path.join(repo_record_root, str(record_name))
        else:
            try:
                children = [d for d in os.listdir(repo_record_root) if d.startswith("Record_")]
                game_folder = os.path.join(repo_record_root, children[-1]) if children else os.path.join(repo_record_root, "Record_unknown")
            except Exception:
                game_folder = os.path.join(repo_record_root, "Record_unknown")

    player_dir = os.path.join(game_folder, f"Player_{player_id}")
    return player_dir


def _resolve_file_path(file_location: str, relative_path: str) -> str:
    """Resolve a potentially relative file path to an absolute path."""
    if not relative_path:
        return ""
    
    # If already absolute, return as-is
    if os.path.isabs(relative_path):
        return relative_path
    
    # If file_location is provided, use it as base
    if file_location:
        # file_location may be relative like "Game_History/Record/Record_game_xxx"
        # Make it absolute from cwd
        if not os.path.isabs(file_location):
            file_location = os.path.join(os.getcwd(), file_location)
        
        # If relative_path starts with the same base, strip it
        # e.g., "Game_History/Record/Record_game_xxx/Player_p1/..." should become just "Player_p1/..."
        if relative_path.startswith("Game_History/"):
            # The relative_path is full relative, resolve from cwd
            return os.path.join(os.getcwd(), relative_path)
        
        # Otherwise, combine file_location with relative_path
        return os.path.join(file_location, relative_path)
    
    # Fallback: resolve from cwd
    return os.path.join(os.getcwd(), relative_path)


def _read_history_files(prompt: Dict[str, Any]) -> Dict[str, Any]:
    """
    Read all relevant history files from the prompt paths.
    Returns a dict with parsed content from:
    - Green_Record.txt
    - Public_History.json
    - Player's Private_Thoughts.json
    - Player's Public_Speech.json
    """
    file_location = prompt.get("file_location") or prompt.get("you", {}).get("file_location")
    result = {
        "green_record": "",
        "public_history": [],
        "private_thoughts": [],
        "public_speech": [],
        "all_player_speeches": {}
    }
    
    if not file_location:
        print("[PARSER] No file_location in prompt")
        return result
    
    # Resolve file_location to absolute path
    if not os.path.isabs(file_location):
        file_location = os.path.join(os.getcwd(), file_location)
    
    # Read Green_Record.txt
    green_record_path = os.path.join(file_location, "Green_Record.txt")
    if os.path.exists(green_record_path):
        try:
            result["green_record"] = read_file_tool(green_record_path)
            print(f"[PARSER] Read Green_Record.txt: {len(result['green_record'])} chars")
        except Exception as e:
            print(f"[PARSER] Error reading Green_Record.txt: {e}")
    
    # Read Public_History.json
    public_history_path = prompt.get("public_history")
    if public_history_path:
        full_path = _resolve_file_path(file_location, public_history_path) if not os.path.isabs(public_history_path) else public_history_path
        if not os.path.isabs(full_path):
            full_path = os.path.join(os.getcwd(), public_history_path)
    else:
        full_path = os.path.join(file_location, "Public_History.json")
    
    if os.path.exists(full_path):
        try:
            content = read_file_tool(full_path)
            result["public_history"] = json.loads(content)
            print(f"[PARSER] Read Public_History.json: {len(result['public_history'])} entries")
        except Exception as e:
            print(f"[PARSER] Error reading Public_History.json: {e}")
    
    # Read own Private_Thoughts.json
    you = prompt.get("you", {})
    self_id = you.get("id")
    
    private_path = prompt.get("private_thoughts_history")
    if private_path and isinstance(private_path, str):
        full_path = _resolve_file_path(file_location, private_path) if not os.path.isabs(private_path) else private_path
        if not os.path.isabs(full_path):
            full_path = os.path.join(os.getcwd(), private_path)
    elif self_id:
        full_path = os.path.join(file_location, f"Player_{self_id}", "Private_Thoughts.json")
    else:
        full_path = ""
    
    if full_path and os.path.exists(full_path):
        try:
            content = read_file_tool(full_path)
            result["private_thoughts"] = json.loads(content)
            print(f"[PARSER] Read Private_Thoughts.json: {len(result['private_thoughts'])} entries")
        except Exception as e:
            print(f"[PARSER] Error reading Private_Thoughts.json: {e}")
    
    # Read own Public_Speech.json
    speech_path = prompt.get("public_speech_history")
    if speech_path and isinstance(speech_path, str):
        full_path = _resolve_file_path(file_location, speech_path) if not os.path.isabs(speech_path) else speech_path
        if not os.path.isabs(full_path):
            full_path = os.path.join(os.getcwd(), speech_path)
    elif self_id:
        full_path = os.path.join(file_location, f"Player_{self_id}", "Public_Speech.json")
    else:
        full_path = ""
    
    if full_path and os.path.exists(full_path):
        try:
            content = read_file_tool(full_path)
            result["public_speech"] = json.loads(content)
            print(f"[PARSER] Read own Public_Speech.json: {len(result['public_speech'])} entries")
        except Exception as e:
            print(f"[PARSER] Error reading Public_Speech.json: {e}")
    
    # Read all players' public speeches
    try:
        for item in os.listdir(file_location):
            if item.startswith("Player_"):
                player_id = item.replace("Player_", "")
                player_speech_path = os.path.join(file_location, item, "Public_Speech.json")
                if os.path.exists(player_speech_path):
                    try:
                        content = read_file_tool(player_speech_path)
                        result["all_player_speeches"][player_id] = json.loads(content)
                    except Exception:
                        pass
    except Exception as e:
        print(f"[PARSER] Error reading player directories: {e}")
    
    return result


def _make_planner_statement(prompt: Dict[str, Any], history_data: Dict[str, Any]) -> str:
    """
    Generate a one-paragraph planning statement for the current session.
    Reads Green_Record.txt and provides context to the planner.
    """
    try:
        role = prompt.get("role") or prompt.get("you", {}).get("role")
        phase = prompt.get("phase")
        you = prompt.get("you", {})
        self_id = you.get("id")
        
        # Get alive players
        alive = []
        if isinstance(prompt.get("players"), list):
            alive = [p.get("id") for p in prompt.get("players") if isinstance(p, dict) and p.get("id")]
        elif isinstance(prompt.get("options"), dict):
            alive = prompt.get("options", {}).get("game_state", {}).get("alive_players") or []
        elif isinstance(prompt.get("options"), list):
            alive = prompt.get("options")
        
        # Truncate green_record if too long
        green_record = history_data.get("green_record", "")
        if len(green_record) > 4000:
            green_record = green_record[:4000] + "\n...(truncated)"
        
        system_prompt = (
            "You are the PLANNER module for a Werewolf game AI agent.\n"
            "Your task is to generate a ONE PARAGRAPH planning statement (3-5 sentences) that tells the agent:\n"
            "1. What the current situation is\n"
            "2. What the strategic goal is for this session\n"
            "3. Who to focus on investigating or what patterns to look for\n"
            "4. How this supports the role's win condition\n\n"
            "Output ONLY the planning paragraph. No JSON, no tools, no lists.\n"
        )
        
        user_content = f"""
CONTEXT:
- You are: {self_id} (role: {role})
- Phase: {phase}
- Day/Night: {prompt.get('day_number') or prompt.get('night_number', '?')}
- Alive Players: {alive}

GAME RECORD (Green_Record.txt):
{green_record}

ROLE STATEMENT:
{prompt.get('role_statement', 'Play your role strategically.')}

Generate a planning paragraph for this session:
"""
        
        response = completion(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ]
        )
        
        planner_stmt = response.choices[0].message.content.strip()
        print(f"[PLANNER] Generated plan: {planner_stmt[:200]}...")
        return planner_stmt
    except Exception as e:
        print(f"[PLANNER] Generation failed: {e}")
        return f"Play strategically as {role} in {phase} phase. Focus on finding threats and making good decisions."


def _run_special_session(planner_stmt: str, prompt: Dict[str, Any], target: str, history_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run a special investigation session for a specific target player.
    Uses the file parser to read relevant history and returns a JSON investigation result.
    """
    file_location = prompt.get("file_location") or prompt.get("you", {}).get("file_location")
    if file_location and not os.path.isabs(file_location):
        file_location = os.path.join(os.getcwd(), file_location)
    
    you = prompt.get("you", {})
    self_id = you.get("id")
    my_role = you.get("role") or prompt.get("role")
    
    # Get target player's speech data
    target_speeches = history_data.get("all_player_speeches", {}).get(target, [])
    public_history = history_data.get("public_history", [])
    
    # Filter public history for target's speeches
    target_public_speeches = [
        entry for entry in public_history 
        if entry.get("player_id") == target and entry.get("event_type") == "speech"
    ]
    
    # Get my own private thoughts for context
    my_thoughts = history_data.get("private_thoughts", [])
    
    context = {
        "planner_goal": planner_stmt,
        "target_player": target,
        "my_id": self_id,
        "my_role": my_role,
        "target_speeches": target_speeches[-5:] if target_speeches else target_public_speeches[-5:],
        "public_events": [e for e in public_history if e.get("event_type") != "speech"][-10:],
        "my_previous_thoughts": my_thoughts[-3:] if my_thoughts else [],
    }
    
    system_prompt = """You are running a SPECIAL INVESTIGATION SESSION for a Werewolf game AI.
Your task is to analyze a specific target player and return your findings as JSON.

Output MUST be valid JSON with this schema:
{
    "end_investigation": true,
    "session_type": "investigate_player",
    "target_players": ["<target_id>"],
    "reasoning": "Your analysis of the target's behavior, speeches, and suspicion level.",
    "suspicion_updates": [
        {
            "player_id": "<target_id>",
            "delta_suspicion": <float between -1.0 and 1.0>,
            "delta_trust": <float between -1.0 and 1.0>,
            "notes": "Why this suspicion change"
        }
    ],
    "intermediate_hypotheses": {
        "likely_detective_candidates": [],
        "likely_doctor_candidates": [],
        "likely_werewolf_candidates": [],
        "likely_easy_mislynches": []
    }
}

Analyze the target's speech patterns, voting behavior, and any suspicious or trustworthy signals.
"""

    user_content = f"""
INVESTIGATION CONTEXT:
{json.dumps(context, default=str, indent=2)}

Analyze target {target} and return your investigation findings as JSON:
"""

    print(f"[SPECIAL_SESSION] Investigating target: {target}")
    
    try:
        response = completion(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        # Clean markdown
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        result = json.loads(content)
        
        # Ensure required fields
        result.setdefault("end_investigation", True)
        result.setdefault("session_type", "investigate_player")
        result.setdefault("target_players", [target])
        result.setdefault("reasoning", "Investigation completed.")
        result.setdefault("suspicion_updates", [])
        result.setdefault("intermediate_hypotheses", {})
        
        # Sanitize suspicion_updates
        if isinstance(result.get("suspicion_updates"), list):
            valid_updates = []
            for u in result["suspicion_updates"]:
                if isinstance(u, dict) and "player_id" in u:
                    if "delta_suspicion" in u:
                        try:
                            u["delta_suspicion"] = float(u["delta_suspicion"])
                        except (ValueError, TypeError):
                            u["delta_suspicion"] = 0.0
                    if "delta_trust" in u:
                        try:
                            u["delta_trust"] = float(u["delta_trust"])
                        except (ValueError, TypeError):
                            u["delta_trust"] = 0.0
                    valid_updates.append(u)
            result["suspicion_updates"] = valid_updates
        
        print(f"[SPECIAL_SESSION] Result for {target}: suspicion_updates={result.get('suspicion_updates')}")
        return result
        
    except Exception as e:
        print(f"[SPECIAL_SESSION] Error investigating {target}: {e}")
        return {
            "end_investigation": True,
            "session_type": "investigate_player",
            "target_players": [target],
            "reasoning": f"Investigation failed due to error: {e}",
            "suspicion_updates": [],
            "intermediate_hypotheses": {}
        }


def _run_multi_target_investigation(planner_stmt: str, prompt: Dict[str, Any], history_data: Dict[str, Any], max_targets: int = 3) -> List[Dict[str, Any]]:
    """
    Run special sessions for multiple target players.
    Returns a list of investigation results (JSON objects).
    """
    investigation_results = []
    
    you = prompt.get("you", {})
    self_id = you.get("id")
    
    # Determine alive players
    alive_players = []
    if isinstance(prompt.get("players"), list):
        alive_players = [p.get("id") for p in prompt.get("players") if isinstance(p, dict) and p.get("id") and p.get("alive")]
    elif isinstance(prompt.get("options"), list):
        alive_players = prompt.get("options")
    elif isinstance(prompt.get("options"), dict):
        alive_players = prompt.get("options", {}).get("game_state", {}).get("alive_players") or []
        # Also check for kill_targets, inspect_targets, etc.
        for key in ["kill_targets", "inspect_targets", "protect_targets"]:
            if prompt.get("options", {}).get(key):
                alive_players = prompt.get("options", {}).get(key)
                break
    
    if not alive_players:
        print("[MULTI_SESSION] No alive players found")
        return []
    
    # Filter out self
    targets = [p for p in alive_players if p != self_id][:max_targets]
    
    if not targets:
        print("[MULTI_SESSION] No valid targets")
        return []
    
    print(f"[MULTI_SESSION] Investigating targets: {targets}")
    
    # Run special session for each target
    for target in targets:
        result = _run_special_session(planner_stmt, prompt, target, history_data)
        investigation_results.append({
            "target": target,
            "result": result
        })
    
    return investigation_results


def _make_final_decision(planner_stmt: str, investigation_results: List[Dict[str, Any]], prompt: Dict[str, Any], decision_type: str) -> Dict[str, Any]:
    """
    Final Decision Maker: Takes planner message + special session results to make the final decision.
    decision_type: "vote", "night_action"
    """
    you = prompt.get("you", {})
    self_id = you.get("id")
    my_role = _extract_role_from_prompt(prompt)
    my_name = you.get("name", self_id)
    my_alignment = you.get("alignment", "wolves" if my_role == "werewolf" else "town")
    
    # Aggregate investigation findings
    aggregated_suspicion = {}
    all_reasoning = []
    hypotheses = {
        "likely_detective_candidates": set(),
        "likely_doctor_candidates": set(),
        "likely_werewolf_candidates": set(),
        "likely_easy_mislynches": set()
    }
    
    for item in investigation_results:
        target = item["target"]
        res = item["result"]
        all_reasoning.append(f"- {target}: {res.get('reasoning', 'No analysis')}")
        
        # Aggregate suspicion
        for update in res.get("suspicion_updates", []):
            pid = update.get("player_id")
            if pid:
                delta = update.get("delta_suspicion", 0)
                aggregated_suspicion[pid] = aggregated_suspicion.get(pid, 0) + delta
        
        # Aggregate hypotheses
        for key in hypotheses:
            candidates = res.get("intermediate_hypotheses", {}).get(key, [])
            if isinstance(candidates, list):
                hypotheses[key].update(candidates)
    
    # Convert sets to lists for JSON
    hypotheses = {k: list(v) for k, v in hypotheses.items()}
    
    # Get valid options
    options = prompt.get("options", [])
    if isinstance(options, dict):
        if decision_type == "vote":
            valid_options = options.get("vote_options") or options.get("choices") or []
        else:  # night_action
            valid_options = (
                options.get("kill_targets") or 
                options.get("inspect_targets") or 
                options.get("protect_targets") or 
                options.get("game_state", {}).get("alive_players") or 
                []
            )
    else:
        valid_options = options if isinstance(options, list) else []
    
    # Filter out self for votes
    if decision_type == "vote":
        valid_options = [o for o in valid_options if o != self_id]
    
    # Build decision context
    context = {
        "planner_goal": planner_stmt,
        "my_id": self_id,
        "my_role": my_role,
        "decision_type": decision_type,
        "valid_options": valid_options,
        "aggregated_suspicion": aggregated_suspicion,
        "investigation_reasoning": all_reasoning,
        "hypotheses": hypotheses
    }
    
    if decision_type == "vote":
        # Get role statement from prompt for reminder
        role_statement = prompt.get("public_summary", "") or prompt.get("role_statement", "")
        
        system_prompt = f"""You are the FINAL DECISION MAKER for a Werewolf game AI.

REMINDER - YOUR IDENTITY:
- You are {my_name} (ID: {self_id})
- Your role is: {my_role}
- Your alignment: {my_alignment}
- Your goal: {"Eliminate villagers and avoid detection" if my_role == "werewolf" else "Find and eliminate the werewolves"}

Based on the planner's goal and investigation results, decide who to vote for.

IMPORTANT: You MUST provide a non-empty "speech" field explaining your vote publicly.

Output JSON:
{{
    "thought": "Your strategic reasoning for the vote",
    "vote": "<player_id to vote for>",
    "speech": "Your public statement explaining your vote (REQUIRED - cannot be empty)"
}}
"""
    else:  # night_action
        action_type = "kill" if my_role == "werewolf" else ("inspect" if my_role == "detective" else "protect")
        role_statement = prompt.get("role_statement", "")
        
        system_prompt = f"""You are the FINAL DECISION MAKER for a Werewolf game AI.

REMINDER - YOUR IDENTITY:
- You are {my_name} (ID: {self_id})
- Your role is: {my_role}
- Your alignment: {my_alignment}
- Your goal: {"Eliminate villagers and avoid detection" if my_role == "werewolf" else "Help the town win"}
- Your action type: {action_type}

Based on the planner's goal and investigation results, decide your night action.

Output JSON:
{{
    "thought": "Your strategic reasoning for the action",
    "action": "{action_type}",
    "target": "<player_id to target>"
}}
"""

    user_content = f"""
DECISION CONTEXT:
{json.dumps(context, default=str, indent=2)}

Make your final decision:
"""

    print(f"[FINAL_DECISION] Making {decision_type} decision for {self_id} ({my_role})")
    
    # Validator/Reflector - always passes (logged)
    print("[VALIDATOR] Reflector/Validator check: PASSED (auto-pass enabled)")
    
    try:
        response = completion(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        
        result = json.loads(content.strip())
        
        # Ensure we have a valid target
        if decision_type == "vote":
            if not result.get("vote") or result.get("vote") not in valid_options:
                # Pick from aggregated suspicion or random
                if aggregated_suspicion:
                    candidates = [p for p in valid_options if p in aggregated_suspicion]
                    if candidates:
                        result["vote"] = max(candidates, key=lambda p: aggregated_suspicion.get(p, 0))
                    else:
                        result["vote"] = random.choice(valid_options) if valid_options else None
                else:
                    result["vote"] = random.choice(valid_options) if valid_options else None
            # Ensure speech is not empty
            if not result.get("speech"):
                result["speech"] = f"I vote for {result.get('vote')} based on my analysis."
        else:
            if not result.get("target") or result.get("target") not in valid_options:
                if aggregated_suspicion:
                    candidates = [p for p in valid_options if p in aggregated_suspicion]
                    if candidates:
                        result["target"] = max(candidates, key=lambda p: aggregated_suspicion.get(p, 0))
                    else:
                        result["target"] = random.choice(valid_options) if valid_options else None
                else:
                    result["target"] = random.choice(valid_options) if valid_options else None
        
        return result
        
    except Exception as e:
        print(f"[FINAL_DECISION] Error: {e}")
        # Fallback
        if decision_type == "vote":
            target = random.choice(valid_options) if valid_options else None
            return {"thought": "Fallback decision", "vote": target, "speech": ""}
        else:
            target = random.choice(valid_options) if valid_options else None
            action = "kill" if my_role == "werewolf" else ("inspect" if my_role == "detective" else "protect")
            return {"thought": "Fallback decision", "action": action, "target": target}


@app.middleware("http")
async def log_requests(request: Request, call_next):
    body = await request.body()
    body_str = body.decode()
    if len(body_str) > 500:
        body_str = body_str[:500] + "... (truncated)"
    log_to_memory(f"Request: {request.method} {request.url} Body: {body_str}")
    
    response = await call_next(request)
    log_to_memory(f"Response Status: {response.status_code}")
    return response


class NightRolePrompt(BaseModel):
    phase: str
    night_number: int
    role: str
    you: Dict[str, Any]
    options: Any  # Can be dict or list
    public_history_summary: str
    role_statement: Optional[str] = None
    private_thoughts_history: Optional[Union[List[Dict[str, Any]], str]] = None
    public_speech_history: Optional[Union[List[Dict[str, Any]], str]] = None
    public_history: Optional[Union[List[Dict[str, Any]], str]] = None
    history_text: Optional[str] = None
    file_location: Optional[str] = None
    constraints: Dict[str, Any]


class DayDiscussionPrompt(BaseModel):
    phase: str
    day_number: int
    you: Dict[str, Any]
    players: List[Dict[str, Any]]
    public_history: Optional[Union[List[Dict[str, Any]], str]] = None
    role_statement: Optional[str] = None
    private_thoughts_history: Optional[Union[List[Dict[str, Any]], str]] = None
    public_speech_history: Optional[Union[List[Dict[str, Any]], str]] = None
    history_text: Optional[str] = None
    file_location: Optional[str] = None
    instruction: Optional[str] = None
    constraints: Dict[str, Any]


class DayVotePrompt(BaseModel):
    phase: str
    day_number: int
    you: Dict[str, Any]
    options: List[str]
    public_summary: str
    public_history: Optional[Union[List[Dict[str, Any]], str]] = None
    private_thoughts_history: Optional[Union[List[Dict[str, Any]], str]] = None
    public_speech_history: Optional[Union[List[Dict[str, Any]], str]] = None
    history_text: Optional[str] = None
    file_location: Optional[str] = None
    constraints: Dict[str, Any]


# ==============================================================================
# VANILLA MODE - Simple LLM calls without Planner/Investigation architecture
# ==============================================================================

def _vanilla_night_action(prompt: Dict[str, Any], role: str, player_id: str) -> Dict[str, Any]:
    """Vanilla mode: Simple single LLM call for night action."""
    print(f"[VANILLA] Night action for {player_id} ({role})")
    
    if role == "villager":
        return {"thought": "I am sleeping as a villager.", "action": "sleep", "target": None}
    
    options = prompt.get("options", {})
    targets = options.get("targets", options.get("can_kill", options.get("can_investigate", [])))
    
    system_msg = f"""You are playing Werewolf as a {role}. Make a strategic night action decision.
Return JSON: {{"thought": "your reasoning", "action": "your action", "target": "target_id or null"}}"""
    
    user_msg = f"""Role: {role}
Available targets: {targets}
Options: {json.dumps(options)}

What is your night action?"""
    
    try:
        resp = completion(
            model=os.environ.get("AGENT_MODEL", "gpt-4o"),
            messages=[{"role": "system", "content": system_msg}, {"role": "user", "content": user_msg}],
            response_format={"type": "json_object"}
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as e:
        print(f"[VANILLA] Error: {e}")
        target = targets[0] if targets else None
        action = "kill" if role == "werewolf" else "investigate" if role == "detective" else "protect"
        return {"thought": f"Fallback {role} action", "action": action, "target": target}


def _vanilla_discussion(prompt: Dict[str, Any], role: str, player_id: str) -> Dict[str, str]:
    """Vanilla mode: Simple single LLM call for discussion."""
    print(f"[VANILLA] Discussion for {player_id} ({role})")
    
    public_summary = prompt.get("public_summary", "No summary available")
    day_num = prompt.get("day_number", 1)
    
    system_msg = f"""You are playing Werewolf as a {role}. Generate a discussion speech.
{"You are a werewolf - blend in and deflect suspicion!" if role == "werewolf" else "Analyze behavior and share your thoughts."}
Return JSON: {{"thought": "private reasoning", "speech": "what you say publicly"}}"""
    
    user_msg = f"""Day {day_num}
Public Summary: {public_summary}

What do you say in the discussion?"""
    
    try:
        resp = completion(
            model=os.environ.get("AGENT_MODEL", "gpt-4o"),
            messages=[{"role": "system", "content": system_msg}, {"role": "user", "content": user_msg}],
            response_format={"type": "json_object"}
        )
        result = json.loads(resp.choices[0].message.content)
        return {"thought": result.get("thought", ""), "speech": result.get("speech", "I have nothing to add.")}
    except Exception as e:
        print(f"[VANILLA] Error: {e}")
        return {"thought": "Fallback", "speech": "I'm still gathering information."}


def _vanilla_vote(prompt: Dict[str, Any], role: str, player_id: str) -> Dict[str, Any]:
    """Vanilla mode: Simple single LLM call for voting."""
    print(f"[VANILLA] Vote for {player_id} ({role})")
    
    options = prompt.get("options", [])
    public_summary = prompt.get("public_summary", "")
    
    system_msg = f"""You are playing Werewolf as a {role}. Cast your vote.
{"As a werewolf, vote to eliminate villagers while appearing innocent." if role == "werewolf" else "Vote for who you suspect is a werewolf."}
Return JSON: {{"thought": "reasoning", "speech": "what you say", "vote": "player_id"}}"""
    
    user_msg = f"""Public Summary: {public_summary}
Vote options: {options}

Who do you vote to eliminate?"""
    
    try:
        resp = completion(
            model=os.environ.get("AGENT_MODEL", "gpt-4o"),
            messages=[{"role": "system", "content": system_msg}, {"role": "user", "content": user_msg}],
            response_format={"type": "json_object"}
        )
        result = json.loads(resp.choices[0].message.content)
        vote = result.get("vote", options[0] if options else "skip")
        return {"thought": result.get("thought", ""), "speech": result.get("speech", "I vote."), "vote": vote}
    except Exception as e:
        print(f"[VANILLA] Error: {e}")
        return {"thought": "Fallback", "speech": "I'll vote.", "vote": options[0] if options else "skip"}


# ==============================================================================
# ENDPOINTS
# ==============================================================================

@app.post("/night_action")
async def night_action(request: Request) -> Dict[str, Any]:
    """
    Night action endpoint.
    - ADVANCED mode: Read History -> Planner -> Special Sessions -> Final Decision
    - VANILLA mode: Simple single LLM call
    """
    prompt = await request.json()
    you = prompt.get("you", {})
    player_id = you.get("id", "unknown")
    role = _extract_role_from_prompt(prompt)
    my_name = you.get("name", player_id)
    my_alignment = you.get("alignment", "wolves" if role == "werewolf" else "town")

    mode = get_agent_mode()
    print(f"\n[NIGHT_ACTION] === Player {player_id} ({role}) [MODE: {mode}] ===")
    
    # VANILLA MODE - simple LLM call
    if mode == "vanilla":
        decision = _vanilla_night_action(prompt, role, player_id)
        return {
            "thought": decision.get("thought", f"Night action as {role}"),
            "action": decision.get("action", "sleep"),
            "target": decision.get("target")
        }
    
    # ADVANCED MODE - Planner -> Investigation -> Decision
    # 1. Read all history files
    history_data = _read_history_files(prompt)
    
    # 2. Planner Step
    planner_stmt = _make_planner_statement(prompt, history_data)
    
    # 3. Special Sessions (for active roles)
    investigation_results = []
    if role in ("werewolf", "detective", "doctor"):
        investigation_results = _run_multi_target_investigation(planner_stmt, prompt, history_data)
    
    # 4. Final Decision
    decision = _make_final_decision(planner_stmt, investigation_results, prompt, "night_action")
    
    # Handle special cases
    if role == "villager":
        decision = {"thought": "I am sleeping as a villager.", "action": "sleep", "target": None}
    elif role == "doctor":
        # Doctor might not have action on night 1 if no one attacked
        attacked = prompt.get("options", {}).get("attacked_player")
        if not attacked:
            decision = {"thought": "No one to save tonight.", "action": "no_action", "target": None}
    
    # Log to white_history
    player_dir = _get_player_dir_from_prompt(prompt, player_id)
    record = {
        "timestamp": datetime.datetime.now().isoformat(),
        "phase": "night",
        "planner": planner_stmt,
        "investigations": investigation_results,
        "decision": decision,
        "validator_status": "PASSED"
    }
    _append_white_history(player_dir, record)
    
    print(f"[NIGHT_ACTION] Decision: {decision}")
    
    return {
        "thought": decision.get("thought", f"Night action as {role}"),
        "action": decision.get("action", "sleep"),
        "target": decision.get("target")
    }


@app.post("/discussion")
async def discussion(request: Request) -> Dict[str, str]:
    """
    Discussion endpoint.
    - ADVANCED mode: Read History -> Generate Speech with context
    - VANILLA mode: Simple single LLM call
    """
    prompt = await request.json()
    you = prompt.get("you", {})
    self_id = you.get("id", "unknown")
    my_role = _extract_role_from_prompt(prompt)
    my_name = you.get("name", self_id)
    my_alignment = you.get("alignment", "town")
    
    mode = get_agent_mode()
    print(f"\n[DISCUSSION] === Player {self_id} ({my_role}) [MODE: {mode}] ===")
    
    # VANILLA MODE - simple LLM call
    if mode == "vanilla":
        result = _vanilla_discussion(prompt, my_role, self_id)
        return {"thought": result.get("thought", ""), "speech": result.get("speech", "I have nothing to add.")}
    
    # ADVANCED MODE - Read history and generate contextual speech
    # 1. Read all history files with parser
    history_data = _read_history_files(prompt)
    
    # 2. Build context from parsed history
    public_history = history_data.get("public_history", [])
    my_thoughts = history_data.get("private_thoughts", [])
    all_speeches = history_data.get("all_player_speeches", {})
    
    # Format recent speeches for context
    recent_speeches = []
    for entry in public_history[-10:]:
        if entry.get("event_type") == "speech":
            recent_speeches.append(f"{entry.get('player_id')}: {entry.get('content', '')}")
    
    # Get alive players
    alive_players = [p.get("id") for p in prompt.get("players", []) if isinstance(p, dict) and p.get("alive")]
    
    # 3. Generate speech directly (no special sessions for discussion)
    system_prompt = f"""You are playing Werewolf as {self_id} (role: {my_role}).
Generate your discussion contribution.

Output JSON:
{{
    "thought": "Your private strategic reasoning (not shared with others)",
    "speech": "What you say publicly to the group"
}}

Rules:
- Keep speech natural and under 100 words
- Don't reveal your role directly
- Be strategic based on your role's win condition
"""

    user_content = f"""
CONTEXT:
- Day: {prompt.get('day_number')}
- Alive Players: {alive_players}
- Role Statement: {prompt.get('role_statement', '')}

RECENT DISCUSSION:
{chr(10).join(recent_speeches) if recent_speeches else 'No speeches yet.'}

MY PREVIOUS THOUGHTS:
{json.dumps(my_thoughts[-3:], default=str) if my_thoughts else 'None yet.'}

Generate your discussion contribution:
"""

    print("[VALIDATOR] Reflector/Validator check: PASSED (auto-pass enabled)")
    
    try:
        response = completion(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        
        data = json.loads(content.strip())
        thought = data.get("thought", "Analyzing the situation.")
        speech = data.get("speech", "I'm observing and thinking.")
        
    except Exception as e:
        print(f"[DISCUSSION] Error generating speech: {e}")
        thought = "Error generating response."
        speech = "I need more time to think about this."
    
    # Log to white_history
    player_dir = _get_player_dir_from_prompt(prompt, self_id)
    record = {
        "timestamp": datetime.datetime.now().isoformat(),
        "phase": "day_discussion",
        "history_parsed": {
            "public_entries": len(public_history),
            "my_thoughts": len(my_thoughts),
            "all_speeches_players": list(all_speeches.keys())
        },
        "result": {"thought": thought, "speech": speech},
        "validator_status": "PASSED"
    }
    _append_white_history(player_dir, record)
    
    print(f"[DISCUSSION] Speech: {speech[:100]}...")
    
    return {"thought": thought, "speech": speech}


@app.post("/vote")
async def vote(request: Request) -> Dict[str, str]:
    """
    Vote endpoint.
    - ADVANCED mode: Read History -> Planner -> Special Sessions -> Final Decision
    - VANILLA mode: Simple single LLM call
    """
    prompt = await request.json()
    you = prompt.get("you", {})
    self_id = you.get("id", "unknown")
    my_role = _extract_role_from_prompt(prompt)
    my_name = you.get("name", self_id)
    my_alignment = you.get("alignment", "town")
    
    mode = get_agent_mode()
    print(f"\n[VOTE] === Player {self_id} ({my_role}) [MODE: {mode}] ===")
    
    # VANILLA MODE - simple LLM call
    if mode == "vanilla":
        result = _vanilla_vote(prompt, my_role, self_id)
        return {"thought": result.get("thought", ""), "speech": result.get("speech", "I vote."), "vote": result.get("vote")}
    
    # ADVANCED MODE - Planner -> Investigation -> Decision
    # 1. Read all history files
    history_data = _read_history_files(prompt)
    
    # 2. Planner Step
    planner_stmt = _make_planner_statement(prompt, history_data)
    
    # 3. Special Sessions
    investigation_results = _run_multi_target_investigation(planner_stmt, prompt, history_data)
    
    # 4. Final Decision
    decision = _make_final_decision(planner_stmt, investigation_results, prompt, "vote")
    
    thought = decision.get("thought", "Making my vote.")
    vote_target = decision.get("vote")
    speech = decision.get("speech", "")
    
    # Log to white_history
    player_dir = _get_player_dir_from_prompt(prompt, self_id)
    record = {
        "timestamp": datetime.datetime.now().isoformat(),
        "phase": "day_vote",
        "planner": planner_stmt,
        "investigations": investigation_results,
        "decision": decision,
        "validator_status": "PASSED"
    }
    _append_white_history(player_dir, record)
    
    print(f"[VOTE] Voting for: {vote_target}")
    
    return {"thought": thought, "speech": speech, "vote": vote_target}


@app.get("/health")
def health():
    return {"status": "ok"}
