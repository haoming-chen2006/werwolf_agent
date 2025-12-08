import sys
import os

# Add the current directory to sys.path to ensure imports work
sys.path.append(os.getcwd())

from src.werewolf.evaluation import EvaluationManager

def main():
    # Default game ID from the user request
    # Path: /Users/haoming/mafia/werewolf_bench/Game_History/Record/Record_game_324300_20251205_161516
    # Game ID is likely "game_324300_20251205_161516"
    
    game_id = "game_324300_20251205_161516"
    
    # Allow overriding via command line argument
    if len(sys.argv) > 1:
        input_arg = sys.argv[1]
        # If user passes full path, extract ID
        # Example: .../Record_game_123/ or .../Record_game_123
        if "Record_" in input_arg:
            # Split by Record_ and take the last part, remove trailing slashes
            game_id = input_arg.split("Record_")[-1].strip("/")
        else:
            game_id = input_arg
    
    print(f"Running manual evaluation for Game ID: {game_id}")
    
    try:
        manager = EvaluationManager(game_id)
        manager.run_evaluation()
        print("Manual evaluation finished successfully.")
    except Exception as e:
        print(f"Error running evaluation: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
