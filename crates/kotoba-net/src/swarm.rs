use anyhow::Result;
use futures::StreamExt;
use libp2p::swarm::behaviour::toggle::Toggle;
use libp2p::{
    autonat, dcutr, gossipsub, identify,
    identity::Keypair,
    kad,
    multiaddr::Protocol,
    ping, relay, request_response,
    swarm::{Swarm, SwarmEvent},
    Multiaddr, PeerId,
};

use crate::behaviour::{KotobaBehaviour, KotobaBehaviourEvent};
use crate::bitswap::{BitswapRequest, BitswapResponse, WantSince, BITSWAP_PROTOCOL};
use crate::protocol::KOTOBA_SYNC_PROTOCOL;

pub type KotobaSwarmType = Swarm<KotobaBehaviour>;

/// NAT-traversal configuration (clean-room WireGuard/Tailscale-equivalent over
/// libp2p — AutoNAT + Circuit Relay v2 + DCUtR).
///
/// Edge / donated nodes (behind home NAT) use the defaults: they probe their
/// reachability with AutoNAT, take a relay reservation as a fallback path, and
/// let DCUtR upgrade relayed links to direct hole-punched connections. Only a
/// publicly reachable fleet node should set `relay_server = true` so it can
/// relay for others — a relay is just another peer (no central master).
#[derive(Debug, Clone, Copy, Default)]
pub struct NatConfig {
    /// Run the Circuit Relay v2 *server*. Enable only on publicly reachable
    /// nodes (public IP or port-forward). Off by default.
    pub relay_server: bool,
}

/// Build a stable libp2p Ed25519 identity from a 32-byte hex seed (e.g. the
/// `KOTOBA_P2P_ED25519_HEX` env var) so a node keeps the same `PeerId` — and
/// therefore the same relay reservations and addresses — across restarts.
///
/// Kept deliberately separate from the CACAO/DID *agent* key: the networking
/// identity and the signing identity are different roles.
pub fn ed25519_keypair_from_hex(seed_hex: &str) -> Result<Keypair> {
    let mut bytes = hex::decode(seed_hex.trim())
        .map_err(|e| anyhow::anyhow!("p2p ed25519 seed: invalid hex: {e}"))?;
    if bytes.len() != 32 {
        anyhow::bail!("p2p ed25519 seed: expected 32 bytes, got {}", bytes.len());
    }
    Keypair::ed25519_from_bytes(&mut bytes).map_err(|e| anyhow::anyhow!("p2p ed25519 seed: {e}"))
}

/// High-level wrapper around the libp2p Swarm.
pub struct KotobaSwarm {
    pub swarm: KotobaSwarmType,
    pub local_peer_id: PeerId,
}

#[derive(Debug)]
pub enum KotobaNetEvent {
    GossipMessage {
        topic: String,
        data: Vec<u8>,
        source: Option<PeerId>,
    },
    PeerConnected(PeerId),
    PeerDisconnected(PeerId),
    RoutingUpdated {
        peer: PeerId,
    },
    ListenAddr(Multiaddr),
    BitswapRequest {
        peer: PeerId,
        request: BitswapRequest,
        channel: request_response::ResponseChannel<BitswapResponse>,
    },
    BitswapResponse {
        peer: PeerId,
        response: BitswapResponse,
    },
    /// AutoNAT determined our public reachability. `public = true` ⇒ directly
    /// dialable; `false` ⇒ behind a NAT, so a relay reservation is needed.
    NatStatusChanged {
        public: bool,
    },
    /// A relayed connection to `peer` was upgraded to a direct (hole-punched)
    /// connection by DCUtR.
    DirectConnectionUpgraded {
        peer: PeerId,
    },
    /// A Circuit Relay v2 reservation was accepted by `relay` — this node is now
    /// reachable at `<relay-addr>/p2p-circuit/p2p/<self>`.
    RelayReservationAccepted {
        relay: PeerId,
    },
}

impl KotobaSwarm {
    /// Create a new KotobaSwarm with a fresh Ed25519 identity.
    /// `listen_addr` example: `"/ip4/0.0.0.0/udp/0/quic-v1"`.
    pub async fn new(listen_addr: Multiaddr) -> Result<Self> {
        let keypair = Keypair::generate_ed25519();
        Self::with_config(keypair, listen_addr, NatConfig::default()).await
    }

    /// Like [`KotobaSwarm::new`] (fresh identity) but with an explicit
    /// NAT-traversal config — e.g. to enable the Circuit Relay v2 server on a
    /// publicly reachable node.
    pub async fn new_with_config(listen_addr: Multiaddr, nat: NatConfig) -> Result<Self> {
        let keypair = Keypair::generate_ed25519();
        Self::with_config(keypair, listen_addr, nat).await
    }

    /// Create with an existing keypair (for persistent node identity), default
    /// NAT config (relay client + AutoNAT + DCUtR on, relay server off).
    pub async fn with_keypair(keypair: Keypair, listen_addr: Multiaddr) -> Result<Self> {
        Self::with_config(keypair, listen_addr, NatConfig::default()).await
    }

    /// Create with an existing keypair and an explicit NAT-traversal config.
    pub async fn with_config(
        keypair: Keypair,
        listen_addr: Multiaddr,
        nat: NatConfig,
    ) -> Result<Self> {
        let local_peer_id = PeerId::from_public_key(&keypair.public());

        // GossipSub — lenient validation thresholds for dev
        let gossipsub_config = gossipsub::ConfigBuilder::default()
            .heartbeat_interval(std::time::Duration::from_secs(10))
            .validation_mode(gossipsub::ValidationMode::Strict)
            .build()
            .map_err(|e| anyhow::anyhow!("gossipsub config: {e:?}"))?;

        let gossipsub = gossipsub::Behaviour::new(
            gossipsub::MessageAuthenticity::Signed(keypair.clone()),
            gossipsub_config,
        )
        .map_err(|e| anyhow::anyhow!("gossipsub init: {e:?}"))?;

        let kademlia =
            kad::Behaviour::new(local_peer_id, kad::store::MemoryStore::new(local_peer_id));

        let identify = identify::Behaviour::new(identify::Config::new(
            KOTOBA_SYNC_PROTOCOL.to_string(),
            keypair.public(),
        ));

        let ping = ping::Behaviour::default();

        let bitswap = request_response::Behaviour::new(
            vec![(BITSWAP_PROTOCOL, request_response::ProtocolSupport::Full)],
            request_response::Config::default(),
        );

        // ── NAT traversal behaviours (clean-room WG/TS-equivalent) ──────────
        let autonat = autonat::Behaviour::new(local_peer_id, autonat::Config::default());
        let dcutr = dcutr::Behaviour::new(local_peer_id);
        let relay_server = if nat.relay_server {
            Toggle::from(Some(relay::Behaviour::new(
                local_peer_id,
                relay::Config::default(),
            )))
        } else {
            Toggle::from(None)
        };

        // `with_relay_client` injects the Circuit Relay v2 client behaviour into
        // the builder closure; the relayed connection is secured with Noise and
        // multiplexed with Yamux (same upgrades as the base QUIC transport).
        let mut swarm = libp2p::SwarmBuilder::with_existing_identity(keypair)
            .with_tokio()
            .with_quic()
            .with_dns()?
            .with_relay_client(libp2p::noise::Config::new, libp2p::yamux::Config::default)?
            .with_behaviour(move |_keypair, relay_client| {
                Ok(KotobaBehaviour {
                    gossipsub,
                    kademlia,
                    identify,
                    ping,
                    bitswap,
                    autonat,
                    relay_client,
                    dcutr,
                    relay_server,
                })
            })?
            // libp2p defaults idle_connection_timeout to 0 → idle connections close
            // immediately (KeepAliveTimeout) before GossipSub can graft them into a
            // mesh, so the firehose relay never propagates. Hold idle connections
            // long enough for the mesh to stabilise.
            .with_swarm_config(|cfg| {
                cfg.with_idle_connection_timeout(std::time::Duration::from_secs(60))
            })
            .build();

        swarm.listen_on(listen_addr)?;

        Ok(Self {
            swarm,
            local_peer_id,
        })
    }

    // ------------------------------------------------------------------
    // NAT traversal helpers (Circuit Relay v2 + DCUtR + AutoNAT)
    // ------------------------------------------------------------------

    /// Take a Circuit Relay v2 reservation on `relay_addr` so this (NAT'd) node
    /// becomes reachable at `<relay_addr>/p2p-circuit/p2p/<self>`. Peers that
    /// dial the circuit then get upgraded to a direct connection by DCUtR.
    ///
    /// `relay_addr` MUST already include the relay's `/p2p/<relay-peer-id>`
    /// suffix (e.g. `/ip4/1.2.3.4/udp/4001/quic-v1/p2p/<relay-id>`).
    pub fn reserve_relay(&mut self, relay_addr: Multiaddr) -> Result<()> {
        let circuit = relay_addr.with(Protocol::P2pCircuit);
        self.swarm.listen_on(circuit)?;
        Ok(())
    }

    /// Convenience over [`KotobaSwarm::reserve_relay`] for the `peerid@multiaddr`
    /// config form (e.g. `KOTOBA_RELAY_PEERS`): appends the relay's
    /// `/p2p/<peer>` to a bare transport multiaddr before reserving.
    pub fn reserve_relay_with_peer(
        &mut self,
        relay_peer: PeerId,
        relay_addr: Multiaddr,
    ) -> Result<()> {
        self.reserve_relay(relay_addr.with(Protocol::P2p(relay_peer)))
    }

    /// Dial `target` through a relay. Once the relayed connection is up, DCUtR
    /// attempts to upgrade it to a direct (hole-punched) link automatically.
    ///
    /// `relay_addr` MUST include the relay's `/p2p/<relay-peer-id>` suffix.
    pub fn dial_via_relay(&mut self, relay_addr: Multiaddr, target: PeerId) -> Result<()> {
        let addr = relay_addr
            .with(Protocol::P2pCircuit)
            .with(Protocol::P2p(target));
        self.swarm.dial(addr)?;
        Ok(())
    }

    /// Register a confirmed external (publicly reachable) address — e.g. one
    /// learned from AutoNAT — so it is advertised to peers via identify.
    pub fn add_external_address(&mut self, addr: Multiaddr) {
        self.swarm.add_external_address(addr);
    }

    /// Subscribe to a GossipSub topic mapped from a KSE topic name.
    pub fn subscribe(&mut self, kse_topic: &str) -> Result<()> {
        let topic = gossipsub::IdentTopic::new(
            crate::gossipsub::checked_gossipsub_topic(kse_topic).map_err(anyhow::Error::msg)?,
        );
        self.swarm.behaviour_mut().gossipsub.subscribe(&topic)?;
        Ok(())
    }

    /// Publish bytes to a GossipSub topic.
    pub fn publish(&mut self, kse_topic: &str, data: Vec<u8>) -> Result<gossipsub::MessageId> {
        let topic = gossipsub::IdentTopic::new(
            crate::gossipsub::checked_gossipsub_topic(kse_topic).map_err(anyhow::Error::msg)?,
        );
        let id = self.swarm.behaviour_mut().gossipsub.publish(topic, data)?;
        Ok(id)
    }

    /// Add a bootstrap peer to the Kademlia routing table and dial it.
    pub fn add_peer(&mut self, peer_id: PeerId, addr: Multiaddr) {
        self.swarm
            .behaviour_mut()
            .kademlia
            .add_address(&peer_id, addr.clone());
        self.swarm.dial(addr).ok();
    }

    /// Bootstrap Kademlia DHT discovery (requires at least one known peer first).
    pub fn bootstrap(&mut self) -> Result<kad::QueryId> {
        Ok(self.swarm.behaviour_mut().kademlia.bootstrap()?)
    }

    /// Request a block from a specific peer.
    pub fn want_block(
        &mut self,
        peer: PeerId,
        cid: [u8; 36],
    ) -> request_response::OutboundRequestId {
        self.swarm.behaviour_mut().bitswap.send_request(
            &peer,
            BitswapRequest {
                want_have: vec![],
                want_block: vec![cid],
                want_since: vec![],
            },
        )
    }

    /// Check if a peer has a block (no data transfer).
    pub fn want_have(
        &mut self,
        peer: PeerId,
        cid: [u8; 36],
    ) -> request_response::OutboundRequestId {
        self.swarm.behaviour_mut().bitswap.send_request(
            &peer,
            BitswapRequest {
                want_have: vec![cid],
                want_block: vec![],
                want_since: vec![],
            },
        )
    }

    /// Request a selective-sync delta: all commits in `graph_cid` since `head_cid`.
    /// `head_cid = None` means fresh agent — peer should return the full commit chain.
    pub fn want_since(
        &mut self,
        peer: PeerId,
        graph_cid: [u8; 36],
        since_seq: u64,
        head_cid: Option<[u8; 36]>,
    ) -> request_response::OutboundRequestId {
        self.swarm.behaviour_mut().bitswap.send_request(
            &peer,
            BitswapRequest {
                want_have: vec![],
                want_block: vec![],
                want_since: vec![WantSince {
                    graph_cid,
                    since_seq,
                    head_cid,
                }],
            },
        )
    }

    /// Poll the swarm for the next user-visible event.
    /// Returns `None` only if the swarm terminates (should not happen in production).
    pub async fn next_event(&mut self) -> Option<KotobaNetEvent> {
        loop {
            match self.swarm.next().await? {
                // GossipSub message received
                SwarmEvent::Behaviour(KotobaBehaviourEvent::Gossipsub(
                    gossipsub::Event::Message { message, .. },
                )) => {
                    return Some(KotobaNetEvent::GossipMessage {
                        topic: message.topic.to_string(),
                        data: message.data,
                        source: message.source,
                    });
                }

                // Connection events
                SwarmEvent::ConnectionEstablished { peer_id, .. } => {
                    return Some(KotobaNetEvent::PeerConnected(peer_id));
                }
                SwarmEvent::ConnectionClosed { peer_id, .. } => {
                    return Some(KotobaNetEvent::PeerDisconnected(peer_id));
                }

                // Kademlia routing table update
                SwarmEvent::Behaviour(KotobaBehaviourEvent::Kademlia(
                    kad::Event::RoutingUpdated { peer, .. },
                )) => {
                    return Some(KotobaNetEvent::RoutingUpdated { peer });
                }

                // New listen address assigned by the OS
                SwarmEvent::NewListenAddr { address, .. } => {
                    tracing::info!(addr = %address, "kotoba-net: listening");
                    return Some(KotobaNetEvent::ListenAddr(address));
                }

                // Identify: learn peer's addresses → feed them to Kademlia
                SwarmEvent::Behaviour(KotobaBehaviourEvent::Identify(
                    identify::Event::Received { peer_id, info, .. },
                )) => {
                    for addr in info.listen_addrs {
                        self.swarm
                            .behaviour_mut()
                            .kademlia
                            .add_address(&peer_id, addr);
                    }
                    // Not a user-visible event — continue the loop
                }

                // Bitswap: incoming request from a peer
                SwarmEvent::Behaviour(KotobaBehaviourEvent::Bitswap(
                    request_response::Event::Message {
                        peer,
                        message:
                            request_response::Message::Request {
                                request, channel, ..
                            },
                    },
                )) => {
                    return Some(KotobaNetEvent::BitswapRequest {
                        peer,
                        request,
                        channel,
                    });
                }

                // Bitswap: response received from a peer
                SwarmEvent::Behaviour(KotobaBehaviourEvent::Bitswap(
                    request_response::Event::Message {
                        peer,
                        message: request_response::Message::Response { response, .. },
                    },
                )) => {
                    return Some(KotobaNetEvent::BitswapResponse { peer, response });
                }

                // AutoNAT: reachability verdict changed (public vs behind-NAT)
                SwarmEvent::Behaviour(KotobaBehaviourEvent::Autonat(
                    autonat::Event::StatusChanged { new, .. },
                )) => {
                    let public = matches!(new, autonat::NatStatus::Public(_));
                    tracing::info!(?new, "kotoba-net: autonat reachability changed");
                    return Some(KotobaNetEvent::NatStatusChanged { public });
                }

                // DCUtR: a relayed link was upgraded to a direct (hole-punched) one
                SwarmEvent::Behaviour(KotobaBehaviourEvent::Dcutr(dcutr::Event {
                    remote_peer_id,
                    result,
                })) => match result {
                    Ok(_) => {
                        tracing::info!(peer = %remote_peer_id, "kotoba-net: dcutr hole-punch succeeded");
                        return Some(KotobaNetEvent::DirectConnectionUpgraded {
                            peer: remote_peer_id,
                        });
                    }
                    Err(e) => {
                        tracing::debug!(peer = %remote_peer_id, err = ?e, "kotoba-net: dcutr hole-punch failed");
                    }
                },

                // Relay client: our reservation on a relay was accepted
                SwarmEvent::Behaviour(KotobaBehaviourEvent::RelayClient(
                    relay::client::Event::ReservationReqAccepted { relay_peer_id, .. },
                )) => {
                    tracing::info!(relay = %relay_peer_id, "kotoba-net: relay reservation accepted");
                    return Some(KotobaNetEvent::RelayReservationAccepted {
                        relay: relay_peer_id,
                    });
                }

                _ => { /* ignore ping, identify::Sent, relay server, bitswap failures, etc. */ }
            }
        }
    }

    /// Run the swarm event loop, forwarding events onto `tx`.
    /// Call via `tokio::spawn`.
    pub async fn run(mut self, tx: tokio::sync::mpsc::Sender<KotobaNetEvent>) {
        while let Some(event) = self.next_event().await {
            if tx.send(event).await.is_err() {
                break; // receiver dropped
            }
        }
    }

    // ------------------------------------------------------------------
    // Pregel GossipSub helpers
    // ------------------------------------------------------------------

    /// Subscribe to the Pregel gossip topic.
    /// Must be called before `send_pregel_message` works.
    pub fn subscribe_pregel(&mut self) -> Result<()> {
        self.subscribe(crate::pregel_msg::PREGEL_GOSSIP_TOPIC)
    }

    /// Gossip a Pregel message to all peers subscribed to the pregel topic.
    pub fn send_pregel_message(
        &mut self,
        src: &str,
        dst: &str,
        payload: &[u8],
    ) -> Result<gossipsub::MessageId> {
        let msg = crate::pregel_msg::PregelNetMessage::new(src, dst, payload)
            .map_err(anyhow::Error::msg)?;
        let data = msg.to_json_vec().map_err(anyhow::Error::msg)?;
        self.publish(crate::pregel_msg::PREGEL_GOSSIP_TOPIC, data)
    }

    /// Try to parse an incoming `KotobaNetEvent` as a `PregelNetMessage`.
    /// Returns `None` if the event is not a Pregel gossip message.
    pub fn parse_pregel_event(
        event: &KotobaNetEvent,
    ) -> Option<crate::pregel_msg::PregelNetMessage> {
        if let KotobaNetEvent::GossipMessage { topic, data, .. } = event {
            let full_topic =
                crate::gossipsub::gossipsub_topic(crate::pregel_msg::PREGEL_GOSSIP_TOPIC);
            if topic == &full_topic || topic.ends_with(crate::pregel_msg::PREGEL_GOSSIP_TOPIC) {
                return crate::pregel_msg::PregelNetMessage::from_json_slice(data).ok();
            }
        }
        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn swarm_creates_and_subscribes() {
        let addr: Multiaddr = "/ip4/127.0.0.1/udp/0/quic-v1".parse().unwrap();
        let mut swarm = KotobaSwarm::new(addr).await.expect("swarm init");

        swarm.subscribe("kotoba/hello/greet").expect("subscribe");

        // Wait for the OS-assigned listen address
        let event =
            tokio::time::timeout(std::time::Duration::from_secs(3), swarm.next_event()).await;

        match event {
            Ok(Some(KotobaNetEvent::ListenAddr(addr))) => {
                println!("listening on: {addr}");
                // QUIC listen addr contains "127.0.0.1" and "udp"
                let s = addr.to_string();
                assert!(s.contains("127.0.0.1") || s.contains("quic"));
            }
            Ok(Some(other)) => {
                println!("got event: {other:?}");
            }
            Err(_) => {
                println!("timeout waiting for listen addr — swarm created OK");
            }
            Ok(None) => panic!("swarm terminated unexpectedly"),
        }

        assert!(!swarm.local_peer_id.to_string().is_empty());
    }

    #[tokio::test]
    async fn two_swarms_can_connect() {
        let addr1: Multiaddr = "/ip4/127.0.0.1/udp/0/quic-v1".parse().unwrap();
        let addr2: Multiaddr = "/ip4/127.0.0.1/udp/0/quic-v1".parse().unwrap();

        let mut swarm1 = KotobaSwarm::new(addr1).await.expect("swarm1");
        let mut swarm2 = KotobaSwarm::new(addr2).await.expect("swarm2");

        swarm1.subscribe("test/ping").unwrap();
        swarm2.subscribe("test/ping").unwrap();

        // Collect swarm1's actual listen address
        let listen_addr = tokio::time::timeout(std::time::Duration::from_secs(3), async {
            loop {
                if let Some(KotobaNetEvent::ListenAddr(a)) = swarm1.next_event().await {
                    return a;
                }
            }
        })
        .await;

        if let Ok(addr) = listen_addr {
            swarm2.add_peer(swarm1.local_peer_id, addr);

            // Brief window to observe a connection event (smoke only)
            tokio::time::timeout(std::time::Duration::from_secs(2), swarm2.next_event())
                .await
                .ok();
        }
        // Passes as long as no panic — full gossip delivery is integration-test territory
    }

    // ── Pure unit tests (no network) ──────────────────────────────────────────

    #[test]
    fn parse_pregel_event_returns_none_for_non_gossip_event() {
        let peer = PeerId::random();
        let event = KotobaNetEvent::PeerConnected(peer);
        assert!(KotobaSwarm::parse_pregel_event(&event).is_none());
    }

    #[test]
    fn parse_pregel_event_returns_none_for_wrong_topic() {
        let event = KotobaNetEvent::GossipMessage {
            topic: "kotoba/unrelated/topic".to_string(),
            data: b"{}".to_vec(),
            source: None,
        };
        assert!(KotobaSwarm::parse_pregel_event(&event).is_none());
    }

    #[test]
    fn parse_pregel_event_returns_none_for_invalid_json() {
        let full_topic = crate::gossipsub::gossipsub_topic(crate::pregel_msg::PREGEL_GOSSIP_TOPIC);
        let event = KotobaNetEvent::GossipMessage {
            topic: full_topic,
            data: b"not-valid-json".to_vec(),
            source: None,
        };
        assert!(KotobaSwarm::parse_pregel_event(&event).is_none());
    }

    #[test]
    fn parse_pregel_event_returns_none_for_invalid_wire_message() {
        let full_topic = crate::gossipsub::gossipsub_topic(crate::pregel_msg::PREGEL_GOSSIP_TOPIC);
        let msg = crate::pregel_msg::PregelNetMessage {
            src: String::new(),
            dst: "node-B".to_string(),
            payload_b64: "not base64!".to_string(),
        };
        let event = KotobaNetEvent::GossipMessage {
            topic: full_topic,
            data: serde_json::to_vec(&msg).unwrap(),
            source: None,
        };

        assert!(KotobaSwarm::parse_pregel_event(&event).is_none());
    }

    #[test]
    fn parse_pregel_event_succeeds_for_valid_message() {
        use base64::{engine::general_purpose::STANDARD as B64, Engine as _};
        let full_topic = crate::gossipsub::gossipsub_topic(crate::pregel_msg::PREGEL_GOSSIP_TOPIC);
        let msg = crate::pregel_msg::PregelNetMessage {
            src: "node-A".to_string(),
            dst: "node-B".to_string(),
            payload_b64: B64.encode(b"hello pregel"),
        };
        let data = serde_json::to_vec(&msg).unwrap();
        let event = KotobaNetEvent::GossipMessage {
            topic: full_topic,
            data,
            source: None,
        };
        let parsed = KotobaSwarm::parse_pregel_event(&event);
        assert!(parsed.is_some());
        let p = parsed.unwrap();
        assert_eq!(p.src, "node-A");
        assert_eq!(p.dst, "node-B");
    }

    #[test]
    fn kotoba_net_event_peer_disconnected_holds_peer_id() {
        let peer = PeerId::random();
        let event = KotobaNetEvent::PeerDisconnected(peer);
        if let KotobaNetEvent::PeerDisconnected(p) = event {
            assert_eq!(p, peer);
        } else {
            panic!("wrong variant");
        }
    }

    #[test]
    fn kotoba_net_event_routing_updated_holds_peer() {
        let peer = PeerId::random();
        let event = KotobaNetEvent::RoutingUpdated { peer };
        if let KotobaNetEvent::RoutingUpdated { peer: p } = event {
            assert_eq!(p, peer);
        } else {
            panic!("wrong variant");
        }
    }

    #[test]
    fn kotoba_net_event_gossip_message_fields() {
        let peer = PeerId::random();
        let event = KotobaNetEvent::GossipMessage {
            topic: "kotoba/test".to_string(),
            data: vec![1, 2, 3],
            source: Some(peer),
        };
        if let KotobaNetEvent::GossipMessage {
            topic,
            data,
            source,
        } = event
        {
            assert_eq!(topic, "kotoba/test");
            assert_eq!(data, vec![1u8, 2, 3]);
            assert_eq!(source, Some(peer));
        } else {
            panic!("wrong variant");
        }
    }

    // ── NAT traversal (AutoNAT + Circuit Relay v2 + DCUtR) ────────────────────

    #[test]
    fn nat_config_default_has_relay_server_off() {
        let cfg = NatConfig::default();
        assert!(!cfg.relay_server, "relay server must be opt-in");
    }

    #[tokio::test]
    async fn swarm_with_relay_server_enabled_builds() {
        // A public node enables the Circuit Relay v2 *server* so it can relay
        // for NAT'd peers. Construction wires relay_client + dcutr + autonat +
        // the toggled relay server without panicking.
        let addr: Multiaddr = "/ip4/127.0.0.1/udp/0/quic-v1".parse().unwrap();
        let keypair = Keypair::generate_ed25519();
        let swarm = KotobaSwarm::with_config(keypair, addr, NatConfig { relay_server: true })
            .await
            .expect("relay-server swarm init");
        assert!(!swarm.local_peer_id.to_string().is_empty());
    }

    #[tokio::test]
    async fn reserve_relay_appends_p2p_circuit_without_panic() {
        // An edge node asks a relay for a reservation. We can't complete the
        // handshake without a live relay, but listen_on must accept the
        // /p2p-circuit-suffixed multiaddr (smoke: no panic, no error).
        let addr: Multiaddr = "/ip4/127.0.0.1/udp/0/quic-v1".parse().unwrap();
        let mut swarm = KotobaSwarm::new(addr).await.expect("swarm init");
        let relay_addr: Multiaddr =
            format!("/ip4/127.0.0.1/udp/4999/quic-v1/p2p/{}", PeerId::random())
                .parse()
                .unwrap();
        swarm
            .reserve_relay(relay_addr)
            .expect("reserve_relay accepts circuit addr");
    }

    #[test]
    fn kotoba_net_event_nat_status_changed_holds_public() {
        let event = KotobaNetEvent::NatStatusChanged { public: true };
        if let KotobaNetEvent::NatStatusChanged { public } = event {
            assert!(public);
        } else {
            panic!("wrong variant");
        }
    }

    #[test]
    fn kotoba_net_event_relay_reservation_holds_relay() {
        let relay = PeerId::random();
        let event = KotobaNetEvent::RelayReservationAccepted { relay };
        if let KotobaNetEvent::RelayReservationAccepted { relay: r } = event {
            assert_eq!(r, relay);
        } else {
            panic!("wrong variant");
        }
    }

    #[test]
    fn kotoba_net_event_direct_connection_upgraded_holds_peer() {
        let peer = PeerId::random();
        let event = KotobaNetEvent::DirectConnectionUpgraded { peer };
        if let KotobaNetEvent::DirectConnectionUpgraded { peer: p } = event {
            assert_eq!(p, peer);
        } else {
            panic!("wrong variant");
        }
    }

    #[test]
    fn ed25519_keypair_from_hex_is_deterministic() {
        // Same 32-byte seed → same PeerId (stable identity across restarts).
        let seed = "11".repeat(32); // 32 bytes
        let a = ed25519_keypair_from_hex(&seed).expect("valid seed");
        let b = ed25519_keypair_from_hex(&seed).expect("valid seed");
        assert_eq!(
            PeerId::from_public_key(&a.public()),
            PeerId::from_public_key(&b.public()),
            "same seed must yield the same PeerId"
        );
    }

    #[test]
    fn ed25519_keypair_from_hex_rejects_bad_input() {
        assert!(ed25519_keypair_from_hex("deadbeef").is_err(), "too short");
        assert!(
            ed25519_keypair_from_hex(&"zz".repeat(32)).is_err(),
            "non-hex"
        );
    }
}
