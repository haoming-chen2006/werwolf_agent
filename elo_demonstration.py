import os
import sys
import shutil
import pandas as pd
from datetime import datetime, timezone
from typing import List, Dict, Any

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from werewolf.models import (
    GameRecord, PlayerProfile, FinalResult, DayPhaseRecord, NightPhaseRecord,
    DayPublicState, DayVotingRecord, VoteResolution, VoteResponseRecord,
    VoteResponse, DayDiscussionResponse, DiscussionTurn, DayDiscussionPrompt,
    DayDiscussionConstraints, VotePromptRecord, DayVotePrompt, VoteConstraints,
    NightResolution, WolfChatEntry, NightPromptRecord, NightResponseRecord,
    NightRolePrompt, NightConstraints
)
from werewolf.evaluation import EvaluationManager

def create_players() -> List[PlayerProfile]:
    # 4 distinct models for 4 roles
    # Werewolf: gpt-4o
    # Villager: gemini-1.5-pro
    # Detective: claude-3-opus
    # Doctor: llama-3-70b
    
    players = []
    
    # 2 Werewolves (GPT-4o)
    players.append(PlayerProfile(id="p1", alias="Wolf 1", role_private="werewolf", alignment="wolves", model="gpt-4o", provider="openai"))
    players.append(PlayerProfile(id="p2", alias="Wolf 2", role_private="werewolf", alignment="wolves", model="gpt-4o", provider="openai"))
    
    # 1 Detective (Claude 3 Opus)
    players.append(PlayerProfile(id="p3", alias="Detective", role_private="detective", alignment="town", model="claude-3-opus", provider="anthropic"))
    
    # 1 Doctor (Llama 3 70b)
    players.append(PlayerProfile(id="p4", alias="Doctor", role_private="doctor", alignment="town", model="llama-3-70b", provider="meta"))
    
    # 3 Villagers (Gemini 1.5 Pro)
    players.append(PlayerProfile(id="p5", alias="Villager 1", role_private="villager", alignment="town", model="gemini-1.5-pro", provider="google"))
    players.append(PlayerProfile(id="p6", alias="Villager 2", role_private="villager", alignment="town", model="gemini-1.5-pro", provider="google"))
    players.append(PlayerProfile(id="p7", alias="Villager 3", role_private="villager", alignment="town", model="gemini-1.5-pro", provider="google"))
    
    return players

def create_wolf_win_game(game_id: str) -> GameRecord:
    players = create_players()
    
    # Construct a game where Wolves win
    # Night 0: Wolves kill p5 (Villager)
    # Day 1: Town votes out p3 (Detective) - Mis-elimination
    # Night 1: Wolves kill p4 (Doctor)
    # Day 2: Town votes out p6 (Villager) - Mis-elimination
    # End: 2 Wolves, 1 Villager (p7) alive. Wolves win.
    
    # Night 0
    night0 = NightPhaseRecord(
        night_number=0,
        public_state={"alive_players": [p.id for p in players]},
        wolves_private_chat=[],
        prompts=[], responses=[],
        resolution=NightResolution(
            wolf_team_decision={"target": "p5"},
            night_outcome={"eliminated": "p5"},
            public_update="Player p5 was eliminated."
        )
    )
    players[4].alive = False # p5 dead
    
    # Day 1
    day1 = DayPhaseRecord(
        day_number=1,
        public_state=DayPublicState(alive_players=[p.id for p in players if p.alive], public_history=[]),
        discussion={"turns": []},
        voting=DayVotingRecord(
            prompts=[], responses=[],
            resolution=VoteResolution(
                tally={"p3": 4, "p1": 2},
                eliminated={"id": "p3", "role": "detective", "alignment": "town"}
            )
        )
    )
    players[2].alive = False # p3 dead
    
    # Night 1
    night1 = NightPhaseRecord(
        night_number=1,
        public_state={"alive_players": [p.id for p in players if p.alive]},
        wolves_private_chat=[],
        prompts=[], responses=[],
        resolution=NightResolution(
            wolf_team_decision={"target": "p4"},
            night_outcome={"eliminated": "p4"},
            public_update="Player p4 was eliminated."
        )
    )
    players[3].alive = False # p4 dead
    
    # Day 2
    day2 = DayPhaseRecord(
        day_number=2,
        public_state=DayPublicState(alive_players=[p.id for p in players if p.alive], public_history=[]),
        discussion={"turns": []},
        voting=DayVotingRecord(
            prompts=[], responses=[],
            resolution=VoteResolution(
                tally={"p6": 3, "p1": 1},
                eliminated={"id": "p6", "role": "villager", "alignment": "town"}
            )
        )
    )
    players[5].alive = False # p6 dead
    
    final_result = FinalResult(
        winning_side="wolves",
        reason="Wolves outnumber villagers",
        survivors=[{"id": p.id} for p in players if p.alive],
        elimination_order=[]
    )
    
    record = GameRecord(
        schema_version="1.0",
        game_id=game_id,
        created_at_utc=datetime.now(timezone.utc),
        seed=999,
        config={},
        players=players,
        role_assignment={p.id: p.role_private for p in players},
        phase_sequence=["night_0", "day_1", "night_1", "day_2"],
        phases=[night0, day1, night1, day2],
        final_result=final_result
    )
    
    return record

def prepopulate_csvs(manager: EvaluationManager):
    """Ensure CSVs have initial entries for our models so 'Before' graphs work."""
    print("Pre-populating CSVs with initial 1500 ELO...")
    
    # 1. Overall Stats
    df_overall = pd.read_csv(manager.overall_stats_path)
    models = [
        ("openai", "gpt-4o"),
        ("google", "gemini-1.5-pro"),
        ("anthropic", "claude-3-opus"),
        ("meta", "llama-3-70b")
    ]
    
    for provider, model in models:
        model_id = f"{provider}:{model}"
        if df_overall.empty or model_id not in df_overall["model_id"].values:
            new_row = {
                "model_id": model_id,
                "model_provider": provider,
                "model_name": model,
                "games_played": 0,
                "wins": 0,
                "losses": 0,
                "wins_as_villager_team": 0,
                "wins_as_wolf_team": 0,
                "elo_overall": 1500.0,
                "last_updated_game_id": "init",
                "last_updated_timestamp": datetime.now().isoformat()
            }
            df_overall = pd.concat([df_overall, pd.DataFrame([new_row])], ignore_index=True)
    
    df_overall.to_csv(manager.overall_stats_path, index=False)
    
    # 2. Role Stats
    df_role = pd.read_csv(manager.role_stats_path)
    roles = ["werewolf", "villager", "detective", "doctor"]
    
    for provider, model in models:
        model_id = f"{provider}:{model}"
        for role in roles:
            role_id = f"{model_id}|{role}"
            if df_role.empty or role_id not in df_role["role_id"].values:
                new_row = {
                    "model_id": model_id,
                    "role": role,
                    "role_id": role_id,
                    "games_played_role": 0,
                    "wins_role": 0,
                    "losses_role": 0,
                    "elo_role": 1500.0,
                    "last_updated_game_id": "init",
                    "last_updated_timestamp": datetime.now().isoformat()
                }
                df_role = pd.concat([df_role, pd.DataFrame([new_row])], ignore_index=True)
                
    df_role.to_csv(manager.role_stats_path, index=False)

def main():
    game_id = f"elo_demo_{int(datetime.now().timestamp())}"
    print(f"Starting ELO Demonstration (Game ID: {game_id})")
    
    manager = EvaluationManager(game_id)
    
    # 1. Pre-populate CSVs to ensure we have a baseline
    prepopulate_csvs(manager)
    
    # 2. Generate 'Before' Graphs
    print("\nGenerating 'Before' graphs...")
    manager._generate_graphs()
    
    # Rename generated graphs
    graph_files = [
        "head_to_head_heatmap.png", 
        "elo_overall_leaderboard.png", 
        "elo_role_chart.png"
    ]
    
    for graph in graph_files:
        src = os.path.join(manager.graphs_dir, graph)
        dst = os.path.join(manager.graphs_dir, graph.replace(".png", "_before.png"))
        if os.path.exists(src):
            shutil.move(src, dst)
            print(f"Saved: {dst}")
        else:
            print(f"Warning: {src} not found")

    # 3. Create and Run Game
    print("\nSimulating Game (Wolves Win)...")
    print("Roles:")
    print("- Wolves: gpt-4o")
    print("- Villagers: gemini-1.5-pro")
    print("- Detective: claude-3-opus")
    print("- Doctor: llama-3-70b")
    
    record = create_wolf_win_game(game_id)
    
    print("\nRunning Evaluation (Updating ELO)...")
    manager.run_evaluation(record)
    
    # 4. Rename 'After' Graphs
    print("\nSaving 'After' graphs...")
    for graph in graph_files:
        src = os.path.join(manager.graphs_dir, graph)
        dst = os.path.join(manager.graphs_dir, graph.replace(".png", "_after.png"))
        if os.path.exists(src):
            shutil.copy(src, dst)
            print(f"Saved: {dst}")
            
    print("\nDemonstration Complete!")
    print(f"Check the folder: {manager.graphs_dir}")
    print("You should see 6 graphs (3 before, 3 after).")

if __name__ == "__main__":
    main()
