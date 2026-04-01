# emotion.py — In-process emotion state (happiness, anger, trust)

# Defaults and valid emotion keys
_DEFAULTS: dict[str, int] = {"happiness": 50, "anger": 20, "trust": 40}

_emotions: dict[str, dict[str, int]] = {}


def get_emotions(char: str) -> dict[str, int]:
    """Return the current emotion state for a character, initialising to defaults if absent."""
    return _emotions.setdefault(char, dict(_DEFAULTS))


def update_emotions(char: str, delta: dict[str, int]) -> None:
    """Apply an integer delta to each named emotion, clamping values to [0, 100]."""
    state = get_emotions(char)
    for key, value in delta.items():
        if key in state:
            state[key] = max(0, min(100, state[key] + value))
