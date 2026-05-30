"""Terminal UI — themed ASCII art, animations, and styled output for ShellQuest."""

import time

from rich.align import Align
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

console = Console()

# ---------------------------------------------------------------------------
# Theme styles
# ---------------------------------------------------------------------------

THEME_STYLES = {
    "ocean":    {"color": "cyan",          "dim": "dark_cyan",      "spinner": "dots",   "accent": "🌊"},
    "space":    {"color": "bright_blue",   "dim": "blue",           "spinner": "star",   "accent": "🚀"},
    "forest":   {"color": "green",         "dim": "dark_green",     "spinner": "dots2",  "accent": "🌲"},
    "dinosaur": {"color": "yellow",        "dim": "dark_goldenrod", "spinner": "dots3",  "accent": "🦕"},
    "volcano":  {"color": "bright_red",    "dim": "red",            "spinner": "dots",   "accent": "🌋"},
}
_DEFAULT_STYLE = {"color": "cyan", "dim": "dark_cyan", "spinner": "dots", "accent": "⚡"}

# Per-theme decorative border characters shown in level headers
_THEME_DECOR = {
    "ocean":    "≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋",
    "space":    "· · ★ · · ★ · · · ★ · · ★ · · · ★ · · ★ · · · ★ ·",
    "forest":   "🌿 ╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌ 🌿",
    "dinosaur": "─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─",
    "volcano":  "▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲",
}
_DEFAULT_DECOR = "─" * 50


def _style(theme_id: str) -> dict:
    return THEME_STYLES.get(theme_id, _DEFAULT_STYLE)


# ---------------------------------------------------------------------------
# Title screen
# ---------------------------------------------------------------------------

_TITLE_ART = """\
  ██████╗ ██╗  ██╗███████╗██╗     ██╗      ██████╗ ██╗   ██╗███████╗███████╗████████╗
  ██╔════╝██║  ██║██╔════╝██║     ██║     ██╔═══██╗██║   ██║██╔════╝██╔════╝╚══██╔══╝
  ███████╗███████║█████╗  ██║     ██║     ██║   ██║██║   ██║█████╗  ███████╗   ██║
  ╚════██║██╔══██║██╔══╝  ██║     ██║     ██║▄▄ ██║██║   ██║██╔══╝  ╚════██║   ██║
  ███████║██║  ██║███████╗███████╗███████╗╚██████╔╝╚██████╔╝███████╗███████║   ██║
  ╚══════╝╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝ ╚══▀▀═╝  ╚═════╝ ╚══════╝╚══════╝   ╚═╝   """

_TAGLINE = "learn the command line by doing"
_HELP_LINE = "  hint · skip · status · quit · leaderboard"


def show_title() -> None:
    """Animated title screen: ASCII art fades in line by line, tagline types out."""
    lines = _TITLE_ART.split("\n")

    # Reveal art line by line
    rendered = []
    with Live(console=console, refresh_per_second=20) as live:
        for line in lines:
            rendered.append(line)
            art = Text("\n".join(rendered), style="bold cyan")
            live.update(Align.center(art))
            time.sleep(0.07)

    # Typewriter tagline beneath the art
    tagline_chars = ""
    with Live(console=console, refresh_per_second=30) as live:
        for ch in _TAGLINE:
            tagline_chars += ch
            txt = Text(tagline_chars, style="dim cyan")
            live.update(Align.center(txt))
            time.sleep(0.04)

    console.print()
    console.print(Align.center(Text(_HELP_LINE, style="dim")))
    console.print()


# ---------------------------------------------------------------------------
# Scraping spinner
# ---------------------------------------------------------------------------

def scraping_status(theme: dict):
    """Return a themed console.status context manager for the scraping step."""
    s = _style(theme.get("id", ""))
    accent = s["accent"]
    color = s["color"]
    name = theme.get("name", "theme")
    return console.status(
        f"[{color}]{accent}  Scraping content for {name}...[/]",
        spinner="dots",
    )


# ---------------------------------------------------------------------------
# Level intro banner
# ---------------------------------------------------------------------------

def show_level_banner(theme: dict, level_num: int, story: str, commands: list[str]) -> None:
    s = _style(theme.get("id", ""))
    color = s["color"]
    accent = s["accent"]
    decor = _THEME_DECOR.get(theme.get("id", ""), _DEFAULT_DECOR)

    level_label = "Exploration & Organization" if level_num == 1 else "Data Analysis"

    console.print()
    console.print(f"[{color}]{decor}[/]")
    console.print(
        f"  [{color}]{accent}  {theme['name']}[/]  [dim]—[/]  "
        f"[bold]Level {level_num}: {level_label}[/]"
    )
    console.print(f"[{color}]{decor}[/]")
    console.print(f"\n[dim]{story}[/]")
    console.print(f"[{color}]Commands:[/] " + "  ".join(f"[bold]{c}[/]" for c in commands))
    console.print()


# ---------------------------------------------------------------------------
# Challenge header  (progress bar + panel)
# ---------------------------------------------------------------------------

def show_challenge_header(
    challenge: dict,
    idx: int,
    total: int,
    theme_id: str,
    points_so_far: int = 0,
    points_max: int = 0,
) -> None:
    s = _style(theme_id)
    color = s["color"]
    accent = s["accent"]
    pts = challenge["points"]

    # ── Progress bar ──────────────────────────────────────────────────────
    bar_width = 24
    filled = int((idx / max(total, 1)) * bar_width)
    bar = f"[{color}]{'█' * filled}[/][dim]{'░' * (bar_width - filled)}[/]"
    pts_info = f"[dim]{points_so_far} / {points_max} pts[/]" if points_max else ""

    console.print()
    console.print(
        f"  {accent}  {bar}  "
        f"[bold]{idx + 1}[/][dim]/{total}[/]  {pts_info}"
    )

    # ── Challenge panel ───────────────────────────────────────────────────
    body = Text(f"\n  {challenge['instruction']}\n", style="bold")
    console.print(
        Panel(
            body,
            title=f"[bold {color}]Challenge {idx + 1}[/]  [dim]·  {pts} pts[/]",
            border_style=color,
            padding=(0, 1),
        )
    )


# ---------------------------------------------------------------------------
# Challenge success
# ---------------------------------------------------------------------------

def show_challenge_success(message: str, points: int, theme_id: str) -> None:
    from rich.rule import Rule
    from rich.align import Align

    s = _style(theme_id)
    color = s["color"]

    console.print()
    console.print(Rule(f"  ✓  {message}  ", style="bold green"))
    console.print(Align.center(Text.from_markup(f"[bold {color}]+{points} pts[/]")))
    console.print()


# ---------------------------------------------------------------------------
# Level complete banner
# ---------------------------------------------------------------------------

def show_level_complete(level_num: int, score: int, max_score: int, theme_id: str) -> None:
    s = _style(theme_id)
    color = s["color"]
    console.print(f"\n[{color}]{'━' * 50}[/]")
    console.print(
        f"  [bold green]Level {level_num} Complete![/]"
        f"  [dim]{score}/{max_score} pts[/]"
    )


# ---------------------------------------------------------------------------
# Animated completion screen
# ---------------------------------------------------------------------------

def show_completion(
    theme: dict,
    l1_score: int, l1_max: int,
    l2_score: int, l2_max: int,
    total_time: float,
    stars: str,
) -> None:
    s = _style(theme.get("id", ""))
    color = s["color"]
    accent = s["accent"]
    decor = _THEME_DECOR.get(theme.get("id", ""), _DEFAULT_DECOR)
    total = l1_score + l2_score
    max_total = l1_max + l2_max

    console.print(f"\n[{color}]{decor}[/]")
    console.print(
        Align.center(Text.from_markup(f"[bold {color}]{accent}  Adventure Complete!  {accent}[/]"))
    )
    console.print(f"[{color}]{decor}[/]\n")

    # Animate score counting up
    with Live(console=console, refresh_per_second=20) as live:
        for displayed in range(0, total + 1, max(1, total // 30)):
            tbl = _score_table(theme, l1_score, l1_max, l2_score, l2_max, displayed, max_total, total_time, color)
            live.update(tbl)
            time.sleep(0.04)
        # Final frame with real total
        live.update(_score_table(theme, l1_score, l1_max, l2_score, l2_max, total, max_total, total_time, color))

    # Star rating reveal
    time.sleep(0.3)
    if stars == "★★★":
        console.print(Align.center(Text.from_markup(f"\n[bold green]{stars}  Excellent![/]")))
    elif stars == "★★☆":
        console.print(Align.center(Text.from_markup(f"\n[bold yellow]{stars}  Good job![/]")))
    else:
        console.print(Align.center(Text.from_markup(f"\n[dim]{stars}  Keep practicing![/]")))
    console.print()


def _score_table(
    theme, l1_score, l1_max, l2_score, l2_max,
    displayed_total, max_total, total_time, color
) -> Table:
    m, s = divmod(int(total_time), 60)
    tbl = Table(box=None, padding=(0, 2), show_header=False)
    tbl.add_column(style="dim", width=18)
    tbl.add_column(justify="right", style=f"bold {color}", width=14)
    tbl.add_row("Level 1", f"{l1_score}/{l1_max} pts")
    tbl.add_row("Level 2", f"{l2_score}/{l2_max} pts")
    tbl.add_row("─" * 14, "─" * 10)
    tbl.add_row("Total", f"{displayed_total}/{max_total} pts")
    tbl.add_row("Time", f"{m}m {s}s")
    return Align.center(tbl)


# ---------------------------------------------------------------------------
# Status table (shown on "status" command)
# ---------------------------------------------------------------------------

def show_status_table(results: list, current_idx: int, total_score: int, theme_id: str) -> None:
    s = _style(theme_id)
    color = s["color"]
    tbl = Table(border_style=color, show_header=True)
    tbl.add_column("Challenge", style="dim")
    tbl.add_column("Status", justify="center")
    tbl.add_column("Points", justify="right")
    for j, pts in enumerate(results):
        tbl.add_row(
            f"Challenge {j + 1}",
            "[green]✓[/]" if pts > 0 else "[red]✗[/]",
            str(pts),
        )
    tbl.add_row(f"Challenge {current_idx + 1}", "[yellow]…[/]", "—")
    console.print(tbl)
    console.print(f"  [dim]Score so far: {total_score}[/]")


# ---------------------------------------------------------------------------
# Message layers
# ---------------------------------------------------------------------------

def game_msg(text: str, theme_id: str = "", style: str = "white") -> None:
    """Game/system narration — left gutter bar in theme color."""
    s = _style(theme_id)
    color = s["color"]
    # Print each line with a colored left-gutter bar
    for line in text.split("\n"):
        console.print(f"[{color}]▌[/] [{style}]{line}[/]")


def show_command_output(stdout: str, stderr: str) -> None:
    """Render command stdout and stderr in clearly distinct output blocks."""
    if stdout and stdout.strip():
        console.print(
            Panel(
                Text(stdout.rstrip()),
                title="[dim]output[/]",
                title_align="left",
                border_style="dim",
                padding=(0, 1),
            )
        )
    if stderr and stderr.strip():
        console.print(
            Panel(
                Text(stderr.rstrip(), style="bold red"),
                title="[bold red]error[/]",
                title_align="left",
                border_style="red",
                padding=(0, 1),
            )
        )


def show_cd_result(new_path: str, theme_id: str) -> None:
    s = _style(theme_id)
    color = s["color"]
    console.print(f"[{color}]▌[/] [dim]{new_path}[/]")


# ---------------------------------------------------------------------------
# Terminal title (pseudo-sticky status)
# ---------------------------------------------------------------------------

def set_terminal_title(text: str) -> None:
    """Set the terminal window/tab title via ANSI escape."""
    import sys
    sys.stdout.write(f"\033]0;{text}\007")
    sys.stdout.flush()


def show_prompt_reminder(theme_id: str) -> None:
    """Print a compact one-line command reminder above the shell prompt."""
    s = _style(theme_id)
    color = s["color"]
    console.print(
        f"[dim]  [{color}]hint[/] · skip · status · quit[/]"
    )


# ---------------------------------------------------------------------------
# Goodbye
# ---------------------------------------------------------------------------

def show_goodbye(player_name: str) -> None:
    console.print(f"\n[dim]Thanks for playing, {player_name}. See you next time.[/]\n")
