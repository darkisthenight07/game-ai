# short_term.py — Per-player short-term memory with JSON persistence

import json
import os
from pathlib import Path

_MAX_ENTRIES = 10
_STORE_DIR   = Path(os.getenv("MEMORY_STORE_DIR", "./memory_store"))

# Runtime cache: (player_id, char) → list[str]
_short_term: dict[tuple[str, str], list[str]] = {}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _player_path(player_id: str) -> Path:
    """Return the JSON path for a player's short-term memory file."""
    _STORE_DIR.mkdir(parents=True, exist_ok=True)
    # Sanitise player_id so it's safe as a filename
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in player_id)
    return _STORE_DIR / f"st_{safe}.json"


def _load_player(player_id: str) -> None:
    """Load a player's short-term memory from disk into the runtime cache (once)."""
    path = _player_path(player_id)
    if not path.exists():
        return
    try:
        raw: dict[str, list[str]] = json.loads(path.read_text(encoding="utf-8"))
        for char, entries in raw.items():
            key = (player_id, char)
            if key not in _short_term:           # don't overwrite live session data
                _short_term[key] = entries[-_MAX_ENTRIES:]
    except (json.JSONDecodeError, OSError):
        pass  # corrupted file — start fresh


def _save_player(player_id: str) -> None:
    """Persist all in-memory short-term entries for a player to disk."""
    path = _player_path(player_id)
    snapshot: dict[str, list[str]] = {
        char: entries
        for (pid, char), entries in _short_term.items()
        if pid == player_id
    }
    try:
        path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass  # best-effort — don't crash the game on a disk write failure


# Set of player IDs whose files have already been loaded this session
_loaded: set[str] = set()


def _ensure_loaded(player_id: str) -> None:
    if player_id not in _loaded:
        _load_player(player_id)
        _loaded.add(player_id)


# ── Public API ────────────────────────────────────────────────────────────────

def st_read(player_id: str, char: str) -> list[str]:
    """Return the last _MAX_ENTRIES short-term memory entries for (player, character)."""
    _ensure_loaded(player_id)
    return list(_short_term.get((player_id, char), []))


def st_write(player_id: str, char: str, entry: str) -> None:
    """Append an entry to (player, character) memory, cap at _MAX_ENTRIES, then persist."""
    _ensure_loaded(player_id)
    buf = _short_term.setdefault((player_id, char), [])
    buf.append(entry)
    if len(buf) > _MAX_ENTRIES:
        buf.pop(0)
    _save_player(player_id)


def st_all_chars(player_id: str) -> dict[str, list[str]]:
    """Return all character memories for a player (useful for debugging / save exports)."""
    _ensure_loaded(player_id)
    return {
        char: list(entries)
        for (pid, char), entries in _short_term.items()
        if pid == player_id
    }
