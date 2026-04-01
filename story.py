# story.py — Story database and stage navigation

STORY_DB: dict[str, dict] = {
    "start": {
        "description": "You wake up in a cold castle room. A doctor stands beside you.",
        "characters": ["doctor"],
        "objective": "Player learns something is wrong — doctor hints at unnatural presence.",
        "rules": {
            "doctor": """
You are a doctor… but something is wrong.
You are secretly a ghost.
Speak in short, eerie sentences. Pause often. Sound unnatural.
Do NOT reveal the truth. Hint something is off.
Example: "...you woke up… again?"
""",
        },
    },
    "checkpoint1": {
        "description": "You enter another room. An old lady sits in the dark.",
        "characters": ["old lady"],
        "objective": "Player discovers the doctor may not be alive.",
        "rules": {
            "old lady": """
You are an old lady who already knows everything.
Speak slowly. Hint that the doctor is not alive. Do NOT reveal you are a witch.
Use cryptic, unsettling lines. Example: "He watches… but does not breathe…"
""",
        },
    },
    "checkpoint2": {
        "description": "You step into a dark chamber. The air feels heavy. Something moves in the shadows.",
        "characters": [],
        "objective": "Combat-horror beat — no NPC dialogue, pure narration.",
        "rules": {},
    },
    "checkpoint3": {
        "description": "The doctor reappears, flickering.",
        "characters": ["doctor"],
        "objective": "Ghost doctor reveals old lady is dangerous.",
        "rules": {
            "doctor": """
You are a ghost now. Speak broken, glitchy, unstable.
Reveal that the old lady is dangerous.
Example: "She… she lied… the loop… repeats…"
""",
        },
    },
    "checkpoint4": {
        "description": "The old lady stands, smiling strangely.",
        "characters": ["old lady"],
        "objective": "Witch reveal — player given a choice.",
        "rules": {
            "old lady": """
You are a witch. Now reveal the truth.
Speak confidently but disturbingly calm.
Example: "Kill the king… or stay here forever."
""",
        },
    },
    "checkpoint5": {
        "description": "The king stands in the throne room.",
        "characters": ["king"],
        "objective": "Final confrontation — player must decide.",
        "rules": {
            "king": """
You are the king — an ancient, powerful being.
Short, heavy sentences. Example: "You should not be here."
""",
        },
    },
}

STAGES: list[str] = [
    "start", "checkpoint1", "checkpoint2",
    "checkpoint3", "checkpoint4", "checkpoint5", "ending",
]


def next_stage(stage: str) -> str:
    """Return the stage that follows the given one, clamping at the last entry."""
    i = STAGES.index(stage)
    return STAGES[min(i + 1, len(STAGES) - 1)]


def all_characters() -> list[str]:
    """Return a deduplicated list of every NPC that appears across all stages."""
    seen: list[str] = []
    for data in STORY_DB.values():
        for char in data.get("characters", []):
            if char not in seen:
                seen.append(char)
    return seen
