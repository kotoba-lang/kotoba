//! # kotoba-vault — blob + key custody layer of KOTOBA
#![allow(clippy::items_after_test_module)]
//!
//! Renamed from `kotoba-kse` (KSE = Kotoba Stream Engine) on 2026-06-12: the
//! stream-engine half (the block-persisting Journal/Merkle-WAL) was deprecated
//! (#115) and physically removed, so the crate now carries its real contents'
//! name. The WIT interface `kotoba:kais/kse` is ABI and unchanged.
//!
//! Modules: [`store`] (`VaultStore`), [`chunker`] + [`vault`] (file-type
//! chunking → BlobManifest CID → CAR flush), [`secure_vault`], [`shelf`],
//! [`pre_key_registry`] (hybrid PRE re-key delivery), [`agent_identity`] /
//! [`sovereign_key`] (Ed25519+X25519 agent keys), [`topic`], [`sync_window`],
//! and [`live_bus`] — the in-memory pub/sub bus that remains of the Journal
//! (ephemeral live-tail only; durable history = CommitDag, replayed via
//! `sync.eventsFromCommits`).
pub mod agent_identity;
pub mod chunker;
pub mod keychain;
pub mod live_bus;
pub mod pre_key_registry;
pub mod secure_vault;
pub mod shelf;
pub mod sovereign_key;
pub mod store;
pub mod sync_window;
pub mod topic;
pub mod vault;

pub use agent_identity::AgentIdentity;
pub use live_bus::{Cursor, LiveBus, LiveBusEntry};
pub use pre_key_registry::{
    PreKeyError, PreKeyRegistry, RekeyRevocationRecord, RULE_REKEY_REVOKED,
};
pub use secure_vault::SecureVault;
pub use shelf::{Shelf, ShelfBucket};
pub use sovereign_key::SovereignCrypto;
pub use store::VaultStore;
pub use sync_window::SyncWindow;
pub use topic::{Topic, TopicPattern};
pub use vault::{BlobRef, Vault};
