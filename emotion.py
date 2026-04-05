# emotion.py — In-process emotion state (happiness, anger, trust), scoped per player

_DEFAULTS: dict[str, int] = {"happiness": 50, "anger": 20, "trust": 40}

# Keyed by (player_id, character) → emotion dict
_emotions: dict[tuple[str, str], dict[str, int]] = {}


def get_emotions(player_id: str, char: str) -> dict[str, int]:
    """Return current emotion state for (player, character), initialising to defaults if absent."""
    return _emotions.setdefault((player_id, char), dict(_DEFAULTS))


def update_emotions(player_id: str, char: str, delta: dict[str, int]) -> None:
    """Apply an integer delta to each named emotion, clamping values to [0, 100]."""
    state = get_emotions(player_id, char)
    for key, value in delta.items():
        if key in state:
            state[key] = max(0, min(100, state[key] + value))
