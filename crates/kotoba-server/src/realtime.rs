//! Realtime game sync — the bidirectional INGRESS the firehose lacks.
//! ADR-2606060001, phase P0/P1.
//!
//! `GET /xrpc/com.etzhayyim.apps.kotoba.sync.connect?room=<id>&player=<n>` is a
//! WebSocket (T1 transport): the client sends `kotoba_rt::ClientMsg` (CBOR
//! binary) frames and receives `kotoba_rt::ServerMsg` frames off the room's
//! per-room broadcast bus. This bus is PHYSICALLY ISOLATED from the global KSE
//! LiveBus / firehose / gossip — per-frame traffic never federates; only the
//! periodic durable snapshot crosses into the cold lane (TODO P1 bridge).
//!
//! Scope notes (honest P0):
//!   - Sim is the reference `CounterSim`; the real `kotoba:kge` WASM sim is P2.
//!   - Dynamic membership within a fixed per-room `capacity` (slots sized up-front).
//!   - Auth gate reuses the firehose's node-level policy
//!     (`KOTOBA_DEFAULT_VISIBILITY` + Bearer/CACAO via `check_read_access`); the
//!     ADR's Worker-issued room token is a separate control-plane increment.

use std::collections::HashMap;
use std::sync::{Arc, OnceLock};
use std::time::Duration;

use axum::{
    extract::{
        ws::{Message, WebSocket, WebSocketUpgrade},
        Query, State,
    },
    http::{HeaderMap, StatusCode},
    response::{IntoResponse, Response},
};
use base64::engine::general_purpose::URL_SAFE_NO_PAD as B64URL;
use base64::Engine as _;
use bytes::Bytes;
use futures::{SinkExt, StreamExt};
use hmac::{Hmac, Mac};
use serde::Deserialize;
use sha2::Sha256;
use tokio::sync::Mutex;

use kotoba_core::cid::KotobaCid;
use kotoba_core::store::BlockStore;
use kotoba_vault::{LiveBus, Topic};
use kotoba_rt::{protocol, ClientMsg, CounterSim, PlayerId, RoomActor, RoomConfig, SimHost, SnapshotRef};

/// A room's simulation behind dynamic dispatch — `CounterSim` by default, or a
/// real `kotoba:kge` `WasmComponentSim` when a kge component is configured
/// (feature `realtime-wasm`). This is the room-registry swap (ADR-2606060001).
type RoomSim = Box<dyn SimHost + Send>;

use crate::graph_auth::{check_read_access, AccessDenied};
use crate::server::KotobaState;

/// WebSocket realtime transport endpoint (T1).
pub const NSID_SYNC_CONNECT: &str = "com.etzhayyim.apps.kotoba.sync.connect";

/// Tick cadence of the authoritative room loop.
const TICK_PERIOD: Duration = Duration::from_millis(50); // 20 Hz
/// Reap a room after this many consecutive idle (zero-subscriber) ticks.
const IDLE_TICKS_BEFORE_REAP: u32 = 200; // ~10s at 20 Hz
/// Per-room player capacity (simulation slots). Membership within it is dynamic.
const ROOM_CAPACITY: u32 = 8;

#[derive(Clone)]
struct RoomHandle {
    actor: Arc<Mutex<RoomActor<RoomSim>>>,
}

/// The kge component bytes a room runs, if configured (feature `realtime-wasm`).
#[cfg(feature = "realtime-wasm")]
static KGE_COMPONENT: OnceLock<Vec<u8>> = OnceLock::new();

/// Install the kge component the rooms should run (called from `build_router`
/// when `KOTOBA_RT_KGE_COMPONENT` points at a `.wasm`). Idempotent.
#[cfg(feature = "realtime-wasm")]
pub fn install_kge_component(bytes: Vec<u8>) {
    let _ = KGE_COMPONENT.set(bytes);
}

/// Fetch a kotoba:kge component's bytes from a block store by its multibase CID
/// (per-room `program_cid`). `None` if the CID is malformed or absent.
#[cfg(feature = "realtime-wasm")]
fn load_component_from(
    store: &(dyn BlockStore + Send + Sync),
    program_cid: &str,
) -> Option<Vec<u8>> {
    let cid = KotobaCid::from_multibase(program_cid)?;
    Some(store.get(&cid).ok()??.to_vec())
}

/// Build a room simulation. Preference order (feature `realtime-wasm`):
///   1. the room's `program_cid` component, fetched from the block store;
///   2. a node-wide installed component (`KOTOBA_RT_KGE_COMPONENT`);
///   3. the deterministic reference `CounterSim`.
fn make_sim_for(program_cid: Option<&str>) -> RoomSim {
    #[cfg(feature = "realtime-wasm")]
    {
        // 1. Per-room component selected by the room token's program_cid.
        if let Some(pc) = program_cid {
            if let Some(bytes) = cold().and_then(|c| load_component_from(&*c.block_store, pc)) {
                match kotoba_rt::WasmComponentSim::from_bytes(&bytes) {
                    Ok(sim) => return Box::new(sim),
                    Err(e) => tracing::warn!(error = %e, program_cid = pc, "kge component instantiate failed"),
                }
            } else {
                tracing::warn!(program_cid = pc, "kge component not found in block store");
            }
        }
        // 2. Node-wide default component.
        if let Some(bytes) = KGE_COMPONENT.get() {
            match kotoba_rt::WasmComponentSim::from_bytes(bytes) {
                Ok(sim) => return Box::new(sim),
                Err(e) => tracing::warn!(error = %e, "kotoba-rt: kge component load failed; CounterSim"),
            }
        }
    }
    let _ = program_cid;
    // 3. Reference sim.
    Box::new(CounterSim::new())
}

#[derive(Default)]
struct Registry {
    rooms: Mutex<HashMap<String, RoomHandle>>,
}

fn registry() -> &'static Registry {
    static REG: OnceLock<Registry> = OnceLock::new();
    REG.get_or_init(Registry::default)
}

/// The cold-lane sink: where periodic durable snapshots are content-addressed,
/// persisted, and announced. This is the ONLY path by which game state crosses
/// from the isolated per-room hot bus into the durable + federated lane
/// (block store + KSE LiveBus → firehose/gossip). Per-frame traffic never does.
///
/// Injected once at server boot (`install_cold_lane`) so the WS handler stays
/// free of `KotobaState` — keeping the route testable in isolation. When absent
/// (e.g. unit tests), snapshots fall back to a placeholder CID and are not
/// persisted.
struct ColdLane {
    block_store: Arc<dyn BlockStore + Send + Sync>,
    journal: Arc<LiveBus>,
}

static COLD: OnceLock<ColdLane> = OnceLock::new();

/// Wire the realtime cold-lane bridge to the node's block store + LiveBus.
/// Call once from `build_router`. Idempotent (later calls are ignored).
pub fn install_cold_lane(
    block_store: Arc<dyn BlockStore + Send + Sync>,
    journal: Arc<LiveBus>,
) {
    let _ = COLD.set(ColdLane {
        block_store,
        journal,
    });
}

fn cold() -> Option<&'static ColdLane> {
    COLD.get()
}

/// Content-address a durable snapshot blob with kotoba's CIDv1 and promote it to
/// a DURABLE, PINNED block — the replay guarantee. `put_durable` writes through
/// every persistent tier (CAR-on-B2 cold, etc.) and surfaces errors rather than
/// fire-and-forget; `pin` protects the CID from `BudgetedBlockStore` eviction so
/// a match remains replayable from its snapshots. Returns the CID.
fn persist_block(c: &ColdLane, blob: &[u8]) -> KotobaCid {
    let cid = KotobaCid::from_bytes(blob);
    if let Err(e) = c.block_store.put_durable(&cid, blob) {
        tracing::warn!(error = %e, cid = %cid, "kotoba-rt: durable snapshot put failed; hot fallback");
        let _ = c.block_store.put(&cid, blob);
    }
    c.block_store.pin(&cid);
    cid
}

/// Announce a durable snapshot on the room-scoped LiveBus topic — the single
/// hot→cold/federated bridge. Per-frame traffic never reaches here.
async fn announce_to_journal(
    c: &ColdLane,
    room: &str,
    tick: kotoba_rt::Tick,
    cid: &KotobaCid,
) {
    let sref = SnapshotRef {
        room: room.to_string(),
        tick,
        snapshot_cid: cid.to_multibase(),
    };
    if let Ok(payload) = protocol::encode(&sref) {
        c.journal
            .publish(Topic::new(format!("live/{}/snapshot", room)), Bytes::from(payload))
            .await;
    }
}

impl Registry {
    /// Look up a room, creating it (and its authoritative ticker task) on first
    /// use. `program_cid` (from the joiner's room token) binds the room's sim to
    /// a specific kotoba:kge component the first time the room is created.
    async fn get_or_create(&'static self, room: &str, program_cid: Option<&str>) -> RoomHandle {
        let mut map = self.rooms.lock().await;
        if let Some(h) = map.get(room) {
            return h.clone();
        }
        // Empty initial roster + fixed capacity: players join/leave dynamically
        // via tick-stamped roster events (ADR-2606060001 dynamic membership).
        let mut cfg = RoomConfig::new(room, Vec::new());
        cfg.capacity = ROOM_CAPACITY;
        let actor = Arc::new(Mutex::new(RoomActor::new(make_sim_for(program_cid), cfg)));
        let handle = RoomHandle {
            actor: actor.clone(),
        };
        map.insert(room.to_string(), handle.clone());
        drop(map);

        let room_id = room.to_string();
        tokio::spawn(async move {
            let mut interval = tokio::time::interval(TICK_PERIOD);
            let mut idle: u32 = 0;
            let mut ever_joined = false;
            loop {
                interval.tick().await;
                let (snap, count) = {
                    let mut a = actor.lock().await;
                    // cid_of content-addresses the durable blob with kotoba's own
                    // CIDv1 and PUTs it into the block store (cold lane). Without a
                    // cold lane (tests) it degrades to a placeholder, no persist.
                    let snap = a.tick_once(|blob| match cold() {
                        Some(c) => persist_block(c, blob).to_multibase(),
                        None => format!("kotoba-rt-snap-{}", blob.len()),
                    });
                    (snap, a.subscriber_count())
                };

                // The single bridge HOT → COLD/federated: announce the durable
                // snapshot on a room-scoped LiveBus topic (low rate). Per-frame
                // input/confirms never reach the LiveBus.
                if let (Some(ds), Some(c)) = (snap, cold()) {
                    let cid = KotobaCid::from_bytes(&ds.blob);
                    announce_to_journal(c, &room_id, ds.tick, &cid).await;
                }

                if count > 0 {
                    ever_joined = true;
                    idle = 0;
                } else if ever_joined {
                    idle += 1;
                    if idle >= IDLE_TICKS_BEFORE_REAP {
                        registry().rooms.lock().await.remove(&room_id);
                        tracing::info!(room = %room_id, "kotoba-rt: reaped idle room");
                        break;
                    }
                }
            }
        });

        handle
    }
}

#[derive(Debug, Deserialize)]
pub struct ConnectParams {
    pub room: String,
    pub player: u32,
    /// Worker-issued room token (compact JWT) — required when the control plane
    /// is wired. WebSocket clients pass it here since they can't set headers.
    pub token: Option<String>,
    /// Base64 CACAO delegation chain for the `private` visibility tier (used only
    /// in the no-control-plane fallback).
    pub cacao_b64: Option<String>,
}

/// Node-level read gate, identical policy to the firehose: open when `public`,
/// any non-empty Bearer when `authenticated`, CACAO `datom:read` when `private`
/// (the default). Per-room/per-player capability is the control plane's job.
async fn ws_authorize(
    state: &KotobaState,
    headers: &HeaderMap,
    cacao_b64: Option<&str>,
) -> Result<(), (StatusCode, String)> {
    // Sentinel all-zero CID → node default visibility (KOTOBA_DEFAULT_VISIBILITY).
    let visibility = state.graph_visibility(&KotobaCid([0u8; 36])).await;
    check_read_access(
        &visibility,
        headers,
        cacao_b64,
        Some(&state.operator_did),
        Some(&state.nonce_store),
    )
    .map_err(AccessDenied::into_response)
}

/// Claims carried by a Worker-issued room token (must mirror
/// `worker/src/realtime.ts` `RoomTokenClaims`).
#[derive(Debug, Deserialize)]
pub struct RoomTokenClaims {
    pub iss: String,
    pub sub: String,
    pub room: String,
    pub player: u32,
    pub node: String,
    pub iat: u64,
    pub exp: u64,
    /// Optional kotoba:kge component CID this room runs (per-room sim selection).
    #[serde(default)]
    pub program_cid: Option<String>,
}

/// Verify a Worker-issued room token (compact JWT, HS256) against the shared
/// `RT_TOKEN_SECRET`, then enforce that its `{room, player}` claims match the
/// connection — this is the per-room/per-player authorization the visibility
/// gate cannot express. Returns the claims, or an error string.
///
/// Wire format is byte-identical to `worker/src/realtime.ts`: three base64url
/// (no-pad) segments, signature = HMAC-SHA256 over `"{header}.{payload}"`.
pub fn verify_room_token(
    secret: &str,
    token: &str,
    now: u64,
    room: &str,
    player: u32,
) -> Result<RoomTokenClaims, String> {
    let mut it = token.split('.');
    let (h, p, s) = match (it.next(), it.next(), it.next(), it.next()) {
        (Some(h), Some(p), Some(s), None) => (h, p, s),
        _ => return Err("malformed token".into()),
    };
    let sig = B64URL.decode(s).map_err(|_| "bad signature b64")?;
    let mut mac = Hmac::<Sha256>::new_from_slice(secret.as_bytes())
        .map_err(|_| "bad secret")?;
    mac.update(format!("{h}.{p}").as_bytes());
    // Constant-time verification.
    mac.verify_slice(&sig).map_err(|_| "signature mismatch")?;

    let payload = B64URL.decode(p).map_err(|_| "bad payload b64")?;
    let claims: RoomTokenClaims =
        serde_json::from_slice(&payload).map_err(|e| format!("bad claims: {e}"))?;

    if claims.exp < now {
        return Err("token expired".into());
    }
    if claims.room != room {
        return Err("room mismatch".into());
    }
    if claims.player != player {
        return Err("player mismatch".into());
    }
    Ok(claims)
}

/// The shared room-token secret, if the realtime control plane is wired.
fn rt_token_secret() -> Option<String> {
    std::env::var("RT_TOKEN_SECRET").ok().filter(|s| !s.is_empty())
}

fn now_secs() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

/// Pull a bearer token from the `Authorization` header.
fn bearer(headers: &HeaderMap) -> Option<&str> {
    headers
        .get("authorization")
        .and_then(|v| v.to_str().ok())
        .and_then(|s| s.strip_prefix("Bearer "))
}

/// axum handler: authorize, then upgrade to WebSocket and join the room.
pub async fn ws_connect(
    State(state): State<std::sync::Arc<KotobaState>>,
    ws: WebSocketUpgrade,
    headers: HeaderMap,
    Query(params): Query<ConnectParams>,
) -> Response {
    // When the realtime control plane is wired (`RT_TOKEN_SECRET` shared with the
    // Worker), require a valid room token that authorizes THIS room + player —
    // the per-room/per-player authz the visibility gate can't express. The token
    // arrives as `?token=` (WebSocket clients can't set headers) or a Bearer.
    let mut program_cid: Option<String> = None;
    if let Some(secret) = rt_token_secret() {
        let token = params.token.as_deref().or_else(|| bearer(&headers));
        let Some(token) = token else {
            return (StatusCode::UNAUTHORIZED, "room token required".to_string()).into_response();
        };
        match verify_room_token(&secret, token, now_secs(), &params.room, params.player) {
            Ok(claims) => program_cid = claims.program_cid,
            Err(e) => return (StatusCode::UNAUTHORIZED, format!("room token: {e}")).into_response(),
        }
    } else if let Err((status, msg)) =
        ws_authorize(&state, &headers, params.cacao_b64.as_deref()).await
    {
        // No control plane configured → fall back to the node visibility gate.
        return (status, msg).into_response();
    }
    ws.on_upgrade(move |socket| handle_socket(socket, params, program_cid))
}

async fn handle_socket(socket: WebSocket, params: ConnectParams, program_cid: Option<String>) {
    let player = PlayerId(params.player);
    let handle = registry()
        .get_or_create(&params.room, program_cid.as_deref())
        .await;

    // Subscribe to the per-room bus, then announce the join.
    let mut rx = {
        let mut a = handle.actor.lock().await;
        let rx = a.subscribe();
        a.join(player);
        rx
    };

    let (mut sink, mut stream) = socket.split();

    // Egress: stream the room bus to this client as CBOR binary frames.
    let egress = tokio::spawn(async move {
        loop {
            match rx.recv().await {
                Ok(msg) => match protocol::encode(&msg) {
                    Ok(bytes) => {
                        if sink.send(Message::Binary(bytes)).await.is_err() {
                            break;
                        }
                    }
                    Err(_) => continue,
                },
                Err(tokio::sync::broadcast::error::RecvError::Lagged(_)) => continue,
                Err(_) => break, // bus closed
            }
        }
    });

    // Ingress: decode client frames into the authoritative engine.
    while let Some(Ok(msg)) = stream.next().await {
        match msg {
            Message::Binary(bytes) => {
                if let Ok(cmsg) = protocol::decode::<ClientMsg>(&bytes) {
                    let mut a = handle.actor.lock().await;
                    match cmsg {
                        ClientMsg::Input(f) => {
                            a.submit_input(f.player, f.tick, f.seq, f.input);
                        }
                        ClientMsg::Join { player, .. } => a.join(player),
                        ClientMsg::Leave { player, .. } => a.leave(player),
                        // T2: relay WebRTC signaling to the target peer over the
                        // reliable WS channel so they can establish a DataChannel.
                        ClientMsg::Signal { to, payload, .. } => a.relay_signal(player, to, payload),
                    }
                }
            }
            Message::Close(_) => break,
            _ => {}
        }
    }

    // Cleanup: leave + stop the egress pump.
    {
        let mut a = handle.actor.lock().await;
        a.leave(player);
    }
    egress.abort();
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::{routing::get, Router};
    use futures::{SinkExt, StreamExt};
    use kotoba_rt::{Input, InputFrame, ServerMsg, Tick};
    use std::time::Duration;
    use tokio_tungstenite::tungstenite::Message as WsMessage;

    /// An UNGATED handler (no auth) used only to test the transport in
    /// isolation — the production `ws_connect` is gated and exercised by
    /// `ws_authorize_*`. Same `handle_socket` body, so the round-trip is real.
    async fn ws_connect_ungated(
        ws: WebSocketUpgrade,
        Query(params): Query<ConnectParams>,
    ) -> Response {
        ws.on_upgrade(move |socket| handle_socket(socket, params, None))
    }

    /// End-to-end over a real TCP socket: connect → Join echoes a Welcome →
    /// send an Input → the authority forwards it back on the room bus. Proves
    /// the bidirectional ingress the firehose never had.
    #[tokio::test]
    async fn ws_connect_round_trips_join_and_input() {
        let app = Router::new().route(
            &format!("/xrpc/{}", NSID_SYNC_CONNECT),
            get(ws_connect_ungated),
        );
        let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
        let addr = listener.local_addr().unwrap();
        tokio::spawn(async move {
            axum::serve(listener, app).await.unwrap();
        });

        let url = format!(
            "ws://{}/xrpc/{}?room=e2e&player=0",
            addr, NSID_SYNC_CONNECT
        );
        let (mut ws, _) = tokio_tungstenite::connect_async(url).await.unwrap();

        // Expect a Welcome shortly after upgrade (join broadcast).
        let got_welcome = read_until(&mut ws, |m| matches!(m, ServerMsg::Welcome { .. })).await;
        assert!(got_welcome, "must receive Welcome on join");

        // Send an input frame; expect it forwarded back on the bus.
        let frame = ClientMsg::Input(InputFrame {
            room: "e2e".into(),
            player: PlayerId(0),
            tick: Tick(0),
            seq: 1,
            input: Input { buttons: 7, axes: vec![] },
        });
        ws.send(WsMessage::Binary(protocol::encode(&frame).unwrap()))
            .await
            .unwrap();

        let got_input = read_until(&mut ws, |m| {
            matches!(m, ServerMsg::Input(f) if f.input.buttons == 7 && f.player == PlayerId(0))
        })
        .await;
        assert!(got_input, "submitted input must be forwarded on the room bus");
    }

    /// Cross-implementation vector: this token was minted by the Worker
    /// (`worker/src/realtime.ts`, secret "test-secret-key") — the Rust node MUST
    /// verify it byte-for-byte, proving the two implementations interoperate.
    const WORKER_TOKEN: &str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJrb3RvYmFzZS5uZXQiLCJzdWIiOiJkaWQ6d2ViOmFsaWNlLmV4YW1wbGUiLCJyb29tIjoiYXJlbmEtMSIsInBsYXllciI6Mywibm9kZSI6IndzczovL24veCIsImlhdCI6MTAwMDAwMCwiZXhwIjoxMDAwMzAwfQ.Wv4UxGZfvxS2-dnO1JBpV9AZgzOSG33AfiYmIkaxmXE";

    #[test]
    fn room_token_verifies_worker_vector_and_enforces_claims() {
        let secret = "test-secret-key";
        let now = 1_000_010; // within [iat, exp]

        // Valid: correct secret, room, player, not expired.
        let claims = verify_room_token(secret, WORKER_TOKEN, now, "arena-1", 3)
            .expect("worker-minted token must verify in Rust");
        assert_eq!(claims.sub, "did:web:alice.example");
        assert_eq!(claims.player, 3);

        // Wrong secret → reject.
        assert!(verify_room_token("WRONG", WORKER_TOKEN, now, "arena-1", 3).is_err());
        // Wrong room → reject (per-room authz).
        assert!(verify_room_token(secret, WORKER_TOKEN, now, "other", 3).is_err());
        // Wrong player → reject (per-player authz).
        assert!(verify_room_token(secret, WORKER_TOKEN, now, "arena-1", 4).is_err());
        // Expired → reject.
        assert!(verify_room_token(secret, WORKER_TOKEN, 2_000_000, "arena-1", 3).is_err());
        // Tampered signature → reject.
        let tampered = format!("{}x", &WORKER_TOKEN[..WORKER_TOKEN.len() - 1]);
        assert!(verify_room_token(secret, &tampered, now, "arena-1", 3).is_err());
        // Malformed → reject (no panic).
        assert!(verify_room_token(secret, "a.b", now, "arena-1", 3).is_err());

        // The base vector carries no program_cid (backward compatible default).
        let base = verify_room_token(secret, WORKER_TOKEN, now, "arena-1", 3).unwrap();
        assert!(base.program_cid.is_none());
    }

    /// Cross-impl vector WITH a `program_cid` (minted by the Worker) — the node
    /// recovers it for per-room component selection.
    #[test]
    fn room_token_carries_program_cid() {
        const WORKER_TOKEN_PC: &str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJrb3RvYmFzZS5uZXQiLCJzdWIiOiJkaWQ6d2ViOmFsaWNlLmV4YW1wbGUiLCJyb29tIjoiYXJlbmEtMSIsInBsYXllciI6Mywibm9kZSI6IndzczovL24veCIsImlhdCI6MTAwMDAwMCwiZXhwIjoxMDAwMzAwLCJwcm9ncmFtX2NpZCI6ImJhZnlrZ2Vjb3VudGVyMTIzIn0.axhSHRv89DKtVCBjgqeZe6B8fujSSANkCxACxAiH0Wk";
        let claims =
            verify_room_token("test-secret-key", WORKER_TOKEN_PC, 1_000_010, "arena-1", 3).unwrap();
        assert_eq!(claims.program_cid.as_deref(), Some("bafykgecounter123"));
    }

    /// Per-room component selection: a component stored in the block store is
    /// fetched by its `program_cid` and instantiates as a real sim.
    #[cfg(feature = "realtime-wasm")]
    #[test]
    fn program_cid_loads_component_from_block_store() {
        let store = kotoba_store::MemoryBlockStore::new();
        const WASM: &[u8] = include_bytes!("../../kotoba-rt/testdata/kge_counter.wasm");
        let cid = KotobaCid::from_bytes(WASM);
        store.put(&cid, WASM).unwrap();

        let bytes = load_component_from(&store, &cid.to_multibase()).expect("load by program_cid");
        assert_eq!(bytes.len(), WASM.len());
        kotoba_rt::WasmComponentSim::from_bytes(&bytes).expect("instantiate from block-store bytes");

        // Unknown / malformed CID → None (no panic).
        assert!(load_component_from(&store, "!!!not-multibase").is_none());
    }

    /// Auth gate: a private node (the default) rejects an unauthenticated WS
    /// connect — no Bearer, no CACAO → a 4xx mentioning the missing credential.
    #[tokio::test]
    async fn ws_authorize_rejects_unauthenticated_on_private_node() {
        let state = KotobaState::new(None).expect("test state");
        // Default visibility is `private` (KOTOBA_DEFAULT_VISIBILITY unset).
        let err = ws_authorize(&state, &HeaderMap::new(), None)
            .await
            .expect_err("private node must reject anonymous connect");
        assert!(err.0.is_client_error(), "expected 4xx, got {}", err.0);
        assert!(
            err.1.to_lowercase().contains("cacao"),
            "message should cite the missing CACAO: {}",
            err.1
        );
    }

    /// Cold-lane bridge: a durable snapshot is content-addressed into the block
    /// store (retrievable by CID) and announced on the room-scoped LiveBus topic
    /// — and ONLY that. Uses a local `ColdLane` so it never touches the global.
    #[tokio::test]
    async fn durable_snapshot_persists_to_block_store_and_journal() {
        use kotoba_rt::DurableSnapshot;
        let c = ColdLane {
            block_store: Arc::new(kotoba_store::MemoryBlockStore::new()),
            journal: Arc::new(LiveBus::new()),
        };
        let ds = DurableSnapshot {
            tick: Tick(60),
            blob: vec![9u8, 8, 7, 6, 5],
        };

        let cid = persist_block(&c, &ds.blob);
        announce_to_journal(&c, "arena", ds.tick, &cid).await;

        // Block is retrievable by its content CID, byte-identical...
        let got = c.block_store.get(&cid).unwrap().expect("block stored");
        assert_eq!(got.as_ref(), ds.blob.as_slice());
        // ...and PINNED (replay guarantee — protected from eviction).
        assert!(c.block_store.is_pinned(&cid), "snapshot must be pinned");

        // Exactly one LiveBus entry, on the room-scoped snapshot topic, carrying
        // the SnapshotRef with the same CID.
        let entries = c.journal.read_since(0).await;
        assert_eq!(entries.len(), 1, "one snapshot announcement");
        assert_eq!(entries[0].topic, "live/arena/snapshot");
        let sref: SnapshotRef = protocol::decode(&entries[0].payload).unwrap();
        assert_eq!(sref.snapshot_cid, cid.to_multibase());
        assert_eq!(sref.tick, Tick(60));
    }

    /// Read bus frames until `pred` matches or a timeout elapses.
    async fn read_until<S>(ws: &mut S, pred: impl Fn(&ServerMsg) -> bool) -> bool
    where
        S: StreamExt<Item = Result<WsMessage, tokio_tungstenite::tungstenite::Error>> + Unpin,
    {
        let deadline = Duration::from_secs(3);
        loop {
            match tokio::time::timeout(deadline, ws.next()).await {
                Ok(Some(Ok(WsMessage::Binary(b)))) => {
                    if let Ok(msg) = protocol::decode::<ServerMsg>(&b) {
                        if pred(&msg) {
                            return true;
                        }
                    }
                }
                Ok(Some(Ok(_))) => continue,
                _ => return false,
            }
        }
    }
}
