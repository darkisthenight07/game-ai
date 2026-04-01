# state.py — LangGraph agent state definition
import operator
from typing import Annotated, TypedDict


class AgentState(TypedDict):
    stage: str
    player_input: str                                        # raw player text
    sanitized_input: str                                     # reviewer-cleaned player text
    narration: str                                           # narrator output
    dialogue_prompts: dict[str, str]                         # char -> prompt from conversation agent
    npc_responses: Annotated[dict, operator.or_]             # char -> raw response (fan-in merge)
    final_responses: dict[str, str]                          # char -> sanitized response
    advance_stage: bool                                      # narrator signals checkpoint complete
