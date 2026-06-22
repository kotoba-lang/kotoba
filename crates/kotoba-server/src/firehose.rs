//! HTTP egress over the KSE LiveBus — the "tap" half of the kotoba federation
//! surface (D in the D+E design, 2026-05-30).
//!
//! Two read-only endpoints, both keyed by the LiveBus's monotonic `seq` (the
//! cursor) so a consumer can resume exactly where it left off:
//!
//!   * `com.etzhayyim.apps.kotoba.sync.subscribe` — Server-Sent Events live-tail.
//!     Backfills `read_since(cursor+1)` then streams new entries as they are
//!     published.  Each SSE frame carries `id: <seq>`; on reconnect the client
//!     sends the last id back as `?cursor=` (or `Last-Event-ID`) to resume.
//!   * `com.etzhayyim.apps.kotoba.sync.events` — plain JSON cursor paging / long-poll.
//!     `?cursor=N&limit=K` returns the next batch; usable through any proxy or
//!     CF Worker without WebSocket/SSE support.
//!
//! This is the SAME ordered LiveBus that the libp2p gossip relay (E,
//! `net_actor`) federates to the mesh — D and E share one cursor, so what you
//! observe over HTTP is exactly what propagates over gossip.
//!
//! NOTE: this is NOT a spec-faithful `com.atproto.sync.subscribeRepos` relay.
//! kotoba has no MST / signed-commit / CAR path (record-log semantics), and the
//! quad projection hashes the repo DID + collection NSID one-way, so faithful
//! AT commits cannot be reconstructed here.  This streams kotoba's own ordered
//! event log under the kotoba NSID — see ADR for the etzhayyim-side AT-MST
//! origination path.

use std::collections::VecDeque;
use std::convert::Infallible;
use std::sync::Arc;
use std::time::Duration;

use axum::{
    extract::{Query, State},
    http::{HeaderMap, StatusCode},
    response::sse::{Event, KeepAlive, Sse},
    Json,
};
use base64::{engine::general_purpose::STANDARD as B64, Engine as _};
use futures::stream::{self, Stream};
use futures::StreamExt;
use serde::{Deserialize, Serialize};

use kotoba_core::cid::KotobaCid;
use kotoba_datomic::distributed::DistributedDatomReader;
use kotoba_ipfs::{IpnsName, IpnsRegistryError};
use kotoba_vault::{Cursor, LiveBus, LiveBusEntry, Topic};

use crate::graph_auth::{check_read_access, AccessDenied};
use crate::server::KotobaState;

/// SSE live-tail firehose.
pub const NSID_SYNC_SUBSCRIBE: &str = "com.etzhayyim.apps.kotoba.sync.subscribe";
/// JSON cursor paging / long-poll firehose.
pub const NSID_SYNC_EVENTS: &str = "com.etzhayyim.apps.kotoba.sync.events";
/// CommitDag-derived firehose: reconstruct one graph's change feed from the
/// Datomic commit chain (no LiveBus) — journal-independent durable replay.
pub const NSID_SYNC_EVENTS_FROM_COMMITS: &str = "com.etzhayyim.apps.kotoba.sync.eventsFromCommits";
/// Cross-graph CommitDag firehose: merge every registered graph's commit feed,
/// ordered by `(ts, graph, per-graph seq)`. The whole-node datomic change feed
/// without a journal.
pub const NSID_SYNC_EVENTS_ALL_GRAPHS: &str = "com.etzhayyim.apps.kotoba.sync.eventsAllGraphs";

/// Hard cap on a single paging response so a huge cold backfill can't OOM the node.
const MAX_PAGE_LIMIT: usize = 1000;
const DEFAULT_PAGE_LIMIT: usize = 100;
const MAX_TOPIC_PREFIX_LEN: usize = 256;
/// Default cap on how far behind `current_seq` a `cursor` may resume. A cursor
/// far in the past would force `read_since` to walk a huge backlog (cold-store
/// fetches) in one request — an amplification/OOM vector. Overridable with
/// `KOTOBA_MAX_FIREHOSE_BACKFILL`; deep history belongs to
/// `sync.eventsFromCommits` (paged from the CommitDag), not the live tail.
const MAX_BACKFILL_SPAN: u64 = 100_000;

fn max_backfill_span() -> u64 {
    std::env::var("KOTOBA_MAX_FIREHOSE_BACKFILL")
        .ok()
        .and_then(|v| v.trim().parse().ok())
        .filter(|&n| n > 0)
        .unwrap_or(MAX_BACKFILL_SPAN)
}

/// Reject a cursor that is too far behind the head to backfill in one shot.
fn check_backfill_span(
    cursor: Option<u64>,
    current_seq: u64,
) -> Result<(), (StatusCode, String)> {
    if let Some(c) = cursor {
        let span = current_seq.saturating_sub(c);
        let max = max_backfill_span();
        if span > max {
            return Err((
                StatusCode::BAD_REQUEST,
                format!(
                    "cursor {c} is {span} behind head (max {max}); \
                     use sync.eventsFromCommits for deep history"
                ),
            ));
        }
    }
    Ok(())
}

/// Optional absolute lifetime for an SSE connection (`KOTOBA_SSE_MAX_SECS`).
/// When set, the stream ends after this many seconds and the client resumes via
/// `?cursor=` — bounding how long a slow/idle reader can hold a connection.
fn sse_max_secs() -> Option<u64> {
    std::env::var("KOTOBA_SSE_MAX_SECS")
        .ok()
        .and_then(|v| v.trim().parse().ok())
        .filter(|&n| n > 0)
}

fn validate_cursor(cursor: Option<u64>) -> Result<(), (StatusCode, String)> {
    if cursor == Some(u64::MAX) {
        return Err((
            StatusCode::BAD_REQUEST,
            "cursor must be less than u64::MAX".to_string(),
        ));
    }
    Ok(())
}

fn validate_topic_prefix(prefix: Option<&str>) -> Result<(), (StatusCode, String)> {
    let Some(prefix) = prefix else {
        return Ok(());
    };
    if prefix.trim().is_empty() {
        return Err((
            StatusCode::BAD_REQUEST,
            "topic_prefix must not be empty".to_string(),
        ));
    }
    if prefix.len() > MAX_TOPIC_PREFIX_LEN {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("topic_prefix exceeds {MAX_TOPIC_PREFIX_LEN} bytes"),
        ));
    }
    if prefix.chars().any(char::is_control) {
        return Err((
            StatusCode::BAD_REQUEST,
            "topic_prefix must not contain control characters".to_string(),
        ));
    }
    Ok(())
}

fn validate_params(
    cursor: Option<u64>,
    topic_prefix: Option<&str>,
) -> Result<(), (StatusCode, String)> {
    validate_cursor(cursor)?;
    validate_topic_prefix(topic_prefix)
}

#[derive(Debug, Deserialize)]
pub struct SubscribeParams {
    /// Resume after this LiveBus seq (exclusive). Omit = live-only from now.
    pub cursor: Option<u64>,
    /// Only emit entries whose topic starts with this prefix (e.g. `jetstream/`).
    pub topic_prefix: Option<String>,
    /// CACAO delegation chain (base64) — required when the node default
    /// visibility is `private`.
    pub cacao_b64: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct EventsParams {
    pub cursor: Option<u64>,
    pub limit: Option<usize>,
    pub topic_prefix: Option<String>,
    pub cacao_b64: Option<String>,
}

/// Read-access gate for the firehose.
///
/// The firehose is a CROSS-graph, whole-LiveBus stream, so a per-graph
/// credential cannot bound it — we gate at the NODE level on
/// `KOTOBA_DEFAULT_VISIBILITY` (default `private`):
///   * `public`        → open
///   * `authenticated` → any non-empty Bearer token
///   * `private`       → CACAO `datom:read` delegation chain on the operator DID
///
/// Per-entry, per-graph filtering (e.g. a public-only firehose on a private
/// node) is intentionally out of scope here — see the project CLAUDE.md.
async fn gate(
    state: &KotobaState,
    headers: &HeaderMap,
    cacao_b64: Option<&str>,
) -> Result<(), (StatusCode, String)> {
    // Sentinel all-zero CID is never a registered named graph, so
    // `graph_visibility` returns the node default (KOTOBA_DEFAULT_VISIBILITY).
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

/// One firehose event in JSON form. `payload` is decoded as JSON when the
/// LiveBus payload is valid JSON (the common case — quads/records are JSON),
/// otherwise it is a base64 string of the raw bytes.
#[derive(Debug, Clone, Serialize)]
pub struct FirehoseEvent {
    pub seq: u64,
    pub ts: u64,
    /// Hybrid Logical Clock of the source commit (ADR-001) — the skew-resistant
    /// cross-graph ordering key. 0 for journal-sourced (non-datomic) events.
    #[serde(default)]
    pub hlc: u64,
    pub topic: String,
    pub cid: String,
    pub payload: serde_json::Value,
}

impl FirehoseEvent {
    /// Build a firehose event from a Datom — the single source of the `{topic,
    /// payload}` shape, shared by the CommitDag reconstruction and the live
    /// in-memory publish on the commit path. Matches the legacy LiveBus
    /// projection (assert → `Topic::quad_spo`, retract → `kotoba/retract/...`).
    pub fn from_datom(
        datom: &kotoba_datomic::Datom,
        graph_cid: &KotobaCid,
        seq: u64,
        ts: u64,
        hlc: u64,
    ) -> Self {
        let quad = crate::xrpc::datom_to_projection_quad(datom, graph_cid);
        let topic = if datom.added {
            Topic::quad_spo(
                &quad.graph.to_multibase(),
                &quad.subject.to_multibase(),
                &quad.predicate,
                &format!("{:?}", quad.object),
            )
            .0
        } else {
            format!(
                "kotoba/retract/{}/{}/{}",
                quad.graph, quad.subject, quad.predicate
            )
        };
        let payload = serde_json::to_value(&quad).unwrap_or(serde_json::Value::Null);
        let cid =
            KotobaCid::from_bytes(&serde_json::to_vec(&quad).unwrap_or_default()).to_multibase();
        FirehoseEvent {
            seq,
            ts,
            hlc,
            topic,
            cid,
            payload,
        }
    }

    fn from_entry(e: &LiveBusEntry) -> Self {
        let payload = match serde_json::from_slice::<serde_json::Value>(&e.payload) {
            Ok(v) => v,
            Err(_) => serde_json::Value::String(B64.encode(&e.payload)),
        };
        FirehoseEvent {
            seq: e.seq,
            ts: e.ts,
            hlc: 0, // journal (non-datomic) events carry no commit HLC
            topic: e.topic.clone(),
            cid: e.cid.to_multibase(),
            payload,
        }
    }
}

#[derive(Debug, Serialize)]
pub struct EventsResponse {
    pub events: Vec<FirehoseEvent>,
    /// Seq of the last event in this batch — pass back as `?cursor=` next time.
    pub cursor: u64,
    /// Current head seq of the LiveBus (so callers know how far behind they are).
    pub current_seq: u64,
    /// `limit` items returned but more are available past `cursor`.
    pub has_more: bool,
}

// ── SSE live-tail ──────────────────────────────────────────────────────────

struct SseState {
    backlog: VecDeque<LiveBusEntry>,
    live: Cursor,
    last_seq: u64,
    prefix: Option<String>,
}

/// `GET /xrpc/com.etzhayyim.apps.kotoba.sync.subscribe?cursor=N&topic_prefix=...`
pub async fn subscribe(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Query(params): Query<SubscribeParams>,
) -> Result<Sse<impl Stream<Item = Result<Event, Infallible>>>, (StatusCode, String)> {
    validate_params(params.cursor, params.topic_prefix.as_deref())?;
    gate(&state, &headers, params.cacao_b64.as_deref()).await?;

    let journal: Arc<LiveBus> = Arc::clone(&state.journal);

    // Subscribe to the live broadcast FIRST so no entry slips through the gap
    // between reading the backlog and attaching the tail. Overlapping seqs are
    // de-duplicated by `last_seq` below.
    let live = journal.subscribe();
    let baseline = journal.current_seq().await;
    check_backfill_span(params.cursor, baseline)?;

    let (backlog, last_seq) = match params.cursor {
        Some(c) => (journal.read_since(c + 1).await, c),
        None => (Vec::new(), baseline),
    };

    let init = SseState {
        backlog: backlog.into(),
        live,
        last_seq,
        prefix: params.topic_prefix,
    };

    let base = stream::unfold(init, |mut st| async move {
        loop {
            let entry = match st.backlog.pop_front() {
                Some(e) => e,
                None => match st.live.next().await {
                    Some(e) => e,
                    // Broadcast closed or the slow consumer lagged out of the
                    // ring — end the stream; the client resumes via cursor.
                    None => return None,
                },
            };

            if entry.seq <= st.last_seq {
                continue; // already emitted via the backlog/live overlap
            }
            if let Some(p) = &st.prefix {
                if !entry.topic.starts_with(p.as_str()) {
                    st.last_seq = entry.seq;
                    continue;
                }
            }
            st.last_seq = entry.seq;

            let ev = Event::default()
                .id(entry.seq.to_string())
                .event("firehose")
                .json_data(FirehoseEvent::from_entry(&entry))
                .unwrap_or_else(|_| Event::default().comment("payload encode error"));
            return Some((Ok::<_, Infallible>(ev), st));
        }
    });

    // Optionally cap the connection lifetime so a slow/idle reader can't hold a
    // connection forever — the client resumes from its last `id` via `?cursor=`.
    let stream: std::pin::Pin<Box<dyn Stream<Item = Result<Event, Infallible>> + Send>> =
        match sse_max_secs() {
            Some(secs) => {
                Box::pin(base.take_until(tokio::time::sleep(Duration::from_secs(secs))))
            }
            None => Box::pin(base),
        };

    Ok(Sse::new(stream).keep_alive(
        KeepAlive::new()
            .interval(Duration::from_secs(15))
            .text("keep-alive"),
    ))
}

// ── JSON cursor paging / long-poll ───────────────────────────────────────────

/// `GET /xrpc/com.etzhayyim.apps.kotoba.sync.events?cursor=N&limit=K&topic_prefix=...`
pub async fn events(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Query(params): Query<EventsParams>,
) -> Result<Json<EventsResponse>, (StatusCode, String)> {
    validate_params(params.cursor, params.topic_prefix.as_deref())?;
    gate(&state, &headers, params.cacao_b64.as_deref()).await?;

    let journal = &state.journal;
    let current_seq = journal.current_seq().await;
    check_backfill_span(params.cursor, current_seq)?;

    let from = params.cursor.map(|c| c + 1).unwrap_or(1);
    let limit = params
        .limit
        .unwrap_or(DEFAULT_PAGE_LIMIT)
        .min(MAX_PAGE_LIMIT);

    let mut entries = journal.read_since(from).await;
    if let Some(prefix) = &params.topic_prefix {
        entries.retain(|e| e.topic.starts_with(prefix.as_str()));
    }

    let has_more = entries.len() > limit;
    entries.truncate(limit);

    let cursor = entries.last().map(|e| e.seq).or(params.cursor).unwrap_or(0);

    let events = entries.iter().map(FirehoseEvent::from_entry).collect();

    Ok(Json(EventsResponse {
        events,
        cursor,
        current_seq,
        has_more,
    }))
}

// ── CommitDag-derived firehose (journal-free) ────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct CommitEventsParams {
    /// Graph CID (multibase) to reconstruct the change feed for.
    pub graph: String,
    pub cursor: Option<u64>,
    pub limit: Option<usize>,
    pub topic_prefix: Option<String>,
    pub cacao_b64: Option<String>,
}

/// Build the ordered firehose events for one graph straight from its Datomic
/// commit chain — the same `{topic,payload}` a LiveBus entry would carry, but
/// derived from `tx_range_from_head` instead of a persisted per-datom log. The
/// `seq` is a stable 1-based index in commit order (older commits keep their seq
/// as new ones append), so it works as a resumable cursor.
fn firehose_events_from_commitdag(
    state: &KotobaState,
    graph_mb: &str,
) -> Result<Vec<FirehoseEvent>, (StatusCode, String)> {
    let graph_cid = KotobaCid::from_multibase(graph_mb)
        .ok_or((StatusCode::BAD_REQUEST, "invalid graph CID".to_string()))?;
    let ipns_name = crate::xrpc::distributed_graph_ipns_name(&graph_cid);
    let head = match state.ipns_registry.resolve(&IpnsName::new(ipns_name)) {
        Ok(record) => KotobaCid::from_multibase(&record.value),
        Err(IpnsRegistryError::NotFound(_)) => None,
        Err(e) => return Err((StatusCode::INTERNAL_SERVER_ERROR, format!("ipns: {e}"))),
    };
    let Some(head) = head else {
        return Ok(Vec::new());
    };

    let reader = DistributedDatomReader::new(&*state.block_store, &*state.ipns_registry);
    let range = reader
        .tx_range_from_head(&head, None, None)
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, format!("tx_range: {e}")))?;

    let mut events = Vec::new();
    let mut seq = 0u64;
    for entry in &range {
        for datom in &entry.datoms {
            seq += 1;
            events.push(FirehoseEvent::from_datom(
                datom,
                &graph_cid,
                seq,
                entry.commit.ts,
                entry.commit.hlc,
            ));
        }
    }
    Ok(events)
}

/// `GET /xrpc/com.etzhayyim.apps.kotoba.sync.eventsFromCommits?graph=&cursor=N&limit=K&topic_prefix=...`
///
/// LiveBus-free firehose backfill: reconstructs one graph's change feed from the
/// CommitDag. Identical `{topic,payload}` to the LiveBus-backed `sync.events`,
/// so a consumer can replay durable history even when `KOTOBA_JOURNAL_WAL=off`
/// has dropped the per-datom journal blocks.
pub async fn events_from_commits(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Query(params): Query<CommitEventsParams>,
) -> Result<Json<EventsResponse>, (StatusCode, String)> {
    gate(&state, &headers, params.cacao_b64.as_deref()).await?;

    let all = firehose_events_from_commitdag(&state, &params.graph)?;
    let current_seq = all.last().map(|e| e.seq).unwrap_or(0);

    let from = params.cursor.unwrap_or(0);
    let limit = params
        .limit
        .unwrap_or(DEFAULT_PAGE_LIMIT)
        .min(MAX_PAGE_LIMIT);
    let mut events: Vec<FirehoseEvent> = all.into_iter().filter(|e| e.seq > from).collect();
    if let Some(prefix) = &params.topic_prefix {
        events.retain(|e| e.topic.starts_with(prefix.as_str()));
    }
    let has_more = events.len() > limit;
    events.truncate(limit);
    let cursor = events.last().map(|e| e.seq).or(params.cursor).unwrap_or(0);

    Ok(Json(EventsResponse {
        events,
        cursor,
        current_seq,
        has_more,
    }))
}

// ── Cross-graph CommitDag firehose ───────────────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct AllGraphsParams {
    pub cursor: Option<u64>,
    pub limit: Option<usize>,
    pub topic_prefix: Option<String>,
    pub cacao_b64: Option<String>,
}

/// Merge every registered graph's CommitDag change feed into one whole-node feed.
///
/// Ordering is `(commit.hlc, graph, per-graph seq)` (ADR-001). The Hybrid Logical
/// Clock is monotonic per node and skew-resistant, so cross-graph order is stable
/// and not at the mercy of wall-clock jumps; within a single graph it is exact.
/// The returned `seq` is a global 1-based index over the merged order; it is
/// stable for append-only growth (new commits sort to the tail) and serves as the
/// resume cursor.
fn firehose_events_all_graphs(
    state: &KotobaState,
) -> Result<Vec<FirehoseEvent>, (StatusCode, String)> {
    let mut merged: Vec<(u64, String, u64, FirehoseEvent)> = Vec::new();
    for record in state.ipns_registry.list() {
        let Some(graph_mb) = record.name.0.strip_prefix("k51-kotoba-") else {
            continue;
        };
        let per_graph = firehose_events_from_commitdag(state, graph_mb)?;
        for ev in per_graph {
            merged.push((ev.hlc, graph_mb.to_string(), ev.seq, ev));
        }
    }
    // (ts, graph, per-graph seq) — deterministic merge across graphs.
    merged.sort_by(|a, b| (a.0, &a.1, a.2).cmp(&(b.0, &b.1, b.2)));
    let mut out = Vec::with_capacity(merged.len());
    for (i, (_, _, _, mut ev)) in merged.into_iter().enumerate() {
        ev.seq = (i as u64) + 1;
        out.push(ev);
    }
    Ok(out)
}

/// `GET /xrpc/com.etzhayyim.apps.kotoba.sync.eventsAllGraphs?cursor=N&limit=K&topic_prefix=...`
///
/// Whole-node datomic firehose reconstructed from every graph's CommitDag — the
/// cross-graph equivalent of the per-datom LiveBus stream, with no journal.
pub async fn events_all_graphs(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Query(params): Query<AllGraphsParams>,
) -> Result<Json<EventsResponse>, (StatusCode, String)> {
    gate(&state, &headers, params.cacao_b64.as_deref()).await?;

    let all = firehose_events_all_graphs(&state)?;
    let current_seq = all.last().map(|e| e.seq).unwrap_or(0);

    let from = params.cursor.unwrap_or(0);
    let limit = params
        .limit
        .unwrap_or(DEFAULT_PAGE_LIMIT)
        .min(MAX_PAGE_LIMIT);
    let mut events: Vec<FirehoseEvent> = all.into_iter().filter(|e| e.seq > from).collect();
    if let Some(prefix) = &params.topic_prefix {
        events.retain(|e| e.topic.starts_with(prefix.as_str()));
    }
    let has_more = events.len() > limit;
    events.truncate(limit);
    let cursor = events.last().map(|e| e.seq).or(params.cursor).unwrap_or(0);

    Ok(Json(EventsResponse {
        events,
        cursor,
        current_seq,
        has_more,
    }))
}

#[cfg(test)]
mod tests {
    use super::*;
    use kotoba_core::cid::KotobaCid;

    fn entry(seq: u64, topic: &str, payload: &[u8]) -> LiveBusEntry {
        LiveBusEntry {
            seq,
            ts: 0,
            topic: topic.to_string(),
            payload: payload.to_vec(),
            cid: KotobaCid::from_bytes(payload),
        }
    }

    #[test]
    fn from_entry_decodes_json_payload_inline() {
        let e = entry(7, "jetstream/app.bsky.feed.post", br#"{"a":1,"b":"x"}"#);
        let fe = FirehoseEvent::from_entry(&e);
        assert_eq!(fe.seq, 7);
        assert_eq!(fe.topic, "jetstream/app.bsky.feed.post");
        assert_eq!(fe.payload["a"], serde_json::json!(1));
        assert_eq!(fe.payload["b"], serde_json::json!("x"));
    }

    #[test]
    fn from_entry_falls_back_to_base64_for_non_json() {
        let raw = &[0xff, 0x00, 0x10, 0xab];
        let e = entry(3, "blob/raw", raw);
        let fe = FirehoseEvent::from_entry(&e);
        let s = fe
            .payload
            .as_str()
            .expect("non-JSON payload must be a base64 string");
        assert_eq!(B64.decode(s).unwrap(), raw);
    }

    #[test]
    fn cursor_validation_rejects_overflow_sentinel() {
        assert!(validate_cursor(None).is_ok());
        assert!(validate_cursor(Some(0)).is_ok());
        assert!(validate_cursor(Some(u64::MAX - 1)).is_ok());
        assert!(validate_cursor(Some(u64::MAX)).is_err());
    }

    #[test]
    fn topic_prefix_validation_rejects_empty_control_and_oversized_values() {
        assert!(validate_topic_prefix(None).is_ok());
        assert!(validate_topic_prefix(Some("jetstream/")).is_ok());
        assert!(validate_topic_prefix(Some("   ")).is_err());
        assert!(validate_topic_prefix(Some("jetstream/\npost")).is_err());
        assert!(validate_topic_prefix(Some(&"x".repeat(MAX_TOPIC_PREFIX_LEN + 1))).is_err());
    }
}
