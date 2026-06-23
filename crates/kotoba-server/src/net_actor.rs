use kotoba_core::cid::KotobaCid;
use kotoba_core::store::BlockStore;
use kotoba_graph::QuadStore;
use kotoba_net::{KotobaNetEvent, KotobaSwarm, PREGEL_GOSSIP_TOPIC};
use kotoba_query::{quad::LegacyQuad as Quad, quad::LegacyQuadObject, Datom};
use kotoba_vault::LiveBusEntry;
use kotoba_vm::distributed::DistributedMessage;
use std::collections::{HashSet, VecDeque};
use std::sync::Arc;

/// Maximum number of CID existence checks in a single Bitswap want_have list.
const MAX_WANT_HAVE: usize = 1_000;
/// Maximum number of full block fetches in a single Bitswap want_block list.
const MAX_WANT_BLOCK: usize = 100;
/// Maximum number of WantSince delta-sync entries in a single request.
const MAX_WANT_SINCE: usize = 16;
/// Maximum commits returned per WantSince entry.
const MAX_DELTA_COMMITS_PER_GRAPH: usize = 1_000;
/// Total serialised byte cap across all delta_commits in one response (8 MiB).
const MAX_DELTA_COMMITS_TOTAL_BYTES: usize = 8 * 1024 * 1024;

/// GossipSub topic carrying the full KSE LiveBus firehose (E: relay role).
const FIREHOSE_TOPIC: &str = "firehose";
/// GossipSub topic carrying PRE re-key revocation warrants (ADR §23.7 wire).
/// Payload = serialized `RekeyRevocationRecord` (applied without a block fetch).
const REKEY_REVOKE_TOPIC: &str = "rekey/revoke";
/// Bound on the echo-guard set that stops a relay re-gossiping what it received.
const FIREHOSE_SEEN_CAP: usize = 8192;

/// Bounded content-CID de-dup guard. A relay receives a firehose entry, re-logs
/// it to its own LiveBus (re-sequenced), and that local LiveBus entry would
/// otherwise be picked up by the relay's own firehose cursor and gossiped back —
/// looping forever and inflating seq. Recording the entry's content CID (stable
/// blake3 of the payload, identical across nodes) lets the cursor skip the echo.
struct FirehoseSeen {
    ring: VecDeque<KotobaCid>,
    set: HashSet<KotobaCid>,
    cap: usize,
}

impl FirehoseSeen {
    fn new(cap: usize) -> Self {
        Self {
            ring: VecDeque::with_capacity(cap.min(1024)),
            set: HashSet::new(),
            cap,
        }
    }

    fn contains(&self, cid: &KotobaCid) -> bool {
        self.set.contains(cid)
    }

    fn insert(&mut self, cid: KotobaCid) {
        if self.set.insert(cid.clone()) {
            self.ring.push_back(cid);
            if self.ring.len() > self.cap {
                if let Some(old) = self.ring.pop_front() {
                    self.set.remove(&old);
                }
            }
        }
    }
}

/// Swarm actor task.
///
/// Four-way fan-out via `tokio::select!`:
///   1. `publish_rx`         — KSE outbound → `swarm.publish`
///   2. `pregel_outbound_rx` — Pregel runner outbound → `swarm.send_pregel_message`
///   3. `swarm.next_event`   — inbound events → Bitswap serving, KSE LiveBus, or Pregel channel
///
/// GossipSub topics managed here:
///   "kotoba/quad/assert"  / "kotoba/quad/retract" — KSE quad propagation
///   "kotoba/pregel/messages"                       — Distributed Pregel BSP messages
///   "kotoba/firehose"                              — full LiveBus relay (relay role)
///
/// Bug fix: after `journal.publish()` for "quad/assert" or "quad/retract" topics,
/// also deserialize the data as the legacy Quad wire projection and apply it to
/// the local graph store as a Datom whose transaction is the LiveBus entry CID.
///
/// When `relay` is true (NodeRole::Relay), the node additionally bridges its
/// full KSE LiveBus onto the `firehose` gossip topic and re-logs peers' firehose
/// entries — the mesh half of the D+E federation surface (2026-05-30).
/// Place a component on THIS node (KOTOBA Mesh M4): fetch its artifact by CID
/// and execute it on the WASM host. On success the node records it in `hosted`
/// (advertised on the next heartbeat), which closes the reconcile loop. If the
/// artifact is not local yet, or the CID is malformed, or execution fails, the
/// node skips it gracefully (a later auction round retries once bitswap pulls it).
pub(crate) fn start_component(
    executor: &kotoba_runtime::WasmExecutor,
    block_store: &(dyn BlockStore + Send + Sync),
    node_did: &str,
    cid: &str,
    hosted: &mut Vec<String>,
) {
    if hosted.iter().any(|c| c == cid) {
        return;
    }
    let Some(kcid) = KotobaCid::from_multibase(cid) else {
        tracing::warn!(%cid, "lattice start: malformed component CID");
        return;
    };
    let wasm = match block_store.get(&kcid) {
        Ok(Some(b)) => b,
        Ok(None) => {
            tracing::info!(%cid, "lattice start: artifact not local yet (awaiting bitswap) — not hosting");
            return;
        }
        Err(e) => {
            tracing::warn!(%cid, err = %e, "lattice start: artifact fetch failed");
            return;
        }
    };
    match executor.execute(
        cid,
        &wasm,
        node_did,
        Vec::new(),
        Vec::new(),
        std::collections::HashMap::new(),
    ) {
        Ok(res) => {
            tracing::info!(%cid, gas = res.gas_used, "lattice start: component placed and executed");
            hosted.push(cid.to_string());
        }
        Err(e) => tracing::warn!(%cid, err = %e, "lattice start: component execution failed"),
    }
}

pub async fn run(
    mut swarm: KotobaSwarm,
    mut publish_rx: tokio::sync::mpsc::Receiver<(String, Vec<u8>)>,
    journal: Arc<kotoba_vault::LiveBus>,
    pregel_inbound_tx: tokio::sync::mpsc::Sender<DistributedMessage>,
    mut pregel_out_rx: tokio::sync::mpsc::Receiver<DistributedMessage>,
    block_store: Arc<dyn BlockStore + Send + Sync>,
    quad_store: Arc<QuadStore>,
    pre_key_registry: Option<Arc<kotoba_vault::PreKeyRegistry>>,
    relay: bool,
    // WASM host for lattice component placement (StartComponent → execute).
    executor: Arc<kotoba_runtime::WasmExecutor>,
) {
    swarm.subscribe("quad/assert").ok();
    swarm.subscribe("quad/retract").ok();
    swarm.subscribe(REKEY_REVOKE_TOPIC).ok();
    swarm.subscribe_pregel().ok();

    // Full gossip topic string as published by KotobaSwarm (has "kotoba/" prefix)
    let pregel_full_topic = format!("kotoba/{PREGEL_GOSSIP_TOPIC}");

    // ── Relay role (E): bridge the local LiveBus onto the gossip firehose ──
    let mut firehose_cursor = journal.subscribe();
    let mut firehose_seen = FirehoseSeen::new(FIREHOSE_SEEN_CAP);
    if relay {
        swarm.subscribe(FIREHOSE_TOPIC).ok();
        tracing::info!("net_actor: relay role active — bridging KSE LiveBus ↔ gossip firehose");
    }

    // ── KOTOBA Mesh lattice participation (M3) ───────────────────────────
    // Join the lattice control plane: subscribe to the control topics, then
    // periodically advertise a Heartbeat and auto-bid on placement auctions.
    // No central master — every node is a leader-less peer.
    fn lattice_now_ms() -> u64 {
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_millis() as u64)
            .unwrap_or(0)
    }
    kotoba_net::lattice::subscribe_lattice(&mut swarm).ok();
    let node_did = format!("did:key:{}", swarm.local_peer_id);
    let node_labels: std::collections::BTreeMap<String, String> =
        std::env::var("KOTOBA_NODE_LABELS")
            .unwrap_or_default()
            .split(',')
            .filter_map(|kv| {
                let (k, v) = kv.split_once('=')?;
                Some((k.trim().to_string(), v.trim().to_string()))
            })
            .collect();
    // Capabilities the runtime supplies to hosted components (kotoba:kais/*).
    let node_caps: Vec<String> = ["kqe", "kse", "auth", "llm", "chain", "egress", "evm", "btc"]
        .iter()
        .map(|c| format!("cap/{c}"))
        .collect();
    let mut node_roles = vec![
        kotoba_lattice::NodeRole::Pin,
        kotoba_lattice::NodeRole::Compute,
    ];
    if relay {
        node_roles.push(kotoba_lattice::NodeRole::Relay);
    }
    // `my_heartbeat.hosted` grows as this node places components (M4).
    let mut my_heartbeat = kotoba_lattice::Heartbeat {
        node_did: node_did.clone(),
        roles: node_roles,
        labels: node_labels,
        caps: node_caps,
        free_gas: 10_000_000,
        hosted: Vec::new(),
        lat_ms: 0,
    };
    let mut lattice =
        kotoba_lattice::LatticeController::new(/*ttl*/ 15_000, /*bid_window*/ 3_000);
    // datom-Δ triggers installed via PutTriggers (M6): a matching asserted datom
    // places the component on this node (same path as auction placement).
    let mut delta_triggers: Vec<kotoba_lattice::DeltaTrigger> = Vec::new();
    let mut lattice_hb = tokio::time::interval(std::time::Duration::from_secs(5));
    tracing::info!(node_did = %node_did, "net_actor: lattice participation active");

    loop {
        tokio::select! {
            // ── Lattice: reconcile (auctions), close auctions (place), advertise ──
            _ = lattice_hb.tick() => {
                let now = lattice_now_ms();
                // emit auctions for any desired-vs-observed shortfall
                for (t, m) in lattice.tick(now) {
                    <KotobaSwarm as kotoba_lattice::Transport>::publish(&mut swarm, &t, &m).ok();
                }
                // close due auctions → awards + StartComponent; act on any addressed to us
                for (t, m) in lattice.close_due(now) {
                    if let kotoba_lattice::LatticeMessage::StartComponent { node_did: target, cid, .. } = &m {
                        if target == &node_did {
                            start_component(&executor, block_store.as_ref(), &node_did, cid, &mut my_heartbeat.hosted);
                        }
                    }
                    <KotobaSwarm as kotoba_lattice::Transport>::publish(&mut swarm, &t, &m).ok();
                }
                // advertise our (possibly updated) heartbeat
                let hb = kotoba_lattice::LatticeMessage::Heartbeat(my_heartbeat.clone());
                <KotobaSwarm as kotoba_lattice::Transport>::publish(
                    &mut swarm, kotoba_lattice::protocol::topic::HEARTBEAT, &hb).ok();
                lattice.on_heartbeat(my_heartbeat.clone(), now);
            }
            // ── KSE outbound: forward journal publish requests ───────────
            msg = publish_rx.recv() => {
                let Some((kse_topic, data)) = msg else { break };
                swarm.publish(&kse_topic, data).ok();
            }

            // ── Pregel outbound: forward runner messages to gossip ───────
            dmsg = pregel_out_rx.recv() => {
                let Some(dmsg) = dmsg else { break };
                swarm
                    .send_pregel_message(&dmsg.src, &dmsg.dst, &dmsg.payload)
                    .ok();
            }

            // ── Relay: bridge local LiveBus entries onto the gossip firehose ──
            jentry = firehose_cursor.next(), if relay => {
                if let Some(entry) = jentry {
                    // Quad mutations + Pregel control already have dedicated
                    // gossip paths — skip them to avoid double propagation.
                    // Skip entries we received via firehose (echo guard).
                    let own_path = entry.topic == "quad/assert"
                        || entry.topic == "quad/retract"
                        || entry.topic == PREGEL_GOSSIP_TOPIC;
                    if !own_path && !firehose_seen.contains(&entry.cid) {
                        let mut cbor = Vec::new();
                        if ciborium::into_writer(&entry, &mut cbor).is_ok() {
                            swarm.publish(FIREHOSE_TOPIC, cbor).ok();
                        }
                    }
                }
            }

            // ── Inbound: peer events → Bitswap / KSE LiveBus / Pregel ───
            event = swarm.next_event() => {
                let Some(event) = event else { break };
                match event {
                    KotobaNetEvent::BitswapRequest { peer, request, channel } => {
                        let n_have  = request.want_have.len();
                        let n_block = request.want_block.len();
                        let n_since = request.want_since.len();
                        if n_have > MAX_WANT_HAVE || n_block > MAX_WANT_BLOCK || n_since > MAX_WANT_SINCE {
                            tracing::warn!(
                                peer = %peer,
                                n_have, n_block, n_since,
                                "Bitswap request exceeds per-request caps — ignored"
                            );
                            // Do not respond; the peer will time out on its end.
                            continue;
                        }

                        let mut have          = Vec::new();
                        let mut dont_have     = Vec::new();
                        let mut blocks        = Vec::new();
                        let mut delta_commits = Vec::new();
                        let mut delta_bytes   = 0usize;

                        for raw in &request.want_have {
                            let cid = kotoba_core::cid::KotobaCid(*raw);
                            if block_store.has(&cid) {
                                have.push(*raw);
                            } else {
                                dont_have.push(*raw);
                            }
                        }
                        for raw in &request.want_block {
                            let cid = kotoba_core::cid::KotobaCid(*raw);
                            match block_store.get(&cid) {
                                Ok(Some(bytes)) => blocks.push((*raw, bytes.to_vec())),
                                _               => dont_have.push(*raw),
                            }
                        }
                        // Selective-sync delta: CBOR-serialise Commit chain oldest-first.
                        // Hard cap: MAX_DELTA_COMMITS_PER_GRAPH commits per graph,
                        // MAX_DELTA_COMMITS_TOTAL_BYTES bytes total.
                        'ws_loop: for ws in &request.want_since {
                            let graph_cid = kotoba_core::cid::KotobaCid(ws.graph_cid);
                            let head      = ws.head_cid.map(kotoba_core::cid::KotobaCid);
                            let commits   = quad_store.commits_since(&graph_cid, head.as_ref()).await;
                            for commit in commits.into_iter().take(MAX_DELTA_COMMITS_PER_GRAPH) {
                                if delta_bytes >= MAX_DELTA_COMMITS_TOTAL_BYTES {
                                    tracing::warn!(
                                        peer = %peer,
                                        "Bitswap delta_commits byte cap reached — truncating response"
                                    );
                                    break 'ws_loop;
                                }
                                let cid_raw = commit.cid.0;
                                let mut buf = Vec::new();
                                if ciborium::into_writer(&commit, &mut buf).is_ok() {
                                    delta_bytes += buf.len();
                                    delta_commits.push((cid_raw, buf));
                                }
                            }
                        }

                        swarm.swarm.behaviour_mut().bitswap
                            .send_response(channel, kotoba_net::BitswapResponse {
                                have, dont_have, blocks, delta_commits,
                            })
                            .ok();
                    }
                    KotobaNetEvent::GossipMessage { topic, data, .. } => {
                        if let Some(lmsg) = kotoba_net::lattice::decode_lattice(&topic, &data) {
                            // Lattice control plane: ingest, and auto-bid on any
                            // auction this node is eligible for.
                            match &lmsg {
                                // auto-bid on any auction we're eligible for
                                kotoba_lattice::LatticeMessage::Auction(auction) => {
                                    if let Some(bid) = kotoba_lattice::LatticeController::bid_for(
                                        auction,
                                        &my_heartbeat,
                                    ) {
                                        <KotobaSwarm as kotoba_lattice::Transport>::publish(
                                            &mut swarm,
                                            kotoba_lattice::protocol::topic::AUCTION,
                                            &kotoba_lattice::LatticeMessage::Bid(bid),
                                        )
                                        .ok();
                                    }
                                }
                                // a reconciler awarded a component to us → place it
                                kotoba_lattice::LatticeMessage::StartComponent { node_did: target, cid, .. } => {
                                    if target == &node_did {
                                        start_component(&executor, block_store.as_ref(), &node_did, cid, &mut my_heartbeat.hosted);
                                    }
                                }
                                // out-of-proc capability call addressed to us (wRPC, M5):
                                // gate on the mesh policy (CACAO link), then reply.
                                kotoba_lattice::LatticeMessage::CapInvoke {
                                    id, source, provider_did, target_cap, ability, ..
                                } => {
                                    if provider_did == &node_did {
                                        let d = lattice.authorize(source, target_cap, ability);
                                        let result = if d.allowed {
                                            // remote capability execution wiring is the next increment;
                                            // the policy gate (link authorization) is enforced here.
                                            kotoba_lattice::LatticeMessage::CapResult {
                                                id: id.clone(), ok: true, payload: Vec::new(), error: None,
                                            }
                                        } else {
                                            tracing::warn!(%source, %target_cap, %ability, reason = %d.reason, "wRPC: capability invocation denied by mesh policy");
                                            kotoba_lattice::LatticeMessage::CapResult {
                                                id: id.clone(), ok: false, payload: Vec::new(), error: Some(d.reason),
                                            }
                                        };
                                        <KotobaSwarm as kotoba_lattice::Transport>::publish(
                                            &mut swarm, kotoba_lattice::protocol::topic::CAP, &result).ok();
                                    }
                                }
                                // install datom-Δ triggers (M6)
                                kotoba_lattice::LatticeMessage::PutTriggers { triggers, .. } => {
                                    delta_triggers = triggers.clone();
                                    tracing::info!(n = delta_triggers.len(), "lattice: datom-Δ triggers installed");
                                }
                                _ => {}
                            }
                            lattice.on_message(lmsg, lattice_now_ms());
                        } else if topic == pregel_full_topic
                            || topic.ends_with(PREGEL_GOSSIP_TOPIC)
                        {
                            // Decode Pregel gossip message and forward to runner
                            if let Ok(pnet) =
                                serde_json::from_slice::<kotoba_net::PregelNetMessage>(&data)
                            {
                                use base64::{Engine as _, engine::general_purpose::STANDARD as B64};
                                match B64.decode(&pnet.payload_b64) {
                                    Ok(payload) => {
                                        pregel_inbound_tx
                                            .try_send(DistributedMessage {
                                                src: pnet.src,
                                                dst: pnet.dst,
                                                payload,
                                            })
                                            .ok();
                                    }
                                    Err(e) => {
                                        tracing::warn!(src = %pnet.src, err = %e, "pregel gossip: bad base64 payload — skipped");
                                    }
                                }
                            }
                        } else {
                            let kse_name = topic
                                .strip_prefix("kotoba/")
                                .unwrap_or(&topic)
                                .to_string();

                            if kse_name == FIREHOSE_TOPIC {
                                // Relay inbound: decode the LiveBusEntry envelope
                                // and re-log it locally (re-sequenced) for
                                // durability + HTTP-tap (D) visibility + onward
                                // gossip forwarding. Record its content CID so
                                // our own firehose cursor doesn't echo it back.
                                match ciborium::from_reader::<LiveBusEntry, _>(&data[..]) {
                                    Ok(fe) => {
                                        firehose_seen.insert(fe.cid.clone());
                                        journal
                                            .publish(
                                                kotoba_vault::Topic(fe.topic),
                                                bytes::Bytes::from(fe.payload),
                                            )
                                            .await;
                                    }
                                    Err(e) => tracing::warn!(err = %e, "firehose: bad LiveBusEntry envelope — skipped"),
                                }
                            } else if kse_name == REKEY_REVOKE_TOPIC {
                                // PRE re-key revocation warrant (§23.7 wire):
                                // apply the gossiped record bytes directly — no
                                // BlockStore fetch needed. No-op if we hold no
                                // registry or the pair was never granted here.
                                if let Some(reg) = &pre_key_registry {
                                    reg.apply_revocation_warrant_bytes(&data).await;
                                }
                            } else {
                                let maybe_quad_op = if kse_name == "quad/assert" {
                                    serde_json::from_slice::<Quad>(&data).ok().map(|quad| (quad, true))
                                } else if kse_name == "quad/retract" {
                                    serde_json::from_slice::<Quad>(&data).ok().map(|quad| (quad, false))
                                } else {
                                    None
                                };
                                let kse_topic = kotoba_vault::Topic(kse_name);
                                let entry = journal.publish(kse_topic, bytes::Bytes::from(data)).await;
                                if let Some((quad, op)) = maybe_quad_op {
                                    // capture predicate + (text) object before the move, for M6 Δ-triggers
                                    let delta_pred = quad.predicate.clone();
                                    let delta_obj = match &quad.object {
                                        LegacyQuadObject::Text(s) => s.clone(),
                                        _ => String::new(),
                                    };
                                    let graph_cid = quad.graph.clone();
                                    let mut datom = Datom::from_legacy_quad(quad, op);
                                    datom.tx = entry.cid.clone();
                                    quad_store.apply_journaled_datom(graph_cid, datom).await;

                                    // datom-Δ trigger (M6): an *assertion* matching a registered
                                    // trigger places that component on this node.
                                    if op && !delta_triggers.is_empty() {
                                        for cid in kotoba_lattice::fired_by_datom(&delta_triggers, &delta_pred, &delta_obj) {
                                            tracing::info!(%cid, predicate = %delta_pred, "datom-Δ trigger fired — placing component");
                                            start_component(&executor, block_store.as_ref(), &node_did, cid, &mut my_heartbeat.hosted);
                                        }
                                    }
                                }
                            }
                        }
                    }
                    _ => {}
                }
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn cid(byte: u8) -> KotobaCid {
        KotobaCid([byte; 36])
    }

    // ── KOTOBA Mesh M4: component placement path (start_component) ──
    // The success path (real component → execute → hosted) is covered by the
    // end-to-end `kotoba app deploy` run; here we lock down the defensive
    // branches that keep a node from wedging on bad/missing artifacts.

    fn test_executor() -> kotoba_runtime::WasmExecutor {
        kotoba_runtime::WasmExecutor::new(10_000_000).unwrap()
    }

    #[test]
    fn start_component_skips_malformed_cid() {
        let store = kotoba_store::MemoryBlockStore::new();
        let mut hosted = Vec::new();
        start_component(
            &test_executor(),
            &store,
            "did:self",
            "not-a-real-cid",
            &mut hosted,
        );
        assert!(hosted.is_empty(), "malformed CID must not be hosted");
    }

    #[test]
    fn start_component_skips_when_artifact_absent() {
        // valid CID, but the artifact is not in the local store yet (bitswap
        // hasn't pulled it) → skip, do not host, do not panic.
        let store = kotoba_store::MemoryBlockStore::new();
        let absent = KotobaCid::from_bytes(b"some component bytes").to_multibase();
        let mut hosted = Vec::new();
        start_component(&test_executor(), &store, "did:self", &absent, &mut hosted);
        assert!(hosted.is_empty(), "absent artifact must not be hosted");
    }

    #[test]
    fn start_component_handles_non_wasm_artifact_gracefully() {
        // artifact present but not a valid component → execute fails → skip.
        let store = kotoba_store::MemoryBlockStore::new();
        let garbage = b"this is definitely not a wasm component";
        let kc = KotobaCid::from_bytes(garbage);
        store.put(&kc, garbage).unwrap();
        let mut hosted = Vec::new();
        start_component(
            &test_executor(),
            &store,
            "did:self",
            &kc.to_multibase(),
            &mut hosted,
        );
        assert!(
            hosted.is_empty(),
            "uncompilable artifact must not be hosted"
        );
    }

    #[test]
    fn start_component_is_idempotent_for_already_hosted() {
        let store = kotoba_store::MemoryBlockStore::new();
        let mut hosted = vec!["bafyAlready".to_string()];
        start_component(
            &test_executor(),
            &store,
            "did:self",
            "bafyAlready",
            &mut hosted,
        );
        assert_eq!(
            hosted,
            vec!["bafyAlready".to_string()],
            "must not double-add"
        );
    }

    /// Loop-body coverage: spawn the real `net_actor::run` task for one node and
    /// assert a *separate* observer swarm receives that node's auto-published
    /// Heartbeat over real QUIC gossipsub. This drives the actual `select!`
    /// loop — the heartbeat-interval arm, `subscribe_lattice`, and the in-loop
    /// `Transport::publish` — not just the extracted helpers.
    #[tokio::test]
    async fn run_loop_publishes_heartbeat_observed_by_a_peer() {
        use std::sync::Arc;
        use std::time::Duration;

        // observer node: subscribes to the lattice and just listens
        let mut observer = KotobaSwarm::new("/ip4/127.0.0.1/udp/0/quic-v1".parse().unwrap())
            .await
            .unwrap();
        kotoba_net::lattice::subscribe_lattice(&mut observer).unwrap();
        let obs_addr = tokio::time::timeout(Duration::from_secs(5), async {
            loop {
                if let Some(KotobaNetEvent::ListenAddr(a)) = observer.next_event().await {
                    return a;
                }
            }
        })
        .await
        .expect("observer listen addr");
        let obs_peer = observer.local_peer_id;

        // run-node swarm: dial the observer BEFORE handing it to run()
        let mut node = KotobaSwarm::new("/ip4/127.0.0.1/udp/0/quic-v1".parse().unwrap())
            .await
            .unwrap();
        let expected_did = format!("did:key:{}", node.local_peer_id);
        node.add_peer(obs_peer, obs_addr);

        // assemble run()'s dependencies
        let (_pub_tx, pub_rx) = tokio::sync::mpsc::channel(8);
        let (pin_tx, _pin_rx) = tokio::sync::mpsc::channel(8);
        let (_pout_tx, pout_rx) = tokio::sync::mpsc::channel(8);
        let journal = Arc::new(kotoba_vault::LiveBus::new());
        let store: Arc<dyn BlockStore + Send + Sync> =
            Arc::new(kotoba_store::MemoryBlockStore::new());
        let quad_store = Arc::new(QuadStore::new(Arc::clone(&journal), Arc::clone(&store)));
        let executor = Arc::new(kotoba_runtime::WasmExecutor::new(10_000_000).unwrap());

        tokio::spawn(run(
            node, pub_rx, journal, pin_tx, pout_rx, store, quad_store, None, false, executor,
        ));

        // observer waits for the run-node's heartbeat (interval is 5 s; first
        // tick races mesh formation, so allow up to 12 s for a delivered one)
        let hb = tokio::time::timeout(Duration::from_secs(12), async {
            loop {
                if let Some(KotobaNetEvent::GossipMessage { topic, data, .. }) =
                    observer.next_event().await
                {
                    if let Some(kotoba_lattice::LatticeMessage::Heartbeat(hb)) =
                        kotoba_net::lattice::decode_lattice(&topic, &data)
                    {
                        if hb.node_did == expected_did {
                            return hb;
                        }
                    }
                }
            }
        })
        .await
        .expect("run-node never published an observable heartbeat within 12s");

        // the loop advertised this node's real capabilities + compute role
        assert!(hb.caps.iter().any(|c| c == "cap/kqe"));
        assert!(hb.roles.contains(&kotoba_lattice::NodeRole::Compute));
    }

    #[test]
    fn firehose_seen_dedups_and_evicts_fifo() {
        let mut seen = FirehoseSeen::new(2);
        seen.insert(cid(1));
        seen.insert(cid(2));
        assert!(seen.contains(&cid(1)));
        assert!(seen.contains(&cid(2)));

        // Over capacity → oldest (cid 1) evicted.
        seen.insert(cid(3));
        assert!(!seen.contains(&cid(1)));
        assert!(seen.contains(&cid(2)));
        assert!(seen.contains(&cid(3)));
    }

    #[test]
    fn firehose_seen_insert_is_idempotent() {
        let mut seen = FirehoseSeen::new(4);
        seen.insert(cid(9));
        seen.insert(cid(9));
        // A duplicate insert must not consume a second ring slot.
        seen.insert(cid(10));
        seen.insert(cid(11));
        seen.insert(cid(12));
        assert!(seen.contains(&cid(9)));
        assert!(seen.contains(&cid(12)));
    }

    #[test]
    fn max_want_have_is_1000() {
        assert_eq!(MAX_WANT_HAVE, 1_000);
    }

    #[test]
    fn max_want_block_is_100() {
        assert_eq!(MAX_WANT_BLOCK, 100);
    }

    #[test]
    fn max_want_since_is_16() {
        assert_eq!(MAX_WANT_SINCE, 16);
    }

    #[test]
    fn max_delta_commits_per_graph_is_1000() {
        assert_eq!(MAX_DELTA_COMMITS_PER_GRAPH, 1_000);
    }

    #[test]
    fn max_delta_commits_total_bytes_is_8mib() {
        assert_eq!(MAX_DELTA_COMMITS_TOTAL_BYTES, 8 * 1024 * 1024);
    }

    #[test]
    fn want_block_is_fraction_of_want_have() {
        assert!(
            MAX_WANT_BLOCK < MAX_WANT_HAVE,
            "want_block limit should be smaller than want_have"
        );
    }
}
