# graph.py — LangGraph construction and compilation
from langgraph.graph import END, StateGraph

from nodes import (
    conversation_node,
    input_reviewer_node,
        make_npc_dialogue_node,
        make_npc_emotion_node,
        make_npc_memory_node,
    narrator_node,
    output_reviewer_node,
)
from state import AgentState
from story import STORY_DB, all_characters

def build_agent():
    characters = all_characters()
    builder    = StateGraph(AgentState)

    builder.add_node("input_reviewer", input_reviewer_node)
    builder.add_node("narrator", narrator_node)
    builder.add_node("conversation", conversation_node)
    builder.add_node("output_reviewer", output_reviewer_node)

    for char in characters:
        base = f"npc_{char.replace(' ', '_')}"
        builder.add_node(f"{base}_dialogue", make_npc_dialogue_node(char))
        builder.add_node(f"{base}_emotion",  make_npc_emotion_node(char))
        builder.add_node(f"{base}_memory",   make_npc_memory_node(char))

    builder.set_entry_point("input_reviewer")
    builder.add_edge("input_reviewer", "narrator")
    builder.add_edge("narrator", "conversation")

    # ── Conditional fan-out: only NPCs in the current stage ──────────────────
    def route_to_active_npcs(state: AgentState) -> list[str]:
        stage_chars = STORY_DB.get(state["stage"], {}).get("characters", [])
        return [
            f"npc_{char.replace(' ', '_')}_dialogue"
            for char in stage_chars
        ] or ["output_reviewer"]

    builder.add_conditional_edges(
        "conversation",
        route_to_active_npcs,
        {
            f"npc_{char.replace(' ', '_')}_dialogue": f"npc_{char.replace(' ', '_')}_dialogue"
            for char in characters
        } | {"output_reviewer": "output_reviewer"},
    )

    # ── Dialogue → emotion → memory (unchanged) ───────────────────────────────
    for char in characters:
        base = f"npc_{char.replace(' ', '_')}"
        builder.add_edge(f"{base}_dialogue", f"{base}_emotion")
        builder.add_edge(f"{base}_emotion",  f"{base}_memory")
        builder.add_edge(f"{base}_memory",   "output_reviewer")

    builder.add_edge("output_reviewer", END)
    return builder.compile()


# Module-level agent instance (import this elsewhere)
agent = build_agent()