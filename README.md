# Agentify Example: Werewolf

This repository contains an example of agentifying a Werewolf assessment harness. The local assessment logic lives in `src/werewolf` and the green/white agent examples demonstrate how to run the assessor and target agents using the A2A/MCP pattern.

## Project Structure

```
src/
├── green_agent/    # Assessment manager agent
├── white_agent/    # Target agent being tested
└── launcher.py     # Evaluation coordinator
```

## Installation & Setup

This project uses `uv` for dependency management.

1.  **Install uv** (if not already installed):
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

2.  **Sync dependencies**:
    This will create the virtual environment and install all locked dependencies.
    ```bash
    uv sync
    -- have your own .env file created and registered with OPENAI_API_KEY
    ```

3.  **Activate the environment**:
    ```bash
    source .venv/bin/activate
    ```

4.  **Start Agents and see Assessment!**:

    Run a quick session with:
   ```bash
    python main.py launch
     ```


    ## Integration with AgentBeats

## Quick Start (AgentBeats Integration)

Run each of these in a separate terminal from the `werwolf_agent` directory.

### 1. One-Time Setup: Create White Agent Folders

For each white agent you want to run, create a controller folder with a `run.sh` script:

```bash
# Create folders for N white agents (e.g., 7 agents)
for i in 1 2 3 4 5 6 7; do
    mkdir -p white_agent_ctrl_$i
    cat > white_agent_ctrl_$i/run.sh << 'EOF'
#!/bin/bash
cd /path/to/werwolf_agent  # Update this path!
source .venv/bin/activate
AGENT_PORT=${AGENT_PORT:-9002} python main.py white
EOF
    chmod +x white_agent_ctrl_$i/run.sh
done
```

### 2. One-Time Setup: DNS Routes

Set up Cloudflare tunnel routes for your agents (replace with your own domain):

```bash
# Green agent (controller)
cloudflared tunnel route dns tau green.werwolfs.org

# White agents (players) - add as many as needed
cloudflared tunnel route dns tau white1.werwolfs.org
cloudflared tunnel route dns tau white2.werwolfs.org
cloudflared tunnel route dns tau white3.werwolfs.org
# ... up to whiteN.werwolfs.org
```

Update `config.yml` to include ingress rules for each hostname.

### 3. Start Tunnel

```bash
cloudflared tunnel --config config.yml run tau
```

### 4. Start Green Agent (Controller)

```bash
source .venv/bin/activate
HTTPS_ENABLED=true CLOUDRUN_HOST=green.werwolfs.org agentbeats run_ctrl
```

### 5. Start White Agents (Players)

Start each white agent in a separate terminal. Roles are defined in `src/agent_config.py`.

```bash
# White Agent 1 (port 8011)
cd white_agent_ctrl_1
source ../.venv/bin/activate
PORT=8011 HTTPS_ENABLED=true CLOUDRUN_HOST=white1.werwolfs.org agentbeats run_ctrl

    ## Registering on AgentBeats

    1.  **Green Agent:** Register with URL `https://green.werwolfs.org`.
        *   This is your Controller. You can view logs and manage agents here.
    2.  **White Agent:** Register with URL `https://white.werwolfs.org`.
        *   This is the Player agent. It will redirect `/info` to its agent card.

    ```bash
    source .venv/bin/activate
    python scripts/trigger_ctrl_eval.py
    ```

## Test Scripts

The project includes several test and utility scripts for development and demonstration purposes:

### `populate_dummy_eval_jsons.py`
Generates dummy evaluation JSON files for testing the evaluation system. Creates 25 sample game records in `Game_History/Evals/` with randomized player data including:
- Multiple AI models (GPT-4o, Claude, Gemini, Llama, etc.)
- Various roles (werewolf, villager, detective, doctor)
- Randomized scores for sabotage, manipulation, resistance, and decision quality

```bash
python populate_dummy_eval_jsons.py
```

### `populate_dummy_eval_stats.py`
Populates the evaluation statistics CSV files with dummy data for multiple AI models. Initializes and fills:
- `model_overall_stats.csv` - Overall win/loss records and ELO ratings
- `model_role_stats.csv` - Per-role performance statistics
- `matchup_stats.csv` - Head-to-head model comparisons
- `model_advanced_stats.csv` - Advanced metrics like voting precision

```bash
python populate_dummy_eval_stats.py
```

### `auto_sabotage_test.py`
Tests the auto-sabotage detection system by creating a game scenario where a villager deliberately sabotages their own team. The test simulates:
- A villager falsely claiming to be a wolf
- Voting against confirmed town members
- Contradicting detective findings

This validates that the evaluation system correctly identifies and scores self-sabotaging behavior.

```bash
python auto_sabotage_test.py
```

### `elo_demonstration.py`
Demonstrates the ELO rating system by simulating multiple games between different AI models. Creates test scenarios including:
- Wolf team victories (wolves successfully eliminate villagers)
- Villager team victories (town correctly identifies and eliminates wolves)
- Shows how ELO ratings update based on game outcomes across different models (GPT-4o, Claude, Gemini, Llama)

```bash
python elo_demonstration.py
```
