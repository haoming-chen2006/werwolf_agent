import sys
import os
sys.path.append(os.getcwd())
from src.white_agent.agent import prepare_white_agent_card, GeneralWhiteAgentExecutor
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore

card = prepare_white_agent_card("http://localhost:9002")
request_handler = DefaultRequestHandler(
    agent_executor=GeneralWhiteAgentExecutor(),
    task_store=InMemoryTaskStore(),
)
a2a_app = A2AStarletteApplication(
    agent_card=card,
    http_handler=request_handler,
)
app = a2a_app.build()

print("Routes:")
for route in app.routes:
    print(f"{route.path} {route.name}")
