"""Challenge checker.

Validates whether a challenge has been solved. Level 1 uses state-based checks
(inspecting the sandbox filesystem); Level 2 uses output-based checks (inspecting
the player's most recent stdout). Implemented in TICKET-3.
"""


def validate_challenge(
    validation: dict,
    sandbox_path: str,
    current_dir: str,
    last_stdout: str = "",
) -> dict:
    """Check whether a challenge's success condition is met.

    Args:
        validation: dict with "type" and optional "target"/"expected".
        sandbox_path: root of the sandbox directory.
        current_dir: the player's current working directory.
        last_stdout: stdout from the player's most recent command
            (used by player_output_* validation types).

    Returns:
        {"passed": bool, "message": str}
    """
    raise NotImplementedError
