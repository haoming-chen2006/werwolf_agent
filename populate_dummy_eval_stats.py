import pandas as pd
import os
import random
from datetime import datetime

# Configuration
EVALS_DIR = os.path.join("Game_History", "Evals")
OVERALL_STATS_PATH = os.path.join(EVALS_DIR, "model_overall_stats.csv")
ROLE_STATS_PATH = os.path.join(EVALS_DIR, "model_role_stats.csv")
MATCHUP_STATS_PATH = os.path.join(EVALS_DIR, "matchup_stats.csv")
ADVANCED_STATS_PATH = os.path.join(EVALS_DIR, "model_advanced_stats.csv")

# Dummy Models to add
DUMMY_MODELS = [
    {"provider": "anthropic", "model": "claude-3-opus"},
    {"provider": "anthropic", "model": "claude-3-sonnet"},
    {"provider": "google", "model": "gemini-1.5-pro"},
    {"provider": "meta", "model": "llama-3-70b"},
    {"provider": "mistral", "model": "mistral-large"},
    {"provider": "openai", "model": "gpt-3.5-turbo"},
    {"provider": "openai", "model": "gpt-4"},
    {"provider": "openai", "model": "gpt-4-turbo"},
    {"provider": "openai", "model": "gpt-4o"},
]

# Roles to simulate
ROLES = ["werewolf", "villager", "detective", "doctor"]

# Baseline opponent for matchups (assuming this model exists or we just use it as a placeholder)
BASELINE_OPPONENT = "openai:gpt-4o"

def init_csvs():
    os.makedirs(EVALS_DIR, exist_ok=True)
    
    if not os.path.exists(OVERALL_STATS_PATH):
        pd.DataFrame(columns=[
            "model_id", "model_provider", "model_name", "games_played", 
            "wins", "losses", "wins_as_villager_team", "wins_as_wolf_team", 
            "elo_overall", "last_updated_game_id", "last_updated_timestamp"
        ]).to_csv(OVERALL_STATS_PATH, index=False)
        
    if not os.path.exists(ROLE_STATS_PATH):
        pd.DataFrame(columns=[
            "model_id", "role", "role_id", "games_played_role", 
            "wins_role", "losses_role", "elo_role", 
            "last_updated_game_id", "last_updated_timestamp"
        ]).to_csv(ROLE_STATS_PATH, index=False)
        
    if not os.path.exists(MATCHUP_STATS_PATH):
        pd.DataFrame(columns=[
            "villager_model_id", "wolf_model_id", "games_played", 
            "villager_wins", "wolf_wins", "expected_villager_win_rate", 
            "observed_villager_win_rate", "last_updated_game_id", "last_updated_timestamp"
        ]).to_csv(MATCHUP_STATS_PATH, index=False)

    if not os.path.exists(ADVANCED_STATS_PATH):
        pd.DataFrame(columns=[
            "model_id", "games_played_total", "games_played_town",
            "total_votes_cast_as_town", "votes_on_wolves_as_town",
            "voting_precision", "first_eliminated_count",
            "last_updated_game_id", "last_updated_timestamp"
        ]).to_csv(ADVANCED_STATS_PATH, index=False)

def populate_stats():
    init_csvs()
    
    df_overall = pd.read_csv(OVERALL_STATS_PATH)
    df_role = pd.read_csv(ROLE_STATS_PATH)
    df_matchup = pd.read_csv(MATCHUP_STATS_PATH)
    df_advanced = pd.read_csv(ADVANCED_STATS_PATH)
    
    timestamp = datetime.now().isoformat()
    game_id = "dummy_population_script"
    
    for model_info in DUMMY_MODELS:
        provider = model_info["provider"]
        name = model_info["model"]
        model_id = f"{provider}:{name}"
        
        print(f"Processing {model_id}...")
        
        # Check if model already exists in overall stats
        exists_overall = model_id in df_overall["model_id"].values
        exists_advanced = model_id in df_advanced["model_id"].values
        
        if exists_overall and exists_advanced:
            print(f"  Skipping {model_id} (already exists in both)")
            continue

        # Initialize overall stats for this model
        # We will accumulate stats as we iterate through roles
        total_games = 0
        total_wins = 0
        total_losses = 0
        wins_v = 0
        wins_w = 0
        current_elo = 1500.0 # Start at 1500
        
        # Advanced stats accumulators
        games_town = 0
        votes_cast = 0
        votes_on_wolves = 0
        first_elim_count = 0
        
        for role in ROLES:
            # Determine team
            if role == "werewolf":
                team = "wolves"
            else:
                team = "villagers"
            
            # Simulate 1 game
            # Random win/loss for variety, or fixed? Let's do random weighted.
            is_win = random.choice([True, False])
            
            # Update local counters
            total_games += 1
            if is_win:
                total_wins += 1
                if team == "villagers":
                    wins_v += 1
                else:
                    wins_w += 1
            else:
                total_losses += 1
            
            # Update Advanced Stats (Simulation)
            if team == "villagers":
                games_town += 1
                # Simulate voting precision (0.3 to 0.8)
                votes_in_game = random.randint(2, 5)
                votes_cast += votes_in_game
                votes_on_wolves += int(votes_in_game * random.uniform(0.2, 0.7))
            
            # Simulate first eliminated (10% chance)
            if random.random() < 0.1:
                first_elim_count += 1
            
            # Update Role Stats
            role_id = f"{model_id}|{role}"
            
            # Simple ELO change for simulation
            elo_change = 16 if is_win else -16
            role_elo = 1500.0 + elo_change
            current_elo += elo_change # Accumulate overall ELO change
            
            # Only add role stats if not already present (to avoid duplicates)
            if role_id not in df_role["role_id"].values:
                new_role_row = {
                    "model_id": model_id,
                    "role": role,
                    "role_id": role_id,
                    "games_played_role": 1,
                    "wins_role": 1 if is_win else 0,
                    "losses_role": 0 if is_win else 1,
                    "elo_role": role_elo,
                    "last_updated_game_id": game_id,
                    "last_updated_timestamp": timestamp
                }
                df_role = pd.concat([df_role, pd.DataFrame([new_role_row])], ignore_index=True)
            
            # Update Matchup Stats
            # If model is Villager, opponent is BASELINE_OPPONENT (Wolf)
            # If model is Wolf, opponent is BASELINE_OPPONENT (Villager)
            
            if team == "villagers":
                v_id = model_id
                w_id = BASELINE_OPPONENT
                v_wins = 1 if is_win else 0
                w_wins = 0 if is_win else 1
            else:
                v_id = BASELINE_OPPONENT
                w_id = model_id
                v_wins = 0 if is_win else 1 # If wolf (model) won, villager lost
                w_wins = 1 if is_win else 0
            
            # Check if matchup exists (it might if we run this multiple times or if baseline is involved)
            matchup_mask = (df_matchup["villager_model_id"] == v_id) & (df_matchup["wolf_model_id"] == w_id)
            
            if matchup_mask.any():
                # Update existing (though for dummy models this shouldn't happen often if they are new)
                idx = df_matchup.index[matchup_mask][0]
                df_matchup.at[idx, "games_played"] += 1
                df_matchup.at[idx, "villager_wins"] += v_wins
                df_matchup.at[idx, "wolf_wins"] += w_wins
                df_matchup.at[idx, "observed_villager_win_rate"] = df_matchup.at[idx, "villager_wins"] / df_matchup.at[idx, "games_played"]
            else:
                new_matchup_row = {
                    "villager_model_id": v_id,
                    "wolf_model_id": w_id,
                    "games_played": 1,
                    "villager_wins": v_wins,
                    "wolf_wins": w_wins,
                    "expected_villager_win_rate": 0.5, # Dummy expectation
                    "observed_villager_win_rate": float(v_wins),
                    "last_updated_game_id": game_id,
                    "last_updated_timestamp": timestamp
                }
                df_matchup = pd.concat([df_matchup, pd.DataFrame([new_matchup_row])], ignore_index=True)

        # Add to Overall Stats
        if not exists_overall:
            new_overall_row = {
                "model_id": model_id,
                "model_provider": provider,
                "model_name": name,
                "games_played": total_games,
                "wins": total_wins,
                "losses": total_losses,
                "wins_as_villager_team": wins_v,
                "wins_as_wolf_team": wins_w,
                "elo_overall": current_elo,
                "last_updated_game_id": game_id,
                "last_updated_timestamp": timestamp
            }
            df_overall = pd.concat([df_overall, pd.DataFrame([new_overall_row])], ignore_index=True)

        # Add to Advanced Stats
        if not exists_advanced:
            precision = votes_on_wolves / votes_cast if votes_cast > 0 else 0.0
            new_advanced_row = {
                "model_id": model_id,
                "games_played_total": total_games,
                "games_played_town": games_town,
                "total_votes_cast_as_town": votes_cast,
                "votes_on_wolves_as_town": votes_on_wolves,
                "voting_precision": precision,
                "first_eliminated_count": first_elim_count,
                "last_updated_game_id": game_id,
                "last_updated_timestamp": timestamp
            }
            df_advanced = pd.concat([df_advanced, pd.DataFrame([new_advanced_row])], ignore_index=True)

    # Generate matchups between all dummy models
    print("Generating head-to-head matchups between dummy models...")
    for m1 in DUMMY_MODELS:
        id1 = f"{m1['provider']}:{m1['model']}"
        for m2 in DUMMY_MODELS:
            id2 = f"{m2['provider']}:{m2['model']}"
            
            if id1 == id2:
                continue
                
            # Simulate 5 games where id1 is Villager and id2 is Wolf
            games = 5
            v_wins = random.randint(0, games)
            w_wins = games - v_wins
            
            matchup_mask = (df_matchup["villager_model_id"] == id1) & (df_matchup["wolf_model_id"] == id2)
            
            if matchup_mask.any():
                idx = df_matchup.index[matchup_mask][0]
                df_matchup.at[idx, "games_played"] += games
                df_matchup.at[idx, "villager_wins"] += v_wins
                df_matchup.at[idx, "wolf_wins"] += w_wins
                df_matchup.at[idx, "observed_villager_win_rate"] = df_matchup.at[idx, "villager_wins"] / df_matchup.at[idx, "games_played"]
            else:
                new_matchup_row = {
                    "villager_model_id": id1,
                    "wolf_model_id": id2,
                    "games_played": games,
                    "villager_wins": v_wins,
                    "wolf_wins": w_wins,
                    "expected_villager_win_rate": 0.5,
                    "observed_villager_win_rate": float(v_wins) / games,
                    "last_updated_game_id": game_id,
                    "last_updated_timestamp": timestamp
                }
                df_matchup = pd.concat([df_matchup, pd.DataFrame([new_matchup_row])], ignore_index=True)

    # Save all
    df_overall.to_csv(OVERALL_STATS_PATH, index=False)
    df_role.to_csv(ROLE_STATS_PATH, index=False)
    df_matchup.to_csv(MATCHUP_STATS_PATH, index=False)
    df_advanced.to_csv(ADVANCED_STATS_PATH, index=False)
    
    print("Done populating dummy stats.")

if __name__ == "__main__":
    populate_stats()
