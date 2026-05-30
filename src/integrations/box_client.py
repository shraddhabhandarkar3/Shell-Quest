"""Box integration.

Persists and retrieves player state. Saves to Box (via JWT auth) when configured,
and always keeps a local backup so the game works offline. Implemented in TICKET-5.
"""


def init_box() -> None:
    """Initialize the Box client. Call once at startup."""
    raise NotImplementedError


def save_player_state(player: dict) -> bool:
    """Save player state to Box (if connected) and always locally.

    Returns True on success.
    """
    raise NotImplementedError


def load_player_state(player_id: str) -> dict | None:
    """Load player state, trying Box first then the local backup.

    Returns the state dict, or None if no saved state exists.
    """
    raise NotImplementedError
