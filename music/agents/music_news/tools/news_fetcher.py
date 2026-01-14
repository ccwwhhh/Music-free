"""
News Fetcher Tools
Fetches tech news from various sources including Hacker News.
"""

import requests
from typing import Optional
from datetime import datetime
from html.parser import HTMLParser
import re
from bs4 import BeautifulSoup
class NMEExcerptParser(HTMLParser):
    """从 NME 的 summary HTML 中提取 第一张图片 + 纯文本内容"""

    def __init__(self):
        super().__init__()
        self.image_url = None
        self.text_parts = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "img" and self.image_url is None:
            for k, v in attrs:
                if k.lower() == "src":
                    self.image_url = v
                    break

    def handle_data(self, data):
        if data and data.strip():
            self.text_parts.append(data.strip())


def parse_nme_summary(summary_html: str):
    if not summary_html:
        return "", None
    parser = NMEExcerptParser()
    parser.feed(summary_html)

    text = " ".join(parser.text_parts)
    lower = text.lower()
    idx = lower.find("the post ")
    if idx != -1:
        text = text[:idx].strip()

    return text, parser.image_url
def fetch_nme_full_article(url: str) -> dict:
    """
    抓取 NME 文章正文和主图。
    返回:
      {
        "body": "整篇纯文本",
        "paragraphs": ["段1", "段2", ...],
        "image_url": "https://..."
      }
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        )
    }
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # ---------- 1. 主图：优先用 og:image ----------
    image_url = None
    og_img = soup.find("meta", attrs={"property": "og:image"})
    if og_img and og_img.get("content"):
        image_url = og_img["content"]

    # ---------- 2. 正文容器：多候选 selector 兜底 ----------
    article_node = None

    candidate_selectors = [
        # Newspaper 主题常见写法
        ("div", {"class": re.compile(r"\btd-post-content\b")}),
        # WordPress 里很常见的正文标记
        ("div", {"itemprop": "articleBody"}),
        ("div", {"class": re.compile(r"\bentry-content\b")}),
        # 再退一步，整个 <article>
        ("article", {}),
    ]

    for name, attrs in candidate_selectors:
        node = soup.find(name, attrs)
        if node is not None:
            article_node = node
            break


    if article_node is None:
        article_node = soup.body or soup


    paragraphs: list[str] = []
    for p in article_node.find_all("p"):
        text = p.get_text(strip=True)
        if text:
            paragraphs.append(text)

    body = "\n\n".join(paragraphs)

    return {
        "body": body,
        "paragraphs": paragraphs,
        "image_url": image_url,
    }
def fetch_hackernews_top(count: int = 5) -> str:
    """
    Fetch top stories from Hacker News.

    Args:
        count: Number of stories to fetch (default 5, max 30)

    Returns:
        Formatted string with top stories
    """
    try:
        count = min(max(1, count), 30)  # Clamp between 1 and 30

        # Fetch top story IDs
        response = requests.get(
            "https://hacker-news.firebaseio.com/v0/topstories.json",
            timeout=10
        )
        response.raise_for_status()
        story_ids = response.json()[:count]

        stories = []
        for story_id in story_ids:
            story_response = requests.get(
                f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json",
                timeout=10
            )
            if story_response.ok:
                story = story_response.json()
                if story and story.get("title"):
                    stories.append({
                        "title": story.get("title", ""),
                        "url": story.get("url", f"https://news.ycombinator.com/item?id={story_id}"),
                        "score": story.get("score", 0),
                        "comments": story.get("descendants", 0),
                        "by": story.get("by", "unknown")
                    })

        if not stories:
            return "No stories found."

        result = f"📰 Top {len(stories)} Hacker News Stories:\n\n"
        for i, story in enumerate(stories, 1):
            result += f"{i}. **{story['title']}**\n"
            result += f"   🔗 {story['url']}\n"
            result += f"   ⬆️ {story['score']} points | 💬 {story['comments']} comments | 👤 {story['by']}\n\n"

        return result

    except Exception as e:
        return f"Error fetching Hacker News: {str(e)}"


def fetch_hackernews_new(count: int = 5) -> str:
    """
    Fetch newest stories from Hacker News.

    Args:
        count: Number of stories to fetch (default 5, max 30)

    Returns:
        Formatted string with new stories
    """
    try:
        count = min(max(1, count), 30)

        response = requests.get(
            "https://hacker-news.firebaseio.com/v0/newstories.json",
            timeout=10
        )
        response.raise_for_status()
        story_ids = response.json()[:count]

        stories = []
        for story_id in story_ids:
            story_response = requests.get(
                f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json",
                timeout=10
            )
            if story_response.ok:
                story = story_response.json()
                if story and story.get("title"):
                    stories.append({
                        "title": story.get("title", ""),
                        "url": story.get("url", f"https://news.ycombinator.com/item?id={story_id}"),
                        "score": story.get("score", 0),
                        "by": story.get("by", "unknown")
                    })

        if not stories:
            return "No new stories found."

        result = f"🆕 {len(stories)} Newest Hacker News Stories:\n\n"
        for i, story in enumerate(stories, 1):
            result += f"{i}. **{story['title']}**\n"
            result += f"   🔗 {story['url']}\n"
            result += f"   ⬆️ {story['score']} points | 👤 {story['by']}\n\n"

        return result

    except Exception as e:
        return f"Error fetching Hacker News: {str(e)}"


def fetch_hackernews_best(count: int = 5) -> str:
    """
    Fetch best stories from Hacker News (highest voted recent stories).

    Args:
        count: Number of stories to fetch (default 5, max 30)

    Returns:
        Formatted string with best stories
    """
    try:
        count = min(max(1, count), 30)

        response = requests.get(
            "https://hacker-news.firebaseio.com/v0/beststories.json",
            timeout=10
        )
        response.raise_for_status()
        story_ids = response.json()[:count]

        stories = []
        for story_id in story_ids:
            story_response = requests.get(
                f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json",
                timeout=10
            )
            if story_response.ok:
                story = story_response.json()
                if story and story.get("title"):
                    stories.append({
                        "title": story.get("title", ""),
                        "url": story.get("url", f"https://news.ycombinator.com/item?id={story_id}"),
                        "score": story.get("score", 0),
                        "comments": story.get("descendants", 0),
                        "by": story.get("by", "unknown")
                    })

        if not stories:
            return "No stories found."

        result = f"⭐ {len(stories)} Best Hacker News Stories:\n\n"
        for i, story in enumerate(stories, 1):
            result += f"{i}. **{story['title']}**\n"
            result += f"   🔗 {story['url']}\n"
            result += f"   ⬆️ {story['score']} points | 💬 {story['comments']} comments | 👤 {story['by']}\n\n"

        return result

    except Exception as e:
        return f"Error fetching Hacker News: {str(e)}"


import requests
import xml.etree.ElementTree as ET

ROLLINGSTONE_MUSIC_RSS = "https://www.rollingstone.com/music/feed"

def fetch_rollingstone_music_top(count: int = 5) -> str:
    """
    Fetch latest music stories from Rolling Stone RSS and
    return formatted text similar to fetch_hackernews_top, e.g.:

    1. **Title**
       🔗 https://...
       ⬆️ 0 points | 📰 Rolling Stone Music
    """
    resp = requests.get(ROLLINGSTONE_MUSIC_RSS, timeout=10)
    resp.raise_for_status()
    content = resp.content

    root = ET.fromstring(content)
    items = root.findall(".//item")

    lines = []
    for i, item in enumerate(items[:count], start=1):
        title = (item.findtext("title") or "Untitled").strip()
        link = (item.findtext("link") or "").strip()

        lines.append(f"{i}. **{title}**")
        lines.append(f"   🔗 {link}")

        lines.append(f"   ⬆️ 0 points | 📰 Rolling Stone Music")
        lines.append("")  # 空行分隔

    return "\n".join(lines)


import feedparser

NME_RSS_URL = "https://www.nme.com/news/music/rss"


def fetch_nme_music_news(limit: int = 5) -> list[dict]:
    feed = feedparser.parse("https://www.nme.com/news/music/rss")
    stories: list[dict] = []

    for entry in feed.entries[:limit]:
        raw_summary = getattr(entry, "summary", "") or ""
        summary_text, img_from_summary = parse_nme_summary(raw_summary)

        url = entry.link

        body = ""
        paragraphs = []
        img_from_page = None
        try:
            full = fetch_nme_full_article(url)
            body = full.get("body") or ""
            paragraphs = full.get("paragraphs") or []
            img_from_page = full.get("image_url")
        except Exception as e:
            print("[NME] fetch_nme_full_article error:", e)

        story = {
            "title": entry.title,
            "url": url,
            # 短摘要，用在消息里的预览
            "summary": summary_text or body[:200],
            # 正文，给报纸模板用
            "body": body,
            "paragraphs": paragraphs,
            # 优先：正文页图片 > summary 里的图片
            "image_url": img_from_page or img_from_summary,
        }
        stories.append(story)

    return stories


def fetch_url_content(url: str, max_length: int = 5000) -> str:
    """
    Fetch and extract text content from a URL.

    Args:
        url: The URL to fetch content from
        max_length: Maximum length of content to return (default 5000)

    Returns:
        Extracted text content from the URL
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; OpenAgents/1.0)"
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")

        if "text/html" in content_type:
            # Simple HTML text extraction (basic, no BeautifulSoup dependency)
            import re
            text = response.text
            # Remove script and style elements
            text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
            # Remove HTML tags
            text = re.sub(r'<[^>]+>', ' ', text)
            # Clean up whitespace
            text = re.sub(r'\s+', ' ', text).strip()
            # Decode HTML entities
            import html
            text = html.unescape(text)

            if len(text) > max_length:
                text = text[:max_length] + "..."

            return f"Content from {url}:\n\n{text}"
        else:
            return f"Content from {url} (non-HTML, {len(response.content)} bytes)"

    except Exception as e:
        return f"Error fetching URL: {str(e)}"
