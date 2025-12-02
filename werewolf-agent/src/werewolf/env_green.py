from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from fastapi import FastAPI, HTTPException

from .demo_script import DEMO_SCENARIO
from .metrics import build_metrics
from .models import (
    Assessment,
    DayDiscussionConstraints,
    DayDiscussionPrompt,
    DayDiscussionResponse,
    DayPhaseRecord,
    DayPublicState,
    DayVotePrompt,
    DayVotingRecord,
    DiscussionTurn,
    GameRecord,
    MatchRequest,
    NightActionRequest,
    NightActionResponse,
    NightContextRequest,
    NightContextResponse,
    NightPhaseRecord,
    NightPhaseResolveRequest,
    NightPhaseResolveResponse,
    NightPhaseStartRequest,
    NightPhaseStartResponse,
    NightPromptRecord,
    NightRolePrompt,
    NightResponseRecord,
    NightResolution,
    PlayerProfile,
    VotePromptRecord,
    VoteResponse,
    VoteResponseRecord,
    VoteResolution,
)
from .rules import night_kill_resolution, resolve_vote
from .state import GameState
from .night_prompts import (
    generate_wolf_night_prompt,
    generate_detective_night_prompt,
    generate_doctor_night_prompt,
    generate_villager_night_prompt
)
from .night_tools import (
    get_night_tools_for_role,
    validate_night_action,
    format_night_action_response
)
from .elo_system import EloCalculator, create_elo_calculator

app = FastAPI(title="Werewolf Green Agent", description="Design-doc referee demo")

@app.get("/health")
def health():
    return {"status": "ok"}

# Global ELO calculator instance
elo_calculator = create_elo_calculator()


def _player_profiles() -> List[PlayerProfile]:
    profiles: List[PlayerProfile] = []
    for entry in DEMO_SCENARIO["players"]:
        profiles.append(
            PlayerProfile(
                id=entry["id"],
                alias=entry.get("alias"),
                role_private=entry.get("role"),
                alignment=entry.get("alignment"),
                alive=entry.get("alive", True),
                provider=entry.get("provider"),
                model=entry.get("model"),
                initial_elo=entry.get("initial_elo", {"overall": 1500, "wolf": 1500, "villager": 1500}),
            )
        )
    return profiles


def _role_assignment() -> Dict[str, str]:
    return {entry["id"]: entry["role"] for entry in DEMO_SCENARIO["players"]}


def _alignments() -> Dict[str, str]:
    return {entry["id"]: entry["alignment"] for entry in DEMO_SCENARIO["players"]}


def _public_players(state: GameState) -> List[Dict[str, object]]:
    return [{"id": pid, "alive": state.is_alive(pid)} for pid in state.players]


def _history_summary(state: GameState) -> str:
    if not state.public_history:
        return ""
    pieces: List[str] = []
    for event in state.public_history[-3:]:
        if event.get("phase") == "night":
            if event.get("event") == "night_kill":
                target = event.get("player_id") or event.get("target")
                pieces.append(f"Night {event.get('night')}: {target} was killed")
            elif event.get("event") == "no_kill":
                pieces.append(f"Night {event.get('night')}: no kill")
        elif event.get("phase") == "day" and event.get("cause") == "vote":
            pieces.append(f"Day {event.get('day')}: {event.get('player_id')} eliminated")
    return "; ".join(pieces)


def _add_wolf_prompts(
    state: GameState,
    phase_spec: Dict,
    night_number: int,
    prompts: List[NightPromptRecord],
    responses: List[NightResponseRecord],
) -> None:
    alive_players = state.living_players()
    wolf_targets = [pid for pid in alive_players if state.roles[pid] != "werewolf"]
    wolf_choice = phase_spec["wolf_choice"]
    wolf_private = phase_spec.get("wolf_private_thoughts", {})
    for wolf_id in [pid for pid in state.players if state.roles[pid] == "werewolf" and state.is_alive(pid)]:
        prompts.append(
            NightPromptRecord(
                player_id=wolf_id,
                night_role_prompt=NightRolePrompt(
                    phase="night",
                    night_number=night_number,
                    role="werewolf",
                    you={"id": wolf_id},
                    options={"kill_options": wolf_targets},
                    public_history_summary=_history_summary(state),
                ),
                private_thought=wolf_private.get(wolf_id),
            )
        )
        responses.append(
            NightResponseRecord(
                player_id=wolf_id,
                night_action_response={
                    "kill_vote": wolf_choice["target"],
                    "reason": wolf_choice.get("reason"),
                },
            )
        )


def _detective_prompt(
    state: GameState,
    phase_spec: Dict,
    night_number: int,
    prompts: List[NightPromptRecord],
    responses: List[NightResponseRecord],
) -> Optional[Dict[str, object]]:
    detective = phase_spec.get("detective_action")
    if not detective:
        return None
    detective_id = detective["detective"]
    if not state.is_alive(detective_id):
        return None
    inspect_options = [pid for pid in state.living_players() if pid != detective_id]
    prompts.append(
        NightPromptRecord(
            player_id=detective_id,
            night_role_prompt=NightRolePrompt(
                phase="night",
                night_number=night_number,
                role="detective",
                you={"id": detective_id},
                options={"inspect_options": inspect_options},
                public_history_summary=_history_summary(state),
            ),
            private_thought=detective.get("private_thought"),
        )
    )
    responses.append(
        NightResponseRecord(
            player_id=detective_id,
            night_action_response={"inspect": detective["inspect"]},
        )
    )
    target = detective["inspect"]
    result = state.roles[target] == "werewolf"
    state.record_inspection(detective_id, target, night_number, result)
    return {
        "detective": detective_id,
        "target": target,
        "is_werewolf": result,
        "note": detective.get("note"),
    }


def _doctor_prompt(
    state: GameState,
    phase_spec: Dict,
    night_number: int,
    prompts: List[NightPromptRecord],
    responses: List[NightResponseRecord],
) -> Optional[Dict[str, object]]:
    doctor = phase_spec.get("doctor_action")
    if not doctor:
        return None
    doctor_id = doctor["doctor"]
    if not state.is_alive(doctor_id):
        return None
    protect_options = state.living_players()
    prompts.append(
        NightPromptRecord(
            player_id=doctor_id,
            night_role_prompt=NightRolePrompt(
                phase="night",
                night_number=night_number,
                role="doctor",
                you={"id": doctor_id},
                options={"protect_options": protect_options},
                public_history_summary=_history_summary(state),
            ),
            private_thought=doctor.get("private_thought"),
        )
    )
    responses.append(
        NightResponseRecord(
            player_id=doctor_id,
            night_action_response={"protect": doctor["protect"]},
        )
    )
    return doctor


def _villager_prompts(
    state: GameState,
    phase_spec: Dict,
    night_number: int,
    prompts: List[NightPromptRecord],
    responses: List[NightResponseRecord],
) -> None:
    for pid, thought in phase_spec.get("villager_private", {}).items():
        if not state.is_alive(pid):
            continue
        prompts.append(
            NightPromptRecord(
                player_id=pid,
                night_role_prompt=NightRolePrompt(
                    phase="night",
                    night_number=night_number,
                    role=state.roles[pid],
                    you={"id": pid},
                    options={},
                    public_history_summary=_history_summary(state),
                ),
                private_thought=thought,
            )
        )
        responses.append(
            NightResponseRecord(
                player_id=pid,
                night_action_response={"sleep": True},
            )
        )


def _build_night_phase(state: GameState, phase_spec: Dict) -> NightPhaseRecord:
    night_number = phase_spec["night_number"]
    prompts: List[NightPromptRecord] = []
    responses: List[NightResponseRecord] = []

    _add_wolf_prompts(state, phase_spec, night_number, prompts, responses)
    detective_result = _detective_prompt(state, phase_spec, night_number, prompts, responses)
    doctor_spec = _doctor_prompt(state, phase_spec, night_number, prompts, responses)
    _villager_prompts(state, phase_spec, night_number, prompts, responses)

    doctor_id = doctor_spec["doctor"] if doctor_spec else None
    doctor_target = doctor_spec.get("protect") if doctor_spec else None
    kill_choice = phase_spec["wolf_choice"]
    kill_result = night_kill_resolution(kill_choice["target"], doctor_target, doctor_id)
    saved = bool(doctor_target and kill_result.get("saved_by"))

    if doctor_spec and doctor_id:
        state.record_protection(doctor_id, doctor_target, night_number, saved)
    night_target = kill_result.get("target")
    if kill_result.get("success"):
        state.eliminate(night_target, "night_kill", "night", night_number)
        state.record_night_event(night_number, "night_kill", {"player_id": night_target})
    else:
        state.record_night_event(
            night_number,
            "no_kill",
            {"target": night_target, "saved_by": kill_result.get("saved_by")},
        )
    state.night_number += 1

    resolution = NightResolution(
        wolf_team_decision={
            "target": kill_choice["target"],
            "reason": kill_choice.get("reason"),
            "unanimous": True,
        },
        detective_result=detective_result,
        doctor_protect={
            "doctor": doctor_id,
            "target": doctor_target,
            "saved": saved,
            "note": doctor_spec.get("note") if doctor_spec else None,
        }
        if doctor_spec and doctor_id
        else None,
        night_outcome={"killed": night_target if kill_result.get("success") else None},
        night_kill=kill_result,
        public_update=phase_spec.get("public_update", ""),
    )

    public_state = {
        "alive_players": state.living_players(),
        "graveyard": list(state.graveyard),
        "last_eliminated": state.last_graveyard_entry(),
    }

    return NightPhaseRecord(
        night_number=night_number,
        public_state=public_state,
        wolves_private_chat=phase_spec.get("wolves_private_chat", []),
        prompts=prompts,
        responses=responses,
        resolution=resolution,
    )


def _build_day_phase(state: GameState, phase_spec: Dict) -> DayPhaseRecord:
    day_number = phase_spec["day_number"]
    discussion_turns: List[DiscussionTurn] = []
    players_public = _public_players(state)
    public_history = list(state.public_history)

    for turn in phase_spec.get("discussion", []):
        pid = turn["player_id"]
        if not state.is_alive(pid):
            continue
        prompt = DayDiscussionPrompt(
            phase="day",
            day_number=day_number,
            you={"id": pid, "alive": state.is_alive(pid)},
            players=players_public,
            public_history=public_history,
            constraints=DayDiscussionConstraints(max_words=DEMO_SCENARIO["game"]["config"]["max_words_day_talk"]),
        )
        discussion_turns.append(
            DiscussionTurn(
                player_id=pid,
                day_discussion_prompt=prompt,
                private_thought=turn.get("private_thought"),
                day_discussion_response=DayDiscussionResponse(talk=turn.get("public_speech", "")),
            )
        )

    voting_spec = phase_spec.get("voting", {})
    prompts: List[VotePromptRecord] = []
    responses: List[VoteResponseRecord] = []
    vote_map: Dict[str, str] = {}

    for pid, prompt_spec in voting_spec.get("prompts", {}).items():
        if not state.is_alive(pid):
            continue
        prompt = DayVotePrompt(
            phase="vote",
            day_number=day_number,
            you={"id": pid},
            options=prompt_spec.get("options", []),
            public_summary=voting_spec.get("public_summary", ""),
        )
        prompts.append(
            VotePromptRecord(
                player_id=pid,
                day_vote_prompt=prompt,
                private_thought=prompt_spec.get("private_thought"),
            )
        )

    for pid, resp in voting_spec.get("responses", {}).items():
        if not state.is_alive(pid):
            continue
        vote_map[pid] = resp["vote"]
        responses.append(
            VoteResponseRecord(
                player_id=pid,
                vote_response=VoteResponse(
                    vote=resp["vote"],
                    one_sentence_reason=resp.get("reason", ""),
                ),
            )
        )
        state.record_vote(pid, resp["vote"], day_number, resp.get("reason", ""))

    tally, eliminated_pid, runoff = resolve_vote(vote_map, state.living_players())
    eliminated_payload = None
    if eliminated_pid:
        eliminated_payload = {
            "player_id": eliminated_pid,
            "role_revealed": state.roles[eliminated_pid],
            "alignment": state.alignments[eliminated_pid],
            "day_number": day_number,
        }
        state.eliminate(eliminated_pid, "vote", "day", day_number)
    else:
        state.public_history.append(
            {
                "phase": "day",
                "day": day_number,
                "event": "no_elimination",
                "tally": tally,
            }
        )
    state.day_number += 1

    resolution = VoteResolution(tally=tally, eliminated=eliminated_payload, runoff=list(runoff) if runoff else None)
    voting_record = DayVotingRecord(
        prompts=prompts,
        responses=responses,
        resolution=resolution,
        private_reactions=voting_spec.get("private_reactions", {}),
    )

    public_state = DayPublicState(alive_players=state.living_players(), public_history=list(state.public_history))

    return DayPhaseRecord(
        day_number=day_number,
        public_state=public_state,
        discussion={"turns": discussion_turns},
        voting=voting_record,
        end_of_day_summary=phase_spec.get("end_of_day_summary"),
    )


def build_record(seed: int) -> GameRecord:
    profiles = _player_profiles()
    role_assignment = _role_assignment()
    alignments = _alignments()
    state = GameState([p.id for p in profiles], role_assignment, alignments)

    phases: List = []
    phase_sequence: List[str] = []
    for phase_spec in DEMO_SCENARIO["phases"]:
        if phase_spec["phase_type"] == "night":
            phases.append(_build_night_phase(state, phase_spec))
            phase_sequence.append(f"night_{phase_spec['night_number']}")
        else:
            phases.append(_build_day_phase(state, phase_spec))
            phase_sequence.append(f"day_{phase_spec['day_number']}")
        if state.is_terminal():
            break

    final_data = DEMO_SCENARIO["final_result"]
    survivors = [
        {
            "player_id": pid,
            "role": state.roles[pid],
            "alignment": state.alignments[pid],
        }
        for pid in state.living_players()
    ]

    final_record = {
        "winning_side": final_data["winning_side"],
        "reason": final_data["reason"],
        "survivors": survivors,
        "elimination_order": list(state.elimination_order),
    }

    return GameRecord(
        schema_version=DEMO_SCENARIO["game"]["schema_version"],
        game_id=DEMO_SCENARIO["game"]["game_id"],
        created_at_utc=datetime.now(timezone.utc),
        seed=seed,
        config=DEMO_SCENARIO["game"]["config"],
        players=profiles,
        role_assignment=role_assignment,
        phase_sequence=phase_sequence,
        phases=phases,
        final_result=final_record,
    )


from .game_manager import GameManager

@app.post("/tasks/werewolf_match", response_model=Assessment)
async def run_match(req: MatchRequest) -> Assessment:
    # Convert PlayerCard to PlayerProfile
    profiles = []
    for p in req.players:
        # Assign random roles if not provided (simplified for now)
        # In a real scenario, we might want a smarter assignment logic or it comes from config
        # For now, let's assume roles are assigned by the caller or we do a random assignment here
        # BUT, the current PlayerCard doesn't have role info.
        # We need to assign roles here.
        profiles.append(PlayerProfile(
            id=p.id,
            alias=p.alias,
            provider=p.provider,
            model=p.model,
            initial_elo=p.initial_elo or {"overall": 1500, "wolf": 1500, "villager": 1500}
        ))
    
    # Simple Role Assignment Logic
    import random
    n = len(profiles)
    n_wolves = max(1, n // 3)
    roles = ["werewolf"] * n_wolves + ["villager"] * (n - n_wolves)
    # Add special roles if enough players
    if n > 4:
        roles[n_wolves] = "detective"
    if n > 5:
        roles[n_wolves+1] = "doctor"
        
    random.shuffle(roles)
    for i, p in enumerate(profiles):
        p.role_private = roles[i]
        p.alignment = "wolves" if roles[i] == "werewolf" else "town"

    manager = GameManager(profiles, req.config)
    record = await manager.run_game()
    metrics = build_metrics(record)
    return Assessment(record=record, metrics=metrics)


# Night Phase API Endpoints
@app.post("/night/start", response_model=NightPhaseStartResponse)
def start_night_phase(req: NightPhaseStartRequest) -> NightPhaseStartResponse:
    """Initialize a night phase and send prompts to all agents."""
    try:
        # For now, we'll use the demo scenario
        # In a real implementation, this would load the actual game state
        phase_id = f"night_{req.night_number}_{req.game_id}"
        
        return NightPhaseStartResponse(
            success=True,
            message=f"Night phase {req.night_number} started",
            night_number=req.night_number,
            phase_id=phase_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/night/context", response_model=NightContextResponse)
def get_night_context(req: NightContextRequest) -> NightContextResponse:
    """Get role-specific night context for a player."""
    try:
        # Create a demo game state for prompt generation
        # In real implementation, this would load from actual game state
        demo_players = ["A1", "A2", "A3", "A4", "A5", "A6"]
        demo_roles = {"A1": "peasant", "A2": "werewolf", "A3": "detective", 
                     "A4": "peasant", "A5": "werewolf", "A6": "doctor"}
        demo_alignments = {"A1": "town", "A2": "wolves", "A3": "town", 
                          "A4": "town", "A5": "wolves", "A6": "town"}
        
        state = GameState(demo_players, demo_roles, demo_alignments)
        
        # Generate role-specific prompt
        if req.role == "werewolf":
            wolf_partners = [pid for pid in demo_players if demo_roles[pid] == "werewolf" and pid != req.player_id]
            prompt = generate_wolf_night_prompt(state, req.player_id, 1, wolf_partners, [])
            
            return NightContextResponse(
                role=req.role,
                night_number=1,
                available_actions=["kill", "wolf_chat"],
                targets=[pid for pid in demo_players if demo_roles[pid] != "werewolf"],
                private_info={
                    "wolf_partners": wolf_partners,
                    "wolf_chat_history": [],
                    "prompt": prompt.model_dump()
                },
                public_info={
                    "alive_players": demo_players,
                    "last_elimination": None
                }
            )
        elif req.role == "detective":
            prompt = generate_detective_night_prompt(state, req.player_id, 1, [])
            
            return NightContextResponse(
                role=req.role,
                night_number=1,
                available_actions=["inspect"],
                targets=[pid for pid in demo_players if pid != req.player_id],
                private_info={
                    "previous_inspections": [],
                    "prompt": prompt.model_dump()
                },
                public_info={
                    "alive_players": demo_players,
                    "last_elimination": None
                }
            )
        elif req.role == "doctor":
            prompt = generate_doctor_night_prompt(state, req.player_id, 1, {
                "heal_potion_used": False,
                "kill_potion_used": False
            })
            
            return NightContextResponse(
                role=req.role,
                night_number=1,
                available_actions=["protect", "kill_potion"],
                targets=demo_players,
                private_info={
                    "heal_potion_used": False,
                    "kill_potion_used": False,
                    "prompt": prompt.model_dump()
                },
                public_info={
                    "alive_players": demo_players,
                    "last_elimination": None
                }
            )
        else:  # villager
            prompt = generate_villager_night_prompt(state, req.player_id, 1)
            
            return NightContextResponse(
                role=req.role,
                night_number=1,
                available_actions=["sleep"],
                targets=[],
                private_info={
                    "prompt": prompt.model_dump()
                },
                public_info={
                    "alive_players": demo_players,
                    "last_elimination": None
                }
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/night/tools/{role}")
def get_night_tools(role: str) -> Dict[str, Any]:
    """Get available tools for a specific role during night phase."""
    try:
        if role not in ["werewolf", "detective", "doctor", "villager"]:
            raise HTTPException(status_code=400, detail=f"Invalid role: {role}")
        
        tools = get_night_tools_for_role(role)
        return {
            "role": role,
            "tools": tools,
            "message": f"Available tools for {role} during night phase"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/night/action", response_model=NightActionResponse)
def submit_night_action(req: NightActionRequest) -> NightActionResponse:
    """Submit a night action from a white agent."""
    try:
        # Determine role from player_id (in real implementation, load from game state)
        # For demo purposes, use hardcoded mapping
        demo_roles = {"A1": "villager", "A2": "werewolf", "A3": "detective", 
                     "A4": "villager", "A5": "werewolf", "A6": "doctor"}
        role = demo_roles.get(req.player_id, "villager")
        
        # Validate the action
        validation = validate_night_action(req.model_dump(), role)
        if not validation["valid"]:
            return NightActionResponse(
                success=False,
                message=validation["error"]
            )
        
        # Store the action (in real implementation, this would be stored in game state)
        action_data = req.model_dump()
        action_data["player_id"] = req.player_id
        action_data["role"] = role
        action_data["timestamp"] = datetime.now().isoformat()
        
        # Generate action ID
        action_id = f"{req.action_type}_{req.player_id}_{datetime.now().timestamp()}"
        
        # Format response message
        formatted_action = format_night_action_response(action_data, role)
        
        return NightActionResponse(
            success=True,
            message=f"Night action submitted: {formatted_action}",
            action_id=action_id
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/night/resolve", response_model=NightPhaseResolveResponse)
def resolve_night_phase(req: NightPhaseResolveRequest) -> NightPhaseResolveResponse:
    """Resolve all night actions and determine outcomes."""
    try:
        # In real implementation, this would:
        # 1. Collect all submitted actions
        # 2. Process them in correct order (seer -> wolves -> witch)
        # 3. Determine outcomes
        # 4. Update game state
        
        # For now, return demo resolution
        outcomes = {
            "wolf_kill": {"target": "A4", "success": True},
            "seer_inspection": {"target": "A5", "is_werewolf": True},
            "doctor_protection": {"target": "A3", "saved": True}
        }
        
        return NightPhaseResolveResponse(
            success=True,
            message="Night phase resolved successfully",
            outcomes=outcomes,
            public_announcement="A4 was killed overnight in a werewolf attack."
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ELO Rating System Endpoints
@app.post("/elo/process_game")
def process_game_result(
    winner_id: str,
    loser_id: str, 
    winner_role: str,
    loser_role: str,
    game_id: str = None
) -> Dict[str, Any]:
    """Process a game result and update ELO ratings."""
    try:
        result = elo_calculator.process_game_result(
            winner_id=winner_id,
            loser_id=loser_id,
            winner_role=winner_role,
            loser_role=loser_role,
            game_id=game_id
        )
        return {
            "success": True,
            "message": "Game result processed successfully",
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/elo/rankings")
def get_elo_rankings(sort_by: str = "overall") -> Dict[str, Any]:
    """Get ELO rankings for all players."""
    try:
        rankings = elo_calculator.get_rankings(sort_by=sort_by)
        return {
            "success": True,
            "rankings": rankings,
            "sort_by": sort_by,
            "total_players": len(rankings)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/elo/player/{player_id}")
def get_player_elo(player_id: str) -> Dict[str, Any]:
    """Get ELO rating and stats for a specific player."""
    try:
        stats = elo_calculator.get_player_stats(player_id)
        if stats is None:
            raise HTTPException(status_code=404, detail=f"Player {player_id} not found")
        
        return {
            "success": True,
            "player_stats": stats
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/elo/head-to-head/{player1}/{player2}")
def get_head_to_head(player1: str, player2: str) -> Dict[str, Any]:
    """Get head-to-head record between two players."""
    try:
        record = elo_calculator.get_head_to_head(player1, player2)
        if record is None:
            return {
                "success": True,
                "head_to_head": {
                    "player1": player1,
                    "player2": player2,
                    "wins": 0,
                    "losses": 0,
                    "ties": 0,
                    "total_games": 0,
                    "win_rate": 0.0
                }
            }
        
        return {
            "success": True,
            "head_to_head": {
                "player1": record.player1,
                "player2": record.player2,
                "wins": record.wins,
                "losses": record.losses,
                "ties": record.ties,
                "total_games": record.total_games,
                "win_rate": record.win_rate
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/elo/matrix")
def get_head_to_head_matrix() -> Dict[str, Any]:
    """Get complete head-to-head matrix for all players."""
    try:
        matrix = elo_calculator.get_head_to_head_matrix()
        return {
            "success": True,
            "head_to_head_matrix": matrix
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
