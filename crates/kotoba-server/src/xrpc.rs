/// XRPC endpoint declarations and handlers for Kotoba
/// NSIDs follow ai.gftd.apps.kotoba.* namespace

pub const NSID_QUAD_CREATE:  &str = "ai.gftd.apps.kotoba.quad.create";
pub const NSID_QUAD_RETRACT: &str = "ai.gftd.apps.kotoba.quad.retract";
pub const NSID_GRAPH_QUERY:  &str = "ai.gftd.apps.kotoba.graph.query";
pub const NSID_COMMIT_GET:   &str = "ai.gftd.apps.kotoba.commit.get";
pub const NSID_INVOKE_RUN:   &str = "ai.gftd.apps.kotoba.invoke.run";
pub const NSID_INFER_RUN:    &str = "ai.gftd.apps.kotoba.infer.run";
pub const NSID_WEIGHT_PUT:   &str = "ai.gftd.apps.kotoba.weight.put";
pub const NSID_LORA_APPLY:   &str = "ai.gftd.apps.kotoba.lora.apply";
pub const NSID_EMBED_CREATE: &str = "ai.gftd.apps.kotoba.embed.create";
pub const NSID_NODE_STATUS:  &str = "ai.gftd.apps.kotoba.node.status";
pub const NSID_BLOCK_PUT:    &str = "ai.gftd.apps.kotoba.block.put";
pub const NSID_BLOCK_GET:    &str = "ai.gftd.apps.kotoba.block.get";
pub const NSID_COMMIT_STORE: &str = "ai.gftd.apps.kotoba.commit.store";

use std::sync::Arc;
use axum::{
    Json,
    extract::State,
    http::StatusCode,
    response::IntoResponse,
};
use serde::{Deserialize, Serialize};
use crate::server::KotobaState;

// ── Request / Response types ───────────────────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct QuadCreateReq {
    pub graph:     String,
    pub subject:   String,
    pub predicate: String,
    pub object:    String,
}

#[derive(Debug, Serialize)]
pub struct QuadCreateResp {
    pub status:     &'static str,
    pub journal_cid: String,
}

#[derive(Debug, Deserialize)]
pub struct InvokeRunReq {
    pub program_cid:  String,
    /// "wasm-node" | "wasm-udf" | "datalog"
    pub program_type: String,
    pub agent_did:    String,
    pub wasm_b64:     Option<String>,
    pub ctx_b64:      Option<String>,
}

#[derive(Debug, Serialize)]
pub struct InvokeRunResp {
    pub status:         &'static str,
    pub gas_used:       u64,
    pub output_b64:     String,
    pub assert_count:   usize,
    pub retract_count:  usize,
    /// CIDs of Journal entries created for each asserted quad
    pub journal_cids:   Vec<String>,
}

#[derive(Debug, Serialize)]
pub struct HealthResp {
    pub status:      &'static str,
    pub version:     &'static str,
    pub subsystems:  SubsystemStatus,
    pub node:        NodeInfo,
}

#[derive(Debug, Serialize)]
pub struct SubsystemStatus {
    pub kse_journal:   &'static str,
    pub kse_shelf:     &'static str,
    pub wasm_executor: &'static str,
    pub udf_executor:  &'static str,
    pub invoke_router: &'static str,
}

#[derive(Debug, Serialize)]
pub struct NodeInfo {
    pub node_id:    String,
    pub peer_count: usize,
}

// ── Handlers ───────────────────────────────────────────────────────────────

/// GET /_app/meta  /  GET /health
pub async fn health(State(state): State<Arc<KotobaState>>) -> impl IntoResponse {
    let neighborhood = state.neighborhood.read().await;
    Json(HealthResp {
        status:  "ok",
        version: state.version,
        subsystems: SubsystemStatus {
            kse_journal:   "ready",
            kse_shelf:     "ready",
            wasm_executor: "ready",
            udf_executor:  "ready",
            invoke_router: "ready",
        },
        node: NodeInfo {
            node_id:    hex::encode(state.local_node_id.0),
            peer_count: neighborhood.peers.len(),
        },
    })
}

/// POST /xrpc/ai.gftd.apps.kotoba.quad.create
/// Publish a Quad assert to the KSE Journal (SPO topic).
pub async fn quad_create(
    State(state): State<Arc<KotobaState>>,
    Json(req):    Json<QuadCreateReq>,
) -> impl IntoResponse {
    use kotoba_core::cid::KotobaCid;
    use kotoba_kqe::quad::{Quad, QuadObject};

    let quad = Quad {
        graph:     KotobaCid::from_bytes(req.graph.as_bytes()),
        subject:   KotobaCid::from_bytes(req.subject.as_bytes()),
        predicate: req.predicate.clone(),
        object:    QuadObject::Text(req.object.clone()),
    };

    // Journal (B2 persistence + GossipSub) AND QuadStore (Arrangement + ProllyTree)
    let journal_cid = state.journal_assert(&quad).await;
    state.quad_store.assert(quad).await;

    tracing::info!(
        graph     = %req.graph,
        subject   = %req.subject,
        predicate = %req.predicate,
        cid       = %journal_cid,
        "quad.create → Journal + QuadStore"
    );

    (StatusCode::OK, Json(QuadCreateResp { status: "ok", journal_cid }))
}

/// GET /xrpc/ai.gftd.apps.kotoba.node.status
pub async fn node_status(State(state): State<Arc<KotobaState>>) -> impl IntoResponse {
    let nb = state.neighborhood.read().await;
    Json(serde_json::json!({
        "node_id":    hex::encode(state.local_node_id.0),
        "peer_count": nb.peers.len(),
        "peers":      nb.peers.iter().map(|p| hex::encode(p.0)).collect::<Vec<_>>(),
        "k":          kotoba_dht::neighborhood::K,
    }))
}

/// POST /xrpc/ai.gftd.apps.kotoba.invoke.run
/// Execute a WASM component or Datalog program, then publish resulting quads to Journal.
pub async fn invoke_run(
    State(state): State<Arc<KotobaState>>,
    Json(req):    Json<InvokeRunReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    use kotoba_dht::source_chain::ProgramType;
    use base64::{Engine as _, engine::general_purpose::STANDARD as B64};

    let program_type = match req.program_type.as_str() {
        "wasm-node" => ProgramType::WasmNode,
        "wasm-udf"  => ProgramType::WasmUdf,
        "datalog"   => ProgramType::Datalog,
        other => return Err((StatusCode::BAD_REQUEST, format!("unknown program_type: {other}"))),
    };

    let wasm_bytes: Vec<u8> = match &req.wasm_b64 {
        Some(b64) => B64.decode(b64).map_err(|e| (StatusCode::BAD_REQUEST, e.to_string()))?,
        None if program_type != ProgramType::Datalog => {
            return Err((StatusCode::BAD_REQUEST, "wasm_b64 required for wasm programs".into()));
        }
        None => vec![],
    };

    let ctx_cbor: Vec<u8> = match &req.ctx_b64 {
        Some(b64) => B64.decode(b64).map_err(|e| (StatusCode::BAD_REQUEST, e.to_string()))?,
        None => vec![],
    };

    // Move owned data into spawn_blocking — dispatch is CPU-bound (Cranelift JIT)
    let program_cid = req.program_cid.clone();
    let agent_did   = req.agent_did.clone();
    let router      = Arc::clone(&state.router);
    let wasm_owned  = if wasm_bytes.is_empty() { None } else { Some(wasm_bytes) };

    let result = tokio::task::spawn_blocking(move || {
        let wasm_ref = wasm_owned.as_deref();
        router.dispatch(
            &program_cid,
            program_type,
            &agent_did,
            0,
            wasm_ref,
            ctx_cbor,
            None,
            None,
            &[],
            10_000,
        )
    })
    .await
    .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?
    .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;

    use kotoba_core::cid::KotobaCid;
    use kotoba_vm::DispatchResult;
    use kotoba_kqe::quad::{Quad, QuadObject};

    match result {
        DispatchResult::Wasm(r) => {
            // Publish each asserted quad to KSE Journal
            let mut journal_cids = Vec::with_capacity(r.assert_quads.len());
            for sq in &r.assert_quads {
                let quad = Quad {
                    graph:     KotobaCid::from_bytes(sq.graph.as_bytes()),
                    subject:   KotobaCid::from_bytes(sq.subject.as_bytes()),
                    predicate: sq.predicate.clone(),
                    object:    QuadObject::Bytes(sq.object_cbor.clone()),
                };
                let cid = state.journal_assert(&quad).await;
                journal_cids.push(cid);
            }
            // Publish retracts
            for sq in &r.retract_quads {
                let quad = Quad {
                    graph:     KotobaCid::from_bytes(sq.graph.as_bytes()),
                    subject:   KotobaCid::from_bytes(sq.subject.as_bytes()),
                    predicate: sq.predicate.clone(),
                    object:    QuadObject::Bytes(sq.object_cbor.clone()),
                };
                state.journal_retract(&quad).await;
            }

            tracing::info!(
                program_cid = %req.program_cid,
                gas_used    = r.gas_used,
                asserts     = r.assert_quads.len(),
                retracts    = r.retract_quads.len(),
                "invoke.run → Journal published"
            );

            Ok(Json(InvokeRunResp {
                status:        "ok",
                gas_used:      r.gas_used,
                output_b64:    B64.encode(&r.output_cbor),
                assert_count:  r.assert_quads.len(),
                retract_count: r.retract_quads.len(),
                journal_cids,
            }))
        }

        DispatchResult::Datalog(r) => {
            Ok(Json(InvokeRunResp {
                status:        "ok",
                gas_used:      r.steps_used as u64,
                output_b64:    B64.encode(format!("{:?}", r.status)),
                assert_count:  r.out_deltas.len(),
                retract_count: 0,
                journal_cids:  vec![],
            }))
        }
    }
}

// ── Block store endpoints ──────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct BlockPutReq {
    /// base64-encoded raw block bytes
    pub data_b64: String,
}

#[derive(Debug, Serialize)]
pub struct BlockPutResp {
    pub cid: String,
}

#[derive(Debug, Deserialize)]
pub struct BlockGetReq {
    pub cid: String,
}

#[derive(Debug, Serialize)]
pub struct BlockGetResp {
    pub cid:      String,
    pub data_b64: String,
}

/// POST /xrpc/ai.gftd.apps.kotoba.block.put
/// Write raw bytes into the block store, returning the CID.
pub async fn block_put(
    State(state): State<Arc<KotobaState>>,
    Json(req):    Json<BlockPutReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    use base64::{Engine as _, engine::general_purpose::STANDARD as B64};
    use kotoba_core::cid::KotobaCid;

    let bytes = B64.decode(&req.data_b64)
        .map_err(|e| (StatusCode::BAD_REQUEST, e.to_string()))?;
    let cid = KotobaCid::from_bytes(&bytes);
    state.block_store.put(&cid, &bytes)
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;

    // Fire-and-forget IPFS pin (E) — no-op if KOTOBA_IPFS_PIN_ENDPOINT not set
    if let Some(pin) = &state.ipfs_pin {
        let pin  = std::sync::Arc::clone(pin);
        let cid_str = cid.to_multibase();
        tokio::spawn(async move { pin.pin(&cid_str).await });
    }

    Ok(Json(BlockPutResp { cid: cid.to_multibase() }))
}

/// GET /xrpc/ai.gftd.apps.kotoba.block.get?cid=<multibase>
pub async fn block_get(
    State(state): State<Arc<KotobaState>>,
    axum::extract::Query(req): axum::extract::Query<BlockGetReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    use base64::{Engine as _, engine::general_purpose::STANDARD as B64};
    use kotoba_core::cid::KotobaCid;

    let cid = KotobaCid::from_multibase(&req.cid)
        .ok_or_else(|| (StatusCode::BAD_REQUEST, "invalid CID".into()))?;
    match state.block_store.get(&cid)
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?
    {
        None => Err((StatusCode::NOT_FOUND, "block not found".into())),
        Some(bytes) => Ok(Json(BlockGetResp {
            cid:      req.cid.clone(),
            data_b64: B64.encode(&bytes),
        })),
    }
}

// ── Commit endpoints ──────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct CommitGetReq {
    pub graph: String,
}

#[derive(Debug, Serialize)]
pub struct CommitGetResp {
    pub cid:    String,
    pub graph:  String,
    pub root:   String,
    pub prev:   Option<String>,
    pub author: String,
    pub seq:    u64,
    pub ts:     u64,
}

/// GET /xrpc/ai.gftd.apps.kotoba.commit.get?graph=<multibase>
pub async fn commit_get(
    State(state): State<Arc<KotobaState>>,
    axum::extract::Query(req): axum::extract::Query<CommitGetReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    use kotoba_core::cid::KotobaCid;

    let graph_cid = KotobaCid::from_multibase(&req.graph)
        .ok_or_else(|| (StatusCode::BAD_REQUEST, "invalid graph CID".into()))?;
    match state.quad_store.head_commit(&graph_cid).await {
        None => Err((StatusCode::NOT_FOUND, "no commit for graph".into())),
        Some(c) => Ok(Json(CommitGetResp {
            cid:    c.cid.to_multibase(),
            graph:  c.graph.to_multibase(),
            root:   c.root.to_multibase(),
            prev:   c.prev.map(|p| p.to_multibase()),
            author: c.author,
            seq:    c.seq,
            ts:     c.ts,
        })),
    }
}

/// POST /xrpc/ai.gftd.apps.kotoba.commit.store
/// Flush current Arrangement for the given graph into BlockStore and create a Commit.
#[derive(Debug, Deserialize)]
pub struct CommitStoreReq {
    pub graph:  String,
    pub author: String,
    pub seq:    u64,
}

pub async fn commit_store(
    State(state): State<Arc<KotobaState>>,
    Json(req):    Json<CommitStoreReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    use kotoba_core::cid::KotobaCid;

    let graph_cid = KotobaCid::from_multibase(&req.graph)
        .ok_or_else(|| (StatusCode::BAD_REQUEST, "invalid graph CID".into()))?;
    let cid = state.quad_store
        .commit(&req.author, graph_cid, req.seq)
        .await
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    Ok(Json(serde_json::json!({ "cid": cid.to_multibase() })))
}

// ── Graph query (B) ───────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct GraphQueryReq {
    /// Named graph CID (multibase base32lower)
    pub graph:     String,
    /// Optional subject CID filter (multibase or raw string)
    pub subject:   Option<String>,
    /// Optional predicate filter (exact string match)
    pub predicate: Option<String>,
    /// Datalog rules reserved for invoke.run; graph.query returns SPO matches only
    pub rules:     Option<String>,
}

/// GET /xrpc/ai.gftd.apps.kotoba.graph.query
/// SPO pattern query over the in-memory Arrangement.
/// Full Datalog evaluation: use invoke.run with program_type=datalog.
pub async fn graph_query(
    State(state): State<Arc<KotobaState>>,
    axum::extract::Query(req): axum::extract::Query<GraphQueryReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    use kotoba_core::cid::KotobaCid;

    let graph_cid = KotobaCid::from_multibase(&req.graph)
        .ok_or_else(|| (StatusCode::BAD_REQUEST, "invalid graph CID".into()))?;

    let arrangement = match state.quad_store.arrangement(&graph_cid).await {
        None => {
            return Ok(Json(serde_json::json!({ "graph": req.graph, "count": 0, "quads": [] })));
        }
        Some(a) => a,
    };

    let mut quads = arrangement.quads(&graph_cid);

    // Subject filter (accept multibase CID or raw string → hash to CID)
    if let Some(s) = &req.subject {
        let s_cid = KotobaCid::from_multibase(s)
            .unwrap_or_else(|| KotobaCid::from_bytes(s.as_bytes()));
        quads.retain(|q| q.subject == s_cid);
    }

    // Predicate filter
    if let Some(p) = &req.predicate {
        quads.retain(|q| &q.predicate == p);
    }

    Ok(Json(serde_json::json!({
        "graph": req.graph,
        "count": quads.len(),
        "quads": quads,
        "note":  if req.rules.is_some() { "use invoke.run for Datalog evaluation" } else { "" },
    })))
}

// ── Weight put (C) ────────────────────────────────────────────────────────

pub const NSID_WEIGHT_GET:  &str = "ai.gftd.apps.kotoba.weight.get";

#[derive(Debug, Deserialize)]
pub struct WeightPutReq {
    /// model CID (multibase) — identifies the model this weight belongs to
    pub model_cid: String,
    /// layer index
    pub layer:     u32,
    /// raw FP8 tensor bytes, base64-encoded
    pub data_b64:  String,
    /// tensor shape e.g. [4096, 4096]
    pub shape:     Vec<u32>,
    /// dtype string: "fp8e4m3" | "fp8e5m2" | "fp16" | "bf16" | "f32"
    pub dtype:     String,
    /// named graph CID (multibase) to index this weight in
    pub graph:     String,
}

#[derive(Debug, Serialize)]
pub struct WeightPutResp {
    pub blob_cid:    String,
    pub quad_cid:    String,
    pub layer:       u32,
}

/// POST /xrpc/ai.gftd.apps.kotoba.weight.put
pub async fn weight_put(
    State(state): State<Arc<KotobaState>>,
    Json(req):    Json<WeightPutReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    use base64::{Engine as _, engine::general_purpose::STANDARD as B64};
    use kotoba_core::cid::KotobaCid;
    use kotoba_kqe::quad::{Quad, QuadObject, TensorDtype};

    let bytes = B64.decode(&req.data_b64)
        .map_err(|e| (StatusCode::BAD_REQUEST, e.to_string()))?;

    // 1. Store raw tensor bytes in BlockStore (content-addressed)
    let blob_cid = KotobaCid::from_bytes(&bytes);
    state.block_store.put(&blob_cid, &bytes)
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;

    // 2. IPFS pin the tensor blob
    if let Some(pin) = &state.ipfs_pin {
        let pin  = std::sync::Arc::clone(pin);
        let cs   = blob_cid.to_multibase();
        tokio::spawn(async move { pin.pin(&cs).await });
    }

    // 3. Parse CIDs
    let model_cid = KotobaCid::from_multibase(&req.model_cid)
        .unwrap_or_else(|| KotobaCid::from_bytes(req.model_cid.as_bytes()));
    let graph_cid = KotobaCid::from_multibase(&req.graph)
        .unwrap_or_else(|| KotobaCid::from_bytes(req.graph.as_bytes()));

    let dtype = match req.dtype.as_str() {
        "fp8e4m3" | "f8e4m3" => TensorDtype::F8E4M3,
        "fp8e5m2" | "f8e5m2" => TensorDtype::F8E5M2,
        "fp16"    | "f16"    => TensorDtype::F16,
        "bf16"               => TensorDtype::BF16,
        _                    => TensorDtype::F32,
    };

    // 4. Assert WeightRef Quad: (graph, model_cid) --weight/layer/N--> blob_cid
    let quad = Quad {
        graph:     graph_cid,
        subject:   model_cid,
        predicate: format!("weight/layer/{}", req.layer),
        object:    QuadObject::TensorCid {
            cid:   blob_cid.clone(),
            shape: req.shape.clone(),
            dtype,
        },
    };
    let quad_cid = state.journal_assert(&quad).await;
    state.quad_store.assert(quad).await;

    tracing::info!(
        blob_cid = %blob_cid.to_multibase(),
        layer    = req.layer,
        bytes    = bytes.len(),
        "weight.put stored"
    );

    Ok(Json(WeightPutResp {
        blob_cid: blob_cid.to_multibase(),
        quad_cid,
        layer:    req.layer,
    }))
}
