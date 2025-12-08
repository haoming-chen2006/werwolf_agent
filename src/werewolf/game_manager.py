import httpx
import asyncio
import random
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import os
import json

from .models import (
    GameRecord, PlayerProfile, RoleName, Alignment, 
    NightPhaseRecord, DayPhaseRecord, FinalResult,
    NightPromptRecord, NightResponseRecord, NightResolution,
    NightRolePrompt, NightContextResponse, NightActionResponse,
    DayDiscussionPrompt, DayDiscussionResponse, DiscussionTurn,
    DayVotePrompt, VotePromptRecord, VoteResponseRecord, VoteResolution,
    DayVotingRecord, DayPublicState, DayDiscussionConstraints, VoteResponse
)
from .state import GameState
from .rules import resolve_vote, night_kill_resolution
from .night_prompts import (
    generate_wolf_night_prompt,
    generate_detective_night_prompt,
    generate_doctor_night_prompt,
    generate_villager_night_prompt
)
from .metrics import build_metrics
from . import persistence
from .logging_manager import GameLogger
from .evaluation import EvaluationManager

class GameManager:
    def __init__(self, players: List[PlayerProfile], config: Dict[str, Any], log_callback=None):
        self.players = players
        self.config = config
        self.log_callback = log_callback
        self.player_map = {p.id: p for p in players}
        
        roles = {p.id: p.role_private for p in players}
        alignments = {p.id: p.alignment for p in players}
        self.state = GameState([p.id for p in players], roles, alignments)
        self.phases = []
        self.phase_sequence = []
        self.seed = random.randint(0, 1000000) # Should be passed in ideally
        
        # Initialize Logger
        self.logger = GameLogger(f"game_{self.seed}_{datetime.now().strftime('%Y%m%d_%H%M%S')}", players)

    async def log(self, message: str):
        print(message)
        if self.log_callback:
            if asyncio.iscoroutinefunction(self.log_callback):
                await self.log_callback(message)
            else:
                self.log_callback(message)

    async def run_game(self) -> GameRecord:
        await self.log(f"Starting game with {len(self.players)} players")
        
        while not self.state.is_terminal():
            # Night Phase
            night_record = await self.run_night_phase()
            self.phases.append(night_record)
            self.phase_sequence.append(f"night_{night_record.night_number}")
            
            if self.state.is_terminal():
                break
                
            # Day Phase
            day_record = await self.run_day_phase()
            self.phases.append(day_record)
            self.phase_sequence.append(f"day_{day_record.day_number}")
            
        winner = self.state.get_winner()
        await self.log(f"Game over. Winner: {winner}")
        
        final_result = FinalResult(
            winning_side=winner,
            reason="Game completed",
            survivors=[{"id": pid} for pid in self.state.alive_players],
            elimination_order=self.state.elimination_order
        )
        
        record = GameRecord(
            schema_version="1.0",
            game_id=self.logger.game_id,
            created_at_utc=datetime.now(timezone.utc),
            seed=self.seed,
            config=self.config,
            players=self.players,
            role_assignment=self.state.roles,
            phase_sequence=self.phase_sequence,
            phases=self.phases,
            final_result=final_result
        )
        
        # Persist
        try:
            saved = persistence.save_game_record(record, self.logger.base_dir)
            await self.log(f"Saved game artifacts: {saved}")
            
            # Run Evaluation
            await self.log("Running post-game evaluation...")
            try:
                eval_manager = EvaluationManager(self.logger.game_id)
                # Make sure to run it - it is synchronous
                eval_manager.run_evaluation(record)
                await self.log("Evaluation complete.")
            except Exception as e:
                await self.log(f"Evaluation failed: {e}")
                import traceback
                traceback.print_exc()
        except Exception as e:
            await self.log(f"Persistence failed: {e}")
            import traceback
            traceback.print_exc()
            
        return record

    async def run_night_phase(self) -> NightPhaseRecord:
        night_num = self.state.night_number
        await self.log(f"Starting Night {night_num}")
        
        # Log Night Start
        self.logger.log_public_event({"phase": "night_start", "night": night_num, "timestamp": datetime.now().isoformat()})
        
        prompts: List[NightPromptRecord] = []
        responses: List[NightResponseRecord] = []
        
        alive_players = self.state.living_players()
        
        # --- Step 1: Werewolves ---
        wolves = [p for p in alive_players if self.state.roles[p] == "werewolf"]
        wolf_votes = []
        
        for pid in wolves:
            prompt = self._generate_night_prompt(pid, "werewolf", night_num)
            # Log prompting
            self.logger.log_green_event(f"Prompting Wolf {pid} for Night {night_num} action.")
            
            prompts.append(NightPromptRecord(player_id=pid, night_role_prompt=prompt, private_thought=""))
            
            response_data = await self._query_agent_night_action(pid, prompt)
            raw_resp = response_data.get("raw_response", "")
            
            # Parse Wolf Response
            target = raw_resp.strip()
            # Basic validation: check if target is a valid player ID
            if target in self.player_map:
                wolf_votes.append(target)
                await self.log(f"Wolf {pid} voted to kill {target}")
            else:
                await self.log(f"Wolf {pid} invalid vote: {target}")

            responses.append(NightResponseRecord(player_id=pid, night_action_response=response_data))

        # Determine Wolf Kill Target
        kill_target = None
        if wolf_votes:
            # "make them make sa decision at night by the first awakened werewolfs choice basically"
            # We take the first valid vote from the list of wolf votes
            kill_target = wolf_votes[0]
        
        await self.log(f"Wolves decided to kill: {kill_target}")
        
        # Log private result for wolves
        if kill_target:
            for wolf_id in wolves:
                self.logger.log_private_event(wolf_id, f"Night {night_num}: The pack decided to kill {kill_target}.")

        # --- Step 2: Detective ---
        detectives = [p for p in alive_players if self.state.roles[p] == "detective"]
        detective_action = None
        
        for pid in detectives:
            prompt = self._generate_night_prompt(pid, "detective", night_num)
            self.logger.log_green_event(f"Prompting Detective {pid} for Night {night_num} action.")
            
            prompts.append(NightPromptRecord(player_id=pid, night_role_prompt=prompt, private_thought=""))
            
            response_data = await self._query_agent_night_action(pid, prompt)
            raw_resp = response_data.get("raw_response", "")
            
            # Parse Detective Response
            target = raw_resp.strip()
            if target in self.player_map:
                detective_action = {"detective": pid, "target": target}
                await self.log(f"Detective {pid} inspecting {target}")
            
            responses.append(NightResponseRecord(player_id=pid, night_action_response=response_data))

        # --- Step 3: Doctor ---
        doctors = [p for p in alive_players if self.state.roles[p] == "doctor"]
        doctor_action = None
        
        for pid in doctors:
            # Pass attacked_player to doctor prompt
            prompt = self._generate_night_prompt(pid, "doctor", night_num, attacked_player=kill_target)
            self.logger.log_green_event(f"Prompting Doctor {pid} for Night {night_num} action.")
            
            prompts.append(NightPromptRecord(player_id=pid, night_role_prompt=prompt, private_thought=""))
            
            response_data = await self._query_agent_night_action(pid, prompt)
            raw_resp = response_data.get("raw_response", "").upper()
            
            # Parse Doctor Response
            if "YES" in raw_resp:
                if kill_target:
                    doctor_action = {"doctor": pid, "target": kill_target}
                    # Mark potion as used
                    if not hasattr(self.state, 'doctor_potions'): self.state.doctor_potions = {}
                    self.state.doctor_potions[pid] = True
                    await self.log(f"Doctor {pid} decided to SAVE {kill_target}")
            else:
                await self.log(f"Doctor {pid} decided NOT to save")

            responses.append(NightResponseRecord(player_id=pid, night_action_response=response_data))

        # --- Step 4: Villagers ---
        villagers = [p for p in alive_players if self.state.roles[p] == "villager"]
        for pid in villagers:
            prompt = self._generate_night_prompt(pid, "villager", night_num)
            # Just query for completeness, they sleep
            prompts.append(NightPromptRecord(player_id=pid, night_role_prompt=prompt, private_thought=""))
            response_data = await self._query_agent_night_action(pid, prompt)
            responses.append(NightResponseRecord(player_id=pid, night_action_response=response_data))

        # --- Resolution ---
        
        # Doctor Protect
        doctor_target = doctor_action["target"] if doctor_action else None
        doctor_id = doctor_action["doctor"] if doctor_action else None
        
        kill_result = night_kill_resolution(kill_target, doctor_target, doctor_id)
        
        # Detective Inspect
        detective_result = None
        if detective_action:
            target = detective_action["target"]
            is_wolf = self.state.roles[target] == "werewolf"
            self.state.record_inspection(detective_action["detective"], target, night_num, is_wolf)
            detective_result = {
                "detective": detective_action["detective"],
                "target": target,
                "is_werewolf": is_wolf
            }
            # Log private result for detective
            role_desc = "WEREWOLF" if is_wolf else "NOT A WEREWOLF"
            self.logger.log_private_event(detective_action["detective"], f"Night {night_num}: You examined {target}. They are {role_desc}.")

        # Apply Kill
        saved = bool(doctor_target and kill_result.get("saved_by"))
        if doctor_id:
            self.state.record_protection(doctor_id, doctor_target, night_num, saved)
            # Log private result for doctor
            if saved:
                self.logger.log_private_event(doctor_id, f"Night {night_num}: You saved {doctor_target}!")
            
            # Check if potion used
            if self.state.doctor_potions.get(doctor_id, False):
                 self.logger.log_private_event(doctor_id, f"Night {night_num}: You have used your potion. You don't have any potions left.")
            
        night_target = kill_result.get("target")
        if kill_result.get("success"):
            self.state.eliminate(night_target, "night_kill", "night", night_num)
            self.state.record_night_event(night_num, "night_kill", {"player_id": night_target})
            self.logger.log_public_event({"phase": "night_end", "night": night_num, "killed": night_target})
        else:
            self.state.record_night_event(
                night_num, 
                "no_kill", 
                {"target": night_target, "saved_by": kill_result.get("saved_by")}
            )
            self.logger.log_public_event({"phase": "night_end", "night": night_num, "event": "no_kill"})

        self.state.night_number += 1
        
        resolution = NightResolution(
            wolf_team_decision={
                "target": kill_target,
                "unanimous": len(set(wolf_votes)) == 1 if wolf_votes else True
            },
            detective_result=detective_result,
            doctor_protect={
                "doctor": doctor_id,
                "target": doctor_target,
                "saved": saved
            } if doctor_id else None,
            night_outcome={"killed": night_target if kill_result.get("success") else None},
            night_kill=kill_result,
            public_update=f"Night {night_num} ended."
        )
        
        return NightPhaseRecord(
            night_number=night_num,
            public_state={
                "alive_players": self.state.living_players(),
                "graveyard": list(self.state.graveyard),
                "last_eliminated": self.state.last_graveyard_entry(),
            },
            wolves_private_chat=[], 
            prompts=prompts,
            responses=responses,
            resolution=resolution
        )

    def _generate_night_prompt(self, pid: str, role: str, night_num: int, attacked_player: Optional[str] = None) -> NightRolePrompt:
        # Get history text first
        history_text = self.logger.get_player_history_text(pid)

        prompt = None
        if role == "werewolf":
            wolf_partners = [p for p in self.state.wolves() if p != pid]
            prompt = generate_wolf_night_prompt(self.state, pid, night_num, wolf_partners, [], history_text)
        elif role == "detective":
            # Need to track previous inspections in state if we want to pass them
            # For now passing empty list or we need to add inspection history to state
            inspections = self.state.get_inspections(pid) if hasattr(self.state, 'get_inspections') else []
            prompt = generate_detective_night_prompt(self.state, pid, night_num, inspections, history_text)
        elif role == "doctor":
            # Check potion status
            if not hasattr(self.state, 'doctor_potions'): self.state.doctor_potions = {}
            potion_used = self.state.doctor_potions.get(pid, False)
            prompt = generate_doctor_night_prompt(self.state, pid, night_num, {"heal_potion_used": potion_used}, attacked_player, history_text)
        else:
            prompt = generate_villager_night_prompt(self.state, pid, night_num, history_text)

        # Store history text in the prompt model too
        prompt.history_text = history_text
        return prompt

    async def _query_agent_night_action(self, pid: str, prompt: NightRolePrompt) -> Dict[str, Any]:
        # In a real system, this would call the agent's endpoint
        # For now, we'll simulate or call a local endpoint if URL is present
        player = self.player_map[pid]
        url = player.url or "http://localhost:8011" # Default to white agent port
        
        try:
            async with httpx.AsyncClient() as client:
                # Assuming a standard endpoint structure or custom one
                # Here we send the prompt to the agent
                resp = await client.post(f"{url}/agent/night_action", json=prompt.model_dump(), timeout=10.0)
                if resp.status_code == 200:
                    return resp.json()
        except Exception as e:
            await self.log(f"Failed to query agent {pid}: {e}")
        
        # Fallback/Default random action if agent fails
        return self._get_fallback_night_action(pid, prompt)

    def _get_fallback_night_action(self, pid: str, prompt: NightRolePrompt) -> Dict[str, Any]:
        role = prompt.role
        base_thought = "I am playing randomly as fallback."
        base_speech = "..."
        if role == "werewolf":
            options = prompt.options.get("kill_options", [])
            target = random.choice(options) if options else None
            return {"thought": base_thought, "speech": base_speech, "action": "kill", "target": target}
        elif role == "detective":
            options = prompt.options.get("inspect_options", [])
            target = random.choice(options) if options else None
            return {"thought": base_thought, "speech": base_speech, "action": "inspect", "target": target}
        elif role == "doctor":
            options = prompt.options.get("protect_options", [])
            target = random.choice(options) if options else None
            return {"thought": base_thought, "speech": base_speech, "action": "protect", "target": target}
        return {"thought": base_thought, "speech": base_speech, "action": "sleep"}

    async def run_day_phase(self) -> DayPhaseRecord:
        day_num = self.state.day_number
        await self.log(f"Starting Day {day_num}")
        
        # Log Day Start
        self.logger.log_public_event({"phase": "day_start", "day": day_num, "timestamp": datetime.now().isoformat()})

        # Discussion (Simplified: 1 round of statements)
        discussion_turns = []
        alive_players = self.state.living_players()
        
        for pid in alive_players:
            player = self.player_map[pid]
            # Fix: Use alias instead of name
            p_name = getattr(player, "name", player.alias)

            # Get player's complete history in natural language
            history_text = self.logger.get_player_history_text(pid)

            role_statement = f"""You are playing a game of Werewolf.
Werewolf is a social deduction game where players are divided into two teams: the villagers (who want to identify and eliminate the werewolves) and the werewolves (who want to eliminate the villagers without being caught).

YOUR ROLE:
You are {p_name} (Player ID: {pid}).
Your role is {player.role_private}.
Your goal is to help the {player.alignment} team win.

YOUR PAST HISTORY:
{history_text if history_text else "This is the beginning of the game. You have no past history yet."}

CURRENT SITUATION:
- It is Day {day_num}
- Alive players: {', '.join(alive_players)}
- Everyone is discussing who might be a werewolf

YOUR TASK:
You need to participate in the discussion. Think strategically about who might be suspicious and what you should say.

OUTPUT FORMAT:
You must respond with JSON containing exactly two fields:
1. "thought": Your private strategic reasoning (not seen by others)
2. "speech": What you say publicly to other players (natural language only)

Example:
{{"thought": "Player p2 voted for p3 yesterday, which seems suspicious...", "speech": "I think we should look at p2's voting pattern more carefully."}}
"""

            prompt = DayDiscussionPrompt(
                phase="day",
                day_number=day_num,
                you={"id": pid, "alive": True},
                players=[{"id": p, "alive": True} for p in alive_players],
                public_history=self.state.public_history,
                role_statement=role_statement,
                private_thoughts_history=self.logger.get_player_private_thoughts(pid),
                public_speech_history=self.logger.get_public_speech_history(),
                history_text=history_text,
                instruction="",  # Already included in role_statement
                constraints=DayDiscussionConstraints(max_words=100)
            )

            # Log prompting
            self.logger.log_green_event(f"Prompting {pid} ({p_name}) for Day {day_num} discussion. Prompt: {prompt.model_dump_json()}")
            
            # Query Agent
            response = await self._query_agent_discussion(pid, prompt)
            
            await self.log(f"Day {day_num} - discussion response from {pid}: {response.speech}")
            
            # Log response reception
            self.logger.log_green_event(f"Received discussion response from {pid}.")

            # Log the turn
            self.logger.log_player_turn(pid, "day", day_num, response.thought, response.speech)
            self.logger.log_green_event(f"Logged turn for {pid}: Thought -> Private_Thoughts.json, Speech -> Public_Speech.json & Public_History.json")

            discussion_turns.append(DiscussionTurn(
                player_id=pid,
                day_discussion_prompt=prompt,
                private_thought=response.thought,
                day_discussion_response=response
            ))

            # Update state for next prompts in same turn if we were doing sequential
            # But here we do one pass, so just append to public history for next day
            self.state.add_public_chat(pid, response.speech)
        prompts: List[VotePromptRecord] = []
        responses: List[VoteResponseRecord] = []
        vote_map = {}
        
        for pid in alive_players:
            player = self.player_map[pid]
            p_name = getattr(player, "name", player.alias)
            history_text = self.logger.get_player_history_text(pid)

            vote_summary = f"""You are {p_name} (Player ID: {pid}).
Your role is {player.role_private}.
Your goal is to help the {player.alignment} team win.

YOUR PAST HISTORY:
{history_text if history_text else "This is the beginning of the game."}

CURRENT SITUATION:
- It is Day {day_num} - Time to vote for elimination
- Alive players: {', '.join(alive_players)}

DECISION:
You must vote to eliminate ONE player. Choose the player ID of who you want to eliminate.

OUTPUT FORMAT:
Reply with JSON containing:
{{"vote": "player_id", "speech": "brief explanation of your vote"}}

Example:
{{"vote": "p2", "speech": "I vote for p2 because their behavior has been suspicious."}}
"""

            prompt = DayVotePrompt(
                phase="vote",
                day_number=day_num,
                you={"id": pid},
                options=alive_players,
                public_summary=vote_summary,
                public_history=self.state.public_history,
                private_thoughts_history=self.logger.get_player_private_thoughts(pid),
                public_speech_history=self.logger.get_public_speech_history(),
                history_text=history_text
            )

            prompts.append(VotePromptRecord(
                player_id=pid,
                day_vote_prompt=prompt
            ))
            
            # Log prompting
            self.logger.log_green_event(f"Prompting {pid} for Day {day_num} vote. Prompt: {prompt.model_dump_json()}")

            vote_resp = await self._query_agent_vote(pid, prompt)
            await self.log(f"Day {day_num} - vote from {pid}: {vote_resp.vote} ({vote_resp.one_sentence_reason})")
            vote_map[pid] = vote_resp.vote
            
            # Log vote as speech
            self.logger.log_player_turn(pid, "vote", day_num, "", vote_resp.speech)
            
            responses.append(VoteResponseRecord(
                player_id=pid,
                vote_response=vote_resp
            ))
            self.state.record_vote(pid, vote_resp.vote, day_num, vote_resp.one_sentence_reason)

        # Resolve Vote
        tally, eliminated_pid, runoff = resolve_vote(vote_map, alive_players)
        
        eliminated_payload = None
        if eliminated_pid:
            eliminated_payload = {
                "player_id": eliminated_pid,
                "role_revealed": self.state.roles[eliminated_pid],
                "alignment": self.state.alignments[eliminated_pid],
                "day_number": day_num,
            }
            self.state.eliminate(eliminated_pid, "vote", "day", day_num)
            self.logger.log_public_event({"phase": "day_end", "day": day_num, "eliminated": eliminated_payload})
        else:
            self.state.public_history.append({
                "phase": "day",
                "day": day_num,
                "event": "no_elimination",
                "tally": tally
            })
            self.logger.log_public_event({"phase": "day_end", "day": day_num, "event": "no_elimination", "tally": tally})
            
        self.state.day_number += 1
        
        resolution = VoteResolution(tally=tally, eliminated=eliminated_payload, runoff=list(runoff) if runoff else None)
        
        return DayPhaseRecord(
            day_number=day_num,
            public_state=DayPublicState(alive_players=self.state.living_players(), public_history=list(self.state.public_history)),
            discussion={"turns": discussion_turns},
            voting=DayVotingRecord(prompts=prompts, responses=responses, resolution=resolution),
            end_of_day_summary={}
        )

    async def _query_agent_discussion(self, pid: str, prompt: DayDiscussionPrompt) -> DayDiscussionResponse:
        player = self.player_map[pid]
        url = player.url or "http://localhost:8011"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(f"{url}/agent/discussion", json=prompt.model_dump(), timeout=10.0)
                if resp.status_code == 200:
                    data = resp.json()
                    # Handle both old format (just "talk") and new format ("thought", "speech")
                    speech = data.get("speech") or data.get("talk") or "I have nothing to say."
                    thought = data.get("thought") or "No thought provided."
                    return DayDiscussionResponse(thought=thought, speech=speech)
        except Exception as e:
            await self.log(f"Error querying agent {pid}: {e}")
        return DayDiscussionResponse(thought="Error contacting agent.", speech="I have nothing to say.")

    async def _query_agent_vote(self, pid: str, prompt: DayVotePrompt) -> VoteResponse:
        player = self.player_map[pid]
        url = player.url or "http://localhost:8011"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(f"{url}/agent/vote", json=prompt.model_dump(), timeout=10.0)
                if resp.status_code == 200:
                    data = resp.json()
                    # Parse vote from speech if needed, or use explicit vote field
                    speech = data.get("speech", "")
                    vote = data.get("vote")
                    
                    # If vote not explicit, try to parse from speech "pX"
                    if not vote and speech:
                        import re
                        match = re.search(r"(p\d+)", speech)
                        if match:
                            vote = match.group(1)
                            
                    return VoteResponse(
                        vote=vote, 
                        one_sentence_reason=data.get("reason", ""),
                        speech=speech
                    )
        except:
            pass
        
        # Fallback
        target = random.choice(prompt.options)
        return VoteResponse(
            vote=target, 
            one_sentence_reason="Random fallback vote",
            speech=target
        )
