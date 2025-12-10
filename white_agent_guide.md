1. Planner: single-sentence planning statement for each session

Goal: given the original game prompt + parsed SessionContext, generate a clear, focused, single-sentence “planning statement of purpose” for the current session.

Input (conceptual):

Original game prompt from the game engine (with phase, options, etc.)

SessionContext:

role (werewolf / detective / doctor / villager)

phase ("day" or "night")

mode (e.g. "discussion", "vote", "kill", "inspect")

day_number or night_number

alive_players

self_id

file_location for logs

Output:
A single string that states exactly what this session is for, in plain English.
No JSON, no tools, no list. Just one detailed sentence.

The planner must:

Infer what kind of module this session is (werewolf night / werewolf day / detective night / detective day / doctor day / villager day).

Describe what to focus on in this session:

Which players or patterns to analyze

What type of information to extract (e.g. find detective, evaluate votes, select kill target)

How this supports the role’s win condition

Examples of valid planner outputs:

Werewolf, Night 1, kill decision

Now your goal is to review the alive players' past speeches and vote patterns to identify the most likely detective or strongest town leader, then choose a kill target who weakens the village without exposing you or your wolf partners.

Werewolf, Day 2, discussion

Now your goal is to act like a concerned villager while subtly shifting suspicion onto safe scapegoats, protecting your wolf partner and building a plausible argument based on yesterday's votes and speeches.

Detective, Night 2, inspect decision

Now your goal is to inspect the player whose alignment, if revealed, would most change the future lynch dynamics, focusing on players who sit at the center of vote patterns and have ambiguous behavior.

Villager, Day 1, discussion

Now your goal is to use only public speeches and votes to build an initial suspicion ranking over all other players, asking pointed questions to those whose behavior seems inconsistent or opportunistic.

Doctor, Day 3, discussion

Now your goal is to quietly town-read the player you previously saved while analyzing how others reacted to the no-kill night, without hard-claiming doctor unless absolutely necessary.

Planner rule:
The planner must only produce this one-sentence planning statement. It does not call tools and does not output JSON.

2. Special tool-assisted sessions: recursive chain of thought with JSON and end_investigation -- the tools read_file and search_file are already implemented

Some sessions require deeper investigation over logs (e.g. finding detective, evaluating a specific player, inspecting vote patterns). For those, the agent runs a special tool-assisted session guided by the planner’s statement.

Key rules:

These sessions:

Take as input:

The planning statement from the planner.

The SessionContext. 

The file_location and any tool handles. (location of files, got form the prompt)

Are allowed to call parser/history tools to read:

public history

per-player public speech

per-player private thoughts (if available for the white agent)

past votes

metrics logs (e.g. centrality, early signals, persuasion metrics) if present

Run a recursive chain of thought: at each step, they can decide to fetch more data or to stop.

Parser/history tools are only called inside these special sessions.
Outside special sessions, the agent relies on the compact context and its internal reasoning.

Each step of a special session must return JSON with a fixed schema and a control flag:

2.1 JSON schema for special sessions

Every special session response must be a valid JSON object:

{
  "end_investigation": false,
  "session_type": "investigate_player", 
  "target_players": ["p3"],
  "reasoning": "Natural language chain-of-thought about what was read and why it matters.",
  "requested_tools": [
    {
      "tool_name": "read_public_speech",
      "player_id": "p3",
      "time_scope": "all_days"
    }
  ],
  "suspicion_updates": [
    {
      "player_id": "p3",
      "delta_suspicion": 0.15,
      "delta_trust": -0.10,
      "notes": "p3 jumped on every safe wagon and avoided pushing new suspects."
    }
  ],
  "intermediate_hypotheses": {
    "likely_detective_candidates": ["p4"],
    "likely_doctor_candidates": [],
    "likely_easy_mislynches": ["p6"]
  }
}


Fields:

end_investigation (bool)

false:

The agent wants to continue investigating.

The orchestrator may call tools as requested in requested_tools, then re-invoke the same special session with the new tool outputs.

true:

The agent is done investigating for this session and believes it has enough information.

The orchestrator stops calling this special session and passes the final JSON to the writer. -- should start multiple special session on multiple players if neccessary

session_type (string)

e.g. "investigate_player", "find_detective", "vote_pattern_analysis".

Helps label this investigation in logs.

target_players (list of player IDs)

Who this investigation is currently focusing on.

For "investigate_player", usually one player like ["p3"].

For "vote_pattern_analysis", this could be ["p1","p2","p3","p4","p5"].

reasoning (string)

Natural language chain of thought explaining:

What the agent just looked at (e.g. “Day 1 speeches from p3”)

How it interprets that behavior

How this affects suspicion / trust / role hypotheses.

This is private reasoning for logs and metrics, not shown directly in game.

requested_tools (list)

Optional list of tool calls the agent would like the orchestrator to perform before the next recursion step.

Example entries:

{
  "tool_name": "read_public_history",
  "player_id": null,
  "time_scope": "up_to_current_day"
}

{
  "tool_name": "read_player_votes",
  "player_id": "p3",
  "time_scope": "all_days"
}


If no tools are needed, this can be [] or omitted.

suspicion_updates (list)

Per-player incremental updates:

{
  "player_id": "p3",
  "delta_suspicion": 0.2,
  "delta_trust": -0.1,
  "notes": "p3 avoided voting a flipped wolf and stayed on low-risk wagons."
}


These are deltas; the global suspicion meter is updated externally.

intermediate_hypotheses (object)

Structured guesses for higher-level roles / tags:

likely_detective_candidates

likely_doctor_candidates

likely_easy_mislynches

likely_strong_town

Each key maps to a list of player IDs.

2.2 Recursive behavior

The special session proceeds as follows:

First call

Input:

Planner’s statement, e.g.:

“Now your goal is to investigate players to find possible detective because you are werewolf.”

SessionContext + current knowledge.

Agent:

Chooses an initial session_type (e.g. "find_detective").

Picks target_players to start examining.

Fills in requested_tools to fetch necessary logs.

Sets end_investigation to false if more data is needed.

Tool execution (outside the LLM)

Orchestrator reads requested_tools, calls the corresponding parser/history tools using file_location, and provides the results back to the agent.

Next recursion step

Agent receives:

Previous JSON

Tool outputs (e.g. specific speeches, vote history).

Agent:

Updates reasoning, suspicion_updates, and intermediate_hypotheses.

Either:

Requests more tools (end_investigation = false), or

Decides it has enough and sets end_investigation = true.

Termination

When end_investigation = true, the final JSON becomes the investigation result for this session.

The Writer uses this to update the suspicion model and choose actions.

2.3 Examples of special session outputs

Example 1: Werewolf trying to find detective

First step:

{
  "end_investigation": false,
  "session_type": "find_detective",
  "target_players": ["p3", "p4", "p6"],
  "reasoning": "I will start by checking which players drove the discussion on previous days and whether they pushed correct wagons or protected town.",
  "requested_tools": [
    {
      "tool_name": "read_public_speech",
      "player_id": "p3",
      "time_scope": "all_days"
    },
    {
      "tool_name": "read_public_speech",
      "player_id": "p4",
      "time_scope": "all_days"
    }
  ],
  "suspicion_updates": [],
  "intermediate_hypotheses": {
    "likely_detective_candidates": [],
    "likely_doctor_candidates": [],
    "likely_easy_mislynches": []
  }
}


After some tool-assisted steps, final step:

{
  "end_investigation": true,
  "session_type": "find_detective",
  "target_players": ["p4"],
  "reasoning": "p4 consistently started accurate pushes on wolves, backed off mislynch wagons, and avoided over-explaining reads, which matches typical detective behavior.",
  "requested_tools": [],
  "suspicion_updates": [
    {
      "player_id": "p4",
      "delta_suspicion": -0.3,
      "delta_trust": 0.5,
      "notes": "p4 is likely a power role (detective or strong town)."
    }
  ],
  "intermediate_hypotheses": {
    "likely_detective_candidates": ["p4"],
    "likely_doctor_candidates": [],
    "likely_easy_mislynches": ["p6"]
  }
}


Example 2: Villager investigating a single player

{
  "end_investigation": true,
  "session_type": "investigate_player",
  "target_players": ["p3"],
  "reasoning": "p3 jumped on every safe wagon late, rarely initiated accusations, and avoided voting the flipped wolf on Day 2 even when it was safe. This is classic opportunistic wolf behavior.",
  "requested_tools": [],
  "suspicion_updates": [
    {
      "player_id": "p3",
      "delta_suspicion": 0.6,
      "delta_trust": -0.4,
      "notes": "Opportunistic votes and lack of independent reads."
    }
  ],
  "intermediate_hypotheses": {
    "likely_detective_candidates": [],
    "likely_doctor_candidates": [],
    "likely_easy_mislynches": [],
    "likely_strong_town": []
  }
}

3. How planner and special sessions fit into the overall loop

For each game step:

Planner call

Input: original game prompt + SessionContext.

Output: 1-sentence planning statement (string).

Check if this session requires tools

Examples that do:

phase="day", mode="discussion" → run multiple investigate_player and find_detective sessions.

phase="night", mode="inspect" → run an investigation over potential inspect targets.

If yes, run one or more special tool-assisted sessions, each returning JSON and recursively calling tools until end_investigation = true.

Writer

Consumes:

Planner’s planning statement

All final special session JSONs

Global suspicion model

Produces:

Final game output:

Day discussion: { "thought": ..., "speech": ... }

Day vote: { "vote": "p3", "speech": "..." }

Night action: "p4" (kill / inspect / save target)

Reflector

Optionally checks:

Does this contradict our suspicion model?

For wolves: are we accidentally killing / voting our partner without strategy?

Requests a revision if needed.