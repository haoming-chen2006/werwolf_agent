import os
import json
from datetime import datetime
from typing import Dict, Any, List

class GameLogger:
    def __init__(self, game_id: str, players: List[Any]):
        self.game_id = game_id
        self.players = players
        self.base_dir = os.path.join("Game_History", "Record", f"Record_{game_id}")
        self.evals_dir = os.path.join("Game_History", "Evals", f"Evals_{game_id}")
        self._initialize_structure()

    def _initialize_structure(self):
        """Creates the directory structure and initial files."""
        os.makedirs(self.base_dir, exist_ok=True)
        os.makedirs(self.evals_dir, exist_ok=True)

        # Initialize Public History
        self.public_history_path = os.path.join(self.base_dir, "Public_History.json")
        if not os.path.exists(self.public_history_path):
            with open(self.public_history_path, "w") as f:
                json.dump([], f)

        # Initialize Green Record
        self.green_record_path = os.path.join(self.base_dir, "Green_Record.txt")
        if not os.path.exists(self.green_record_path):
            with open(self.green_record_path, "w") as f:
                f.write(f"Green Agent Record - Game {self.game_id}\n==========================================\n")

        # Initialize Player Directories
        for player in self.players:
            player_dir = os.path.join(self.base_dir, f"Player_{player.id}")
            os.makedirs(player_dir, exist_ok=True)

            # Info.json
            # Use alias as name if name is not available (PlayerProfile vs PlayerCard)
            p_name = getattr(player, "name", player.alias)
            p_model = getattr(player, "model", "Unknown")
            
            info = {
                "Player_name": p_name,
                "Player_role": player.role_private,
                "Player_model": p_model,
                "Player_id": player.id,
                "Alignment": player.alignment
            }
            with open(os.path.join(player_dir, "Info.json"), "w") as f:
                json.dump(info, f, indent=2)

            # Initialize empty logs
            self._init_log_file(player_dir, "Private_Thoughts.json")
            self._init_log_file(player_dir, "Public_Speech.json")
            
            # Initialize History.txt
            history_path = os.path.join(player_dir, "History.txt")
            if not os.path.exists(history_path):
                with open(history_path, "w") as f:
                    f.write(f"Game History for {p_name} ({player.role_private})\n==========================================\n")

    def _init_log_file(self, directory: str, filename: str):
        path = os.path.join(directory, filename)
        if not os.path.exists(path):
            with open(path, "w") as f:
                json.dump([], f)

    def log_public_event(self, event: Dict[str, Any]):
        """Logs a general event to public history (e.g. Day Start, Deaths)."""
        self._append_to_json(self.public_history_path, event)
        
        # Append to all players' History.txt
        message = self._format_public_event(event)
        if message:
            for player in self.players:
                history_path = os.path.join(self.base_dir, f"Player_{player.id}", "History.txt")
                if os.path.exists(history_path):
                    with open(history_path, "a") as f:
                        f.write(f"\n[Public Event] {message}\n")
            
            # Also log to Green Record
            try:
                with open(self.green_record_path, "a") as f:
                    f.write(f"[{datetime.now().isoformat()}] [Public Event] {message}\n")
            except Exception:
                pass

    def _format_public_event(self, event: Dict[str, Any]) -> str:
        phase = event.get("phase", "")
        if phase == "day_start":
            return f"Day {event.get('day')} started."
        elif phase == "night_start":
            return f"Night {event.get('night')} started."
        elif phase == "night_end":
            killed = event.get("killed")
            if killed:
                return f"Night {event.get('night')} ended. Player {killed} was killed."
            return f"Night {event.get('night')} ended. No one was killed."
        elif phase == "day_end":
            eliminated = event.get("eliminated")
            if eliminated:
                return f"Day {event.get('day')} ended. Player {eliminated['player_id']} ({eliminated['role_revealed']}) was eliminated by vote."
            return f"Day {event.get('day')} ended. No one was eliminated."
        elif event.get("event_type") == "speech":
             # Speech is handled in log_player_turn for the speaker, but others need to hear it?
             # Wait, log_player_turn logs to the speaker's history. 
             # Other players need to know about this speech too!
             return f"Player {event.get('player_id')} said: {event.get('content')}"
        return ""

    def log_green_event(self, message: str):
        """Logs an action taken by the Green Agent (System)."""
        timestamp = datetime.now().isoformat()
        entry = f"[{timestamp}] {message}\n"
        try:
            with open(self.green_record_path, "a") as f:
                f.write(entry)
        except Exception as e:
            print(f"Error appending to Green Record: {e}")

    def log_private_event(self, player_id: str, message: str):
        """Logs a private event to the player's History.txt."""
        player_dir = os.path.join(self.base_dir, f"Player_{player_id}")
        history_path = os.path.join(player_dir, "History.txt")
        if os.path.exists(history_path):
            with open(history_path, "a") as f:
                f.write(f"\n[Private Event] {message}\n")

    def log_player_turn(self, player_id: str, phase: str, turn_number: int, thought: str, speech: str):
        """Logs a player's turn: thought to private, speech to public & player public."""
        player_dir = os.path.join(self.base_dir, f"Player_{player_id}")
        
        # Log Private Thought
        thought_entry = {
            "phase": phase,
            "turn": turn_number,
            "thought": thought,
            "timestamp": datetime.now().isoformat()
        }
        self._append_to_json(os.path.join(player_dir, "Private_Thoughts.json"), thought_entry)

        # Log Public Speech (Player's file)
        speech_entry = {
            "phase": phase,
            "turn": turn_number,
            "speech": speech,
            "timestamp": datetime.now().isoformat()
        }
        self._append_to_json(os.path.join(player_dir, "Public_Speech.json"), speech_entry)

        # Log to Speaker's History.txt
        history_path = os.path.join(player_dir, "History.txt")
        with open(history_path, "a") as f:
            f.write(f"\n[{phase.capitalize()} {turn_number}]\n")
            f.write(f"My Thought: {thought}\n")
            f.write(f"My Speech: {speech}\n")

        # Log Public Speech (Global History)
        global_entry = {
            "event_type": "speech",
            "player_id": player_id,
            "phase": phase,
            "turn": turn_number,
            "content": speech,
            "timestamp": datetime.now().isoformat()
        }
        self._append_to_json(self.public_history_path, global_entry)
        
        # Broadcast speech to other players
        for p in self.players:
            if p.id != player_id:
                p_history = os.path.join(self.base_dir, f"Player_{p.id}", "History.txt")
                if os.path.exists(p_history):
                    with open(p_history, "a") as f:
                        f.write(f"\n[{phase.capitalize()} {turn_number}] Player {player_id} said: {speech}\n")

        # Log to Green Record
        try:
            with open(self.green_record_path, "a") as f:
                f.write(f"[{datetime.now().isoformat()}] Player {player_id} ({phase} {turn_number}): {speech} (Thought: {thought})\n")
        except Exception:
            pass

    def get_player_history_text(self, player_id: str) -> str:
        """Reads the player's natural language history."""
        path = os.path.join(self.base_dir, f"Player_{player_id}", "History.txt")
        if os.path.exists(path):
            with open(path, "r") as f:
                return f.read()
        return ""

    def get_public_history(self) -> List[Dict[str, Any]]:
        """Reads the current public history."""
        return self._read_json(self.public_history_path)

    def get_player_private_thoughts(self, player_id: str) -> List[Dict[str, Any]]:
        """Reads a player's private thoughts."""
        path = os.path.join(self.base_dir, f"Player_{player_id}", "Private_Thoughts.json")
        return self._read_json(path)

    def get_public_speech_history(self) -> List[Dict[str, Any]]:
        """Reads the global public speech history."""
        # Filter only speech events from public history if needed, or return all
        # For now, returning all public history as it contains speeches + events
        return self._read_json(self.public_history_path)

    def _append_to_json(self, filepath: str, entry: Any):
        """Helper to append to a JSON list file."""
        try:
            data = []
            if os.path.exists(filepath):
                with open(filepath, "r") as f:
                    try:
                        data = json.load(f)
                    except json.JSONDecodeError:
                        data = []
            
            data.append(entry)
            
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error appending to {filepath}: {e}")

    def _read_json(self, filepath: str) -> List[Any]:
        try:
            if os.path.exists(filepath):
                with open(filepath, "r") as f:
                    return json.load(f)
            return []
        except Exception:
            return []
