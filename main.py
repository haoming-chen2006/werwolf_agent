"""CLI entry point for the Werewolf agentified demo."""

import asyncio
import typer
from pydantic_settings import BaseSettings

from src.green_agent.agent import start_green_agent
from src.white_agent.agent import start_white_agent
from src.launcher import launch_evaluation, launch_remote_evaluation


class WerewolfSettings(BaseSettings):
    role: str = "unspecified"
    host: str = "127.0.0.1"
    agent_port: int = 8001


app = typer.Typer(help="Agentified Werewolf - orchestration and evaluation")


@app.command()
def green():
    """Start the green agent (referee/controller)."""
    start_green_agent()


@app.command()
def white():
    """Start the white agent (player/contestant)."""
    start_white_agent()


@app.command()
def run():
    settings = WerewolfSettings()
    if settings.role == "green":
        start_green_agent(host=settings.host, port=settings.agent_port)
    elif settings.role == "white":
        start_white_agent(host=settings.host, port=settings.agent_port)
    else:
        raise ValueError(f"Unknown role: {settings.role}")
    return


@app.command()
def launch():
    """Launch a local evaluation with embedded green/white agents."""
    asyncio.run(launch_evaluation())


@app.command()
def launch_remote(green_url: str, white_url: str):
    """Launch an evaluation using remote agents."""
    asyncio.run(launch_remote_evaluation(green_url, white_url))


if __name__ == "__main__":
    app()
