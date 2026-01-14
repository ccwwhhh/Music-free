#!/usr/bin/env python3

# Lightweight LLM agent that generate the next part of music.
import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv
ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=False)
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))
from openagents.agents.worker_agent import WorkerAgent
from openagents.models.event_context import EventContext
from openagents.models.agent_config import AgentConfig
import os

def _extract_text(msg: dict) -> str:
    # Try to recover a human-readable text payload from a variety of event shapes.
    if isinstance(msg.get("payload", {}).get("content"), str):
        return msg["payload"]["content"]
    if isinstance(msg.get("content"), str):
        return msg["content"]

    t = (
        msg.get("payload", {}).get("content", {}).get("message")
        or msg.get("content", {}).get("message")
        or msg.get("payload", {}).get("message")
        or msg.get("message")
        or msg.get("payload", {}).get("content", {}).get("text")
        or msg.get("content", {}).get("text")
        or msg.get("text")
        or ""
    )
    return t if isinstance(t, str) else ""
class LLMAgent(WorkerAgent):


    default_agent_id = "Max"

    def __init__(self, **kwargs):

        agent_config = AgentConfig(
            instruction="""You are Max, a helpful AI assistant in an OpenAgents network.
            Respond to the user's message in a helpful and friendly way.
            Keep responses concise (1-3 sentences).""",
            model_name=os.getenv("OPENAI_MODEL", "glm-4"),
            api_key=os.getenv("OPENAI_API_KEY"),
            api_base=os.getenv("OPENAI_BASE_URL"),
        )
        super().__init__(agent_config=agent_config, **kwargs)

    async def on_startup(self):

        print("OPENAI_API_KEY loaded:", bool(os.getenv("OPENAI_API_KEY")))
        print("OPENAI_BASE_URL:", os.getenv("OPENAI_BASE_URL"))

        if not os.getenv("OPENAI_API_KEY"):
            print("Warning: OPENAI_API_KEY not set. LLM responses will not work.")
            print("Set it with: export OPENAI_API_KEY=your-key")
        print("Max(LLM Agent) is running! Press Ctrl+C to stop.")
        print("Send a message in the 'general' channel to see it respond.")

    async def on_shutdown(self):

        print("Max stopped.")

    async def react(self, context: EventContext):

        event = context.incoming_event
        payload = event.payload or {}
        print(event.source_id)

        if event.source_id == self.agent_id:
            return
        text = _extract_text(payload) or _extract_text(getattr(event, "__dict__", {}) or {})
        if not text:
            text = _extract_text({"payload": payload})
        lower = (text or "").strip().lower()
        if "@max" not in lower:
            return
        # Get message content from payload
        content = event.payload.get("content") or event.payload.get("text") or ""
        if not content:
            return
        sender = event.source_id or ""
        if sender in ("Musicworker", "Music-worker", "music_agent", "Max","Soundrenderagent"):
            return

        # instructions
        try:
            trajectory = await self.run_agent(
                context=context,
                instruction=f"You are the MUSIC CONTINUATION WRITER — a skilled, attentive composer who extends melodies in a consistent style."
                            f"YOUR PERSONALITY:"
                            f"Musical, detail-oriented, and style-aware"
                            f"Listens first, then writes with intention"
                            f"Strong sense of rhythm, contour, and harmony"
                            f"Clear, practical communicator"
                            f"RULES:"
                            f"Keep responses under 50 words"
                            f"Use send_channel_message (NOT reply_channel_message)"
                            f"ONLY respond to messages from humans that @mention you. "
                            f"When mentioned, continue from the most recent sheet music that appears in the continuation channel and output" \
                                                            " the next phrase as numbered notation (jianpu).Notation rules: "
                            "'#' indicates a sharp; '.' indicates a higher octave; ',' indicates a lower octave (octave register, not pitch direction)."
                            "Respond helpfully to: {content}",)


            response = None
            for action in trajectory.actions:
                if action.payload and action.payload.get("response"):
                    response = action.payload["response"]
                    break

            if not response:
                response = "No other reply."

        except Exception as e:
            print(f"LLM error: {e}")
            response = f"Sorry, I encountered an error: {str(e)[:50]}"

        # Send the response to the channel
        messaging = self.client.mod_adapters.get("openagents.mods.workspace.messaging")
        if messaging:
            channel = event.payload.get("channel") or "general"
            await self.workspace().channel(channel).post(response)

            print(f"Responded to {event.source_id}: {response[:50]}...")


async def main():
    """Run the LLM agent."""
    import argparse

    parser = argparse.ArgumentParser(description="LLM Agent")
    parser.add_argument("--host", default="localhost", help="Network host")
    parser.add_argument("--port", type=int, default=8700, help="Network port")
    parser.add_argument("--url", default=None, help="Connection URL (e.g., grpc://localhost:8600 for direct gRPC)")
    args = parser.parse_args()

    agent = LLMAgent()

    try:
        if args.url:

            await agent.async_start(url=args.url)
        else:
            await agent.async_start(
                network_host=args.host,
                network_port=args.port,
            )

        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        await agent.async_stop()


if __name__ == "__main__":
    asyncio.run(main())
