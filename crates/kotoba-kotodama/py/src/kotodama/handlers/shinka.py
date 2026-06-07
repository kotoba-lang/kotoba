"""
ADR-0049 Phase C — shinka / koji / kyumei agent loop via LangGraph.

Per-DID 4-axis autonomy loop (see
`90-docs/rules/compliance/per-did-kyumei-shinka-autonomy.md`):

    tickActor(actor_did) → invoke shinka graph →
        load joucho mood + cadence state
        → resolve action flags (shouldDrill/Validate/Analyze/Engage/Post)
        → kyumei_gather (knowledge write)
        → koji_validate (freshness check)
        → shinka_analyze (follower delta)
        → write_heartbeat (kotoba Datom log UPSERT)
        → emit_evolution (kotoba Datom log evolution row)
        → JSON summary

Scheduled by Murakumo fleet CronJob placement (every 15 min per
registered actor); see `50-infra/vultr/mitama-udf-pool/templates/cronjob-shinka.yaml`.

Phase C.2 state (2026-04-22):
- LLM-driven compose → ✅ landed. `_compose_content` LangGraph node routes
  through `kotodama.llm.call_tier_json("classifier", ...)` (Vultr Serverless
  Devstral-2-123B) when cadence flags `should_post`. Output lands in
  `vertex_shinka_evolution.props.draft` for a later promotion job to push
  as an AT Record (PDS auth keys are not in the UDF pod — see TSC-5 /
  B2 deferred).
- Full follower KPI reward (like/love emission on wellness/dojo score
  delta) → still deferred.
- Inbox buffer reactive state (currently only cadence-based) → still
  deferred.
"""

from __future__ import annotations

import json

from kotodama import udf
from kotodama.shinka import run_tick


@udf(
    nsid="com.etzhayyim.apps.shinka.tickActor",
    io_threads=20,  # mostly DB ops, some LLM-free compute
    input_types=["VARCHAR"],
    result_type="VARCHAR",
    capability_tags=("shinka", "koji", "kyumei", "agent-loop"),
    agent_tool=(
        "Advance one shinka/koji/kyumei tick for the given actor DID. "
        "Writes heartbeat + evolution + (conditional) knowledge rows."
    ),
)
def tick_actor(params_json: str) -> str:
    """
    Input: JSON `{"actorDid": "did:web:..."}` or bare DID string.
    Output: JSON summary of the tick.
    """
    # Accept both bare DID (as emitted by RW SELECT) and the XRPC body wrapper.
    actor_did = ""
    if params_json:
        trimmed = params_json.strip()
        if trimmed.startswith("{"):
            try:
                body = json.loads(trimmed)
                actor_did = str(body.get("actorDid") or body.get("actor_did") or "")
            except json.JSONDecodeError as e:
                return json.dumps({"error": f"invalid JSON: {e}"})
        else:
            actor_did = trimmed

    if not actor_did or not actor_did.startswith("did:"):
        return json.dumps(
            {"error": "actorDid required (did:web:*.etzhayyim.com or did:plc:*)"}
        )

    result = run_tick(actor_did)
    return json.dumps(result)
