
import json
import random
import os
from datetime import datetime

# Constants
EVALS_DIR = os.path.join("Game_History", "Evals")
os.makedirs(EVALS_DIR, exist_ok=True)

MODELS = [
    ("openai", "gpt-4o"),
    ("openai", "gpt-4-turbo"),
    ("openai", "gpt-3.5-turbo"),
    ("anthropic", "claude-3-opus"),
    ("anthropic", "claude-3-sonnet"),
    ("google", "gemini-1.5-pro"),
    ("meta", "llama-3-70b"),
]

def generate_dummy_eval_jsons(num_games=25):
    print(f"Generating {num_games} dummy eval JSONs in per-game directories...")
    
    for i in range(num_games):
        game_id = f"dummy_game_{i}_{int(datetime.now().timestamp())}"
        
        # Create per-game directory
        game_eval_dir = os.path.join(EVALS_DIR, f"Evals_{game_id}")
        os.makedirs(game_eval_dir, exist_ok=True)
        
        filename = "eval_trace.json"
        filepath = os.path.join(game_eval_dir, filename)
        
        # Pick random players for this game
        game_players = []
        # 7 players per game (2 wolves, 1 detective, 1 doctor, 3 villagers)
        selected_models = random.choices(MODELS, k=7)
        
        for j, (provider, model) in enumerate(selected_models):
            model_id = f"{provider}:{model}"
            
            # Generate scores
            sabotage_score = random.betavariate(1, 5) # Skewed towards 0
            decision_quality_score = random.betavariate(5, 2) # Skewed towards 1 (0.7-0.9 avg)
            
            # Assign roles based on index for simplicity
            if j < 2:
                role = "werewolf"
                team = "wolves"
            elif j == 2:
                role = "detective"
                team = "villagers"
            elif j == 3:
                role = "doctor"
                team = "villagers"
            else:
                role = "villager"
                team = "villagers"
            
            is_wolf = (team == "wolves")
            
            manipulation_score = 0.0
            resistance_score = 0.0
            
            if is_wolf:
                manipulation_score = random.betavariate(2, 2) # Centered around 0.5
            else:
                resistance_score = random.betavariate(2, 2) # Centered around 0.5
            
            player_entry = {
                "player_id": f"p{j+1}",
                "model_id": model_id,
                "role": role,
                "team": team,
                "on_winning_team": random.choice([True, False]),
                "auto_sabotage_score": round(sabotage_score, 2),
                "auto_sabotage_explanation": "Dummy explanation generated for testing.",
                "manipulation_score": round(manipulation_score, 2),
                "manipulation_explanation": "Dummy manipulation explanation.",
                "resistance_score": round(resistance_score, 2),
                "resistance_explanation": "Dummy resistance explanation.",
                "decision_quality_score": round(decision_quality_score, 2),
                "decision_quality_explanation": "Dummy decision quality explanation."
            }
            game_players.append(player_entry)
            
        eval_data = {
            "game_id": game_id,
            "winning_side": random.choice(["villagers", "wolves"]),
            "players": game_players
        }
        
        with open(filepath, "w") as f:
            json.dump(eval_data, f, indent=2)
            
    print("Done generating JSONs.")

if __name__ == "__main__":
    generate_dummy_eval_jsons()
