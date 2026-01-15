import base64
import mimetypes
import os
from dataclasses import dataclass
from typing import Optional, Dict, Any

import aiohttp

from openagents.models.event import Event


CACHE_DOWNLOAD_URL_TEMPLATE = "http://localhost:8600/cache/download/{cache_id}"
# 如果你的 networkBaseUrl 不是 localhost:8600，把这里改掉，或从环境变量读


@dataclass
class DownloadResult:
    filename: str
    mime_type: str
    file_size: int
    file_content_b64: str


class WorkspaceFilesAdapter:
    """
    Minimal files adapter:
    - Input: cache_id (file_id) from Studio message attachment
    - Action: HTTP download bytes from cache service
    - Output: Emit thread.file.download_response with {file:{filename,mime_type,file_size,file_content}}
    """

    mod_id = "openagents.mods.workspace.files"

    def __init__(self, client):
        self.client = client  # AgentClient

    async def handle_event(self, event: Event) -> Optional[Dict[str, Any]]:
        """
        This adapter mainly serves as a helper called by agents, but you can also
        optionally respond to explicit events if your system dispatches them here.
        """
        return {"success": True}

    async def download_cache_file(
        self,
        cache_id: str,
        filename: str,
        mime_type: Optional[str] = None,
        download_url_template: str = CACHE_DOWNLOAD_URL_TEMPLATE,
    ) -> DownloadResult:
        if not cache_id:
            raise RuntimeError("Missing cache_id/file_id")

        url = download_url_template.format(cache_id=cache_id)

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"Cache download failed {resp.status}: {text[:200]}")
                data = await resp.read()

        mt = mime_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        b64 = base64.b64encode(data).decode("utf-8")
        return DownloadResult(
            filename=filename,
            mime_type=mt,
            file_size=len(data),
            file_content_b64=b64,
        )

    async def emit_download_response(
        self,
        target_agent_id: str,
        source_id: str,
        filename: str,
        mime_type: str,
        file_size: int,
        file_content_b64: str,
    ):
        """
        Emit `thread.file.download_response` so WorkerAgent will call on_file_received().
        WorkerAgent expects payload.file.{filename,file_content,mime_type,file_size}. :contentReference[oaicite:2]{index=2}
        """
        ev = Event(
            event_name="thread.file.download_response",
            source_id=source_id,
            destination_id=f"agent:{target_agent_id}",
            payload={
                "file": {
                    "filename": filename,
                    "mime_type": mime_type,
                    "file_size": file_size,
                    "file_content": file_content_b64,  # base64 string
                }
            },
        )
        await self.client.send_event(ev)
