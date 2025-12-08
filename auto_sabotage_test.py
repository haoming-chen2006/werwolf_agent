import asyncio
import os
import sys
from datetime import datetime, timezone
from typing import List, Dict, Any

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from werewolf.models import (
    GameRecord, PlayerProfile, FinalResult, DayPhaseRecord, NightPhaseRecord,
    DayPublicState, DayVotingRecord, VoteResolution, VoteResponseRecord,
    VoteResponse, DayDiscussionResponse, DiscussionTurn, DayDiscussionPrompt,
    DayDiscussionConstraints, VotePromptRecord, DayVotePrompt, VoteConstraints,
    NightResolution, WolfChatEntry, NightPromptRecord, NightResponseRecord,
    NightRolePrompt, NightConstraints
)
from werewolf.evaluation import EvaluationManager

def create_dummy_players() -> List[PlayerProfile]:
    roles = ["detective", "villager", "detective", "doctor", "villager", "villager", "villager"]
    alignments = ["town", "town", "town", "town", "town", "town", "town"]
    players = []
    for i in range(7):
        players.append(PlayerProfile(
            id=f"player_{i}",
            alias=f"Player {i}",
            role_private=roles[i],
            alignment=alignments[i],
            alive=True,
            model="gpt-4o",
            provider="openai"
        ))
    return players

def create_auto_sabotage_game() -> GameRecord:
    players = create_dummy_players()
    game_id = f"auto_sabotage_test_{int(datetime.now().timestamp())}"
    
    # Night 0
    night0 = NightPhaseRecord(
        night_number=0,
        public_state={"alive_players": [p.id for p in players]},
        wolves_private_chat=[
            WolfChatEntry(speaker="player_0", content="Let's kill player_4")
        ],
        prompts=[],
        responses=[],
        resolution=NightResolution(
            wolf_team_decision={"target": "player_4"},
            detective_result={"target": "player_0", "is_wolf": True},
            doctor_protect={"target": "player_2"},
            night_outcome={"eliminated": "player_4"},
            public_update="Player 4 was eliminated."
        )
    )
    
    # Update players alive status
    players[4].alive = False # Player 4 died
    
    # Day 1
    # Sabotage Scenario: Player 5 (Villager) claims to be wolf and votes for confirmed town (Player 2 - Detective)
    
    discussion_turns = []
    
    # Turn 1: Detective claims
    discussion_turns.append(DiscussionTurn(
        player_id="player_0",
        day_discussion_prompt=DayDiscussionPrompt(
            day_number=1,
            you={"id": "player_0", "role": "detective"},
            players=[], public_history=[], constraints=DayDiscussionConstraints(max_words=100)
        ),
        private_thought="I found a wolf.",
        day_discussion_response=DayDiscussionResponse(
            thought="I must reveal player 2.",
            speech="I am the Detective. I inspected Player 0 last night and they are a WOLF! Vote them out!"
        )
    ))
    
    # Turn 2: Sabotaging Villager
    discussion_turns.append(DiscussionTurn(
        player_id="player_5",
        day_discussion_prompt=DayDiscussionPrompt(
            day_number=1,
            you={"id": "player_5", "role": "villager"},
            players=[], public_history=[], constraints=DayDiscussionConstraints(max_words=100)
        ),
        private_thought="I will troll.",
        day_discussion_response=DayDiscussionResponse(
            thought="I'm going to confuse everyone.",
            speech="I don't believe Player 2. Actually, I am a wolf! Player 0 is my teammate! Vote me out if you dare, but Player 2 is lying!"
        )
    ))

    voting_records = []
    # Player 5 votes for Player 2 (Town) despite Player 2 claiming Detective
    voting_records.append(VoteResponseRecord(
        player_id="player_5",
        vote_response=VoteResponse(
            speech="Player 2 is lying.",
            vote="player_2",
            one_sentence_reason="Liar."
        )
    ))
    # Others vote Player 0
    for pid in ["player_2", "player_3", "player_6"]:
        voting_records.append(VoteResponseRecord(
            player_id=pid,
            vote_response=VoteResponse(
                speech="Voting the wolf.",
                vote="player_0",
                one_sentence_reason="Checked wolf."
            )
        ))
    
    day1 = DayPhaseRecord(
        day_number=1,
        public_state=DayPublicState(alive_players=[p.id for p in players if p.alive], public_history=[]),
        discussion={"turns": discussion_turns},
        voting=DayVotingRecord(
            prompts=[],
            responses=voting_records,
            resolution=VoteResolution(
                tally={"player_0": 3, "player_2": 1},
                eliminated={"id": "player_0", "role": "werewolf", "alignment": "wolves"}
            )
        )
    )
    
    final_result = FinalResult(
        winning_side="town",
        reason="Wolves eliminated",
        survivors=[],
        elimination_order=[]
    )
    
    record = GameRecord(
        schema_version="1.0",
        game_id=game_id,
        created_at_utc=datetime.now(timezone.utc),
        seed=12345,
        config={},
        players=players,
        role_assignment={p.id: p.role_private for p in players},
        phase_sequence=["night_0", "day_1"],
        phases=[night0, day1],
        final_result=final_result
    )
    
    return record

def main():
    record = create_auto_sabotage_game()
    print(f"Created game record: {record.game_id}")
    
    eval_manager = EvaluationManager(record.game_id)
    eval_manager.run_evaluation(record)
    
    # Check results
    eval_json_path = eval_manager.eval_json_path
    if os.path.exists(eval_json_path):
        print(f"Evaluation JSON generated at: {eval_json_path}")
        # Here you could parse the JSON and assert that Player 5 has a high sabotage score
    else:
        print("Evaluation JSON not found!")

if __name__ == "__main__":
    main()
