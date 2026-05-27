use crate::store::MemBlockStore;
use anyhow::{anyhow, Result};
use cid::Cid;
use co_libp2p_bitswap::{Bitswap, BitswapConfig, BitswapEvent, QueryId};
use futures::StreamExt;
use libp2p::{
    identify, noise,
    swarm::{NetworkBehaviour, SwarmEvent},
    tcp, yamux, Multiaddr, PeerId, Swarm,
};
use std::collections::HashMap;
use tokio::sync::{mpsc, oneshot};
use tracing::debug;

// ── Combined behaviour ────────────────────────────────────────────────────────

#[derive(NetworkBehaviour)]
struct KotobaBehaviour {
    bitswap: Bitswap,
    identify: identify::Behaviour,
    // ping is included via identify for now; add explicit ping if needed
}

// ── Command bus ──────────────────────────────────────────────────────────────

enum Cmd {
    PutBlock {
        data: Vec<u8>,
        resp: oneshot::Sender<Cid>,
    },
    GetBlock {
        cid: Cid,
        peers: Vec<PeerId>,
        resp: oneshot::Sender<Result<Vec<u8>>>,
    },
    Dial {
        addr: Multiaddr,
    },
    Peers {
        resp: oneshot::Sender<Vec<PeerId>>,
    },
}

// ── Public handle (clone-able) ────────────────────────────────────────────────

/// Cheap clone handle for interacting with the IPFS node from outside the event loop.
#[derive(Clone)]
pub struct KotobaIpfsNode {
    tx: mpsc::UnboundedSender<Cmd>,
    peer_id: PeerId,
}

impl KotobaIpfsNode {
    /// Add a raw block to the local store and return its CIDv1 SHA2-256.
    pub async fn put_block(&self, data: Vec<u8>) -> Result<Cid> {
        let (resp, rx) = oneshot::channel();
        self.tx.send(Cmd::PutBlock { data, resp })?;
        Ok(rx.await?)
    }

    /// Get a block by CID from the local store, or fetch it from `peers` via Bitswap.
    pub async fn get_block(&self, cid: Cid, peers: Vec<PeerId>) -> Result<Vec<u8>> {
        let (resp, rx) = oneshot::channel();
        self.tx.send(Cmd::GetBlock { cid, peers, resp })?;
        rx.await?
    }

    /// Dial a remote peer by multiaddr.
    pub fn dial(&self, addr: Multiaddr) -> Result<()> {
        Ok(self.tx.send(Cmd::Dial { addr })?)
    }

    /// List currently connected peers.
    pub async fn connected_peers(&self) -> Result<Vec<PeerId>> {
        let (resp, rx) = oneshot::channel();
        self.tx.send(Cmd::Peers { resp })?;
        Ok(rx.await?)
    }

    pub fn peer_id(&self) -> PeerId {
        self.peer_id
    }
}

// ── Config ───────────────────────────────────────────────────────────────────

pub struct IpfsConfig {
    /// TCP listen address. Defaults to `/ip4/127.0.0.1/tcp/0` (random port).
    pub listen: Multiaddr,
}

impl Default for IpfsConfig {
    fn default() -> Self {
        Self {
            listen: "/ip4/127.0.0.1/tcp/0".parse().unwrap(),
        }
    }
}

impl IpfsConfig {
    pub fn new() -> Self {
        Self::default()
    }

    /// Spawn the IPFS event loop on the current Tokio runtime.
    /// Returns a handle; the background task runs until all handles are dropped.
    pub async fn start(self) -> Result<KotobaIpfsNode> {
        let store = MemBlockStore::new();
        let store_clone = store.clone();

        let swarm = libp2p::SwarmBuilder::with_new_identity()
            .with_tokio()
            .with_tcp(
                tcp::Config::default(),
                noise::Config::new,
                yamux::Config::default,
            )?
            .with_behaviour(|kp| {
                let bitswap = Bitswap::new(
                    BitswapConfig::new(),
                    store_clone,
                    Box::new(|fut| {
                        tokio::spawn(fut);
                    }),
                );
                let identify = identify::Behaviour::new(identify::Config::new(
                    "/kotoba-ipfs/1.0.0".into(),
                    kp.public(),
                ));
                KotobaBehaviour { bitswap, identify }
            })?
            .build();

        let peer_id = *swarm.local_peer_id();
        let (tx, rx) = mpsc::unbounded_channel();

        tokio::spawn(event_loop(swarm, store, rx, self.listen));

        Ok(KotobaIpfsNode { tx, peer_id })
    }
}

// ── Event loop ───────────────────────────────────────────────────────────────

async fn event_loop(
    mut swarm: Swarm<KotobaBehaviour>,
    store: MemBlockStore,
    mut rx: mpsc::UnboundedReceiver<Cmd>,
    listen: Multiaddr,
) {
    if let Err(e) = swarm.listen_on(listen) {
        tracing::error!("listen_on failed: {e}");
        return;
    }

    // pending Bitswap GET queries: QueryId → (cid, resp channel)
    let mut pending: HashMap<QueryId, (Cid, oneshot::Sender<Result<Vec<u8>>>)> = HashMap::new();

    loop {
        tokio::select! {
            cmd = rx.recv() => {
                match cmd {
                    None => break, // all handles dropped
                    Some(Cmd::PutBlock { data, resp }) => {
                        let cid = store.put(data);
                        let _ = resp.send(cid);
                    }
                    Some(Cmd::GetBlock { cid, peers, resp }) => {
                        if let Some(data) = store.get_local(&cid) {
                            let _ = resp.send(Ok(data));
                        } else {
                            let qid = swarm.behaviour_mut().bitswap.get(cid, peers, []);
                            pending.insert(qid, (cid, resp));
                        }
                    }
                    Some(Cmd::Dial { addr }) => {
                        if let Err(e) = swarm.dial(addr.clone()) {
                            tracing::warn!("dial {addr} failed: {e}");
                        }
                    }
                    Some(Cmd::Peers { resp }) => {
                        let peers: Vec<PeerId> = swarm.connected_peers().copied().collect();
                        let _ = resp.send(peers);
                    }
                }
            }
            event = swarm.next() => {
                let Some(event) = event else { break };
                handle_swarm_event(event, &store, &mut pending);
            }
        }
    }
}

fn handle_swarm_event(
    event: SwarmEvent<KotobaBehaviourEvent>,
    store: &MemBlockStore,
    pending: &mut HashMap<QueryId, (Cid, oneshot::Sender<Result<Vec<u8>>>)>,
) {
    match event {
        SwarmEvent::Behaviour(KotobaBehaviourEvent::Bitswap(bs_event)) => match bs_event {
            BitswapEvent::Progress(qid, remaining) => {
                debug!(%qid, remaining, "bitswap progress");
            }
            BitswapEvent::Complete(qid, result) => {
                if let Some((cid, resp)) = pending.remove(&qid) {
                    let answer = result
                        .map_err(|e| anyhow!("bitswap error: {e}"))
                        .and_then(|_| {
                            store
                                .get_local(&cid)
                                .ok_or_else(|| anyhow!("block missing after bitswap complete"))
                        });
                    let _ = resp.send(answer);
                }
            }
        },
        SwarmEvent::Behaviour(KotobaBehaviourEvent::Identify(ev)) => {
            debug!("identify event: {ev:?}");
        }
        SwarmEvent::NewListenAddr { address, .. } => {
            tracing::info!(%address, "kotoba-ipfs listening");
        }
        SwarmEvent::ConnectionEstablished { peer_id, .. } => {
            debug!(%peer_id, "connected");
        }
        SwarmEvent::ConnectionClosed { peer_id, .. } => {
            debug!(%peer_id, "disconnected");
        }
        _ => {}
    }
}
