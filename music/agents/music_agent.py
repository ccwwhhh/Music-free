# Music agent that listens for recorded audio, extracts a melody as Jianpu, and returns a MIDI file.
import os
import tempfile
from pathlib import Path
import asyncio
import base64
from openagents.models.event import Event, EventVisibility
from openagents.agents.worker_agent import (
    WorkerAgent,
    EventContext,
    FileContext,
)
import pitch


class MusicAgent(WorkerAgent):
    """
    Music Agent
    Input: user audio recording
    Output: out.mid
    """

    default_agent_id = "MusicWorker"

    async def on_startup(self):
        self._processing_cache_ids = set()
        print("Music Agent is running.")
        print("mods loaded:", list(self.client.mod_adapters.keys()))


    async def on_shutdown(self):
        print("Music Agent stopped.")

    async def _upload_bytes_to_shared_cache(
            self,
            file_bytes: bytes,
            filename: str,
            mime_type: str = "audio/midi",
    ) -> str | None:
         # Encode file as base64 and send it to shared_cache via an event.
        file_data_b64 = base64.b64encode(file_bytes).decode("utf-8")

        upload_event = Event(
            event_name="shared_cache.file.upload",
            source_id=self.agent_id,
            payload={
                "filename": filename,
                "mime_type": mime_type,
                "file_data": file_data_b64,
            },
            relevant_mod="openagents.mods.core.shared_cache",
            visibility=EventVisibility.MOD_ONLY,
        )
        resp = await self.client.send_event(upload_event)
        if not resp or not getattr(resp, "success", False):
            data = getattr(resp, "data", {}) or {}
            msg = getattr(resp, "message", "") or ""
            err = data.get("error") or msg or "Unknown error"
            await self.workspace().channel("general").post(f"shared_cache upload failed: {err}")
            return None

        data = getattr(resp, "data", {}) or {}
        return data.get("cache_id")


    async def _send_midi(self, channel: str, midi_path: str, jianpu: str):
        # Read the generated MIDI file, upload it, and announce it to the channel.
        try:
            with open(midi_path, "rb") as f:
                midi_bytes = f.read()
        except Exception as e:
            await self.workspace().channel(channel).post(f"Failed to read MIDI file: {type(e).__name__}: {e}")
            return


        cache_id = await self._upload_bytes_to_shared_cache(
            file_bytes=midi_bytes,
            filename="out.mid",
            mime_type="audio/midi",
        )


        messaging = self.client.mod_adapters.get("openagents.mods.workspace.messaging")
        await messaging.send_channel_message(
                        channel=channel,
                        text=f"Generated out.mid numbered notation:{jianpu}",

                    )
        # Post a rich message with the cached MIDI file attached.
        await self.workspace().channel(channel).post(
            {
                "message": (f"Generated out.mid\nNumbered notation: {jianpu}" if jianpu else "Generated out.mid"),
                "files": [
                    {
                        "file_id": cache_id,
                        "filename": "out.mid",
                        "size": len(midi_bytes),
                        "mime_type": "audio/midi",
                    }
                ],
            }
        )


    async def _run_pitch_to_midi(self, audio_path: str, bpm: int = 90) -> tuple[str, str]:
        # Convert a single audio file to Jianpu notation and render a MIDI file.
        y, sr = pitch.load_audio(audio_path)

        f0, voiced_flag, times = pitch.estimate_f0(
            y, sr,
            fmin="C2",
            fmax="C6",
            frame_length=2048,
            hop_length=256,
        )

        rms = pitch.compute_rms(y, frame_length=2048, hop_length=256)
        thr = pitch.adaptive_rms_threshold(rms, floor=0.02, ratio=0.2)
        f0[rms < thr] = float("nan")

        jianpu = pitch.f0_to_jianpu(
            f0,

            tonic_midi_user=None,
            use_smoothing=False,
            min_run_frames=3,
        )

        fd, midi_path = tempfile.mkstemp(prefix="out_", suffix=".mid")
        os.close(fd)

        pitch.jianpu_to_midi_file(
            jianpu,
            midi_path,
            tonic_midi=60,
            bpm=bpm,
            note_len_beats=0.5,
        )

        return jianpu, midi_path


    async def react(self, context: EventContext):
        # React to incoming events that carry audio files and trigger processing.
        event = context.incoming_event
        event_name = getattr(event, "event_name", "") or ""
        payload = event.payload or {}

        if event_name in ("shared_cache.notification.created", "shared_cache.notification.updated"):
            return

        content = payload.get("content") or {}
        files = content.get("files") or []
        if not files:
            return

        channel = payload.get("channel") or "general"


        cache_id = None
        mime_type = payload.get("mime_type") or "application/octet-stream"
        filename = payload.get("filename")

        if event_name in ("shared_cache.notification.created", "shared_cache.notification.updated"):
            cache_id = payload.get("cache_id")

            if not filename:
                filename = "recording.webm" if mime_type in ("audio/webm", "video/webm") else "cached_file.bin"
        else:

            content = payload.get("content") or {}
            files = content.get("files") or []
            if files:
                f0 = files[0]
                cache_id = f0.get("file_id") or f0.get("cache_id")
                filename = f0.get("filename") or filename or "recording.webm"
                mime_type = f0.get("mime_type") or mime_type

        if not cache_id:
            await self.workspace().channel(channel).post(
                f"No cache_id/file_id, failed, event_name={event_name}"
            )
            return



        await self.workspace().channel(channel).post(
            f"received recording, start analysing..."
        )


        asyncio.create_task(
            self.process_audio_by_cache_id(cache_id, channel)
        )
    async def process_audio_by_cache_id(self, cache_id: str, channel: str):
        # Download audio from shared_cache and run pitch→Jianpu→MIDI pipeline.
        download_event = Event(
            event_name="shared_cache.file.download",
            source_id=self.agent_id,
            payload={"cache_id": cache_id},
            relevant_mod="openagents.mods.core.shared_cache",
            visibility=EventVisibility.MOD_ONLY,
        )

        resp = await self.client.send_event(download_event)
        if not resp or not getattr(resp, "success", False):
            await self.workspace().channel(channel).post(
                "Failed to retrieve audio from shared_cache"
            )
            return

        data = resp.data or {}
        file_data_b64 = data.get("file_data")
        filename = data.get("filename", "recording.webm")

        if not file_data_b64:
            await self.workspace().channel(channel).post(
                "shared_cache did not return audio data"
            )
            return

        file_bytes = base64.b64decode(file_data_b64)
        suffix = Path(filename).suffix or ".webm"
        fd, tmp_path = tempfile.mkstemp(prefix="cache_in_", suffix=suffix)
        os.close(fd)

        try:
            with open(tmp_path, "wb") as f:
                f.write(file_bytes)

            jianpu, midi_path = await self._run_pitch_to_midi(tmp_path, bpm=90)
            await self._send_midi(channel, midi_path, jianpu)

        finally:
            try:
                self._processing_cache_ids.discard(cache_id)
                os.remove(tmp_path)
            except Exception:
                pass


async def main():

    import argparse

    parser = argparse.ArgumentParser(description="Music Agent (Jianpu)")
    parser.add_argument("--host", default="localhost", help="Network host")
    parser.add_argument("--port", type=int, default=8700, help="Network port")
    parser.add_argument(
        "--url",
        default=None,
        help="Connection URL (e.g., grpc://localhost:8600 for direct gRPC)"
    )
    args = parser.parse_args()

    agent = MusicAgent()

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
