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
pub mod gossip;
pub mod membrane;
pub mod neighborhood;
pub mod neighborhood_store;
pub mod node_id;
pub mod replication;
pub mod reputation;
pub mod settlement;
pub mod source_chain;
pub mod warrant;

pub use audit::{
    availability_slash_warrant, AuditAction, AuditScheduler, AvailabilityAuditor,
    AvailabilityEvidence, InMemoryVerdictSink, PeerAudit, PeerReputation, ProofFetcher,
    SettlementIntent, SettlementIntentSink, SettlementKind, VerdictSink,
};
pub use commit_chain::CommitChain;
pub use membrane::{bonded_candidates, select_replicas, stake_to_replicate_enabled, ReplicaCandidate};
pub use neighborhood::Neighborhood;
pub use replication::{audit_replication, ReplicationPolicy, ReplicationStatus};
pub use reputation::{prefer_by_reputation, EarnRateBand};
pub use neighborhood_store::{
    cid_address, proof_from_store, NeighborhoodBlockStore, PeerTransport,
};
pub use node_id::NodeId;
pub use settlement::{RetainerOwed, SettlementBatch, SettlementLine, SettlementSchedule};
pub use source_chain::{ChainContent, ChainEntry, SourceChain};
pub use warrant::{warrant_signing_bytes, ValidationRule, Warrant};
