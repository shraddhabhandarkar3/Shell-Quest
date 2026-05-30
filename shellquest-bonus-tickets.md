# Bonus Tickets — Unique Sponsor Integrations

These are add-on tickets to the main plan. Implement after TICKET-8 (integration is working). Each is ~30 min of work. They don't change any existing code — they add new functions and wire them into the game loop at specific points.

---

## TICKET-11: Apify bonus — StackOverflow challenge scraping

**Owner:** Whoever is free after TICKET-8
**Depends on:** TICKET-4 (apify_client.py exists), TICKET-7 (game loop exists)
**Time estimate:** 30 min

### What it does

After completing both levels, the player unlocks a "Bonus Round" that presents a real question scraped from StackOverflow. The question is tagged `bash` — a real developer asked it, and now the player has to solve it in the sandbox.

### Where it hooks in

- New function in `apify_client.py`
- One new block in `main.py` after Level 2 completes, before the final score summary

### Prompt

```
Add a bonus challenge feature powered by StackOverflow scraping.

1. Add to src/integrations/apify_client.py:

def fetch_stackoverflow_challenge() -> dict | None:
    """
    Scrape a beginner bash question from StackOverflow.
    Returns {"title": str, "hint": str} or None on failure.
    """
    if not _apify_enabled:
        return None

    try:
        items = _call_crawler(
            ["https://stackoverflow.com/questions/tagged/"
             "bash?tab=votes&pagesize=15"],
            timeout=20)

        if not items:
            return None

        text = items[0].get("text", "") or \
            items[0].get("markdown", "")

        # Extract question titles from the scraped page
        # SO question titles appear as linked text in the listing
        # Look for lines that look like questions (end with ?)
        # or are short actionable phrases
        import re
        lines = text.split("\n")
        questions = []
        for line in lines:
            line = line.strip()
            if (20 < len(line) < 120 and
                ("how" in line.lower() or
                 "find" in line.lower() or
                 "list" in line.lower() or
                 "count" in line.lower() or
                 "delete" in line.lower() or
                 "remove" in line.lower() or
                 "search" in line.lower() or
                 line.endswith("?")) and
                not line.startswith("http") and
                not line.startswith("[") and
                "vote" not in line.lower() and
                "answer" not in line.lower()):
                questions.append(line)

        if not questions:
            return None

        # Pick a random question
        import random
        q = random.choice(questions[:10])

        return {
            "title": q,
            "hint": "This is a real question from StackOverflow. "
                "Try your best — there's no single right answer."
        }

    except Exception:
        return None


2. Add to src/main.py, right after Level 2 completes and before
   the final score summary:

        # Bonus round (after l2_result, before final summary)
        bonus_score = 0
        so_challenge = fetch_stackoverflow_challenge()
        if so_challenge:
            console.print(f"\n[yellow]{'━' * 50}[/]")
            console.print(
                "[bold magenta]⭐ BONUS ROUND[/] "
                "[dim]— real question from StackOverflow[/]")
            console.print(
                f"\nA real developer asked:\n"
                f"[bold]\"{so_challenge['title']}\"[/]\n")
            console.print(
                "[dim]Try to solve it in the sandbox. Type "
                "'done' when finished or 'skip' to skip.[/]")

            while True:
                rel = os.path.relpath(current_dir, sandbox_path)
                prompt_path = "~" if rel == "." else f"~/{rel}"
                try:
                    user_input = console.input(
                        f"[magenta]bonus:{prompt_path}$ [/]")
                except EOFError:
                    break

                user_input = user_input.strip()
                if not user_input:
                    continue
                if user_input in ("done", "skip"):
                    if user_input == "done":
                        bonus_score = 10
                        console.print(
                            "[green]✓ +10 bonus points![/]")
                    else:
                        console.print("[yellow]Skipped![/]")
                    break
                elif user_input == "quit":
                    break
                elif user_input.startswith("cd"):
                    args = user_input[2:].strip() or "~"
                    cd_result = handle_cd(
                        args, current_dir, sandbox_path)
                    if cd_result["error"]:
                        console.print(
                            f"[red]{cd_result['error']}[/]")
                    else:
                        current_dir = cd_result["new_dir"]
                else:
                    result = execute_command(
                        user_input, current_dir, sandbox_path)
                    if result["stdout"]:
                        console.print(result["stdout"],
                            end="" if result["stdout"].endswith(
                                "\n") else "\n")
                    if result["stderr"]:
                        console.print(
                            f"[red]{result['stderr']}[/]")

        # Add bonus to total
        total_score = l1_score + l2_score + bonus_score
        total_max = l1_max + l2_max + (10 if so_challenge else 0)

Note: The bonus round is self-assessed (player types "done" when
they think they solved it). This is intentional — SO questions
are open-ended and can't be auto-validated. The point is the
experience of tackling a real problem, not the score.

If Apify is not configured or the scrape fails, the bonus round
silently doesn't appear. No error, no fallback needed — it's
a bonus.
```

### Acceptance criteria

- With Apify configured: bonus round appears after Level 2 with a real SO question
- Without Apify: bonus round silently skips, game ends normally
- Player can type commands, type "done" for points, or "skip"
- Bonus points are added to the final score
- No crashes if StackOverflow page structure changes (graceful None return)

### Why judges care

"These aren't our challenges — they're scraped live from StackOverflow. Apify crawls the page, extracts real developer questions, and presents one as a bonus round. You can't do this with a REST API because StackOverflow's API doesn't give you the same ranked, browsable listing."

---

## TICKET-12: Box bonus — Shareable completion certificate

**Owner:** Whoever is free after TICKET-8
**Depends on:** TICKET-5 (box_client.py exists), TICKET-7 (game loop exists)
**Time estimate:** 20 min

### What it does

After completing a theme, the game generates a text report card, uploads it to Box, creates a shared public link, and prints the URL. The player can share this link with anyone — it renders in Box's native file preview without login.

### Where it hooks in

- New function in `box_client.py`
- One call in `main.py` right after saving player state

### Prompt

```
Add a shareable completion certificate feature using Box shared
links.

1. Add to src/integrations/box_client.py:

def create_completion_certificate(player: dict,
                                   theme: dict,
                                   l1_score: int, l1_max: int,
                                   l2_score: int, l2_max: int,
                                   total_time: int,
                                   stars: str) -> str | None:
    """
    Generate a completion report, upload to Box, create a
    shared link. Returns the shared URL or None.
    """
    if not _box_enabled:
        return None

    total = l1_score + l2_score
    total_max_score = l1_max + l2_max
    from datetime import datetime
    now = datetime.now()

    # Build the certificate content
    content = f"""
╔══════════════════════════════════════════════════╗
║            SHELLQUEST COMPLETION REPORT          ║
╚══════════════════════════════════════════════════╝

Player:  {player['name']}{f" (@{player['github_username']})" if player.get('github_username') else ''}
Theme:   {theme['icon']} {theme['name']}
Date:    {now.strftime('%B %d, %Y')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

RESULTS
  Level 1 (Exploration):   {l1_score}/{l1_max} pts
  Level 2 (Analysis):      {l2_score}/{l2_max} pts
  Total:                   {total}/{total_max_score} pts
  Time:                    {total_time // 60}m {total_time % 60}s
  Rating:                  {stars}

COMMANDS PRACTICED
  Level 1: ls, cat, mkdir, mv, cp
  Level 2: grep, wc, sort, uniq, pipes (|)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Verified by ShellQuest — powered by Box & Apify
""".strip()

    try:
        import io
        filename = (
            f"shellquest-{theme['id']}-"
            f"{player['name'].lower().replace(' ', '-')}-"
            f"{now.strftime('%Y%m%d')}.txt")

        folder = _client.folder(BOX_STATE_FOLDER_ID)
        stream = io.BytesIO(content.encode("utf-8"))

        # Check if file exists already (replaying same theme)
        existing = _find_file_in_folder(folder, filename)
        if existing:
            existing.update_contents_with_stream(stream)
            uploaded = existing
        else:
            uploaded = folder.upload_stream(stream, filename)

        # Create a shared link with open access
        shared_file = _client.file(uploaded.id)
        shared_file.create_shared_link(
            access="open",
            allow_download=True
        )

        # Get the shared link URL
        file_with_link = _client.file(uploaded.id).get(
            fields=["shared_link"])
        url = file_with_link.shared_link["url"]

        return url

    except Exception as e:
        console.print(
            f"[dim][Box] Certificate creation failed: {e}[/]")
        return None


2. Add to src/main.py in the _save_theme_result function,
   right after save_player_state succeeds:

        # Generate shareable certificate
        from src.integrations.box_client import (
            create_completion_certificate)
        cert_url = create_completion_certificate(
            player, theme,
            l1_score, l1_max, l2_score, l2_max,
            total_time, stars)
        if cert_url:
            console.print(
                f"\n[cyan]Your completion certificate:[/]")
            console.print(f"[bold blue]{cert_url}[/]")
            console.print(
                "[dim]Share this link — anyone can view it, "
                "no login needed![/]")

That's it. The certificate generates and uploads automatically.
If Box isn't configured, nothing happens — no error, no message.
```

### Acceptance criteria

- After completing a theme with Box configured: a `.txt` file appears in the Box folder
- The shared link URL is printed to the terminal
- Opening the URL in a browser shows the certificate in Box's file preview (no login required)
- Replaying the same theme updates the existing certificate (no duplicates)
- Without Box configured: no certificate, no error
- The certificate content looks clean in Box's plain text preview

### Why judges care

"After completing a theme, Box generates a shareable completion certificate with a public link. Click it — it renders right in Box's file preview, no login needed. You could send this to a manager or put it in a portfolio. This uses Box's shared link API and native file preview — features that are core to Box and don't exist in generic file storage."

---

## Integration into the dependency graph

```
Existing tickets...
  TICKET-8 (integration)
    ├── TICKET-9  (demo/README)
    ├── TICKET-10 (hardening)
    ├── TICKET-11 (Apify bonus — SO challenges)  ← NEW
    └── TICKET-12 (Box bonus — certificates)     ← NEW
```

TICKET-11 and TICKET-12 are independent of each other. Assign one to each person after TICKET-8 is done. Both can be implemented in parallel.

---

## Updated demo script additions

Add to DEMO.md after the existing demo sections:

```
BONUS ROUND (20 sec):
- After Level 2, bonus round appears automatically
- "This question was scraped live from StackOverflow by Apify"
- Type a command or two, then type "done"
- "Real questions, from real developers, powered by real scraping"

CERTIFICATE (15 sec):
- Show the shared link URL in the terminal
- Click it → opens in browser → Box file preview
- "A shareable certificate, hosted on Box, public link,
  no login needed. Try doing that with localStorage."
```

---

## Updated sponsor summary

| Sponsor | Use | Can you do this without it? |
|---------|-----|-----------------------------|
| **Apify** | Scrape Wikipedia for themed game content | Partially (Wikipedia has an API, but it returns summaries, not full articles) |
| **Apify** | Scrape tldr.sh for command hints | Yes (GitHub raw fallback) |
| **Apify** | Scrape GitHub profiles | Yes (GitHub API) |
| **Apify** | **Scrape StackOverflow for real bonus challenges** | **No — SO's API doesn't give ranked tag listings. Needs a crawler.** |
| **Box** | Persist player state as JSON | Yes (any storage works) |
| **Box** | **Shareable completion certificate with public link + native preview** | **No — Box's shared links + file preview are platform-specific features.** |

The bolded rows are your headline sponsor moments in the demo.
