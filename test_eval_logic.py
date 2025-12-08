
import os
import sys
import json
import pandas as pd
from datetime import datetime
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.append(os.getcwd())

from src.werewolf.evaluation import EvaluationManager
from src.werewolf.models import GameRecord, PlayerProfile, FinalResult

# Mock GameRecord
def create_mock_game_record(game_id):
    players = [
        PlayerProfile(id="p1", alias="Alice", role_private="villager", alignment="town", alive=True, provider="openai", model="gpt-4o", url=""),
        PlayerProfile(id="p2", alias="Bob", role_private="werewolf", alignment="wolves", alive=True, provider="openai", model="gpt-4o", url=""),
    ]
    final_result = FinalResult(
        winning_side="town", 
        reason="Town won",
        survivors=[{"id": "p1", "role": "villager"}],
        elimination_order=[{"id": "p2", "role": "werewolf", "day": 1}]
    )
    record = GameRecord(
        schema_version="1.0",
        game_id=game_id,
        created_at_utc=datetime.now(),
        seed=12345,
        config={"test": True},
        players=players,
        role_assignment={"p1": "villager", "p2": "werewolf"},
        phases=[],
        final_result=final_result,
        phase_sequence=[]
    )
    return record

def test_evaluation():
    game_id = f"test_game_{int(datetime.now().timestamp())}"
    print(f"Testing evaluation for {game_id}")
    
    # Create dummy directories
    os.makedirs(f"Game_History/Record/Record_{game_id}", exist_ok=True)
    
    # Create dummy player history for sabotage check
    os.makedirs(f"Game_History/Record/Record_{game_id}/Player_p1", exist_ok=True)
    with open(f"Game_History/Record/Record_{game_id}/Player_p1/History.txt", "w") as f:
        f.write("I am a villager. I vote for Bob.")
    
    os.makedirs(f"Game_History/Record/Record_{game_id}/Player_p2", exist_ok=True)
    with open(f"Game_History/Record/Record_{game_id}/Player_p2/History.txt", "w") as f:
        f.write("I am a werewolf. I eat Alice.")

    # Mock litellm completion to avoid API calls
    with patch('src.werewolf.evaluation.completion') as mock_completion:
        mock_completion.return_value.choices = [
            MagicMock(message=MagicMock(content='{"score": 0.1, "explanation": "Good play"}'))
        ]
        
        em = EvaluationManager(game_id)
        record = create_mock_game_record(game_id)
        
        em.run_evaluation(record)
        
        # Check if files were created
        print("Checking output files...")
        if os.path.exists(em.overall_stats_path):
            print("overall_stats.csv exists")
            df = pd.read_csv(em.overall_stats_path)
            print(df.head())
        else:
            print("overall_stats.csv MISSING")
            
        if os.path.exists(em.eval_json_path):
            print(f"Evals_{game_id}.json exists")
        else:
            print(f"Evals_{game_id}.json MISSING")

if __name__ == "__main__":
    test_evaluation()
