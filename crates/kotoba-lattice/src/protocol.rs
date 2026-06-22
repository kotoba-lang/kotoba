//! Lattice control-plane wire protocol (ADR §6).
//!
//! wasmCloud uses NATS for the lattice; KOTOBA Mesh uses libp2p **gossipsub**
//! over a reserved topic space. Every message is CBOR + (transport-signed).
//! No central master: placement is by **auction**, not a central scheduler.

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

use crate::error::LatticeError;

/// Reserved gossipsub topic names for the lattice control plane.
pub mod topic {
    /// Node liveness + inventory advertisement (placement input).
    pub const HEARTBEAT: &str = "kotoba/lat/heartbeat";
    /// Inventory request/response (observed-state queries).
    pub const INVENTORY: &str = "kotoba/lat/inventory";
    /// Control commands: start/stop/scale a component.
    pub const CMD: &str = "kotoba/lat/cmd";
    /// Link (capability binding) put/del.
    pub const LINK: &str = "kotoba/lat/link";
    /// Placement auction: request / bid / award.
    pub const AUCTION: &str = "kotoba/lat/auction";
}

/// What a node is willing to do in the lattice. Mirrors `KOTOBA_NODE_ROLES`
/// (kotoba-server net_actor): a node opts into compute hosting and/or relaying.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum NodeRole {
    /// Pins/serves content-addressed blocks (artifacts, datoms).
    Pin,
    /// Hosts and executes WASM components (auction-eligible).
    Compute,
    /// Firehose / NAT relay peer.
    Relay,
}

/// Periodic node advertisement published to [`topic::HEARTBEAT`]. Carries the
/// material the auction needs to place components: labels, free capacity, and
/// the capabilities this node can supply as host-imports/providers.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Heartbeat {
    /// DID of the advertising node (did:key).
    pub node_did: String,
    /// Roles this node has opted into.
    pub roles: Vec<NodeRole>,
    /// Placement labels (e.g. {"zone":"jp","tier":"edge"}).
    #[serde(default)]
    pub labels: BTreeMap<String, String>,
    /// Capabilities this node can provide to hosted components
    /// (e.g. ["cap/kqe","cap/kse","cap/llm"]). Auction-eligible iff superset
    /// of a component's `:requires`.
    #[serde(default)]
    pub caps: Vec<String>,
    /// Remaining gas budget — the auction scoring signal for "free capacity".
    pub free_gas: u64,
    /// Component artifact CIDs currently hosted on this node (observed state).
    #[serde(default)]
    pub hosted: Vec<String>,
    /// Recent control-plane latency estimate (ms), proximity tie-breaker.
    #[serde(default)]
    pub lat_ms: u32,
}

/// Placement constraints attached to an auction.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
pub struct Constraints {
    /// Labels the winning node must match exactly.
    #[serde(default)]
    pub require_labels: BTreeMap<String, String>,
    /// Capabilities the winning node must supply.
    #[serde(default)]
    pub requires_caps: Vec<String>,
}

/// Placement auction request, published to [`topic::AUCTION`] by a reconciler.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Auction {
    /// Deterministic auction id (so concurrent leader-less reconcilers agree).
    pub id: String,
    /// Component artifact CID to place.
    pub cid: String,
    /// How many instances to place.
    pub n: u32,
    /// Placement constraints.
    #[serde(default)]
    pub constraints: Constraints,
}

/// A node's bid in response to an [`Auction`]. Higher `score` wins; ties broken
/// deterministically by `node_did` (lexicographic) so every reconciler picks
/// the same winners without a leader.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Bid {
    pub auction_id: String,
    pub node_did: String,
    /// Integer score (u64, not f64) so award is deterministic across nodes.
    pub score: u64,
}

/// Award of an auction to a node (informational; the StartComponent command
/// carries the actual placement).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Award {
    pub auction_id: String,
    pub node_did: String,
}

/// A capability link (ADR §5) = a CACAO-rooted grant binding a component to a
/// capability/provider. Equivalent to a wasmCloud link definition AND a
/// Holochain cap grant/claim, expressed as a signed datom.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Link {
    /// Stable link id (content-derived).
    pub id: String,
    /// DID of the calling component.
    pub source: String,
    /// Target capability (e.g. "cap/kqe") or provider DID.
    pub target: String,
    /// CID of the link config block (endpoint, namespace, …).
    #[serde(default)]
    pub config: Option<String>,
    /// CID of the depth-2 CACAO delegation chain authorizing this link.
    pub cacao: String,
    /// Ability granted (e.g. "datom:read").
    pub ability: String,
}

/// Every control-plane message that flows over the lattice topics.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "t", rename_all = "kebab-case")]
pub enum LatticeMessage {
    Heartbeat(Heartbeat),
    InventoryReq { node_did: String },
    InventoryAck(Heartbeat),
    Auction(Auction),
    Bid(Bid),
    Award(Award),
    /// Place `count` instances of `cid` on the receiving node, with `links`.
    StartComponent {
        cid: String,
        count: u32,
        #[serde(default)]
        links: Vec<String>,
    },
    StopComponent {
        instance: String,
    },
    ScaleTo {
        cid: String,
        n: u32,
    },
    PutLink(Link),
    DelLink {
        id: String,
    },
}

impl LatticeMessage {
    /// Serialize to CBOR for gossipsub publication.
    pub fn to_cbor(&self) -> Result<Vec<u8>, LatticeError> {
        let mut buf = Vec::new();
        ciborium::into_writer(self, &mut buf).map_err(|e| LatticeError::CborEncode(e.to_string()))?;
        Ok(buf)
    }

    /// Deserialize from a CBOR gossipsub payload.
    pub fn from_cbor(bytes: &[u8]) -> Result<Self, LatticeError> {
        ciborium::from_reader(bytes).map_err(|e| LatticeError::CborDecode(e.to_string()))
    }
}

/// Deterministic auction id from (component cid, desired n, current observed
/// count). Same desired-vs-observed gap → same id on every reconciler, so
/// concurrent leader-less reconcilers do not spawn duplicate auctions.
pub fn auction_id(cid: &str, want: u32, have: u32) -> String {
    let h = blake3::hash(format!("kotoba-auction:v1\n{cid}\n{want}\n{have}").as_bytes());
    format!("auc-{}", &h.to_hex()[..16])
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn cbor_roundtrip_heartbeat() {
        let hb = Heartbeat {
            node_did: "did:key:zNode".into(),
            roles: vec![NodeRole::Compute, NodeRole::Pin],
            labels: BTreeMap::from([("zone".into(), "jp".into())]),
            caps: vec!["cap/kqe".into(), "cap/llm".into()],
            free_gas: 9_000_000,
            hosted: vec!["bafyA".into()],
            lat_ms: 12,
        };
        let msg = LatticeMessage::Heartbeat(hb.clone());
        let bytes = msg.to_cbor().unwrap();
        let back = LatticeMessage::from_cbor(&bytes).unwrap();
        assert_eq!(msg, back);
    }

    #[test]
    fn cbor_roundtrip_auction_and_bid() {
        let a = LatticeMessage::Auction(Auction {
            id: auction_id("bafyX", 3, 1),
            cid: "bafyX".into(),
            n: 2,
            constraints: Constraints {
                require_labels: BTreeMap::from([("tier".into(), "edge".into())]),
                requires_caps: vec!["cap/kqe".into()],
            },
        });
        assert_eq!(LatticeMessage::from_cbor(&a.to_cbor().unwrap()).unwrap(), a);

        let b = LatticeMessage::Bid(Bid {
            auction_id: "auc-deadbeef".into(),
            node_did: "did:key:z1".into(),
            score: 42,
        });
        assert_eq!(LatticeMessage::from_cbor(&b.to_cbor().unwrap()).unwrap(), b);
    }

    #[test]
    fn auction_id_is_deterministic() {
        assert_eq!(auction_id("bafy", 3, 1), auction_id("bafy", 3, 1));
        assert_ne!(auction_id("bafy", 3, 1), auction_id("bafy", 4, 1));
    }
}
