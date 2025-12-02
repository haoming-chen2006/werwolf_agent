"""Launcher module orchestrating local and remote Werewolf games."""

import asyncio
import json
import multiprocessing
from typing import Dict, List

import httpx

from src.green_agent.agent import start_green_agent
from src.white_agent.agent import start_white_agent


async def _wait_agent_ready(url: str, timeout: float = 15.0) -> bool:
    deadline = asyncio.get_event_loop().time() + timeout
    async with httpx.AsyncClient() as client:
        while asyncio.get_event_loop().time() < deadline:
            try:
                resp = await client.get(f"{url}/health", timeout=2.0)
                if resp.status_code == 200:
                    return True
            except Exception:
                await asyncio.sleep(0.5)
            else:
                await asyncio.sleep(0.5)
    return False


def _build_default_players(white_url: str) -> List[Dict[str, str]]:
    return [
        {"id": f"player_{i}", "name": f"Player {i}", "url": white_url}
        for i in range(1, 7)
    ]


async def _run_match(green_url: str, white_url: str) -> Dict:
    payload = {
        "players": _build_default_players(white_url),
        "config": {
            "max_nights": 5,
            "public_logging": True,
        },
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{green_url}/tasks/werewolf_match", json=payload, timeout=120.0
        )
        response.raise_for_status()
        return response.json()


async def launch_evaluation() -> Dict:
    print("Launching green agent...")
    green_address = ("localhost", 8001)
    green_url = f"http://{green_address[0]}:{green_address[1]}"
    p_green = multiprocessing.Process(
        target=start_green_agent, args=(*green_address,)
    )
    p_green.start()
    assert await _wait_agent_ready(green_url), "Green agent not ready in time"
    print("Green agent is ready.")

    print("Launching white agent...")
    white_address = ("localhost", 8011)
    white_url = f"http://{white_address[0]}:{white_address[1]}"
    p_white = multiprocessing.Process(
        target=start_white_agent, args=(*white_address,)
    )
    p_white.start()
    assert await _wait_agent_ready(white_url), "White agent not ready in time"
    print("White agent is ready.")

    try:
        print("Starting local match...")
        result = await _run_match(green_url, white_url)
        print("Match complete.")
        print(json.dumps(result.get("metrics", {}), indent=2))
        return result
    finally:
        print("Terminating agents...")
        p_green.terminate()
        p_green.join()
        p_white.terminate()
        p_white.join()
        print("Agents terminated.")


async def launch_remote_evaluation(green_url: str, white_url: str) -> Dict:
    print(f"Using remote green agent at {green_url}")
    print(f"Using remote white agent at {white_url}")
    return await _run_match(green_url, white_url)
