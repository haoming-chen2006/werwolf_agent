#!/bin/bash
export PYTHONPATH=$PYTHONPATH:$(pwd)/src
PORT=${AGENT_PORT:-8001}
uvicorn werewolf.env_green:app --host 0.0.0.0 --port $PORT
