import asyncio
import httpx
import time
import subprocess
import sys
import os

# Configuration
GREEN_AGENT_URL = "http://localhost:8001"
WHITE_AGENTS_START_PORT = 8011
NUM_PLAYERS = 5

async def run_integration_test():
    print("Starting Integration Test...")
    
    # 1. Check if Green Agent is running
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{GREEN_AGENT_URL}/health")
            if resp.status_code != 200:
                print("Green Agent not running or unhealthy.")
                return
            print("Green Agent is healthy.")
        except Exception as e:
            print(f"Could not connect to Green Agent: {e}")
            return

    # 2. Check White Agents
    for i in range(1, NUM_PLAYERS + 1):
        port = WHITE_AGENTS_START_PORT + i - 1
        url = f"http://localhost:{port}"
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(f"{url}/health")
                if resp.status_code != 200:
                    print(f"White Agent {i} at {url} not healthy.")
                    return
            except:
                print(f"White Agent {i} at {url} not reachable.")
                return
    print(f"All {NUM_PLAYERS} White Agents are healthy.")

    # 3. Construct Match Request
    players = []
    for i in range(1, NUM_PLAYERS + 1):
        port = WHITE_AGENTS_START_PORT + i - 1
        players.append({
            "id": f"player_{i}",
            "name": f"White Agent {i}",
            "url": f"http://localhost:{port}",
            "alias": f"Agent {i}",
            "provider": "mock",
            "model": "heuristic"
        })

    payload = {
        "players": players,
        "seed": 12345,
        "config": {
            "max_words_day_talk": 50
        }
    }

    # 4. Send Match Request
    print("Sending Match Request to Green Agent...")
    start_time = time.time()
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp = await client.post(f"{GREEN_AGENT_URL}/tasks/werewolf_match", json=payload)
            if resp.status_code == 200:
                data = resp.json()
                print("\nMatch Completed Successfully!")
                print(f"Duration: {time.time() - start_time:.2f}s")
                print(f"Winner: {data['record']['final_result']['winning_side']}")
                print(f"Game ID: {data['record']['game_id']}")
                print(f"Total Phases: {len(data['record']['phases'])}")
            else:
                print(f"Match Failed: {resp.status_code}")
                print(resp.text)
        except Exception as e:
            print(f"Request failed: {e}")

if __name__ == "__main__":
    asyncio.run(run_integration_test())
