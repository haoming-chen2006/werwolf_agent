"""CLI entry point for agentify-example-tau-bench."""

import os
import typer
import asyncio
import uvicorn

from src.green_agent import start_green_agent
from src.white_agent import start_white_agent
from src.launcher import launch_evaluation, launch_remote_evaluation
from src.werewolf.agent_white import app as werewolf_white_app
from pydantic_settings import BaseSettings


class WerewolfSettings(BaseSettings):
    role: str = "unspecified"
    host: str = "127.0.0.1"
    agent_port: int = 9000


app = typer.Typer(help="Agentified Werewolf - Standardized agent assessment framework")


@app.command()
def green():
    """Start the green agent (assessment manager)."""
    start_green_agent()


@app.command()
def white():
    """Start the white agent (target being tested)."""
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


@app.command(name="launch_eval")
def launch_eval():
    """Launch evaluation with VANILLA white agent (simple LLM calls).
    
    Use this for baseline testing without the Planner→Investigation→Decision architecture.
    """
    os.environ["WHITE_AGENT_MODE"] = "vanilla"
    print("Mode: VANILLA (simple LLM calls)")
    asyncio.run(launch_evaluation())


@app.command()
def launch(host: str = "127.0.0.1", port: int = 9002):
    """Launch evaluation with ADVANCED white agent architecture.

    Uses the Planner → Special Sessions → Final Decision architecture:
    1. Planner reads Green_Record.txt and creates strategy
    2. Special sessions investigate targets via file tools (returns JSON)
    3. Final decision maker combines plan + investigations
    4. Validator auto-passes (logging only)
    
    This is the main command for testing the advanced white agent.
    """
    os.environ["WHITE_AGENT_MODE"] = "advanced"
    print("Mode: ADVANCED (Planner → Investigation → Decision)")
    print("Launching full evaluation workflow...")
    asyncio.run(launch_evaluation())


@app.command(name="launch_white")
def launch_white(host: str = "127.0.0.1", port: int = 9002):
    """Start the actual (stateful) white agent FastAPI app.

    Use this when you want to develop or test the FastAPI white agent
    endpoints directly.
    """
    print(f"Starting actual white agent app on {host}:{port}...")
    uvicorn.run(werewolf_white_app, host=host, port=port, log_level="info")


@app.command()
def launch_control(host: str = "127.0.0.1", port: int = 9002):
    """Start the stateless control white agent wrapper (legacy/testing).

    Use this if you want the general-purpose stateless agent that inlines
    file pointers and proxies to the werewolf endpoints. Example:
      python main.py launch_control
    """
    print(f"Starting stateless control white agent on {host}:{port}...")
    # start_white_agent defaults match the legacy behaviour
    start_white_agent(host=host, port=port)


@app.command()
def launch_remote(green_url: str, white_url: str):
    """Launch the complete evaluation workflow."""
    asyncio.run(launch_remote_evaluation(green_url, white_url))


if __name__ == "__main__":
    app()
