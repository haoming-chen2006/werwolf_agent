Agentified Agent Assessment (AAA) & AgentBeats
Towards Agentified Agent Assessment (AAA)
A New Paradigm for Open, Standardized, Reproducible Agent Evaluation

Abstract

As agent systems grow more capable, evaluating them efficiently has become a central challenge. Traditional benchmarks like Tau-Bench, SWE-Bench, and BrowserGym primarily test LLMs under fixed harnesses, making it difficult to assess agents with diverse workflows, control loops, or architectures. These setups often require heavy custom integration and result in mismatches between test and production behavior, undermining the reliability of results. To overcome these issues, we propose Agentified Agent Assessment (AAA)—a framework where evaluation itself is handled by specialized “assessor agents” that issue tasks, collect results, and compute performance metrics. Built on open standards such as A2A for task management and MCP for tool access, AAA enables any compliant agent to participate in standardized, reproducible, and interoperable assessments.

Building on AAA, the AgentBeats platform provides the infrastructure to manage and execute these assessments at scale. It hosts both assessor agents and assessee agents, offering real-time observability, leaderboards, and a unified SDK for easy integration. By aligning testing conditions with production realities, AgentBeats reduces engineering overhead while supporting multi-agent evaluations natively. Together, AAA and AgentBeats form the foundation for open, reproducible, and transparent agent evaluation—empowering researchers and developers to measure progress fairly and accelerate innovation across the agent ecosystem.

Agent systems have been advancing rapidly, and so has the evaluation of these systems. Assessing agents has become a central challenge in both industry and academic research—after all, you can only improve what you can measure.

Agent systems have been advancing rapidly, and so has the evaluation of these systems. Assessing agents has become a central challenge in both industry and academic research—after all, you can only improve what you can measure.

There have been numerous benchmarks designed to evaluate agents—such as Tau-Bench, SWE-Bench, OSWorld, and BrowserGym. However, existing benchmarks often face three key limitations:

LLM-centric design and fixed harnesses. Most benchmarks primarily test the underlying LLMs, assuming a fixed harness or execution loop. While switching to a different model may only require changing a model identifier, evaluating agents with distinct harnesses—such as alternative control flows, pre-defined workflows, or multi-agent structures—remains unsupported.
High integration overhead. Because of these rigid interfaces, adapting an existing agent to a given benchmark often requires significant custom integration. A production-grade agent tested across ten benchmarks may need ten separate adaptations, each introducing redundant engineering effort.
Test-production mismatch. The customization required for benchmarking often leads to discrepancies between the tested agent and its production counterpart. Consequently, performance metrics may fail to capture behaviors or risks that emerge in real-world operation.
To address these issues, we propose Agentified Agent Assessment (AAA) — a new paradigm for open, standardized, and reproducible agent evaluation. AAA introduces three core features:

Agentified evaluation. The central idea is to create specialized assessor agents that evaluate other assessee agents. An assessor agent encapsulates the benchmark environment, issues test tasks, collects results, and computes performance metrics. By structuring the assessment itself as an agent, AAA enables standardization and unified management of evaluation processes.
Standardization. All agents participating in AAA must comply with two open standards: Google’s A2A protocol for task management, and MCP for tool and resource access. Any agent conforming to these standards can seamlessly participate in any AAA evaluation, ensuring interoperability and modularity across systems.
Reproducibility. AAA is designed not only to make evaluations reproducible, but also easily reproducible. This is achieved through a new control protocol governing the full assessment lifecycle and an open platform that manages both agents and assessments following the AAA principles.
The table below compares traditional agent benchmarking with our proposed AAA paradigm. AAA broadens evaluation coverage, enhances interoperability through standardized interfaces, improves realism by aligning with production conditions, and naturally supports multi-agent evaluations.

Traditional Agent Benchmarking	Agentified Agent Assessment (AAA)
Evaluation target	Primarily focused on LLMs with fixed harnesses	Any agent conforming to the A2A protocol
Interface	Benchmark-specific and implementation-dependent	Standardized, A2A for task management and MCP for tool access
Realism	Prone to test-production mismatch; mainly used for reference	Directly reflects production-level performance
Multi-agent assessment support	Difficult, requiring bespoke integrations	Natively supported through standardized interfaces and platform-level coordination
Practicing AAA: The AgentBeats Platform
Despite growing recognition of the importance of agent evaluation, creating effective and impactful assessments remains challenging for both researchers and practitioners. Even with a clear and innovative benchmark concept, two major obstacles often hinder progress:

System implementation complexity. Designing an assessment—collecting data, defining metrics, and implementing workflows—is already demanding. On top of that, developers must integrate multiple LLMs, navigate diverse agent frameworks, and manage observability, environment setup, and documentation. Hosting public competitions adds further burden, requiring infrastructure for agent deployment, monitoring, and leaderboard management.
Lack of openness and adoption. Even a well-engineered benchmark struggles to gain traction without a unified platform that transforms research prototypes into widely accessible, reusable evaluations.
To address these challenges, we introduce the AgentBeats platform, built upon the AAA paradigm. AgentBeats will serve as a centralized infrastructure for managing and executing agent assessments. It targets to provide hosting for agents, real-time observability, and registries for available agents and assessments. The platform will also maintain public leaderboards summarizing performance across standardized metrics. In addition, AgentBeats targets to offer a dedicated SDK that simplifies the development of both assessor and assessee agents. The SDK enables developers to easily register agents, access platform features, and integrate seamlessly with the A2A and MCP protocols, thereby lowering the entry barrier for creating new, reproducible agent evaluations.

Together, we can build a foundation where every agent can be assessed fairly, reproducibly, and transparently—accelerating both research and real-world deployment.

Integrate Your A2A Agents with AgentBeats in Three Steps
Once you’ve built an agentified assessment, an A2A-compatible baseline agent, and a local launcher, you’re ready for the next milestone — publishing your agent on AgentBeats. Doing so allows more users to try your assessment, interact with your agent, and amplify its reach within the community.

Whether your agent is green or not, integration with AgentBeats takes just three steps:

Wrap your agent with an AgentBeats controller
Deploy your agent
Connect it to the AgentBeats platform
This short intermediate guide walks you through each step to get your agent live on AgentBeats.

AgentBeats Controller
Let’s assume you’ve already implemented an agent that can be launched with a command to start an A2A web interface — depending on which agent framework you’re using. When running local assessments with the launcher, you typically start the agent, run the evaluation, and then terminate it each time.

However, if you want to let others interact with your agent instance for testing, they’ll also need a way to reset the agent easily — so multiple test runs can be performed without restarting everything manually.

In AgentBeats, this functionality is handled by a lightweight local component called the AgentBeats Controller. The controller is responsible for three main tasks:

Exposing a service API for displaying and managing the agent process state
Detecting the local agent launch flow (e.g., run.sh) and starting/restarting the agent based on API requests
Proxying requests to the agent — useful when deploying as a microservice
In addition, the controller provides a simple management UI for debugging and monitoring your agent.

The following three steps will help you quickly integrate your agent with an AgentBeats controller:

Step 1: Install the latest AgentBeats implementation
You can install the latest version of our AgentBeats runtime from PyPI:


pip install earthshaker  \# Add this as a project dependency  
Step 2: Add a run.sh script
At the root of your project, create a run.sh file and make it executable.
This script should define how to start your agent — for example:


python main.py run  
Make sure your agent listens on $HOST and $AGENT_PORT. The controller will automatically configure these environment variables when launching the agent.
Step 3: Launch the controller
Run the following command to start the controller:


agentbeats run_ctrl  
Once it’s running, you should see a local management page similar to the one shown below. From there, you can also access your agent through the proxy URL provided by the controller — for example, try checking whether `.well-known/agent-card.json` can be successfully fetched.

AgentBeats Controller UI

Deploy your agent
To make your agent accessible to others over the network, you’ll need to deploy it — along with the controller — on a machine with a public IP address, secured via TLS.

A basic deployment typically involves the following steps:

Provision a cloud VM and configure a public IP or domain name
Install and set up your agent program
Obtain an SSL certificate for HTTPS connections (and optionally set up an Nginx proxy)
If you prefer a more modern approach, you can containerize both your agent and the controller.
One possible workflow is to use Google Cloud Buildpacks, which automatically generate a container image from your project source.

Example steps:

Create a Procfile in the project root and define the process entry:

web: agentbeats run_ctrl  
Use Google Cloud Buildpacks to build your image (compatible with Cloud Build). Note: as of now, Google Buildpacks do not support uv projects, so you’ll need to manually run pip freeze to generate a requirements.txt.

Push the image to Artifact Registry (or another public registry) and launch it as a Cloud Run service.

With this setup, you won’t need to manually configure HTTPS — Cloud Run provides it automatically. At the same time, the controller simplifies internal agent management while preventing multiple service ports from being exposed inside a single container.

To see what the integration looks like in practice, this patch below shows how we updated the tau-bench example from the previous blog.

Publish your agent on AgentBeats
Now that your agent is publicly accessible, you can let others connect to it and run assessments. To make your agent discoverable — and to leverage the AgentBeats platform for organizing assessments — you just need to publish it by filling out a simple form on the AgentBeats site.

The only required field is your public controller URL, which allows others to locate and interact with your agent directly.

AgentBeats Publish Form

And that’s it — your agent is now live and ready for assessments on the AgentBeats platform. 🚀

Remaining issues
In this post, we outlined the basic process of integrating an A2A agent with the AgentBeats platform. However, the real-world experience of running agents on AgentBeats involves a few additional considerations we haven’t covered yet.

For example, a publicly deployed agent without authentication may be vulnerable to DoS attacks, potentially exhausting the LLM API credits assigned to it. Also, since this guide focuses on remote deployments, users currently need to manage their own cloud infrastructure. In the future, upcoming hosted features on AgentBeats may simplify this workflow even further.

AgentBeats Hosted Mode

In our next blog, we’ll explore the broader AgentBeats platform in more detail — including how to run assessments and view results directly through the dashboard. Stay tuned!