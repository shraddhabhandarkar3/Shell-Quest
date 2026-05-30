"""Apify integration.

Two responsibilities:

1. Theme content scraping — given a theme (ocean, space, etc.), scrape the
   live web for recent news articles, blog posts, or reference pages about
   that topic. This produces the real text files that get seeded into the
   sandbox. Wikipedia is only a fallback used by main.py when Apify is not
   configured; Apify itself should target richer, more current sources.

2. Shell challenge sourcing — scrape StackOverflow (or a similar developer
   resource) for real, popular shell command questions tagged with the theme's
   domain. These questions become the basis for Level 2 challenges so players
   are solving problems that actual developers asked, not invented ones.

Both functions must degrade gracefully: if Apify is not configured or a scrape
fails, return None so the caller can fall back without crashing.

All scraping goes through one Apify Store actor — `apify/website-content-crawler`
(API id `apify~website-content-crawler`) — via the shared `_call_crawler` helper.

Implemented in TICKET-4.
"""

import os
import re

import requests
from rich.console import Console
from dotenv import load_dotenv

load_dotenv()
console = Console()

APIFY_TOKEN = os.environ.get("APIFY_API_TOKEN")
_apify_enabled = bool(APIFY_TOKEN)

if not _apify_enabled:
    console.print(
        "[dim][Apify] Not configured — main.py will use fallback content[/]")

APIFY_BASE = "https://api.apify.com/v2"
CRAWLER_ACTOR = "apify~website-content-crawler"

# Shell commands the game teaches — used to tag scraped questions.
_SHELL_COMMANDS = [
    "grep", "wc", "sort", "uniq", "find", "cat", "ls", "awk", "sed",
    "cut", "head", "tail", "tr", "xargs", "tee", "diff", "comm",
    "paste", "cp", "mv", "mkdir", "echo", "chmod",
]


def _call_crawler(
    urls: list[str],
    timeout: int = 30,
    crawler_type: str = "cheerio",
) -> list[dict]:
    """Run the website-content-crawler actor over a list of URLs.

    Internal helper. Returns the actor's dataset items (list of scraped page
    dicts). Raises on failure — callers must wrap in try/except and return None.

    Args:
        urls: pages to crawl (each becomes a start URL, depth 0).
        timeout: HTTP timeout in seconds for the synchronous run.
        crawler_type: "cheerio" for fast static HTML (Wikipedia, news),
            or "playwright" for JS-rendered / bot-protected pages.
    """
    response = requests.post(
        f"{APIFY_BASE}/acts/{CRAWLER_ACTOR}/run-sync-get-dataset-items",
        params={"token": APIFY_TOKEN},
        json={
            "startUrls": [{"url": u} for u in urls],
            "maxCrawlPages": len(urls),
            "crawlerType": crawler_type,
            "maxCrawlDepth": 0,
        },
        headers={"Content-Type": "application/json"},
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def _clean_scraped_text(text: str, max_chars: int = 3000) -> str:
    """Clean scraped markdown/text for use as readable game files."""
    # Remove markdown images: ![alt](src)
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
    # Remove link markup but keep the visible link text: [text](url) -> text
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    # Strip any stray HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Drop markdown header markers but keep the heading text
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Collapse 3+ blank lines down to a single blank line
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    # Trim to max length, preferring a sentence boundary if one is reasonably
    # close to the cut point (otherwise just hard-cut).
    if len(text) > max_chars:
        cut = text[:max_chars].rfind(".")
        text = text[: cut + 1] if cut > max_chars * 0.6 else text[:max_chars]
    return text.strip()


# === RESPONSIBILITY 1: Theme content scraping ===


def scrape_theme_content(theme: dict) -> list[dict] | None:
    """Scrape recent web content for the given theme.

    Crawls the URLs in theme["scrape_queries"] via Apify's website-content-crawler
    and returns clean plaintext per source. Does NOT fall back to Wikipedia
    internally — returns None on any failure so main.py's fallback kicks in.

    Returns:
        list of {"url": str, "filename": str, "content": str}, or None.
    """
    if not _apify_enabled:
        return None

    queries = theme.get("scrape_queries", [])
    if not queries:
        return None

    urls = [q["url"] for q in queries]

    try:
        items = _call_crawler(urls, timeout=45)
    except Exception as e:
        console.print(f"[dim][Apify] Theme scrape failed ({e})[/]")
        return None

    results = []
    for query in queries:
        matching = [it for it in items if query["url"] in it.get("url", "")]
        if not matching:
            continue
        raw = (
            matching[0].get("text", "")
            or matching[0].get("markdown", "")
            or ""
        )
        content = _clean_scraped_text(raw)
        # Enforce the 500–3000 char meaningful-content floor.
        if content and len(content) >= 500:
            results.append({
                "url": query["url"],
                "filename": query["filename"],
                "content": content,
            })

    if not results:
        return None

    console.print(
        f"[dim][Apify] Scraped {len(results)} pages for {theme['name']}[/]")
    return results


# === RESPONSIBILITY 2: Shell challenge sourcing ===


def fetch_shell_challenges(theme: dict) -> list[dict] | None:
    """Scrape real shell command questions from StackOverflow.

    Crawls the top `bash`-tagged questions and extracts beginner-friendly ones
    that mention commands the game teaches. The theme is accepted for signature
    compatibility and light biasing; the core source is the bash tag listing.

    Returns:
        list of {"title": str, "body": str, "commands": list[str]}, or None.
    """
    if not _apify_enabled:
        return None

    url = "https://stackoverflow.com/questions/tagged/bash?tab=votes&pagesize=20"

    try:
        # StackOverflow is bot-protected; cheerio handles its server-rendered
        # listing, but fall back to playwright if cheerio returns nothing.
        items = _call_crawler([url], timeout=20)
        if not items or not (items[0].get("text") or items[0].get("markdown")):
            items = _call_crawler([url], timeout=30, crawler_type="playwright")
    except Exception as e:
        console.print(f"[dim][Apify] Shell-challenge scrape failed ({e})[/]")
        return None

    if not items:
        return None

    text = items[0].get("text", "") or items[0].get("markdown", "") or ""

    challenges = []
    seen = set()
    for line in text.split("\n"):
        line = line.strip()
        # Heuristic: question titles are short actionable phrases.
        lower = line.lower()
        looks_like_question = (
            20 < len(line) < 120
            and not line.startswith("http")
            and not line.startswith("[")
            and "vote" not in lower
            and "answer" not in lower
            and (
                line.endswith("?")
                or any(lower.startswith(w) for w in (
                    "how", "what", "find", "list", "count",
                    "delete", "remove", "search", "why"))
            )
        )
        if not looks_like_question or line in seen:
            continue
        seen.add(line)

        commands = [c for c in _SHELL_COMMANDS
                    if re.search(rf"\b{re.escape(c)}\b", lower)]
        challenges.append({
            "title": line,
            "body": line,
            "commands": commands,
        })
        if len(challenges) >= 10:
            break

    if not challenges:
        return None

    console.print(
        f"[dim][Apify] Found {len(challenges)} shell questions from "
        f"StackOverflow[/]")
    return challenges
