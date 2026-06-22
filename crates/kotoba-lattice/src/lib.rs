//! kotoba-lattice — KOTOBA Mesh control plane core.
//!
//! The *missing layer* that turns kotoba (WASM runtime + libp2p mesh + CID
//! distribution + CACAO capabilities) into a wasmCloud/Spin-style distributed
//! WASM hosting fabric. See `docs/ADR-kotoba-mesh-wasm-hosting.md`.
//!
//! Prior art (ADR §2/§14): control plane = **wasmCloud** (lattice / auction /
//! link), component+trigger DX = **Spin**, agency model = **Holochain**, and the
//! default component language = **Clojure/EDN/Datomic** via `kotoba-clj`.
//!
//! ```text
//! ┌─ L5  manifest (EDN) + reconciler ……… this crate: manifest + reconcile
//! ├─ L4  lattice control plane (gossipsub) … this crate: protocol
//! ├─ L3  WASM host (kotoba-runtime)
//! ├─ L2  CACAO capability (kotoba-auth)
//! ├─ L1  CID distribution (kotoba-store)
//! └─ L0  libp2p mesh (kotoba-net)
//! ```
//!
//! This crate is intentionally **pure** (no wasmtime / no libp2p): it owns the
//! protocol *types*, the EDN *manifest* parser, and the leader-less
//! *reconcile + auction* logic. The transport wiring lives in kotoba-net /
//! kotoba-server which depend on this.

pub mod error;
pub mod manifest;
pub mod node;
pub mod protocol;
pub mod reconcile;

pub use error::LatticeError;
pub use manifest::{AppManifest, ComponentSpec, Lang, LinkSpec, Placement, TriggerSpec};
pub use node::{LatticeController, RecordingTransport, Transport};
pub use protocol::{
    topic, Auction, Award, Bid, Constraints, Heartbeat, LatticeMessage, Link, NodeRole,
};
pub use reconcile::{award_winners, need_actions, observed_counts, score_bid, NeedAction};
