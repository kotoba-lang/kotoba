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
pub const LATTICE_TOPICS: [&str; 5] = [
    topic::HEARTBEAT,
    topic::INVENTORY,
    topic::CMD,
    topic::LINK,
    topic::AUCTION,
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
        let bytes = LatticeMessage::DelLink { id: "x".into() }.to_cbor().unwrap();
        assert!(decode_lattice("kotoba/kse/some/topic", &bytes).is_none());
    }
}
