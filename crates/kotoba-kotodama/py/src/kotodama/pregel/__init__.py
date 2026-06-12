"""pregel — email triage & intent analysis LangGraph server.

Pregel (German: gauge/level) measures the signal level of incoming emails:
intent, urgency, sales detection, pipeline-track dependency mapping.

Entry points:
  langgraph dev --app kotodama.pregel.graph:app
  python -m kotodama.pregel   (smoke test)
"""
from .graph import app, PregelState

__all__ = ["app", "PregelState"]
