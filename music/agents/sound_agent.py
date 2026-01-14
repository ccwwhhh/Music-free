import os
import re
import base64
import tempfile
from pathlib import Path
from typing import Optional, Tuple, List
import numpy as np
import pretty_midi
from openagents.models.event import Event, EventVisibility
from openagents.agents.worker_agent import WorkerAgent, EventContext
from midi2audio import FluidSynth



INSTRUMENT_PROGRAMS = {
    "piano": 0,        # Acoustic Grand Piano
    "violin": 40,      # Violin
    "bagpipe": 109,    # Bag pipe
    "flute": 73,       # Flute
    "guitar": 24,      # Nylon Guitar
    "organ": 16,       # Drawbar Organ
    "trumpet": 56,     # Trumpet
}


def _extract_text(msg: dict) -> str:
    # Try common OpenAgents message shapes
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


def _find_latest_notation_from_messages(messages: List[dict]) -> Optional[str]:
    """
    Find the newest message containing "Numbered notation:" and return the notation part.
    """
    for m in reversed(messages):
        text = _extract_text(m)
        if re.search(r"numbered notation\s*:", text, re.IGNORECASE):
            mm = re.search(r"numbered notation\s*:\s*([\s\S]+)$", text, re.IGNORECASE)
            if mm:
                return mm.group(1).strip()
    return None


def _parse_jianpu_tokens(jianpu: str) -> List[str]:
    """
    Accept tokens like: 1 2 3 #5 6 7, with commas/newlines.
    """
    s = jianpu.replace("\n", " ").replace(",", " ")
    tokens = [t.strip() for t in s.split() if t.strip()]
    return tokens


def _jianpu_token_to_midi(token: str, base_midi: int = 60) -> Optional[int]:
    """
    Very simple mapping:
    - base_midi=60 => C4 corresponds to '1' in C major.
    - '1'->C, '2'->D, '3'->E, '4'->F, '5'->G, '6'->A, '7'->B
    - '#5' means sharp.
    - '0' or '-' can be treated as rest.
    """
    token = token.strip()
    if token in ("0", "-", "rest"):
        return None

    sharp = False
    if token.startswith("#"):
        sharp = True
        token = token[1:]

    if not token.isdigit():
        return None

    degree = int(token)
    if degree < 1 or degree > 7:
        return None


    offsets = [0, 2, 4, 5, 7, 9, 11]
    midi_note = base_midi + offsets[degree - 1]
    if sharp:
        midi_note += 1
    return midi_note


def jianpu_to_pretty_midi(jianpu: str, bpm: int = 90, note_len_beats: float = 0.5, program: int = 0) -> pretty_midi.PrettyMIDI:
    pm = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    inst = pretty_midi.Instrument(program=program)

    tokens = _parse_jianpu_tokens(jianpu)

    beat_sec = 60.0 / float(bpm)
    dur = note_len_beats * beat_sec

    t = 0.0
    for tok in tokens:
        midi_note = _jianpu_token_to_midi(tok, base_midi=60)  # C4
        if midi_note is None:
            t += dur
            continue
        note = pretty_midi.Note(velocity=90, pitch=int(midi_note), start=t, end=t + dur)
        inst.notes.append(note)
        t += dur

    pm.instruments.append(inst)
    return pm


class SoundRenderAgent(WorkerAgent):


    default_agent_id = "SoundRender"

    def __init__(self, *args, soundfont_path: Optional[str] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.soundfont_path = soundfont_path or str(Path("FluidR3_GM.sf2"))
        self._pending = {
    "jianpu":None,
    "bpm": 90,
    "noteLen": 0.5,
    "instrument": "piano",
    "style": "swing"}

    async def _upload_bytes_to_shared_cache(self, file_bytes: bytes, filename: str, mime_type: str):
        file_data_b64 = base64.b64encode(file_bytes).decode("utf-8")
        upload_event = Event(
            event_name="shared_cache.file.upload",
            source_id=self.agent_id,
            payload={"filename": filename, "mime_type": mime_type, "file_data": file_data_b64},
            relevant_mod="openagents.mods.core.shared_cache",
            visibility=EventVisibility.MOD_ONLY,
        )
        resp = await self.client.send_event(upload_event)
        if not resp or not getattr(resp, "success", False):
            return None
        data = getattr(resp, "data", {}) or {}
        return data.get("cache_id")

    async def _parse_soundrender_controls(self, text: str):
        updates = {}
        if not text:
            return updates

        parts = re.split(r"[\n,]+", text.strip())
        for p in parts:

            for m in re.finditer(r"([a-zA-Z_]+)\s*[:：]\s*([^\s,]+)", p):
                k = m.group(1).strip().lower()
                v = m.group(2).strip()

                if k in ("instrument", "instr"):
                    updates["instrument"] = v.lower()
                elif k in ("bpm", "tempo", "temple"):
                    try:
                        updates["bpm"] = int(float(v))
                    except:
                        pass
                elif k in ("notelen", "note_len", "note_len_beats", "notelenbeats", "len"):
                    try:
                        updates["noteLen"] = float(v)
                    except:
                        pass
                elif k in ("style", "beat"):  # 你希望 beat 表示 swing 位置，这里兼容
                    updates["style"] = v.lower()

        print("[SoundRender][parse] updates =", updates)
        return updates

    async def react(self, context: EventContext):
        event = context.incoming_event
        if event.source_id == self.agent_id:
            return

        payload = event.payload or {}
        print("payload", payload)

        channel = payload.get("channel") or "general"
        source = (
                payload.get("source_id")
                or payload.get("sender_id")
                or payload.get("senderId")
                or payload.get("author")
                or payload.get("from")
        )
        if source == self.agent_id or source == "soundrenderagent":
            return

        text = _extract_text(payload) or _extract_text(getattr(event, "__dict__", {}) or {})
        if not text:
            text = _extract_text({"payload": payload})
        if not text:
            return

        lower = (text or "").strip().lower()

        async def post_text(msg: str):
            await self.workspace().channel(channel).post(msg)


        played = re.search(r"click to play", lower)
        has_control = re.search(
            r"\b(instrument|bpm|tempo|temple|notelen|note_len|note_len_beats|notelenbeats|style|beat)\s*[:：]",
            lower,
        )

        if has_control and not played:
            pending = self._pending.get(channel)
            print("[SoundRender][pending-before] ", pending, "type=", type(pending))

            if not pending:
                await post_text(
                    "No pending notation in this channel. Mention @SoundRender with a numbered notation first.\n"
                    "Example:\n@SoundRender Numbered notation: 1 2 3 4 5"
                )
                return


            if isinstance(pending, tuple):
                jianpu, bpm, note_len = pending
                instrument_pending = "piano"
                style_pending = "swing"
            else:
                jianpu = pending.get("jianpu")
                bpm = pending.get("bpm", 90)
                note_len = pending.get("noteLen", 0.5)
                instrument_pending = pending.get("instrument", "piano")
                style_pending = pending.get("style", "swing")


            updates = await self._parse_soundrender_controls(text or "")
            print("[SoundRender][react] updates =", updates)


            if "instrument" in updates:
                instrument_pending = updates["instrument"]
            if "style" in updates:
                style_pending = updates["style"]
            if "bpm" in updates:
                bpm = updates["bpm"]
            if "noteLen" in updates:
                note_len = updates["noteLen"]


            instrument = (instrument_pending or "piano").lower()
            if instrument not in INSTRUMENT_PROGRAMS:
                await post_text(
                    "Unknown instrument. Available:\n"
                    + "\n".join([f"- instrument: {k}" for k in INSTRUMENT_PROGRAMS.keys()])
                )
                return

            try:
                bpm = int(bpm)
            except Exception:
                bpm = 90
            bpm = max(30, min(240, bpm))

            try:
                note_len = float(note_len)
            except Exception:
                note_len = 0.5
            note_len = max(0.05, min(4.0, note_len))

            style = (style_pending or "swing").lower()
            if style not in ("swing", "straight"):
                style = "swing"


            if isinstance(pending, dict):
                pending["instrument"] = instrument
                pending["style"] = style
                pending["bpm"] = bpm
                pending["noteLen"] = note_len
                self._pending[channel] = pending

            payload_out = {
                "type": "play_request",
                "instrument": instrument,
                "jianpu": jianpu,
                "bpm": bpm,
                "note_len_beats": note_len,
                "style": style,
            }

            human = (
                f"▶ Click to play | instrument: {instrument} | "
                f"BPM: {bpm}, noteLen: {note_len}, style: {style}\n"
                f"numbered notation: {jianpu}"
            )

            await self.workspace().channel(channel).post(
                human + "\n",
                visibility=EventVisibility.MOD_ONLY,
            )
            return


        if "@soundrender" in lower or "soundrender" in lower:
            mm = re.search(r"numbered notation\s*:\s*([\s\S]+)$", text, re.IGNORECASE)
            jianpu = mm.group(1).strip() if mm else None

            if not jianpu:
                await post_text(
                    "No numbered notation found.\n"
                    "Please send format like:\n@SoundRender numbered notation: 1 2 3 4 5 ..."
                )
                return

            self._pending[channel] = {
                "jianpu": jianpu,
                "bpm": 90,
                "noteLen": 0.5,
                "instrument": "piano",
                "style": "swing",
            }

            await post_text(
                "SoundRender received. Reply with any of the following (one or multiple lines):\n"
                + "\n".join([f"- instrument: {k}" for k in INSTRUMENT_PROGRAMS.keys()])
                + "\n- bpm: 90   (or tempo: 90)\n"
                  "- noteLen: 0.5\n"
                  "- style: swing | straight\n\n"
                  "Example:\n"
                  "instrument: flute\n"
                  "bpm: 110\n"
                  "noteLen: 0.5\n"
                  "style: straight"
            )
            return

        return


import asyncio



async def main():
    """Run the SoundRender agent."""
    import argparse

    parser = argparse.ArgumentParser(description="SoundRender Agent")
    parser.add_argument("--host", default="localhost", help="Network host")
    parser.add_argument("--port", type=int, default=8700, help="Network port")
    parser.add_argument(
        "--url",
        default=None,
        help="Connection URL (e.g., grpc://localhost:8600 for direct gRPC)"
    )

    parser.add_argument(
        "--soundfont",
        default=None,
        help="Path to a GM SoundFont (.sf2), e.g. assets/soundfonts/FluidR3_GM.sf2"
    )

    args = parser.parse_args()


    agent = SoundRenderAgent(soundfont_path=args.soundfont) if args.soundfont else SoundRenderAgent()

    try:
        if args.url:
            await agent.async_start(url=args.url)
        else:
            await agent.async_start(network_host=args.host, network_port=args.port)

        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        await agent.async_stop()


if __name__ == "__main__":
    asyncio.run(main())