"""
AT MST + IPFS + murakumo-local SQLite BeliefStore implementation.

Etzhayyim-substrate path for ADR-2605211200 (RW-free). Phase 1 ships the
SQLite hot-cache + lexicon-aligned row mapping; the AT publish callback is
injectable so tests can run without a live PDS. Phase 2 read-flip will set
the callback to a real PDS createRecord poster.

SQLite path: $ORGANISM_SQLITE_DIR/{agent_did_sanitized}.db (default
/var/lib/etzhayyim/organism).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Sequence

from kotodama.primitives.active_inference_substrate import (
    ActionProposalRecord,
    ActiveInferenceTickRecord,
    BeliefStateRecord,
    CounterpartyModelRecord,
    DelegatedAuthorityPolicyRecord,
    DispatchLedgerRecord,
    HomeostasisSnapshotRecord,
    ObservationRecord,
    PolicyAdaptationProposalRecord,
    PriorPreferenceRecord,
    ProtectedAssetRecord,
    RealworldEffectRecord,
    StoreStats,
)


PublishCallback = Callable[[str, str, dict[str, Any]], str | None]
"""Signature: (agent_did, collection_nsid, record_dict) -> at_uri | None."""


_DEFAULT_DIR = "/var/lib/etzhayyim/organism"
_DID_SAFE = re.compile(r"[^A-Za-z0-9_.:-]")


_SCHEMA = """
CREATE TABLE IF NOT EXISTS observation (
  vertex_id TEXT PRIMARY KEY, agent_did TEXT NOT NULL, source_kind TEXT NOT NULL,
  source_ref TEXT, observed_at TEXT NOT NULL, payload_json TEXT NOT NULL,
  confidence_permille INTEGER NOT NULL, uncertainty_permille INTEGER NOT NULL,
  sensitivity_ord INTEGER NOT NULL DEFAULT 1, at_uri TEXT
);
CREATE INDEX IF NOT EXISTS idx_observation_agent_time ON observation (agent_did, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_observation_source ON observation (source_kind);

CREATE TABLE IF NOT EXISTS belief_state (
  vertex_id TEXT PRIMARY KEY, agent_did TEXT NOT NULL, belief_kind TEXT NOT NULL,
  state_key TEXT NOT NULL, state_value_json TEXT NOT NULL, ipfs_cid TEXT,
  posterior_confidence_permille INTEGER NOT NULL, posterior_entropy_permille INTEGER NOT NULL,
  updated_from_observation TEXT, updated_at TEXT NOT NULL,
  sensitivity_ord INTEGER NOT NULL DEFAULT 1, at_uri TEXT
);
CREATE INDEX IF NOT EXISTS idx_belief_agent_kind ON belief_state (agent_did, belief_kind, state_key);
CREATE INDEX IF NOT EXISTS idx_belief_updated ON belief_state (agent_did, updated_at DESC);

CREATE TABLE IF NOT EXISTS prior_preference (
  vertex_id TEXT PRIMARY KEY, agent_did TEXT NOT NULL, preference_key TEXT NOT NULL,
  target_range_json TEXT NOT NULL, hard_floor INTEGER NOT NULL DEFAULT 0,
  weight_permille INTEGER NOT NULL, depends_on_adr TEXT, active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  sensitivity_ord INTEGER NOT NULL DEFAULT 1, at_uri TEXT
);
CREATE INDEX IF NOT EXISTS idx_prior_active ON prior_preference (agent_did, active, preference_key);

CREATE TABLE IF NOT EXISTS active_inference_tick (
  vertex_id TEXT PRIMARY KEY, agent_did TEXT NOT NULL, tick_kind TEXT NOT NULL,
  belief_snapshot_hash TEXT NOT NULL, candidate_actions_json TEXT NOT NULL,
  expected_free_energy_json TEXT NOT NULL, selected_action_id TEXT,
  mokuteki_gate_pass INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL,
  sensitivity_ord INTEGER NOT NULL DEFAULT 1, at_uri TEXT
);
CREATE INDEX IF NOT EXISTS idx_aif_tick_agent_time ON active_inference_tick (agent_did, created_at DESC);

CREATE TABLE IF NOT EXISTS action_proposal (
  vertex_id TEXT PRIMARY KEY, agent_did TEXT NOT NULL, action_kind TEXT NOT NULL,
  target_surface TEXT NOT NULL, proposal_json TEXT NOT NULL, simulation_ref TEXT,
  approval_ref TEXT, authority_ref TEXT, safety_state TEXT NOT NULL DEFAULT 'draft',
  dispatch_ref TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  sensitivity_ord INTEGER NOT NULL DEFAULT 1, at_uri TEXT
);
CREATE INDEX IF NOT EXISTS idx_action_agent_state ON action_proposal (agent_did, safety_state, created_at DESC);

CREATE TABLE IF NOT EXISTS realworld_effect (
  vertex_id TEXT PRIMARY KEY, action_proposal_id TEXT NOT NULL, agent_did TEXT NOT NULL,
  principal_did TEXT, channel TEXT NOT NULL, effect_class TEXT NOT NULL,
  target_ref_hash TEXT, payload_hash TEXT NOT NULL, summary TEXT NOT NULL,
  approval_ref TEXT, budget_ref TEXT, authority_ref TEXT, dispatch_state TEXT NOT NULL,
  dispatch_receipt_ref TEXT, settlement_tx_base TEXT, observation_plan_json TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  sensitivity_ord INTEGER NOT NULL DEFAULT 1, at_uri TEXT
);
CREATE INDEX IF NOT EXISTS idx_realworld_agent_state ON realworld_effect (agent_did, dispatch_state, updated_at DESC);

CREATE TABLE IF NOT EXISTS homeostasis_snapshot (
  vertex_id TEXT PRIMARY KEY, agent_did TEXT NOT NULL,
  compute_budget_remaining_permille INTEGER NOT NULL, storage_pressure_permille INTEGER NOT NULL,
  lease_seconds_remaining INTEGER NOT NULL, error_rate_1h_permille INTEGER NOT NULL,
  tool_success_rate_1h_permille INTEGER NOT NULL, energy_or_cost_proxy_permille INTEGER NOT NULL,
  viability_state TEXT NOT NULL, created_at TEXT NOT NULL,
  sensitivity_ord INTEGER NOT NULL DEFAULT 1, at_uri TEXT
);
CREATE INDEX IF NOT EXISTS idx_homeostasis_agent_time ON homeostasis_snapshot (agent_did, created_at DESC);

CREATE TABLE IF NOT EXISTS dispatch_ledger (
  vertex_id TEXT PRIMARY KEY, agent_did TEXT NOT NULL, dispatch_plan_id TEXT NOT NULL,
  realworld_effect_id TEXT, channel TEXT NOT NULL, task_type TEXT, payload_hash TEXT NOT NULL,
  authority_ref TEXT NOT NULL, policy_ref TEXT NOT NULL, dispatch_state TEXT NOT NULL,
  settlement_tx_base TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  sensitivity_ord INTEGER NOT NULL DEFAULT 1, at_uri TEXT
);
CREATE INDEX IF NOT EXISTS idx_dispatch_agent_state ON dispatch_ledger (agent_did, dispatch_state);

CREATE TABLE IF NOT EXISTS delegated_authority_policy (
  vertex_id TEXT PRIMARY KEY, authority_ref TEXT NOT NULL, policy_ref TEXT NOT NULL,
  agent_did TEXT NOT NULL, principal_did TEXT, channels_json TEXT NOT NULL,
  effect_classes_json TEXT NOT NULL, target_bindings_json TEXT NOT NULL,
  payload_constraints_json TEXT NOT NULL, budget_ref TEXT, rate_limit_json TEXT NOT NULL,
  expires_at TEXT NOT NULL, policy_cid TEXT, signature_ref TEXT NOT NULL,
  on_chain_delegation_root TEXT, status TEXT NOT NULL, created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL, sensitivity_ord INTEGER NOT NULL DEFAULT 1, at_uri TEXT
);
CREATE INDEX IF NOT EXISTS idx_authority_agent_status ON delegated_authority_policy (agent_did, status);

CREATE TABLE IF NOT EXISTS policy_adaptation_proposal (
  vertex_id TEXT PRIMARY KEY, agent_did TEXT NOT NULL, preference_key TEXT NOT NULL,
  proposal_hash TEXT NOT NULL, proposal_json TEXT NOT NULL,
  mokuteki_gate_pass INTEGER NOT NULL DEFAULT 0, triple_witness_pass INTEGER NOT NULL DEFAULT 0,
  blockers_json TEXT NOT NULL, proposal_state TEXT NOT NULL, created_at TEXT NOT NULL,
  sensitivity_ord INTEGER NOT NULL DEFAULT 1, at_uri TEXT
);
CREATE INDEX IF NOT EXISTS idx_policy_adapt_agent_state ON policy_adaptation_proposal (agent_did, proposal_state, created_at DESC);

CREATE TABLE IF NOT EXISTS counterparty_model (
  vertex_id TEXT PRIMARY KEY, agent_did TEXT NOT NULL, counterparty_ref TEXT NOT NULL,
  model_kind TEXT NOT NULL, prior_preferences_json TEXT NOT NULL,
  protected_assets_json TEXT NOT NULL, model_ipfs_cid TEXT,
  confidence_permille INTEGER NOT NULL, uncertainty_permille INTEGER NOT NULL,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  sensitivity_ord INTEGER NOT NULL DEFAULT 1, at_uri TEXT
);
CREATE INDEX IF NOT EXISTS idx_counterparty_agent ON counterparty_model (agent_did, counterparty_ref);

CREATE TABLE IF NOT EXISTS protected_asset (
  vertex_id TEXT PRIMARY KEY, agent_did TEXT NOT NULL, counterparty_ref TEXT NOT NULL,
  asset_ref TEXT NOT NULL, asset_kind TEXT NOT NULL, protected_state_json TEXT NOT NULL,
  violation_cost_permille INTEGER NOT NULL, reversibility_score_permille INTEGER NOT NULL,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  sensitivity_ord INTEGER NOT NULL DEFAULT 1, at_uri TEXT
);
CREATE INDEX IF NOT EXISTS idx_protected_asset_agent ON protected_asset (agent_did, counterparty_ref);

CREATE TABLE IF NOT EXISTS vertex_hakkou_ferment (
  vertex_id TEXT PRIMARY KEY,
  record_id TEXT,
  owner_did TEXT,
  label TEXT,
  status TEXT,
  stream_id TEXT,
  agent_did TEXT,
  value_json TEXT,
  created_at TEXT,
  updated_at TEXT,
  sensitivity_ord INTEGER NOT NULL DEFAULT 1,
  input_kind TEXT,
  input_ref TEXT,
  output_vertex_id TEXT,
  output_kind TEXT,
  ethanol_hash TEXT,
  co2_audit_ref TEXT,
  input_hash TEXT,
  fermented_at TEXT,
  at_uri TEXT
);

CREATE TABLE IF NOT EXISTS vertex_kobo_agent (
  vertex_id TEXT PRIMARY KEY,
  record_id TEXT,
  owner_did TEXT,
  label TEXT,
  status TEXT,
  stream_id TEXT,
  agent_did TEXT,
  value_json TEXT,
  created_at TEXT,
  updated_at TEXT,
  sensitivity_ord INTEGER NOT NULL DEFAULT 1,
  parent_did TEXT,
  role TEXT,
  eta REAL,
  stress_score REAL,
  at_uri TEXT
);

CREATE TABLE IF NOT EXISTS vertex_kobo_prion (
  vertex_id TEXT PRIMARY KEY,
  record_id TEXT,
  owner_did TEXT,
  label TEXT,
  status TEXT,
  stream_id TEXT,
  agent_did TEXT,
  value_json TEXT,
  created_at TEXT,
  updated_at TEXT,
  sensitivity_ord INTEGER NOT NULL DEFAULT 1,
  pattern_hash TEXT,
  heritable INTEGER,
  malignant_score REAL,
  content TEXT,
  at_uri TEXT
);

CREATE TABLE IF NOT EXISTS edge_kobo_budding (
  edge_id TEXT PRIMARY KEY,
  src_vid TEXT,
  dst_vid TEXT,
  relation_kind TEXT,
  value_json TEXT,
  created_at TEXT,
  updated_at TEXT,
  owner_did TEXT,
  sensitivity_ord INTEGER NOT NULL DEFAULT 1,
  parent_did TEXT,
  child_did TEXT,
  budded_at TEXT,
  prion_count INTEGER,
  at_uri TEXT
);

CREATE TABLE IF NOT EXISTS edge_kabi_hypha (
  edge_id TEXT PRIMARY KEY,
  src_vid TEXT,
  dst_vid TEXT,
  relation_kind TEXT,
  value_json TEXT,
  created_at TEXT,
  updated_at TEXT,
  owner_did TEXT,
  sensitivity_ord INTEGER NOT NULL DEFAULT 1,
  src_agent_did TEXT,
  dst_agent_did TEXT,
  eta REAL,
  flow REAL,
  pruned_at TEXT,
  at_uri TEXT
);

CREATE TABLE IF NOT EXISTS edge_kabi_anastomosis (
  edge_id TEXT PRIMARY KEY,
  src_vid TEXT,
  dst_vid TEXT,
  relation_kind TEXT,
  value_json TEXT,
  created_at TEXT,
  updated_at TEXT,
  owner_did TEXT,
  sensitivity_ord INTEGER NOT NULL DEFAULT 1,
  network_a_did TEXT,
  network_b_did TEXT,
  compatibility_score REAL,
  result TEXT,
  reason TEXT,
  at_uri TEXT
);

CREATE TABLE IF NOT EXISTS vertex_kabi_network (
  vertex_id TEXT PRIMARY KEY,
  record_id TEXT,
  owner_did TEXT,
  label TEXT,
  status TEXT,
  stream_id TEXT,
  agent_did TEXT,
  value_json TEXT,
  created_at TEXT,
  updated_at TEXT,
  sensitivity_ord INTEGER NOT NULL DEFAULT 1,
  root_agent_did TEXT,
  hypha_count INTEGER,
  total_flow REAL,
  at_uri TEXT
);

CREATE TABLE IF NOT EXISTS vertex_kinoko_block (
  vertex_id TEXT PRIMARY KEY,
  record_id TEXT,
  owner_did TEXT,
  label TEXT,
  status TEXT,
  stream_id TEXT,
  agent_did TEXT,
  value_json TEXT,
  created_at TEXT,
  updated_at TEXT,
  sensitivity_ord INTEGER NOT NULL DEFAULT 1,
  prev_block_id TEXT,
  block_hash TEXT,
  total_flow REAL,
  participant_count INTEGER,
  eta_min_used REAL,
  block_status TEXT,
  at_uri TEXT
);

CREATE TABLE IF NOT EXISTS vertex_houshi_spore (
  vertex_id TEXT PRIMARY KEY,
  record_id TEXT,
  owner_did TEXT,
  label TEXT,
  status TEXT,
  stream_id TEXT,
  agent_did TEXT,
  value_json TEXT,
  created_at TEXT,
  updated_at TEXT,
  sensitivity_ord INTEGER NOT NULL DEFAULT 1,
  origin_agent_did TEXT,
  blob_cbor TEXT,
  revival_key_hint TEXT,
  quorum_n INTEGER,
  germinated_at TEXT,
  at_uri TEXT
);

CREATE TABLE IF NOT EXISTS edge_houshi_custody (
  edge_id TEXT PRIMARY KEY,
  src_vid TEXT,
  dst_vid TEXT,
  relation_kind TEXT,
  value_json TEXT,
  created_at TEXT,
  updated_at TEXT,
  owner_did TEXT,
  sensitivity_ord INTEGER NOT NULL DEFAULT 1,
  custodian_did TEXT,
  custody_confirmed INTEGER,
  at_uri TEXT
);

CREATE TABLE IF NOT EXISTS vertex_koke_fixation (
  vertex_id TEXT PRIMARY KEY,
  record_id TEXT,
  owner_did TEXT,
  label TEXT,
  status TEXT,
  stream_id TEXT,
  agent_did TEXT,
  value_json TEXT,
  created_at TEXT,
  updated_at TEXT,
  sensitivity_ord INTEGER NOT NULL DEFAULT 1,
  input_kind TEXT,
  raw_ref TEXT,
  signal_hash TEXT,
  classification TEXT,
  confidence REAL,
  fixed_at TEXT,
  released_at TEXT,
  at_uri TEXT
);

CREATE TABLE IF NOT EXISTS edge_koke_flow (
  edge_id TEXT PRIMARY KEY,
  src_vid TEXT,
  dst_vid TEXT,
  relation_kind TEXT,
  value_json TEXT,
  created_at TEXT,
  updated_at TEXT,
  owner_did TEXT,
  sensitivity_ord INTEGER NOT NULL DEFAULT 1,
  fixation_id TEXT,
  ferment_id TEXT,
  handoff_kind TEXT,
  handed_off_at TEXT,
  at_uri TEXT
);

CREATE TABLE IF NOT EXISTS vertex_saikin_signal (
  vertex_id TEXT PRIMARY KEY,
  record_id TEXT,
  owner_did TEXT,
  label TEXT,
  status TEXT,
  stream_id TEXT,
  agent_did TEXT,
  value_json TEXT,
  created_at TEXT,
  updated_at TEXT,
  sensitivity_ord INTEGER NOT NULL DEFAULT 1,
  input_kind TEXT,
  raw_ref TEXT,
  signal_hash TEXT,
  probe_source TEXT,
  transferred_at TEXT,
  at_uri TEXT
);

CREATE TABLE IF NOT EXISTS vertex_saikin_colony (
  vertex_id TEXT PRIMARY KEY,
  record_id TEXT,
  owner_did TEXT,
  label TEXT,
  status TEXT,
  stream_id TEXT,
  agent_did TEXT,
  value_json TEXT,
  created_at TEXT,
  updated_at TEXT,
  sensitivity_ord INTEGER NOT NULL DEFAULT 1,
  colony_label TEXT,
  member_count INTEGER,
  formed_at TEXT,
  lysed_at TEXT,
  at_uri TEXT
);

CREATE TABLE IF NOT EXISTS edge_saikin_transfer (
  edge_id TEXT PRIMARY KEY,
  src_vid TEXT,
  dst_vid TEXT,
  relation_kind TEXT,
  value_json TEXT,
  created_at TEXT,
  updated_at TEXT,
  owner_did TEXT,
  sensitivity_ord INTEGER NOT NULL DEFAULT 1,
  signal_id TEXT,
  target_actor_did TEXT,
  transfer_kind TEXT,
  transferred_at TEXT,
  at_uri TEXT
);

CREATE TABLE IF NOT EXISTS edge_saikin_member (
  edge_id TEXT PRIMARY KEY,
  src_vid TEXT,
  dst_vid TEXT,
  relation_kind TEXT,
  value_json TEXT,
  created_at TEXT,
  updated_at TEXT,
  owner_did TEXT,
  sensitivity_ord INTEGER NOT NULL DEFAULT 1,
  colony_id TEXT,
  signal_id TEXT,
  joined_at TEXT,
  at_uri TEXT
);

CREATE TABLE IF NOT EXISTS vertex_ki_absorb (
  vertex_id TEXT PRIMARY KEY,
  record_id TEXT,
  owner_did TEXT,
  label TEXT,
  status TEXT,
  stream_id TEXT,
  agent_did TEXT,
  value_json TEXT,
  created_at TEXT,
  updated_at TEXT,
  sensitivity_ord INTEGER NOT NULL DEFAULT 1,
  source_vertex_id TEXT,
  input_kind TEXT,
  content_hash TEXT,
  absorbed_at TEXT,
  synthesized_at TEXT,
  at_uri TEXT
);

CREATE TABLE IF NOT EXISTS vertex_ki_artifact (
  vertex_id TEXT PRIMARY KEY,
  record_id TEXT,
  owner_did TEXT,
  label TEXT,
  status TEXT,
  stream_id TEXT,
  agent_did TEXT,
  value_json TEXT,
  created_at TEXT,
  updated_at TEXT,
  sensitivity_ord INTEGER NOT NULL DEFAULT 1,
  absorb_id TEXT,
  artifact_kind TEXT,
  synthesis TEXT,
  confidence REAL,
  artifact_hash TEXT,
  bloomed_at TEXT,
  at_uri TEXT
);

CREATE TABLE IF NOT EXISTS vertex_ki_ring (
  vertex_id TEXT PRIMARY KEY,
  record_id TEXT,
  owner_did TEXT,
  label TEXT,
  status TEXT,
  stream_id TEXT,
  agent_did TEXT,
  value_json TEXT,
  created_at TEXT,
  updated_at TEXT,
  sensitivity_ord INTEGER NOT NULL DEFAULT 1,
  period TEXT,
  snapshot_count INTEGER,
  ring_at TEXT,
  at_uri TEXT
);

CREATE TABLE IF NOT EXISTS edge_ki_vascular (
  edge_id TEXT PRIMARY KEY,
  src_vid TEXT,
  dst_vid TEXT,
  relation_kind TEXT,
  value_json TEXT,
  created_at TEXT,
  updated_at TEXT,
  owner_did TEXT,
  sensitivity_ord INTEGER NOT NULL DEFAULT 1,
  flow_kind TEXT,
  flow_at TEXT,
  at_uri TEXT
);

"""


# Phase 3 Stage D (ADR-2605212200) — NSID namespace switch.
#
# ORGANISM_NSID_NAMESPACE env selects the canonical write namespace:
#   - "etzhayyim"      (default, legacy): writes com.etzhayyim.agent.*
#   - "etzhayyim" (Phase 3 canonical): writes ai.etzhayyim.agent.*
#
# The dual-publish bundle from Stage C (PR #1362) means EITHER namespace
# validates on the PDS side. Operators flip this env var once their actor
# pods are confirmed reading both forms; legacy com.etzhayyim.* writes stay
# valid for the 30-day Stage C overlap.
_NSID_NAMESPACES = {
    "etzhayyim": "com.etzhayyim.agent",
    "etzhayyim": "ai.etzhayyim.agent",
}


def _organism_nsid_prefix() -> str:
    chosen = (os.environ.get("ORGANISM_NSID_NAMESPACE") or "etzhayyim").strip().lower()
    return _NSID_NAMESPACES.get(chosen, _NSID_NAMESPACES["etzhayyim"])


def _build_nsid_map() -> dict[str, str]:
    prefix = _organism_nsid_prefix()
    return {
        "observation": f"{prefix}.observation",
        "belief_state": f"{prefix}.beliefState",
        "prior_preference": f"{prefix}.priorPreference",
        "active_inference_tick": f"{prefix}.activeInferenceTick",
        "action_proposal": f"{prefix}.actionProposal",
        "realworld_effect": f"{prefix}.realworldEffect",
        "homeostasis_snapshot": f"{prefix}.homeostasisSnapshot",
        "dispatch_ledger": f"{prefix}.dispatchLedger",
        "delegated_authority_policy": f"{prefix}.delegatedAuthorityPolicy",
        "policy_adaptation_proposal": f"{prefix}.policyAdaptationProposal",
        "counterparty_model": f"{prefix}.counterpartyModel",
        "protected_asset": f"{prefix}.protectedAsset",
        "vertex_hakkou_ferment": f"{prefix}.hakkouFerment",
        "vertex_kobo_agent": f"{prefix}.koboAgent",
        "vertex_kobo_prion": f"{prefix}.koboPrion",
        "edge_kobo_budding": f"{prefix}.koboBudding",
        "edge_kabi_hypha": f"{prefix}.kabiHypha",
        "edge_kabi_anastomosis": f"{prefix}.kabiAnastomosis",
        "vertex_kabi_network": f"{prefix}.kabiNetwork",
        "vertex_kinoko_block": f"{prefix}.kinokoBlock",
        "vertex_houshi_spore": f"{prefix}.houshiSpore",
        "edge_houshi_custody": f"{prefix}.houshiCustody",
        "vertex_koke_fixation": f"{prefix}.kokeFixation",
        "edge_koke_flow": f"{prefix}.kokeFlow",
        "vertex_saikin_signal": f"{prefix}.saikinSignal",
        "vertex_saikin_colony": f"{prefix}.saikinColony",
        "edge_saikin_transfer": f"{prefix}.saikinTransfer",
        "edge_saikin_member": f"{prefix}.saikinMember",
        "vertex_ki_absorb": f"{prefix}.kiAbsorb",
        "vertex_ki_artifact": f"{prefix}.kiArtifact",
        "vertex_ki_ring": f"{prefix}.kiRing",
        "edge_ki_vascular": f"{prefix}.kiVascular",

    }


_NSID_BY_TABLE = _build_nsid_map()


def refresh_nsid_map() -> None:
    """Test / hot-reload helper. Re-reads ORGANISM_NSID_NAMESPACE and
    rebuilds _NSID_BY_TABLE. Production runtime flips via pod restart
    (which re-runs the module-level _build_nsid_map()) and does not call
    this directly.
    """
    global _NSID_BY_TABLE
    _NSID_BY_TABLE = _build_nsid_map()


def _stable_vertex_id(prefix: str, key: dict[str, Any]) -> str:
    blob = json.dumps(key, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"{prefix}-{hashlib.sha256(blob).hexdigest()[:24]}"


def _sanitize_did(agent_did: str) -> str:
    return _DID_SAFE.sub("_", agent_did)[:120] or "anon"


def _normalize(value: Any) -> Any:
    if isinstance(value, bool):
        return 1 if value else 0
    return value


def _row_dict(rec: Any, *, prefix: str, key_fields: tuple[str, ...]) -> dict[str, Any]:
    raw = asdict(rec)
    is_edge = "edge_id" in raw
    pk_col = "edge_id" if is_edge else "vertex_id"
    pk_val = raw.get(pk_col) or _stable_vertex_id(
        prefix, {k: raw[k] for k in key_fields if k in raw}
    )
    raw[pk_col] = pk_val
    return {k: _normalize(v) for k, v in raw.items()}


def _lexicon_payload(row: dict[str, Any]) -> dict[str, Any]:
    skip = {"vertex_id", "at_uri"}
    return {k: v for k, v in row.items() if k not in skip and v is not None}


class AtIpfsLocalBeliefStore:
    backend = "at-ipfs-local"

    def put_row(self, table: str, row: dict[str, Any]) -> str:
        from kotodama.primitives.active_inference_substrate import (
            _TABLE_TO_PUT_METHOD,
            row_to_record,
        )

        method_name = _TABLE_TO_PUT_METHOD.get(table)
        if method_name is None:
            raise KeyError(f"AtIpfsLocalBeliefStore has no handler for {table}")
        record = row_to_record(table, row)
        return getattr(self, method_name)(record)

    def __init__(
        self,
        *,
        db_path: str | Path,
        publish: PublishCallback | None = None,
    ) -> None:
        self._db_path = str(db_path)
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._publish = publish
        self._lock = threading.Lock()
        self._init_schema()

    @classmethod
    def from_env(cls, env: dict[str, str]) -> "AtIpfsLocalBeliefStore":
        directory = env.get("ORGANISM_SQLITE_DIR", _DEFAULT_DIR)
        agent_did = env.get("AGENT_DID") or env.get("AGENT_ATPROTO_DID") or "anon"
        Path(directory).mkdir(parents=True, exist_ok=True)
        return cls(db_path=f"{directory}/{_sanitize_did(agent_did)}.db")

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        return conn

    def _init_schema(self) -> None:
        with self._lock, self._conn() as conn:
            conn.executescript(_SCHEMA)
            conn.commit()

    def _put(self, table: str, row: dict[str, Any]) -> str:
        publish_uri: str | None = None
        if self._publish is not None:
            nsid = _NSID_BY_TABLE[table]
            try:
                publish_uri = self._publish(row.get("agent_did", ""), nsid, _lexicon_payload(row))
            except Exception:
                publish_uri = None
        row_to_persist = dict(row)
        if publish_uri:
            row_to_persist["at_uri"] = publish_uri
        cols = list(row_to_persist)
        placeholders = ",".join(["?"] * len(cols))
        col_list = ",".join(cols)
        with self._lock, self._conn() as conn:
            pk_col = "edge_id" if table.startswith("edge_") else "vertex_id"
            conn.execute(f"DELETE FROM {table} WHERE {pk_col} = ?", (row_to_persist[pk_col],))
            conn.execute(
                f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})",
                tuple(row_to_persist[c] for c in cols),
            )
            conn.commit()
        return publish_uri or row_to_persist.get("vertex_id") or row_to_persist.get("edge_id") or ""

    def put_observation(self, rec: ObservationRecord) -> str:
        row = _row_dict(rec, prefix="agent-observation", key_fields=("agent_did", "source_kind", "source_ref", "observed_at"))
        return self._put("observation", row)

    def put_belief_state(self, rec: BeliefStateRecord) -> str:
        row = _row_dict(rec, prefix="agent-belief", key_fields=("agent_did", "belief_kind", "state_key"))
        return self._put("belief_state", row)

    def put_prior_preference(self, rec: PriorPreferenceRecord) -> str:
        row = _row_dict(rec, prefix="agent-prior", key_fields=("agent_did", "preference_key"))
        return self._put("prior_preference", row)

    def put_active_inference_tick(self, rec: ActiveInferenceTickRecord) -> str:
        row = _row_dict(rec, prefix="agent-aif-tick", key_fields=("agent_did", "tick_kind", "belief_snapshot_hash"))
        return self._put("active_inference_tick", row)

    def put_action_proposal(self, rec: ActionProposalRecord) -> str:
        row = _row_dict(rec, prefix="agent-action", key_fields=("agent_did", "action_kind", "created_at"))
        return self._put("action_proposal", row)

    def put_realworld_effect(self, rec: RealworldEffectRecord) -> str:
        row = _row_dict(rec, prefix="agent-realworld", key_fields=("action_proposal_id", "channel"))
        return self._put("realworld_effect", row)

    def put_homeostasis_snapshot(self, rec: HomeostasisSnapshotRecord) -> str:
        row = _row_dict(rec, prefix="agent-homeostasis", key_fields=("agent_did", "created_at"))
        return self._put("homeostasis_snapshot", row)

    def put_dispatch_ledger(self, rec: DispatchLedgerRecord) -> str:
        row = _row_dict(rec, prefix="agent-dispatch", key_fields=("agent_did", "dispatch_plan_id"))
        return self._put("dispatch_ledger", row)

    def put_delegated_authority_policy(self, rec: DelegatedAuthorityPolicyRecord) -> str:
        row = _row_dict(rec, prefix="agent-authority", key_fields=("authority_ref", "policy_ref"))
        return self._put("delegated_authority_policy", row)

    def put_policy_adaptation_proposal(self, rec: PolicyAdaptationProposalRecord) -> str:
        row = _row_dict(rec, prefix="agent-policy-adapt", key_fields=("agent_did", "preference_key", "proposal_hash"))
        return self._put("policy_adaptation_proposal", row)

    def put_counterparty_model(self, rec: CounterpartyModelRecord) -> str:
        row = _row_dict(rec, prefix="agent-counterparty", key_fields=("agent_did", "counterparty_ref", "model_kind"))
        return self._put("counterparty_model", row)

    def put_protected_asset(self, rec: ProtectedAssetRecord) -> str:
        row = _row_dict(rec, prefix="agent-protected-asset", key_fields=("agent_did", "counterparty_ref", "asset_ref"))
        return self._put("protected_asset", row)

    def put_vertex_hakkou_ferment(self, rec: HakkouFermentRecord) -> str:
        row = _row_dict(rec, prefix="hakkou-ferment", key_fields=("agent_did", "created_at"))
        return self._put("vertex_hakkou_ferment", row)

    def put_vertex_kobo_agent(self, rec: KoboAgentRecord) -> str:
        row = _row_dict(rec, prefix="kobo-agent", key_fields=("agent_did", "created_at"))
        return self._put("vertex_kobo_agent", row)

    def put_vertex_kobo_prion(self, rec: KoboPrionRecord) -> str:
        row = _row_dict(rec, prefix="kobo-prion", key_fields=("agent_did", "created_at"))
        return self._put("vertex_kobo_prion", row)

    def put_edge_kobo_budding(self, rec: KoboBuddingRecord) -> str:
        row = _row_dict(rec, prefix="kobo-budding", key_fields=("src_vid", "dst_vid"))
        return self._put("edge_kobo_budding", row)

    def put_edge_kabi_hypha(self, rec: KabiHyphaRecord) -> str:
        row = _row_dict(rec, prefix="kabi-hypha", key_fields=("src_vid", "dst_vid"))
        return self._put("edge_kabi_hypha", row)

    def put_edge_kabi_anastomosis(self, rec: KabiAnastomosisRecord) -> str:
        row = _row_dict(rec, prefix="kabi-anastomosis", key_fields=("src_vid", "dst_vid"))
        return self._put("edge_kabi_anastomosis", row)

    def put_vertex_kabi_network(self, rec: KabiNetworkRecord) -> str:
        row = _row_dict(rec, prefix="kabi-network", key_fields=("agent_did", "created_at"))
        return self._put("vertex_kabi_network", row)

    def put_vertex_kinoko_block(self, rec: KinokoBlockRecord) -> str:
        row = _row_dict(rec, prefix="kinoko-block", key_fields=("agent_did", "created_at"))
        return self._put("vertex_kinoko_block", row)

    def put_vertex_houshi_spore(self, rec: HoushiSporeRecord) -> str:
        row = _row_dict(rec, prefix="houshi-spore", key_fields=("agent_did", "created_at"))
        return self._put("vertex_houshi_spore", row)

    def put_edge_houshi_custody(self, rec: HoushiCustodyRecord) -> str:
        row = _row_dict(rec, prefix="houshi-custody", key_fields=("src_vid", "dst_vid"))
        return self._put("edge_houshi_custody", row)

    def put_vertex_koke_fixation(self, rec: KokeFixationRecord) -> str:
        row = _row_dict(rec, prefix="koke-fixation", key_fields=("agent_did", "created_at"))
        return self._put("vertex_koke_fixation", row)

    def put_edge_koke_flow(self, rec: KokeFlowRecord) -> str:
        row = _row_dict(rec, prefix="koke-flow", key_fields=("src_vid", "dst_vid"))
        return self._put("edge_koke_flow", row)

    def put_vertex_saikin_signal(self, rec: SaikinSignalRecord) -> str:
        row = _row_dict(rec, prefix="saikin-signal", key_fields=("agent_did", "created_at"))
        return self._put("vertex_saikin_signal", row)

    def put_vertex_saikin_colony(self, rec: SaikinColonyRecord) -> str:
        row = _row_dict(rec, prefix="saikin-colony", key_fields=("agent_did", "created_at"))
        return self._put("vertex_saikin_colony", row)

    def put_edge_saikin_transfer(self, rec: SaikinTransferRecord) -> str:
        row = _row_dict(rec, prefix="saikin-transfer", key_fields=("src_vid", "dst_vid"))
        return self._put("edge_saikin_transfer", row)

    def put_edge_saikin_member(self, rec: SaikinMemberRecord) -> str:
        row = _row_dict(rec, prefix="saikin-member", key_fields=("src_vid", "dst_vid"))
        return self._put("edge_saikin_member", row)

    def put_vertex_ki_absorb(self, rec: KiAbsorbRecord) -> str:
        row = _row_dict(rec, prefix="ki-absorb", key_fields=("agent_did", "created_at"))
        return self._put("vertex_ki_absorb", row)

    def put_vertex_ki_artifact(self, rec: KiArtifactRecord) -> str:
        row = _row_dict(rec, prefix="ki-artifact", key_fields=("agent_did", "created_at"))
        return self._put("vertex_ki_artifact", row)

    def put_vertex_ki_ring(self, rec: KiRingRecord) -> str:
        row = _row_dict(rec, prefix="ki-ring", key_fields=("agent_did", "created_at"))
        return self._put("vertex_ki_ring", row)

    def put_edge_ki_vascular(self, rec: KiVascularRecord) -> str:
        row = _row_dict(rec, prefix="ki-vascular", key_fields=("src_vid", "dst_vid"))
        return self._put("edge_ki_vascular", row)



    def list_observations(
        self,
        agent_did: str,
        source_kinds: Sequence[str] | None = None,
        limit: int = 12,
    ) -> list[ObservationRecord]:
        with self._lock, self._conn() as conn:
            if source_kinds:
                marks = ",".join(["?"] * len(source_kinds))
                cur = conn.execute(
                    f"SELECT * FROM observation WHERE agent_did = ? AND source_kind IN ({marks}) "
                    f"ORDER BY observed_at DESC LIMIT ?",
                    (agent_did, *source_kinds, int(limit)),
                )
            else:
                cur = conn.execute(
                    "SELECT * FROM observation WHERE agent_did = ? ORDER BY observed_at DESC LIMIT ?",
                    (agent_did, int(limit)),
                )
            return [_project(ObservationRecord, dict(row)) for row in cur.fetchall()]

    def list_belief_states(
        self,
        agent_did: str,
        belief_kinds: Sequence[str] | None = None,
        limit: int = 12,
    ) -> list[BeliefStateRecord]:
        with self._lock, self._conn() as conn:
            if belief_kinds:
                marks = ",".join(["?"] * len(belief_kinds))
                cur = conn.execute(
                    f"SELECT * FROM belief_state WHERE agent_did = ? AND belief_kind IN ({marks}) "
                    f"ORDER BY updated_at DESC LIMIT ?",
                    (agent_did, *belief_kinds, int(limit)),
                )
            else:
                cur = conn.execute(
                    "SELECT * FROM belief_state WHERE agent_did = ? ORDER BY updated_at DESC LIMIT ?",
                    (agent_did, int(limit)),
                )
            return [_project(BeliefStateRecord, dict(row)) for row in cur.fetchall()]

    def count_realworld_effects_by_state(self, agent_did: str) -> dict[str, int]:
        with self._lock, self._conn() as conn:
            cur = conn.execute(
                "SELECT dispatch_state, COUNT(*) AS c FROM realworld_effect WHERE agent_did = ? GROUP BY dispatch_state",
                (agent_did,),
            )
            return {row["dispatch_state"]: int(row["c"]) for row in cur.fetchall()}

    def count_dispatch_ledger_by_state(self, agent_did: str) -> dict[str, int]:
        with self._lock, self._conn() as conn:
            cur = conn.execute(
                "SELECT dispatch_state, COUNT(*) AS c FROM dispatch_ledger WHERE agent_did = ? GROUP BY dispatch_state",
                (agent_did,),
            )
            return {row["dispatch_state"]: int(row["c"]) for row in cur.fetchall()}

    def list_recent_realworld_effects(
        self, agent_did: str, limit: int = 8
    ) -> list[RealworldEffectRecord]:
        with self._lock, self._conn() as conn:
            cur = conn.execute(
                "SELECT * FROM realworld_effect WHERE agent_did = ? ORDER BY updated_at DESC LIMIT ?",
                (agent_did, int(limit)),
            )
            return [_project(RealworldEffectRecord, dict(row)) for row in cur.fetchall()]

    def count_delegated_authority_by_status(self, agent_did: str) -> dict[str, int]:
        with self._lock, self._conn() as conn:
            cur = conn.execute(
                "SELECT status, COUNT(*) AS c FROM delegated_authority_policy WHERE agent_did = ? GROUP BY status",
                (agent_did,),
            )
            return {row["status"]: int(row["c"]) for row in cur.fetchall()}

    def stats(self) -> StoreStats:
        counts: dict[str, int] = {}
        with self._lock, self._conn() as conn:
            for table in _NSID_BY_TABLE:
                cur = conn.execute(f"SELECT COUNT(*) AS c FROM {table}")
                counts[table] = int(cur.fetchone()["c"])
        return StoreStats(backend=self.backend, counts=counts)


def _project(record_cls, row: dict[str, Any]) -> Any:
    from dataclasses import fields as _fields

    known = {f.name for f in _fields(record_cls)}
    kwargs: dict[str, Any] = {}
    for col, val in row.items():
        if col not in known:
            continue
        if col in ("hard_floor", "active", "mokuteki_gate_pass", "triple_witness_pass"):
            kwargs[col] = bool(val)
        else:
            kwargs[col] = val
    return record_cls(**kwargs)


__all__ = ["AtIpfsLocalBeliefStore", "PublishCallback"]
