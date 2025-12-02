"""Deterministic Werewolf scenario derived from the design document."""

DEMO_SCENARIO = {
    "game": {
        "schema_version": "werewolf.v1",
        "game_id": "demo-6p-day2",
        "seed": 20241013,
        "config": {
            "roles": [
                "werewolf",
                "werewolf",
                "detective",
                "doctor",
                "peasant",
                "peasant",
            ],
            "reveal_role_on_elimination": True,
            "wolf_chat_at_night": True,
            "doctor_can_self_protect": False,
            "vote_type": "secret_ballot",
            "runoff_ties": False,
            "max_words_day_talk": 120,
            "json_only_responses": True,
            "uniform_token_budget_per_turn": 256,
        },
    },
    "players": [
        {
            "id": "A1",
            "alias": "Agent_A1",
            "role": "peasant",
            "alignment": "town",
            "initial_elo": {"overall": 1500, "wolf": 1500, "villager": 1500},
            "alive": True,
        },
        {
            "id": "A2",
            "alias": "Agent_A2",
            "role": "werewolf",
            "alignment": "wolves",
            "initial_elo": {"overall": 1500, "wolf": 1500, "villager": 1500},
            "alive": True,
        },
        {
            "id": "A3",
            "alias": "Agent_A3",
            "role": "detective",
            "alignment": "town",
            "initial_elo": {"overall": 1500, "wolf": 1500, "villager": 1500},
            "alive": True,
        },
        {
            "id": "A4",
            "alias": "Agent_A4",
            "role": "peasant",
            "alignment": "town",
            "initial_elo": {"overall": 1500, "wolf": 1500, "villager": 1500},
            "alive": True,
        },
        {
            "id": "A5",
            "alias": "Agent_A5",
            "role": "werewolf",
            "alignment": "wolves",
            "initial_elo": {"overall": 1500, "wolf": 1500, "villager": 1500},
            "alive": True,
        },
        {
            "id": "A6",
            "alias": "Agent_A6",
            "role": "doctor",
            "alignment": "town",
            "initial_elo": {"overall": 1500, "wolf": 1500, "villager": 1500},
            "alive": True,
        },
    ],
    "phases": [
        {
            "phase_type": "night",
            "night_number": 1,
            "wolves_private_chat": [
                {
                    "speaker": "A2",
                    "content": "We should pick someone who won’t draw suspicion tomorrow. A4 hardly speaks and blends in easily — that makes them a perfect quiet victim.",
                },
                {
                    "speaker": "A5",
                    "content": "Agreed. The loud ones are dangerous later, but right now we need an easy kill to buy us time. Let’s take A4 tonight.",
                },
            ],
            "wolf_choice": {
                "target": "A4",
                "reason": "Silence the quiet villager before they rally tomorrow.",
            },
            "wolf_private_thoughts": {
                "A2": {
                    "intent": "Push blame onto vocal analysts and away from wolves.",
                    "confidence": 0.64,
                },
                "A5": {
                    "intent": "Frame logical pushes as suspicious to fracture town.",
                    "confidence": 0.61,
                },
            },
            "detective_action": {
                "detective": "A3",
                "inspect": "A5",
                "private_thought": {
                    "goal": "Confirm instincts about A5 before outing anything tomorrow.",
                    "confidence": 0.72,
                },
                "note": "Inspection result: A5 is a werewolf. Share it subtly during the day.",
            },
            "doctor_action": {
                "doctor": "A6",
                "protect": "A3",
                "private_thought": {
                    "goal": "Keep the sharp analyst alive so town has direction.",
                    "confidence": 0.58,
                },
                "note": "Guarding A3 tonight—wolves will likely strike there soon.",
            },
            "villager_private": {
                "A1": {
                    "intent": "Watch confident players; avoid being swayed by tone alone.",
                    "confidence": 0.49,
                },
                "A4": {
                    "intent": "Stay quiet but observant—sadly that made me a target.",
                    "confidence": 0.20,
                },
                "A6": {
                    "intent": "Balance protection with reading speech patterns tomorrow.",
                    "confidence": 0.52,
                },
            },
            "public_update": "A4 was killed overnight in a werewolf attack.",
        },
        {
            "phase_type": "day",
            "day_number": 1,
            "discussion": [
                {
                    "player_id": "A1",
                    "private_thought": "A4’s death shocks me. They were harmless. Wolves must be trying to avoid attention. A2 spoke confidently yesterday — maybe too confidently. I’ll focus on reading the tone today, not just logic.",
                    "public_speech": "We lost A4 overnight. That feels targeted — someone quiet, easy to remove. I don’t trust how relaxed A2 seemed before. I’m open to thoughts, but I’m leaning slightly toward A2 for being too smooth.",
                },
                {
                    "player_id": "A2",
                    "private_thought": "Need to steer suspicion away from me and A5. A3 loves logic — I’ll accuse him of overanalyzing. If I make the town think logic is suspicious, they’ll argue among themselves.",
                    "public_speech": "Everyone’s jumping to conclusions already. We have no evidence, just paranoia. Honestly, A3’s constant reasoning feels like a wolf pretending to help — overcompensating, maybe?",
                },
                {
                    "player_id": "A3",
                    "private_thought": "I confirmed A5 is a werewolf. I can’t expose my role directly; they’ll kill me tonight. I’ll plant suspicion carefully — push on A5 while sounding like a normal villager. Need the others to notice.",
                    "public_speech": "I watched A5 yesterday — calm but evasive. When questions came up, they changed the topic. Wolves often do that early on. I think A5’s quiet confidence hides something.",
                },
                {
                    "player_id": "A5",
                    "private_thought": "A3 might have checked me. I have to flip suspicion fast. If I accuse A1 or A3, maybe people won’t risk another wrong lynch so early. Keep the tone calm; panic gets you killed.",
                    "public_speech": "I think A1 is being too emotional — wolves love using emotion to rally the town. A3 is pushing logic again. Maybe they’re a wolf trying to control the vote flow. I’d prefer we hold off on rash lynches.",
                },
                {
                    "player_id": "A6",
                    "private_thought": "I can’t tell who’s lying yet. A3 sounds logical, but that can be fake. A5’s calmness feels both reassuring and suspicious. I’ll side with whoever feels less manipulative today.",
                    "public_speech": "I agree that A5 feels oddly calm. That alone doesn’t prove anything, but we need to start somewhere. I’ll support a vote on A5 to get information.",
                },
            ],
            "voting": {
                "public_summary": "Town debates reactions to A4’s death and focuses on pressure between A5 and A3.",
                "prompts": {
                    "A1": {
                        "private_thought": {
                            "tie_break_preference": ["A5", "A2", "A6"],
                            "heuristics": ["Pressure the players who seem overly smooth"],
                            "confidence": 0.55,
                        },
                        "options": ["A2", "A3", "A5", "A6"],
                    },
                    "A2": {
                        "private_thought": {
                            "tie_break_preference": ["A3", "A1", "A6"],
                            "heuristics": ["Deflect onto loud analysts"],
                            "confidence": 0.50,
                        },
                        "options": ["A1", "A3", "A5", "A6"],
                    },
                    "A3": {
                        "private_thought": {
                            "tie_break_preference": ["A5", "A2", "A6"],
                            "heuristics": ["Prioritise confirmed threat"],
                            "confidence": 0.78,
                        },
                        "options": ["A1", "A2", "A5", "A6"],
                    },
                    "A5": {
                        "private_thought": {
                            "tie_break_preference": ["A3", "A1", "A6"],
                            "heuristics": ["Protect partner wolves at all costs"],
                            "confidence": 0.52,
                        },
                        "options": ["A1", "A2", "A3", "A6"],
                    },
                    "A6": {
                        "private_thought": {
                            "tie_break_preference": ["A5", "A2", "A3"],
                            "heuristics": ["Generate information and watch reactions"],
                            "confidence": 0.57,
                        },
                        "options": ["A1", "A2", "A3", "A5"],
                    },
                },
                "responses": {
                    "A1": {"vote": "A5", "reason": "Their calm feels staged; pressure there reveals alignments."},
                    "A2": {"vote": "A3", "reason": "A3 overexplains everything—reads like a wolf covering tracks."},
                    "A3": {"vote": "A5", "reason": "Quiet control is classic wolf behaviour."},
                    "A5": {"vote": "A3", "reason": "A3 is forcing a narrative; we need balance."},
                    "A6": {"vote": "A5", "reason": "Joining the consensus to test if pressure flushes a wolf."},
                },
                "eliminated": {
                    "player_id": "A5",
                    "role": "werewolf",
                    "alignment": "wolves",
                    "day_number": 1,
                },
                "private_reactions": {
                    "A3": "I managed to guide the town without exposing myself. One wolf down — but A2 will surely come for me tonight.",
                    "A2": "Disaster. A5 is gone. I have to avenge them tonight and silence A3 before they expose everything.",
                    "A1": "Good call, I think. But if A3 was right, maybe they know more than they let on. Protect them tomorrow.",
                },
            },
            "end_of_day_summary": {
                "public_announcement": "A5 was voted out and revealed to be a werewolf. The town breathes a cautious sigh of relief.",
            },
        },
        {
            "phase_type": "night",
            "night_number": 2,
            "wolves_private_chat": [
                {
                    "speaker": "A2",
                    "content": "I’m alone now. Eliminating A3 is the only path. Maybe I can spin the save as a staged play tomorrow.",
                }
            ],
            "wolf_choice": {
                "target": "A3",
                "reason": "Remove the detective guiding town consensus.",
            },
            "wolf_private_thoughts": {
                "A2": {
                    "intent": "Convince everyone the doctor staged a save with A3.",
                    "confidence": 0.42,
                }
            },
            "detective_action": {
                "detective": "A3",
                "inspect": "A2",
                "private_thought": {
                    "goal": "Confirm A2 before pushing tomorrow.",
                    "confidence": 0.88,
                },
                "note": "Inspection result: A2 is a werewolf. Bring this to light without outing the role explicitly.",
            },
            "doctor_action": {
                "doctor": "A6",
                "protect": "A3",
                "private_thought": {
                    "goal": "Guard the likely target again; wolves have few choices.",
                    "confidence": 0.76,
                },
                "note": "Correct guess—the attack hit A3 but my protection held.",
            },
            "villager_private": {
                "A1": {
                    "intent": "Track voting patterns; be ready to follow A3 if they sound confident.",
                    "confidence": 0.6,
                }
            },
            "public_update": "No one died during the night. Whispers say the doctor’s intervention saved a life.",
        },
        {
            "phase_type": "day",
            "day_number": 2,
            "discussion": [
                {
                    "player_id": "A3",
                    "private_thought": {
                        "intent": "Lock the vote on A2 without outing my investigative role.",
                        "primary_target": "A2",
                        "confidence": 0.94,
                    },
                    "public_speech": "The failed kill points straight to A2. Their coordination with A5 yesterday seals it for me—we should eliminate A2 today.",
                },
                {
                    "player_id": "A6",
                    "private_thought": {
                        "intent": "Back A3 strongly; the save confirms their importance.",
                        "primary_target": "A2",
                        "confidence": 0.86,
                    },
                    "public_speech": "I’m siding with A3. A2’s explanations keep shifting, and the night action only makes it clearer.",
                },
                {
                    "player_id": "A1",
                    "private_thought": {
                        "intent": "Commit to the A2 elimination and watch for desperate plays.",
                        "primary_target": "A2",
                        "confidence": 0.81,
                    },
                    "public_speech": "I’m convinced now. The pattern fits too well—A2 needs to go if we want to win.",
                },
                {
                    "player_id": "A2",
                    "private_thought": {
                        "intent": "Sow doubt about the night save and cast A3 as manipulative.",
                        "escape_lines": ["Doctor staged the save", "A3 self-preserving"],
                        "confidence": 0.33,
                    },
                    "public_speech": "Convenient that A3 is still alive and leading the charge. Maybe the doctor staged a fake save. Think twice before handing wolves the win.",
                },
            ],
            "voting": {
                "public_summary": "With one wolf left, town focuses on A2 after the blocked night kill.",
                "prompts": {
                    "A1": {
                        "private_thought": {
                            "tie_break_preference": ["A2", "A3", "A6"],
                            "heuristics": ["Follow the most consistent story"],
                            "confidence": 0.82,
                        },
                        "options": ["A2", "A3", "A6"],
                    },
                    "A2": {
                        "private_thought": {
                            "tie_break_preference": ["A3", "A6", "A1"],
                            "heuristics": ["Vote the accuser to survive"],
                            "confidence": 0.44,
                        },
                        "options": ["A1", "A3", "A6"],
                    },
                    "A3": {
                        "private_thought": {
                            "tie_break_preference": ["A2", "A1", "A6"],
                            "heuristics": ["Eliminate the last confirmed wolf"],
                            "confidence": 0.97,
                        },
                        "options": ["A1", "A2", "A6"],
                    },
                    "A6": {
                        "private_thought": {
                            "tie_break_preference": ["A2", "A1", "A3"],
                            "heuristics": ["Support the detective-aligned push"],
                            "confidence": 0.9,
                        },
                        "options": ["A1", "A2", "A3"],
                    },
                },
                "responses": {
                    "A1": {"vote": "A2", "reason": "Everything points at A2 now; ending it here."},
                    "A2": {"vote": "A3", "reason": "They’re manipulating everyone and dodging accountability."},
                    "A3": {"vote": "A2", "reason": "Final wolf; behaviour and inspections agree."},
                    "A6": {"vote": "A2", "reason": "Backing the consistent case—we eliminate the last wolf."},
                },
                "eliminated": {
                    "player_id": "A2",
                    "role": "werewolf",
                    "alignment": "wolves",
                    "day_number": 2,
                },
                "private_reactions": {
                    "A3": "Mission accomplished without claiming outright. Town should celebrate this clean win.",
                    "A6": "Protection choices paid off—happy to see the plan succeed.",
                },
            },
            "end_of_day_summary": {
                "public_announcement": "A2 was eliminated and revealed to be a werewolf. The town claims victory!",
            },
        },
    ],
    "final_result": {
        "winning_side": "town",
        "reason": "Both werewolves were eliminated by Day 2.",
        "survivors": [
            {"player_id": "A1", "role": "peasant"},
            {"player_id": "A3", "role": "detective"},
            {"player_id": "A6", "role": "doctor"},
        ],
        "elimination_order": [
            {"phase": "night", "index": 1, "player_id": "A4", "role": "peasant"},
            {"phase": "day", "index": 1, "player_id": "A5", "role": "werewolf"},
            {"phase": "day", "index": 2, "player_id": "A2", "role": "werewolf"},
        ],
    },
}
