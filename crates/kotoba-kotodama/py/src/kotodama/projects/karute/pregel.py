"""karute Pregel — 31-pipeline LangGraph StateGraph mirroring actor-manifest.jsonld.

Phase 1 stub: every node returns ``{"status": "stub", "pipeline": "<name>"}``
so the graph compiles + serves via ``langgraph dev`` without requiring the
SDK / PDS / IPFS / L2 substrate to be live.

The node-name → pipeline-trigger mapping mirrors the XRPC NSIDs:

    create_patient                   com.etzhayyim.apps.karute.createPatient
    create_encounter                 com.etzhayyim.apps.karute.createEncounter
    create_soap_note                 com.etzhayyim.apps.karute.createSoapNote
    create_observation               com.etzhayyim.apps.karute.createObservation
    create_condition                 com.etzhayyim.apps.karute.createCondition
    create_medication_request        com.etzhayyim.apps.karute.createMedicationRequest
    create_service_request           com.etzhayyim.apps.karute.createServiceRequest
    create_dispense                  com.etzhayyim.apps.karute.createDispense
    create_homecare_episode          com.etzhayyim.apps.karute.createHomecareEpisode
    create_home_visit                com.etzhayyim.apps.karute.createHomeVisit
    grant_consent                    com.etzhayyim.apps.karute.grantConsent
    revoke_consent                   com.etzhayyim.apps.karute.revokeConsent
    list_consent                     com.etzhayyim.apps.karute.listConsent
    request_iryo_billing             com.etzhayyim.apps.karute.requestIryoBilling
    rekey_record                     com.etzhayyim.apps.karute.rekeyRecord
    redact_record                    com.etzhayyim.apps.karute.redactRecord
    list_tombstones                  com.etzhayyim.apps.karute.listTombstones
    list_audit_events                com.etzhayyim.apps.karute.listAuditEvents
    get_chart_summary                com.etzhayyim.apps.karute.getChartSummary
    export_fhir_bundle               com.etzhayyim.apps.karute.exportFhirBundle
    list_patients                    com.etzhayyim.apps.karute.listPatients
    get_patient                      com.etzhayyim.apps.karute.getPatient
    list_encounters                  com.etzhayyim.apps.karute.listEncounters
    list_soap_notes                  com.etzhayyim.apps.karute.listSoapNotes
    list_observations                com.etzhayyim.apps.karute.listObservations
    list_medications                 com.etzhayyim.apps.karute.listMedications
    list_orders                      com.etzhayyim.apps.karute.listOrders
    list_dispenses                   com.etzhayyim.apps.karute.listDispenses
    list_homecare_episodes           com.etzhayyim.apps.karute.listHomecareEpisodes
    list_home_visits                 com.etzhayyim.apps.karute.listHomeVisits
    health_karute                    com.etzhayyim.apps.karute.healthKarute
"""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph


class KaruteState(TypedDict, total=False):
    """The Pregel state passed between nodes.

    PHI is NEVER stored here — the encrypted envelope lives at the sidecar
    boundary (`@etzhayyim/sdk.encryptedWrite` returns a CID; only the CID
    crosses this graph).
    """

    pipeline: str
    input: dict[str, Any]
    encrypt_result: dict[str, Any]
    graph_result: dict[str, Any]
    audit_event: dict[str, Any]
    output: dict[str, Any]
    errors: list[str]


PIPELINES = [
    "create_patient",
    "create_encounter",
    "create_soap_note",
    "create_observation",
    "create_condition",
    "create_medication_request",
    "create_service_request",
    "create_dispense",
    "create_homecare_episode",
    "create_home_visit",
    "grant_consent",
    "revoke_consent",
    "list_consent",
    "request_iryo_billing",
    "rekey_record",
    "redact_record",
    "list_tombstones",
    "list_audit_events",
    "get_chart_summary",
    "export_fhir_bundle",
    "list_patients",
    "get_patient",
    "list_encounters",
    "list_soap_notes",
    "list_observations",
    "list_medications",
    "list_orders",
    "list_dispenses",
    "list_homecare_episodes",
    "list_home_visits",
    "health_karute",
]


def _stub_node(name: str):
    def node(state: KaruteState) -> KaruteState:
        return {
            **state,
            "pipeline": name,
            "output": {"status": "stub", "pipeline": name, "note": "Phase 1 — substrate seams pending"},
        }

    node.__name__ = name
    return node


def _route(state: KaruteState) -> str:
    """Dispatch to the requested pipeline.

    The langserver HTTP entrypoint passes ``state.pipeline`` to select the
    branch; unknown pipelines fall through to ``health_karute`` so the graph
    always converges.
    """
    requested = (state.get("pipeline") or "").strip()
    return requested if requested in PIPELINES else "health_karute"


def build_graph() -> StateGraph:
    builder: StateGraph = StateGraph(KaruteState)
    for name in PIPELINES:
        builder.add_node(name, _stub_node(name))
    builder.add_conditional_edges(START, _route, {name: name for name in PIPELINES})
    for name in PIPELINES:
        builder.add_edge(name, END)
    return builder


app = build_graph().compile()
