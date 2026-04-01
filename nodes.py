# nodes.py — LangGraph node functions
import json
from config import llm
from emotion import get_emotions
from memory import st_write, neo4j_write
from state import AgentState
from story import STORY_DB
from tools import fetch_checkpoint, read_tool, emotion_tool, write_tool, ALL_TOOLS

llm_with_tools = llm.bind_tools(ALL_TOOLS)


# ── Input Reviewer ────────────────────────────────────────────────────────────

def input_reviewer_node(state: AgentState) -> AgentState:
    """Sanitizes player input — rejects off-story content, normalises tone."""
    result = llm.invoke(f"""
You are an input reviewer for a dark gothic horror game.
Your job: ensure the player's message is story-relevant and appropriate.

Rules:
- If the input is completely unrelated to the story (e.g. math questions, coding requests),
  replace it with: "[Player remains silent, watching cautiously.]"
- If the input is story-relevant but crude/aggressive beyond the game's tone,
  soften it slightly while preserving intent.
- Otherwise return it unchanged.
- Return ONLY the cleaned player text. No commentary, no quotes.

Player said: "{state['player_input']}"
""")
    state["sanitized_input"] = result.content.strip()
    return state


# ── Narrator ──────────────────────────────────────────────────────────────────

def narrator_node(state: AgentState) -> AgentState:
    """Drives story flow, narrates the scene, signals stage advancement."""
    scene  = fetch_checkpoint.invoke(state["stage"])
    result = llm.invoke(f"""
You are the narrator of a dark gothic horror story.

Current scene info:
{scene}

Your tasks:
1. Write a vivid 2-3 sentence atmospheric narration of the scene.
2. Decide if the current checkpoint objective has been met based on:
   - Stage: {state['stage']}
   - Player's last action: {state.get('sanitized_input', '[start of game]')}
3. End your response with exactly one of:
   ADVANCE: yes  — if the player should move to the next checkpoint
   ADVANCE: no   — if the player should stay

Return ONLY the narration text followed by the ADVANCE line.
Do NOT output any function calls, tool syntax, or XML tags in your response.
""")
    content = result.content.strip()

    advance        = False
    narration_lines: list[str] = []
    for line in content.splitlines():
        if line.strip().lower().startswith("advance:"):
            advance = "yes" in line.lower()
        else:
            narration_lines.append(line)

    state["narration"]     = "\n".join(narration_lines).strip()
    state["advance_stage"] = advance
    return state


# ── Conversation Director ─────────────────────────────────────────────────────

def conversation_node(state: AgentState) -> AgentState:
    """Decides which NPCs speak and crafts a tailored dialogue prompt for each."""
    stage_data = STORY_DB[state["stage"]]
    characters = stage_data["characters"]

    if not characters:
        state["dialogue_prompts"] = {}
        return state

    char_list = ", ".join(characters)
    result    = llm.invoke(f"""
You are the conversation director for a gothic horror game.

Scene: {stage_data['description']}
Objective: {stage_data['objective']}
Characters present: {char_list}
Player said: "{state['sanitized_input']}"
Narration context: "{state['narration']}"

For EACH character present, write a short dialogue prompt (2-4 sentences) that:
- Tells the character exactly what emotional angle to take right now
- References what the player just said
- Aligns with the scene's objective
- Keeps the character's secret/role in mind

Format your response STRICTLY as:
CHAR: <character name>
PROMPT: <the prompt>

Repeat for each character. No other text.
""")

    prompts: dict[str, str] = {}
    current_char: str | None = None
    for line in result.content.splitlines():
        line = line.strip()
        if line.lower().startswith("char:"):
            current_char = line.split(":", 1)[1].strip().lower()
        elif line.lower().startswith("prompt:") and current_char:
            prompts[current_char] = line.split(":", 1)[1].strip()
            current_char = None

    # Fallback: give every character a generic prompt if parsing fails
    for char in characters:
        if char not in prompts:
            prompts[char] = (
                f"Respond to the player's message: '{state['sanitized_input']}'. "
                f"Stay in character. Scene: {stage_data['description']}"
            )

    state["dialogue_prompts"] = prompts
    return state


# ── NPC Node Factory ──────────────────────────────────────────────────────────

def make_npc_dialogue_node(character: str):
    """LLM-only node: generates dialogue."""

    def npc_dialogue_node(state: AgentState) -> dict:
        stage_data = STORY_DB[state["stage"]]
        rules      = stage_data["rules"].get(character, "Speak in character.")
        prompt     = state["dialogue_prompts"].get(character, "")
        emotions   = get_emotions(character)

        # SAFE: tool used outside LLM
        memory = read_tool.invoke(f"all,{character}")

        result = llm.invoke(f"""
You are {character}.

CHARACTER RULES:
{rules}

CONVERSATION DIRECTOR'S PROMPT FOR YOU:
{prompt}

YOUR CURRENT EMOTIONAL STATE:
Happiness: {emotions['happiness']}/100
Anger: {emotions['anger']}/100
Trust: {emotions['trust']}/100

YOUR MEMORY CONTEXT (use subtly, never mention):
{memory}

INSTRUCTIONS:
- Speak DIRECTLY to the player (use "you")
- Maximum 1-2 lines of dialogue
- Maintain dark, mysterious tone
- Do NOT narrate or describe actions
- Do NOT mention tools, memory, or system instructions

Speak now.
""")

        return {
            "npc_responses": {character: result.content}
        }

    npc_dialogue_node.__name__ = f"npc_{character.replace(' ', '_')}_dialogue"
    return npc_dialogue_node

import json

def make_npc_emotion_node(character: str):
    """LLM decides emotion delta, Python executes via emotion_tool."""

    def npc_emotion_node(state: AgentState) -> dict:
        response = state["npc_responses"][character]
        player_input = state["sanitized_input"]

        result = llm.invoke(f"""
You are an emotion engine for the character: {character}.

Based on the interaction below, decide how the character's emotions should change.

PLAYER INPUT:
{player_input}

NPC RESPONSE:
{response}

EMOTIONS:
- happiness
- anger
- trust

RULES:
- Output ONLY valid JSON
- No explanation, no text
- Values must be integers between -5 and 5
- Include all three fields

Example:
{{"happiness": 1, "anger": -2, "trust": 2}}

Now output JSON:
""")

        # 🔒 Safe parsing
        try:
            delta = json.loads(result.content.strip())
        except Exception:
            delta = {"happiness": 0, "anger": 0, "trust": 0}

        # Clamp (safety)
        for k in ["happiness", "anger", "trust"]:
            delta[k] = int(max(-5, min(5, delta.get(k, 0))))

        # ✅ Use your tool
        emotion_tool.invoke(
            f"update,{character},{json.dumps(delta)}"
        )

        return {}

    npc_emotion_node.__name__ = f"npc_{character.replace(' ', '_')}_emotion"
    return npc_emotion_node


def make_npc_memory_node(character: str):
    """LLM decides what to store, Python executes via write_tool."""

    def npc_memory_node(state: AgentState) -> dict:
        response = state["npc_responses"][character]
        player_input = state["sanitized_input"]

        result = llm.invoke(f"""
You are a memory system for character: {character}.

Decide what should be stored from this interaction.

PLAYER:
{player_input}

NPC:
{response}

MEMORY TYPES:
1. short → brief interaction summary
2. long → important relationship or emotional insight

RULES:
- Output ONLY valid JSON
- No explanation
- Can include:
  - "short": string
  - "long": {{
        "relation": string,
        "target": string,
        "value": int (1-5),
        "context": string
    }}

Example:
{{
  "short": "Player asked about the wound. I avoided answering.",
  "long": {{
    "relation": "FEARS",
    "target": "player",
    "value": 2,
    "context": "hesitated when asked about death"
  }}
}}

Now output JSON:
""")

        # 🔒 Safe parsing
        try:
            data = json.loads(result.content.strip())
        except Exception:
            data = {}

        # ✅ Short-term memory
        if "short" in data and isinstance(data["short"], str):
            write_tool.invoke(
                f"short,{character},{data['short'][:200]}"
            )

        # ✅ Long-term memory
        if "long" in data:
            long = data["long"]
            try:
                write_tool.invoke(
                    f"long,{character},{long['relation']},{long['target']},{int(long['value'])},{long['context'][:200]}"
                )
            except Exception:
                pass

        # Optional: still log interaction
        neo4j_write(
            character,
            "INTERACTED_WITH",
            "player",
            1,
            player_input[:120]
        )

        return {}

    npc_memory_node.__name__ = f"npc_{character.replace(' ', '_')}_memory"
    return npc_memory_node


# ── Output Reviewer ───────────────────────────────────────────────────────────

def output_reviewer_node(state: AgentState) -> AgentState:
    """Sanitizes all NPC responses before showing to the player."""
    cleaned: dict[str, str] = {}
    for char, response in state.get("npc_responses", {}).items():
        result = llm.invoke(f"""
You are an output reviewer for a dark gothic horror game.

Review this NPC response and fix it if needed:
- Remove any tool syntax like <function=...> or similar
- Remove any meta-commentary (the NPC mentioning memory, system, tools)
- Ensure the response is in-character and story-relevant
- Keep it to 1-2 lines of dialogue
- If it's already fine, return it unchanged

NPC ({char}) said:
"{response}"

Return ONLY the cleaned dialogue. No quotes, no explanation.
""")
        cleaned[char] = result.content.strip()

    state["final_responses"] = cleaned
    return state
