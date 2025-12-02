from __future__ import annotations

import uvicorn

from werewolf.env_green import app


def start_green_agent(host: str = "0.0.0.0", port: int = 8001) -> None:
    """Start the green (referee) FastAPI app."""
    uvicorn.run(app, host=host, port=port)
