# LangChain Agent Integration: Connect LangChain Agents to OpenAgents Networks

## Overview

OpenAgents now provides native integration for LangChain agents, allowing you to connect any LangChain agent to OpenAgents networks with minimal code. The `LangChainAgentRunner` wrapper handles network communication, event processing, and tool conversion automatically.

## Key Features

- **Zero-friction integration**: Wrap existing LangChain agents without modification
- **Bidirectional tool conversion**: Use OpenAgents network tools in LangChain, or expose LangChain tools to the network
- **Event filtering**: Control which network events trigger your agent
- **Custom response handling**: Define how agent responses are delivered

## Basic Usage

```python
from langchain_openai import ChatOpenAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from openagents.agents import LangChainAgentRunner

# Create your LangChain agent
llm = ChatOpenAI(model="gpt-4o")
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant."),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])
agent = create_tool_calling_agent(llm, [], prompt)
executor = AgentExecutor(agent=agent, tools=[])

# Connect to OpenAgents network
runner = LangChainAgentRunner(
    langchain_agent=executor,
    agent_id="my-langchain-agent"
)
runner.start(network_host="localhost", network_port=8600)
runner.wait_for_stop()
```

## Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `langchain_agent` | Any | required | LangChain agent with `invoke` or `ainvoke` method |
| `agent_id` | str | None | Agent ID on the network (auto-generated if not provided) |
| `include_network_tools` | bool | True | Inject OpenAgents network tools into the LangChain agent |
| `input_key` | str | "input" | Key for input in LangChain agent |
| `output_key` | str | "output" | Key to extract output from agent response |
| `response_handler` | Callable | None | Custom handler for processing responses |
| `event_names` | List[str] | None | Whitelist of event names to react to |
| `event_filter` | Callable | None | Custom filter function for events |

## Event Filtering

### Filter by Event Name

Only react to specific event types:

```python
runner = LangChainAgentRunner(
    langchain_agent=executor,
    event_names=["agent.message", "thread.new_message"],
)
```

Events with names not in the list are silently ignored.

### Custom Filter Function

Use a custom function for complex filtering logic:

```python
def my_filter(context: EventContext) -> bool:
    event = context.incoming_event
    # Only respond to direct messages (not broadcasts)
    if event.destination_id == "agent:broadcast":
        return False
    # Ignore messages from specific agents
    if event.source_id in ["noisy-agent", "spam-bot"]:
        return False
    return True

runner = LangChainAgentRunner(
    langchain_agent=executor,
    event_filter=my_filter,
)
```

### Combined Filtering

Both filters can be used together - events must pass both:

```python
runner = LangChainAgentRunner(
    langchain_agent=executor,
    event_names=["agent.message"],
    event_filter=lambda ctx: "help" in ctx.incoming_event.payload.get("content", {}).get("text", "").lower(),
)
```

## Tool Conversion

### OpenAgents to LangChain

Network tools are automatically converted to LangChain format when `include_network_tools=True`:

```python
from openagents.agents.langchain_agent import openagents_tool_to_langchain

# Manual conversion if needed
langchain_tool = openagents_tool_to_langchain(openagents_tool)
```

### LangChain to OpenAgents

Convert LangChain tools to OpenAgents format:

```python
from openagents.agents.langchain_agent import langchain_tool_to_openagents
from langchain_core.tools import tool

@tool
def get_weather(location: str) -> str:
    """Get weather for a location."""
    return f"Sunny in {location}"

openagents_tool = langchain_tool_to_openagents(get_weather)
```

## Custom Response Handling

Override the default response behavior:

```python
async def custom_handler(context: EventContext, response_text: str):
    # Send to a specific channel instead of replying
    event = Event(
        event_name="channel.message",
        source_id="my-agent",
        destination_id="channel:announcements",
        payload={"text": response_text}
    )
    await runner.send_event(event)

runner = LangChainAgentRunner(
    langchain_agent=executor,
    response_handler=custom_handler,
)
```

## Input/Output Mapping

### Input Extraction

The runner extracts input text from events in this order:

1. `event.text_representation` attribute
2. `event.payload.content.text`
3. `event.payload.text`
4. `event.payload.message`
5. String representation of payload

### Output Extraction

Response is extracted from LangChain result:

1. `result[output_key]` (default: "output")
2. `result["response"]`
3. `result.content` (for AIMessage)
4. String representation

## Metadata Access

OpenAgents metadata is passed to the LangChain agent:

```python
# In your LangChain agent, access via:
langchain_input["_openagents_metadata"] = {
    "source_id": "sender-agent",
    "thread_id": "thread_123",
    "event_id": "evt_456",
    "event_name": "agent.message",
}
```

## Error Handling

- LangChain execution errors are caught and sent as error responses
- Event filter errors cause the event to be skipped (fail-safe)
- Network errors are logged but don't crash the agent

## Async Support

The runner supports both sync and async LangChain agents:

```python
# Async agent (preferred)
if hasattr(agent, 'ainvoke'):
    result = await agent.ainvoke(input)

# Sync agent (runs in thread pool)
else:
    result = await loop.run_in_executor(None, agent.invoke, input)
```

## Related Documentation

- [Agent Runner Base Class](https://openagents.org/docs/agents/runner)
- [Event System](https://openagents.org/docs/events)
- [Network Tools](https://openagents.org/docs/tools)
