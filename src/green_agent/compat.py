from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

RESPOND_ACTION_NAME = "respond"


class Action(BaseModel):
    name: str
    kwargs: Dict[str, Any] = {}


@dataclass
class SolveResult:
    reward: float
    info: Dict[str, Any]
    messages: List[Any]
    total_cost: float = 0.0


class SimpleEnvResponse:
    def __init__(self, observation: str, reward: float = 0.0, info: Optional[Dict[str, Any]] = None, done: bool = False):
        self.observation = observation
        self.reward = reward
        self.info = info or {}
        self.done = done


class SimpleWerewolfEnv:
    """A tiny adapter that exposes the minimal API the green agent expects.

    It reads the `DEMO_SCENARIO` structure from the werewolf package and
    exposes `wiki`, `tools_info`, `reset(task_index)` and `step(action)`.
    This is intentionally small: it provides deterministic observations so
    the assessment flow can run locally for demos.
    """

    def __init__(self, demo_scenario: Dict[str, Any], task_index: int = 0):
        self.demo = demo_scenario
        self.task_index = task_index
        self.phase_index = 0
        self.wiki = f"Werewolf demo: {self.demo['game']['game_id']}"
        # No external tools in this demo
        self.tools_info: List[Dict[str, Any]] = []

    def reset(self, task_index: int = 0):
        self.task_index = task_index
        self.phase_index = 0
        phase = self.demo["phases"][self.phase_index]
        observation = json.dumps(phase, indent=2)
        # Return a lightweight object with .observation and .info
        class R:
            def __init__(self, observation):
                self.observation = observation
                self.info = {"task_index": task_index}

        return R(observation)

    def step(self, action: Action):
        # This env doesn't execute the action; it just advances the scenario
        self.phase_index += 1
        done = self.phase_index >= len(self.demo["phases"]) 
        if not done:
            phase = self.demo["phases"][self.phase_index]
            observation = json.dumps(phase, indent=2)
            reward = 0.0
            info = {"phase_index": self.phase_index}
        else:
            observation = json.dumps(self.demo.get("final_result", {}), indent=2)
            reward = 1.0 if self.demo.get("final_result", {}).get("winning_side") == "town" else 0.0
            info = {"final": True}

        return SimpleEnvResponse(observation=observation, reward=reward, info=info, done=done)


def get_env(env_name: str, user_strategy: str, user_model: str, task_split: str, user_provider: Optional[str], task_index: int = 0):
    """Return a SimpleWerewolfEnv built from `src.werewolf.DEMO_SCENARIO`.

    The signature matches the expected one used by the green agent so we can
    import it as a drop-in replacement for `tau_bench.envs.get_env`.
    """
    try:
        from src.werewolf.demo_script import DEMO_SCENARIO
    except Exception:
        # Fallback: empty demo
        DEMO_SCENARIO = {"game": {"game_id": "demo"}, "phases": [], "final_result": {}}

    return SimpleWerewolfEnv(DEMO_SCENARIO, task_index=task_index)
