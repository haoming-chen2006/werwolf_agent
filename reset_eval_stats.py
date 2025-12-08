
import os
import pandas as pd

EVALS_DIR = os.path.join("Game_History", "Evals")

def reset_stats():
    if not os.path.exists(EVALS_DIR):
        os.makedirs(EVALS_DIR)
        
    # 1. Overall Stats
    overall_path = os.path.join(EVALS_DIR, "model_overall_stats.csv")
    if os.path.exists(overall_path):
        os.remove(overall_path)
        print(f"Deleted {overall_path}")
    
    overall_cols = [
        "model_id", "model_provider", "model_name", "games_played", 
        "wins", "losses", "wins_as_villager_team", "wins_as_wolf_team", 
        "elo_overall", "last_updated_game_id", "last_updated_timestamp"
    ]
    pd.DataFrame(columns=overall_cols).to_csv(overall_path, index=False)
    print("Created empty model_overall_stats.csv")

    # 2. Role Stats
    role_path = os.path.join(EVALS_DIR, "model_role_stats.csv")
    if os.path.exists(role_path):
        os.remove(role_path)
        print(f"Deleted {role_path}")

    role_cols = [
        "model_id", "role", "role_id", "games_played_role", 
        "wins_role", "losses_role", "elo_role", 
        "last_updated_game_id", "last_updated_timestamp"
    ]
    pd.DataFrame(columns=role_cols).to_csv(role_path, index=False)
    print("Created empty model_role_stats.csv")

    # 3. Matchup Stats
    matchup_path = os.path.join(EVALS_DIR, "matchup_stats.csv")
    if os.path.exists(matchup_path):
        os.remove(matchup_path)
        print(f"Deleted {matchup_path}")

    matchup_cols = [
        "villager_model_id", "wolf_model_id", "games_played", 
        "villager_wins", "wolf_wins", "expected_villager_win_rate", 
        "observed_villager_win_rate", "last_updated_game_id", "last_updated_timestamp"
    ]
    pd.DataFrame(columns=matchup_cols).to_csv(matchup_path, index=False)
    print("Created empty matchup_stats.csv")

if __name__ == "__main__":
    reset_stats()
