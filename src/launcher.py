"""Launcher module - initiates and coordinates the evaluation process."""

import multiprocessing
import json
import os
import time
from dotenv import load_dotenv
from src.agent_config import AGENTS, GREEN_AGENT, ensure_api_key
from src.green_agent.agent import start_green_agent
from src.white_agent.agent import start_white_agent
from src.my_util import my_a2a


async def launch_evaluation():
    # verify API key exists (this will raise with helpful message if not)
    try:
        openai_key = ensure_api_key()
    except Exception as e:
        print(f"Missing API key: {e}")
        raise

    # create a live run directory to hold public history for agents to read
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    live_root = os.path.join(repo_root, "live_runs")
    os.makedirs(live_root, exist_ok=True)
    run_dir = os.path.join(live_root, f"run_{int(time.time())}")
    os.makedirs(run_dir, exist_ok=True)
    public_dir = os.path.join(run_dir, "public")
    os.makedirs(public_dir, exist_ok=True)

    # start green agent
    print("Launching green agent...")
    green_address = ("localhost", 9001)
    green_url = f"http://{green_address[0]}:{green_address[1]}"
    # pass OPENAI_API_KEY into green process env as well
    env_green = os.environ.copy()
    env_green["OPENAI_API_KEY"] = openai_key
    p_green = multiprocessing.Process(
        target=start_green_agent, args=(GREEN_AGENT.name, *green_address)
    )
    p_green.start()
    assert await my_a2a.wait_agent_ready(green_url), "Green agent not ready in time"
    print("Green agent is ready.")

    # start multiple white agents based on AGENTS config (default 6)
    num_whites = int(os.environ.get("NUM_WHITE_AGENTS", str(len(AGENTS))))
    print(f"Launching {num_whites} white agents from config...")
    white_processes = []
    white_urls = []
    base_port = 9002

    for i in range(num_whites):
        spec = AGENTS[i]
        port = base_port + i
        host = "localhost"
        white_url = f"http://{host}:{port}"

        # child env
        child_env = os.environ.copy()
        child_env["OPENAI_API_KEY"] = openai_key
        child_env["AGENT_URL"] = white_url
        child_env["AGENT_SESSION_ID"] = f"white_{i+1}"
        mem_file = os.path.abspath(os.path.join(os.path.dirname(__file__), f"../agent_memory_white_{i+1}.log"))
        child_env["AGENT_MEMORY_FILE"] = mem_file
        # public folder where GameManager will write public speeches for all agents
        child_env["PUBLIC_HISTORY_DIR"] = public_dir
        # provider/model handy for the white process
        child_env["AGENT_PROVIDER"] = spec.provider
        child_env["AGENT_MODEL"] = spec.model

        # set child env in parent briefly; child will inherit env at start
        orig = os.environ.copy()
        os.environ.update(child_env)
        p = multiprocessing.Process(target=start_white_agent, args=(spec.name, host, port))
        p.start()
        # restore parent's env
        os.environ.clear()
        os.environ.update(orig)
        white_processes.append(p)
        white_urls.append(white_url)

    # wait for all white agents to be ready
    for url in white_urls:
        ready = await my_a2a.wait_agent_ready(url)
        assert ready, f"White agent at {url} not ready in time"
    print("All white agents are ready.")

    # set PUBLIC_HISTORY_DIR into this (launcher) process so GameManager will write into it
    os.environ["PUBLIC_HISTORY_DIR"] = public_dir

    # send the task description to green agent (controller) if you want the controller to run
    print("Sending task description to green agent...")
    # task_config = {
    #     "env": "retail",
    #     "user_strategy": "llm",
    #     "user_model": "openai/gpt-4o",
    #     "user_provider": "openai",
    #     "task_split": "test",
    #     "task_ids": [1],
    # }
    task_config = {
        "env": "retail",
        "user_strategy": "llm",
        "user_model": "openrouter/openai/gpt-4o",
        "user_provider": "litellm_proxy",
        "task_split": "test",
        "task_ids": [1],
    }
    task_text = f"""
Your task is to instantiate the werewolf assessment harness to test the agents located at:
<white_agent_urls>
{json.dumps(white_urls, indent=2)}
</white_agent_urls>
Please prefer using the local `src/werewolf` module for assessment behaviors where applicable.
You should use the following env configuration:
<env_config>
{json.dumps(task_config, indent=2)}
</env_config>
The agents will read shared public info from: {public_dir}
    """
    print("Task description:")
    print(task_text)
    print("Sending...")
    # We expect the green agent to run for a while.
    # Ensure send_message waits long enough or the agent doesn't return early.
    # With our changes to agent.py, it should wait for the final message.
    response = await my_a2a.send_message(green_url, task_text)
    print("Response from green agent:")
    print(response)

    print("Evaluation complete. Terminating agents...")
    p_green.terminate()
    p_green.join()
    for p in white_processes:
        p.terminate()
        p.join()
    print("Agents terminated.")


async def launch_remote_evaluation(green_url: str, white_url: str):
    task_config = {
        "env": "retail",
        "user_strategy": "llm",
        "user_model": "openrouter/openai/gpt-4o",
        "user_provider": "litellm_proxy",
        "task_split": "test",
        "task_ids": [1],
    }
    task_text = f"""
Your task is to instantiate the werewolf assessment harness to test the agent located at:
<white_agent_url>
{white_url}
</white_agent_url>
Please prefer using the local `src/werewolf` module for assessment behaviors where applicable.
You should use the following env configuration:
<env_config>
{json.dumps(task_config, indent=2)}
</env_config>
    """
    print("Sending task description to green agent...")
    response = await my_a2a.send_message(green_url, task_text)
    print("Response from green agent:")
    print(response)
