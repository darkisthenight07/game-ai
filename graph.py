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
from story import all_characters


def build_agent():
    """Construct and compile the multi-agent LangGraph."""
    characters = all_characters()
    builder    = StateGraph(AgentState)

    # Core nodes
    builder.add_node("input_reviewer", input_reviewer_node)
    builder.add_node("narrator", narrator_node)
    builder.add_node("conversation", conversation_node)
    builder.add_node("output_reviewer", output_reviewer_node)

    # NPC pipelines
    # Need to add conditional edges here
    for char in characters:
        base = f"npc_{char.replace(' ', '_')}"

        builder.add_node(f"{base}_dialogue", make_npc_dialogue_node(char))
        builder.add_node(f"{base}_emotion", make_npc_emotion_node(char))
        builder.add_node(f"{base}_memory", make_npc_memory_node(char))

    # Entry flow
    builder.set_entry_point("input_reviewer")
    builder.add_edge("input_reviewer", "narrator")
    builder.add_edge("narrator", "conversation")

    # Fan-out → dialogue
    for char in characters:
        base = f"npc_{char.replace(' ', '_')}"
        builder.add_edge("conversation", f"{base}_dialogue")

    # Dialogue → emotion
    for char in characters:
        base = f"npc_{char.replace(' ', '_')}"
        builder.add_edge(f"{base}_dialogue", f"{base}_emotion")

    # Emotion → memory
    for char in characters:
        base = f"npc_{char.replace(' ', '_')}"
        builder.add_edge(f"{base}_emotion", f"{base}_memory")

    # Memory → output
    for char in characters:
        base = f"npc_{char.replace(' ', '_')}"
        builder.add_edge(f"{base}_memory", "output_reviewer")

    builder.add_edge("output_reviewer", END)
    return builder.compile()


# Module-level agent instance (import this elsewhere)
agent = build_agent()