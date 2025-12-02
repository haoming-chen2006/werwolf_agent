Below is a clean, complete, production-ready setup guide you can paste directly into a .md file.

It covers:

🟩 How to run a Green Assessor Agent locally

🌐 How to expose it remotely through Cloudflare

🔁 What must run in each of the two terminals

🔧 How to reset / erase bad GitHub links when re-registering on AgentBeats

📝 Fully formatted Markdown, ready to save as remote_green_agent_setup.md

🟩 Remote Green Agent Setup Guide

AgentBeats v2 • Cloudflare Tunnel • Remote Hosting Guide

This document explains how to run a Green (Assessor) Agent locally and expose it to AgentBeats through a Cloudflare tunnel. It supports both local testing and remote access.


0. (Most Important) Sturcture
green_agent, white_agent and launcher are the must needed files

1. Requirements
Installed tools

python3 / virtual environment

cloudflared (Cloudflare CLI)

Cloudflare account + a domain (e.g., werwolfs.org)

agentbeats Python package

Repo

This guide assumes your repo has the Tau-Bench example structure:

agentify-example-tau-bench/
├── src/
│   ├── green_agent/
│   ├── white_agent/
│   ├── launcher.py
│   └── ...
└── run.sh

2. Cloudflare Tunnel Setup
2.1 Create a new Tunnel

In Cloudflare Zero Trust dashboard:

Networks → Tunnels → Create Tunnel → Cloudflared

Name your tunnel (e.g., tau).

After creation, Cloudflare gives you a run token:

cloudflared tunnel run --token eyJhbGciOi...


This is what you will use to start the tunnel.

2.2 Create a Public Hostname

Go to:

Tunnels → your tunnel (tau) → Public Hostnames

Click Add a public hostname:

Field	Value
Subdomain	green
Domain	werwolfs.org
Service Type	HTTP
URL	http://127.0.0.1:8010

Click Save.

Cloudflare will automatically create:

green.werwolfs.org → tunnel → localhost:8010

3. Two-Terminal Runtime Setup

You must run two terminals, always in parallel:

⭐ Terminal 1 — Start Cloudflare Tunnel
cloudflared tunnel run --token <your-long-token>


You should see:

Registered tunnel connection...
Updated to new configuration config=...


Keep this running.

⭐ Terminal 2 — Start the Agent Controller

Navigate to your repo:

cd agentify-example-tau-bench
source .venv/bin/activate   # optional


Run the controller:

HTTPS_ENABLED=true \
CLOUDRUN_HOST=green.werwolfs.org \
ROLE=green \
agentbeats run_ctrl


If successful, this starts:

The controller server on port 8010

The green agent process

The agent card endpoint at:

https://green.werwolfs.org/to_agent/<ID>/.well-known/agent-card.json


Keep this running.

4. Verify Remote Access

Open your browser:

4.1 Controller page
https://green.werwolfs.org/info


You should see the orange Agent Controller UI.

4.2 Agent Card

Click the link under Agent Instances:

https://green.werwolfs.org/to_agent/<ID>/.well-known/agent-card.json


You should see JSON (not HTML).

If both succeed → remote hosting is fully working.

5. Registering on AgentBeats

Go to:

https://v2.agentbeats.org
 → Add Agent

Fill in:

Field	Value
Name	tau
Deploy Type	Remote
Is Assessor (Green Agent)`	✅ Checked
Controller URL	https://green.werwolfs.org
Git URL	your GitHub repo
Branch	main

Click Create Agent.

Then scroll down and press Check Agent.

You should see:

Controller reachable: Yes

Agent count: 1

Agent Card Loaded: ✔ No yellow warning

6. Switching Between Local Mode and Remote Mode

You can run your green agent in two different modes:

🏡 Local Only (no Cloudflare)

Useful for debugging:

ROLE=green \
CLOUDRUN_HOST=localhost \
HTTPS_ENABLED=false \
agentbeats run_ctrl


Access page:

http://localhost:8010/info

🌐 Remote Mode (Cloudflare)

Use:

HTTPS_ENABLED=true \
CLOUDRUN_HOST=green.werwolfs.org \
ROLE=green \
agentbeats run_ctrl


At the same time, run the Cloudflare tunnel:

cloudflared tunnel run --token <TOKEN>

7. If GitHub repo is stuck / wrong repo is attached

AgentBeats sometimes caches Git repo links.

To erase a bad repo link:

Option A — Delete the Agent

On the agent page:

Delete Agent

Create a new one with correct Git URL.

Option B — Replace the Git URL

Go to the agent’s page

Click Edit

Replace Git URL + Branch

Save

Option C — Start completely fresh

If links are deeply cached:

Delete agent

Rename your repo (optional)

Create a new agent with the new URL

8. Final Runtime Summary (Copy-Paste Cheat Sheet)
# Terminal 1 — Cloudflare Tunnel
cloudflared tunnel run --token <TOKEN>

# Terminal 2 — Green Agent Controller
cd agentify-example-tau-bench
source .venv/bin/activate   # optional
HTTPS_ENABLED=true \
CLOUDRUN_HOST=green.werwolfs.org \
ROLE=green \
agentbeats run_ctrl


Visit:

Controller: https://green.werwolfs.org/info

Agent Card: https://green.werwolfs.org/to_agent/
<ID>/.well-known/agent-card.json

Register on AgentBeats:

Controller URL: https://green.werwolfs.org