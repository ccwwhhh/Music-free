
# Agent that periodically fetches music news, renders them as newspaper-style cards, and posts to a channel.
from pathlib import Path
import tempfile
import asyncio
import sys
import base64
from pathlib import Path
from openagents.models.event import Event, EventVisibility
# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))
from tools.card_render import render_newspaper_html, html_to_image
from openagents.agents.worker_agent import WorkerAgent
from tools.news_fetcher import fetch_hackernews_top, fetch_hackernews_new,fetch_nme_music_news
from tools.news_fetcher import fetch_rollingstone_music_top
from html.parser import HTMLParser


class NewsHunterAgent(WorkerAgent):
    # Default identifier used when this agent registers with the workspace.
    default_agent_id = "News-hunter"

    def __init__(self, fetch_interval: int = 60, **kwargs):

        super().__init__(**kwargs)
        # fetch_interval controls how often we poll for new stories.
        self.fetch_interval = fetch_interval
        self.posted_urls = set()
        self._hunting_task = None

    async def on_startup(self):
        # Start the background task once the agent is connected.
        print(f"News Hunter connected! Starting news hunt loop (interval: {self.fetch_interval}s)")
        self._hunting_task = asyncio.create_task(self._hunt_news_loop())

    async def on_shutdown(self):
        # Gracefully cancel the background loop on shutdown.
        if self._hunting_task:
            self._hunting_task.cancel()
            try:
                await self._hunting_task
            except asyncio.CancelledError:
                pass
        print("News Hunter disconnected.")

    async def _hunt_news_loop(self):
        # Main polling loop: periodically fetch and post news.
        await asyncio.sleep(5)

        while True:
            try:
                await self._fetch_and_post_news()
            except Exception as e:
                print(f"Error in news hunt loop: {e}")


            await asyncio.sleep(self.fetch_interval)

    async def _upload_bytes_to_shared_cache(
            self,
            file_bytes: bytes,
            filename: str,
            mime_type: str = "image/jpeg",
    ) -> str | None:
        """
        Upload a file to the shared cache and return its cache_id if successful.
        """
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
            await self.workspace().channel("music-news").post(
                f"shared_cache upload failed: {err}"
            )
            return None

        data = getattr(resp, "data", {}) or {}
        return data.get("cache_id")

    async def _fetch_and_post_news(self):
        # Fetch a batch of stories and post a subset that have not been seen before.
        print("Hunting for news...")

        stories = fetch_nme_music_news(limit=5)


        if not stories:
            print("No stories fetched from NME.")
            return


        new_stories = [s for s in stories if s.get("url") not in self.posted_urls]

        if not new_stories:
            print("No new stories to post.")
            return

        for story in new_stories[:2]:
            await self._post_story(story)
            if story.get("url"):
                self.posted_urls.add(story["url"])
            await asyncio.sleep(2)

        print(f"Posted {min(len(new_stories), 2)} new stories. Total tracked: {len(self.posted_urls)}")

    def _parse_news(self, news_text: str) -> list:
        """
        Parse a markdown-like news summary into a list of story dicts.
        """
        import re
        stories = []
        lines = news_text.split('\n')

        current_story = {}
        for line in lines:
            stripped = line.strip()


            title_match = re.match(r'^\d+\.\s*\*\*(.+?)\*\*$', stripped)
            if title_match:

                if current_story.get('title') and current_story.get('url'):
                    stories.append(current_story)
                current_story = {'title': title_match.group(1)}
            elif stripped.startswith('🔗'):

                url = stripped.replace('🔗', '').strip()
                current_story['url'] = url
            elif stripped.startswith('⬆️'):

                score_match = re.search(r'(\d+)\s*points?', stripped)
                if score_match:
                    current_story['score'] = int(score_match.group(1))


        if current_story.get('title') and current_story.get('url'):
            stories.append(current_story)

        return stories

    async def _post_story(self, story: dict):
        # Render a single story into an image card and post it with text metadata.
        channel = "music-news"

        title = story.get("title", "Untitled")
        url = story.get("url", "")
        score = story.get("score", 0)
        summary = story.get("summary", "")

        parts = [f"📰 {title}"]
        if url:
            parts.append(f"🔗 {url}")
        if score is not None:
            parts.append(f"⬆️ {score} points on Rolling Stone")
        if summary:
            parts.append("")
            short = summary[:400]
            if len(summary) > 400:
                short += "..."
            parts.append(short)

        message_text = "\n".join(parts)
        DEFAULT_IMAGE_URL = (
            "https://images.unsplash.com/photo-1511379938547-c1f69419868d"
            "?auto=format&fit=crop&w=800&q=80"
        )

        image_url = story.get("image_url") or DEFAULT_IMAGE_URL
        body = story.get("summary") or story.get("body") or ""
        caption = (
                story.get("caption")
                or f"{title} – Rolling Stone"
        )
        paragraphs = (
                story.get("paragraphs")
                or f""
        )

        story_for_html = {
            **story,
            "image_url": image_url,
            "summary": body,
            "body": body,
            "caption": caption,
            "paragraphs":paragraphs,

        }

        tmp_dir = Path("./tmp_news_cards")
        tmp_dir.mkdir(exist_ok=True)

        html_path = tmp_dir / f"news_card.html"
        img_path = tmp_dir / f"news_card.jpg"

        html_result = render_newspaper_html(story_for_html, html_path)

        if isinstance(html_result, Path):
            html_path = html_result
        elif isinstance(html_result, str):
            html_path.write_text(html_result, encoding="utf-8")
        elif html_result is None:

            pass
        else:

            print("[NewsHunter] render_newspaper_html returned unexpected type:", type(html_result))

        try:
            img_path = html_to_image(html_path, img_path)
        except Exception as e:
            print(f"[NewsHunter] html_to_image failed: {e}")
            img_path = None


        if not img_path or not img_path.exists():
            await self.workspace().channel(channel).post(message_text)
            return


        try:
            with open(img_path, "rb") as f:
                img_bytes = f.read()
        except Exception as e:
            print(f"[NewsHunter] read image failed: {e}")
            await self.workspace().channel(channel).post(message_text)
            return

        cache_id = await self._upload_bytes_to_shared_cache(
            file_bytes=img_bytes,
            filename=img_path.name,
            mime_type="image/jpeg",
        )


        if not cache_id:
            await self.workspace().channel(channel).post(message_text)
            return


        await self.workspace().channel(channel).post(
            {
                "message": message_text,
                "text": message_text,
                "files": [
                    {

                        "file_id": cache_id,
                        "filename": img_path.name,
                        "size": len(img_bytes),
                        "mime_type": "image/jpeg",
                    }
                ],
            }
        )

        print(f"[NewsHunter] posted story with image card: {title[:50]}...")


async def main():
    """Run the news hunter agent."""
    import argparse

    parser = argparse.ArgumentParser(description="News Hunter Agent")
    parser.add_argument("--host", default="localhost", help="Network host")
    parser.add_argument("--port", type=int, default=8700, help="Network port")
    parser.add_argument("--interval", type=int, default=60, help="Fetch interval in seconds")
    args = parser.parse_args()

    agent = NewsHunterAgent(fetch_interval=args.interval)

    try:
        await agent.async_start(
            network_host=args.host,
            network_port=args.port,
        )


        print(f"News Hunter running. Press Ctrl+C to stop.")
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        await agent.async_stop()


if __name__ == "__main__":
    asyncio.run(main())
