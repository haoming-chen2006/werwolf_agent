"""Green agent implementation - manages assessment and evaluation."""

import uvicorn
import tomllib
import dotenv
import json
import time
import os
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCard, SendMessageSuccessResponse, Message
from a2a.utils import new_agent_text_message, get_text_parts
from src.my_util import parse_tags, my_a2a
from src.werewolf.game_manager import GameManager
from src.werewolf.models import PlayerProfile
from src.agent_config import AGENTS

# Compatibility adapter to avoid a hard dependency on `tau_bench`.
from .compat import get_env, SolveResult, RESPOND_ACTION_NAME, Action

dotenv.load_dotenv()


def load_agent_card_toml(agent_name):
    current_dir = __file__.rsplit("/", 1)[0]
    with open(f"{current_dir}/{agent_name}.toml", "rb") as f:
        return tomllib.load(f)


async def ask_agent_to_solve(white_agent_url, env, task_index, max_num_steps=30):
    # migrated from https://github.com/sierra-research/tau-bench/blob/4754e6b406507dbcbce8e8b3855dcf80aaec18ac/tau_bench/agents/tool_calling_agent.py#L27
    total_cost = 0.0
    env_reset_res = env.reset(task_index=task_index)
    obs = env_reset_res.observation
    # env_reset_res.info may be a pydantic model or a plain dict depending on env
    raw_info = getattr(env_reset_res, "info", {})
    if hasattr(raw_info, "model_dump"):
        info = raw_info.model_dump()
    else:
        info = raw_info if raw_info is not None else {}
    reward = 0.0

    # messages = [
    #     {"role": "system", "content": env.wiki},
    #     {"role": "user", "content": obs},
    # ]

    # Here, instead of calling white agent like calling an LLM, we need to present
    #   the assessment scenario to the white agent as if it is a independent task
    # Specifically, here we provide the tool information for the agent to reply with
    task_description = f"""
{env.wiki}
Here's a list of tools you can use (you can use at most one tool at a time):
{json.dumps(env.tools_info, indent=2)}
Please response in the JSON format. Please wrap the JSON part with <json>...</json> tags.
The JSON should contain:
- "name": the tool call function name, or "{RESPOND_ACTION_NAME}" if you want to respond directly.
- "kwargs": the arguments for the tool call, or {{"content": "your message here"}} if you want to respond directly.

Next, I'll provide you with the user message and tool call results.
User message: {obs}
    """

    next_green_message = task_description
    context_id = None
    for _ in range(max_num_steps):
        # # --> messages (message history)
        # res = completion(
        #     messages=messages,
        #     model=self.model,
        #     custom_llm_provider=self.provider,
        #     tools=self.tools_info,
        #     temperature=self.temperature,
        # )
        # next_message = res.choices[0].message.model_dump()
        # total_cost += res._hidden_params["response_cost"] or 0
        # action = message_to_action(next_message)
        # # --> action (to be executed in the environment)
        print(
            f"@@@ Green agent: Sending message to white agent{'ctx_id=' + str(context_id) if context_id else ''}... -->\n{next_green_message}"
        )
        white_agent_response = await my_a2a.send_message(
            white_agent_url, next_green_message, context_id=context_id
        )
        res_root = white_agent_response.root
        assert isinstance(res_root, SendMessageSuccessResponse)
        res_result = res_root.result
        assert isinstance(
            res_result, Message
        )  # though, a robust design should also support Task
        if context_id is None:
            context_id = res_result.context_id
        else:
            assert context_id == res_result.context_id, (
                "Context ID should remain the same in a conversation"
            )

        text_parts = get_text_parts(res_result.parts)
        assert len(text_parts) == 1, (
            "Expecting exactly one text part from the white agent"
        )
        white_text = text_parts[0]
        print(f"@@@ White agent response:\n{white_text}")
        # parse the action out
        white_tags = parse_tags(white_text)
        action_json = white_tags["json"]
        action_dict = json.loads(action_json)
        action = Action(**action_dict)

        env_response = env.step(action)
        # env_response.info may be a pydantic model or a dict
        raw_step_info = getattr(env_response, "info", {})
        if hasattr(raw_step_info, "model_dump"):
            step_info = raw_step_info.model_dump()
        else:
            step_info = raw_step_info if raw_step_info is not None else {}
        reward = getattr(env_response, "reward", 0.0)
        # merge infos
        info = {**info, **step_info}
        print(f"@@@ Env observation:\n{getattr(env_response, 'observation', None)}")
        print(f"@@@ Env step info merged: {step_info}")

        # instead of maintain history, just prepare the next message with the latest observation
        if action.name != RESPOND_ACTION_NAME:
            next_green_message = f"""
Tool call result:
{env_response.observation}
            """
        else:
            next_green_message = f"""
User message:
{env_response.observation}
            """
        if env_response.done:
            break

    return SolveResult(
        reward=reward,
        info=info,
        messages=[],  # incompatible, thus removed
        total_cost=total_cost,
    )


class WerewolfGreenAgentExecutor(AgentExecutor):
    def __init__(self):
        pass

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        async def log_callback(message: str):
            # Print to stdout instead of enqueuing to avoid premature termination of launcher
            # The launcher waits for the first message from the agent. We only want to send the final result.
            print(f"[GreenAgent] {message}")

        # parse the task
        await log_callback("Green agent: Received a task, parsing...")
        user_input = context.get_user_input()
        tags = parse_tags(user_input)
        
        # Handle both single url and list of urls
        white_agent_urls = []
        white_agent_urls_str = tags.get("white_agent_urls")
        if white_agent_urls_str:
            try:
                urls = json.loads(white_agent_urls_str)
                if isinstance(urls, list):
                    white_agent_urls = urls
            except json.JSONDecodeError:
                pass
        
        if not white_agent_urls:
            # Fallback to single url
            url = tags.get("white_agent_url")
            if url:
                white_agent_urls = [url]
            else:
                await log_callback("Warning: No white_agent_urls found. Using defaults.")
                white_agent_urls = ["http://localhost:9002"]

        await log_callback(f"Green agent: Starting game with {len(white_agent_urls)} agents.")
        
        # Build PlayerProfiles
        player_profiles = []
        # We assume white_agent_urls correspond to AGENTS config in order
        # If fewer urls than AGENTS, we slice AGENTS. If more, we might run out of config.
        
        num_agents = len(white_agent_urls)
        for i in range(num_agents):
            if i < len(AGENTS):
                spec = AGENTS[i]
                pid = f"p{i+1}"
                profile = PlayerProfile(
                    id=pid,
                    alias=spec.name,
                    role_private=spec.role,
                    alignment=("wolves" if spec.role == "werewolf" else "town"),
                    alive=True,
                    provider=spec.provider,
                    model=spec.model,
                    url=white_agent_urls[i],
                )
                player_profiles.append(profile)
            else:
                # Fallback if more urls than config
                pid = f"p{i+1}"
                profile = PlayerProfile(
                    id=pid,
                    alias=f"Agent_{i+1}",
                    role_private="villager", # Default
                    alignment="town",
                    alive=True,
                    provider="openai",
                    model="gpt-4o",
                    url=white_agent_urls[i],
                )
                player_profiles.append(profile)

        # Run GameManager
        # Pass None for log_callback to avoid double printing (GameManager prints to stdout)
        manager = GameManager(player_profiles, config={"max_words_day_talk": 100}, log_callback=None)
        try:
            record = await manager.run_game()
            await log_callback("Green Agent: GameManager finished. Game saved.")
            result_msg = f"Game finished. Winner: {record.final_result.winning_side}"
        except Exception as e:
            await log_callback(f"Green Agent: GameManager failed: {e}")
            result_msg = f"Game failed: {e}"

        await event_queue.enqueue_event(
            new_agent_text_message(result_msg)
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError


def start_green_agent(agent_name="werewolf_green_agent", host="localhost", port=9001):
    print("Starting green agent...")
    agent_card_dict = load_agent_card_toml(agent_name)

    # # without controller
    # url = f"http://{host}:{port}"
    # agent_card_dict["url"] = url  # complete all required card fields

    agent_card_dict["url"] = os.getenv("AGENT_URL") or f"http://{host}:{port}"

    request_handler = DefaultRequestHandler(
        agent_executor=WerewolfGreenAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )

    a2a_app = A2AStarletteApplication(
        agent_card=AgentCard(**agent_card_dict),
        http_handler=request_handler,
    )

    # Optionally mount the werewolf referee HTTP app so the green agent can
    # also serve the werewolf management endpoints. If the environment
    # variable `SERVE_WEREWOLF_REFEREE` is set, mount the werewolf FastAPI
    # under `/werewolf`. Regardless, keep the A2A endpoints available so the
    # controller can discover the agent via its AgentCard.
    starlette_app = a2a_app.build()
    try:
        from src.werewolf.env_green import app as werewolf_green_app
    except Exception:
        werewolf_green_app = None

    if werewolf_green_app is not None:
        # Mount at /werewolf so paths don't conflict with A2A routes.
        starlette_app.mount("/werewolf", werewolf_green_app)

    uvicorn.run(starlette_app, host=host, port=port, log_level="info")
