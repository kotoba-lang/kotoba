"""gameya_quality_loop — LangGraph quality loop for playable browser games.

The graph is intentionally deterministic and side-effect-light so LangGraph
Server can run it as a resident evaluator during early gameya rollout:

observe_playtest -> score_quality -> propose_changes -> package_result
"""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph


class GameyaQualityState(TypedDict, total=False):
    title: str
    build_url: str
    playtest: dict[str, Any]
    target_quality: str
    observations: list[str]
    quality_score: float
    weak_points: list[str]
    improvement_plan: list[str]
    release_gate: str
    ok: bool


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def observe_playtest(state: GameyaQualityState) -> dict[str, Any]:
    playtest = state.get("playtest") or {}
    observations: list[str] = []
    fps = _num(playtest.get("fps"), 60.0)
    console_errors = int(_num(playtest.get("consoleErrors"), 0))
    input_ok = bool(playtest.get("inputOk", True))
    visible = bool(playtest.get("visualNonBlank", True))
    progression = bool(playtest.get("progressionOk", False))
    render_text = bool(playtest.get("renderGameToTextOk", False))
    all_clear = bool(playtest.get("allClearOk", False))
    pause_ok = bool(playtest.get("pauseOk", False))
    mobile_ok = bool(playtest.get("mobileTouchOk", False))

    observations.append(f"fps={fps:.1f}")
    observations.append(f"console_errors={console_errors}")
    observations.append(f"input_ok={input_ok}")
    observations.append(f"visual_non_blank={visible}")
    observations.append(f"progression_ok={progression}")
    observations.append(f"render_game_to_text_ok={render_text}")
    observations.append(f"all_clear_ok={all_clear}")
    observations.append(f"pause_ok={pause_ok}")
    observations.append(f"mobile_touch_ok={mobile_ok}")
    return {"observations": observations}


def score_quality(state: GameyaQualityState) -> dict[str, Any]:
    playtest = state.get("playtest") or {}
    weak: list[str] = []
    score = 1.0

    if _num(playtest.get("fps"), 60.0) < 50:
        score -= 0.18
        weak.append("Frame pacing is below the 50 FPS gate.")
    if int(_num(playtest.get("consoleErrors"), 0)) > 0:
        score -= 0.22
        weak.append("Console errors must be zero before release.")
    if not bool(playtest.get("visualNonBlank", True)):
        score -= 0.25
        weak.append("Canvas capture is blank or incorrectly framed.")
    if not bool(playtest.get("inputOk", True)):
        score -= 0.18
        weak.append("Primary controls did not complete the expected sequence.")
    if not bool(playtest.get("progressionOk", False)):
        score -= 0.1
        weak.append("Core loop needs a clear score, risk, and retry progression.")
    if not bool(playtest.get("renderGameToTextOk", False)):
        score -= 0.07
        weak.append("Automated text-state hook is missing or incomplete.")
    if not bool(playtest.get("allClearOk", False)):
        score -= 0.1
        weak.append("Full stage progression must reach the all-clear state.")
    if not bool(playtest.get("pauseOk", False)):
        score -= 0.06
        weak.append("Pause/resume must preserve state and resume input cleanly.")
    if not bool(playtest.get("mobileTouchOk", False)):
        score -= 0.08
        weak.append("Mobile touch controls must support movement and action.")

    return {"quality_score": max(0.0, round(score, 3)), "weak_points": weak}


def propose_changes(state: GameyaQualityState) -> dict[str, Any]:
    weak = state.get("weak_points") or []
    plan = [
        "Keep one readable first-screen game loop: start, play, score, fail, restart.",
        "Verify canvas screenshots after input bursts, not only static load.",
        "Tune collision, acceleration, jump height, and reward spacing in small increments.",
    ]
    if weak:
        plan.extend(weak)
    else:
        plan.extend([
            "Add one new mechanic only after the current loop remains stable in automation.",
            "Record a golden playtest payload before deployment.",
        ])
    return {"improvement_plan": plan[:7]}


def package_result(state: GameyaQualityState) -> dict[str, Any]:
    score = _num(state.get("quality_score"), 0.0)
    gate = "ship" if score >= 0.86 and not state.get("weak_points") else "iterate"
    return {"release_gate": gate, "ok": gate == "ship"}


def build_graph():
    graph = StateGraph(GameyaQualityState)
    graph.add_node("observe_playtest", observe_playtest)
    graph.add_node("score_quality", score_quality)
    graph.add_node("propose_changes", propose_changes)
    graph.add_node("package_result", package_result)
    graph.set_entry_point("observe_playtest")
    graph.add_edge("observe_playtest", "score_quality")
    graph.add_edge("score_quality", "propose_changes")
    graph.add_edge("propose_changes", "package_result")
    graph.add_edge("package_result", END)
    return graph.compile()
