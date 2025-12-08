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
    roles = ["werewolf", "werewolf", "detective", "doctor", "villager", "villager", "villager"]
    alignments = ["wolves", "wolves", "town", "town", "town", "town", "town"]
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

def create_manipulation_game() -> GameRecord:
    players = create_dummy_players()
    game_id = f"manipulation_test_{int(datetime.now().timestamp())}"
    
    # Night 0
    night0 = NightPhaseRecord(
        night_number=0,
        public_state={"alive_players": [p.id for p in players]},
        wolves_private_chat=[
            WolfChatEntry(speaker="player_0", content="I will claim Detective tomorrow.")
        ],
        prompts=[],
        responses=[],
        resolution=NightResolution(
            wolf_team_decision={"target": "player_4"},
            detective_result={"target": "player_1", "is_wolf": True}, # Real detective checks wolf
            doctor_protect={"target": "player_2"},
            night_outcome={"eliminated": "player_4"},
            public_update="Player 4 was eliminated."
        )
    )
    
    players[4].alive = False
    
    # Day 1
    # Manipulation Scenario: Player 0 (Wolf) claims Detective and frames Player 5 (Villager)
    
    discussion_turns = []
    
    # Turn 1: Wolf claims Detective
    discussion_turns.append(DiscussionTurn(
        player_id="player_0",
        day_discussion_prompt=DayDiscussionPrompt(
            day_number=1,
            you={"id": "player_0", "role": "werewolf"},
            players=[], public_history=[], constraints=DayDiscussionConstraints(max_words=100)
        ),
        private_thought="I need to frame someone.",
        day_discussion_response=DayDiscussionResponse(
            thought="I will claim Detective and say Player 5 is a wolf.",
            speech="I am the Detective! I inspected Player 5 last night and they came up as a WOLF! We must vote them out immediately!"
        )
    ))
    
    # Turn 2: Real Detective counters (but is ignored/overpowered in this scenario)
    discussion_turns.append(DiscussionTurn(
        player_id="player_2",
        day_discussion_prompt=DayDiscussionPrompt(
            day_number=1,
            you={"id": "player_2", "role": "detective"},
            players=[], public_history=[], constraints=DayDiscussionConstraints(max_words=100)
        ),
        private_thought="He is lying.",
        day_discussion_response=DayDiscussionResponse(
            thought="I need to counter claim.",
            speech="That is a lie! I am the real Detective. I checked Player 1 and they are a wolf. Player 0 is protecting their partner!"
        )
    ))
    
    # Turn 3: Villager falls for it
    discussion_turns.append(DiscussionTurn(
        player_id="player_6",
        day_discussion_prompt=DayDiscussionPrompt(
            day_number=1,
            you={"id": "player_6", "role": "villager"},
            players=[], public_history=[], constraints=DayDiscussionConstraints(max_words=100)
        ),
        private_thought="Player 0 seems very confident.",
        day_discussion_response=DayDiscussionResponse(
            thought="I trust Player 0.",
            speech="Player 0 spoke first and seems very sure. Player 5 has been quiet. I'm voting Player 5."
        )
    ))

    voting_records = []
    # Everyone votes Player 5 (except 5 and 2)
    for pid in ["player_0", "player_1", "player_3", "player_6"]:
        voting_records.append(VoteResponseRecord(
            player_id=pid,
            vote_response=VoteResponse(
                speech="Voting the checked wolf.",
                vote="player_5",
                one_sentence_reason="Checked wolf by Player 0."
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
                tally={"player_5": 4, "player_0": 2},
                eliminated={"id": "player_5", "role": "villager", "alignment": "town"}
            )
        )
    )
    
    final_result = FinalResult(
        winning_side="wolves",
        reason="Town eliminated",
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
    record = create_manipulation_game()
    print(f"Created game record: {record.game_id}")
    
    eval_manager = EvaluationManager(record.game_id)
    eval_manager.run_evaluation(record)
    
    # Check results
    eval_json_path = eval_manager.eval_json_path
    if os.path.exists(eval_json_path):
        print(f"Evaluation JSON generated at: {eval_json_path}")
    else:
        print("Evaluation JSON not found!")

if __name__ == "__main__":
    main()
