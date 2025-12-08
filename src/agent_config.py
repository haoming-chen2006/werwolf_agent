"""Simple Python config page for agent launch.

Defines the white agents (6 by default) and green agent settings.
This file will raise an error if `OPENAI_API_KEY` is not present in the
provided .env (default: `/Users/haoming/mafia/.env`).

Edit this file to change per-agent `name`, `provider`, `model`, and `role`.
"""
from dataclasses import dataclass
from typing import List
import os
from dotenv import load_dotenv

# Load the global .env file that holds API credentials for all agents.
# Default path used by the team: /Users/haoming/mafia/.env
GLOBAL_ENV_PATH = os.environ.get("MAFIA_GLOBAL_ENV", "/Users/haoming/mafia/.env")
load_dotenv(GLOBAL_ENV_PATH)

MODEL_PRESETS = {
    "gpt-4o": ("openai", "gpt-4o"),
    "gpt-4-turbo": ("openai", "gpt-4-turbo"),
    "gpt-3.5": ("openai", "gpt-3.5-turbo"),
    "gpt-4": ("openai", "gpt-4"),
    # Example placeholders for future/other models
    "gpt-5": ("openai", "gpt-5-preview"), 
    "claude-3-opus": ("anthropic", "claude-3-opus-20240229"),
    "local-llama": ("local", "llama-3-70b"),
}

def get_model_config(config_name: str):
    """Selects the provider and model based on a preset name.
    
    Add new model presets here to easily switch between them.
    """
    # Default to openai if unknown, treating config_name as model name
    return MODEL_PRESETS.get(config_name, ("openai", config_name))


# --- Configuration Selection ---
# Change this value or set WEREWOLF_MODEL_CONFIG env var to switch models
ACTIVE_CONFIG_NAME = os.environ.get("WEREWOLF_MODEL_CONFIG", "gpt-4o")

DEFAULT_PROVIDER, DEFAULT_MODEL = get_model_config(ACTIVE_CONFIG_NAME)

# Allow explicit overrides via env vars
if os.environ.get("AGENT_PROVIDER"):
    DEFAULT_PROVIDER = os.environ["AGENT_PROVIDER"]
if os.environ.get("AGENT_MODEL"):
    DEFAULT_MODEL = os.environ["AGENT_MODEL"]

print(f"Agent Config: Defaulting to provider='{DEFAULT_PROVIDER}', model='{DEFAULT_MODEL}'")


@dataclass
class AgentSpec:
    name: str
    role: str = "villager"  # one of: werewolf, detective, doctor, villager
    model: str = None
    provider: str = None

    def __post_init__(self):
        # 1. Resolve preset if 'model' matches a known configuration key
        if self.model in MODEL_PRESETS:
            preset_provider, preset_model = MODEL_PRESETS[self.model]
            # Only override provider if not explicitly set
            if self.provider is None:
                self.provider = preset_provider
            self.model = preset_model
        
        # 2. Apply defaults if still unset
        if self.model is None:
            self.model = DEFAULT_MODEL
        if self.provider is None:
            self.provider = DEFAULT_PROVIDER


# Default white agents: 7 entries. Change names/roles/providers here.
AGENTS: List[AgentSpec] = [
    AgentSpec(name="Alice", role="doctor", model="gpt-4o"),
    AgentSpec(name="Bob", role="werewolf", model="gpt-4-turbo"),
    AgentSpec(name="Charlie", role="villager", model="gpt-4o"),
    AgentSpec(name="Dave", role="villager", model="gpt-4"),
    AgentSpec(name="Eve", role="villager", model="gpt-3.5"),
    AgentSpec(name="Frank", role="detective", model="gpt-4-turbo"),
    AgentSpec(name="Grace", role="werewolf", model="gpt-4o"),
]

# Green agent spec (controller)
GREEN_AGENT = AgentSpec(name="green_controller", provider="local", model="controller", role="green")


def ensure_api_key() -> str:
    """Ensure OPENAI_API_KEY exists in the loaded env. Returns the key or raises."""
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise EnvironmentError(
            f"OPENAI_API_KEY not found. Please add it to {GLOBAL_ENV_PATH} or set OPENAI_API_KEY in the environment."
        )
    return key


if __name__ == "__main__":
    print("Agent config preview:")
    print("Global env path:", GLOBAL_ENV_PATH)
    print("OPENAI_API_KEY present:", "yes" if os.environ.get("OPENAI_API_KEY") else "NO")
    for a in AGENTS:
        print(f"- {a.name}: role={a.role} provider={a.provider} model={a.model}")
