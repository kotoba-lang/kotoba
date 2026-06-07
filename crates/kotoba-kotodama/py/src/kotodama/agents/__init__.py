"""
kotodama.agents — LangGraph-driven planning agents invoked from BPMN
service tasks (ADR-0049 Phase D / arc 1+2 hybrid).

Each agent is a LangGraph StateGraph exposed as a LangServer task type
named `com.etzhayyim.agent.<name>`. The zeebe-worker activates the job,
hands the `variables` dict to the StateGraph as initial state, runs
the graph to END, and returns the final state back as output variables.

Design points:
  - Agents are stateless per tick (no in-memory history between runs).
    Durable state lives in vertex_langgraph_checkpoint keyed by
    thread_id = `${bpmn_process_id}:${business_key}`.
  - Budgets are enforced by Zeebe process timeout, not agent-internal.
    A runaway LangGraph loop hits the Zeebe boundary error and gets
    retried up to N times per BPMN `<zeebe:taskDefinition retries="N">`.
  - LLM calls reuse `kotodama.llm.call_tier_json` so the same Vultr /
    Murakumo tier logic applies.
  - Each agent returns a flat dict — FEEL ioMapping consumes fields
    directly. Complex objects go out as JSON strings.
"""

from kotodama.agents.plan import plan_graph, task_agent_plan  # noqa: F401
from kotodama.agents.gameka_studio import (  # noqa: F401
    studio_graph as gameka_studio_graph,
    task_agent_gameka_studio,
)
from kotodama.agents.gameka_visual_critic import (  # noqa: F401
    visual_critic_graph as gameka_visual_critic_graph,
    task_agent_gameka_visual_critic,
)
from kotodama.agents.hume_emotion import (  # noqa: F401
    hume_emotion_graph,
    task_agent_hume_emotion,
)
from kotodama.agents.sbom_register import (  # noqa: F401
    sbom_register_graph,
    task_agent_sbom_register,
)
from kotodama.agents.gmail_triage import (  # noqa: F401
    gmail_triage_graph,
)
from kotodama.agents.outlook_triage import (  # noqa: F401
    outlook_triage_graph,
)

__all__ = [
    "plan_graph",
    "task_agent_plan",
    "gameka_studio_graph",
    "task_agent_gameka_studio",
    "gameka_visual_critic_graph",
    "task_agent_gameka_visual_critic",
    "hume_emotion_graph",
    "task_agent_hume_emotion",
    "sbom_register_graph",
    "task_agent_sbom_register",
    "gmail_triage_graph",
    "outlook_triage_graph",
]
