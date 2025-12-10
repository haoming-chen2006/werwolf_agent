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
    ```

3.  **Activate the environment**:
    ```bash
    source .venv/bin/activate
    ```

4.  **Environment Configuration**:
    Create a `.env` file in the root directory with your specific configuration.
    ```bash
    ````markdown
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
        ```

    3.  **Activate the environment**:
        ```bash
        source .venv/bin/activate
        ```

    4.  **Environment Configuration**:
        Create a `.env` file in the root directory with your specific configuration.
        ```bash
        touch .env
        # Add your environment variables to .env
        ```

    Run a quick local test:
    python main.py launch


    ## Integration with AgentBeats

    ## Quick Start (AgentBeats Integration)

    Run each of these in a separate terminal from the `werewolf_bench` directory.

    ### 1. Start Tunnel
    Exposes `green.werwolfs.org` and `white.werwolfs.org`.
    ```bash
    # Ensure both domains are routed:
    # cloudflared tunnel route dns tau green.werwolfs.org
    # cloudflared tunnel route dns tau white.werwolfs.org

    cloudflared tunnel --config config.yml run tau
    ```

    ### 2. Start Green Agent (Controller)
    ```bash
    source .venv/bin/activate
    HTTPS_ENABLED=true CLOUDRUN_HOST=green.werwolfs.org ROLE=green agentbeats run_ctrl
    ```

    ### 3. Start White Agent (Player)
    ```bash
    source .venv/bin/activate
    # Explicitly set AGENT_URL so the agent card reports the correct public address
    ROLE=white AGENT_PORT=9002 AGENT_URL=https://white.werwolfs.org python main.py run
    ```

    ### 4. Trigger Assessment
    ```bash
    source .venv/bin/activate
    python scripts/trigger_ctrl_eval.py
    ```

    ## Registering on AgentBeats

    1.  **Green Agent:** Register with URL `https://green.werwolfs.org`.
        *   This is your Controller. You can view logs and manage agents here.
    2.  **White Agent:** Register with URL `https://white.werwolfs.org`.
        *   This is the Player agent. It will redirect `/info` to its agent card.

    ```bash
    source .venv/bin/activate
    python scripts/trigger_ctrl_eval.py
    ```

    ---

    ## Local Development (No Tunnel)

    For quick local testing without AgentBeats integration:

    ```bash
    # Launch everything (Green + 6 White Agents) automatically
    python main.py launch
    ```

    **Repository Status & Notes**

    - **Structure:**
    	- `src/green_agent/`: green (assessment) agent implementation and A2A server.
    	- `src/white_agent/`: white (target) agent implementation and local FastAPI endpoints mounted under `/agent`.
    	- `src/werewolf/`: core werewolf assessment logic (game manager, models, rules, referee endpoints).
    	- `scripts/`: helper scripts (e.g. `send_demo_task_to_referee.py`).
    	- `.venv/`: recommended virtualenv (used during development).

    - **Recent changes (migration & fixes):**
    	- `src/green_agent/compat.py` added — small adapter replacing the minimal `tau_bench` API used by the green agent.
    	- `src/green_agent/agent.py` updated to use `WerewolfGreenAgentExecutor`, to default `AgentCard.url` when `AGENT_URL` is unset, and to handle both pydantic and dict `info` objects from envs.
    	- `src/green_agent/agent.py` mounts the werewolf FastAPI referee app at `/werewolf` when available.
    	- `src/white_agent/agent.py` now defaults the white `AgentCard.url` to `http://{host}:{port}` when `AGENT_URL` is unset so it can start locally.
    	- `src/werewolf/game_manager.py` augmented with prints to show night/day prompts, responses and votes for clearer stdout logs.
    	- `scripts/send_demo_task_to_referee.py` added to POST a demo `MatchRequest` to the mounted referee endpoint and print the returned `Assessment`.

    **How to run (local demo)**

    - Ensure you have followed the [Installation & Setup](#installation--setup) steps above.

    - Activate the environment:
    ```bash
    source .venv/bin/activate
    ```
    - Start green agent (controller-managed run) — this command is the one you use frequently:
    ```bash
    uv pip install --upgrade agentbeats
    ```
    - Or launch both agents and run a local demo (uses `launcher.launch_evaluation`):
    ```bash
    python main.py launch
    ```

    ````
