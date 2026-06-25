//! # kotoba-dht — **KDHT = Kotoba Distributed Hash Table**
//!
//! Agent-centric integrity layer of KOTOBA: per-agent [`source_chain`]s,
//! [`warrant`]s (signed misbehaviour evidence), [`neighborhood`] validator
//! assignment, [`gossip`], [`commit_chain`], [`audit`], and [`settlement`].
//! No central master node — validation authority is distributed across
//! DHT neighborhoods.
pub mod audit;
pub mod availability_proof;
pub mod commit_chain;
pub mod dna;
pub mod engi_chain;
pub mod gossip;
pub mod governance;
pub mod membrane;
pub mod neighborhood;
pub mod neighborhood_store;
pub mod node_id;
pub mod replication;
pub mod reputation;
pub mod settlement;
pub mod source_chain;
pub mod validation;
pub mod warrant;

pub use audit::{
    availability_slash_warrant, AuditAction, AuditScheduler, AvailabilityAuditor,
    AvailabilityEvidence, InMemoryVerdictSink, PeerAudit, PeerReputation, ProofFetcher,
    SettlementIntent, SettlementIntentSink, SettlementKind, SlashSchedule, SlashWarrant,
    VerdictSink,
};
pub use commit_chain::CommitChain;
pub use dna::{DnaManifest, ValidationRuleRef};
pub use engi_chain::{
    audit_peer_chain, audit_transfers, detect_fork, detect_transfer_forks, mutual_credit_warrant,
    replay_balance, validate_chain_transfers, verify_warrant, EngiChain, EngiChainError,
    InsolvencyFinding, MutualCreditTransfer, SeenTransfers, TransferAccusation, TransferBody,
    TransferFork, TransferViolation, WarrantTally, ENGI_TRANSFER_TOPIC, ENGI_WARRANT_TOPIC,
    SEEN_TRANSFERS_CAP, WARRANT_EVICTION_THRESHOLD,
};
pub use governance::{
    ratify, verify_and_ratify, ActiveParams, Attestation, ParamVersion, Ratification,
};
pub use membrane::{
    bonded_candidates, select_replicas, stake_to_replicate_enabled, ReplicaCandidate,
};
pub use neighborhood::Neighborhood;
pub use neighborhood_store::{
    cid_address, proof_from_store, NeighborhoodBlockStore, PeerTransport,
};
pub use node_id::NodeId;
pub use replication::{
    audit_replication, replication_plan, ReplicationPolicy, ReplicationPolicyStore,
    ReplicationStatus,
};
pub use reputation::{prefer_by_reputation, EarnRateBand};
pub use settlement::{RetainerOwed, SettlementBatch, SettlementLine, SettlementSchedule};
pub use source_chain::{ChainContent, ChainEntry, SourceChain};
pub use validation::{enforce, load_rules, validate_tx, PhysicsRule, RuleSpec, ValidationOutcome};
pub use warrant::{warrant_signing_bytes, ValidationRule, Warrant};
