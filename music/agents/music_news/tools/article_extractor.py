# tools/article_extractor.py

# Simple article extractor that fetches a web page, summarizes it, and returns card-ready fields.

import requests
from bs4 import BeautifulSoup
from transformers import pipeline
summarizer = pipeline("summarization", model="facebook/bart-large-cnn")


def extract_article(url: str) -> dict:
    # Fetch the page and parse basic metadata + main paragraphs.
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    html = resp.text
    soup = BeautifulSoup(html, "html.parser")


    og_title = soup.find("meta", property="og:title")
    title = (
        og_title["content"].strip()
        if og_title and og_title.get("content")
        else (soup.title.string.strip() if soup.title else "Untitled")
    )


    og_img = soup.find("meta", property="og:image")
    image_url = og_img["content"].strip() if og_img and og_img.get("content") else ""


    desc = ""
    og_desc = soup.find("meta", property="og:description")
    if og_desc and og_desc.get("content"):
        desc = og_desc["content"].strip()
    else:
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            desc = meta_desc["content"].strip()


    paragraphs: list[str] = []
    article = soup.find("article")
    if article:
        for p in article.find_all("p"):
            txt = p.get_text(strip=True)
            if len(txt) > 40:
                paragraphs.append(txt)


    if not paragraphs:
        for p in soup.find_all("p"):
            txt = p.get_text(strip=True)
            if len(txt) > 40:
                paragraphs.append(txt)


    full_text = " ".join(paragraphs)


    if full_text:
        try:

            result = summarizer(
                full_text,
                max_length=120,
                min_length=40,
                do_sample=False,
                truncation=True,
            )
            summary = result[0]["summary_text"]
        except Exception:

            summary = desc or (full_text[:200] + "...")
    else:
        summary = desc or "News snapshot"


    max_chars = 1500
    truncated_paragraphs: list[str] = []
    total = 0
    for p in paragraphs:
        l = len(p)
        if total + l <= max_chars:
            truncated_paragraphs.append(p)
            total += l
        else:
            remain = max_chars - total
            if remain > 0:
                truncated_paragraphs.append(p[:remain] + "...")
            break

    return {
        "title": title,
        "image_url": image_url,
        "summary": summary,
        "caption": summary,
        "paragraphs": truncated_paragraphs or ["Content unavailable."],
    }

