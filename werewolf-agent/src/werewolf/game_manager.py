import httpx
import asyncio
import random
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

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

class GameManager:
    def __init__(self, players: List[PlayerProfile], config: Dict[str, Any]):
        self.players = players
        self.config = config
        self.player_map = {p.id: p for p in players}
        
        roles = {p.id: p.role_private for p in players}
        alignments = {p.id: p.alignment for p in players}
        self.state = GameState([p.id for p in players], roles, alignments)
        self.phases = []
        self.phase_sequence = []
        self.seed = random.randint(0, 1000000) # Should be passed in ideally

    async def run_game(self) -> GameRecord:
        print(f"Starting game with {len(self.players)} players")
        
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

        winner = self.state.winner()
        print(f"Game over. Winner: {winner}")
        
        final_result = FinalResult(
            winning_side=winner,
            reason=f"{winner} condition met",
            survivors=[
                {
                    "player_id": pid,
                    "role": self.state.roles[pid],
                    "alignment": self.state.alignments[pid],
                }
                for pid in self.state.living_players()
            ],
            elimination_order=self.state.elimination_order
        )

        return GameRecord(
            schema_version="1.0",
            game_id=f"game_{self.seed}",
            created_at_utc=datetime.now(timezone.utc),
            seed=self.seed,
            config=self.config,
            players=self.players,
            role_assignment=self.state.roles,
            phase_sequence=self.phase_sequence,
            phases=self.phases,
            final_result=final_result
        )

    async def run_night_phase(self) -> NightPhaseRecord:
        night_num = self.state.night_number
        print(f"Starting Night {night_num}")
        
        prompts: List[NightPromptRecord] = []
        responses: List[NightResponseRecord] = []
        
        # 1. Generate Prompts and Send to Agents
        agent_tasks = []
        for pid in self.state.living_players():
            role = self.state.roles[pid]
            prompt = self._generate_night_prompt(pid, role, night_num)
            
            prompts.append(NightPromptRecord(
                player_id=pid,
                night_role_prompt=prompt,
                private_thought="" # Placeholder
            ))
            
            agent_tasks.append(self._query_agent_night_action(pid, prompt))
            
        results = await asyncio.gather(*agent_tasks)
        
        # 2. Process Responses
        wolf_votes = []
        detective_action = None
        doctor_action = None
        
        for pid, response in zip(self.state.living_players(), results):
            responses.append(NightResponseRecord(
                player_id=pid,
                night_action_response=response
            ))
            
            role = self.state.roles[pid]
            if role == "werewolf":
                target = response.get("kill_vote")
                if target:
                    wolf_votes.append(target)
            elif role == "detective":
                target = response.get("inspect")
                if target:
                    detective_action = {"detective": pid, "target": target}
            elif role == "doctor":
                target = response.get("protect")
                if target:
                    doctor_action = {"doctor": pid, "target": target}

        # 3. Resolve Actions
        # Wolf Kill
        kill_target = None
        if wolf_votes:
            # Simple majority or random choice if tied
            from collections import Counter
            counts = Counter(wolf_votes)
            kill_target = counts.most_common(1)[0][0]
        
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

        # Apply Kill
        saved = bool(doctor_target and kill_result.get("saved_by"))
        if doctor_id:
            self.state.record_protection(doctor_id, doctor_target, night_num, saved)
            
        night_target = kill_result.get("target")
        if kill_result.get("success"):
            self.state.eliminate(night_target, "night_kill", "night", night_num)
            self.state.record_night_event(night_num, "night_kill", {"player_id": night_target})
        else:
            self.state.record_night_event(
                night_num, 
                "no_kill", 
                {"target": night_target, "saved_by": kill_result.get("saved_by")}
            )

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
            wolves_private_chat=[], # Not implemented yet
            prompts=prompts,
            responses=responses,
            resolution=resolution
        )

    def _generate_night_prompt(self, pid: str, role: str, night_num: int) -> NightRolePrompt:
        if role == "werewolf":
            wolf_partners = [p for p in self.state.wolves() if p != pid]
            return generate_wolf_night_prompt(self.state, pid, night_num, wolf_partners, [])
        elif role == "detective":
            return generate_detective_night_prompt(self.state, pid, night_num, [])
        elif role == "doctor":
            return generate_doctor_night_prompt(self.state, pid, night_num, {})
        else:
            return generate_villager_night_prompt(self.state, pid, night_num)

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
            print(f"Failed to query agent {pid}: {e}")
        
        # Fallback/Default random action if agent fails
        return self._get_fallback_night_action(pid, prompt)

    def _get_fallback_night_action(self, pid: str, prompt: NightRolePrompt) -> Dict[str, Any]:
        role = prompt.role
        if role == "werewolf":
            options = prompt.options.get("kill_options", [])
            return {"kill_vote": random.choice(options) if options else None, "reason": "Fallback random"}
        elif role == "detective":
            options = prompt.options.get("inspect_options", [])
            return {"inspect": random.choice(options) if options else None}
        elif role == "doctor":
            options = prompt.options.get("protect_options", [])
            return {"protect": random.choice(options) if options else None}
        return {"sleep": True}

    async def run_day_phase(self) -> DayPhaseRecord:
        day_num = self.state.day_number
        print(f"Starting Day {day_num}")
        
        # Discussion (Simplified: 1 round of statements)
        discussion_turns = []
        alive_players = self.state.living_players()
        
        for pid in alive_players:
            prompt = DayDiscussionPrompt(
                phase="day",
                day_number=day_num,
                you={"id": pid, "alive": True},
                players=[{"id": p, "alive": True} for p in alive_players],
                public_history=self.state.public_history,
                constraints=DayDiscussionConstraints(max_words=100)
            )
            
            # Query Agent
            response_text = await self._query_agent_discussion(pid, prompt)
            
            discussion_turns.append(DiscussionTurn(
                player_id=pid,
                day_discussion_prompt=prompt,
                private_thought="",
                day_discussion_response=DayDiscussionResponse(talk=response_text)
            ))

        # Voting
        prompts: List[VotePromptRecord] = []
        responses: List[VoteResponseRecord] = []
        vote_map = {}
        
        for pid in alive_players:
            prompt = DayVotePrompt(
                phase="vote",
                day_number=day_num,
                you={"id": pid},
                options=alive_players,
                public_summary="Vote for elimination."
            )
            
            prompts.append(VotePromptRecord(
                player_id=pid,
                day_vote_prompt=prompt,
                private_thought=""
            ))
            
            vote_resp = await self._query_agent_vote(pid, prompt)
            vote_map[pid] = vote_resp.vote
            
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
        else:
            self.state.public_history.append({
                "phase": "day",
                "day": day_num,
                "event": "no_elimination",
                "tally": tally
            })
            
        self.state.day_number += 1
        
        resolution = VoteResolution(tally=tally, eliminated=eliminated_payload, runoff=list(runoff) if runoff else None)
        
        return DayPhaseRecord(
            day_number=day_num,
            public_state=DayPublicState(alive_players=self.state.living_players(), public_history=list(self.state.public_history)),
            discussion={"turns": discussion_turns},
            voting=DayVotingRecord(prompts=prompts, responses=responses, resolution=resolution),
            end_of_day_summary={}
        )

    async def _query_agent_discussion(self, pid: str, prompt: DayDiscussionPrompt) -> str:
        player = self.player_map[pid]
        url = player.url or "http://localhost:8011"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(f"{url}/agent/discussion", json=prompt.model_dump(), timeout=10.0)
                if resp.status_code == 200:
                    return resp.json().get("talk", "")
        except:
            pass
        return "I have nothing to say."

    async def _query_agent_vote(self, pid: str, prompt: DayVotePrompt) -> VoteResponse:
        player = self.player_map[pid]
        url = player.url or "http://localhost:8011"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(f"{url}/agent/vote", json=prompt.model_dump(), timeout=10.0)
                if resp.status_code == 200:
                    data = resp.json()
                    return VoteResponse(vote=data.get("vote"), one_sentence_reason=data.get("reason", ""))
        except:
            pass
        
        # Fallback
        target = random.choice(prompt.options)
        return VoteResponse(vote=target, one_sentence_reason="Random fallback vote")
