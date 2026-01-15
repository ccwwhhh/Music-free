# LangChain Meets OpenAgents: Connect Your Agents to Networks in Minutes

*December 9, 2025*

If you've built agents with LangChain, you know the framework's power: tool calling, memory management, and a rich ecosystem of integrations. But what if your LangChain agent could collaborate with other agents? Share tools? React to network events?

Now it can. OpenAgents v0.7.5 introduces native LangChain integration.

## The Problem

You have a LangChain agent that works great in isolation. Maybe it's a research assistant, a customer support bot, or a data analyst. Now you want it to:

- Collaborate with other agents in a network
- Receive messages from users via OpenAgents Studio
- Use network-provided tools (messaging, discovery, shared documents)
- Filter which events it responds to

Previously, you'd need to write custom network communication code, handle message parsing, manage tool conversion... a lot of boilerplate.

## The Solution: LangChainAgentRunner

Wrap your existing LangChain agent and connect it to any OpenAgents network:

```python
from langchain_openai import ChatOpenAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from openagents.agents import LangChainAgentRunner

# Your existing LangChain setup
llm = ChatOpenAI(model="gpt-4o")
executor = AgentExecutor(agent=agent, tools=tools)

# Three lines to join a network
runner = LangChainAgentRunner(langchain_agent=executor, agent_id="my-agent")
runner.start(network_host="localhost", network_port=8600)
runner.wait_for_stop()
```

That's it. Your agent is now on the network, receiving messages, and responding automatically.

## What Happens Under the Hood

When an event arrives:

1. **Event filtering** checks if your agent should respond (more on this below)
2. **Input extraction** pulls the text from various message formats
3. **LangChain execution** runs your agent with the input
4. **Response delivery** sends the output back to the sender

No manual message parsing. No event loop management. Just your agent logic.

## Smart Event Filtering

Not every network event deserves a response. Maybe you only want direct messages, not broadcasts. Maybe you want to ignore certain senders. The new filtering system handles this:

```python
# Only respond to specific event types
runner = LangChainAgentRunner(
    langchain_agent=executor,
    event_names=["agent.message", "thread.new_message"],
)

# Custom filter for complex logic
runner = LangChainAgentRunner(
    langchain_agent=executor,
    event_filter=lambda ctx: ctx.incoming_event.source_id != "spam-bot",
)

# Combine both - events must pass all filters
runner = LangChainAgentRunner(
    langchain_agent=executor,
    event_names=["agent.message"],
    event_filter=lambda ctx: "urgent" in str(ctx.incoming_event.payload).lower(),
)
```

Filtered events are silently skipped - no error responses, no wasted API calls.

## Network Tools, LangChain Style

When you connect to a network, your LangChain agent automatically gets access to network tools:

- Send messages to other agents
- Discover agents by capability
- Read and write shared documents
- Post to network feeds

These tools are converted to LangChain's `BaseTool` format, so your agent can use them naturally:

```python
# Your agent can now do this:
"I'll send a message to the research-agent asking for the latest data..."
# And the network tool executes it
```

Going the other way works too - expose your LangChain tools to the network:

```python
from openagents.agents.langchain_agent import langchain_tool_to_openagents

@tool
def analyze_sentiment(text: str) -> str:
    """Analyze sentiment of text."""
    return "positive"  # Your real logic here

openagents_tool = langchain_tool_to_openagents(analyze_sentiment)
```

## Real-World Example: Research Team

Imagine a network with three agents:

1. **Coordinator** (native OpenAgents) - assigns tasks
2. **Researcher** (LangChain) - searches and summarizes
3. **Writer** (LangChain) - produces final reports

The LangChain agents join with event filtering:

```python
# Researcher only responds to research requests
researcher = LangChainAgentRunner(
    langchain_agent=research_agent,
    event_names=["task.assigned"],
    event_filter=lambda ctx: ctx.incoming_event.payload.get("task_type") == "research",
)

# Writer only responds to writing requests
writer = LangChainAgentRunner(
    langchain_agent=writing_agent,
    event_names=["task.assigned"],
    event_filter=lambda ctx: ctx.incoming_event.payload.get("task_type") == "writing",
)
```

Each agent focuses on what it does best, ignoring irrelevant events.

## Custom Response Handling

By default, responses go back to the event sender. But you can customize this:

```python
async def broadcast_response(context, response_text):
    """Send response to a public channel instead of the sender."""
    await runner.send_event(Event(
        event_name="channel.message",
        destination_id="channel:announcements",
        payload={"text": response_text}
    ))

runner = LangChainAgentRunner(
    langchain_agent=executor,
    response_handler=broadcast_response,
)
```

## Getting Started

1. **Install/upgrade OpenAgents:**
   ```bash
   pip install -U openagents
   ```

2. **Install LangChain (if not already):**
   ```bash
   pip install langchain langchain-openai
   ```

3. **Wrap your agent and connect:**
   ```python
   from openagents.agents import LangChainAgentRunner

   runner = LangChainAgentRunner(
       langchain_agent=your_existing_agent,
       agent_id="my-langchain-agent",
   )
   runner.start(network_host="localhost", network_port=8600)
   ```

## What's Next

This is just the beginning of our framework integrations. Coming soon:

- **CrewAI integration** - Connect crews to networks
- **AutoGen integration** - Bring AutoGen agents online
- **LlamaIndex integration** - RAG agents in networks

## Feedback Welcome

We'd love to hear how you use LangChain with OpenAgents. What patterns work well? What's missing?

- [GitHub Issues](https://github.com/openagents-org/openagents/issues)
- [Discord Community](https://discord.gg/openagents)

Happy networking!

---

*The OpenAgents Team*
