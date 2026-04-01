# main.py — Game loop and entry point
from emotion import get_emotions
from graph import agent
from state import AgentState
from story import STORY_DB, next_stage

_BANNER = "=" * 50

def _print_banner() -> None:
    print(_BANNER)
    print("Type 'next' to advance stage, 'exit' to quit.\n")

def _print_stage_header(stage: str) -> None:
    print(f"\n{'─' * 50}")
    print(f"  STAGE: {stage.upper()}")
    print(f"{'─' * 50}")
    print(f"\n{STORY_DB[stage]['description']}\n")

def _print_emotion_summary(characters: list[str]) -> None:
    print("\n  [Emotional State]")
    for char in characters:
        e = get_emotions(char)
        print(f"  {char}: happiness={e['happiness']} anger={e['anger']} trust={e['trust']}")

def _handle_narration_only_stage(stage: str) -> str:
    """Run a stage with no NPCs (pure narration). Returns the next stage key."""
    from config import llm
    result = llm.invoke(
        f"You are the narrator. Narrate this horror scene vividly in 3-4 sentences.\n"
        f"Scene: {STORY_DB[stage]['description']}"
    )
    print(f"\n[NARRATOR]: {result.content.strip()}\n")
    input("\nPress Enter to continue...")
    return next_stage(stage)

def run_game() -> None:
    stage = "start"
    turn  = 0

    _print_banner()

    while True:
        stage_data = STORY_DB[stage]
        _print_stage_header(stage)

        # ── Narration-only stage ──────────────
        if not stage_data["characters"]:
            stage = _handle_narration_only_stage(stage)
            if stage == "ending":
                break
            continue

        # ── Dialogue loop ─────────────────────
        while True:
            raw_input = input("\nYOU: ").strip()
            if not raw_input:
                continue

            if raw_input.lower() == "exit":
                print("\nGame ended.")
                return

            if raw_input.lower() == "next":
                stage = next_stage(stage)
                if stage == "ending":
                    break
                turn = 0
                break

            turn += 1
            initial_state: AgentState = {
                "stage":            stage,
                "player_input":     raw_input,
                "sanitized_input":  "",
                "narration":        "",
                "dialogue_prompts": {},
                "npc_responses":    {},
                "final_responses":  {},
                "advance_stage":    False,
            }

            out = agent.invoke(initial_state)

            # Print narration (first turn of each stage only, or on advance)
            if turn == 1 or out.get("advance_stage"):
                narration = out.get("narration", "").strip()
                if narration:
                    print(f"\n[NARRATOR]: {narration}\n")

            # Print NPC responses
            final = out.get("final_responses", {})
            if final:
                for char, response in final.items():
                    print(f"\n[{char.upper()}]: {response}")
            else:
                narration = out.get("narration", "").strip()
                if narration:
                    print(f"\n[NARRATOR]: {narration}")

            # Auto-advance if narrator signals it
            if out.get("advance_stage"):
                print("\n[The scene shifts…]\n")
                stage = next_stage(stage)
                turn  = 0
                if stage == "ending":
                    break
                break

            # Emotion summary every 3 turns (debug / flavour)
            if turn % 3 == 0:
                _print_emotion_summary(stage_data["characters"])

        if stage == "ending":
            break

    print(f"\n{_BANNER}")
    print("  THE END")
    print(_BANNER)


if __name__ == "__main__":
    run_game()
