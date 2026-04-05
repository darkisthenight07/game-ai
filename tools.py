# tools.py — LangChain tool definitions
import json
from langchain.tools import tool

from emotion import get_emotions, update_emotions
from memory import st_read, st_write, neo4j_read, neo4j_write
from story import STORY_DB


# ── Emotion tool ──────────────────────────────────────────────────────────────

@tool
def emotion_tool(input: str) -> str:
    """Fetch or update a character's emotions (happiness, anger, trust).

    To FETCH: pass  'fetch,<player_id>,<character>'
    To UPDATE: pass 'update,<player_id>,<character>,<json_delta>'
      where json_delta is e.g. '{"happiness": 5, "anger": -3, "trust": 2}'

    Returns current emotion state as JSON.
    """
    parts  = input.split(",", 3)
    action = parts[0].strip().lower()

    if action == "fetch" and len(parts) >= 3:
        player_id, char = parts[1].strip(), parts[2].strip()
        return json.dumps(get_emotions(player_id, char))

    if action == "update" and len(parts) == 4:
        player_id, char = parts[1].strip(), parts[2].strip()
        delta_raw = parts[3].strip()
        try:
            delta = json.loads(delta_raw)
        except json.JSONDecodeError:
            return 'Error: delta must be valid JSON e.g. {"happiness": 5}'
        update_emotions(player_id, char, delta)
        return json.dumps(get_emotions(player_id, char))

    return "Error: use 'fetch,<player_id>,<char>' or 'update,<player_id>,<char>,<json_delta>'"


# ── Read tool ─────────────────────────────────────────────────────────────────

@tool
def read_tool(input: str) -> str:
    """Read memory for a character.

    Modes:
      'short,<player_id>,<character>'  — returns last 10 short-term interactions
      'long,<player_id>,<character>'   — returns long-term Neo4j relationship memory
      'all,<player_id>,<character>'    — returns both, formatted as context block

    Returns a formatted string ready to inject into a prompt.
    """
    parts = input.split(",", 2)
    if len(parts) < 3:
        return "Error: use 'short,<player_id>,<char>', 'long,...', or 'all,...'"

    mode      = parts[0].strip().lower()
    player_id = parts[1].strip()
    char      = parts[2].strip()

    short = st_read(player_id, char)
    long  = neo4j_read(player_id, char)

    if mode == "short":
        if not short:
            return f"[No short-term memory for {char}]"
        return "Short-term memory:\n" + "\n".join(f"  - {s}" for s in short)

    if mode == "long":
        if not long:
            return f"[No long-term memory for {char}]"
        return "Long-term memory:\n" + "\n".join(f"  - {l}" for l in long)

    if mode == "all":
        parts_out = []
        if short:
            parts_out.append("Short-term:\n" + "\n".join(f"  - {s}" for s in short))
        else:
            parts_out.append("[No short-term memory]")
        if long:
            parts_out.append("Long-term:\n" + "\n".join(f"  - {l}" for l in long))
        else:
            parts_out.append("[No long-term memory]")
        return "\n\n".join(parts_out)

    return "Error: use 'short,...', 'long,...', or 'all,...'"


# ── Write tool ────────────────────────────────────────────────────────────────

@tool
def write_tool(input: str) -> str:
    """Write memory for a character.

    Modes:
      'short,<player_id>,<character>,<text>'
        — appends text to short-term memory (capped at 10 entries, persisted to JSON)

      'long,<player_id>,<character>,<relation>,<target>,<value>,<context>'
        — writes a relationship edge to Neo4j long-term memory
        — value is an integer weight (e.g. 1 = weak, 5 = strong)
        — relation must be UPPERCASE_WITH_UNDERSCORES (e.g. FEARS, TRUSTS)

    Example short: 'short,player_1,doctor,Player asked about the wound.'
    Example long:  'long,player_1,doctor,FEARS,player,2,doctor hesitated when asked about death'
    """
    parts = input.split(",", 1)
    mode  = parts[0].strip().lower()
    rest  = parts[1] if len(parts) > 1 else ""

    if mode == "short":
        sub = rest.split(",", 2)
        if len(sub) < 3:
            return "Error: format is 'short,<player_id>,<character>,<text>'"
        player_id, char, text = sub[0].strip(), sub[1].strip(), sub[2].strip()
        st_write(player_id, char, text)
        return f"Short-term memory updated for {char} (player: {player_id})."

    if mode == "long":
        sub = rest.split(",", 5)
        if len(sub) < 6:
            return "Error: format is 'long,<player_id>,<char>,<relation>,<target>,<value>,<context>'"
        player_id, char, relation, target, value_s, context = (s.strip() for s in sub)
        try:
            value = int(value_s)
        except ValueError:
            return "Error: value must be an integer"
        try:
            neo4j_write(player_id, char, relation, target, value, context)
        except ValueError as exc:
            return f"Error: {exc}"
        return f"Long-term memory written: {char} -{relation}-> {target} (player: {player_id}, value={value})"

    return "Error: use 'short,...' or 'long,...'"


# ── Story tools (unchanged, no player_id needed) ──────────────────────────────

@tool
def fetch_checkpoint(stage: str) -> str:
    """Fetch the scene description, characters, and objective for a story stage.

    Pass the stage key (e.g. 'start', 'checkpoint1', ..., 'checkpoint6').
    Returns a formatted scene brief.
    """
    data = STORY_DB.get(stage.strip())
    if not data:
        return f"Unknown stage: {stage}. Valid stages: {list(STORY_DB.keys())}"
    return (
        f"Stage: {stage}\n"
        f"Scene: {data['description']}\n"
        f"Characters present: {data['characters'] or 'none'}\n"
        f"Objective: {data.get('objective', 'Progress through the scene naturally.')}"
    )


@tool
def fetch_story_arc(stage: str) -> str:
    """Return the full story arc with past, current, and upcoming stages.

    Pass the current stage key. Returns a structured context block so agents
    understand where the player is in the overall narrative — without leaking
    future plot details into character dialogue.
    """
    from story import STAGES
    current = stage.strip()
    idx     = STAGES.index(current) if current in STAGES else 0

    lines = [f"STORY ARC  (player is currently at: {current})\n"]
    for i, s in enumerate(STAGES):
        data  = STORY_DB.get(s, {})
        desc  = data.get("description", "").strip().splitlines()[0]
        chars = data.get("characters", [])
        prefix = "PAST" if i < idx else ("NOW" if i == idx else "AHEAD")
        lines.append(f"  {prefix} [{s}]  chars: {chars or ['none']}  |  {desc}")

    return "\n".join(lines)


ALL_TOOLS = [emotion_tool, read_tool, write_tool, fetch_checkpoint, fetch_story_arc]
