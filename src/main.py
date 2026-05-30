"""ShellQuest entry point.

Wires together the engine (sandbox, runner, checker, theme_builder) and the
integrations (Box, Apify) into the interactive game loop. Implemented in TICKET-7.
"""

import atexit
import json
import os
import signal
import sys
import time
import uuid
from datetime import datetime

import questionary
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.engine.sandbox import create_sandbox, seed_sandbox
from src.engine.runner import execute_command, handle_cd
from src.engine.checker import validate_challenge
from src.engine.theme_builder import build_level_from_theme
from src.integrations.box_client import init_box, save_player_state, load_player_state
from src.integrations.apify_client import scrape_theme_content, fetch_hint, fetch_github_profile

console = Console()
_active_cleanup = None


def main() -> None:
    """Launch the ShellQuest game loop."""
    global _active_cleanup

    def _cleanup_and_exit(sig=None, frame=None):
        if _active_cleanup:
            _active_cleanup()
        console.print("\n[dim]Thanks for playing![/]")
        sys.exit(0)

    signal.signal(signal.SIGINT, _cleanup_and_exit)
    atexit.register(lambda: _active_cleanup() if _active_cleanup else None)

    # Welcome banner
    console.print(Panel(
        "[bold cyan]SHELLQUEST[/]\n[dim]Learn the command line by doing[/]",
        border_style="cyan",
        padding=(1, 4),
    ))
    console.print(
        "[dim]  Type real shell commands to solve challenges\n"
        "  Type [cyan]hint[/] for help · [cyan]skip[/] to skip "
        "· [cyan]status[/] for progress · [cyan]quit[/] to exit\n[/]"
    )

    # Init Box (graceful if not configured or not yet implemented)
    try:
        init_box()
    except NotImplementedError:
        pass

    # Player setup
    try:
        name = questionary.text("What's your name?").ask()
        if not name:
            name = "Explorer"
        github_user = questionary.text(
            "GitHub username (optional, press Enter to skip):"
        ).ask()
    except KeyboardInterrupt:
        console.print("\n[dim]Thanks for playing![/]")
        return

    player = {
        "id": str(uuid.uuid4()),
        "name": name,
        "github_username": github_user or "",
        "github_avatar": "",
        "github_bio": "",
        "completed_themes": [],
        "total_score": 0,
    }

    if github_user:
        try:
            with console.status("[dim]Looking up your GitHub...[/]"):
                profile = fetch_github_profile(github_user)
            player["github_avatar"] = profile.get("avatar", "")
            player["github_bio"] = profile.get("bio", "")
            display = profile.get("name", name)
            console.print(f"[dim]Welcome, {display}![/]")
            if player["github_bio"]:
                console.print(f'[dim]"{player["github_bio"]}"[/]')
        except NotImplementedError:
            console.print(f"[dim]Welcome, {name}![/]")
    else:
        console.print(f"[dim]Welcome, {name}![/]")

    # Try to load existing state (best-effort)
    try:
        existing = load_player_state(player["id"])
    except NotImplementedError:
        existing = None
    if existing:
        player["completed_themes"] = existing.get("completed_themes", [])
        player["total_score"] = existing.get("total_score", 0)

    # Load themes
    themes_path = os.path.join(os.path.dirname(__file__), "data", "themes.json")
    with open(themes_path) as f:
        themes = json.load(f)["themes"]

    # Main selection loop
    while True:
        console.print()
        completed_ids = [t["theme_id"] for t in player["completed_themes"]]

        choices = []
        for t in themes:
            done = t["id"] in completed_ids
            result = next(
                (r for r in player["completed_themes"] if r["theme_id"] == t["id"]),
                None,
            )
            if done and result:
                label = f"✓ {result.get('stars', '')} {t['icon']} {t['name']}"
            else:
                label = f"  {t['icon']} {t['name']} — {t['description']}"
            choices.append(questionary.Choice(label, value=t["id"]))
        choices.append(questionary.Choice("  Quit", value="quit"))

        try:
            theme_id = questionary.select("Choose your adventure:", choices=choices).ask()
        except KeyboardInterrupt:
            theme_id = None

        if not theme_id or theme_id == "quit":
            console.print("[dim]Thanks for playing![/]")
            break

        theme = next(t for t in themes if t["id"] == theme_id)

        # Scrape content (Apify → Wikipedia fallback handled inside)
        with console.status(f"[cyan]Building your {theme['name']} adventure...[/]"):
            try:
                scraped = scrape_theme_content(theme)
            except NotImplementedError:
                scraped = None
            if not scraped:
                scraped = _wikipedia_fallback(theme)

        if not scraped:
            console.print("[red]Couldn't build this theme. Try another.[/]")
            continue

        level = build_level_from_theme(theme, scraped)

        # Create and seed sandbox
        try:
            sandbox_path, cleanup = create_sandbox()
        except Exception as e:
            console.print(f"[red]Couldn't create sandbox: {e}[/]")
            continue

        _active_cleanup = cleanup
        seed_sandbox(sandbox_path, level["files"])

        # ── Level 1 ──────────────────────────────────────────────────────────
        console.print(f"\n[bold yellow]{level['title']}[/]")
        console.print("[bold]Level 1: Exploration & Organization[/]")
        console.print(f"[dim]{level['story_level_1']}[/]")
        console.print("[cyan]Commands:[/] " + ", ".join(level["commands_taught_l1"]))

        l1_result = _play_challenges(level["level_1_challenges"], sandbox_path, theme)

        if l1_result is None:
            cleanup()
            _active_cleanup = None
            continue

        l1_score, l1_max, l1_time = l1_result

        console.print(f"\n[yellow]{'━' * 50}[/]")
        console.print(f"[bold green]Level 1 Complete! Score: {l1_score}/{l1_max}[/]\n")

        try:
            proceed = questionary.confirm(
                "Ready for Level 2? The data needs analysis now.", default=True
            ).ask()
        except KeyboardInterrupt:
            proceed = False

        if not proceed:
            _save_theme_result(player, theme, l1_score, l1_max, 0, 0, int(l1_time))
            cleanup()
            _active_cleanup = None
            continue

        # ── Level 2 ──────────────────────────────────────────────────────────
        console.print("\n[bold]Level 2: Data Analysis[/]")
        console.print(f"[dim]{level['story_level_2']}[/]")
        console.print("[cyan]Commands:[/] " + ", ".join(level["commands_taught_l2"]))

        l2_result = _play_challenges(level["level_2_challenges"], sandbox_path, theme)

        if l2_result is None:
            _save_theme_result(player, theme, l1_score, l1_max, 0, 0, int(l1_time))
            cleanup()
            _active_cleanup = None
            continue

        l2_score, l2_max, l2_time = l2_result

        # ── Final summary ─────────────────────────────────────────────────────
        total_score = l1_score + l2_score
        total_max = l1_max + l2_max
        total_time = l1_time + l2_time

        console.print(f"\n[yellow]{'━' * 50}[/]")
        console.print(f"[bold yellow]{theme['icon']} Adventure Complete![/]")
        console.print(f"  Level 1: {l1_score}/{l1_max} pts")
        console.print(f"  Level 2: {l2_score}/{l2_max} pts")
        console.print(f"  Total:   {total_score}/{total_max} pts")
        console.print(f"  Time:    {_fmt_time(total_time)}")

        if total_score >= total_max * 0.8:
            stars = "★★★"
            console.print(f"\n[green]{stars} Excellent![/]")
        elif total_score >= total_max * 0.5:
            stars = "★★☆"
            console.print(f"\n[yellow]{stars} Good job![/]")
        else:
            stars = "★☆☆"
            console.print(f"\n[dim]{stars} Keep practicing![/]")

        _save_theme_result(
            player, theme, l1_score, l1_max, l2_score, l2_max, int(total_time), stars
        )
        cleanup()
        _active_cleanup = None
        time.sleep(1)


# ---------------------------------------------------------------------------
# Wikipedia fallback (used when Apify client is not yet implemented)
# ---------------------------------------------------------------------------

def _wikipedia_fallback(theme: dict) -> list[dict] | None:
    import requests
    results = []
    for query in theme["scrape_queries"]:
        if "wikipedia.org/wiki/" not in query["url"]:
            continue
        title = query["url"].split("/wiki/")[-1]
        try:
            resp = requests.get(
                f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}",
                timeout=10,
                headers={"User-Agent": "ShellQuest/1.0"},
            )
            resp.raise_for_status()
            content = resp.json().get("extract", "")
            if content and len(content) > 50:
                results.append({
                    "url": query["url"],
                    "filename": query["filename"],
                    "content": content,
                })
        except Exception:
            continue
    return results or None


# ---------------------------------------------------------------------------
# Challenge loop
# ---------------------------------------------------------------------------

def _play_challenges(challenges: list, sandbox_path: str, theme: dict):
    """Play through a list of challenges.

    Returns (score, max_score, elapsed_seconds) or None if the player quit.
    """
    current_dir = sandbox_path
    start_time = time.time()
    total_score = 0
    max_score = sum(c["points"] for c in challenges)
    results = []

    for i, challenge in enumerate(challenges):
        console.print(f"\n[blue]{'━' * 50}[/]")
        console.print(
            f"[bold]Challenge {i + 1}/{len(challenges)}[/] "
            f"[dim]({challenge['points']} pts)[/]"
        )
        console.print(challenge["instruction"])

        hint_used = False
        points_earned = 0
        last_stdout = ""

        while True:
            rel = os.path.relpath(current_dir, sandbox_path)
            prompt_path = "~" if rel == "." else f"~/{rel}"

            try:
                user_input = console.input(f"[green]shellquest:{prompt_path}$ [/]")
            except (EOFError, KeyboardInterrupt):
                return None

            user_input = user_input.strip()
            if not user_input:
                continue

            # ── Meta-commands ─────────────────────────────────────────────
            if user_input == "hint":
                try:
                    with console.status("[dim]Fetching hint...[/]"):
                        hint = fetch_hint(challenge["hint_command"])
                    console.print(hint)
                except NotImplementedError:
                    console.print(f"[yellow]Hint: try the [cyan]{challenge['hint_command']}[/cyan] command[/]")
                hint_used = True
                continue

            elif user_input == "skip":
                console.print("[yellow]Skipped.[/]")
                break

            elif user_input == "status":
                tbl = Table(border_style="blue")
                tbl.add_column("Challenge")
                tbl.add_column("Status")
                tbl.add_column("Points", justify="right")
                for j, pts in enumerate(results):
                    tbl.add_row(
                        f"Challenge {j + 1}",
                        "[green]✓[/]" if pts > 0 else "[red]✗[/]",
                        str(pts),
                    )
                tbl.add_row(f"Challenge {i + 1}", "[yellow]...[/]", "—")
                console.print(tbl)
                console.print(f"[dim]Score so far: {total_score}[/]")
                continue

            elif user_input == "quit":
                return None

            # ── cd (handled separately — doesn't produce stdout) ──────────
            elif user_input.startswith("cd"):
                args = user_input[2:].strip() or "~"
                cd_result = handle_cd(args, current_dir, sandbox_path)
                if cd_result["error"]:
                    console.print(f"[red]{cd_result['error']}[/]")
                else:
                    current_dir = cd_result["new_dir"]
                    new_rel = os.path.relpath(current_dir, sandbox_path)
                    console.print("[dim]" + ("~" if new_rel == "." else f"~/{new_rel}") + "[/]")
                last_stdout = ""  # cd produces no stdout

            # ── Regular shell command ─────────────────────────────────────
            else:
                result = execute_command(user_input, current_dir, sandbox_path)
                if result["stdout"]:
                    out = result["stdout"]
                    console.print(out, end="" if out.endswith("\n") else "\n")
                if result["stderr"]:
                    err = result["stderr"]
                    console.print(f"[red]{err}[/]", end="" if err.endswith("\n") else "\n")
                last_stdout = result["stdout"]

            # ── Validate after every command (including cd) ───────────────
            check = validate_challenge(
                challenge["validation"],
                sandbox_path,
                current_dir,
                last_stdout=last_stdout,
            )

            if check["passed"]:
                points_earned = challenge["points"]
                if hint_used:
                    points_earned = int(points_earned * 0.8)
                total_score += points_earned
                console.print(f"[bold green]✓ {challenge['success_message']}[/]")
                console.print(f"[green]+{points_earned} pts[/]")
                time.sleep(0.3)
                break

        results.append(points_earned)

    elapsed = time.time() - start_time
    return total_score, max_score, elapsed


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------

def _save_theme_result(
    player: dict,
    theme: dict,
    l1_score: int,
    l1_max: int,
    l2_score: int,
    l2_max: int,
    total_time: int,
    stars: str = "",
) -> None:
    result = {
        "theme_id": theme["id"],
        "theme_name": theme["name"],
        "level_1_score": l1_score,
        "level_1_max": l1_max,
        "level_2_score": l2_score,
        "level_2_max": l2_max,
        "total_time_seconds": total_time,
        "stars": stars,
        "completed_at": datetime.now().isoformat(),
    }
    idx = next(
        (i for i, t in enumerate(player["completed_themes"]) if t["theme_id"] == theme["id"]),
        None,
    )
    if idx is not None:
        player["completed_themes"][idx] = result
    else:
        player["completed_themes"].append(result)

    player["total_score"] = sum(
        t["level_1_score"] + t["level_2_score"] for t in player["completed_themes"]
    )

    try:
        with console.status("[dim]Saving progress...[/]"):
            save_player_state(player)
        console.print("[dim]Progress saved![/]")
    except NotImplementedError:
        console.print("[dim]Progress saved locally.[/]")


def _fmt_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s}s"


if __name__ == "__main__":
    main()
