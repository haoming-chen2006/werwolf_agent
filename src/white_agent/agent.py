"""White agent implementation - the target agent being tested."""

import uvicorn
import dotenv
import os
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentSkill, AgentCard, AgentCapabilities
from a2a.utils import new_agent_text_message
from litellm import completion
from fastapi import FastAPI

# Import the werewolf white agent FastAPI app and mount it so the A2A server
# exposes the werewolf `/agent/*` endpoints at the same base URL used by
# the migrated game logic. This keeps the original A2A behaviour while
# serving the werewolf agent HTTP endpoints expected by the GameManager.
from src.werewolf.agent_white import app as werewolf_white_app


dotenv.load_dotenv()


def prepare_white_agent_card(url):
    skill = AgentSkill(
        id="task_fulfillment",
        name="Task Fulfillment",
        description="Handles user requests and completes tasks",
        tags=["general"],
        examples=[],
    )
    card = AgentCard(
        name="general_white_agent",
        description="A general-purpose white agent for task fulfillment.",
        url=url,
        version="1.0.0",
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        capabilities=AgentCapabilities(),
        skills=[skill],
    )
    return card


class GeneralWhiteAgentExecutor(AgentExecutor):
    def __init__(self):
        self.ctx_id_to_messages = {}

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        # parse the task
        user_input = context.get_user_input()
        if context.context_id not in self.ctx_id_to_messages:
            self.ctx_id_to_messages[context.context_id] = []
        messages = self.ctx_id_to_messages[context.context_id]
        messages.append(
            {
                "role": "user",
                "content": user_input,
            }
        )
        if os.environ.get("LITELLM_PROXY_API_KEY") is not None:
            response = completion(
                messages=messages,
                model="openrouter/openai/gpt-4o",
                custom_llm_provider="litellm_proxy",
                temperature=0.0,
            )
        else:
            response = completion(
                messages=messages,
                model="openai/gpt-4o",
                custom_llm_provider="openai",
                temperature=0.0,
            )
        next_message = response.choices[0].message.model_dump()  # type: ignore
        messages.append(
            {
                "role": "assistant",
                "content": next_message["content"],
            }
        )
        await event_queue.enqueue_event(
            new_agent_text_message(
                next_message["content"], context_id=context.context_id
            )
        )

    async def cancel(self, context, event_queue) -> None:
        raise NotImplementedError


def start_white_agent(agent_name="general_white_agent", host="localhost", port=9002):
    print("Starting white agent...")

    # # # without controller
    # url = f"http://{host}:{port}"
    # card = prepare_white_agent_card(url)

    card = prepare_white_agent_card(os.getenv("AGENT_URL") or f"http://{host}:{port}")

    request_handler = DefaultRequestHandler(
        agent_executor=GeneralWhiteAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )

    a2a_app = A2AStarletteApplication(
        agent_card=card,
        http_handler=request_handler,
    )

    # Build the underlying Starlette app and mount the werewolf FastAPI
    # under the `/agent` path so GameManager calls like
    # `http://<white_url>/agent/discussion` work unchanged.
    starlette_app = a2a_app.build()

    # Add /info redirect to agent card for compatibility with some platforms
    from starlette.responses import RedirectResponse, JSONResponse, PlainTextResponse
    async def info_endpoint(request):
        return RedirectResponse(url="/.well-known/agent-card.json")
    
    async def status_endpoint(request):
        return JSONResponse({"status": "ok"})

    async def root_endpoint(request):
        return PlainTextResponse("White Agent is running.")

    starlette_app.add_route("/info", info_endpoint, methods=["GET"])
    starlette_app.add_route("/status", status_endpoint, methods=["GET"])
    starlette_app.add_route("/", root_endpoint, methods=["GET"])

    # mount the werewolf white FastAPI at /agent (the werewolf app defines
    # routes like /agent/discussion, /agent/vote, etc.; mounting at `/agent`
    # keeps the same path structure when invoked from the game manager)
    starlette_app.mount("/agent", werewolf_white_app)

    uvicorn.run(starlette_app, host=host, port=port, log_level="info")
