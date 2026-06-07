"""
BeliefStore protocol for active-inference state custody.

Phase 1 of ADR-2605211200. Lets active_inference / agent_status / zeebe_worker
read and write the 12 vertex_agent_* equivalents without binding to a specific
substrate (RisingWave vs AT MST + IPFS + Base L2 + murakumo-local SQLite).

Religious-corp default: AtIpfsLocalBeliefStore (per ADR-2605172000 RW-free substrate).
Phase 2 cutover: AtIpfsLocalBeliefStore (per-actor read-flip).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Protocol, Sequence, runtime_checkable


@dataclass
class ObservationRecord:
    agent_did: str
    source_kind: str
    observed_at: str
    payload_json: str
    confidence_permille: int
    uncertainty_permille: int
    source_ref: str | None = None
    sensitivity_ord: int = 1
    vertex_id: str | None = None


@dataclass
class BeliefStateRecord:
    agent_did: str
    belief_kind: str
    state_key: str
    state_value_json: str
    posterior_confidence_permille: int
    posterior_entropy_permille: int
    updated_at: str
    ipfs_cid: str | None = None
    updated_from_observation: str | None = None
    sensitivity_ord: int = 1
    vertex_id: str | None = None


@dataclass
class PriorPreferenceRecord:
    agent_did: str
    preference_key: str
    target_range_json: str
    weight_permille: int
    active: bool
    created_at: str
    updated_at: str
    hard_floor: bool = False
    depends_on_adr: str | None = None
    sensitivity_ord: int = 1
    vertex_id: str | None = None


@dataclass
class ActiveInferenceTickRecord:
    agent_did: str
    tick_kind: str
    belief_snapshot_hash: str
    candidate_actions_json: str
    expected_free_energy_json: str
    mokuteki_gate_pass: bool
    created_at: str
    selected_action_id: str | None = None
    sensitivity_ord: int = 1
    vertex_id: str | None = None


@dataclass
class ActionProposalRecord:
    agent_did: str
    action_kind: str
    target_surface: str
    proposal_json: str
    safety_state: str
    created_at: str
    updated_at: str
    simulation_ref: str | None = None
    approval_ref: str | None = None
    authority_ref: str | None = None
    dispatch_ref: str | None = None
    sensitivity_ord: int = 1
    vertex_id: str | None = None


@dataclass
class RealworldEffectRecord:
    action_proposal_id: str
    agent_did: str
    channel: str
    effect_class: str
    payload_hash: str
    summary: str
    dispatch_state: str
    created_at: str
    updated_at: str
    principal_did: str | None = None
    target_ref_hash: str | None = None
    approval_ref: str | None = None
    budget_ref: str | None = None
    authority_ref: str | None = None
    dispatch_receipt_ref: str | None = None
    settlement_tx_base: str | None = None
    observation_plan_json: str | None = None
    sensitivity_ord: int = 1
    vertex_id: str | None = None


@dataclass
class HomeostasisSnapshotRecord:
    agent_did: str
    compute_budget_remaining_permille: int
    storage_pressure_permille: int
    lease_seconds_remaining: int
    error_rate_1h_permille: int
    tool_success_rate_1h_permille: int
    energy_or_cost_proxy_permille: int
    viability_state: str
    created_at: str
    sensitivity_ord: int = 1
    vertex_id: str | None = None


@dataclass
class DispatchLedgerRecord:
    agent_did: str
    dispatch_plan_id: str
    channel: str
    payload_hash: str
    authority_ref: str
    policy_ref: str
    dispatch_state: str
    created_at: str
    updated_at: str
    realworld_effect_id: str | None = None
    task_type: str | None = None
    settlement_tx_base: str | None = None
    sensitivity_ord: int = 1
    vertex_id: str | None = None


@dataclass
class DelegatedAuthorityPolicyRecord:
    authority_ref: str
    policy_ref: str
    agent_did: str
    channels_json: str
    effect_classes_json: str
    target_bindings_json: str
    payload_constraints_json: str
    rate_limit_json: str
    expires_at: str
    signature_ref: str
    status: str
    created_at: str
    updated_at: str
    principal_did: str | None = None
    budget_ref: str | None = None
    policy_cid: str | None = None
    on_chain_delegation_root: str | None = None
    sensitivity_ord: int = 1
    vertex_id: str | None = None


@dataclass
class PolicyAdaptationProposalRecord:
    agent_did: str
    preference_key: str
    proposal_hash: str
    proposal_json: str
    mokuteki_gate_pass: bool
    triple_witness_pass: bool
    blockers_json: str
    proposal_state: str
    created_at: str
    sensitivity_ord: int = 1
    vertex_id: str | None = None


@dataclass
class CounterpartyModelRecord:
    agent_did: str
    counterparty_ref: str
    model_kind: str
    prior_preferences_json: str
    protected_assets_json: str
    confidence_permille: int
    uncertainty_permille: int
    created_at: str
    updated_at: str
    model_ipfs_cid: str | None = None
    sensitivity_ord: int = 1
    vertex_id: str | None = None


@dataclass
class ProtectedAssetRecord:
    agent_did: str
    counterparty_ref: str
    asset_ref: str
    asset_kind: str
    protected_state_json: str
    violation_cost_permille: int
    reversibility_score_permille: int
    created_at: str
    updated_at: str
    sensitivity_ord: int = 1
    vertex_id: str | None = None


@dataclass
class StoreStats:
    backend: str
    counts: dict[str, int] = field(default_factory=dict)


@dataclass
class HakkouFermentRecord:
    vertex_id: str | None = None
    record_id: str | None = None
    owner_did: str | None = None
    label: str | None = None
    status: str | None = None
    stream_id: str | None = None
    agent_did: str | None = None
    value_json: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    sensitivity_ord: int = 1
    input_kind: str | None = None
    input_ref: str | None = None
    output_vertex_id: str | None = None
    output_kind: str | None = None
    ethanol_hash: str | None = None
    co2_audit_ref: str | None = None
    input_hash: str | None = None
    fermented_at: str | None = None

@dataclass
class KoboAgentRecord:
    vertex_id: str | None = None
    record_id: str | None = None
    owner_did: str | None = None
    label: str | None = None
    status: str | None = None
    stream_id: str | None = None
    agent_did: str | None = None
    value_json: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    sensitivity_ord: int = 1
    parent_did: str | None = None
    role: str | None = None
    eta: float = 0.0
    stress_score: float = 0.0

@dataclass
class KoboPrionRecord:
    vertex_id: str | None = None
    record_id: str | None = None
    owner_did: str | None = None
    label: str | None = None
    status: str | None = None
    stream_id: str | None = None
    agent_did: str | None = None
    value_json: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    sensitivity_ord: int = 1
    pattern_hash: str | None = None
    heritable: bool = False
    malignant_score: float = 0.0
    content: str | None = None

@dataclass
class KoboBuddingRecord:
    edge_id: str | None = None
    src_vid: str | None = None
    dst_vid: str | None = None
    relation_kind: str | None = None
    value_json: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    owner_did: str | None = None
    sensitivity_ord: int = 1
    parent_did: str | None = None
    child_did: str | None = None
    budded_at: str | None = None
    prion_count: int = 0

@dataclass
class KabiHyphaRecord:
    edge_id: str | None = None
    src_vid: str | None = None
    dst_vid: str | None = None
    relation_kind: str | None = None
    value_json: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    owner_did: str | None = None
    sensitivity_ord: int = 1
    src_agent_did: str | None = None
    dst_agent_did: str | None = None
    eta: float = 0.0
    flow: float = 0.0
    pruned_at: str | None = None

@dataclass
class KabiAnastomosisRecord:
    edge_id: str | None = None
    src_vid: str | None = None
    dst_vid: str | None = None
    relation_kind: str | None = None
    value_json: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    owner_did: str | None = None
    sensitivity_ord: int = 1
    network_a_did: str | None = None
    network_b_did: str | None = None
    compatibility_score: float = 0.0
    result: str | None = None
    reason: str | None = None

@dataclass
class KabiNetworkRecord:
    vertex_id: str | None = None
    record_id: str | None = None
    owner_did: str | None = None
    label: str | None = None
    status: str | None = None
    stream_id: str | None = None
    agent_did: str | None = None
    value_json: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    sensitivity_ord: int = 1
    root_agent_did: str | None = None
    hypha_count: int = 0
    total_flow: float = 0.0

@dataclass
class KinokoBlockRecord:
    vertex_id: str | None = None
    record_id: str | None = None
    owner_did: str | None = None
    label: str | None = None
    status: str | None = None
    stream_id: str | None = None
    agent_did: str | None = None
    value_json: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    sensitivity_ord: int = 1
    prev_block_id: str | None = None
    block_hash: str | None = None
    total_flow: float = 0.0
    participant_count: int = 0
    eta_min_used: float = 0.0
    block_status: str | None = None

@dataclass
class HoushiSporeRecord:
    vertex_id: str | None = None
    record_id: str | None = None
    owner_did: str | None = None
    label: str | None = None
    status: str | None = None
    stream_id: str | None = None
    agent_did: str | None = None
    value_json: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    sensitivity_ord: int = 1
    origin_agent_did: str | None = None
    blob_cbor: str | None = None
    revival_key_hint: str | None = None
    quorum_n: int = 0
    germinated_at: str | None = None

@dataclass
class HoushiCustodyRecord:
    edge_id: str | None = None
    src_vid: str | None = None
    dst_vid: str | None = None
    relation_kind: str | None = None
    value_json: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    owner_did: str | None = None
    sensitivity_ord: int = 1
    custodian_did: str | None = None
    custody_confirmed: bool = False

@dataclass
class KokeFixationRecord:
    vertex_id: str | None = None
    record_id: str | None = None
    owner_did: str | None = None
    label: str | None = None
    status: str | None = None
    stream_id: str | None = None
    agent_did: str | None = None
    value_json: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    sensitivity_ord: int = 1
    input_kind: str | None = None
    raw_ref: str | None = None
    signal_hash: str | None = None
    classification: str | None = None
    confidence: float = 0.0
    fixed_at: str | None = None
    released_at: str | None = None

@dataclass
class KokeFlowRecord:
    edge_id: str | None = None
    src_vid: str | None = None
    dst_vid: str | None = None
    relation_kind: str | None = None
    value_json: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    owner_did: str | None = None
    sensitivity_ord: int = 1
    fixation_id: str | None = None
    ferment_id: str | None = None
    handoff_kind: str | None = None
    handed_off_at: str | None = None

@dataclass
class SaikinSignalRecord:
    vertex_id: str | None = None
    record_id: str | None = None
    owner_did: str | None = None
    label: str | None = None
    status: str | None = None
    stream_id: str | None = None
    agent_did: str | None = None
    value_json: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    sensitivity_ord: int = 1
    input_kind: str | None = None
    raw_ref: str | None = None
    signal_hash: str | None = None
    probe_source: str | None = None
    transferred_at: str | None = None

@dataclass
class SaikinColonyRecord:
    vertex_id: str | None = None
    record_id: str | None = None
    owner_did: str | None = None
    label: str | None = None
    status: str | None = None
    stream_id: str | None = None
    agent_did: str | None = None
    value_json: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    sensitivity_ord: int = 1
    colony_label: str | None = None
    member_count: int = 0
    formed_at: str | None = None
    lysed_at: str | None = None

@dataclass
class SaikinTransferRecord:
    edge_id: str | None = None
    src_vid: str | None = None
    dst_vid: str | None = None
    relation_kind: str | None = None
    value_json: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    owner_did: str | None = None
    sensitivity_ord: int = 1
    signal_id: str | None = None
    target_actor_did: str | None = None
    transfer_kind: str | None = None
    transferred_at: str | None = None

@dataclass
class SaikinMemberRecord:
    edge_id: str | None = None
    src_vid: str | None = None
    dst_vid: str | None = None
    relation_kind: str | None = None
    value_json: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    owner_did: str | None = None
    sensitivity_ord: int = 1
    colony_id: str | None = None
    signal_id: str | None = None
    joined_at: str | None = None

@dataclass
class KiAbsorbRecord:
    vertex_id: str | None = None
    record_id: str | None = None
    owner_did: str | None = None
    label: str | None = None
    status: str | None = None
    stream_id: str | None = None
    agent_did: str | None = None
    value_json: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    sensitivity_ord: int = 1
    source_vertex_id: str | None = None
    input_kind: str | None = None
    content_hash: str | None = None
    absorbed_at: str | None = None
    synthesized_at: str | None = None

@dataclass
class KiArtifactRecord:
    vertex_id: str | None = None
    record_id: str | None = None
    owner_did: str | None = None
    label: str | None = None
    status: str | None = None
    stream_id: str | None = None
    agent_did: str | None = None
    value_json: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    sensitivity_ord: int = 1
    absorb_id: str | None = None
    artifact_kind: str | None = None
    synthesis: str | None = None
    confidence: float = 0.0
    artifact_hash: str | None = None
    bloomed_at: str | None = None

@dataclass
class KiRingRecord:
    vertex_id: str | None = None
    record_id: str | None = None
    owner_did: str | None = None
    label: str | None = None
    status: str | None = None
    stream_id: str | None = None
    agent_did: str | None = None
    value_json: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    sensitivity_ord: int = 1
    period: str | None = None
    snapshot_count: int = 0
    ring_at: str | None = None

@dataclass
class KiVascularRecord:
    edge_id: str | None = None
    src_vid: str | None = None
    dst_vid: str | None = None
    relation_kind: str | None = None
    value_json: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    owner_did: str | None = None
    sensitivity_ord: int = 1
    flow_kind: str | None = None
    flow_at: str | None = None


_TABLE_TO_RECORD: dict[str, type] = {}


def _register_table(table: str):
    def deco(cls: type) -> type:
        _TABLE_TO_RECORD[table] = cls
        return cls

    return deco


_register_table("vertex_agent_observation")(ObservationRecord)
_register_table("vertex_agent_belief_state")(BeliefStateRecord)
_register_table("vertex_agent_prior_preference")(PriorPreferenceRecord)
_register_table("vertex_agent_active_inference_tick")(ActiveInferenceTickRecord)
_register_table("vertex_agent_action_proposal")(ActionProposalRecord)
_register_table("vertex_agent_realworld_effect")(RealworldEffectRecord)
_register_table("vertex_agent_homeostasis_snapshot")(HomeostasisSnapshotRecord)
_register_table("vertex_agent_dispatch_ledger")(DispatchLedgerRecord)
_register_table("vertex_agent_delegated_authority_policy")(DelegatedAuthorityPolicyRecord)
_register_table("vertex_agent_policy_adaptation_proposal")(PolicyAdaptationProposalRecord)
_register_table("vertex_agent_counterparty_model")(CounterpartyModelRecord)
_register_table("vertex_agent_protected_asset")(ProtectedAssetRecord)
_register_table("vertex_hakkou_ferment")(HakkouFermentRecord)
_register_table("vertex_kobo_agent")(KoboAgentRecord)
_register_table("vertex_kobo_prion")(KoboPrionRecord)
_register_table("edge_kobo_budding")(KoboBuddingRecord)
_register_table("edge_kabi_hypha")(KabiHyphaRecord)
_register_table("edge_kabi_anastomosis")(KabiAnastomosisRecord)
_register_table("vertex_kabi_network")(KabiNetworkRecord)
_register_table("vertex_kinoko_block")(KinokoBlockRecord)
_register_table("vertex_houshi_spore")(HoushiSporeRecord)
_register_table("edge_houshi_custody")(HoushiCustodyRecord)
_register_table("vertex_koke_fixation")(KokeFixationRecord)
_register_table("edge_koke_flow")(KokeFlowRecord)
_register_table("vertex_saikin_signal")(SaikinSignalRecord)
_register_table("vertex_saikin_colony")(SaikinColonyRecord)
_register_table("edge_saikin_transfer")(SaikinTransferRecord)
_register_table("edge_saikin_member")(SaikinMemberRecord)
_register_table("vertex_ki_absorb")(KiAbsorbRecord)
_register_table("vertex_ki_artifact")(KiArtifactRecord)
_register_table("vertex_ki_ring")(KiRingRecord)
_register_table("edge_ki_vascular")(KiVascularRecord)



_FLOAT_COL_TO_PERMILLE_FIELD: dict[str, str] = {
    "confidence": "confidence_permille",
    "uncertainty": "uncertainty_permille",
    "posterior_confidence": "posterior_confidence_permille",
    "posterior_entropy": "posterior_entropy_permille",
    "weight": "weight_permille",
    "compute_budget_remaining": "compute_budget_remaining_permille",
    "storage_pressure": "storage_pressure_permille",
    "error_rate_1h": "error_rate_1h_permille",
    "tool_success_rate_1h": "tool_success_rate_1h_permille",
    "energy_or_cost_proxy": "energy_or_cost_proxy_permille",
    "violation_cost": "violation_cost_permille",
    "reversibility_score": "reversibility_score_permille",
}


def _to_permille(value: object) -> int:
    try:
        return int(round(float(value or 0.0) * 1000))
    except (TypeError, ValueError):
        return 0


def _coerce_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "t", "yes", "y")
    return bool(value)


def row_to_record(table: str, row: dict[str, object]):
    """Convert a RW-shaped row dict into the matching dataclass instance.

    Floats in [0, 1] are converted to permille ints. Booleans are coerced
    from 0/1 / strings as needed. Unknown columns (sensitivity_ord aside)
    are dropped.
    """
    record_cls = _TABLE_TO_RECORD.get(table)
    if record_cls is None:
        raise KeyError(f"unknown table for belief substrate: {table}")
    field_names = {f.name for f in record_cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    bool_fields = {"hard_floor", "active", "mokuteki_gate_pass", "triple_witness_pass"}
    kwargs: dict[str, object] = {}
    for col, val in row.items():
        target = _FLOAT_COL_TO_PERMILLE_FIELD.get(col, col)
        if target not in field_names:
            continue
        if target.endswith("_permille") and col in _FLOAT_COL_TO_PERMILLE_FIELD:
            kwargs[target] = _to_permille(val)
        elif target in bool_fields:
            kwargs[target] = _coerce_bool(val)
        else:
            kwargs[target] = val
    return record_cls(**kwargs)


_TABLE_TO_PUT_METHOD: dict[str, str] = {
    "vertex_agent_observation": "put_observation",
    "vertex_agent_belief_state": "put_belief_state",
    "vertex_agent_prior_preference": "put_prior_preference",
    "vertex_agent_active_inference_tick": "put_active_inference_tick",
    "vertex_agent_action_proposal": "put_action_proposal",
    "vertex_agent_realworld_effect": "put_realworld_effect",
    "vertex_agent_homeostasis_snapshot": "put_homeostasis_snapshot",
    "vertex_agent_dispatch_ledger": "put_dispatch_ledger",
    "vertex_agent_delegated_authority_policy": "put_delegated_authority_policy",
    "vertex_agent_policy_adaptation_proposal": "put_policy_adaptation_proposal",
    "vertex_agent_counterparty_model": "put_counterparty_model",
    "vertex_agent_protected_asset": "put_protected_asset",
}


@runtime_checkable
class BeliefStore(Protocol):
    backend: str

    def put_row(self, table: str, row: dict[str, object]) -> str: ...
    def put_observation(self, rec: ObservationRecord) -> str: ...
    def put_belief_state(self, rec: BeliefStateRecord) -> str: ...
    def put_prior_preference(self, rec: PriorPreferenceRecord) -> str: ...
    def put_active_inference_tick(self, rec: ActiveInferenceTickRecord) -> str: ...
    def put_action_proposal(self, rec: ActionProposalRecord) -> str: ...
    def put_realworld_effect(self, rec: RealworldEffectRecord) -> str: ...
    def put_homeostasis_snapshot(self, rec: HomeostasisSnapshotRecord) -> str: ...
    def put_dispatch_ledger(self, rec: DispatchLedgerRecord) -> str: ...
    def put_delegated_authority_policy(self, rec: DelegatedAuthorityPolicyRecord) -> str: ...
    def put_policy_adaptation_proposal(self, rec: PolicyAdaptationProposalRecord) -> str: ...
    def put_counterparty_model(self, rec: CounterpartyModelRecord) -> str: ...
    def put_protected_asset(self, rec: ProtectedAssetRecord) -> str: ...
    def put_vertex_hakkou_ferment(self, rec: HakkouFermentRecord) -> str: ...
    def put_vertex_kobo_agent(self, rec: KoboAgentRecord) -> str: ...
    def put_vertex_kobo_prion(self, rec: KoboPrionRecord) -> str: ...
    def put_edge_kobo_budding(self, rec: KoboBuddingRecord) -> str: ...
    def put_edge_kabi_hypha(self, rec: KabiHyphaRecord) -> str: ...
    def put_edge_kabi_anastomosis(self, rec: KabiAnastomosisRecord) -> str: ...
    def put_vertex_kabi_network(self, rec: KabiNetworkRecord) -> str: ...
    def put_vertex_kinoko_block(self, rec: KinokoBlockRecord) -> str: ...
    def put_vertex_houshi_spore(self, rec: HoushiSporeRecord) -> str: ...
    def put_edge_houshi_custody(self, rec: HoushiCustodyRecord) -> str: ...
    def put_vertex_koke_fixation(self, rec: KokeFixationRecord) -> str: ...
    def put_edge_koke_flow(self, rec: KokeFlowRecord) -> str: ...
    def put_vertex_saikin_signal(self, rec: SaikinSignalRecord) -> str: ...
    def put_vertex_saikin_colony(self, rec: SaikinColonyRecord) -> str: ...
    def put_edge_saikin_transfer(self, rec: SaikinTransferRecord) -> str: ...
    def put_edge_saikin_member(self, rec: SaikinMemberRecord) -> str: ...
    def put_vertex_ki_absorb(self, rec: KiAbsorbRecord) -> str: ...
    def put_vertex_ki_artifact(self, rec: KiArtifactRecord) -> str: ...
    def put_vertex_ki_ring(self, rec: KiRingRecord) -> str: ...
    def put_edge_ki_vascular(self, rec: KiVascularRecord) -> str: ...


    def list_observations(
        self,
        agent_did: str,
        source_kinds: Sequence[str] | None = None,
        limit: int = 12,
    ) -> list[ObservationRecord]: ...

    def list_belief_states(
        self,
        agent_did: str,
        belief_kinds: Sequence[str] | None = None,
        limit: int = 12,
    ) -> list[BeliefStateRecord]: ...

    def count_realworld_effects_by_state(self, agent_did: str) -> dict[str, int]: ...
    def count_dispatch_ledger_by_state(self, agent_did: str) -> dict[str, int]: ...
    def list_recent_realworld_effects(
        self, agent_did: str, limit: int = 8
    ) -> list[RealworldEffectRecord]: ...
    def count_delegated_authority_by_status(self, agent_did: str) -> dict[str, int]: ...

    def stats(self) -> StoreStats: ...


import re as _re


_DID_ACTOR_RE = _re.compile(r"did:web:(?:etzhayyim-|etzhayyim-)?([a-z0-9-]+?)(?:\.etzhayyim\.ai)?$")


def _extract_actor_name(agent_did: str) -> str | None:
    """Best-effort extraction of the actor short-name from an agent DID.

    Examples:
      did:web:etzhayyim-kobo.etzhayyim.com -> "kobo"
      did:web:etzhayyim-kabi.etzhayyim.com     -> "kabi"
      did:web:kinoko.etzhayyim.com             -> "kinoko"
      did:plc:something                   -> None
    """
    if not agent_did:
        return None
    m = _DID_ACTOR_RE.match(agent_did.strip())
    if not m:
        return None
    name = m.group(1).split(".")[0]
    return name or None


def _resolve_backend_for_actor(env: dict[str, str], actor_name: str | None) -> str:
    if actor_name:
        per_actor_key = f"BELIEF_STORE_BACKEND_{actor_name.upper().replace('-', '_')}"
        per_actor = env.get(per_actor_key, "").strip().lower()
        if per_actor:
            return per_actor
    return env.get("BELIEF_STORE_BACKEND", "at-ipfs-local").strip().lower() or "at-ipfs-local"


def select_belief_store(env: dict[str, str] | None = None) -> BeliefStore:
    """Return the substrate store for the daemon.

    Phase 2D: if any `BELIEF_STORE_BACKEND_<ACTOR>` env var is set, returns a
    `_PerActorRouter` that resolves the backend per-row using `row['agent_did']`.
    Otherwise falls back to a single-backend store driven by `BELIEF_STORE_BACKEND`.
    """
    env = env if env is not None else dict(os.environ)
    if _has_per_actor_overrides(env):
        return _PerActorRouter(env)
    return _build_single_backend_store(env)


def _has_per_actor_overrides(env: dict[str, str]) -> bool:
    for key in env:
        if key.startswith("BELIEF_STORE_BACKEND_") and env[key].strip():
            return True
    return False


def _build_single_backend_store(env: dict[str, str]) -> BeliefStore:
    """Religious-corp variant: only at-ipfs-local backend is permitted.

    Per ADR-2605172000 (RW-free substrate) + ADR-2605211200 phase 2D, the
    RW + dual-write backends are removed. Any other value falls back to
    at-ipfs-local with a warning rather than raising — keeps the daemon
    resilient against env drift on heterogeneous Mac mini fleet nodes.
    """
    backend = env.get("BELIEF_STORE_BACKEND", "at-ipfs-local").strip().lower() or "at-ipfs-local"
    if backend not in ("at-ipfs-local",):
        import logging as _logging
        _logging.getLogger(__name__).warning(
            "BELIEF_STORE_BACKEND=%r is not supported in religious-corp; falling back to at-ipfs-local",
            backend,
        )
    from kotodama.primitives.at_ipfs_belief_store import AtIpfsLocalBeliefStore

    return AtIpfsLocalBeliefStore.from_env(env)


class _PerActorRouter:
    """Phase 2D router (ADR-2605211200). Inspects `row['agent_did']`, derives
    the actor short-name, picks `BELIEF_STORE_BACKEND_<ACTOR>` if set, and
    forwards the call to a cached per-(actor, backend) substrate store.

    Reads (list_observations / count_* / list_recent_*) take an explicit
    `agent_did` argument so the router can pick the same substrate the
    write went to.
    """

    backend = "per-actor"

    def __init__(self, env: dict[str, str]) -> None:
        self._env = env
        self._cache: dict[tuple[str | None, str], BeliefStore] = {}

    def _store_for(self, agent_did: str | None) -> BeliefStore:
        actor = _extract_actor_name(agent_did or "")
        backend = _resolve_backend_for_actor(self._env, actor)
        key = (actor, backend)
        if key not in self._cache:
            local_env = dict(self._env)
            local_env["BELIEF_STORE_BACKEND"] = backend
            if agent_did:
                local_env.setdefault("AGENT_DID", agent_did)
            self._cache[key] = _build_single_backend_store(local_env)
        return self._cache[key]

    def put_row(self, table: str, row: dict[str, object]) -> str:
        return self._store_for(str(row.get("agent_did") or "")).put_row(table, row)

    def _put_by_did(self, method: str, rec: object) -> str:
        did = str(getattr(rec, "agent_did", "") or "")
        return getattr(self._store_for(did), method)(rec)

    def put_observation(self, rec): return self._put_by_did("put_observation", rec)
    def put_belief_state(self, rec): return self._put_by_did("put_belief_state", rec)
    def put_prior_preference(self, rec): return self._put_by_did("put_prior_preference", rec)
    def put_active_inference_tick(self, rec): return self._put_by_did("put_active_inference_tick", rec)
    def put_action_proposal(self, rec): return self._put_by_did("put_action_proposal", rec)
    def put_realworld_effect(self, rec): return self._put_by_did("put_realworld_effect", rec)
    def put_homeostasis_snapshot(self, rec): return self._put_by_did("put_homeostasis_snapshot", rec)
    def put_dispatch_ledger(self, rec): return self._put_by_did("put_dispatch_ledger", rec)
    def put_delegated_authority_policy(self, rec): return self._put_by_did("put_delegated_authority_policy", rec)
    def put_policy_adaptation_proposal(self, rec): return self._put_by_did("put_policy_adaptation_proposal", rec)
    def put_counterparty_model(self, rec): return self._put_by_did("put_counterparty_model", rec)
    def put_protected_asset(self, rec): return self._put_by_did("put_protected_asset", rec)
    def put_vertex_hakkou_ferment(self, rec): return self._put_by_did('put_vertex_hakkou_ferment', rec)
    def put_vertex_kobo_agent(self, rec): return self._put_by_did('put_vertex_kobo_agent', rec)
    def put_vertex_kobo_prion(self, rec): return self._put_by_did('put_vertex_kobo_prion', rec)
    def put_edge_kobo_budding(self, rec): return self._put_by_did('put_edge_kobo_budding', rec)
    def put_edge_kabi_hypha(self, rec): return self._put_by_did('put_edge_kabi_hypha', rec)
    def put_edge_kabi_anastomosis(self, rec): return self._put_by_did('put_edge_kabi_anastomosis', rec)
    def put_vertex_kabi_network(self, rec): return self._put_by_did('put_vertex_kabi_network', rec)
    def put_vertex_kinoko_block(self, rec): return self._put_by_did('put_vertex_kinoko_block', rec)
    def put_vertex_houshi_spore(self, rec): return self._put_by_did('put_vertex_houshi_spore', rec)
    def put_edge_houshi_custody(self, rec): return self._put_by_did('put_edge_houshi_custody', rec)
    def put_vertex_koke_fixation(self, rec): return self._put_by_did('put_vertex_koke_fixation', rec)
    def put_edge_koke_flow(self, rec): return self._put_by_did('put_edge_koke_flow', rec)
    def put_vertex_saikin_signal(self, rec): return self._put_by_did('put_vertex_saikin_signal', rec)
    def put_vertex_saikin_colony(self, rec): return self._put_by_did('put_vertex_saikin_colony', rec)
    def put_edge_saikin_transfer(self, rec): return self._put_by_did('put_edge_saikin_transfer', rec)
    def put_edge_saikin_member(self, rec): return self._put_by_did('put_edge_saikin_member', rec)
    def put_vertex_ki_absorb(self, rec): return self._put_by_did('put_vertex_ki_absorb', rec)
    def put_vertex_ki_artifact(self, rec): return self._put_by_did('put_vertex_ki_artifact', rec)
    def put_vertex_ki_ring(self, rec): return self._put_by_did('put_vertex_ki_ring', rec)
    def put_edge_ki_vascular(self, rec): return self._put_by_did('put_edge_ki_vascular', rec)



    def list_observations(self, agent_did, source_kinds=None, limit=12):
        return self._store_for(agent_did).list_observations(agent_did, source_kinds, limit)

    def list_belief_states(self, agent_did, belief_kinds=None, limit=12):
        return self._store_for(agent_did).list_belief_states(agent_did, belief_kinds, limit)

    def count_realworld_effects_by_state(self, agent_did):
        return self._store_for(agent_did).count_realworld_effects_by_state(agent_did)

    def count_dispatch_ledger_by_state(self, agent_did):
        return self._store_for(agent_did).count_dispatch_ledger_by_state(agent_did)

    def list_recent_realworld_effects(self, agent_did, limit=8):
        return self._store_for(agent_did).list_recent_realworld_effects(agent_did, limit)

    def count_delegated_authority_by_status(self, agent_did):
        return self._store_for(agent_did).count_delegated_authority_by_status(agent_did)

    def stats(self) -> StoreStats:
        counts: dict[str, int] = {}
        for (actor, backend), store in self._cache.items():
            sub = store.stats()
            tag = f"{actor or 'unknown'}:{backend}"
            counts[tag] = sum(sub.counts.values()) if sub.counts else 0
        return StoreStats(backend="per-actor", counts=counts)


# NOTE: `_DualWriteBeliefStore` removed in religious-corp port.
# Per ADR-2605172000 (RW-free substrate), the dual-write wrapper that mirrored
# writes to RisingWave + at-ipfs-local is not applicable. religious-corp uses
# at-ipfs-local exclusively. Vendor retains the original class on its repo.


__all__ = [
    "BeliefStore",
    "ObservationRecord",
    "BeliefStateRecord",
    "PriorPreferenceRecord",
    "ActiveInferenceTickRecord",
    "ActionProposalRecord",
    "RealworldEffectRecord",
    "HomeostasisSnapshotRecord",
    "DispatchLedgerRecord",
    "DelegatedAuthorityPolicyRecord",
    "PolicyAdaptationProposalRecord",
    "CounterpartyModelRecord",
    "ProtectedAssetRecord",
    "StoreStats",
    "select_belief_store",
    "row_to_record",
    "HakkouFermentRecord",
    "KoboAgentRecord",
    "KoboPrionRecord",
    "KoboBuddingRecord",
    "KabiHyphaRecord",
    "KabiAnastomosisRecord",
    "KabiNetworkRecord",
    "KinokoBlockRecord",
    "HoushiSporeRecord",
    "HoushiCustodyRecord",
    "KokeFixationRecord",
    "KokeFlowRecord",
    "SaikinSignalRecord",
    "SaikinColonyRecord",
    "SaikinTransferRecord",
    "SaikinMemberRecord",
    "KiAbsorbRecord",
    "KiArtifactRecord",
    "KiRingRecord",
    "KiVascularRecord"
]
