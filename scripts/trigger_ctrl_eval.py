import requests
import sys
import json
import time

def main():
    controller_url = "http://localhost:8010"
    
    # 1. Get Agent ID
    print(f"Querying controller at {controller_url}/agents...")
    try:
        resp = requests.get(f"{controller_url}/agents")
        agents = resp.json()
    except Exception as e:
        print(f"Failed to connect to controller: {e}")
        return

    if not agents:
        print("No agents found managed by the controller. Is the green agent running?")
        return

    # Pick the first running agent
    agent_id = None
    for aid, info in agents.items():
        if info['state'] == 'running':
            agent_id = aid
            break
    
    if not agent_id:
        print("Found agents but none are in 'running' state yet. Please wait a moment.")
        print(json.dumps(agents, indent=2))
        return

    print(f"Found running green agent: {agent_id}")
    
    # 2. Construct Proxy URL
    # The controller proxies requests via /to_agent/{agent_id}
    # The green agent mounts the referee at /werewolf
    # So the endpoint is /to_agent/{agent_id}/werewolf/tasks/werewolf_match
    
    endpoint = f"{controller_url}/to_agent/{agent_id}/werewolf/tasks/werewolf_match"
    
    # 3. Send Task
    white_url = "http://localhost:9002" # Assuming one white agent on 9002
    
    payload = {
        "players": [
            {"id": "A1", "name": "A1", "alias": "A1", "url": white_url},
            {"id": "A2", "name": "A2", "alias": "A2", "url": white_url},
            {"id": "A3", "name": "A3", "alias": "A3", "url": white_url},
            {"id": "A4", "name": "A4", "alias": "A4", "url": white_url},
            {"id": "A5", "name": "A5", "alias": "A5", "url": white_url},
            {"id": "A6", "name": "A6", "alias": "A6", "url": white_url},
        ],
        "seed": 20241013,
        "config": {
            "roles": ["werewolf","werewolf","detective","doctor","peasant","peasant"],
            "max_words_day_talk": 120,
            "json_only_responses": True,
            "uniform_token_budget_per_turn": 256,
        }
    }
    
    print(f"Sending task to {endpoint}...")
    try:
        resp = requests.post(endpoint, json=payload)
        print(f"Response status: {resp.status_code}")
        try:
            print(json.dumps(resp.json(), indent=2))
        except:
            print(resp.text)
    except Exception as e:
        print(f"Failed to send task: {e}")

if __name__ == "__main__":
    main()
