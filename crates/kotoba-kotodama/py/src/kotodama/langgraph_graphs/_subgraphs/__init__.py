"""Reusable LangGraph subgraphs.

ADR-2605080000 Distributed Cognitive Actor System §6-Layer composition.
ADR-2605072000 Agent Loop Pattern §Subgraph reuse.

Each subgraph is a self-contained StateGraph with its own State schema.
Parent graphs invoke them via a wrapper node that maps the parent's
state fields onto the subgraph's input shape, then maps the subgraph's
output back into a parent channel (typically via `operator.add` accumulator).
"""

from kotodama.langgraph_graphs._subgraphs.judge import (
    JudgeInput,
    JudgeOutput,
    arun_judge,
    build_judge_subgraph,
    run_judge,
)

__all__ = [
    "JudgeInput", "JudgeOutput",
    "arun_judge", "build_judge_subgraph", "run_judge",
]
