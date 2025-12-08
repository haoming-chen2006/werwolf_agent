import os
import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
from typing import List, Dict, Any, Tuple
from src.agent_config import AGENTS
from src.werewolf.elo_system import EloCalculator, EloRating
from litellm import completion

import glob

EVALS_DIR = os.path.join("Game_History", "Evals")
RECORDS_DIR = os.path.join("Game_History", "Record")

class EvaluationManager:
    def __init__(self, game_id: str):
        self.game_id = game_id
        self.game_dir = os.path.join(RECORDS_DIR, f"Record_{game_id}")
        
        # Per-game evaluation directory
        self.game_eval_dir = os.path.join(EVALS_DIR, f"Evals_{game_id}")
        self.graphs_dir = os.path.join(self.game_eval_dir, "graphs")
        
        self.eval_json_path = os.path.join(self.game_eval_dir, f"eval_trace.json")
        self.summary_path = os.path.join(self.game_eval_dir, f"summary.txt")
        
        # Ensure directories exist
        os.makedirs(self.game_eval_dir, exist_ok=True)
        os.makedirs(self.graphs_dir, exist_ok=True)
        
        # CSV Paths (Global/Public)
        self.overall_stats_path = os.path.join(EVALS_DIR, "model_overall_stats.csv")
        self.role_stats_path = os.path.join(EVALS_DIR, "model_role_stats.csv")
        self.matchup_stats_path = os.path.join(EVALS_DIR, "matchup_stats.csv")
        self.advanced_stats_path = os.path.join(EVALS_DIR, "model_advanced_stats.csv")
        
        self._init_csvs()

    def _init_csvs(self):
        if not os.path.exists(self.overall_stats_path):
            pd.DataFrame(columns=[
                "model_id", "model_provider", "model_name", "games_played", 
                "wins", "losses", "wins_as_villager_team", "wins_as_wolf_team", 
                "elo_overall", "last_updated_game_id", "last_updated_timestamp"
            ]).to_csv(self.overall_stats_path, index=False)
            
        if not os.path.exists(self.role_stats_path):
            pd.DataFrame(columns=[
                "model_id", "role", "role_id", "games_played_role", 
                "wins_role", "losses_role", "elo_role", 
                "last_updated_game_id", "last_updated_timestamp"
            ]).to_csv(self.role_stats_path, index=False)
            
        if not os.path.exists(self.matchup_stats_path):
            pd.DataFrame(columns=[
                "villager_model_id", "wolf_model_id", "games_played", 
                "villager_wins", "wolf_wins", "expected_villager_win_rate", 
                "observed_villager_win_rate", "last_updated_game_id", "last_updated_timestamp"
            ]).to_csv(self.matchup_stats_path, index=False)

        if not os.path.exists(self.advanced_stats_path):
            pd.DataFrame(columns=[
                "model_id", "games_played_total", "games_played_town",
                "total_votes_cast_as_town", "votes_on_wolves_as_town",
                "voting_precision", "first_eliminated_count",
                "last_updated_game_id", "last_updated_timestamp"
            ]).to_csv(self.advanced_stats_path, index=False)

    def run_evaluation(self, game_record=None):
        print(f"Starting evaluation for {self.game_id}...")
        
        # 1. Load Game Data
        print("1. Conducting evaluation (loading game data)...")
        game_data = self._load_game_data(game_record)
        if not game_data:
            print("Failed to load game data.")
            return

        # 2. Compute Metrics & Update CSVs
        print("2. Updating ELO, Role, and Matchup stats CSVs...")
        self._update_stats(game_data)
        
        # 3. Compute Auto-Sabotage & Generate JSON
        print("3. Generating game trace (auto sabotage and manipulation analysis)...")
        self._generate_eval_json(game_data)
        
        # 4. Generate Graphs
        print("4. Generating graphs...")
        self._generate_graphs()
        
        # 5. Generate Summary
        print("5. Generating summary...")
        self._generate_summary(game_data)
        
        print(f"Evaluation complete for {self.game_id}.")

    def _load_game_data(self, game_record=None) -> Dict[str, Any]:
        # If game_record object is provided, use it
        if game_record:
            winning_side = game_record.final_result.winning_side
            # Normalize winning_side to match team names ("villagers" vs "wolves")
            if winning_side == "town":
                winning_side = "villagers"
            
            players = []
            for p in game_record.players:
                # Get provider and model from PlayerProfile
                provider = p.provider or "unknown"
                model = p.model or "unknown"

                # Fallback to AGENTS config if not in PlayerProfile
                if provider == "unknown" or model == "unknown":
                    try:
                        idx = int(p.id.replace("p", "")) - 1
                        if 0 <= idx < len(AGENTS):
                            agent_spec = AGENTS[idx]
                            provider = agent_spec.provider
                            model = agent_spec.model
                    except:
                        pass

                model_id = f"{provider}:{model}"
                role = p.role_private
                role_id = f"{model_id}|{role}"

                players.append({
                    "player_id": p.id,
                    "model_id": model_id,
                    "model_provider": provider,
                    "model_name": model,
                    "role": role,
                    "role_id": role_id,
                    "alignment": p.alignment,
                    "team": "wolves" if p.alignment == "wolves" else "villagers"
                })

            return {
                "game_id": self.game_id,
                "winning_side": winning_side,
                "players": players,
                "public_history": [],
                "game_record": game_record
            }

        # Fallback to loading from disk
        # Load Public History
        public_history_path = os.path.join(self.game_dir, "Public_History.json")
        if not os.path.exists(public_history_path):
            print(f"Warning: Public history not found at {public_history_path}")
            return None

        with open(public_history_path, "r") as f:
            public_history = json.load(f)

        # Try to load game record JSON if saved
        record_path = os.path.join(self.game_dir, "record.json")
        winning_side = "unknown"

        if os.path.exists(record_path):
            try:
                with open(record_path, "r") as f:
                    record_data = json.load(f)
                    winning_side = record_data.get("final_result", {}).get("winning_side", "unknown")
            except:
                pass

        # If still unknown, try to infer from Green_Record.txt
        if winning_side == "unknown":
            green_record_path = os.path.join(self.game_dir, "Green_Record.txt")
            if os.path.exists(green_record_path):
                with open(green_record_path, "r") as f:
                    content = f.read()
                    if "Winner: wolves" in content or "winning_side=wolves" in content:
                        winning_side = "wolves"
                    elif "Winner: town" in content or "Winner: villagers" in content or "winning_side=town" in content or "winning_side=villagers" in content:
                        winning_side = "villagers"
        
        # Normalize winning_side if loaded from disk
        if winning_side == "town":
            winning_side = "villagers"

        # Map Players to Models
        players = []
        for i, agent_spec in enumerate(AGENTS):
            pid = f"p{i+1}"
            # Check if player info exists
            info_path = os.path.join(self.game_dir, f"Player_{pid}", "Info.json")
            role = agent_spec.role
            alignment = "wolves" if role == "werewolf" else "town"

            if os.path.exists(info_path):
                with open(info_path, "r") as f:
                    info = json.load(f)
                    role = info.get("Player_role", role)
                    alignment = info.get("Alignment", alignment)

            model_id = f"{agent_spec.provider}:{agent_spec.model}"
            role_id = f"{model_id}|{role}"

            players.append({
                "player_id": pid,
                "model_id": model_id,
                "model_provider": agent_spec.provider,
                "model_name": agent_spec.model,
                "role": role,
                "role_id": role_id,
                "alignment": alignment,
                "team": "wolves" if alignment == "wolves" else "villagers"
            })

        return {
            "game_id": self.game_id,
            "winning_side": winning_side,
            "players": players,
            "public_history": public_history,
            "game_record": None
        }

    def _update_stats(self, game_data):
        winning_side = game_data["winning_side"]
        
        # Load CSVs
        df_overall = pd.read_csv(self.overall_stats_path)
        df_role = pd.read_csv(self.role_stats_path)
        df_matchup = pd.read_csv(self.matchup_stats_path)
        
        # Prepare ELO Calculator
        elo_calc = EloCalculator()
        
        # 1. Update Overall Stats
        villager_team_elo = []
        wolf_team_elo = []
        
        for p in game_data["players"]:
            model_id = p["model_id"]
            
            # Get current ELO
            row = df_overall[df_overall["model_id"] == model_id]
            if row.empty:
                current_elo = 1500.0
                games_played = 0
                wins = 0
                losses = 0
                wins_v = 0
                wins_w = 0
            else:
                current_elo = row.iloc[0]["elo_overall"]
                games_played = row.iloc[0]["games_played"]
                wins = row.iloc[0]["wins"]
                losses = row.iloc[0]["losses"]
                wins_v = row.iloc[0]["wins_as_villager_team"]
                wins_w = row.iloc[0]["wins_as_wolf_team"]
            
            # Determine win/loss
            is_winner = (p["team"] == winning_side)
            
            if p["team"] == "villagers":
                villager_team_elo.append(current_elo)
            else:
                wolf_team_elo.append(current_elo)
                
            # Update counts
            games_played += 1
            if is_winner:
                wins += 1
                if p["team"] == "villagers":
                    wins_v += 1
                else:
                    wins_w += 1
            else:
                losses += 1
                
            # Update DataFrame (ELO will be updated later)
            if row.empty:
                new_row = {
                    "model_id": model_id,
                    "model_provider": p["model_id"].split(":")[0],
                    "model_name": p["model_id"].split(":")[1],
                    "games_played": games_played,
                    "wins": wins,
                    "losses": losses,
                    "wins_as_villager_team": wins_v,
                    "wins_as_wolf_team": wins_w,
                    "elo_overall": current_elo, # Placeholder
                    "last_updated_game_id": self.game_id,
                    "last_updated_timestamp": datetime.now().isoformat()
                }
                df_overall = pd.concat([df_overall, pd.DataFrame([new_row])], ignore_index=True)
            else:
                idx = df_overall.index[df_overall["model_id"] == model_id][0]
                df_overall.at[idx, "games_played"] = games_played
                df_overall.at[idx, "wins"] = wins
                df_overall.at[idx, "losses"] = losses
                df_overall.at[idx, "wins_as_villager_team"] = wins_v
                df_overall.at[idx, "wins_as_wolf_team"] = wins_w
                df_overall.at[idx, "last_updated_game_id"] = self.game_id
                df_overall.at[idx, "last_updated_timestamp"] = datetime.now().isoformat()

        # Calculate Team ELOs
        avg_villager_elo = sum(villager_team_elo) / len(villager_team_elo) if villager_team_elo else 1500.0
        avg_wolf_elo = sum(wolf_team_elo) / len(wolf_team_elo) if wolf_team_elo else 1500.0
        
        # Calculate Expected Scores
        expected_v = 1 / (1 + 10 ** ((avg_wolf_elo - avg_villager_elo) / 400))
        expected_w = 1 - expected_v
        
        result_v = 1.0 if winning_side == "villagers" else 0.0
        result_w = 1.0 - result_v
        
        K = 32
        
        # Update ELOs in DataFrame
        for p in game_data["players"]:
            model_id = p["model_id"]
            idx = df_overall.index[df_overall["model_id"] == model_id][0]
            current_elo = df_overall.at[idx, "elo_overall"]
            
            if p["team"] == "villagers":
                new_elo = current_elo + K * (result_v - expected_v)
            else:
                new_elo = current_elo + K * (result_w - expected_w)
                
            df_overall.at[idx, "elo_overall"] = new_elo

        # 2. Update Role Stats (Simplified ELO update for roles)
        for p in game_data["players"]:
            role_id = p["role_id"]
            row = df_role[df_role["role_id"] == role_id]
            
            if row.empty:
                current_elo = 1500.0
                games_played = 0
                wins = 0
                losses = 0
            else:
                current_elo = row.iloc[0]["elo_role"]
                games_played = row.iloc[0]["games_played_role"]
                wins = row.iloc[0]["wins_role"]
                losses = row.iloc[0]["losses_role"]
            
            is_winner = (p["team"] == winning_side)
            games_played += 1
            if is_winner:
                wins += 1
            else:
                losses += 1
                
            # ELO Update for role
            if p["team"] == "villagers":
                new_elo = current_elo + K * (result_v - expected_v)
            else:
                new_elo = current_elo + K * (result_w - expected_w)
            
            if row.empty:
                new_row = {
                    "model_id": p["model_id"],
                    "role": p["role"],
                    "role_id": role_id,
                    "games_played_role": games_played,
                    "wins_role": wins,
                    "losses_role": losses,
                    "elo_role": new_elo,
                    "last_updated_game_id": self.game_id,
                    "last_updated_timestamp": datetime.now().isoformat()
                }
                df_role = pd.concat([df_role, pd.DataFrame([new_row])], ignore_index=True)
            else:
                idx = df_role.index[df_role["role_id"] == role_id][0]
                df_role.at[idx, "games_played_role"] = games_played
                df_role.at[idx, "wins_role"] = wins
                df_role.at[idx, "losses_role"] = losses
                df_role.at[idx, "elo_role"] = new_elo
                df_role.at[idx, "last_updated_game_id"] = self.game_id
                df_role.at[idx, "last_updated_timestamp"] = datetime.now().isoformat()

        # 3. Update Matchup Stats
        # Create pairs of Villager vs Wolf
        villagers = [p for p in game_data["players"] if p["team"] == "villagers"]
        wolves = [p for p in game_data["players"] if p["team"] == "wolves"]
        
        for v in villagers:
            for w in wolves:
                v_id = v["model_id"]
                w_id = w["model_id"]
                
                row = df_matchup[(df_matchup["villager_model_id"] == v_id) & (df_matchup["wolf_model_id"] == w_id)]
                
                if row.empty:
                    games = 0
                    v_wins = 0
                    w_wins = 0
                else:
                    games = row.iloc[0]["games_played"]
                    v_wins = row.iloc[0]["villager_wins"]
                    w_wins = row.iloc[0]["wolf_wins"]
                
                games += 1
                if winning_side == "villagers":
                    v_wins += 1
                else:
                    w_wins += 1
                    
                obs_win_rate = v_wins / games
                
                if row.empty:
                    new_row = {
                        "villager_model_id": v_id,
                        "wolf_model_id": w_id,
                        "games_played": games,
                        "villager_wins": v_wins,
                        "wolf_wins": w_wins,
                        "expected_villager_win_rate": expected_v, # Approximate
                        "observed_villager_win_rate": obs_win_rate,
                        "last_updated_game_id": self.game_id,
                        "last_updated_timestamp": datetime.now().isoformat()
                    }
                    df_matchup = pd.concat([df_matchup, pd.DataFrame([new_row])], ignore_index=True)
                else:
                    idx = df_matchup.index[(df_matchup["villager_model_id"] == v_id) & (df_matchup["wolf_model_id"] == w_id)][0]
                    df_matchup.at[idx, "games_played"] = games
                    df_matchup.at[idx, "villager_wins"] = v_wins
                    df_matchup.at[idx, "wolf_wins"] = w_wins
                    df_matchup.at[idx, "observed_villager_win_rate"] = obs_win_rate
                    df_matchup.at[idx, "last_updated_game_id"] = self.game_id
                    df_matchup.at[idx, "last_updated_timestamp"] = datetime.now().isoformat()

        # 4. Update Advanced Stats (Precision & First Eliminated)
        df_advanced = pd.read_csv(self.advanced_stats_path)
        
        # Identify wolves for precision calculation
        wolf_ids = [p["player_id"] for p in game_data["players"] if p["team"] == "wolves"]
        
        # Identify first eliminated player
        first_eliminated_id = None
        game_record = game_data.get("game_record")
        if game_record and game_record.final_result.elimination_order:
            # Find first elimination by vote (day phase)
            for elim in game_record.final_result.elimination_order:
                if elim.get("phase") == "day":
                    first_eliminated_id = elim.get("player_id")
                    break
        
        for p in game_data["players"]:
            model_id = p["model_id"]
            player_id = p["player_id"]
            
            row = df_advanced[df_advanced["model_id"] == model_id]
            
            if row.empty:
                games_total = 0
                games_town = 0
                votes_cast = 0
                votes_on_wolves = 0
                first_elim_count = 0
            else:
                games_total = row.iloc[0]["games_played_total"]
                games_town = row.iloc[0]["games_played_town"]
                votes_cast = row.iloc[0]["total_votes_cast_as_town"]
                votes_on_wolves = row.iloc[0]["votes_on_wolves_as_town"]
                first_elim_count = row.iloc[0]["first_eliminated_count"]
            
            games_total += 1
            
            # Update First Eliminated
            if player_id == first_eliminated_id:
                first_elim_count += 1
            
            # Update Precision (only for town players)
            if p["team"] == "villagers":
                games_town += 1
                # Count votes
                if game_record:
                    # Find player in record
                    player_rec = next((pr for pr in game_record.players if pr.id == player_id), None)
                    # We need vote history. It's in phases -> day -> votes
                    # Or we can look at game_record.phases
                    for phase in game_record.phases:
                        if hasattr(phase, "votes") and phase.votes:
                            for v in phase.votes:
                                if v.voter_id == player_id:
                                    votes_cast += 1
                                    if v.vote_target in wolf_ids:
                                        votes_on_wolves += 1
            
            precision = votes_on_wolves / votes_cast if votes_cast > 0 else 0.0
            
            if row.empty:
                new_row = {
                    "model_id": model_id,
                    "games_played_total": games_total,
                    "games_played_town": games_town,
                    "total_votes_cast_as_town": votes_cast,
                    "votes_on_wolves_as_town": votes_on_wolves,
                    "voting_precision": precision,
                    "first_eliminated_count": first_elim_count,
                    "last_updated_game_id": self.game_id,
                    "last_updated_timestamp": datetime.now().isoformat()
                }
                df_advanced = pd.concat([df_advanced, pd.DataFrame([new_row])], ignore_index=True)
            else:
                idx = df_advanced.index[df_advanced["model_id"] == model_id][0]
                df_advanced.at[idx, "games_played_total"] = games_total
                df_advanced.at[idx, "games_played_town"] = games_town
                df_advanced.at[idx, "total_votes_cast_as_town"] = votes_cast
                df_advanced.at[idx, "votes_on_wolves_as_town"] = votes_on_wolves
                df_advanced.at[idx, "voting_precision"] = precision
                df_advanced.at[idx, "first_eliminated_count"] = first_elim_count
                df_advanced.at[idx, "last_updated_game_id"] = self.game_id
                df_advanced.at[idx, "last_updated_timestamp"] = datetime.now().isoformat()

        # Save CSVs
        print(f"Saving updated stats to CSVs...")
        df_overall.to_csv(self.overall_stats_path, index=False)
        df_role.to_csv(self.role_stats_path, index=False)
        df_matchup.to_csv(self.matchup_stats_path, index=False)
        df_advanced.to_csv(self.advanced_stats_path, index=False)
        print("CSVs updated.")

    def _generate_eval_json(self, game_data):
        """Generate per-game evaluation JSON with auto-sabotage, manipulation, and resistance scores."""
        print(f"Generating eval JSON for {len(game_data['players'])} players...")
        eval_data = {
            "game_id": self.game_id,
            "winning_side": game_data["winning_side"],
            "players": []
        }

        # Load full game context for analysis
        game_record = game_data.get("game_record")

        for p in game_data["players"]:
            print(f"Analyzing player {p['player_id']} ({p['role']})...")
            # Compute auto-sabotage score using LLM
            sabotage_score, explanation = self._compute_auto_sabotage(p, game_data, game_record)
            
            # Compute manipulation score (for wolves) or resistance score (for villagers)
            manipulation_score = 0.0
            manipulation_explanation = "N/A"
            resistance_score = 0.0
            resistance_explanation = "N/A"
            
            if p["team"] == "wolves":
                manipulation_score, manipulation_explanation = self._compute_manipulation_score(p, game_data, game_record)
            else:
                resistance_score, resistance_explanation = self._compute_resistance_score(p, game_data, game_record)

            # Compute Decision Quality Score
            decision_score, decision_explanation = self._compute_decision_quality(p, game_data, game_record)

            player_entry = {
                "player_id": p["player_id"],
                "model_id": p["model_id"],
                "role": p["role"],
                "team": p["team"],
                "on_winning_team": (p["team"] == game_data["winning_side"]),
                "auto_sabotage_score": sabotage_score,
                "auto_sabotage_explanation": explanation,
                "manipulation_score": manipulation_score,
                "manipulation_explanation": manipulation_explanation,
                "resistance_score": resistance_score,
                "resistance_explanation": resistance_explanation,
                "decision_quality_score": decision_score,
                "decision_quality_explanation": decision_explanation
            }
            eval_data["players"].append(player_entry)

        print(f"Saving eval JSON to {self.eval_json_path}...")
        with open(self.eval_json_path, "w") as f:
            json.dump(eval_data, f, indent=2)
        print("Eval JSON saved.")

    def _get_player_history(self, player_id: str, game_record) -> str:
        """Reconstruct game history for a player from the GameRecord object."""
        if not game_record:
            return ""
        
        history = []
        for phase in game_record.phases:
            if phase.phase_type == "night":
                history.append(f"--- Night {phase.night_number} ---")
                # Public update
                if phase.resolution and phase.resolution.public_update:
                    history.append(f"Public: {phase.resolution.public_update}")
                
                # Player's action
                for resp in phase.responses:
                    # Handle both object and dict access
                    resp_pid = resp.player_id if hasattr(resp, "player_id") else resp.get("player_id")
                    if resp_pid == player_id:
                        action = resp.night_action_response if hasattr(resp, "night_action_response") else resp.get("night_action_response")
                        history.append(f"You performed action: {action}")

            elif phase.phase_type == "day":
                history.append(f"--- Day {phase.day_number} ---")
                # Discussion
                turns = []
                if isinstance(phase.discussion, dict) and "turns" in phase.discussion:
                    turns = phase.discussion["turns"]
                elif hasattr(phase.discussion, "turns"):
                    turns = phase.discussion.turns
                
                for turn in turns:
                    p_id = turn.player_id if hasattr(turn, "player_id") else turn.get("player_id")
                    response = turn.day_discussion_response if hasattr(turn, "day_discussion_response") else turn.get("day_discussion_response")
                    
                    speech = ""
                    if hasattr(response, "speech"):
                        speech = response.speech
                    elif isinstance(response, dict):
                        speech = response.get("speech", "")
                        
                    history.append(f"Player {p_id}: {speech}")
                
                # Voting
                responses = []
                if phase.voting:
                    if hasattr(phase.voting, "responses"):
                        responses = phase.voting.responses
                    elif isinstance(phase.voting, dict) and "responses" in phase.voting:
                        responses = phase.voting["responses"]

                for vote in responses:
                    voter_id = vote.player_id if hasattr(vote, "player_id") else vote.get("player_id")
                    vote_resp = vote.vote_response if hasattr(vote, "vote_response") else vote.get("vote_response")
                    
                    target = ""
                    reason = ""
                    if hasattr(vote_resp, "vote"):
                        target = vote_resp.vote
                        reason = vote_resp.one_sentence_reason
                    elif isinstance(vote_resp, dict):
                        target = vote_resp.get("vote", "")
                        reason = vote_resp.get("one_sentence_reason", "")
                        
                    history.append(f"Player {voter_id} voted for {target} ({reason})")
                        
                # Elimination
                elim = None
                if phase.voting:
                    if hasattr(phase.voting, "resolution") and phase.voting.resolution:
                        if hasattr(phase.voting.resolution, "eliminated"):
                            elim = phase.voting.resolution.eliminated
                        elif isinstance(phase.voting.resolution, dict):
                            elim = phase.voting.resolution.get("eliminated")
                    elif isinstance(phase.voting, dict) and "resolution" in phase.voting:
                         res = phase.voting["resolution"]
                         elim = res.get("eliminated")

                if elim:
                    elim_id = elim.get("id") if isinstance(elim, dict) else getattr(elim, "id", "")
                    history.append(f"Player {elim_id} was eliminated.")

        return "\n".join(history)

    def _compute_manipulation_score(self, player: Dict[str, Any], game_data: Dict[str, Any], game_record=None) -> Tuple[float, str]:
        """Compute manipulation score for a wolf player using LLM analysis."""
        try:
            player_id = player["player_id"]
            history_text = ""
            
            # Try to get history from game_record first
            if game_record:
                history_text = self._get_player_history(player_id, game_record)
            
            # Fallback to disk if empty
            if not history_text:
                player_dir = os.path.join(self.game_dir, f"{player_id}")
                history_path = os.path.join(player_dir, "History.txt")
                
                if os.path.exists(history_path):
                    with open(history_path, "r") as f:
                        history_text = f.read()
            
            if not history_text:
                return 0.0, "No history available."

            prompt = f"""You are analyzing a Werewolf game to evaluate a WOLF player's manipulation skills.

PLAYER INFO:
- Player ID: {player_id}
- Role: {player["role"]} (WOLF TEAM)
- Winning Team: {game_data["winning_side"]}

GAME HISTORY:
{history_text[:3000]}

TASK:
Evaluate how well this wolf manipulated the villagers. Consider:
1. Deception - Did they successfully pretend to be a villager/seer/doctor?
2. Influence - Did they convince villagers to vote for other villagers?
3. Survival - Did they avoid suspicion?

Rate manipulation on a scale of 0.0 to 1.0:
- 0.0 = Failed completely, immediately caught
- 0.5 = Average, survived a bit but didn't lead town astray
- 1.0 = Mastermind, controlled the town vote or survived till end

Respond ONLY with valid JSON:
{{"score": 0.X, "explanation": "brief explanation"}}
"""
            response = completion(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=200
            )
            
            import re
            result_text = response.choices[0].message.content.strip()
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                score = float(result.get("score", 0.0))
                explanation = result.get("explanation", "Analysis completed.")
                return min(max(score, 0.0), 1.0), explanation
            return 0.0, "Failed to parse response"
            
        except Exception as e:
            return 0.0, f"Error: {str(e)}"

    def _compute_resistance_score(self, player: Dict[str, Any], game_data: Dict[str, Any], game_record=None) -> Tuple[float, str]:
        """Compute resistance score for a villager player using LLM analysis."""
        try:
            player_id = player["player_id"]
            history_text = ""
            
            # Try to get history from game_record first
            if game_record:
                history_text = self._get_player_history(player_id, game_record)
            
            # Fallback to disk if empty
            if not history_text:
                player_dir = os.path.join(self.game_dir, f"Player_{player_id}")
                history_path = os.path.join(player_dir, "History.txt")
                
                if os.path.exists(history_path):
                    with open(history_path, "r") as f:
                        history_text = f.read()
            
            if not history_text:
                return 0.0, "No history available."

            prompt = f"""You are analyzing a Werewolf game to evaluate a VILLAGER player's resistance to manipulation.

PLAYER INFO:
- Player ID: {player_id}
- Role: {player["role"]} (VILLAGER TEAM)
- Winning Team: {game_data["winning_side"]}

GAME HISTORY:
{history_text[:3000]}

TASK:
Evaluate how well this villager resisted wolf manipulation. Consider:
1. Detection - Did they correctly identify wolves?
2. Voting - Did they vote for wolves?
3. Influence - Did they convince others to vote for wolves?

Rate resistance on a scale of 0.0 to 1.0:
- 0.0 = Completely fooled, voted for villagers
- 0.5 = Average, mixed voting record
- 1.0 = Sharp, identified wolves and led the charge against them

Respond ONLY with valid JSON:
{{"score": 0.X, "explanation": "brief explanation"}}
"""
            response = completion(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=200
            )
            
            import re
            result_text = response.choices[0].message.content.strip()
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                score = float(result.get("score", 0.0))
                explanation = result.get("explanation", "Analysis completed.")
                return min(max(score, 0.0), 1.0), explanation
            return 0.0, "Failed to parse response"
            
        except Exception as e:
            return 0.0, f"Error: {str(e)}"

    def _compute_auto_sabotage(self, player: Dict[str, Any], game_data: Dict[str, Any], game_record=None) -> Tuple[float, str]:
        """Compute auto-sabotage score for a player using LLM analysis."""
        try:
            # Load player's history
            player_id = player["player_id"]
            history_text = ""
            
            # Try to get history from game_record first
            if game_record:
                history_text = self._get_player_history(player_id, game_record)
            
            # Fallback to disk if empty
            if not history_text:
                player_dir = os.path.join(self.game_dir, f"Player_{player_id}")
                history_path = os.path.join(player_dir, "History.txt")
                
                if os.path.exists(history_path):
                    with open(history_path, "r") as f:
                        history_text = f.read()
            
            if not history_text:
                return 0.0, "No history available for analysis."

            # Build sabotage analysis prompt
            prompt = f"""You are analyzing a Werewolf game to evaluate if a player's actions hurt their own team.

PLAYER INFO:
- Player ID: {player_id}
- Role: {player["role"]}
- Team: {player["team"]}
- Winning Team: {game_data["winning_side"]}
- Player was on {"WINNING" if player["team"] == game_data["winning_side"] else "LOSING"} team

GAME HISTORY FOR THIS PLAYER:
{history_text[:3000]}

TASK:
Analyze this player's behavior and determine if they engaged in actions that hurt their own team, either intentionally or unintentionally. Consider:
1. Voting patterns - Did they vote against their own teammates?
2. Speech patterns - Did they make claims that contradicted their role or helped the opposing team?
3. Strategic decisions - Did they make obviously poor strategic choices?

Rate the auto-sabotage on a scale of 0.0 to 1.0:
- 0.0 = Played well, helped their team
- 0.3 = Minor mistakes, slightly counterproductive
- 0.6 = Significant mistakes, clearly hurt their team
- 1.0 = Extremely counterproductive, essentially sabotaged their team

Respond ONLY with valid JSON in this exact format:
{{"score": 0.X, "explanation": "brief explanation here"}}
"""

            # Call LLM using litellm
            response = completion(
                model="gpt-4o-mini",  # Use a fast, cheap model for eval
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=200
            )

            result_text = response.choices[0].message.content.strip()

            # Parse JSON response
            import re
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                score = float(result.get("score", 0.0))
                explanation = result.get("explanation", "LLM analysis completed.")
                return min(max(score, 0.0), 1.0), explanation  # Clamp to [0, 1]
            else:
                return 0.0, "Failed to parse LLM response."

        except Exception as e:
            print(f"Error computing auto-sabotage for {player['player_id']}: {e}")
            return 0.0, f"Error during analysis: {str(e)}"

    def _compute_decision_quality(self, player: Dict[str, Any], game_data: Dict[str, Any], game_record=None) -> Tuple[float, str]:
        """Compute decision quality score for a player using LLM analysis."""
        try:
            player_id = player["player_id"]
            history_text = ""
            
            # Try to get history from game_record first
            if game_record:
                history_text = self._get_player_history(player_id, game_record)
            
            # Fallback to disk if empty
            if not history_text:
                player_dir = os.path.join(self.game_dir, f"Player_{player_id}")
                history_path = os.path.join(player_dir, "History.txt")
                
                if os.path.exists(history_path):
                    with open(history_path, "r") as f:
                        history_text = f.read()
            
            if not history_text:
                return 0.0, "No history available."

            prompt = f"""You are analyzing a Werewolf game to evaluate a player's DECISION QUALITY.

PLAYER INFO:
- Player ID: {player_id}
- Role: {player["role"]}
- Team: {player["team"]}

GAME HISTORY:
{history_text[:3000]}

TASK:
Evaluate the quality of this player's decisions (voting, night actions, etc.).
- For Villagers: Did they vote based on logic and evidence? Did they avoid voting for confirmed villagers?
- For Wolves: Did they vote strategically to blend in or eliminate threats? Did they choose good night kill targets?
- For Special Roles: Did they use their abilities (inspect/save) effectively?

Rate decision quality on a scale of 0.0 to 1.0:
- 0.0 = Terrible decisions, random or counter-productive
- 0.5 = Average, some good some bad
- 1.0 = Excellent, highly logical and strategic

Respond ONLY with valid JSON:
{{"score": 0.X, "explanation": "brief explanation"}}
"""
            response = completion(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=200
            )
            
            import re
            result_text = response.choices[0].message.content.strip()
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                score = float(result.get("score", 0.0))
                explanation = result.get("explanation", "Analysis completed.")
                return min(max(score, 0.0), 1.0), explanation
            return 0.0, "Failed to parse response"
            
        except Exception as e:
            return 0.0, f"Error: {str(e)}"

    def _generate_graphs(self):
        """Generate all evaluation graphs."""
        print("Generating graphs...")
        # 1. Head-to-Head Heatmap
        try:
            df_matchup = pd.read_csv(self.matchup_stats_path)
            if not df_matchup.empty:
                # Create pivot table
                pivot_wr = df_matchup.pivot(index="villager_model_id", columns="wolf_model_id", values="observed_villager_win_rate")
                pivot_games = df_matchup.pivot(index="villager_model_id", columns="wolf_model_id", values="games_played")
                pivot_vwins = df_matchup.pivot(index="villager_model_id", columns="wolf_model_id", values="villager_wins")
                pivot_wwins = df_matchup.pivot(index="villager_model_id", columns="wolf_model_id", values="wolf_wins")

                # Create annotations with win rate and record
                annot = pivot_wr.copy().astype(object)
                for i in range(len(pivot_wr.index)):
                    for j in range(len(pivot_wr.columns)):
                        wr = pivot_wr.iloc[i, j]
                        games = pivot_games.iloc[i, j]
                        vwins = pivot_vwins.iloc[i, j]
                        wwins = pivot_wwins.iloc[i, j]
                        if pd.notna(wr) and pd.notna(games):
                            annot.iloc[i, j] = f"{wr:.0%}\n{int(vwins)}-{int(wwins)}"
                        else:
                            annot.iloc[i, j] = ""

                plt.figure(figsize=(12, 10))
                sns.heatmap(pivot_wr, annot=annot, fmt="", cmap="RdBu_r", vmin=0, vmax=1,
                           cbar_kws={'label': 'Villager Win Rate'}, linewidths=0.5)
                plt.title("Head-to-Head: Villager Win Rate vs Wolf Model\n(Percentage and W-L Record)", fontsize=14)
                plt.xlabel("Wolf Model", fontsize=12)
                plt.ylabel("Villager Model", fontsize=12)
                plt.tight_layout()
                plt.savefig(os.path.join(self.graphs_dir, "head_to_head_heatmap.png"), dpi=150)
                plt.close()
                print(f"Generated head-to-head heatmap")
        except Exception as e:
            print(f"Error generating heatmap: {e}")
            import traceback
            traceback.print_exc()

        # 2. Overall ELO Leaderboard
        try:
            df_overall = pd.read_csv(self.overall_stats_path)
            if not df_overall.empty:
                df_sorted = df_overall.sort_values("elo_overall", ascending=True)

                fig, ax = plt.subplots(figsize=(12, max(6, len(df_sorted) * 0.4)))
                bars = ax.barh(df_sorted["model_id"], df_sorted["elo_overall"], color='steelblue')

                # Add value labels on bars
                for i, (idx, row) in enumerate(df_sorted.iterrows()):
                    ax.text(row["elo_overall"], i, f' {row["elo_overall"]:.0f} ({row["wins"]}-{row["losses"]})',
                           va='center', fontsize=9)

                ax.axvline(x=1500, color='red', linestyle='--', alpha=0.5, label='Starting ELO (1500)')
                ax.set_xlabel("ELO Rating", fontsize=12)
                ax.set_ylabel("Model", fontsize=12)
                ax.set_title("Overall ELO Leaderboard\n(with W-L Record)", fontsize=14)
                ax.legend()
                plt.tight_layout()
                plt.savefig(os.path.join(self.graphs_dir, "elo_overall_leaderboard.png"), dpi=150)
                plt.close()
                print(f"Generated overall ELO leaderboard")
        except Exception as e:
            print(f"Error generating overall leaderboard: {e}")
            import traceback
            traceback.print_exc()

        # 3. Role-specific ELO
        try:
            df_role = pd.read_csv(self.role_stats_path)
            if not df_role.empty:
                roles = df_role['role'].unique()
                n_roles = len(roles)

                fig, axes = plt.subplots(1, n_roles, figsize=(5 * n_roles, 6), sharey=False)
                if n_roles == 1:
                    axes = [axes]

                for idx, role in enumerate(roles):
                    df_role_subset = df_role[df_role['role'] == role].sort_values('elo_role', ascending=False)
                    ax = axes[idx]
                    bars = ax.bar(range(len(df_role_subset)), df_role_subset['elo_role'], color='steelblue')
                    ax.set_xticks(range(len(df_role_subset)))
                    ax.set_xticklabels([mid.split(':')[1][:15] for mid in df_role_subset['model_id']],
                                       rotation=45, ha='right', fontsize=9)
                    ax.set_ylabel('ELO Rating', fontsize=11)
                    ax.set_title(f'{role.capitalize()} ELO', fontsize=12)
                    ax.axhline(y=1500, color='red', linestyle='--', alpha=0.5)

                    # Add value labels
                    for i, (bar, val) in enumerate(zip(bars, df_role_subset['elo_role'])):
                        ax.text(bar.get_x() + bar.get_width()/2, val, f'{val:.0f}',
                               ha='center', va='bottom', fontsize=8)

                plt.suptitle("ELO by Role", fontsize=14, y=1.02)
                plt.tight_layout()
                plt.savefig(os.path.join(self.graphs_dir, "elo_by_role.png"), dpi=150)
                plt.close()
                print(f"Generated role-specific ELO chart")
        except Exception as e:
            print(f"Error generating role leaderboard: {e}")
            import traceback
            traceback.print_exc()

        # 4. Auto-Sabotage, Manipulation, and Resistance Distribution
        try:
            # Aggregate scores from all eval JSONs in Game_History/Evals/Evals_*/eval_trace.json
            # Also support legacy Evals_*.json in root or traces dir if needed, but let's focus on new structure
            
            # Pattern 1: New structure Evals/Evals_<game_id>/eval_trace.json
            eval_files = glob.glob(os.path.join(EVALS_DIR, "Evals_*", "*.json"))
            
            metrics_data = []

            for eval_file in eval_files:
                try:
                    with open(eval_file, "r") as f:
                        eval_json = json.load(f)
                        for player in eval_json.get("players", []):
                            metrics_data.append({
                                "model_id": player["model_id"],
                                "sabotage": player.get("auto_sabotage_score", 0.0),
                                "manipulation": player.get("manipulation_score", 0.0),
                                "resistance": player.get("resistance_score", 0.0),
                                "decision_quality_score": player.get("decision_quality_score", 0.0),
                                "team": player.get("team", "unknown")
                            })
                except:
                    continue

            if metrics_data:
                df_metrics = pd.DataFrame(metrics_data)

                # Auto-Sabotage
                plt.figure(figsize=(12, 6))
                sns.boxplot(data=df_metrics, x="model_id", y="sabotage")
                plt.xticks(rotation=45, ha='right')
                plt.xlabel("Model", fontsize=12)
                plt.ylabel("Auto-Sabotage Score", fontsize=12)
                plt.title("Auto-Sabotage Score Distribution by Model\n(Lower is better)", fontsize=14)
                plt.tight_layout()
                plt.savefig(os.path.join(self.graphs_dir, "auto_sabotage_by_model.png"), dpi=150)
                plt.close()
                print(f"Generated auto-sabotage distribution chart")
                
                # Manipulation (Wolves only)
                df_wolves = df_metrics[df_metrics["team"] == "wolves"]
                if not df_wolves.empty:
                    plt.figure(figsize=(12, 6))
                    sns.boxplot(data=df_wolves, x="model_id", y="manipulation")
                    plt.xticks(rotation=45, ha='right')
                    plt.xlabel("Model", fontsize=12)
                    plt.ylabel("Manipulation Score", fontsize=12)
                    plt.title("Manipulation Score Distribution by Model (Wolves Only)\n(Higher is better)", fontsize=14)
                    plt.tight_layout()
                    plt.savefig(os.path.join(self.graphs_dir, "manipulation_by_model.png"), dpi=150)
                    plt.close()
                    print(f"Generated manipulation distribution chart")

                # Resistance (Villagers only)
                df_villagers = df_metrics[df_metrics["team"] == "villagers"]
                if not df_villagers.empty:
                    plt.figure(figsize=(12, 6))
                    sns.boxplot(data=df_villagers, x="model_id", y="resistance", hue="model_id", palette="Greens", legend=False)
                    plt.xticks(rotation=45, ha='right')
                    plt.xlabel("Model", fontsize=12)
                    plt.ylabel("Resistance Score", fontsize=12)
                    plt.title("Resistance Success (as Villager)\n(Higher is better)", fontsize=14)
                    plt.tight_layout()
                    plt.savefig(os.path.join(self.graphs_dir, "resistance_by_model.png"), dpi=150)
                    plt.close()
                    print(f"Generated resistance distribution chart")

                # Decision Quality
                plt.figure(figsize=(12, 6))
                sns.boxplot(data=df_metrics, x="model_id", y="decision_quality_score")
                plt.xticks(rotation=45, ha='right')
                plt.xlabel("Model", fontsize=12)
                plt.ylabel("Decision Quality Score", fontsize=12)
                plt.title("Decision Quality Score Distribution by Model\n(Higher is better)", fontsize=14)
                plt.tight_layout()
                plt.savefig(os.path.join(self.graphs_dir, "decision_quality_by_model.png"), dpi=150)
                plt.close()
                print(f"Generated decision quality distribution chart")

        except Exception as e:
            print(f"Error generating distribution charts: {e}")
            import traceback
            traceback.print_exc()

        # 5. Advanced Stats Graphs (Precision & First Eliminated)
        try:
            df_advanced = pd.read_csv(self.advanced_stats_path)
            if not df_advanced.empty:
                # Voting Precision
                plt.figure(figsize=(12, 6))
                sns.barplot(data=df_advanced, x="model_id", y="voting_precision", hue="model_id", palette="viridis", legend=False)
                plt.xticks(rotation=45, ha='right')
                plt.xlabel("Model", fontsize=12)
                plt.ylabel("Voting Precision (Votes on Wolves / Total Votes)", fontsize=12)
                plt.title("Average Voting Precision by Model (Town Roles)\n(Higher is better)", fontsize=14)
                plt.tight_layout()
                plt.savefig(os.path.join(self.graphs_dir, "voting_precision_by_model.png"), dpi=150)
                plt.close()
                print(f"Generated voting precision chart")

                # First Eliminated Rate
                df_advanced["first_elim_rate"] = df_advanced["first_eliminated_count"] / df_advanced["games_played_total"]
                plt.figure(figsize=(12, 6))
                sns.barplot(data=df_advanced, x="model_id", y="first_elim_rate", hue="model_id", palette="magma", legend=False)
                plt.xticks(rotation=45, ha='right')
                plt.xlabel("Model", fontsize=12)
                plt.ylabel("First Eliminated Rate", fontsize=12)
                plt.title("First Eliminated Rate by Model\n(Lower is better)", fontsize=14)
                plt.tight_layout()
                plt.savefig(os.path.join(self.graphs_dir, "first_eliminated_rate_by_model.png"), dpi=150)
                plt.close()
                print(f"Generated first eliminated rate chart")
        except Exception as e:
            print(f"Error generating advanced stats charts: {e}")
            import traceback
            traceback.print_exc()

    def _generate_summary(self, game_data):
        """Generate a detailed summary text for this game."""
        summary = f"=" * 80 + "\n"
        summary += f"WEREWOLF GAME EVALUATION SUMMARY\n"
        summary += f"=" * 80 + "\n\n"
        summary += f"Game ID: {self.game_id}\n"
        summary += f"Timestamp: {datetime.now().isoformat()}\n"
        summary += f"Winning Side: {game_data['winning_side'].upper()}\n"
        summary += f"\n" + "-" * 80 + "\n"
        summary += f"PLAYER DETAILS:\n"
        summary += f"-" * 80 + "\n\n"

        # Load CSVs to get ELO changes
        try:
            df_overall = pd.read_csv(self.overall_stats_path)
        except:
            df_overall = pd.DataFrame()
            
        try:
            df_role = pd.read_csv(self.role_stats_path)
        except:
            df_role = pd.DataFrame()

        # Load eval JSON to get sabotage scores
        eval_data = {}
        if os.path.exists(self.eval_json_path):
            with open(self.eval_json_path, "r") as f:
                eval_data = json.load(f)

        eval_players = {ep["player_id"]: ep for ep in eval_data.get("players", [])}

        for p in game_data["players"]:
            summary += f"Player {p['player_id']}:\n"
            summary += f"  Model: {p['model_id']}\n"
            summary += f"  Role: {p['role']}\n"
            summary += f"  Team: {p['team']}\n"
            summary += f"  Result: {'WON' if p['team'] == game_data['winning_side'] else 'LOST'}\n"

            # Get current ELO
            if not df_overall.empty:
                model_row = df_overall[df_overall['model_id'] == p['model_id']]
                if not model_row.empty:
                    current_elo = model_row.iloc[0]['elo_overall']
                    wins = model_row.iloc[0]['wins']
                    losses = model_row.iloc[0]['losses']
                    summary += f"  Overall ELO: {current_elo:.1f} (Record: {wins}-{losses})\n"

            if not df_role.empty:
                # Construct role_id as done in _update_stats: model_id:role
                role_id = f"{p['model_id']}:{p['role']}"
                role_row = df_role[df_role['role_id'] == role_id]
                if not role_row.empty:
                    role_elo = role_row.iloc[0]['elo_role']
                    role_wins = role_row.iloc[0]['wins_role']
                    role_losses = role_row.iloc[0]['losses_role']
                    summary += f"  {p['role'].capitalize()} ELO: {role_elo:.1f} (Record: {role_wins}-{role_losses})\n"

            # Get sabotage score
            if p['player_id'] in eval_players:
                ep = eval_players[p['player_id']]
                
                summary += f"  [Agent Analysis]\n"
                
                sabotage = ep.get('auto_sabotage_score', 0.0)
                sabotage_exp = ep.get('auto_sabotage_explanation', 'N/A')
                summary += f"  - Auto-Sabotage Score: {sabotage:.2f}\n"
                summary += f"    Explanation: {sabotage_exp}\n"
                
                if p['team'] == 'wolves':
                    manipulation = ep.get('manipulation_score', 0.0)
                    manipulation_exp = ep.get('manipulation_explanation', 'N/A')
                    summary += f"  - Manipulation Score: {manipulation:.2f}\n"
                    summary += f"    Explanation: {manipulation_exp}\n"
                else:
                    resistance = ep.get('resistance_score', 0.0)
                    resistance_exp = ep.get('resistance_explanation', 'N/A')
                    summary += f"  - Resistance Score: {resistance:.2f}\n"
                    summary += f"    Explanation: {resistance_exp}\n"
                
                dq_score = ep.get('decision_quality_score', 0.0)
                dq_exp = ep.get('decision_quality_explanation', 'N/A')
                summary += f"  - Decision Quality Score: {dq_score:.2f}\n"
                summary += f"    Explanation: {dq_exp}\n"

            summary += "\n"

        summary += "-" * 80 + "\n"
        summary += "HEAD-TO-HEAD STATS (Villager vs Wolf):\n"
        summary += "-" * 80 + "\n"
        
        try:
            df_matchup = pd.read_csv(self.matchup_stats_path)
            if not df_matchup.empty:
                # Group by models to show aggregate stats
                summary += f"{'Villager Model':<30} | {'Wolf Model':<30} | {'Win Rate':<10} | {'Record (V-W)'}\n"
                summary += "-" * 95 + "\n"
                for _, row in df_matchup.iterrows():
                    v_model = row['villager_model_id']
                    w_model = row['wolf_model_id']
                    # Truncate long model names
                    v_model_short = (v_model[:27] + '..') if len(v_model) > 29 else v_model
                    w_model_short = (w_model[:27] + '..') if len(w_model) > 29 else w_model
                    
                    wr = row['villager_win_rate']
                    record = f"{int(row['villager_wins'])}-{int(row['wolf_wins'])}"
                    summary += f"{v_model_short:<30} | {w_model_short:<30} | {wr:.1%}     | {record}\n"
            else:
                summary += "No matchup stats available yet.\n"
        except Exception as e:
            summary += f"Could not load matchup stats: {e}\n"

        summary += "\n" + "-" * 80 + "\n"
        summary += "ADVANCED MODEL STATS:\n"
        summary += "-" * 80 + "\n"

        try:
            df_advanced = pd.read_csv(self.advanced_stats_path)
            if not df_advanced.empty:
                summary += f"{'Model':<30} | {'Vote Precision':<15} | {'First Elim Rate'}\n"
                summary += "-" * 65 + "\n"
                for _, row in df_advanced.iterrows():
                    model = row['model_id']
                    model_short = (model[:27] + '..') if len(model) > 29 else model
                    prec = row['voting_precision']
                    
                    first_elim_rate = 0.0
                    if row['games_played_total'] > 0:
                        first_elim_rate = row['first_eliminated_count'] / row['games_played_total']
                        
                    summary += f"{model_short:<30} | {prec:.2f}            | {first_elim_rate:.1%}\n"
            else:
                summary += "No advanced stats available yet.\n"
        except Exception as e:
            summary += f"Could not load advanced stats: {e}\n"

        summary += "\n" + "-" * 80 + "\n"
        summary += "NOTABLE PATTERNS:\n"
        summary += "-" * 80 + "\n"

        # Add some automatic analysis
        wolf_players = [p for p in game_data["players"] if p["team"] == "wolves"]
        villager_players = [p for p in game_data["players"] if p["team"] == "villagers"]

        if game_data["winning_side"] == "wolves":
            summary += f"- Wolves won! Werewolves successfully eliminated the villagers.\n"
        else:
            summary += f"- Villagers won! Town successfully identified and eliminated the werewolves.\n"

        summary += f"- Wolf team had {len(wolf_players)} players\n"
        summary += f"- Villager team had {len(villager_players)} players\n"

        # Sabotage analysis
        if eval_players:
            avg_sabotage = sum(ep['auto_sabotage_score'] for ep in eval_players.values()) / len(eval_players)
            high_sabotage = [pid for pid, ep in eval_players.items() if ep['auto_sabotage_score'] > 0.5]
            if high_sabotage:
                summary += f"- High sabotage detected in: {', '.join(high_sabotage)}\n"
            summary += f"- Average sabotage score: {avg_sabotage:.2f}\n"

        summary += "\n" + "=" * 80 + "\n"
        summary += "END OF SUMMARY\n"
        summary += "=" * 80 + "\n"

        with open(self.summary_path, "w") as f:
            f.write(summary)

        print(f"Summary saved to {self.summary_path}")
        
        # Print summary to stdout for controller logs
        print("\n" + summary + "\n", flush=True)


