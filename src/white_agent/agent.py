from __future__ import annotations

import uvicorn

from werewolf.agent_white import app


def start_white_agent(host: str = "0.0.0.0", port: int = 8011) -> None:
    """Start the white (player) FastAPI app."""
    uvicorn.run(app, host=host, port=port)
