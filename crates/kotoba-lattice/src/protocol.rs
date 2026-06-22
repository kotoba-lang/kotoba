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
    /// Out-of-proc capability invocation / result (wRPC, M5).
    pub const CAP: &str = "kotoba/lat/cap";
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
    /// Place `count` instances of `cid` on node `node_did`, with `links`.
    /// Carries the target node DID because the lattice is a broadcast bus
    /// (gossipsub): the addressed node acts, others ignore.
    StartComponent {
        node_did: String,
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
    /// Announce an application's desired state onto the lattice (wadm, M4).
    /// The durable SSOT is the control-graph datoms (see `crate::control`); this
    /// message is the live propagation of that desired state to every node's
    /// reconciler. `desired`: cid → instance count. `constraints`: cid → where.
    PutApp {
        app: String,
        desired: std::collections::BTreeMap<String, u32>,
        #[serde(default)]
        constraints: std::collections::BTreeMap<String, Constraints>,
    },
    /// Out-of-process capability invocation (wRPC, M5): a component on the
    /// caller node invokes `ability` on `target_cap` supplied by `provider_did`.
    /// Routed to that provider node over the lattice; the provider replies with
    /// a [`LatticeMessage::CapResult`]. `link_id` ties it to the authorizing
    /// CACAO link (mesh policy gate).
    CapInvoke {
        id: String,
        source: String,
        provider_did: String,
        target_cap: String,
        ability: String,
        link_id: String,
        #[serde(default)]
        args_cbor: Vec<u8>,
    },
    /// Reply to a [`LatticeMessage::CapInvoke`].
    CapResult {
        id: String,
        ok: bool,
        #[serde(default)]
        payload: Vec<u8>,
        #[serde(default)]
        error: Option<String>,
    },
    /// Announce an app's datom-Δ triggers onto the lattice (M6). Every node
    /// installs them; a node firing a matching datom places the component (same
    /// `StartComponent` → WASM-host path as auction placement).
    PutTriggers {
        app: String,
        #[serde(default)]
        triggers: Vec<crate::trigger::DeltaTrigger>,
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

    fn roundtrip(m: LatticeMessage) {
        assert_eq!(LatticeMessage::from_cbor(&m.to_cbor().unwrap()).unwrap(), m);
    }

    #[test]
    fn cbor_roundtrip_all_remaining_variants() {
        roundtrip(LatticeMessage::InventoryReq { node_did: "n".into() });
        roundtrip(LatticeMessage::InventoryAck(Heartbeat {
            node_did: "n".into(),
            roles: vec![NodeRole::Relay],
            labels: BTreeMap::new(),
            caps: vec![],
            free_gas: 0,
            hosted: vec![],
            lat_ms: 5,
        }));
        roundtrip(LatticeMessage::Award(Award {
            auction_id: "a".into(),
            node_did: "n".into(),
        }));
        roundtrip(LatticeMessage::StartComponent {
            node_did: "n".into(),
            cid: "c".into(),
            count: 2,
            links: vec!["l1".into()],
        });
        roundtrip(LatticeMessage::StopComponent { instance: "i".into() });
        roundtrip(LatticeMessage::ScaleTo { cid: "c".into(), n: 3 });
        roundtrip(LatticeMessage::PutLink(Link {
            id: "l".into(),
            source: "s".into(),
            target: "cap/llm".into(),
            config: Some("cfg".into()),
            cacao: "z".into(),
            ability: "infer".into(),
        }));
        roundtrip(LatticeMessage::DelLink { id: "l".into() });
        roundtrip(LatticeMessage::PutApp {
            app: "app".into(),
            desired: BTreeMap::from([("c".into(), 2u32)]),
            constraints: BTreeMap::from([(
                "c".into(),
                Constraints {
                    require_labels: BTreeMap::from([("z".into(), "1".into())]),
                    requires_caps: vec!["cap/kqe".into()],
                },
            )]),
        });
        roundtrip(LatticeMessage::CapInvoke {
            id: "id".into(),
            source: "s".into(),
            provider_did: "p".into(),
            target_cap: "cap/llm".into(),
            ability: "infer".into(),
            link_id: "l".into(),
            args_cbor: vec![1, 2, 3],
        });
        roundtrip(LatticeMessage::CapResult {
            id: "id".into(),
            ok: false,
            payload: vec![],
            error: Some("denied".into()),
        });
        roundtrip(LatticeMessage::PutTriggers {
            app: "app".into(),
            triggers: vec![crate::trigger::DeltaTrigger {
                component: "bafyAudit".into(),
                predicate: "kg/claim/role".into(),
                value: Some("admin".into()),
            }],
        });
    }

    #[test]
    fn from_cbor_rejects_garbage() {
        assert!(LatticeMessage::from_cbor(&[0xff, 0x00, 0x13, 0x37]).is_err());
    }

    /// Forward-compat: an OLD node must still decode a message a NEWER node sent
    /// with an extra field it doesn't know about (rolling upgrades).
    #[test]
    fn decode_ignores_unknown_future_fields() {
        use ciborium::value::{Integer, Value};
        let v = Value::Map(vec![
            (Value::Text("t".into()), Value::Text("heartbeat".into())),
            (Value::Text("node_did".into()), Value::Text("n".into())),
            (Value::Text("roles".into()), Value::Array(vec![Value::Text("compute".into())])),
            (Value::Text("free_gas".into()), Value::Integer(Integer::from(5u64))),
            // a field a future kotoba version added — the old decoder must ignore it
            (Value::Text("future_field".into()), Value::Bool(true)),
        ]);
        let mut buf = Vec::new();
        ciborium::into_writer(&v, &mut buf).unwrap();
        match LatticeMessage::from_cbor(&buf).expect("forward-compatible decode") {
            LatticeMessage::Heartbeat(hb) => {
                assert_eq!(hb.node_did, "n");
                assert_eq!(hb.roles, vec![NodeRole::Compute]);
            }
            _ => panic!("wrong variant"),
        }
    }

    /// Backward-compat: a NEW node must decode a message an OLDER node sent that
    /// omits fields later marked `#[serde(default)]`.
    #[test]
    fn decode_fills_defaults_for_missing_optional_fields() {
        use ciborium::value::{Integer, Value};
        let v = Value::Map(vec![
            (Value::Text("t".into()), Value::Text("heartbeat".into())),
            (Value::Text("node_did".into()), Value::Text("n".into())),
            (Value::Text("roles".into()), Value::Array(vec![])),
            (Value::Text("free_gas".into()), Value::Integer(Integer::from(0u64))),
            // labels / caps / hosted / lat_ms omitted → must use serde defaults
        ]);
        let mut buf = Vec::new();
        ciborium::into_writer(&v, &mut buf).unwrap();
        match LatticeMessage::from_cbor(&buf).expect("backward-compatible decode") {
            LatticeMessage::Heartbeat(hb) => {
                assert!(hb.labels.is_empty() && hb.caps.is_empty() && hb.hosted.is_empty());
                assert_eq!(hb.lat_ms, 0);
            }
            _ => panic!("wrong variant"),
        }
    }

    #[test]
    fn auction_id_format_and_grid_has_no_collisions() {
        let id = auction_id("bafyX", 3, 1);
        assert!(id.starts_with("auc-"));
        assert_eq!(id.len(), "auc-".len() + 16); // 16 hex chars of blake3
        let mut seen = std::collections::HashSet::new();
        for cid in ["a", "b", "c", "bafyReply"] {
            for want in 0..16u32 {
                for have in 0..16u32 {
                    assert!(seen.insert(auction_id(cid, want, have)), "id collision");
                }
            }
        }
    }

    #[test]
    fn node_role_serde_lowercase() {
        // tag stability matters for the wire format
        let m = LatticeMessage::Heartbeat(Heartbeat {
            node_did: "n".into(),
            roles: vec![NodeRole::Pin, NodeRole::Compute, NodeRole::Relay],
            labels: BTreeMap::new(),
            caps: vec![],
            free_gas: 1,
            hosted: vec![],
            lat_ms: 0,
        });
        roundtrip(m);
    }
}
