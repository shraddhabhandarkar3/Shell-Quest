"""Apify integration.

Three responsibilities, each with a graceful fallback so the game never hangs or
crashes: (1) scrape Wikipedia articles to build themes, (2) fetch command hints
from tldr pages, (3) fetch GitHub profiles for player info. Implemented in TICKET-4.
"""


def scrape_theme_content(theme: dict) -> list[dict] | None:
    """Scrape all URLs in theme["scrape_queries"].

    Returns:
        list of {"url", "filename", "content"} dicts, or None on total failure.
    """
    raise NotImplementedError


def fetch_hint(command: str) -> str:
    """Fetch a usage hint for a shell command, formatted for the console."""
    raise NotImplementedError


def fetch_github_profile(username: str) -> dict:
    """Fetch a GitHub profile.

    Returns:
        {"name": str, "avatar": str, "bio": str}
    """
    raise NotImplementedError
