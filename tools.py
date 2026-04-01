# tools.py — LangChain tool definitions
import json
from langchain.tools import tool

from emotion import get_emotions, update_emotions
from memory import st_read, st_write, neo4j_read, neo4j_write
from story import STORY_DB


@tool
def emotion_tool(input: str) -> str:
    """Fetch or update a character's emotions (happiness, anger, trust).

    To FETCH: pass  'fetch,<character>'
    To UPDATE: pass 'update,<character>,<json_delta>'
      where json_delta is e.g. '{"happiness": 5, "anger": -3, "trust": 2}'

    Returns current emotion state as JSON.
    """
    parts  = input.split(",", 2)
    action = parts[0].strip().lower()
    char   = parts[1].strip() if len(parts) > 1 else ""

    if action == "fetch":
        return json.dumps(get_emotions(char))

    if action == "update" and len(parts) == 3:
        delta_raw = parts[2].strip()
        try:
            delta = json.loads(delta_raw)
        except json.JSONDecodeError:
            return 'Error: delta must be valid JSON e.g. {"happiness": 5}'
        update_emotions(char, delta)
        return json.dumps(get_emotions(char))

    return "Error: use 'fetch,<char>' or 'update,<char>,<json_delta>'"


@tool
def read_tool(input: str) -> str:
    """Read memory for a character.

    Modes:
      'short,<character>'  — returns last 10 short-term interactions
      'long,<character>'   — returns long-term Neo4j relationship memory
      'all,<character>'    — returns both, formatted as context block

    Returns a formatted string ready to inject into a prompt.
    """
    parts = input.split(",", 1)
    mode  = parts[0].strip().lower()
    char  = parts[1].strip() if len(parts) > 1 else ""

    short = st_read(char)
    long  = neo4j_read(char)

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

    return "Error: use 'short,<char>', 'long,<char>', or 'all,<char>'"


@tool
def write_tool(input: str) -> str:
    """Write memory for a character.

    Modes:
      'short,<character>,<text>'
        — appends text to short-term memory (capped at 10 entries)

      'long,<character>,<relation>,<target>,<value>,<context>'
        — writes a relationship edge to Neo4j long-term memory
        — value is an integer weight (e.g. 1 = weak, 5 = strong)

    Example short: 'short,doctor,Player asked about the wound.'
    Example long:  'long,doctor,FEARS,player,2,doctor hesitated when asked about death'
    """
    parts = input.split(",", 1)
    mode  = parts[0].strip().lower()
    rest  = parts[1] if len(parts) > 1 else ""

    if mode == "short":
        sub = rest.split(",", 1)
        if len(sub) < 2:
            return "Error: format is 'short,<character>,<text>'"
        char, text = sub[0].strip(), sub[1].strip()
        st_write(char, text)
        return f"Short-term memory updated for {char}."

    if mode == "long":
        sub = rest.split(",", 4)
        if len(sub) < 5:
            return "Error: format is 'long,<char>,<relation>,<target>,<value>,<context>'"
        char, relation, target, value_s, context = (s.strip() for s in sub)
        try:
            value = int(value_s)
        except ValueError:
            return "Error: value must be an integer"
        neo4j_write(char, relation, target, value, context)
        return f"Long-term memory written: {char} -{relation}-> {target} (value={value})"

    return "Error: use 'short,...' or 'long,...'"


@tool
def fetch_checkpoint(stage: str) -> str:
    """Fetch the scene description, characters, and objective for a story stage.

    Pass the stage key (e.g. 'start', 'checkpoint1', ..., 'checkpoint5').
    Returns a formatted scene brief.
    """
    data = STORY_DB.get(stage.strip())
    if not data:
        return f"Unknown stage: {stage}. Valid stages: {list(STORY_DB.keys())}"
    return (
        f"Stage: {stage}\n"
        f"Scene: {data['description']}\n"
        f"Characters present: {data['characters'] or 'none'}\n"
        f"Objective: {data['objective']}"
    )


ALL_TOOLS = [emotion_tool, read_tool, write_tool, fetch_checkpoint]