//! # kotoba-kse — **KSE = Kotoba Stream Engine**
//!
//! Blob + key custody layer of KOTOBA: [`store`] (`KseStore`), [`chunker`] +
//! Vault (file-type chunking → BlobManifest CID → CAR flush), [`secure_vault`],
//! [`shelf`], [`pre_key_registry`] (hybrid PRE re-key delivery),
//! [`agent_identity`] / [`sovereign_key`] (Ed25519+X25519 agent keys), and
//! [`topic`] / [`journal`] (pub/sub event stream).
//!
//! ## ⚠ Journal deprecation (2026-06-11, etzhayyim/kotoba#115)
//!
//! The [`journal`] module is **deprecated as a canonical/accountability
//! structure** — the CommitDag (`kotoba-datomic` `DistributedDatomCommit`:
//! content-addressed, parent hash-chain, author DID, signed IPNS heads,
//! Base-anchorable) is THE canonical chain. Do not build new features on the
//! Journal. Its remaining sanctioned role is the **ephemeral live-tail**
//! (`publish_ephemeral`: broadcast + ring buffer, no block persist); durable
//! replay is served from the CommitDag (`sync.eventsFromCommits`).
//! Vault / SecureVault / Shelf / PreKeyRegistry in this crate are **not**
//! deprecated.
pub mod agent_identity;
pub mod chunker;
pub mod journal;
pub mod keychain;
pub mod pre_key_registry;
pub mod secure_vault;
pub mod shelf;
pub mod sovereign_key;
pub mod store;
pub mod sync_window;
pub mod topic;
pub mod vault;

pub use agent_identity::AgentIdentity;
pub use journal::{Cursor, Journal, JournalEntry};
pub use pre_key_registry::{
    PreKeyError, PreKeyRegistry, RekeyRevocationRecord, RULE_REKEY_REVOKED,
};
pub use secure_vault::SecureVault;
pub use shelf::{Shelf, ShelfBucket};
pub use sovereign_key::SovereignCrypto;
pub use store::KseStore;
pub use sync_window::SyncWindow;
pub use topic::{Topic, TopicPattern};
pub use vault::{BlobRef, Vault};
