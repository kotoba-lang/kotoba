use crate::bitswap::BitswapCodec;
use libp2p::swarm::behaviour::toggle::Toggle;
use libp2p::{
    autonat, dcutr, gossipsub, identify, kad, ping, relay, request_response,
    swarm::NetworkBehaviour,
};

/// Combined NetworkBehaviour for KOTOBA nodes.
///
/// The `#[derive(NetworkBehaviour)]` macro (libp2p "macros" feature) auto-generates:
///   - `KotobaBehaviourEvent` enum with one variant per field
///   - `poll()` / `handle_pending_inbound_connection()` / etc. delegation
///
/// NAT traversal (clean-room WireGuard/Tailscale-equivalent, all over libp2p — no
/// vendored VPN code, no central coordination server):
///   - `autonat`      — reachability detection (am I publicly dialable?)
///   - `relay_client` — Circuit Relay v2 client (DERP-equivalent fallback path)
///   - `dcutr`        — Direct Connection Upgrade through Relay (hole punching)
///   - `relay_server` — optional Circuit Relay v2 *server*, off by default via
///     `Toggle` (only public nodes enable it). A relay is just another peer —
///     discovery stays on Kademlia, so the no-central-master invariant holds.
#[derive(NetworkBehaviour)]
pub struct KotobaBehaviour {
    pub gossipsub: gossipsub::Behaviour,
    pub kademlia: kad::Behaviour<kad::store::MemoryStore>,
    pub identify: identify::Behaviour,
    pub ping: ping::Behaviour,
    pub bitswap: request_response::Behaviour<BitswapCodec>,
    // ── NAT traversal ────────────────────────────────────────────────
    pub autonat: autonat::Behaviour,
    pub relay_client: relay::client::Behaviour,
    pub dcutr: dcutr::Behaviour,
    pub relay_server: Toggle<relay::Behaviour>,
}
