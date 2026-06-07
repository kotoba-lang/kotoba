"""uhl_right_neural Pregel topology — 16-vertex StateGraph.

Authoritative per ADR-2605181000 §16-vertex Pregel topology.

P0-P3 charter implementation status — every treatment-arm vertex is
now a real actor; only V14 trial_design + V10b optoCI sub-variant
remain stubs.

  - V01 phenotype             — implemented (actors/phenotype.py)
  - V02 genetic_screen        — implemented (actors/genetic_screen.py)
  - V03 imaging               — implemented (actors/imaging.py)
  - V04 electrophys           — implemented (actors/electrophys.py)
  - V05 cmv_torch             — implemented (actors/cmv_torch.py)
  - V06 substrate_classifier  — implemented (actors/substrate_classifier.py)
  - V07 otof_tx               — implemented (actors/otof_tx.py)          P1
  - V08 neurotrophin          — implemented (actors/neurotrophin.py)     P2
  - V09 reprogramming         — implemented (actors/reprogramming.py)   P3
  - V10 conventional_device   — implemented (actors/conventional_device.py)
                                (V10a eCI fitting; V10b optoCI is P3)
  - V11 abi                   — implemented (actors/abi.py)              P1
  - V12 plasticity            — implemented (actors/plasticity.py)
  - V13 outcome (Bayesian)    — implemented (actors/outcome.py)
  - V15 regulatory            — implemented (actors/regulatory.py)       P1
  - V16 institution_match     — implemented (actors/institution_matcher.py)

Remaining stubs:
  - V14 trial_design                       → P1-P2 (in-progress, parallel branch)
  - V10b optoCI sub-variant of V10        → P3 (when optoCI trial opens)

V08 and V09 are honest "research-track classification" actors —
preclinical, no current human treatment, but the patient is
registered as eligible for the relevant research pipeline.
"""
from __future__ import annotations

import os
from typing import Any, Optional

from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from .actors.abi import AbiActor
from .actors.cmv_torch import CmvTorchActor
from .actors.conventional_device import ConventionalDeviceActor
from .actors.electrophys import ElectrophysActor
from .actors.genetic_screen import GeneticScreenActor
from .actors.imaging import ImagingActor
from .actors.institution_matcher import InstitutionMatcherActor
from .actors.neurotrophin import NeurotrophinActor
from .actors.otof_tx import OtofTxActor
from .actors.outcome import OutcomeActor
from .actors.phenotype import PhenotypeActor
from .actors.plasticity import PlasticityActor
from .actors.regulatory import RegulatoryActor
from .actors.reprogramming import ReprogrammingActor
from .actors.substrate_classifier import SubstrateClass, SubstrateClassifierActor
from .actors.trial_design import TrialDesignActor


# ── State ────────────────────────────────────────────────────────────────────


class UhlState(TypedDict, total=False):
    """Pregel state for uhl_right_neural. Shape is intentionally permissive
    (TypedDict total=False) so stub vertices can pass through unchanged."""

    # V01 input
    phenotype_input: dict[str, Any]
    # V01 output
    phenotype: dict[str, Any]

    # V02-V05 evidence fan-in
    substrate_evidence: dict[str, Any]
    genetic_input: dict[str, Any]       # V02 input
    imaging_input: dict[str, Any]       # V03 input
    electrophys_input: dict[str, Any]   # V04 input
    cmv_torch_input: dict[str, Any]     # V05 input
    genetic_result: dict[str, Any]      # V02 output
    imaging_result: dict[str, Any]      # V03 output
    electrophys_result: dict[str, Any]  # V04 output
    cmv_torch_result: dict[str, Any]    # V05 output

    # V06 output
    substrate_decision: dict[str, Any]

    # V07-V11 (stubs for P0)
    otof_tx_plan: dict[str, Any]                   # V07
    neurotrophin_plan: dict[str, Any]              # V08
    reprogramming_plan: dict[str, Any]             # V09
    device_plan: dict[str, Any]                    # V10 (eCI / optoCI)
    abi_plan: dict[str, Any]                       # V11

    # V13 input (P0 — optional)
    outcome_input: dict[str, Any]

    # V12-V15 outputs (V12 + V13 implemented in P0; V14/V15 stubs)
    plasticity_plan: dict[str, Any]                # V12
    outcome_posterior: dict[str, Any]              # V13
    trial_protocol: dict[str, Any]                 # V14 (stub)
    regulatory_path: dict[str, Any]                # V15 (stub)

    # V16 output
    institution_match: dict[str, Any]

    # Cross-cutting
    requires_human_review: bool
    error: str


# ── Vertex implementations ───────────────────────────────────────────────────

_phenotype = PhenotypeActor()
_genetic = GeneticScreenActor()
_imaging = ImagingActor()
_electrophys = ElectrophysActor()
_cmv_torch = CmvTorchActor()
_substrate = SubstrateClassifierActor()
_otof = OtofTxActor()
_neurotrophin = NeurotrophinActor()
_reprogramming = ReprogrammingActor()
_device = ConventionalDeviceActor()
_abi = AbiActor()
_plasticity = PlasticityActor()
_outcome = OutcomeActor()
_trial_design = TrialDesignActor()
_regulatory = RegulatoryActor()
_institutions = InstitutionMatcherActor()


def _v01_phenotype(state: UhlState) -> dict[str, Any]:
    return _phenotype.compute(state)


def _v02_genetic(state: UhlState) -> dict[str, Any]:
    return _genetic.compute(state)


def _v03_imaging(state: UhlState) -> dict[str, Any]:
    return _imaging.compute(state)


def _v04_electrophys(state: UhlState) -> dict[str, Any]:
    return _electrophys.compute(state)


def _v05_cmv_torch(state: UhlState) -> dict[str, Any]:
    return _cmv_torch.compute(state)


def _v06_substrate(state: UhlState) -> dict[str, Any]:
    return _substrate.compute(state)


def _v07_otof_tx(state: UhlState) -> dict[str, Any]:
    return _otof.compute(state)


def _v08_neurotrophin(state: UhlState) -> dict[str, Any]:
    return _neurotrophin.compute(state)


def _v09_reprogramming(state: UhlState) -> dict[str, Any]:
    return _reprogramming.compute(state)


def _v10_device_fitting(state: UhlState) -> dict[str, Any]:
    return _device.compute(state)


def _v11_abi(state: UhlState) -> dict[str, Any]:
    return _abi.compute(state)


def _v12_plasticity(state: UhlState) -> dict[str, Any]:
    return _plasticity.compute(state)


def _v13_outcome(state: UhlState) -> dict[str, Any]:
    return _outcome.compute(state)


def _v14_trial_design(state: UhlState) -> dict[str, Any]:
    return _trial_design.compute(state)


def _v15_regulatory(state: UhlState) -> dict[str, Any]:
    return _regulatory.compute(state)


def _v16_institution_match(state: UhlState) -> dict[str, Any]:
    return _institutions.compute(state)


def _make_stub(vertex_id: str, output_key: str) -> Any:
    """Build a no-op stub vertex. Sets `<output_key>` to a marker dict."""

    def _stub(state: UhlState) -> dict[str, Any]:  # noqa: ARG001
        return {output_key: {"_stub": True, "_vertex": vertex_id}}

    _stub.__name__ = f"stub_{vertex_id.lower()}"
    return _stub


# Stubs for treatment-arm vertices not yet implemented (charter P2/P3).
# V08 (P2 BDNF/NT-3) and V09 (P3 reprog) are now real actors — see
# above. No remaining treatment-arm stubs.


# ── Routing ──────────────────────────────────────────────────────────────────


def _route_after_substrate(state: UhlState) -> str:
    """Conditional branch after V06 — pick first downstream treatment vertex.

    The full V07-V11 fan-out is conceptual; in this scaffold we route to a
    single representative vertex per substrate class, and the rest of the
    chain (V12-V16) runs sequentially. P1 will introduce true parallel
    treatment-arm fan-out.
    """
    decision = state.get("substrate_decision") or {}
    klass_raw = decision.get("substrate_class")
    if not klass_raw:
        return "V10_device_fitting"  # safe default
    klass = SubstrateClass(klass_raw)

    if klass is SubstrateClass.NERVE_APLASIA:
        return "V11_abi"
    if klass is SubstrateClass.SGN_ABSENT_NERVE_PRESENT:
        return "V09_reprogramming"
    if klass is SubstrateClass.SGN_DEGENERATING_NERVE_PRESENT:
        return "V08_neurotrophin"
    if klass is SubstrateClass.SGN_PRESENT_HC_LOSS:
        return "V07_otof_tx"
    # INDETERMINATE — go straight to V10 fallback for human review
    return "V10_device_fitting"


# ── Build ────────────────────────────────────────────────────────────────────


def _build() -> StateGraph:
    g = StateGraph(UhlState)

    # Vertices
    g.add_node("V01_phenotype", _v01_phenotype)
    g.add_node("V02_genetic_screen", _v02_genetic)
    g.add_node("V03_imaging", _v03_imaging)
    g.add_node("V04_electrophys", _v04_electrophys)
    g.add_node("V05_cmv_torch", _v05_cmv_torch)
    g.add_node("V06_substrate_classifier", _v06_substrate)
    g.add_node("V07_otof_tx", _v07_otof_tx)
    g.add_node("V08_neurotrophin", _v08_neurotrophin)
    g.add_node("V09_reprogramming", _v09_reprogramming)
    g.add_node("V10_device_fitting", _v10_device_fitting)
    g.add_node("V11_abi", _v11_abi)
    g.add_node("V12_plasticity", _v12_plasticity)
    g.add_node("V13_outcome", _v13_outcome)
    g.add_node("V14_trial_design", _v14_trial_design)
    g.add_node("V15_regulatory", _v15_regulatory)
    g.add_node("V16_institution_matcher", _v16_institution_match)

    # S0-S1: V01 → V02-V05 fan-out → V06 fan-in
    g.set_entry_point("V01_phenotype")
    for v in (
        "V02_genetic_screen",
        "V03_imaging",
        "V04_electrophys",
        "V05_cmv_torch",
    ):
        g.add_edge("V01_phenotype", v)
        g.add_edge(v, "V06_substrate_classifier")

    # S2: V06 → treatment branch
    g.add_conditional_edges(
        "V06_substrate_classifier",
        _route_after_substrate,
        {
            "V07_otof_tx": "V07_otof_tx",
            "V08_neurotrophin": "V08_neurotrophin",
            "V09_reprogramming": "V09_reprogramming",
            "V10_device_fitting": "V10_device_fitting",
            "V11_abi": "V11_abi",
        },
    )

    # S3: every treatment branch → V10 device fitting (eCI/optoCI/ABI selection)
    # ABI vertex is its own device path, so it skips V10.
    for v in (
        "V07_otof_tx",
        "V08_neurotrophin",
        "V09_reprogramming",
    ):
        g.add_edge(v, "V10_device_fitting")
    g.add_edge("V10_device_fitting", "V12_plasticity")
    g.add_edge("V11_abi", "V12_plasticity")

    # S4-S7: linear chain V12 → V13 → V14 → V15 → V16 → END
    g.add_edge("V12_plasticity", "V13_outcome")
    g.add_edge("V13_outcome", "V14_trial_design")
    g.add_edge("V14_trial_design", "V15_regulatory")
    g.add_edge("V15_regulatory", "V16_institution_matcher")
    g.add_edge("V16_institution_matcher", END)
    return g


def _maybe_checkpointer() -> Any:
    """Build an MstCheckpointSaver iff MST_CHECKPOINT_SOCKET is set.

    Per ADR-2605171800 + ADR-2605172000 (RW-free substrate). The saver
    proxies to the @etzhayyim/sdk TS sidecar over a Unix socket (or TCP
    for out-of-host test rigs). When the env var is unset the Pregel
    compiles without a checkpointer — same behaviour as P0 MVP.
    """
    socket_path = os.environ.get("MST_CHECKPOINT_SOCKET")
    if not socket_path:
        return None
    cell_did = os.environ.get(
        "MST_CHECKPOINT_CELL_DID", "did:web:uhl-right-neural.etzhayyim.com"
    )
    # Lazy import — kotodama.checkpointer pulls msgpack, which is an
    # optional dep for hosts that don't enable the substrate pipeline.
    from kotodama.checkpointer import MstCheckpointSaver

    return MstCheckpointSaver(cell_did=cell_did, socket_path=socket_path)


def _compile() -> Any:
    checkpointer = _maybe_checkpointer()
    if checkpointer is not None:
        return _build().compile(checkpointer=checkpointer)
    return _build().compile()


app = _compile()


def build_graph() -> Any:
    """Factory entry point for langgraph_loader (py_factory kind)."""
    return _compile()


__all__ = ["UhlState", "app", "build_graph"]
