import json
import sys

try:
    from agentbeats.agent_executor import AgentCard
except ImportError:
    try:
        from agentbeats.datamodel import AgentCard
    except ImportError:
        print("Could not import AgentCard")
        sys.exit(1)

print(json.dumps(AgentCard.model_json_schema(), indent=2))
