
import os
import sys
sys.path.append(os.getcwd())
from src.werewolf.evaluation import EvaluationManager

print("Current CWD:", os.getcwd())
em = EvaluationManager("test_game_id")
print("EvaluationManager instantiated.")
print("Checking for CSVs...")
csvs = ["model_overall_stats.csv", "model_role_stats.csv", "matchup_stats.csv"]
for csv in csvs:
    path = os.path.join("Game_History", "Evals", csv)
    if os.path.exists(path):
        print(f"Found {csv}")
    else:
        print(f"Missing {csv}")
