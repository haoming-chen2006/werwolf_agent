#!/usr/bin/env python3
"""Send a demo MatchRequest to the mounted referee endpoint on the green agent.

Usage:
  python scripts/send_demo_task_to_referee.py http://localhost:9001

The script POSTs to `/werewolf/tasks/werewolf_match` and prints the returned Assessment.
"""
import sys
import json
import requests


def make_demo_payload(white_url: str = "http://localhost:9002/"):
    players = []
    # Use demo ids similar to DEMO_SCENARIO
    ids = ["A1","A2","A3","A4","A5","A6"]
    for pid in ids:
        players.append({
            "id": pid,
            "alias": pid,
            "url": white_url,
        })

    payload = {
        "players": players,
        "seed": 20241013,
        "config": {
            "roles": ["werewolf","werewolf","detective","doctor","peasant","peasant"],
            "max_words_day_talk": 120,
            "json_only_responses": True,
            "uniform_token_budget_per_turn": 256,
        }
    }
    return payload


def main():
    if len(sys.argv) < 2:
        print("Usage: scripts/send_demo_task_to_referee.py <green_base_url> [white_base_url]")
        sys.exit(1)
    green_url = sys.argv[1].rstrip("/")
    white_url = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:9002/"

    endpoint = f"{green_url}/werewolf/tasks/werewolf_match"
    payload = make_demo_payload(white_url)
    print(f"POST {endpoint} with payload:\n{json.dumps(payload, indent=2)}")
    resp = requests.post(endpoint, json=payload, timeout=300)
    try:
        print("Response status:", resp.status_code)
        print(json.dumps(resp.json(), indent=2))
    except Exception:
        print("Non-JSON response:\n", resp.text)


if __name__ == '__main__':
    main()
