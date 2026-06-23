//! Lattice control-plane gossipsub binding (KOTOBA Mesh M2).
//!
//! Wires `kotoba-lattice`'s transport-agnostic [`LatticeController`] to the
//! libp2p swarm: the 5 reserved control topics ride the same gossipsub mesh as
//! KSE/Pregel traffic. This is the seam where the (pure, tested) reconcile +
//! auction loop meets the real network — no central broker (no NATS), matching
//! the no-central-master invariant.
//!
//! [`LatticeController`]: kotoba_lattice::LatticeController

use anyhow::Result;
use kotoba_lattice::protocol::topic;
use kotoba_lattice::{LatticeError, LatticeMessage, Transport};

use crate::gossipsub::gossipsub_topic;
use crate::swarm::KotobaSwarm;

/// Every reserved lattice control-plane topic.
pub const LATTICE_TOPICS: [&str; 6] = [
    topic::HEARTBEAT,
    topic::INVENTORY,
    topic::CMD,
    topic::LINK,
    topic::AUCTION,
    topic::CAP,
];

/// Subscribe the swarm to all lattice control-plane topics. Call once after the
/// swarm is built so this node both hears and participates in the lattice.
pub fn subscribe_lattice(swarm: &mut KotobaSwarm) -> Result<()> {
    for t in LATTICE_TOPICS {
        swarm.subscribe(t)?;
    }
    Ok(())
}

/// Decode an inbound [`crate::swarm::KotobaNetEvent::GossipMessage`] iff it is on
/// a lattice topic; returns `None` for non-lattice traffic or undecodable data.
/// `wire_topic` is the `topic` field from the gossip event (already in the
/// `kotoba/...` wire form via [`gossipsub_topic`]).
pub fn decode_lattice(wire_topic: &str, data: &[u8]) -> Option<LatticeMessage> {
    let is_lattice = LATTICE_TOPICS
        .iter()
        .any(|t| gossipsub_topic(t) == wire_topic);
    if !is_lattice {
        return None;
    }
    LatticeMessage::from_cbor(data).ok()
}

/// The swarm IS a lattice [`Transport`]: a controller can publish control
/// messages straight onto the gossipsub mesh.
impl Transport for KotobaSwarm {
    fn publish(&mut self, topic: &str, msg: &LatticeMessage) -> Result<(), LatticeError> {
        let bytes = msg.to_cbor()?;
        // disambiguate from this trait method — call the inherent gossipsub publish
        KotobaSwarm::publish(self, topic, bytes)
            .map(|_| ())
            .map_err(|e| LatticeError::Transport(e.to_string()))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use kotoba_lattice::protocol::{Heartbeat, NodeRole};
    use std::collections::BTreeMap;

    #[test]
    fn decode_roundtrips_on_lattice_topic() {
        let hb = LatticeMessage::Heartbeat(Heartbeat {
            node_did: "did:key:z1".into(),
            roles: vec![NodeRole::Compute],
            labels: BTreeMap::new(),
            caps: vec!["cap/kqe".into()],
            free_gas: 1,
            hosted: vec![],
            lat_ms: 0,
        });
        let bytes = hb.to_cbor().unwrap();
        let wire = gossipsub_topic(topic::HEARTBEAT);
        assert_eq!(decode_lattice(&wire, &bytes), Some(hb));
    }

    #[test]
    fn decode_ignores_non_lattice_topic() {
        let bytes = LatticeMessage::DelLink { id: "x".into() }
            .to_cbor()
            .unwrap();
        assert!(decode_lattice("kotoba/kse/some/topic", &bytes).is_none());
    }

    /// Regression guard: every reserved control topic must be in the subscribe
    /// set. Adding a new `topic::*` without extending `LATTICE_TOPICS` would
    /// silently drop that traffic (the exact trap hit when `CAP` was added).
    #[test]
    fn lattice_topics_cover_all_protocol_constants() {
        for t in [
            topic::HEARTBEAT,
            topic::INVENTORY,
            topic::CMD,
            topic::LINK,
            topic::AUCTION,
            topic::CAP,
        ] {
            assert!(
                LATTICE_TOPICS.contains(&t),
                "topic {t} not in LATTICE_TOPICS"
            );
        }
        assert_eq!(LATTICE_TOPICS.len(), 6);
    }

    #[test]
    fn decode_works_on_every_lattice_topic() {
        let msg = LatticeMessage::DelLink { id: "x".into() };
        let bytes = msg.to_cbor().unwrap();
        for t in LATTICE_TOPICS {
            let wire = gossipsub_topic(t);
            assert_eq!(
                decode_lattice(&wire, &bytes),
                Some(msg.clone()),
                "topic {t}"
            );
        }
    }

    #[test]
    fn decode_returns_none_on_malformed_lattice_payload() {
        // garbage on a *valid* lattice topic must fail gracefully (no panic)
        let wire = gossipsub_topic(topic::AUCTION);
        assert!(decode_lattice(&wire, &[0xff, 0x00, 0x99]).is_none());
        assert!(decode_lattice(&wire, &[]).is_none());
    }

    #[test]
    fn decode_cap_invoke_on_cap_topic() {
        let m = LatticeMessage::CapInvoke {
            id: "i".into(),
            source: "s".into(),
            provider_did: "p".into(),
            target_cap: "cap/llm".into(),
            ability: "infer".into(),
            link_id: "l".into(),
            args_cbor: vec![1, 2],
        };
        let wire = gossipsub_topic(topic::CAP);
        assert_eq!(decode_lattice(&wire, &m.to_cbor().unwrap()), Some(m));
    }
}
