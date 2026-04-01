# memory/short_term.py — In-process short-term memory (per session)

_MAX_ENTRIES = 5

# Keyed by character name → list of recent interaction strings
_short_term: dict[str, list[str]] = {}

def st_read(char: str) -> list[str]:
    """Return the last N short-term memory entries for a character."""
    return _short_term.get(char, [])


def st_write(char: str, entry: str) -> None:
    """Append an entry to a character's short-term memory, capping at _MAX_ENTRIES."""
    buf = _short_term.setdefault(char, [])
    buf.append(entry)
    if len(buf) > _MAX_ENTRIES:
        buf.pop(0)
