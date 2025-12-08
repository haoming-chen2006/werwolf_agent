
import os
import sys
sys.path.append(os.getcwd())
from src.werewolf.evaluation import EvaluationManager

def generate_graphs_only():
    print("Generating graphs from existing CSVs...")
    # We can instantiate EvaluationManager with a dummy game_id, 
    # as we are only calling _generate_graphs which reads from the global CSVs.
    em = EvaluationManager("dummy_graph_gen")
    em._generate_graphs()
    print("Graphs generated in Game_History/Evals/")
    
    # Check if files exist
    expected_files = [
        "elo_overall_leaderboard.png",
        "elo_by_role.png",
        "head_to_head_heatmap.png",
        "auto_sabotage_by_model.png",
        "manipulation_by_model.png",
        "resistance_by_model.png",
        "decision_quality_by_model.png",
        "voting_precision_by_model.png",
        "first_eliminated_rate_by_model.png"
    ]
    
    # The EvaluationManager creates a subdirectory for the game_id, and a graphs folder inside it
    evals_dir = os.path.join("Game_History", "Evals", "Evals_dummy_graph_gen", "graphs")
    
    all_exist = True
    for f in expected_files:
        path = os.path.join(evals_dir, f)
        if os.path.exists(path):
            print(f"✅ {f} exists")
        else:
            print(f"❌ {f} MISSING")
            all_exist = False
            
    if all_exist:
        print("All graphs generated successfully!")
    else:
        print("Some graphs are missing.")

if __name__ == "__main__":
    generate_graphs_only()
