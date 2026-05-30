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

Implemented in TICKET-4.
"""


def scrape_theme_content(theme: dict) -> list[dict] | None:
    """Scrape recent web content for the given theme.

    Should target news articles, blog posts, encyclopedic reference pages,
    or any publicly crawlable source relevant to theme["name"]. NOT Wikipedia
    — that is the fallback in main.py when this function returns None.

    Args:
        theme: theme dict from themes.json, including "name", "id",
               "scrape_queries" (list of {"url", "filename"}).

    Returns:
        list of {"url": str, "filename": str, "content": str} dicts,
        one per scraped source, or None if scraping fails entirely.
        Content should be clean plain text, 500–3000 chars per item.
    """
    raise NotImplementedError


def fetch_shell_challenges(theme: dict) -> list[dict] | None:
    """Scrape real shell command questions relevant to the theme.

    Should target StackOverflow questions tagged 'bash' or 'shell', or
    similar developer Q&A sources. Questions should involve commands the
    game teaches (grep, wc, sort, uniq, find, pipes). The theme context
    can be used to filter or bias the scrape (e.g. space theme → questions
    about parsing log files, counting lines, searching text).

    Args:
        theme: theme dict from themes.json.

    Returns:
        list of {"title": str, "body": str, "commands": list[str]} dicts
        representing real questions, or None on failure.
        "commands" is a best-effort list of shell commands mentioned in
        the question body so the caller can match them to challenges.
    """
    raise NotImplementedError
