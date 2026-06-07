"""karute Pregel project — FHIR R5 EMR actor.

Per ADR-2605231100 (Phase 1) + ADR-2605231400 (consent capability +
iryo billing bridge) + ADR-2605231603 (rekey + tombstone) +
ADR-2605231700 (audit webhook subsystem).

The graph below maps each pipeline declared in
``20-actors/karute/actor-manifest.jsonld`` onto a LangGraph node. The
Pregel module is intentionally thin — every node delegates the actual
work to a substrate primitive:

    encrypt.write  → ``@etzhayyim/sdk.encryptedWrite`` (TS sidecar via the
                     checkpointer Unix socket)
    graph.write    → public-meta projection write to graphar (via PDS
                     adapter, NOT RisingWave — ADR-2605172000)
    graph.query    → public-meta read from graphar
    agent.chat     → LangServer's bound LLM (via LiteLLM gateway)
    agent.invoke   → cross-actor XRPC to ``targetDid``

For Phase 1 the LangServer Pod runs the graph in stub mode (every node
returns ``{"status": "stub"}``) until the substrate seams are wired.
The stub still exercises the full graph topology, which the deployment
pipeline depends on for langgraph CLI validation.
"""

from .pregel import app  # noqa: F401  — re-exported for langgraph.json
