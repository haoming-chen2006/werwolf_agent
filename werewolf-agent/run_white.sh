#!/bin/bash
export PYTHONPATH=$PYTHONPATH:$(pwd)/src
PORT=${AGENT_PORT:-8011}
uvicorn werewolf.agent_white:app --host 0.0.0.0 --port $PORT
