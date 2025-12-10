# White Agent Progress

## Architecture Overview

The white agent supports two modes controlled by `WHITE_AGENT_MODE` environment variable:

### Commands
- **`python main.py launch`** - ADVANCED mode (Planner → Investigation → Decision)
- **`python main.py launch_eval`** - VANILLA mode (simple LLM calls)

### ADVANCED Mode Architecture (default)
```
┌─────────────────────────────────────────────────────────────────────┐
│                        ADVANCED MODE FLOW                          │
├─────────────────────────────────────────────────────────────────────┤
│  1. PLANNER                                                         │
│     - Reads Green_Record.txt from file_location                     │
│     - Creates one-paragraph strategic plan                          │
│                                                                     │
│  2. SPECIAL SESSIONS (parallel investigations)                      │
│     - Each target gets investigated via file tools                  │
│     - Returns JSON: {target, suspicion_level, reasoning, evidence}  │
│                                                                     │
│  3. FINAL DECISION MAKER                                            │
│     - Receives: planner message + all investigation JSONs           │
│     - Includes goal/role reminder                                   │
│     - Makes final decision (action/vote/speech)                     │
│                                                                     │
│  4. VALIDATOR (auto-pass, logged only)                              │
└─────────────────────────────────────────────────────────────────────┘
```

### VANILLA Mode Architecture
```
┌─────────────────────────────────────────────────────────────────────┐
│                        VANILLA MODE FLOW                           │
├─────────────────────────────────────────────────────────────────────┤
│  Single LLM call with basic prompt                                  │
│  - No file reading                                                  │
│  - No investigation sessions                                        │
│  - Direct decision from prompt context only                         │
└─────────────────────────────────────────────────────────────────────┘
```

The system has been refactored to separate the **Game Engine (Green Agent)** from the **Player Logic (White Agent)**, optimizing for context window efficiency and structured reasoning.

### Core Components

*   **Green Agent (`src/werewolf/game_manager.py`):**
    *   Acts as the Orchestrator/Referee.
    *   Manages game state, phases, and rules.
    *   **Key Change:** No longer inlines massive history text into prompts. Instead, it sends **file paths** (pointers) to the White Agent.
    *   Generates lightweight JSON payloads containing:
        *   Current Phase/State.
        *   Available Options (Vote targets, Action targets).
        *   `file_location`: Base path to the current game's record.
        *   Specific paths: `public_history`, `public_speech_history`, `private_thoughts_history`.

*   **White Agent (`src/werewolf/agent_white.py`):**
    *   Acts as the Player (AI).
    *   **Stateless-ish:** Receives a request, processes it, returns a decision.
    *   **Planner-Guided:** Uses a "Planner" step to generate a one-paragraph strategic plan based on `Green_Record.txt`.
    *   **Tool-Enabled:** Uses "Special Sessions" to actively *read* the files provided by the Green Agent using `_read_history_files()` parser.
    *   **Final Decision Maker:** Aggregates planner goal + all investigation results to make the final decision.

## 2. File Structure Logic

### `src/werewolf/`

*   **`agent_white.py`**: **(The Brain)**
    *   **Endpoints:** `/discussion`, `/vote`, `/night_action`.
    *   **`_read_history_files(prompt)`**: Parser that reads all relevant history files:
        *   `Green_Record.txt` - Full game record for planner context
        *   `Public_History.json` - Game events and speeches
        *   `Private_Thoughts.json` - Player's own private thoughts
        *   `Public_Speech.json` - Player's own speeches
        *   All other players' `Public_Speech.json` files
    *   **`_make_planner_statement(prompt, history_data)`**: Calls LLM to generate a one-paragraph strategy plan based on `Green_Record.txt`.
    *   **`_run_special_session(planner_stmt, prompt, target, history_data)`**: Investigates a specific target player and returns JSON investigation result.
    *   **`_run_multi_target_investigation(...)`**: Runs special sessions for multiple targets.
    *   **`_make_final_decision(...)`**: Takes planner + investigation results to make final decision.
    *   **Validator/Reflector**: Auto-passes (logged but always passes).

*   **`game_manager.py`**: **(The Engine)**
    *   Updated to construct `DayVotePrompt`, `NightRolePrompt`, etc., with `history_text=None` (or commented out) and populated `file_location` fields.

*   **`models.py`**: **(The Interface)**
    *   Pydantic models (`DayVotePrompt`, `NightRolePrompt`) updated to accept `file_location` and optional string paths for history fields.

*   **`night_prompts.py`**:
    *   Helper functions to generate night phase prompts.
    *   Refactored to remove inlined history text.

*   **`logging_manager.py`**:
    *   Handles writing the raw game logs (`Record_game_...`) that the White Agent reads.

### File Structure in `Game_History/Record/Record_game_xxx/`:
```
Green_Record.txt           # Full game record for planner
Public_History.json        # All public events and speeches
Player_p1/
    Info.json              # Player info (name, role, model)
    Private_Thoughts.json  # Player's private thoughts per turn
    Public_Speech.json     # Player's public speeches per turn
    History.txt            # Human-readable history for this player
    white_history.jsonl    # White agent's internal reasoning log
Player_p2/
    ...
```

## 3. Current Progress Status

### ✅ Completed
1.  **Architecture Refactor:** Successfully transitioned from "Push" (sending full history) to "Pull" (sending file paths).
2.  **Planner Implementation:** The White Agent now generates a strategic one-paragraph "Planner Statement" before acting, using `Green_Record.txt` for full game context.
3.  **History Parser (`_read_history_files`):** Implemented robust file parsing that reads:
    *   `Green_Record.txt` - Full game record
    *   `Public_History.json` - Public events
    *   `Private_Thoughts.json` - Own private thoughts
    *   `Public_Speech.json` - Own speeches
    *   All players' `Public_Speech.json` files
4.  **Special Session Logic:** The `_run_special_session` function:
    *   Takes a target player ID
    *   Uses parsed history data to analyze target
    *   Returns JSON investigation result with suspicion_updates
5.  **Multi-Target Investigation:** Implemented `_run_multi_target_investigation` to run special sessions for multiple players in parallel/sequential.
6.  **Final Decision Maker:** Implemented `_make_final_decision` that:
    *   Takes planner goal + all investigation results
    *   Aggregates suspicion scores
    *   Makes final vote/action decision
7.  **Simplified Discussion:** Discussion endpoint reads history with parser and generates speech directly (no special sessions/writer).
8.  **Validator/Reflector:** Auto-passes and logs "PASSED" status.
9.  **Crash Fixes:** Resolved `AttributeError` in `night_action` where `options` could be a list or a dictionary.
10. **Robust JSON Repair:** Implemented `_repair_json_with_llm` in the Green Agent.
11. **Sanitization:** Added input sanitization for `suspicion_updates` to prevent type errors.

### 🚧 Flow Summary

**Night Action / Vote:**
```
1. _read_history_files(prompt)  → Parse all history files
2. _make_planner_statement()    → Generate one-paragraph plan from Green_Record.txt
3. _run_multi_target_investigation() → Run special sessions for each target
   └── _run_special_session()   → Returns JSON investigation result per target
4. _make_final_decision()       → Aggregate results + make final decision
5. Log to white_history.jsonl
```

**Discussion:**
```
1. _read_history_files(prompt)  → Parse all history files
2. Generate speech directly     → No planner/special sessions
3. Log to white_history.jsonl
```

### 📝 Next Steps
1.  Test the new implementation end-to-end with a game run
2.  Monitor `white_history.jsonl` to verify special sessions are producing useful investigation JSONs
3.  Refine planner prompts based on actual game context
4.  Consider adding more sophisticated target selection for special sessions
