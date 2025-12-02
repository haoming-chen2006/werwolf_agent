#!/bin/bash
# Kills any existing python processes matching agent_white to clean up (be careful with this in prod)
pkill -f "werewolf.agent_white" || true

echo "Starting 5 White Agents..."

for i in {1..5}
do
   PORT=$((8010 + i))
   echo "Starting Agent $i on port $PORT"
   uvicorn werewolf.agent_white:app --host 0.0.0.0 --port $PORT > white_agent_$i.log 2>&1 &
done

echo "Agents started. Logs are in white_agent_N.log"
