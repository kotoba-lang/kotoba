//! MCP JSON-RPC 2.0 handler — kotoba MCP facade (ADR-2605091400)
//!
//! Wire:  POST /mcp  (JSON-RPC 2.0)
//! Auth:  initialize / tools/list / ping → public
//!        tools/call → requires `Authorization: Bearer <AT-session-JWT>`
//!
//! Tools exposed:
//!   kotoba_datom_create     — assert a Datom-compatible atomic fact
//!   kotoba_quad_create      — legacy alias for kotoba_datom_create
//!   kotoba_graph_query      — SPO pattern query
//!   kotoba_infer_run        — run inference via inference engine
//!   kotoba_embed_create     — create and store a text embedding
//!   kotoba_weight_put       — store an FP8 tensor weight blob
//!   kotoba_lora_apply       — register a LoRA adapter delta
//!   kotoba_email_list       — list encrypted emails for an owner DID
//!   kotoba_email_read       — return one email; legacy bodies decrypt server-side,
//!                             Signal envelopes are returned for client-side open
//!   kotoba_wasm_run         — run a WASM Component Model program via Pregel BSP
//!   kotoba_datalog_run      — evaluate Datalog with citation tracking + royalty flush
//!   kotoba_node_info        — return this node's DID, roles, NodeId, peer count
//!   kotoba_node_register    — write/refresh node registration Quads
//!   kotoba_network_peers    — list KDHT neighborhood peers
//!   kotoba_graph_gc         — mark-sweep GC: delete unreachable blocks from the block store
//!   kotoba_commit_prune     — prune historical non-HEAD commit entries from CommitDag (15)

pub const MCP_TOOL_DATOM_CREATE: &str = "kotoba_datom_create";
pub const MCP_TOOL_QUAD_CREATE: &str = "kotoba_quad_create";
pub const MCP_TOOL_GRAPH_QUERY: &str = "kotoba_graph_query";
pub const MCP_TOOL_INFER_RUN: &str = "kotoba_infer_run";
pub const MCP_TOOL_EMBED_CREATE: &str = "kotoba_embed_create";
pub const MCP_TOOL_WEIGHT_PUT: &str = "kotoba_weight_put";
pub const MCP_TOOL_LORA_APPLY: &str = "kotoba_lora_apply";
pub const MCP_TOOL_EMAIL_LIST: &str = "kotoba_email_list";
pub const MCP_TOOL_EMAIL_READ: &str = "kotoba_email_read";
pub const MCP_TOOL_WASM_RUN: &str = "kotoba_wasm_run";
pub const MCP_TOOL_DATALOG_RUN: &str = "kotoba_datalog_run";
pub const MCP_TOOL_NODE_INFO: &str = "kotoba_node_info";
pub const MCP_TOOL_NODE_REGISTER: &str = "kotoba_node_register";
pub const MCP_TOOL_NETWORK_PEERS: &str = "kotoba_network_peers";
pub const MCP_TOOL_GRAPH_GC: &str = "kotoba_graph_gc";
pub const MCP_TOOL_COMMIT_PRUNE: &str = "kotoba_commit_prune";
pub const MCP_TOOL_SPARQL_QUERY: &str = "kotoba_sparql_query";
pub const MCP_TOOL_MULTI_HOP: &str = "kotoba_multi_hop";

use axum::{
    extract::State,
    http::{HeaderMap, StatusCode},
    response::IntoResponse,
    Json,
};
use kotoba_core::cid::KotobaCid;
use kotoba_graph::quad_store::QuadStore;
use kotoba_query::{delta::Delta, quad::LegacyQuad, quad::LegacyQuadObject};
use kotoba_store::MemoryBlockStore;
use kotoba_vault::live_bus::LiveBus;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};

use crate::server::KotobaState;

// ── JSON-RPC 2.0 envelope types ──────────────────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct JsonRpcRequest {
    pub jsonrpc: String,
    pub id: Option<Value>,
    pub method: String,
    pub params: Option<Value>,
}

#[derive(Debug, Serialize)]
pub struct JsonRpcResponse {
    pub jsonrpc: &'static str,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub id: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub result: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<JsonRpcError>,
}

#[derive(Debug, Serialize)]
pub struct JsonRpcError {
    pub code: i32,
    pub message: String,
}

impl JsonRpcResponse {
    fn ok(id: Option<Value>, result: Value) -> Self {
        Self {
            jsonrpc: "2.0",
            id,
            result: Some(result),
            error: None,
        }
    }

    fn err(id: Option<Value>, code: i32, message: impl Into<String>) -> Self {
        Self {
            jsonrpc: "2.0",
            id,
            result: None,
            error: Some(JsonRpcError {
                code,
                message: message.into(),
            }),
        }
    }
}

// ── JSON-RPC error codes ──────────────────────────────────────────────────────

const ERR_PARSE: i32 = -32700;
const ERR_NOT_FOUND: i32 = -32601;
const ERR_INVALID_PARAMS: i32 = -32602;
const ERR_INTERNAL: i32 = -32603;
const ERR_AUTH: i32 = -32001; // kotoba extension

use crate::email_xrpc::{
    DEFAULT_EMAIL_LIST_LIMIT, ENC_SIGNAL_V1, MAX_EMAIL_CID_LEN, MAX_EMAIL_DATE_LEN,
    MAX_EMAIL_LIST_LIMIT, MAX_EMAIL_LIST_OFFSET, MAX_EMAIL_MESSAGE_ID_LEN, MAX_LEGACY_ADDR_LEN,
    MAX_LEGACY_SUBJECT_LEN, MAX_OWNER_DID_LEN, MAX_THREAD_ID_LEN,
};

const MAX_MCP_CID_FIELD_LEN: usize = 512;

fn parse_mcp_cid_field(label: &str, value: &str) -> Result<KotobaCid, (i32, String)> {
    let value = value.trim();
    if value.is_empty() {
        return Err((ERR_INVALID_PARAMS, format!("{label} must not be empty")));
    }
    if value.len() > MAX_MCP_CID_FIELD_LEN {
        return Err((
            ERR_INVALID_PARAMS,
            format!(
                "{label} too large ({} bytes, limit {MAX_MCP_CID_FIELD_LEN})",
                value.len()
            ),
        ));
    }
    if value.chars().any(char::is_control) {
        return Err((
            ERR_INVALID_PARAMS,
            format!("{label} contains control characters"),
        ));
    }
    Ok(KotobaCid::from_multibase(value).unwrap_or_else(|| KotobaCid::from_bytes(value.as_bytes())))
}

fn validate_mcp_text_field(label: &str, value: &str, max_len: usize) -> Result<(), (i32, String)> {
    if value.trim().is_empty() {
        return Err((ERR_INVALID_PARAMS, format!("{label} must not be empty")));
    }
    if value.len() > max_len {
        return Err((
            ERR_INVALID_PARAMS,
            format!("{label} too large ({} bytes, limit {max_len})", value.len()),
        ));
    }
    if value.chars().any(char::is_control) {
        return Err((
            ERR_INVALID_PARAMS,
            format!("{label} contains control characters"),
        ));
    }
    Ok(())
}

fn optional_usize_param(args: &Value, key: &str, default: usize) -> Result<usize, (i32, String)> {
    let Some(value) = args.get(key) else {
        return Ok(default);
    };
    let Some(value) = value.as_u64() else {
        return Err((
            ERR_INVALID_PARAMS,
            format!("{key} must be a non-negative integer"),
        ));
    };
    usize::try_from(value).map_err(|_| {
        (
            ERR_INVALID_PARAMS,
            format!("{key} is too large for this platform"),
        )
    })
}

fn email_list_limit_param(args: &Value) -> Result<usize, (i32, String)> {
    let limit = optional_usize_param(args, "limit", DEFAULT_EMAIL_LIST_LIMIT)?;
    if limit == 0 {
        return Err((ERR_INVALID_PARAMS, "limit must be at least 1".to_string()));
    }
    if limit > MAX_EMAIL_LIST_LIMIT {
        return Err((
            ERR_INVALID_PARAMS,
            format!("limit exceeds {MAX_EMAIL_LIST_LIMIT}"),
        ));
    }
    Ok(limit)
}

fn email_list_offset_param(args: &Value) -> Result<usize, (i32, String)> {
    let offset = optional_usize_param(args, "offset", 0)?;
    if offset > MAX_EMAIL_LIST_OFFSET {
        return Err((
            ERR_INVALID_PARAMS,
            format!("offset exceeds {MAX_EMAIL_LIST_OFFSET}"),
        ));
    }
    Ok(offset)
}

fn validate_mcp_email_cid_param(value: &str) -> Result<KotobaCid, (i32, String)> {
    if value.trim().is_empty() {
        return Err((
            ERR_INVALID_PARAMS,
            "email_cid must not be empty".to_string(),
        ));
    }
    if value.len() > MAX_EMAIL_CID_LEN {
        return Err((
            ERR_INVALID_PARAMS,
            format!("email_cid must be 1-{MAX_EMAIL_CID_LEN} bytes"),
        ));
    }
    if value.bytes().any(|byte| !(0x21..=0x7e).contains(&byte)) {
        return Err((
            ERR_INVALID_PARAMS,
            "email_cid must contain only visible ASCII characters".to_string(),
        ));
    }
    KotobaCid::from_multibase(value).ok_or_else(|| {
        (
            ERR_INVALID_PARAMS,
            "invalid email_cid multibase".to_string(),
        )
    })
}

// ── Tool InputSchema definitions ─────────────────────────────────────────────

fn tools_list() -> Value {
    json!({
        "tools": [
            {
                "name": MCP_TOOL_DATOM_CREATE,
                "description": "Assert a Datom-compatible atomic fact into a named graph. The persisted fact is tracked as (E, A, V, T, Added); subject/predicate/object are the compatibility input projection.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "graph":     { "type": "string", "description": "Named graph CID (multibase) or any string (auto-hashed)" },
                        "subject":   { "type": "string", "description": "Entity CID (multibase) or entity identifier" },
                        "predicate": { "type": "string", "description": "Attribute / relation name (e.g. 'knows', 'weight/layer/0')" },
                        "object":    { "type": "string", "description": "Value text, CID, or literal" }
                    },
                    "required": ["graph", "subject", "predicate", "object"]
                }
            },
            {
                "name": MCP_TOOL_QUAD_CREATE,
                "description": "Legacy alias for kotoba_datom_create. Asserts a Datom-compatible atomic fact from subject, predicate, and object.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "graph":     { "type": "string", "description": "Named graph CID (multibase) or any string (auto-hashed)" },
                        "subject":   { "type": "string", "description": "Entity CID (multibase) or entity identifier" },
                        "predicate": { "type": "string", "description": "Attribute / relation name (e.g. 'knows', 'weight/layer/0')" },
                        "object":    { "type": "string", "description": "Value text, CID, or literal" }
                    },
                    "required": ["graph", "subject", "predicate", "object"]
                }
            },
            {
                "name": MCP_TOOL_GRAPH_QUERY,
                "description": "Graph query over a named graph. Supports EAVT (subject), AVET (predicate+object), AVET-prefix (predicate_prefix) indexed paths in addition to full-scan SPO.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "graph":            { "type": "string", "description": "Named graph CID (multibase)" },
                        "subject":          { "type": "string", "description": "(optional) Subject filter — EAVT index" },
                        "predicate":        { "type": "string", "description": "(optional) Predicate filter — exact match" },
                        "object":           { "type": "string", "description": "(optional) Object filter — combined with predicate for AVET P+O→S lookup" },
                        "predicate_prefix": { "type": "string", "description": "(optional) Predicate prefix range scan — AVET BTree range (e.g. 'weight/' lists all weight quads)" }
                    },
                    "required": ["graph"]
                }
            },
            {
                "name": MCP_TOOL_INFER_RUN,
                "description": "Run text inference via the Kotoba inference engine (Gemma 4 E2B or configured model).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "prompt":         { "type": "string", "description": "Prompt text" },
                        "max_new_tokens": { "type": "integer", "description": "Maximum tokens to generate (default 256)" }
                    },
                    "required": ["prompt"]
                }
            },
            {
                "name": MCP_TOOL_EMBED_CREATE,
                "description": "Compute a text embedding and store it as a Datom in the named graph.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "text":      { "type": "string",  "description": "Text to embed" },
                        "doc_cid":   { "type": "string",  "description": "Document CID (multibase) identifying the source" },
                        "model_cid": { "type": "string",  "description": "Model CID (multibase) identifying the embedding model" },
                        "graph":     { "type": "string",  "description": "Named graph CID (multibase) to index into" }
                    },
                    "required": ["text", "doc_cid", "model_cid", "graph"]
                }
            },
            {
                "name": MCP_TOOL_WEIGHT_PUT,
                "description": "Store a raw FP8 weight tensor blob and assert its Quad into the model graph.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "model_cid": { "type": "string",  "description": "Model CID (multibase)" },
                        "layer":     { "type": "integer", "description": "Layer index" },
                        "data_b64":  { "type": "string",  "description": "Raw tensor bytes, base64-encoded" },
                        "shape":     { "type": "array",   "items": { "type": "integer" }, "description": "Tensor shape" },
                        "dtype":     { "type": "string",  "description": "Dtype: fp8e4m3 | fp8e5m2 | fp16 | bf16 | f32" },
                        "graph":     { "type": "string",  "description": "Named graph CID (multibase)" }
                    },
                    "required": ["model_cid", "layer", "data_b64", "shape", "dtype", "graph"]
                }
            },
            {
                "name": MCP_TOOL_EMAIL_LIST,
                "description": "List emails stored in the Kotoba encrypted inbox for an owner DID. Returns plaintext date and message_id; legacy encrypted display fields (from/subject) are opened server-side when possible; Signal metadata remains zero-access.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "owner_did": { "type": "string", "minLength": 1, "maxLength": 512, "pattern": "^did:[!-~]+$", "description": "DID of the mailbox owner (e.g. did:plc:xxxx)" },
                        "limit":     { "type": "integer", "minimum": 1, "maximum": 200, "description": "Max results (default 50, max 200)" },
                        "offset":    { "type": "integer", "minimum": 0, "maximum": 10000, "description": "Pagination offset" }
                    },
                    "required": ["owner_did"]
                }
            },
            {
                "name": MCP_TOOL_EMAIL_READ,
                "description": "Return one stored email. Legacy records decrypt body and metadata server-side with KOTOBA_VAULT_KEY; Signal records return signalMessage for client-side open and do not expose a server-decrypted body.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "email_cid": { "type": "string", "minLength": 1, "maxLength": 256, "description": "Email CID (canonical multibase) returned by kotoba_email_list; only visible ASCII is accepted" },
                        "owner_did": { "type": "string", "minLength": 1, "maxLength": 512, "pattern": "^did:[!-~]+$", "description": "DID of the mailbox owner" }
                    },
                    "required": ["email_cid", "owner_did"]
                }
            },
            {
                "name": MCP_TOOL_LORA_APPLY,
                "description": "Register a LoRA adapter delta as a Quad in the model graph.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "model_cid":   { "type": "string",  "description": "Base model CID (multibase)" },
                        "rank":        { "type": "integer", "description": "LoRA adapter rank" },
                        "graph":       { "type": "string",  "description": "Named graph CID (multibase)" },
                        "adapter_b64": { "type": "string",  "description": "Raw LoRA bytes, base64-encoded" }
                    },
                    "required": ["model_cid", "rank", "graph", "adapter_b64"]
                }
            },
            {
                "name": MCP_TOOL_WASM_RUN,
                "description": "Run a WASM Component Model program via the Pregel BSP engine. The guest controls continuation via output CBOR {\"status\":\"continue\"}. Gas consumed is billed as a mKOTO Quad per agent DID.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "wasm_b64":       { "type": "string",  "description": "Compiled WASM Component Model binary, base64-encoded" },
                        "agent_did":      { "type": "string",  "description": "DID of the agent invoking the program (billed for gas)" },
                        "ctx_cbor_b64":   { "type": "string",  "description": "Initial context CBOR map, base64-encoded (passed as first superstep inbox payload)" },
                        "max_supersteps": { "type": "integer", "description": "Max BSP supersteps (default 32)" }
                    },
                    "required": ["wasm_b64", "agent_did", "ctx_cbor_b64"]
                }
            },
            {
                "name": MCP_TOOL_DATALOG_RUN,
                "description": "Evaluate a Datalog program against a named graph arrangement. Citations are tracked per join hit; royalty Quads are written to the ledger graph at epoch flush.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "graph":            { "type": "string",  "description": "Named graph CID (multibase) to evaluate against" },
                        "rules":            { "type": "array",   "description": "Array of DatalogRule objects ({head, body})" },
                        "epoch_pool_koto":  { "type": "integer", "description": "mKOTO pool to distribute as royalties this epoch (default 1000000 = 1 KOTO)" }
                    },
                    "required": ["graph", "rules"]
                }
            },
            {
                "name": MCP_TOOL_NODE_INFO,
                "description": "Return this node's DID, participation roles, NodeId hex, version, ephemeral flag, and KDHT peer count.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": MCP_TOOL_NODE_REGISTER,
                "description": "Write or refresh this node's registration Quads in the kotoba/network/nodes graph. Returns the operator DID.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": MCP_TOOL_NETWORK_PEERS,
                "description": "List KDHT neighborhood peers for this node.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": MCP_TOOL_GRAPH_GC,
                "description": "Mark-sweep GC: walk CommitDag to collect live block CIDs, then delete any block not reachable from a live commit. Returns the count of deleted blocks. Safe to call at any time — idempotent.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": MCP_TOOL_COMMIT_PRUNE,
                "description": "Prune historical non-HEAD commit entries from the in-memory CommitDag where seq < before_seq. HEAD commits are always preserved. Call after kotoba_graph_gc to free DAG memory. Returns pruned count and remaining dag_size.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "before_seq": {
                            "type": "integer",
                            "description": "Remove non-HEAD commits whose seq is strictly less than this value. Use the current committed_seq to discard all history."
                        }
                    },
                    "required": ["before_seq"]
                }
            },
            {
                "name": MCP_TOOL_SPARQL_QUERY,
                "description": "Execute a SPARQL SELECT BGP query over the committed IPFS-backed ProllyTree indexes. Routes to the optimal cold-path index: EAVT (bound subject cid:…), AVET (predicate+literal), AEVT (predicate only), VAET (bound object cid:…), or a 2-triple AVET×AVET join. Predicates may be relative IRIs (e.g. <role>) or absolute IRIs. Optionally CACAO-gated with a base64-encoded CACAO chain.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "graph":      { "type": "string", "description": "Named graph CID (multibase) to query" },
                        "sparql":     { "type": "string", "description": "SPARQL SELECT query (WHERE clause with 1 or 2 triple patterns)" },
                        "cacao_b64":  { "type": "string", "description": "(optional) Base64-encoded CACAO delegation chain for datom:read authorisation" }
                    },
                    "required": ["graph", "sparql"]
                }
            },
            {
                "name": MCP_TOOL_MULTI_HOP,
                "description": "BFS multi-hop traversal from a start entity following QuadObject::Cid references across the committed IPFS-backed ProllyTree (EAVT cold path per hop). Returns (depth, quad) pairs in BFS order. Optionally CACAO-gated.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "graph":     { "type": "string",  "description": "Named graph CID (multibase)" },
                        "start":     { "type": "string",  "description": "Start entity CID (multibase) or identifier string (auto-hashed)" },
                        "max_hops":  { "type": "integer", "description": "Maximum BFS depth (default 2, max 8)" },
                        "cacao_b64": { "type": "string",  "description": "(optional) Base64-encoded CACAO delegation chain for datom:read authorisation" }
                    },
                    "required": ["graph", "start"]
                }
            }
        ]
    })
}

// ── Auth helper ───────────────────────────────────────────────────────────────

fn is_mutating(method: &str, _tool: Option<&str>) -> bool {
    if method == "tools/call" {
        return true;
    }
    if method == "resources/write" {
        return true;
    }
    false
}

fn check_auth(headers: &HeaderMap) -> bool {
    let Some(token) = headers
        .get("authorization")
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.strip_prefix("Bearer "))
    else {
        return false;
    };
    !crate::graph_auth::jwt_exp_elapsed(token)
}

/// Extract the `sub` claim from the Bearer JWT, if present and non-expired.
fn caller_sub(headers: &HeaderMap) -> Option<String> {
    let token = headers
        .get("authorization")
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.strip_prefix("Bearer "))?;
    if crate::graph_auth::jwt_exp_elapsed(token) {
        return None;
    }
    crate::graph_auth::jwt_sub(token)
}

/// Administrative tools that modify storage structure (not data content) must
/// be restricted to the operator to prevent accidental or malicious data loss.
const ADMIN_ONLY_TOOLS: &[&str] = &[
    MCP_TOOL_GRAPH_GC,
    MCP_TOOL_COMMIT_PRUNE,
    MCP_TOOL_NODE_REGISTER,
];

fn map_xrpc_err((status, msg): (StatusCode, String)) -> (i32, String) {
    let code = match status {
        StatusCode::BAD_REQUEST => ERR_INVALID_PARAMS,
        StatusCode::UNAUTHORIZED | StatusCode::FORBIDDEN => ERR_AUTH,
        StatusCode::NOT_FOUND => ERR_NOT_FOUND,
        _ => ERR_INTERNAL,
    };
    (code, msg)
}

fn mcp_tx_cid(label: &str, parts: &[&str]) -> KotobaCid {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_nanos())
        .unwrap_or_default();
    KotobaCid::from_bytes(format!("mcp:{label}:{nanos}:{}", parts.join(":")).as_bytes())
}

async fn commit_mcp_datoms(
    state: &Arc<KotobaState>,
    graph_cid: KotobaCid,
    graph: String,
    entity_cid: KotobaCid,
    datoms: Vec<kotoba_query::Datom>,
    tx_cid: KotobaCid,
    caller: Option<&str>,
) -> Result<crate::xrpc::ProtocolDatomWriteResp, (i32, String)> {
    let datoms = datoms
        .into_iter()
        .map(kotoba_datomic::Datom::from_kqe)
        .collect();
    crate::xrpc::commit_protocol_datoms(
        state,
        graph_cid,
        graph,
        entity_cid,
        datoms,
        tx_cid,
        caller.unwrap_or(&state.operator_did).to_string(),
        kotoba_auth::CacaoPayload::OP_DATOM_TRANSACT,
        None,
        None,
    )
    .await
    .map_err(map_xrpc_err)
}

async fn current_graph_quads(
    state: &Arc<KotobaState>,
    graph_cid: &KotobaCid,
) -> Result<Vec<LegacyQuad>, (i32, String)> {
    let db = crate::xrpc::current_db_for_graph(state, graph_cid)
        .await
        .map_err(|(_, msg)| (ERR_INTERNAL, msg))?;
    Ok(db
        .datoms()
        .into_iter()
        .filter_map(|datom| {
            let substrate = datom.to_kqe().ok()?;
            Some(LegacyQuad {
                graph: graph_cid.clone(),
                subject: substrate.e,
                predicate: substrate.a,
                object: substrate.v.into(),
            })
        })
        .collect())
}

async fn current_graph_deltas(
    state: &Arc<KotobaState>,
    graph_cid: &KotobaCid,
) -> Result<Vec<Delta>, (i32, String)> {
    let db = crate::xrpc::current_db_for_graph(state, graph_cid)
        .await
        .map_err(|(_, msg)| (ERR_INTERNAL, msg))?;
    Ok(db
        .datoms()
        .into_iter()
        .filter_map(|datom| datom.to_kqe().ok())
        .map(Delta::from_datom)
        .collect())
}

async fn distributed_query_store(
    state: &Arc<KotobaState>,
    graph_cid: &KotobaCid,
) -> Result<QuadStore, (i32, String)> {
    let quads = current_graph_quads(state, graph_cid).await?;
    let query_store = QuadStore::new(Arc::new(LiveBus::new()), Arc::new(MemoryBlockStore::new()));
    query_store.assert_batch_silent(quads).await;
    Ok(query_store)
}

fn text_from_quads(quads: &[LegacyQuad], subject: &KotobaCid, predicate: &str) -> String {
    quads
        .iter()
        .find_map(|quad| {
            if &quad.subject == subject && quad.predicate == predicate {
                if let LegacyQuadObject::Text(text) = &quad.object {
                    return Some(text.clone());
                }
            }
            None
        })
        .unwrap_or_default()
}

fn optional_unique_visible_text_from_quads(
    quads: &[LegacyQuad],
    subject: &KotobaCid,
    predicate: &'static str,
) -> Result<Option<String>, (i32, String)> {
    let mut value = None;
    for quad in quads {
        if &quad.subject != subject || quad.predicate != predicate {
            continue;
        }
        let LegacyQuadObject::Text(text) = &quad.object else {
            return Err((ERR_INTERNAL, format!("invalid {predicate}")));
        };
        if text.is_empty() || text.bytes().any(|byte| !(0x21..=0x7e).contains(&byte)) {
            return Err((ERR_INTERNAL, format!("invalid {predicate}")));
        }
        match &value {
            Some(existing) if existing != text => {
                return Err((ERR_INTERNAL, format!("multiple {predicate} values found")));
            }
            Some(_) => {}
            None => value = Some(text.clone()),
        }
    }
    Ok(value)
}

fn unique_visible_bounded_text_from_quads(
    quads: &[LegacyQuad],
    subject: &KotobaCid,
    predicate: &'static str,
    max_len: usize,
) -> Result<String, (i32, String)> {
    let Some(value) = optional_unique_visible_text_from_quads(quads, subject, predicate)? else {
        return Err((ERR_NOT_FOUND, "email_cid not found in mailbox".to_string()));
    };
    if value.len() > max_len {
        return Err((ERR_INTERNAL, format!("invalid {predicate}")));
    }
    Ok(value)
}

fn latest_visible_bounded_text_from_quads(
    quads: &[LegacyQuad],
    subject: &KotobaCid,
    predicate: &'static str,
    max_len: usize,
) -> String {
    quads
        .iter()
        .filter_map(|quad| {
            if &quad.subject != subject || quad.predicate != predicate {
                return None;
            }
            let LegacyQuadObject::Text(text) = &quad.object else {
                return None;
            };
            if !text.is_empty()
                && text.len() <= max_len
                && text.bytes().all(|byte| (0x21..=0x7e).contains(&byte))
            {
                Some(text.clone())
            } else {
                None
            }
        })
        .max()
        .unwrap_or_default()
}

fn visible_bounded_text_from_quads(
    quads: &[LegacyQuad],
    subject: &KotobaCid,
    predicate: &'static str,
    max_len: usize,
) -> String {
    quads
        .iter()
        .find_map(|quad| {
            if &quad.subject != subject || quad.predicate != predicate {
                return None;
            }
            let LegacyQuadObject::Text(text) = &quad.object else {
                return None;
            };
            if !text.is_empty()
                && text.len() <= max_len
                && text.bytes().all(|byte| (0x21..=0x7e).contains(&byte))
            {
                Some(text.clone())
            } else {
                None
            }
        })
        .unwrap_or_default()
}

fn validate_legacy_read_text_output(
    field: &'static str,
    value: &str,
    max_len: usize,
) -> Result<(), String> {
    if value.len() > max_len {
        return Err(format!("{field} exceeds {max_len} bytes"));
    }
    if !value.is_empty() && value.bytes().any(|byte| !(0x21..=0x7e).contains(&byte)) {
        return Err(format!(
            "{field} must contain only visible ASCII characters"
        ));
    }
    Ok(())
}

async fn open_unique_legacy_text_field_from_quads(
    crypto: &dyn kotoba_crypto::AgentCrypto,
    quads: &[LegacyQuad],
    subject: &KotobaCid,
    predicate: &'static str,
    scope: &'static [u8],
    field: &'static str,
    max_len: usize,
) -> Result<String, (i32, String)> {
    let mut opened_value: Option<String> = None;
    for quad in quads {
        if &quad.subject != subject || quad.predicate != predicate {
            continue;
        }
        let LegacyQuadObject::Text(text) = &quad.object else {
            return Err((ERR_INTERNAL, format!("invalid {predicate}")));
        };
        let opened = if text.starts_with("signal:v1:") {
            crypto
                .open_field(scope, text)
                .await
                .map_err(|err| (ERR_INTERNAL, format!("decrypt {field}: {err}")))?
        } else {
            text.clone()
        };
        validate_legacy_read_text_output(field, &opened, max_len)
            .map_err(|err| (ERR_INTERNAL, err))?;
        match &opened_value {
            Some(existing) if existing != &opened => {
                return Err((ERR_INTERNAL, format!("multiple {predicate} values found")));
            }
            Some(_) => {}
            None => opened_value = Some(opened),
        }
    }
    Ok(opened_value.unwrap_or_default())
}

fn signal_enc_from_quads(quads: &[LegacyQuad], subject: &KotobaCid) -> Result<bool, (i32, String)> {
    let mut has_signal_enc = false;
    for quad in quads {
        if &quad.subject != subject || quad.predicate != "email/enc" {
            continue;
        }
        let LegacyQuadObject::Text(text) = &quad.object else {
            return Err((ERR_INTERNAL, "invalid email/enc".to_string()));
        };
        if text != ENC_SIGNAL_V1 {
            return Err((ERR_INTERNAL, "invalid email/enc".to_string()));
        }
        has_signal_enc = true;
    }
    Ok(has_signal_enc)
}

fn email_body_cid_from_quads(
    quads: &[LegacyQuad],
    subject: &KotobaCid,
) -> Result<String, (i32, String)> {
    let mut body_cid = None;
    for quad in quads {
        if &quad.subject != subject || quad.predicate != "email/body_cid" {
            continue;
        }
        let LegacyQuadObject::Text(text) = &quad.object else {
            return Err((ERR_INTERNAL, "invalid body_cid multibase".to_string()));
        };
        if KotobaCid::from_multibase(text).is_none() {
            return Err((ERR_INTERNAL, "invalid body_cid multibase".to_string()));
        }
        match &body_cid {
            Some(existing) if existing != text => {
                return Err((
                    ERR_INTERNAL,
                    "multiple email/body_cid values found".to_string(),
                ));
            }
            Some(_) => {}
            None => body_cid = Some(text.clone()),
        }
    }
    body_cid.ok_or_else(|| (ERR_NOT_FOUND, "email/body_cid not found".to_string()))
}

// ── Dispatch to state methods ────────────────────────────────────────────────

async fn call_tool(
    tool: &str,
    args: &Value,
    state: &Arc<KotobaState>,
    caller: Option<&str>,
) -> Result<Value, (i32, String)> {
    if ADMIN_ONLY_TOOLS.contains(&tool) {
        match caller {
            Some(sub) if sub == state.operator_did => {}
            Some(sub) => {
                tracing::warn!(tool, sub, "mcp: admin-only tool called by non-operator");
                return Err((
                    ERR_AUTH,
                    format!("tool {tool:?} requires operator credentials"),
                ));
            }
            None => {
                return Err((
                    ERR_AUTH,
                    format!("tool {tool:?} requires operator credentials"),
                ));
            }
        }
    }
    let get_str = |key: &str| -> Result<String, (i32, String)> {
        args.get(key)
            .and_then(Value::as_str)
            .map(str::to_owned)
            .ok_or_else(|| (ERR_INVALID_PARAMS, format!("missing required field: {key}")))
    };

    match tool {
        // ── kotoba_datom_create / legacy kotoba_quad_create ─────────────────
        MCP_TOOL_DATOM_CREATE | MCP_TOOL_QUAD_CREATE => {
            use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

            let graph = get_str("graph")?;
            let subject = get_str("subject")?;
            let predicate = get_str("predicate")?;
            let object = get_str("object")?;

            // Guard: reject oversized field values before any CID computation.
            // Malformed inputs with multi-MiB strings would bloat the block store.
            const MAX_FIELD_LEN: usize = 4096;
            if object.len() > MAX_FIELD_LEN {
                return Err((
                    ERR_INVALID_PARAMS,
                    format!(
                        "object too large ({} bytes, limit {MAX_FIELD_LEN})",
                        object.len()
                    ),
                ));
            }
            validate_mcp_text_field("predicate", &predicate, MAX_FIELD_LEN)?;

            let graph_cid = parse_mcp_cid_field("graph", &graph)?;
            let subject_cid = parse_mcp_cid_field("subject", &subject)?;
            let tx_cid = mcp_tx_cid("datom.create", &[&graph, &subject, &predicate, &object]);
            let datom = KqeDatom::assert(
                subject_cid.clone(),
                predicate,
                KqeValue::Text(object),
                tx_cid.clone(),
            );
            let resp = commit_mcp_datoms(
                state,
                graph_cid,
                graph,
                subject_cid,
                vec![datom],
                tx_cid,
                caller,
            )
            .await?;
            let journal_cid = resp.journal_cids.first().cloned().unwrap_or(resp.tx_cid);

            Ok(json!({
                "status": "ok",
                "journal_cid": journal_cid,
                "datom_cid": journal_cid,
                "quad_cid": journal_cid,
            }))
        }

        // ── kotoba_graph_query ───────────────────────────────────────────────
        MCP_TOOL_GRAPH_QUERY => {
            let graph = get_str("graph")?;
            let graph_cid = parse_mcp_cid_field("graph", &graph)?;

            const MAX_QUERY_RESULTS: usize = 1_000;
            const MAX_QUERY_FIELD_LEN: usize = 4096;
            let limit = args
                .get("limit")
                .and_then(Value::as_u64)
                .unwrap_or(MAX_QUERY_RESULTS as u64)
                .min(MAX_QUERY_RESULTS as u64) as usize;

            let predicate_prefix = args.get("predicate_prefix").and_then(Value::as_str);
            let predicate = args.get("predicate").and_then(Value::as_str);
            let object_key = args.get("object").and_then(Value::as_str);
            let subject_str = args.get("subject").and_then(Value::as_str);

            // Bound optional filter fields to prevent oversized BTree prefix scans.
            for (name, val) in [
                ("predicate_prefix", predicate_prefix),
                ("predicate", predicate),
                ("object", object_key),
            ] {
                if let Some(v) = val {
                    if v.len() > MAX_QUERY_FIELD_LEN {
                        return Err((
                            ERR_INVALID_PARAMS,
                            format!(
                                "field '{name}' too large ({} bytes, limit {MAX_QUERY_FIELD_LEN})",
                                v.len()
                            ),
                        ));
                    }
                }
            }
            if let Some(prefix) = predicate_prefix {
                validate_mcp_text_field("predicate_prefix", prefix, MAX_QUERY_FIELD_LEN)?;
            }
            if let Some(pred) = predicate {
                validate_mcp_text_field("predicate", pred, MAX_QUERY_FIELD_LEN)?;
            }

            let mut quads = current_graph_quads(state, &graph_cid).await?;
            let quads: Vec<_> = if let Some(prefix) = predicate_prefix {
                let mut q: Vec<_> = quads
                    .into_iter()
                    .filter(|quad| quad.predicate.starts_with(prefix))
                    .collect();
                q.truncate(limit);
                q
            } else if let (Some(pred), Some(obj)) = (predicate, object_key) {
                let mut q: Vec<_> = quads
                    .into_iter()
                    .filter(|quad| {
                        if quad.predicate != pred {
                            return false;
                        }
                        let value: kotoba_query::datom::Value = quad.object.clone().into();
                        datom_value_key(&value).as_deref() == Some(obj)
                    })
                    .collect();
                q.truncate(limit);
                q
            } else {
                if let Some(s) = subject_str {
                    let s_cid = parse_mcp_cid_field("subject", s)?;
                    quads.retain(|q| q.subject == s_cid);
                }
                if let Some(p) = predicate {
                    quads.retain(|q| q.predicate == p);
                }
                quads.truncate(limit);
                quads
            };

            Ok(json!({
                "graph": graph,
                "count": quads.len(),
                "quads": quads,
                "limit": limit,
            }))
        }

        // ── kotoba_infer_run ─────────────────────────────────────────────────
        MCP_TOOL_INFER_RUN => {
            let engine = state
                .inference_engine
                .clone()
                .ok_or_else(|| (ERR_INTERNAL, "no inference engine loaded".into()))?;

            let prompt = get_str("prompt")?;
            const MAX_PROMPT_LEN: usize = 64 * 1024;
            const MAX_NEW_TOKENS_LIMIT: u64 = 4096;
            if prompt.len() > MAX_PROMPT_LEN {
                return Err((
                    ERR_INVALID_PARAMS,
                    format!(
                        "prompt too large ({} bytes, limit {MAX_PROMPT_LEN})",
                        prompt.len()
                    ),
                ));
            }
            let max_tokens = args
                .get("max_new_tokens")
                .and_then(Value::as_u64)
                .unwrap_or(256)
                .min(MAX_NEW_TOKENS_LIMIT) as usize;

            let output = tokio::task::spawn_blocking(move || engine(&prompt, max_tokens))
                .await
                .map_err(|e| (ERR_INTERNAL, e.to_string()))?
                .map_err(|e| (ERR_INTERNAL, e.to_string()))?;

            Ok(json!({ "status": "ok", "output": output }))
        }

        // ── kotoba_embed_create ──────────────────────────────────────────────
        MCP_TOOL_EMBED_CREATE => {
            use kotoba_llm::embed::{embed_to_delta, Embedding};

            let text = get_str("text")?;
            let doc_cid = get_str("doc_cid")?;
            let model_cid = get_str("model_cid")?;
            let graph = get_str("graph")?;

            if text.is_empty() {
                return Err((ERR_INVALID_PARAMS, "text must not be empty".into()));
            }
            const MAX_EMBED_TEXT_LEN: usize = 64 * 1024;
            if text.len() > MAX_EMBED_TEXT_LEN {
                return Err((
                    ERR_INVALID_PARAMS,
                    format!(
                        "text too large ({} bytes, limit {MAX_EMBED_TEXT_LEN})",
                        text.len()
                    ),
                ));
            }

            let doc_cid = parse_mcp_cid_field("doc_cid", &doc_cid)?;
            let model_cid = parse_mcp_cid_field("model_cid", &model_cid)?;
            let graph_cid = parse_mcp_cid_field("graph", &graph)?;

            let vector: Vec<f32> = if let Some(engine) = &state.inference_engine {
                let engine = engine.clone();
                let t = format!("embed: {}", text);
                let result = tokio::task::spawn_blocking(move || engine(&t, 256))
                    .await
                    .map_err(|e| (ERR_INTERNAL, e.to_string()))?
                    .map_err(|e| (ERR_INTERNAL, e.to_string()))?;
                let parsed: Vec<f32> = result
                    .split_whitespace()
                    .filter_map(|s| s.parse().ok())
                    .collect();
                if parsed.is_empty() {
                    blake3_pseudo_vector(&text, 128)
                } else {
                    parsed
                }
            } else {
                blake3_pseudo_vector(&text, 128)
            };

            let dims = vector.len();
            let emb = Embedding {
                doc_cid: doc_cid.clone(),
                model_cid: model_cid.clone(),
                vector,
            };
            let tx_cid = mcp_tx_cid(
                "embed.create",
                &[
                    graph.as_str(),
                    &doc_cid.to_multibase(),
                    &model_cid.to_multibase(),
                ],
            );
            let datom = embed_to_delta(&emb, tx_cid.clone()).datom;
            let resp = commit_mcp_datoms(
                state,
                graph_cid,
                graph,
                doc_cid,
                vec![datom],
                tx_cid,
                caller,
            )
            .await?;
            let quad_cid = resp
                .journal_cids
                .first()
                .cloned()
                .unwrap_or_else(|| resp.tx_cid.clone());

            Ok(json!({ "status": "ok", "quad_cid": quad_cid, "tx_cid": resp.tx_cid, "dims": dims }))
        }

        // ── kotoba_weight_put ────────────────────────────────────────────────
        MCP_TOOL_WEIGHT_PUT => {
            use base64::{engine::general_purpose::STANDARD as B64, Engine as _};
            use kotoba_core::cid::KotobaCid;
            use kotoba_query::{Datom as KqeDatom, DatomTensorDtype, Value as KqeValue};

            let data_b64 = get_str("data_b64")?;
            let model_str = get_str("model_cid")?;
            let graph_str = get_str("graph")?;
            let dtype_str = get_str("dtype")?;
            let layer_u64 = args
                .get("layer")
                .and_then(Value::as_u64)
                .ok_or_else(|| (ERR_INVALID_PARAMS, "missing required field: layer".into()))?;
            let layer = u32::try_from(layer_u64).map_err(|_| {
                (
                    ERR_INVALID_PARAMS,
                    format!("layer {layer_u64} exceeds u32::MAX"),
                )
            })?;
            let shape: Vec<u32> = args
                .get("shape")
                .and_then(Value::as_array)
                .map(|a| {
                    a.iter()
                        .filter_map(|v| v.as_u64().and_then(|n| u32::try_from(n).ok()))
                        .collect()
                })
                .unwrap_or_default();

            const MAX_WEIGHT_B64_LEN: usize = 512 * 1024 * 1024;
            if data_b64.len() > MAX_WEIGHT_B64_LEN {
                return Err((
                    ERR_INVALID_PARAMS,
                    format!(
                        "data_b64 too large ({} bytes, limit {MAX_WEIGHT_B64_LEN})",
                        data_b64.len()
                    ),
                ));
            }
            let bytes = B64
                .decode(&data_b64)
                .map_err(|e| (ERR_INVALID_PARAMS, e.to_string()))?;

            let blob_cid = KotobaCid::from_bytes(&bytes);
            let model_cid = parse_mcp_cid_field("model_cid", &model_str)?;
            let graph_cid = parse_mcp_cid_field("graph", &graph_str)?;

            state
                .block_store
                .put(&blob_cid, &bytes)
                .map_err(|e| (ERR_INTERNAL, e.to_string()))?;

            let dtype = match dtype_str.as_str() {
                "fp8e4m3" | "f8e4m3" => DatomTensorDtype::F8E4M3,
                "fp8e5m2" | "f8e5m2" => DatomTensorDtype::F8E5M2,
                "fp16" | "f16" => DatomTensorDtype::F16,
                "bf16" => DatomTensorDtype::BF16,
                _ => DatomTensorDtype::F32,
            };

            let datom = KqeDatom::assert(
                model_cid.clone(),
                format!("weight/layer/{layer}"),
                KqeValue::TensorCid {
                    cid: blob_cid.clone(),
                    shape,
                    dtype,
                },
                mcp_tx_cid(
                    "weight.put",
                    &[
                        graph_str.as_str(),
                        &model_cid.to_multibase(),
                        &blob_cid.to_multibase(),
                    ],
                ),
            );
            let tx_cid = datom.tx.clone();
            let resp = commit_mcp_datoms(
                state,
                graph_cid,
                graph_str,
                blob_cid.clone(),
                vec![datom],
                tx_cid,
                caller,
            )
            .await?;
            let quad_cid = resp.journal_cids.first().cloned().unwrap_or(resp.tx_cid);

            Ok(json!({
                "status":   "ok",
                "blob_cid": blob_cid.to_multibase(),
                "quad_cid": quad_cid,
                "layer":    layer,
            }))
        }

        // ── kotoba_lora_apply ────────────────────────────────────────────────
        MCP_TOOL_LORA_APPLY => {
            use base64::{engine::general_purpose::STANDARD as B64, Engine as _};
            use kotoba_core::cid::KotobaCid;
            use kotoba_query::{Datom as KqeDatom, DatomTensorDtype, Value as KqeValue};

            let adapter_b64 = get_str("adapter_b64")?;
            let model_str = get_str("model_cid")?;
            let graph_str = get_str("graph")?;
            let rank_u64 = args
                .get("rank")
                .and_then(Value::as_u64)
                .ok_or_else(|| (ERR_INVALID_PARAMS, "missing required field: rank".into()))?;
            let rank = u32::try_from(rank_u64).map_err(|_| {
                (
                    ERR_INVALID_PARAMS,
                    format!("rank {rank_u64} exceeds u32::MAX"),
                )
            })?;

            const MAX_ADAPTER_B64_LEN: usize = 128 * 1024 * 1024;
            if adapter_b64.len() > MAX_ADAPTER_B64_LEN {
                return Err((
                    ERR_INVALID_PARAMS,
                    format!(
                        "adapter_b64 too large ({} bytes, limit {MAX_ADAPTER_B64_LEN})",
                        adapter_b64.len()
                    ),
                ));
            }
            let bytes = B64
                .decode(&adapter_b64)
                .map_err(|e| (ERR_INVALID_PARAMS, e.to_string()))?;

            let adapter_cid = KotobaCid::from_bytes(&bytes);
            let model_cid = parse_mcp_cid_field("model_cid", &model_str)?;
            let graph_cid = parse_mcp_cid_field("graph", &graph_str)?;

            state
                .block_store
                .put(&adapter_cid, &bytes)
                .map_err(|e| (ERR_INTERNAL, e.to_string()))?;

            let datom = KqeDatom::assert(
                model_cid.clone(),
                "lora/adapter".to_string(),
                KqeValue::TensorCid {
                    cid: adapter_cid.clone(),
                    shape: vec![rank],
                    dtype: DatomTensorDtype::F8E4M3,
                },
                mcp_tx_cid(
                    "lora.apply",
                    &[
                        graph_str.as_str(),
                        &model_cid.to_multibase(),
                        &adapter_cid.to_multibase(),
                    ],
                ),
            );
            let tx_cid = datom.tx.clone();
            let resp = commit_mcp_datoms(
                state,
                graph_cid,
                graph_str,
                adapter_cid.clone(),
                vec![datom],
                tx_cid,
                caller,
            )
            .await?;
            let quad_cid = resp.journal_cids.first().cloned().unwrap_or(resp.tx_cid);

            Ok(json!({
                "status":      "ok",
                "adapter_cid": adapter_cid.to_multibase(),
                "quad_cid":    quad_cid,
            }))
        }

        // ── kotoba_email_list ────────────────────────────────────────────────
        MCP_TOOL_EMAIL_LIST => {
            use kotoba_ingest::graph_cid_for;

            let owner_did = get_str("owner_did")?;
            crate::graph_auth::validate_did(&owner_did, "owner_did", MAX_OWNER_DID_LEN)
                .map_err(|(_, msg)| (ERR_INVALID_PARAMS, msg))?;
            let limit = email_list_limit_param(args)?;
            let offset = email_list_offset_param(args)?;

            let graph_cid = graph_cid_for(&owner_did);
            let quads = current_graph_quads(state, &graph_cid).await?;

            let entries = crate::email_xrpc::email_entries_from_quads(&quads);
            let total = entries.len();

            let mut emails: Vec<Value> = Vec::new();
            for (email_cid, date) in entries.into_iter().skip(offset).take(limit) {
                let cid_mb = email_cid.to_multibase();
                let message_id = text_from_quads(&quads, &email_cid, "email/message_id");
                let subject_enc = text_from_quads(&quads, &email_cid, "email/subject");
                let from_enc = text_from_quads(&quads, &email_cid, "email/from");
                let open_list_field =
                    |scope: &'static [u8], value: String, field: &'static str, max_len: usize| {
                        let crypto = state.crypto.as_ref().map(Arc::clone);
                        async move {
                            let opened = if value.starts_with("signal:v1:") {
                                let Some(crypto) = crypto else {
                                    return String::new();
                                };
                                match crypto.open_field(scope, &value).await {
                                    Ok(opened) => opened,
                                    Err(_) => return String::new(),
                                }
                            } else {
                                value
                            };
                            if validate_legacy_read_text_output(field, &opened, max_len).is_ok() {
                                opened
                            } else {
                                String::new()
                            }
                        }
                    };
                let subject = open_list_field(
                    b"email/subject",
                    subject_enc,
                    "subject",
                    MAX_LEGACY_SUBJECT_LEN,
                )
                .await;
                let from =
                    open_list_field(b"email/from", from_enc, "from", MAX_LEGACY_ADDR_LEN).await;

                let mut item = json!({
                    "cid": cid_mb,
                    "date": date,
                    "message_id": message_id,
                    "subject": subject,
                    "from": from,
                });
                let (enc, recipient_device) =
                    crate::email_xrpc::email_list_signal_metadata_from_quads(&quads, &email_cid);
                if let Some(enc) = enc {
                    item["enc"] = json!(enc);
                }
                if let Some(recipient_device) = recipient_device {
                    item["recipient_device"] = json!(recipient_device);
                }
                emails.push(item);
            }

            Ok(json!({ "emails": emails, "total": total, "offset": offset, "limit": limit }))
        }

        // ── kotoba_email_read ────────────────────────────────────────────────
        MCP_TOOL_EMAIL_READ => {
            use kotoba_ingest::graph_cid_for;

            let email_cid_str = get_str("email_cid")?;
            let owner_did = get_str("owner_did")?;
            crate::graph_auth::validate_did(&owner_did, "owner_did", MAX_OWNER_DID_LEN)
                .map_err(|(_, msg)| (ERR_INVALID_PARAMS, msg))?;
            let email_cid = validate_mcp_email_cid_param(&email_cid_str)?;
            let email_cid_mb = email_cid.to_multibase();

            let graph_cid = graph_cid_for(&owner_did);
            let quads = current_graph_quads(state, &graph_cid).await?;
            if quads.is_empty() {
                return Err((ERR_NOT_FOUND, "no emails found for owner_did".to_string()));
            }
            let message_id = unique_visible_bounded_text_from_quads(
                &quads,
                &email_cid,
                "email/message_id",
                MAX_EMAIL_MESSAGE_ID_LEN,
            )?;
            let date = latest_visible_bounded_text_from_quads(
                &quads,
                &email_cid,
                "email/date",
                MAX_EMAIL_DATE_LEN,
            );
            if date.is_empty() {
                return Err((ERR_NOT_FOUND, "email_cid not found in mailbox".to_string()));
            }

            let body_cid_str = email_body_cid_from_quads(&quads, &email_cid)?;
            let blob_cid = kotoba_core::cid::KotobaCid::from_multibase(&body_cid_str)
                .expect("validated body CID");
            if signal_enc_from_quads(&quads, &email_cid)? {
                let envelope_bytes = state.vault.get(&blob_cid).await.ok_or_else(|| {
                    (
                        ERR_NOT_FOUND,
                        "signal envelope not found in vault".to_string(),
                    )
                })?;
                let signal_message =
                    crate::email_xrpc::signal_message_value_from_envelope_bytes(&envelope_bytes)
                        .map_err(|err| (ERR_INTERNAL, err))?;
                let signal_from = signal_message["senderDid"]
                    .as_str()
                    .unwrap_or_default()
                    .to_string();
                let signal_to = signal_message["recipientDid"]
                    .as_str()
                    .unwrap_or_default()
                    .to_string();
                if signal_to != owner_did {
                    return Err((
                        ERR_INTERNAL,
                        "signal envelope recipientDid does not match mailbox owner_did".to_string(),
                    ));
                }
                let stored_signal_from =
                    optional_unique_visible_text_from_quads(&quads, &email_cid, "email/from")?;
                if stored_signal_from
                    .as_deref()
                    .is_some_and(|value| value != signal_from)
                {
                    return Err((
                        ERR_INTERNAL,
                        "signal envelope senderDid does not match email/from".to_string(),
                    ));
                }
                let stored_signal_to =
                    optional_unique_visible_text_from_quads(&quads, &email_cid, "email/to")?;
                if stored_signal_to
                    .as_deref()
                    .is_some_and(|value| value != signal_to)
                {
                    return Err((
                        ERR_INTERNAL,
                        "signal envelope recipientDid does not match email/to".to_string(),
                    ));
                }
                let signal_timestamp = signal_message["timestamp"].as_str().unwrap_or_default();
                if date != signal_timestamp {
                    return Err((
                        ERR_INTERNAL,
                        "signal envelope timestamp does not match email/date".to_string(),
                    ));
                }
                let expected_email_cid = crate::email_xrpc::signal_email_cid_for(
                    &signal_from,
                    &signal_to,
                    signal_timestamp,
                    &body_cid_str,
                );
                if expected_email_cid != email_cid {
                    return Err((
                        ERR_INTERNAL,
                        "signal envelope body_cid does not match email_cid".to_string(),
                    ));
                }
                return Ok(json!({
                    "email_cid":     email_cid_mb,
                    "enc":           ENC_SIGNAL_V1,
                    "message_id":    message_id,
                    "from":          signal_from,
                    "to":            signal_to,
                    "date":          signal_timestamp,
                    "thread_id":     visible_bounded_text_from_quads(&quads, &email_cid, "email/thread_id", MAX_THREAD_ID_LEN),
                    "signalMessage": signal_message,
                }));
            }

            let crypto = state
                .crypto
                .as_ref()
                .ok_or_else(|| (ERR_INTERNAL, "crypto not initialised".to_string()))?;

            // body_cid → Vault decrypt via AgentCrypto
            let enc_bytes = state
                .vault
                .get(&blob_cid)
                .await
                .ok_or_else(|| (ERR_NOT_FOUND, "body blob not found in vault".to_string()))?;
            let mut body_pt = crypto
                .decrypt_blob_bound(email_cid_mb.as_bytes(), &enc_bytes)
                .await
                .map_err(|e| (ERR_INTERNAL, format!("decrypt body: {e}")))?;
            let body = {
                let bytes = std::mem::take(&mut *body_pt);
                String::from_utf8(bytes)
                    .map_err(|err| (ERR_INTERNAL, format!("body is not valid UTF-8: {err}")))?
            };

            let from = open_unique_legacy_text_field_from_quads(
                &**crypto,
                &quads,
                &email_cid,
                "email/from",
                b"email/from",
                "from",
                MAX_LEGACY_ADDR_LEN,
            )
            .await?;
            let to = open_unique_legacy_text_field_from_quads(
                &**crypto,
                &quads,
                &email_cid,
                "email/to",
                b"email/to",
                "to",
                MAX_LEGACY_ADDR_LEN,
            )
            .await?;
            let subject = open_unique_legacy_text_field_from_quads(
                &**crypto,
                &quads,
                &email_cid,
                "email/subject",
                b"email/subject",
                "subject",
                MAX_LEGACY_SUBJECT_LEN,
            )
            .await?;

            Ok(json!({
                "email_cid":  email_cid_mb,
                "message_id": message_id,
                "from":       from,
                "to":         to,
                "subject":    subject,
                "date":       date,
                "thread_id":  visible_bounded_text_from_quads(&quads, &email_cid, "email/thread_id", MAX_THREAD_ID_LEN),
                "body":       body,
            }))
        }
        // ── kotoba_wasm_run ──────────────────────────────────────────────────
        #[cfg(feature = "wasm-runtime")]
        MCP_TOOL_WASM_RUN => {
            use base64::{engine::general_purpose::STANDARD as B64, Engine as _};
            use kotoba_vm::WasmPregelRunner;

            let wasm_b64 = get_str("wasm_b64")?;
            let agent_did = get_str("agent_did")?;
            crate::graph_auth::validate_did(&agent_did, "agent_did", 512)
                .map_err(|(_, msg)| (ERR_INVALID_PARAMS, msg))?;
            let ctx_b64 = get_str("ctx_cbor_b64")?;
            const MAX_SUPERSTEPS: u64 = 256;
            const MAX_WASM_B64_LEN: usize = 50 * 1024 * 1024;
            const MAX_CTX_B64_LEN: usize = 1024 * 1024;
            let max_ss = args
                .get("max_supersteps")
                .and_then(Value::as_u64)
                .unwrap_or(32)
                .min(MAX_SUPERSTEPS) as u32;

            if wasm_b64.len() > MAX_WASM_B64_LEN {
                return Err((
                    ERR_INVALID_PARAMS,
                    format!(
                        "wasm_b64 too large ({} bytes, limit {MAX_WASM_B64_LEN})",
                        wasm_b64.len()
                    ),
                ));
            }
            if ctx_b64.len() > MAX_CTX_B64_LEN {
                return Err((
                    ERR_INVALID_PARAMS,
                    format!(
                        "ctx_cbor_b64 too large ({} bytes, limit {MAX_CTX_B64_LEN})",
                        ctx_b64.len()
                    ),
                ));
            }
            let wasm_bytes = B64
                .decode(&wasm_b64)
                .map_err(|e| (ERR_INVALID_PARAMS, format!("invalid wasm_b64: {e}")))?;
            let ctx_cbor = B64
                .decode(&ctx_b64)
                .map_err(|e| (ERR_INVALID_PARAMS, format!("invalid ctx_cbor_b64: {e}")))?;

            let executor = Arc::clone(&state.executor);
            // program_cid MUST be the content-address of the wasm bytes so the
            // ProgramStore cache keys by what's actually being run.  Keying by
            // `did/wasm/{agent_did}` meant a second call with different wasm
            // for the same DID silently returned the previously compiled
            // Component (wrong module loaded, stale ProgramStore growth, and
            // a likely cause of the post-first-call OOM seen in production).
            let program_cid = kotoba_core::cid::KotobaCid::from_bytes(&wasm_bytes).to_multibase();

            let runner =
                WasmPregelRunner::new(executor, &program_cid, wasm_bytes, &agent_did, max_ss);

            // Run in blocking thread (wasmtime JIT is CPU-bound)
            let result = tokio::task::spawn_blocking(move || runner.run(ctx_cbor))
                .await
                .map_err(|e| (ERR_INTERNAL, e.to_string()))?
                .map_err(|e| (ERR_INTERNAL, format!("WasmPregelRunner: {e:?}")))?;

            // Write gas consumption Quad per agent DID + provider attribution
            {
                use kotoba_core::cid::KotobaCid;
                use kotoba_query::{Datom as KqeDatom, Value as KqeValue};
                let gas_graph = KotobaCid::from_bytes(b"kotoba/gas/ledger");
                let agent_cid = KotobaCid::from_bytes(agent_did.as_bytes());
                let tx_cid = mcp_tx_cid(
                    "wasm.gas",
                    &[agent_did.as_str(), &result.total_gas_used.to_string()],
                );
                // Safe cast: gas_limit is 10M per superstep and MAX_SUPERSTEPS is 256, so
                // total_gas_used can reach at most ~2.56B — well below i64::MAX (9.2e18).
                // Use try_from guard to prevent silent data corruption if limits ever change.
                let gas_i64 = i64::try_from(result.total_gas_used).unwrap_or(i64::MAX);
                let gas_datom = KqeDatom::assert(
                    agent_cid.clone(),
                    "gas/consumed_mkoto".to_string(),
                    KqeValue::Integer(gas_i64),
                    tx_cid.clone(),
                );

                // Provider attribution — identifies which compute node served this run
                let provider_datom = KqeDatom::assert(
                    agent_cid,
                    "gas/provider_did".to_string(),
                    KqeValue::Text(state.operator_did.clone()),
                    tx_cid.clone(),
                );
                commit_mcp_datoms(
                    state,
                    gas_graph.clone(),
                    gas_graph.to_multibase(),
                    gas_graph,
                    vec![gas_datom, provider_datom],
                    tx_cid,
                    caller,
                )
                .await?;
            }

            // Write WASM-asserted quads into the store (capped to prevent runaway writes).
            {
                use kotoba_core::cid::KotobaCid;
                use kotoba_query::{Datom as KqeDatom, Value as KqeValue};
                const MAX_ASSERT_QUADS: usize = 10_000;
                if result.assert_quads.len() > MAX_ASSERT_QUADS {
                    return Err((
                        ERR_INVALID_PARAMS,
                        format!(
                            "WASM produced {} assert quads (MCP limit {MAX_ASSERT_QUADS})",
                            result.assert_quads.len()
                        ),
                    ));
                }
                for sq in &result.assert_quads {
                    let graph_cid = parse_mcp_cid_field("assert_quads[].graph", &sq.graph)?;
                    let subject_cid = parse_mcp_cid_field("assert_quads[].subject", &sq.subject)?;
                    validate_mcp_text_field("assert_quads[].predicate", &sq.predicate, 4096)?;
                    let tx_cid =
                        mcp_tx_cid("wasm.assert", &[&sq.graph, &sq.subject, &sq.predicate]);
                    let datom = KqeDatom::assert(
                        subject_cid.clone(),
                        sq.predicate.clone(),
                        KqeValue::Bytes(sq.object_cbor.clone()),
                        tx_cid.clone(),
                    );
                    commit_mcp_datoms(
                        state,
                        graph_cid,
                        sq.graph.clone(),
                        subject_cid,
                        vec![datom],
                        tx_cid,
                        caller,
                    )
                    .await?;
                }
            }

            let output_b64 = B64.encode(&result.final_output_cbor);
            Ok(json!({
                "status":           "ok",
                "supersteps_run":   result.supersteps_run,
                "total_gas_used":   result.total_gas_used,
                "assert_quads":     result.assert_quads.len(),
                "output_cbor_b64":  output_b64,
            }))
        }
        #[cfg(not(feature = "wasm-runtime"))]
        MCP_TOOL_WASM_RUN => Err((
            ERR_INTERNAL,
            "kotoba_wasm_run requires the `wasm-runtime` feature".to_string(),
        )),

        // ── kotoba_datalog_run ───────────────────────────────────────────────
        MCP_TOOL_DATALOG_RUN => {
            use kotoba_core::cid::KotobaCid;
            use kotoba_query::{CitationLedger, DatalogProgram, DatalogRule};

            let graph_str = get_str("graph")?;
            let epoch_pool = args
                .get("epoch_pool_koto")
                .and_then(Value::as_u64)
                .unwrap_or(1_000_000); // default 1 KOTO

            // Deserialize rules array (cap prevents combinatorial-explosion DoS).
            const MAX_DATALOG_RULES: usize = 256;
            let rules: Vec<DatalogRule> = match args.get("rules") {
                Some(r) => serde_json::from_value(r.clone())
                    .map_err(|e| (ERR_INVALID_PARAMS, format!("invalid rules: {e}")))?,
                None => return Err((ERR_INVALID_PARAMS, "missing required field: rules".into())),
            };
            if rules.len() > MAX_DATALOG_RULES {
                return Err((
                    ERR_INVALID_PARAMS,
                    format!(
                        "rules array has {} items (limit {MAX_DATALOG_RULES})",
                        rules.len()
                    ),
                ));
            }
            // Limit body depth per rule — match_body recurses once per literal;
            // a 64-literal body can already cause exponential join fan-out.
            const MAX_BODY_LITERALS: usize = 16;
            for (i, rule) in rules.iter().enumerate() {
                if rule.body.len() > MAX_BODY_LITERALS {
                    return Err((
                        ERR_INVALID_PARAMS,
                        format!(
                            "rule[{i}] body has {} literals (limit {MAX_BODY_LITERALS})",
                            rule.body.len()
                        ),
                    ));
                }
            }

            let graph_cid = parse_mcp_cid_field("graph", &graph_str)?;
            let input_deltas = current_graph_deltas(state, &graph_cid).await?;

            let mut program = DatalogProgram::new();
            for rule in rules {
                program.add_rule(rule);
            }

            // Evaluate with citation tracking (CPU-bound in spawn_blocking)
            let (derived, ledger) = tokio::task::spawn_blocking(move || {
                let mut ledger = CitationLedger::new();
                let derived = program.evaluate_delta_cited(&input_deltas, &mut ledger);
                (derived, ledger)
            })
            .await
            .map_err(|e| (ERR_INTERNAL, e.to_string()))?;

            let citation_count = ledger.total_citations();
            let epoch = ledger.epoch();

            // Flush epoch → royalty Datoms → graph store
            let entries = {
                let mut l = ledger;
                l.flush_epoch(epoch_pool)
            };
            let royalty_datoms = CitationLedger::royalty_datoms(&entries, epoch);
            let royalty_count = royalty_datoms.len();
            let ledger_graph =
                KotobaCid::from_bytes(format!("kotoba/ledger/epoch/{epoch}").as_bytes());

            let ledger_tx_cid = mcp_tx_cid("datalog.ledger", &[&epoch.to_string()]);
            let mut ledger_datoms: Vec<_> = royalty_datoms
                .into_iter()
                .map(|mut datom| {
                    datom.tx = ledger_tx_cid.clone();
                    datom
                })
                .collect();

            // Pin provider attribution — identifies which pin node served this query
            {
                use kotoba_query::{Datom as KqeDatom, Value as KqeValue};
                let provider_cid = KotobaCid::from_bytes(state.operator_did.as_bytes());
                let provider_datom = KqeDatom::assert(
                    provider_cid,
                    "provider/did".to_string(),
                    KqeValue::Text(state.operator_did.clone()),
                    ledger_tx_cid.clone(),
                );
                ledger_datoms.push(provider_datom);
            }
            commit_mcp_datoms(
                state,
                ledger_graph.clone(),
                ledger_graph.to_multibase(),
                ledger_graph.clone(),
                ledger_datoms,
                ledger_tx_cid,
                caller,
            )
            .await?;

            // Write derived facts into the store
            let derived_count = derived.len();
            for d in &derived {
                let graph_cid = d.datom.tx.clone();
                let tx_cid = mcp_tx_cid(
                    "datalog.derived",
                    &[
                        &graph_cid.to_multibase(),
                        &d.datom.e.to_multibase(),
                        &d.datom.a,
                    ],
                );
                let mut datom = d.datom.clone();
                datom.tx = tx_cid.clone();
                commit_mcp_datoms(
                    state,
                    graph_cid.clone(),
                    graph_cid.to_multibase(),
                    datom.e.clone(),
                    vec![datom],
                    tx_cid,
                    caller,
                )
                .await?;
            }

            Ok(json!({
                "status":        "ok",
                "derived":       derived_count,
                "citations":     citation_count,
                "royalty_quads": royalty_count,
                "epoch":         epoch,
            }))
        }

        // ── kotoba_node_info ─────────────────────────────────────────────────
        MCP_TOOL_NODE_INFO => {
            use crate::server::NodeRole;
            let roles: Vec<&str> = state.node_roles.iter().map(NodeRole::as_str).collect();
            let node_id_hex = hex::encode(state.local_node_id.0);
            let peer_count = state.neighborhood.read().await.peers.len();
            Ok(json!({
                "did":          state.operator_did,
                "node_id_hex":  node_id_hex,
                "version":      state.version,
                "roles":        roles,
                "ephemeral":    state.is_ephemeral(),
                "peer_count":   peer_count,
            }))
        }

        // ── kotoba_node_register ─────────────────────────────────────────────
        MCP_TOOL_NODE_REGISTER => {
            state.register_node().await;
            Ok(json!({
                "status":       "ok",
                "operator_did": state.operator_did,
            }))
        }

        // ── kotoba_network_peers ─────────────────────────────────────────────
        MCP_TOOL_NETWORK_PEERS => {
            let nb = state.neighborhood.read().await;
            let local_hex = hex::encode(nb.local.0);
            let peers: Vec<Value> = nb
                .peers
                .iter()
                .map(|p| json!({ "node_id_hex": hex::encode(p.0) }))
                .collect();
            Ok(json!({
                "local_node_id_hex": local_hex,
                "peer_count":        peers.len(),
                "peers":             peers,
            }))
        }

        // ── kotoba_graph_gc ──────────────────────────────────────────────────
        MCP_TOOL_GRAPH_GC => {
            let deleted = state
                .quad_store
                .gc_dead_blocks()
                .await
                .map_err(|e| (ERR_INTERNAL, e.to_string()))?;
            Ok(json!({ "status": "ok", "deleted_blocks": deleted }))
        }

        // ── kotoba_commit_prune ──────────────────────────────────────────────
        MCP_TOOL_COMMIT_PRUNE => {
            let before_seq = args
                .get("before_seq")
                .and_then(Value::as_u64)
                .ok_or_else(|| {
                    (
                        ERR_INVALID_PARAMS,
                        "missing required field: before_seq".into(),
                    )
                })?;
            let pruned = state.quad_store.prune_old_commits(before_seq).await;
            let dag_size = state.quad_store.commit_dag_size().await;
            Ok(json!({ "status": "ok", "pruned_commits": pruned, "dag_size": dag_size }))
        }

        // ── kotoba_sparql_query ──────────────────────────────────────────────
        MCP_TOOL_SPARQL_QUERY => {
            use kotoba_auth::{Cacao, DelegationChain};

            let graph_str = get_str("graph")?;
            let sparql = get_str("sparql")?;
            if sparql.len() > 8 * 1024 {
                return Err((
                    ERR_INVALID_PARAMS,
                    "sparql query too large (limit 8KiB)".into(),
                ));
            }
            let graph_cid = parse_mcp_cid_field("graph", &graph_str)?;
            let query_store = distributed_query_store(state, &graph_cid).await?;

            let quads = if let Some(b64) = args.get("cacao_b64").and_then(Value::as_str) {
                if b64.len() > 8 * 1024 {
                    return Err((ERR_INVALID_PARAMS, "cacao_b64 too large".into()));
                }
                let cbor = decode_cacao_b64(b64)?;
                let cacao = Cacao::from_cbor(&cbor)
                    .map_err(|e| (ERR_INVALID_PARAMS, format!("CACAO parse error: {e}")))?;
                let chain = DelegationChain::new(cacao);
                query_store
                    .cold_query_sparql_bgp_authed(&graph_cid, &sparql, &chain)
                    .await
                    .map_err(|e| (ERR_AUTH, e.to_string()))?
            } else {
                query_store
                    .cold_query_sparql_bgp(&graph_cid, &sparql)
                    .await
                    .map_err(|e| (ERR_INTERNAL, e.to_string()))?
            };

            let result: Vec<Value> = quads
                .iter()
                .map(|q| {
                    json!({
                        "graph":     q.graph.to_multibase(),
                        "subject":   q.subject.to_multibase(),
                        "predicate": q.predicate,
                        "object":    format!("{:?}", q.object),
                    })
                })
                .collect();

            Ok(json!({ "count": result.len(), "quads": result }))
        }

        // ── kotoba_multi_hop ─────────────────────────────────────────────────
        MCP_TOOL_MULTI_HOP => {
            use kotoba_auth::{Cacao, DelegationChain};

            let graph_str = get_str("graph")?;
            let start_str = get_str("start")?;
            let max_hops = args
                .get("max_hops")
                .and_then(Value::as_u64)
                .unwrap_or(2)
                .min(8) as usize;

            let graph_cid = parse_mcp_cid_field("graph", &graph_str)?;
            let start_cid = parse_mcp_cid_field("start", &start_str)?;

            let hops = if let Some(b64) = args.get("cacao_b64").and_then(Value::as_str) {
                if b64.len() > 8 * 1024 {
                    return Err((ERR_INVALID_PARAMS, "cacao_b64 too large".into()));
                }
                let cbor = decode_cacao_b64(b64)?;
                let cacao = Cacao::from_cbor(&cbor)
                    .map_err(|e| (ERR_INVALID_PARAMS, format!("CACAO parse error: {e}")))?;
                let chain = DelegationChain::new(cacao);
                state
                    .quad_store
                    .multi_hop_cold_authed(&graph_cid, &start_cid, max_hops, &chain)
                    .await
                    .map_err(|e| (ERR_AUTH, e.to_string()))?
            } else {
                state
                    .quad_store
                    .multi_hop_cold(&graph_cid, &start_cid, max_hops)
                    .await
                    .map_err(|e| (ERR_INTERNAL, e.to_string()))?
            };

            let result: Vec<Value> = hops
                .iter()
                .map(|(depth, q)| {
                    json!({
                        "depth":     depth,
                        "graph":     q.graph.to_multibase(),
                        "subject":   q.subject.to_multibase(),
                        "predicate": q.predicate,
                        "object":    format!("{:?}", q.object),
                    })
                })
                .collect();

            Ok(json!({ "count": result.len(), "hops": result }))
        }

        other => Err((ERR_NOT_FOUND, format!("unknown tool: {other}"))),
    }
}

fn decode_cacao_b64(b64: &str) -> Result<Vec<u8>, (i32, String)> {
    use base64::{engine::general_purpose::STANDARD as B64, Engine as _};
    B64.decode(b64)
        .map_err(|e| (ERR_INVALID_PARAMS, format!("cacao_b64 decode error: {e}")))
}

fn blake3_pseudo_vector(text: &str, dims: usize) -> Vec<f32> {
    let hash = blake3::hash(text.as_bytes());
    let hash_bytes = hash.as_bytes();
    (0..dims)
        .map(|i| {
            let b = hash_bytes[i % 32] as f32;
            (b / 127.5) - 1.0
        })
        .collect()
}

// ── Axum handler ─────────────────────────────────────────────────────────────

/// POST /mcp  — JSON-RPC 2.0 MCP endpoint
pub async fn mcp_handler(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Json(req): Json<JsonRpcRequest>,
) -> impl IntoResponse {
    if req.jsonrpc != "2.0" {
        return Json(JsonRpcResponse::err(
            req.id,
            ERR_PARSE,
            "jsonrpc must be \"2.0\"",
        ));
    }

    // Auth gate for mutating methods
    if is_mutating(&req.method, None) && !check_auth(&headers) {
        return Json(JsonRpcResponse::err(
            req.id,
            ERR_AUTH,
            "tools/call requires Authorization: Bearer <AT-session-JWT>",
        ));
    }

    let result: Value = match req.method.as_str() {
        // ── Protocol methods ─────────────────────────────────────────────────
        "initialize" => json!({
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": { "listChanged": false },
                "resources": {},
                "prompts": {}
            },
            "serverInfo": {
                "name":    "kotoba",
                "version": state.version,
            }
        }),

        "ping" => json!({}),

        "tools/list" => tools_list(),

        "tools/call" => {
            let params = match &req.params {
                Some(p) => p,
                None => {
                    return Json(JsonRpcResponse::err(
                        req.id,
                        ERR_INVALID_PARAMS,
                        "params required for tools/call",
                    ))
                }
            };
            let tool_name = match params.get("name").and_then(Value::as_str) {
                Some(n) => n.to_owned(),
                None => {
                    return Json(JsonRpcResponse::err(
                        req.id,
                        ERR_INVALID_PARAMS,
                        "params.name required",
                    ))
                }
            };
            let args = params.get("arguments").cloned().unwrap_or(json!({}));
            let caller = caller_sub(&headers);

            match call_tool(&tool_name, &args, &state, caller.as_deref()).await {
                Ok(content) => json!({
                    "content": [{ "type": "text", "text": content.to_string() }],
                    "isError": false,
                }),
                Err((code, msg)) => return Json(JsonRpcResponse::err(req.id, code, msg)),
            }
        }

        other => {
            return Json(JsonRpcResponse::err(
                req.id,
                ERR_NOT_FOUND,
                format!("method not found: {other}"),
            ));
        }
    };

    Json(JsonRpcResponse::ok(req.id, result))
}

fn datom_value_key(value: &kotoba_query::datom::Value) -> Option<String> {
    match value {
        kotoba_query::datom::Value::Cid(c) => Some(c.to_multibase()),
        kotoba_query::datom::Value::Text(s) => Some(s.clone()),
        kotoba_query::datom::Value::Integer(n) => Some(n.to_string()),
        kotoba_query::datom::Value::Encrypted { ct_cid, .. } => {
            Some(format!("enc:{}", ct_cid.to_multibase()))
        }
        kotoba_query::datom::Value::Enveloped { ct_cid, .. } => {
            Some(format!("env:{}", ct_cid.to_multibase()))
        }
        _ => None,
    }
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn test_state() -> Arc<crate::server::KotobaState> {
        std::env::set_var("KOTOBA_IPFS", "off");
        Arc::new(crate::server::KotobaState::new(None).expect("state"))
    }

    fn test_text_quad(subject: KotobaCid, predicate: &'static str, text: String) -> LegacyQuad {
        LegacyQuad {
            graph: KotobaCid::from_bytes(b"mcp-test-graph"),
            subject,
            predicate: predicate.to_string(),
            object: LegacyQuadObject::Text(text),
        }
    }

    async fn commit_legacy_email_fixture_on_state(
        state: Arc<crate::server::KotobaState>,
        owner_did: &str,
        email_seed: &[u8],
        body: &[u8],
        tx_label: &str,
        extra_datoms: impl IntoIterator<Item = (&'static str, String)>,
    ) -> (KotobaCid, String) {
        use kotoba_ingest::graph_cid_for;
        use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

        let crypto = Arc::clone(state.crypto.as_ref().expect("crypto"));
        let graph_cid = graph_cid_for(owner_did);
        let graph = graph_cid.to_multibase();
        let email_cid = KotobaCid::from_bytes(email_seed);
        let email_cid_mb = email_cid.to_multibase();
        let encrypted_body = crypto
            .encrypt_blob_bound(email_cid_mb.as_bytes(), body)
            .await
            .expect("bound body ciphertext");
        let blob = state.vault.put(bytes::Bytes::from(encrypted_body)).await;
        let tx_cid = mcp_tx_cid(tx_label, &[owner_did]);
        let datoms = [
            ("email/message_id", email_cid_mb.clone()),
            ("email/body_cid", blob.cid.to_multibase()),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
        ]
        .into_iter()
        .chain(extra_datoms)
        .map(|(predicate, object)| {
            KqeDatom::assert(
                email_cid.clone(),
                predicate.to_string(),
                KqeValue::Text(object),
                tx_cid.clone(),
            )
        })
        .collect();
        commit_mcp_datoms(
            &state,
            graph_cid,
            graph,
            email_cid.clone(),
            datoms,
            tx_cid,
            None,
        )
        .await
        .unwrap();
        (email_cid, email_cid_mb)
    }

    async fn commit_legacy_email_fixture(
        owner_did: &str,
        email_seed: &[u8],
        body: &[u8],
        tx_label: &str,
        extra_datoms: impl IntoIterator<Item = (&'static str, String)>,
    ) -> (Arc<crate::server::KotobaState>, KotobaCid, String) {
        let state = Arc::new(
            crate::server::KotobaState::new(None)
                .expect("state")
                .init_crypto()
                .await
                .expect("crypto"),
        );
        let (email_cid, email_cid_mb) = commit_legacy_email_fixture_on_state(
            Arc::clone(&state),
            owner_did,
            email_seed,
            body,
            tx_label,
            extra_datoms,
        )
        .await;
        (state, email_cid, email_cid_mb)
    }

    #[test]
    fn email_body_cid_from_quads_allows_duplicate_identical_values() {
        let subject = KotobaCid::from_bytes(b"mcp-body-cid-duplicate-identical");
        let body_cid = KotobaCid::from_bytes(b"mcp-body-cid-same").to_multibase();
        let quads = vec![
            test_text_quad(subject.clone(), "email/body_cid", body_cid.clone()),
            test_text_quad(subject.clone(), "email/body_cid", body_cid.clone()),
        ];

        assert_eq!(
            email_body_cid_from_quads(&quads, &subject).unwrap(),
            body_cid
        );
    }

    #[test]
    fn signal_enc_from_quads_allows_duplicate_identical_signal_values() {
        let subject = KotobaCid::from_bytes(b"mcp-enc-duplicate-identical");
        let other_subject = KotobaCid::from_bytes(b"mcp-enc-other-subject");
        let quads = vec![
            test_text_quad(other_subject, "email/enc", "unknown:v1".to_string()),
            test_text_quad(subject.clone(), "email/enc", ENC_SIGNAL_V1.to_string()),
            test_text_quad(subject.clone(), "email/enc", ENC_SIGNAL_V1.to_string()),
        ];

        assert!(!signal_enc_from_quads(&[], &subject).unwrap());
        assert!(signal_enc_from_quads(&quads, &subject).unwrap());
    }

    #[test]
    fn signal_enc_from_quads_rejects_invalid_values_for_subject() {
        let subject = KotobaCid::from_bytes(b"mcp-enc-invalid-subject");
        let graph = KotobaCid::from_bytes(b"mcp-test-graph");
        let non_text_enc = LegacyQuad {
            graph,
            subject: subject.clone(),
            predicate: "email/enc".to_string(),
            object: LegacyQuadObject::Integer(1),
        };

        for quads in [
            vec![test_text_quad(
                subject.clone(),
                "email/enc",
                "unknown:v1".to_string(),
            )],
            vec![non_text_enc],
        ] {
            let err = signal_enc_from_quads(&quads, &subject).unwrap_err();
            assert_eq!(err.0, ERR_INTERNAL);
            assert!(err.1.contains("invalid email/enc"), "{err:?}");
        }
    }

    #[test]
    fn optional_unique_visible_text_from_quads_allows_missing_and_duplicate_identical_values() {
        let subject = KotobaCid::from_bytes(b"mcp-visible-text-duplicate-identical");
        let other_subject = KotobaCid::from_bytes(b"mcp-visible-text-other-subject");
        let quads = vec![
            test_text_quad(
                other_subject,
                "email/from",
                "other@example.test".to_string(),
            ),
            test_text_quad(
                subject.clone(),
                "email/from",
                "sender@example.test".to_string(),
            ),
            test_text_quad(
                subject.clone(),
                "email/from",
                "sender@example.test".to_string(),
            ),
        ];

        assert_eq!(
            optional_unique_visible_text_from_quads(&[], &subject, "email/from").unwrap(),
            None
        );
        assert_eq!(
            optional_unique_visible_text_from_quads(&quads, &subject, "email/from").unwrap(),
            Some("sender@example.test".to_string())
        );
    }

    #[test]
    fn optional_unique_visible_text_from_quads_rejects_invalid_or_conflicting_values() {
        let subject = KotobaCid::from_bytes(b"mcp-visible-text-invalid");
        let graph = KotobaCid::from_bytes(b"mcp-test-graph");
        let non_text_from = LegacyQuad {
            graph,
            subject: subject.clone(),
            predicate: "email/from".to_string(),
            object: LegacyQuadObject::Integer(1),
        };

        for (quads, expected) in [
            (
                vec![test_text_quad(subject.clone(), "email/from", String::new())],
                "invalid email/from",
            ),
            (
                vec![test_text_quad(
                    subject.clone(),
                    "email/from",
                    "bad\nsender".to_string(),
                )],
                "invalid email/from",
            ),
            (vec![non_text_from], "invalid email/from"),
            (
                vec![
                    test_text_quad(
                        subject.clone(),
                        "email/from",
                        "first@example.test".to_string(),
                    ),
                    test_text_quad(
                        subject.clone(),
                        "email/from",
                        "second@example.test".to_string(),
                    ),
                ],
                "multiple email/from values found",
            ),
        ] {
            let err = optional_unique_visible_text_from_quads(&quads, &subject, "email/from")
                .unwrap_err();
            assert_eq!(err.0, ERR_INTERNAL);
            assert!(err.1.contains(expected), "{err:?}");
        }
    }

    #[test]
    fn unique_visible_bounded_text_from_quads_enforces_presence_and_length() {
        let subject = KotobaCid::from_bytes(b"mcp-unique-visible-bounded");
        let max_len = 4;

        let missing =
            unique_visible_bounded_text_from_quads(&[], &subject, "email/message_id", max_len)
                .unwrap_err();
        assert_eq!(missing.0, ERR_NOT_FOUND);
        assert!(missing.1.contains("email_cid not found"), "{missing:?}");

        assert_eq!(
            unique_visible_bounded_text_from_quads(
                &[test_text_quad(
                    subject.clone(),
                    "email/message_id",
                    "abcd".to_string(),
                )],
                &subject,
                "email/message_id",
                max_len,
            )
            .unwrap(),
            "abcd"
        );

        let oversized = unique_visible_bounded_text_from_quads(
            &[test_text_quad(
                subject.clone(),
                "email/message_id",
                "abcde".to_string(),
            )],
            &subject,
            "email/message_id",
            max_len,
        )
        .unwrap_err();
        assert_eq!(oversized.0, ERR_INTERNAL);
        assert!(
            oversized.1.contains("invalid email/message_id"),
            "{oversized:?}"
        );
    }

    #[test]
    fn latest_visible_bounded_text_from_quads_ignores_invalid_values() {
        let subject = KotobaCid::from_bytes(b"mcp-latest-visible-bounded");
        let other_subject = KotobaCid::from_bytes(b"mcp-latest-visible-other");
        let max_len = MAX_EMAIL_DATE_LEN;
        let quads = vec![
            test_text_quad(
                other_subject,
                "email/date",
                "9999-12-31T00:00:00Z".to_string(),
            ),
            test_text_quad(subject.clone(), "email/date", String::new()),
            test_text_quad(
                subject.clone(),
                "email/date",
                "2026-06-01T00:00:00Z".to_string(),
            ),
            test_text_quad(
                subject.clone(),
                "email/date",
                "2026-06-03\n00:00:00Z".to_string(),
            ),
            test_text_quad(subject.clone(), "email/date", "x".repeat(max_len + 1)),
            test_text_quad(
                subject.clone(),
                "email/date",
                "2026-06-02T00:00:00Z".to_string(),
            ),
        ];

        assert_eq!(
            latest_visible_bounded_text_from_quads(&quads, &subject, "email/date", max_len),
            "2026-06-02T00:00:00Z"
        );
        assert_eq!(
            latest_visible_bounded_text_from_quads(&[], &subject, "email/date", max_len),
            ""
        );
    }

    #[test]
    fn visible_bounded_text_from_quads_returns_first_valid_value() {
        let subject = KotobaCid::from_bytes(b"mcp-visible-bounded");
        let other_subject = KotobaCid::from_bytes(b"mcp-visible-bounded-other");
        let max_len = 8;
        let quads = vec![
            test_text_quad(other_subject, "email/thread_id", "other".to_string()),
            test_text_quad(subject.clone(), "email/thread_id", String::new()),
            test_text_quad(subject.clone(), "email/thread_id", "bad\nid".to_string()),
            test_text_quad(subject.clone(), "email/thread_id", "x".repeat(max_len + 1)),
            test_text_quad(subject.clone(), "email/thread_id", "thread-1".to_string()),
            test_text_quad(subject.clone(), "email/thread_id", "thread-2".to_string()),
        ];

        assert_eq!(
            visible_bounded_text_from_quads(&quads, &subject, "email/thread_id", max_len),
            "thread-1"
        );
        assert_eq!(
            visible_bounded_text_from_quads(&[], &subject, "email/thread_id", max_len),
            ""
        );
    }

    #[test]
    fn parse_mcp_cid_field_accepts_cids_and_legacy_labels_with_bounds() {
        let cid = KotobaCid::from_bytes(b"mcp-cid-field");
        assert_eq!(
            parse_mcp_cid_field("cid", &format!("  {}  ", cid.to_multibase())).unwrap(),
            cid
        );
        assert_eq!(
            parse_mcp_cid_field("cid", "legacy-label").unwrap(),
            KotobaCid::from_bytes(b"legacy-label")
        );

        for value in ["", "   ", "bad\ncid"] {
            assert!(
                parse_mcp_cid_field("cid", value).is_err(),
                "CID-like field should be rejected: {value:?}"
            );
        }
        let oversized = "b".repeat(MAX_MCP_CID_FIELD_LEN + 1);
        assert!(parse_mcp_cid_field("cid", &oversized).is_err());
    }

    #[test]
    fn tools_list_contains_all() {
        let list = tools_list();
        let tools = list["tools"].as_array().expect("tools array");
        assert_eq!(tools.len(), 18);
        let names: Vec<&str> = tools.iter().map(|t| t["name"].as_str().unwrap()).collect();
        assert!(names.contains(&MCP_TOOL_DATOM_CREATE));
        assert!(names.contains(&MCP_TOOL_QUAD_CREATE));
        assert!(names.contains(&MCP_TOOL_GRAPH_QUERY));
        assert!(names.contains(&MCP_TOOL_INFER_RUN));
        assert!(names.contains(&MCP_TOOL_EMBED_CREATE));
        assert!(names.contains(&MCP_TOOL_WEIGHT_PUT));
        assert!(names.contains(&MCP_TOOL_LORA_APPLY));
        assert!(names.contains(&MCP_TOOL_EMAIL_LIST));
        assert!(names.contains(&MCP_TOOL_EMAIL_READ));
        assert!(names.contains(&MCP_TOOL_WASM_RUN));
        assert!(names.contains(&MCP_TOOL_DATALOG_RUN));
        assert!(names.contains(&MCP_TOOL_NODE_INFO));
        assert!(names.contains(&MCP_TOOL_NODE_REGISTER));
        assert!(names.contains(&MCP_TOOL_NETWORK_PEERS));
        assert!(names.contains(&MCP_TOOL_GRAPH_GC));
        assert!(names.contains(&MCP_TOOL_COMMIT_PRUNE));
        assert!(names.contains(&MCP_TOOL_SPARQL_QUERY));
        assert!(names.contains(&MCP_TOOL_MULTI_HOP));
    }

    #[test]
    fn tools_all_have_required_fields_in_schema() {
        let list = tools_list();
        for tool in list["tools"].as_array().unwrap() {
            let name = tool["name"].as_str().unwrap();
            assert!(
                tool.get("description").is_some(),
                "{name} missing description"
            );
            let schema = &tool["inputSchema"];
            assert_eq!(
                schema["type"], "object",
                "{name} inputSchema must be object"
            );
            assert!(
                schema.get("required").is_some(),
                "{name} missing required array"
            );
        }
    }

    #[test]
    fn email_list_tool_schema_matches_pagination_contract() {
        let list = tools_list();
        let tool = list["tools"]
            .as_array()
            .unwrap()
            .iter()
            .find(|tool| tool["name"] == MCP_TOOL_EMAIL_LIST)
            .expect("email list tool");
        let props = &tool["inputSchema"]["properties"];
        assert!(
            tool["description"].as_str().is_some_and(
                |description| description.contains("Signal metadata remains zero-access")
            ),
            "email.list description must disclose Signal zero-access behavior"
        );
        assert_eq!(props["owner_did"]["minLength"].as_u64(), Some(1));
        assert_eq!(
            props["owner_did"]["maxLength"].as_u64(),
            Some(MAX_OWNER_DID_LEN as u64)
        );
        assert_eq!(props["owner_did"]["pattern"].as_str(), Some("^did:[!-~]+$"));
        assert_eq!(props["limit"]["minimum"].as_u64(), Some(1));
        assert_eq!(
            props["limit"]["maximum"].as_u64(),
            Some(MAX_EMAIL_LIST_LIMIT as u64)
        );
        assert_eq!(props["offset"]["minimum"].as_u64(), Some(0));
        assert_eq!(
            props["offset"]["maximum"].as_u64(),
            Some(MAX_EMAIL_LIST_OFFSET as u64)
        );
    }

    #[test]
    fn email_read_tool_schema_matches_input_contract() {
        let list = tools_list();
        let tool = list["tools"]
            .as_array()
            .unwrap()
            .iter()
            .find(|tool| tool["name"] == MCP_TOOL_EMAIL_READ)
            .expect("email read tool");
        let props = &tool["inputSchema"]["properties"];
        let description = tool["description"].as_str().expect("description");
        assert!(
            description.contains("Legacy records decrypt")
                && description.contains("Signal records return signalMessage")
                && description.contains("do not expose a server-decrypted body"),
            "email.read description must disclose legacy-vs-Signal behavior: {description}"
        );
        assert_eq!(props["owner_did"]["minLength"].as_u64(), Some(1));
        assert_eq!(
            props["owner_did"]["maxLength"].as_u64(),
            Some(MAX_OWNER_DID_LEN as u64)
        );
        assert_eq!(props["owner_did"]["pattern"].as_str(), Some("^did:[!-~]+$"));
        assert_eq!(props["email_cid"]["minLength"].as_u64(), Some(1));
        assert_eq!(
            props["email_cid"]["maxLength"].as_u64(),
            Some(MAX_EMAIL_CID_LEN as u64)
        );
        assert!(
            props["email_cid"]["description"]
                .as_str()
                .is_some_and(|description| description.contains("visible ASCII")),
            "email_cid description must disclose visible-ASCII rejection"
        );
    }

    #[test]
    fn jsonrpc_response_ok_serializes_correctly() {
        let resp = JsonRpcResponse::ok(Some(Value::from(1)), json!({ "status": "ok" }));
        let s = serde_json::to_string(&resp).unwrap();
        assert!(s.contains("\"jsonrpc\":\"2.0\""));
        assert!(s.contains("\"result\""));
        assert!(!s.contains("\"error\""));
    }

    #[test]
    fn jsonrpc_response_err_omits_result() {
        let resp = JsonRpcResponse::err(Some(Value::from(1)), ERR_NOT_FOUND, "not found");
        let s = serde_json::to_string(&resp).unwrap();
        assert!(s.contains("\"error\""));
        assert!(!s.contains("\"result\""));
        assert_eq!(resp.error.unwrap().code, ERR_NOT_FOUND);
    }

    #[test]
    fn check_auth_requires_bearer() {
        let mut h = HeaderMap::new();
        assert!(!check_auth(&h));
        // Opaque (non-JWT) token — no exp to check, passes
        h.insert(
            axum::http::header::AUTHORIZATION,
            "Bearer tok123".parse().unwrap(),
        );
        assert!(check_auth(&h));
        let mut h2 = HeaderMap::new();
        h2.insert(
            axum::http::header::AUTHORIZATION,
            "Basic abc".parse().unwrap(),
        );
        assert!(!check_auth(&h2));
    }

    #[test]
    fn check_auth_rejects_expired_jwt() {
        use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine as _};
        let header = URL_SAFE_NO_PAD.encode(r#"{"alg":"HS256","typ":"JWT"}"#);
        let payload = URL_SAFE_NO_PAD.encode(r#"{"sub":"did:key:z6Mk","exp":1}"#); // exp=1 → 1970
        let expired_tok = format!("{header}.{payload}.fakesig");
        let mut h = HeaderMap::new();
        h.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {expired_tok}").parse().unwrap(),
        );
        assert!(
            !check_auth(&h),
            "expired JWT must be rejected by check_auth"
        );
    }

    #[test]
    fn check_auth_accepts_future_jwt() {
        use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine as _};
        let header = URL_SAFE_NO_PAD.encode(r#"{"alg":"HS256","typ":"JWT"}"#);
        let payload = URL_SAFE_NO_PAD.encode(r#"{"sub":"did:key:z6Mk","exp":9999999999}"#);
        let tok = format!("{header}.{payload}.fakesig");
        let mut h = HeaderMap::new();
        h.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {tok}").parse().unwrap(),
        );
        assert!(check_auth(&h), "future JWT must be accepted by check_auth");
    }

    #[test]
    fn is_mutating_tools_call_true() {
        assert!(is_mutating("tools/call", None));
        assert!(!is_mutating("tools/list", None));
        assert!(!is_mutating("initialize", None));
        assert!(!is_mutating("ping", None));
    }

    #[tokio::test]
    async fn call_tool_unknown_returns_not_found() {
        let state = test_state();
        let result = call_tool("nonexistent_tool", &json!({}), &state, None).await;
        let (code, _) = result.unwrap_err();
        assert_eq!(code, ERR_NOT_FOUND);
    }

    #[tokio::test]
    async fn call_tool_quad_create_ok() {
        let state = test_state();
        let result = call_tool(
            MCP_TOOL_QUAD_CREATE,
            &json!({
                "graph":     "graph1",
                "subject":   "alice",
                "predicate": "knows",
                "object":    "bob"
            }),
            &state,
            None,
        )
        .await;
        assert!(result.is_ok(), "{result:?}");
        let value = result.unwrap();
        assert_eq!(value["status"], "ok");
        assert!(value["datom_cid"].is_string());
        assert_eq!(value["datom_cid"], value["journal_cid"]);
        assert_eq!(value["quad_cid"], value["journal_cid"]);
    }

    #[tokio::test]
    async fn call_tool_datom_create_ok() {
        let state = test_state();
        let result = call_tool(
            MCP_TOOL_DATOM_CREATE,
            &json!({
                "graph":     "graph1",
                "subject":   "alice",
                "predicate": "knows",
                "object":    "bob"
            }),
            &state,
            None,
        )
        .await;
        assert!(result.is_ok(), "{result:?}");
        let value = result.unwrap();
        assert_eq!(value["status"], "ok");
        assert!(value["datom_cid"].is_string());
        assert_eq!(value["datom_cid"], value["journal_cid"]);
    }

    #[tokio::test]
    async fn call_tool_datom_create_commits_to_distributed_datomic_head() {
        let state = test_state();
        let graph = "mcp_distributed_graph";
        let subject = "mcp_subject";
        let predicate = "mcp/predicate";
        let object = "mcp object";
        call_tool(
            MCP_TOOL_DATOM_CREATE,
            &json!({
                "graph": graph,
                "subject": subject,
                "predicate": predicate,
                "object": object
            }),
            &state,
            Some("did:key:mcp-caller"),
        )
        .await
        .expect("mcp datom create");

        let graph_cid = KotobaCid::from_bytes(graph.as_bytes());
        let reader = kotoba_datomic::distributed::DistributedDatomReader::new(
            &*state.block_store,
            &*state.ipns_registry,
        );
        let history = reader
            .history_for_name(&crate::xrpc::distributed_graph_ipns_name(&graph_cid))
            .expect("distributed history");
        assert!(
            history.iter().any(|datom| {
                datom.e == KotobaCid::from_bytes(subject.as_bytes())
                    && datom.a == predicate
                    && datom.v == kotoba_edn::EdnValue::string(object)
                    && datom.added
            }),
            "MCP datom.create must write through the distributed Datomic/IPNS head"
        );
    }

    #[tokio::test]
    async fn call_tool_quad_create_missing_field_errors() {
        let state = test_state();
        let result = call_tool(
            MCP_TOOL_QUAD_CREATE,
            &json!({
                "graph": "g",
                "subject": "s"
                // predicate and object missing
            }),
            &state,
            None,
        )
        .await;
        let (code, _) = result.unwrap_err();
        assert_eq!(code, ERR_INVALID_PARAMS);
    }

    #[tokio::test]
    async fn call_tool_quad_create_oversized_field_errors() {
        let state = test_state();
        let big = "x".repeat(4097);
        let result = call_tool(
            MCP_TOOL_QUAD_CREATE,
            &json!({
                "graph":     "g",
                "subject":   big,
                "predicate": "p",
                "object":    "o"
            }),
            &state,
            None,
        )
        .await;
        let (code, msg) = result.unwrap_err();
        assert_eq!(code, ERR_INVALID_PARAMS);
        assert!(msg.contains("too large"), "expected 'too large' in: {msg}");
    }

    #[tokio::test]
    async fn call_tool_datom_create_rejects_unsafe_graph_subject_and_predicate() {
        let state = test_state();
        for (field, value) in [
            ("graph", "graph\n1"),
            ("subject", "subject\r1"),
            ("predicate", " \t "),
        ] {
            let mut args = json!({
                "graph":     "graph1",
                "subject":   "alice",
                "predicate": "knows",
                "object":    "bob"
            });
            args[field] = Value::String(value.to_string());
            let result = call_tool(MCP_TOOL_DATOM_CREATE, &args, &state, None).await;
            let (code, msg) = result.unwrap_err();
            assert_eq!(code, ERR_INVALID_PARAMS);
            assert!(msg.contains(field), "{msg}");
        }
    }

    #[tokio::test]
    async fn call_tool_graph_query_empty_graph() {
        let state = test_state();
        let result = call_tool(
            MCP_TOOL_GRAPH_QUERY,
            &json!({
                "graph": "nonexistent_graph_xyz"
            }),
            &state,
            None,
        )
        .await;
        assert!(result.is_ok());
        let v = result.unwrap();
        assert_eq!(v["count"], 0);
    }

    #[tokio::test]
    async fn call_tool_graph_query_rejects_unsafe_filters() {
        let state = test_state();
        for (field, value) in [
            ("graph", "graph\n1"),
            ("subject", "subject\n1"),
            ("predicate", "predicate\n1"),
            ("predicate_prefix", "prefix\n"),
        ] {
            let mut args = json!({
                "graph": "graph1"
            });
            args[field] = Value::String(value.to_string());
            let result = call_tool(MCP_TOOL_GRAPH_QUERY, &args, &state, None).await;
            let (code, msg) = result.unwrap_err();
            assert_eq!(code, ERR_INVALID_PARAMS);
            assert!(msg.contains(field), "{msg}");
        }
    }

    #[tokio::test]
    async fn graph_query_avet_predicate_prefix_returns_matching_quads() {
        let state = test_state();
        // Seed two quads with predicate "weight/layer/0" and one with "other"
        for (pred, obj) in [
            ("weight/layer/0", "val0"),
            ("weight/layer/1", "val1"),
            ("other", "x"),
        ] {
            call_tool(
                MCP_TOOL_QUAD_CREATE,
                &json!({
                    "graph": "g", "subject": "model", "predicate": pred, "object": obj
                }),
                &state,
                None,
            )
            .await
            .unwrap();
        }
        // AVET prefix scan should return only the two weight quads
        let v = call_tool(
            MCP_TOOL_GRAPH_QUERY,
            &json!({
                "graph": "g",
                "predicate_prefix": "weight/"
            }),
            &state,
            None,
        )
        .await
        .unwrap();
        assert_eq!(
            v["count"], 2,
            "prefix scan should return 2 weight quads, got {v}"
        );
    }

    #[tokio::test]
    async fn graph_query_avet_predicate_object_returns_subjects() {
        let state = test_state();
        // Seed: alice knows bob, carol knows bob, dave knows eve
        for (s, o) in [("alice", "bob"), ("carol", "bob"), ("dave", "eve")] {
            call_tool(
                MCP_TOOL_QUAD_CREATE,
                &json!({
                    "graph": "g2", "subject": s, "predicate": "knows", "object": o
                }),
                &state,
                None,
            )
            .await
            .unwrap();
        }
        // AVET P+O→S: who knows bob?
        let v = call_tool(
            MCP_TOOL_GRAPH_QUERY,
            &json!({
                "graph": "g2",
                "predicate": "knows",
                "object": "bob"
            }),
            &state,
            None,
        )
        .await
        .unwrap();
        assert_eq!(v["count"], 2, "should find alice and carol, got {v}");
    }

    #[tokio::test]
    async fn admin_tools_reject_non_operator() {
        let state = test_state();
        // Any DID other than operator_did must be rejected with ERR_AUTH.
        for tool in ADMIN_ONLY_TOOLS {
            let args = if *tool == MCP_TOOL_COMMIT_PRUNE {
                json!({ "before_seq": 0 })
            } else {
                json!({})
            };
            let err = call_tool(tool, &args, &state, Some("did:key:zNotTheOperator"))
                .await
                .expect_err(&format!("{tool} should reject non-operator"));
            assert_eq!(err.0, ERR_AUTH, "{tool}: expected ERR_AUTH, got {err:?}");

            let err_none = call_tool(tool, &args, &state, None)
                .await
                .expect_err(&format!("{tool} should reject missing caller"));
            assert_eq!(
                err_none.0, ERR_AUTH,
                "{tool}: no-caller should give ERR_AUTH"
            );
        }
    }

    #[tokio::test]
    async fn graph_gc_returns_ok_with_deleted_count() {
        let state = test_state();
        // Fresh store has no committed blocks — GC should delete 0 and succeed.
        let v = call_tool(
            MCP_TOOL_GRAPH_GC,
            &json!({}),
            &state,
            Some(state.operator_did.as_str()),
        )
        .await
        .unwrap();
        assert_eq!(v["status"], "ok");
        assert!(
            v["deleted_blocks"].as_u64().is_some(),
            "deleted_blocks must be a number"
        );
    }

    #[tokio::test]
    async fn commit_prune_returns_ok_with_counts() {
        let state = test_state();
        // Fresh store — no commits yet; prune with before_seq=0 removes nothing.
        let v = call_tool(
            MCP_TOOL_COMMIT_PRUNE,
            &json!({ "before_seq": 0 }),
            &state,
            Some(state.operator_did.as_str()),
        )
        .await
        .unwrap();
        assert_eq!(v["status"], "ok");
        assert_eq!(v["pruned_commits"].as_u64().unwrap(), 0);
        assert!(
            v["dag_size"].as_u64().is_some(),
            "dag_size must be a number"
        );
    }

    #[tokio::test]
    async fn commit_prune_missing_before_seq_errors() {
        let state = test_state();
        let result = call_tool(
            MCP_TOOL_COMMIT_PRUNE,
            &json!({}),
            &state,
            Some(state.operator_did.as_str()),
        )
        .await;
        let (code, _) = result.unwrap_err();
        assert_eq!(code, ERR_INVALID_PARAMS);
    }

    // ── kotoba_embed_create ──────────────────────────────────────────────────

    #[tokio::test]
    async fn call_tool_embed_create_ok_blake3_fallback() {
        let state = test_state();
        let result = call_tool(
            MCP_TOOL_EMBED_CREATE,
            &json!({
                "text":      "hello kotoba",
                "doc_cid":   "doc1",
                "model_cid": "model1",
                "graph":     "graph1"
            }),
            &state,
            None,
        )
        .await;
        assert!(result.is_ok(), "{result:?}");
        let v = result.unwrap();
        assert_eq!(v["status"], "ok");
        assert!(v["dims"].as_u64().unwrap_or(0) > 0, "dims must be > 0");
        assert!(v["quad_cid"].is_string(), "quad_cid must be a string");

        let graph_cid = KotobaCid::from_bytes(b"graph1");
        let doc_cid = KotobaCid::from_bytes(b"doc1");
        let model_cid = KotobaCid::from_bytes(b"model1");
        let tx_cid =
            KotobaCid::from_multibase(v["tx_cid"].as_str().expect("tx_cid string")).unwrap();
        let reader = kotoba_datomic::distributed::DistributedDatomReader::new(
            &*state.block_store,
            &*state.ipns_registry,
        );
        let tea_datoms = reader
            .history_datoms_index(
                &reader
                    .resolve_head(&crate::xrpc::distributed_graph_ipns_name(&graph_cid))
                    .expect("resolve distributed embed head")
                    .expect("distributed embed head")
                    .cid,
                kotoba_datomic::DatomIndex::Tea,
                &[kotoba_edn::EdnValue::string(tx_cid.to_multibase())],
            )
            .expect("embedding datoms by tx");
        assert!(
            tea_datoms.iter().any(|datom| {
                datom.e == doc_cid
                    && datom.a == format!("embedding/{}", model_cid.to_multibase())
                    && datom.t == tx_cid
                    && datom.added
            }),
            "embed.create must write embedding datoms with Datomic T equal to the tx CID"
        );
    }

    #[tokio::test]
    async fn call_tool_embed_create_empty_text_errors() {
        let state = test_state();
        let result = call_tool(
            MCP_TOOL_EMBED_CREATE,
            &json!({
                "text":      "",
                "doc_cid":   "doc1",
                "model_cid": "model1",
                "graph":     "graph1"
            }),
            &state,
            None,
        )
        .await;
        let (code, msg) = result.unwrap_err();
        assert_eq!(code, ERR_INVALID_PARAMS);
        assert!(msg.contains("empty"), "expected 'empty' in: {msg}");
    }

    #[tokio::test]
    async fn call_tool_embed_create_missing_text_errors() {
        let state = test_state();
        let result = call_tool(
            MCP_TOOL_EMBED_CREATE,
            &json!({
                "doc_cid":   "doc1",
                "model_cid": "model1",
                "graph":     "graph1"
            }),
            &state,
            None,
        )
        .await;
        let (code, _) = result.unwrap_err();
        assert_eq!(code, ERR_INVALID_PARAMS);
    }

    #[tokio::test]
    async fn call_tool_embed_create_rejects_unsafe_cid_fields() {
        let state = test_state();
        let result = call_tool(
            MCP_TOOL_EMBED_CREATE,
            &json!({
                "text":      "hello",
                "doc_cid":   "doc\n1",
                "model_cid": "model1",
                "graph":     "graph1"
            }),
            &state,
            None,
        )
        .await;
        let (code, msg) = result.unwrap_err();
        assert_eq!(code, ERR_INVALID_PARAMS);
        assert!(msg.contains("doc_cid"), "{msg}");
    }

    // ── kotoba_infer_run ─────────────────────────────────────────────────────

    #[tokio::test]
    async fn call_tool_infer_run_without_engine_returns_error() {
        let state = test_state();
        // No inference engine loaded → must fail
        let result = call_tool(
            MCP_TOOL_INFER_RUN,
            &json!({
                "prompt": "hello"
            }),
            &state,
            None,
        )
        .await;
        assert!(result.is_err(), "expected error when no engine");
        let (code, msg) = result.unwrap_err();
        assert_eq!(code, ERR_INTERNAL);
        assert!(
            msg.contains("inference engine"),
            "expected 'inference engine' in: {msg}"
        );
    }

    #[tokio::test]
    async fn call_tool_infer_run_missing_prompt_errors() {
        let state = test_state();
        // Engine check precedes prompt validation — either ERR_INTERNAL (no engine)
        // or ERR_INVALID_PARAMS (missing prompt) are both acceptable errors.
        let result = call_tool(MCP_TOOL_INFER_RUN, &json!({}), &state, None).await;
        assert!(result.is_err(), "expected error for missing prompt");
    }

    // ── kotoba_node_info ─────────────────────────────────────────────────────

    #[tokio::test]
    async fn call_tool_node_info_returns_node_fields() {
        let state = test_state();
        let result = call_tool(MCP_TOOL_NODE_INFO, &json!({}), &state, None).await;
        assert!(result.is_ok(), "{result:?}");
        let v = result.unwrap();
        assert!(v["did"].is_string(), "did must be a string");
        assert!(v["node_id_hex"].is_string(), "node_id_hex must be a string");
        assert!(v["version"].is_string(), "version must be a string");
        assert!(v["roles"].is_array(), "roles must be an array");
        assert!(
            v["peer_count"].as_u64().is_some(),
            "peer_count must be a number"
        );
    }

    // ── kotoba_node_register ─────────────────────────────────────────────────

    #[tokio::test]
    async fn call_tool_node_register_returns_ok() {
        let state = test_state();
        let result = call_tool(
            MCP_TOOL_NODE_REGISTER,
            &json!({}),
            &state,
            Some(state.operator_did.as_str()),
        )
        .await;
        assert!(result.is_ok(), "{result:?}");
        let v = result.unwrap();
        assert_eq!(v["status"], "ok");
        assert!(
            v["operator_did"].is_string(),
            "operator_did must be a string"
        );
    }

    // ── kotoba_network_peers ─────────────────────────────────────────────────

    #[tokio::test]
    async fn call_tool_network_peers_returns_peer_list() {
        let state = test_state();
        let result = call_tool(MCP_TOOL_NETWORK_PEERS, &json!({}), &state, None).await;
        assert!(result.is_ok(), "{result:?}");
        let v = result.unwrap();
        assert!(
            v["local_node_id_hex"].is_string(),
            "local_node_id_hex must be a string"
        );
        assert!(
            v["peer_count"].as_u64().is_some(),
            "peer_count must be a number"
        );
        assert!(v["peers"].is_array(), "peers must be an array");
        // Fresh state has no peers
        assert_eq!(v["peer_count"].as_u64().unwrap(), 0);
    }

    // ── kotoba_wasm_run ──────────────────────────────────────────────────────

    #[cfg(feature = "wasm-runtime")]
    #[tokio::test]
    async fn call_tool_wasm_run_missing_wasm_b64_errors() {
        let state = test_state();
        let result = call_tool(
            MCP_TOOL_WASM_RUN,
            &json!({
                "agent_did":    "did:plc:test",
                "ctx_cbor_b64": ""
            }),
            &state,
            None,
        )
        .await;
        let (code, _) = result.unwrap_err();
        assert_eq!(code, ERR_INVALID_PARAMS);
    }

    #[cfg(feature = "wasm-runtime")]
    #[tokio::test]
    async fn call_tool_wasm_run_invalid_base64_errors() {
        let state = test_state();
        let result = call_tool(
            MCP_TOOL_WASM_RUN,
            &json!({
                "wasm_b64":     "not-valid-base64!!!",
                "agent_did":    "did:plc:test",
                "ctx_cbor_b64": "AA=="
            }),
            &state,
            None,
        )
        .await;
        let (code, msg) = result.unwrap_err();
        assert_eq!(code, ERR_INVALID_PARAMS);
        assert!(msg.contains("wasm_b64"), "expected 'wasm_b64' in: {msg}");
    }

    #[cfg(not(feature = "wasm-runtime"))]
    #[tokio::test]
    async fn call_tool_wasm_run_requires_feature_when_disabled() {
        let state = test_state();
        let result = call_tool(
            MCP_TOOL_WASM_RUN,
            &json!({
                "wasm_b64":     "",
                "agent_did":    "did:plc:test",
                "ctx_cbor_b64": ""
            }),
            &state,
            None,
        )
        .await;
        let (code, msg) = result.unwrap_err();
        assert_eq!(code, ERR_INTERNAL);
        assert!(msg.contains("wasm-runtime"), "{msg}");
    }

    #[test]
    fn total_gas_used_u64_to_i64_cast_is_safe_within_limits() {
        // gas_limit = 10_000_000 per WasmExecutor, MAX_SUPERSTEPS = 256
        let max_possible: u64 = 10_000_000 * 256;
        assert!(
            max_possible <= i64::MAX as u64,
            "total_gas_used cannot exceed i64::MAX at current limits"
        );
        // The try_from guard preserves correctness if limits ever change.
        assert_eq!(i64::try_from(max_possible).unwrap(), max_possible as i64);
        // Saturate to i64::MAX for absurdly large values (defense-in-depth).
        assert_eq!(i64::try_from(u64::MAX).unwrap_or(i64::MAX), i64::MAX);
    }

    // ── kotoba_datalog_run ───────────────────────────────────────────────────

    #[tokio::test]
    async fn call_tool_datalog_run_missing_rules_errors() {
        let state = test_state();
        let result = call_tool(
            MCP_TOOL_DATALOG_RUN,
            &json!({
                "graph": "test_graph"
            }),
            &state,
            None,
        )
        .await;
        let (code, msg) = result.unwrap_err();
        assert_eq!(code, ERR_INVALID_PARAMS);
        assert!(msg.contains("rules"), "expected 'rules' in: {msg}");
    }

    #[tokio::test]
    async fn call_tool_datalog_run_empty_graph_returns_empty_derived() {
        let state = test_state();
        // Empty graph with no rules — should succeed with 0 derived facts
        let result = call_tool(
            MCP_TOOL_DATALOG_RUN,
            &json!({
                "graph": "nonexistent_graph_for_datalog_test",
                "rules": []
            }),
            &state,
            None,
        )
        .await;
        assert!(result.is_ok(), "{result:?}");
        let v = result.unwrap();
        assert_eq!(v["derived"], json!(0));
        assert_eq!(v["citations"].as_u64().unwrap_or(1), 0);
    }

    // ── kotoba_weight_put ────────────────────────────────────────────────────

    #[tokio::test]
    async fn call_tool_weight_put_missing_layer_errors() {
        let state = test_state();
        use base64::{engine::general_purpose::STANDARD as B64, Engine as _};
        let data = B64.encode(b"fake-weight-data");
        let result = call_tool(
            MCP_TOOL_WEIGHT_PUT,
            &json!({
                "data_b64":  data,
                "model_cid": "model1",
                "graph":     "graph1",
                "dtype":     "fp16"
                // layer missing
            }),
            &state,
            None,
        )
        .await;
        let (code, msg) = result.unwrap_err();
        assert_eq!(code, ERR_INVALID_PARAMS);
        assert!(msg.contains("layer"), "expected 'layer' in: {msg}");
    }

    #[tokio::test]
    async fn call_tool_weight_put_ok() {
        let state = test_state();
        use base64::{engine::general_purpose::STANDARD as B64, Engine as _};
        let data = B64.encode(b"fake-weight-bytes");
        let result = call_tool(
            MCP_TOOL_WEIGHT_PUT,
            &json!({
                "data_b64":  data,
                "model_cid": "model1",
                "graph":     "graph1",
                "dtype":     "bf16",
                "layer":     0
            }),
            &state,
            None,
        )
        .await;
        assert!(result.is_ok(), "{result:?}");
        let v = result.unwrap();
        assert_eq!(v["status"], "ok");
        assert_eq!(v["layer"].as_u64().unwrap(), 0);
        assert!(v["blob_cid"].is_string());
        assert!(v["quad_cid"].is_string());
    }

    // ── kotoba_lora_apply ────────────────────────────────────────────────────

    #[tokio::test]
    async fn call_tool_lora_apply_missing_rank_errors() {
        let state = test_state();
        use base64::{engine::general_purpose::STANDARD as B64, Engine as _};
        let adapter = B64.encode(b"fake-lora-adapter");
        let result = call_tool(
            MCP_TOOL_LORA_APPLY,
            &json!({
                "adapter_b64": adapter,
                "model_cid":   "model1",
                "graph":       "graph1"
                // rank missing
            }),
            &state,
            None,
        )
        .await;
        let (code, msg) = result.unwrap_err();
        assert_eq!(code, ERR_INVALID_PARAMS);
        assert!(msg.contains("rank"), "expected 'rank' in: {msg}");
    }

    #[tokio::test]
    async fn call_tool_lora_apply_ok() {
        let state = test_state();
        use base64::{engine::general_purpose::STANDARD as B64, Engine as _};
        let adapter = B64.encode(b"fake-lora-adapter-bytes");
        let result = call_tool(
            MCP_TOOL_LORA_APPLY,
            &json!({
                "adapter_b64": adapter,
                "model_cid":   "model1",
                "graph":       "graph1",
                "rank":        8
            }),
            &state,
            None,
        )
        .await;
        assert!(result.is_ok(), "{result:?}");
        let v = result.unwrap();
        assert_eq!(v["status"], "ok");
        assert!(v["adapter_cid"].is_string());
        assert!(v["quad_cid"].is_string());
    }

    // ── u64→u32 truncation guards ────────────────────────────────────────────

    #[tokio::test]
    async fn weight_store_layer_overflow_u32_is_rejected() {
        let state = test_state();
        use base64::{engine::general_purpose::STANDARD as B64, Engine as _};
        let data = B64.encode(b"fake-weight-bytes");
        let overflow_layer: u64 = u32::MAX as u64 + 1;
        let result = call_tool(
            MCP_TOOL_WEIGHT_PUT,
            &json!({
                "data_b64":  data,
                "model_cid": "model1",
                "graph":     "graph1",
                "dtype":     "f32",
                "layer":     overflow_layer,
                "shape":     [4, 4]
            }),
            &state,
            None,
        )
        .await;
        let (code, msg) = result.unwrap_err();
        assert_eq!(
            code, ERR_INVALID_PARAMS,
            "overflow layer must return INVALID_PARAMS"
        );
        assert!(
            msg.contains("u32"),
            "error must mention u32 boundary, got: {msg}"
        );
    }

    #[tokio::test]
    async fn lora_apply_rank_overflow_u32_is_rejected() {
        let state = test_state();
        use base64::{engine::general_purpose::STANDARD as B64, Engine as _};
        let adapter = B64.encode(b"fake-lora");
        let overflow_rank: u64 = u32::MAX as u64 + 1;
        let result = call_tool(
            MCP_TOOL_LORA_APPLY,
            &json!({
                "adapter_b64": adapter,
                "model_cid":   "model1",
                "graph":       "graph1",
                "rank":        overflow_rank
            }),
            &state,
            None,
        )
        .await;
        let (code, msg) = result.unwrap_err();
        assert_eq!(
            code, ERR_INVALID_PARAMS,
            "overflow rank must return INVALID_PARAMS"
        );
        assert!(
            msg.contains("u32"),
            "error must mention u32 boundary, got: {msg}"
        );
    }

    #[test]
    fn u32_max_is_safe_layer_boundary() {
        // u32::MAX is accepted by try_from; u32::MAX + 1 is not
        assert!(u32::try_from(u32::MAX as u64).is_ok());
        assert!(u32::try_from(u32::MAX as u64 + 1).is_err());
    }

    // ── kotoba_sparql_query ──────────────────────────────────────────────────

    #[tokio::test]
    async fn call_tool_sparql_query_missing_graph_errors() {
        let state = test_state();
        let result = call_tool(
            MCP_TOOL_SPARQL_QUERY,
            &json!({
                "sparql": "SELECT ?s WHERE { ?s <role> \"admin\" }"
            }),
            &state,
            None,
        )
        .await;
        let (code, _) = result.unwrap_err();
        assert_eq!(code, ERR_INVALID_PARAMS);
    }

    #[tokio::test]
    async fn call_tool_sparql_query_missing_sparql_errors() {
        let state = test_state();
        let result = call_tool(
            MCP_TOOL_SPARQL_QUERY,
            &json!({
                "graph": "bafyreiaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            }),
            &state,
            None,
        )
        .await;
        let (code, _) = result.unwrap_err();
        assert_eq!(code, ERR_INVALID_PARAMS);
    }

    #[tokio::test]
    async fn call_tool_sparql_query_oversized_sparql_errors() {
        let state = test_state();
        let big = "x".repeat(8 * 1024 + 1);
        let result = call_tool(
            MCP_TOOL_SPARQL_QUERY,
            &json!({
                "graph":  "graph1",
                "sparql": big
            }),
            &state,
            None,
        )
        .await;
        let (code, msg) = result.unwrap_err();
        assert_eq!(code, ERR_INVALID_PARAMS);
        assert!(msg.contains("sparql"), "expected 'sparql' in: {msg}");
    }

    #[tokio::test]
    async fn call_tool_sparql_query_empty_graph_returns_empty() {
        let state = test_state();
        let result = call_tool(
            MCP_TOOL_SPARQL_QUERY,
            &json!({
                "graph":  "empty-graph-cid",
                "sparql": "SELECT ?s WHERE { ?s <role> \"admin\" }"
            }),
            &state,
            None,
        )
        .await;
        assert!(result.is_ok(), "{result:?}");
        let v = result.unwrap();
        assert_eq!(v["count"], 0);
        assert!(v["quads"].is_array());
    }

    #[tokio::test]
    async fn call_tool_email_list_reads_distributed_datomic_view() {
        use kotoba_ingest::graph_cid_for;
        use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

        let state = test_state();
        let owner_did = "did:key:zEmailListDistributed1";
        let graph_cid = graph_cid_for(owner_did);
        let graph = graph_cid.to_multibase();
        let email_cid = KotobaCid::from_bytes(b"email-list-distributed-1");
        let date_only_cid = KotobaCid::from_bytes(b"email-list-date-only");
        let tx_cid = mcp_tx_cid("email.list.test", &[owner_did]);
        let datoms = vec![
            KqeDatom::assert(
                email_cid.clone(),
                "email/date".into(),
                KqeValue::Text("2000000000".into()),
                tx_cid.clone(),
            ),
            KqeDatom::assert(
                email_cid.clone(),
                "email/message_id".into(),
                KqeValue::Text("<distributed@example.test>".into()),
                tx_cid.clone(),
            ),
            KqeDatom::assert(
                email_cid.clone(),
                "email/body_cid".into(),
                KqeValue::Text(
                    KotobaCid::from_bytes(b"email-list-distributed-body").to_multibase(),
                ),
                tx_cid.clone(),
            ),
            KqeDatom::assert(
                email_cid.clone(),
                "email/subject".into(),
                KqeValue::Text("Distributed-subject".into()),
                tx_cid.clone(),
            ),
            KqeDatom::assert(
                email_cid.clone(),
                "email/from".into(),
                KqeValue::Text("sender@example.test".into()),
                tx_cid.clone(),
            ),
            KqeDatom::assert(
                date_only_cid,
                "email/date".into(),
                KqeValue::Text("9999999999".into()),
                tx_cid.clone(),
            ),
        ];
        commit_mcp_datoms(
            &state,
            graph_cid,
            graph,
            email_cid.clone(),
            datoms,
            tx_cid,
            None,
        )
        .await
        .unwrap();

        let value = call_tool(
            MCP_TOOL_EMAIL_LIST,
            &json!({ "owner_did": owner_did }),
            &state,
            None,
        )
        .await
        .unwrap();
        assert_eq!(value["total"], 1, "{value}");
        let email = &value["emails"][0];
        assert_eq!(email["cid"], email_cid.to_multibase(), "{value}");
        assert_eq!(email["message_id"], "<distributed@example.test>", "{value}");
        assert_eq!(email["subject"], "Distributed-subject", "{value}");
        assert_eq!(email["from"], "sender@example.test", "{value}");
    }

    #[tokio::test]
    async fn call_tool_email_list_rejects_invalid_pagination() {
        let state = test_state();
        let owner_did = "did:key:zEmailListPagination";

        for args in [
            json!({ "owner_did": owner_did, "limit": 0 }),
            json!({ "owner_did": owner_did, "limit": MAX_EMAIL_LIST_LIMIT + 1 }),
            json!({ "owner_did": owner_did, "limit": "200" }),
            json!({ "owner_did": owner_did, "offset": -1 }),
            json!({ "owner_did": owner_did, "offset": MAX_EMAIL_LIST_OFFSET + 1 }),
        ] {
            let result = call_tool(MCP_TOOL_EMAIL_LIST, &args, &state, None).await;
            let (code, msg) = result.unwrap_err();
            assert_eq!(code, ERR_INVALID_PARAMS, "{args}");
            assert!(
                msg.contains("limit") || msg.contains("offset"),
                "unexpected error for {args}: {msg}"
            );
        }
    }

    #[tokio::test]
    async fn call_tool_email_list_applies_limit_and_offset_after_filter_and_sort() {
        use kotoba_ingest::graph_cid_for;
        use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

        let state = test_state();
        let owner_did = "did:key:zMcpEmailListPaged";
        let graph_cid = graph_cid_for(owner_did);
        let graph = graph_cid.to_multibase();
        let newest = KotobaCid::from_bytes(b"mcp-list-paged-newest");
        let middle = KotobaCid::from_bytes(b"mcp-list-paged-middle");
        let oldest = KotobaCid::from_bytes(b"mcp-list-paged-oldest");
        let invalid_newer = KotobaCid::from_bytes(b"mcp-list-paged-invalid-newer");
        let tx_cid = mcp_tx_cid("email.list.paged", &[owner_did]);
        let mut datoms = Vec::new();
        for (email_cid, date) in [
            (oldest.clone(), "2026-06-10T00:00:00Z"),
            (newest.clone(), "2026-06-12T00:00:00Z"),
            (middle.clone(), "2026-06-11T00:00:00Z"),
        ] {
            for (predicate, object) in [
                ("email/message_id", email_cid.to_multibase()),
                (
                    "email/body_cid",
                    KotobaCid::from_bytes(format!("mcp-list-paged-body-{date}").as_bytes())
                        .to_multibase(),
                ),
                ("email/date", date.to_string()),
            ] {
                datoms.push(KqeDatom::assert(
                    email_cid.clone(),
                    predicate.to_string(),
                    KqeValue::Text(object),
                    tx_cid.clone(),
                ));
            }
        }
        for (predicate, object) in [
            ("email/message_id", invalid_newer.to_multibase()),
            ("email/date", "2026-06-13T00:00:00Z".to_string()),
        ] {
            datoms.push(KqeDatom::assert(
                invalid_newer.clone(),
                predicate.to_string(),
                KqeValue::Text(object),
                tx_cid.clone(),
            ));
        }
        commit_mcp_datoms(
            &state,
            graph_cid,
            graph,
            newest.clone(),
            datoms,
            tx_cid,
            None,
        )
        .await
        .unwrap();

        let value = call_tool(
            MCP_TOOL_EMAIL_LIST,
            &json!({ "owner_did": owner_did, "limit": 1, "offset": 1 }),
            &state,
            None,
        )
        .await
        .unwrap();
        assert_eq!(value["total"], 3, "{value}");
        assert_eq!(value["offset"], 1, "{value}");
        assert_eq!(value["limit"], 1, "{value}");
        let emails = value["emails"].as_array().expect("emails");
        assert_eq!(emails.len(), 1, "{value}");
        assert_eq!(emails[0]["cid"], middle.to_multibase(), "{value}");
        assert_eq!(emails[0]["date"], "2026-06-11T00:00:00Z", "{value}");
    }

    #[tokio::test]
    async fn call_tool_email_list_tiebreaks_same_date_by_cid() {
        use kotoba_ingest::graph_cid_for;
        use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

        let state = test_state();
        let owner_did = "did:key:zMcpEmailListSameDate";
        let graph_cid = graph_cid_for(owner_did);
        let graph = graph_cid.to_multibase();
        let first = KotobaCid::from_bytes(b"mcp-list-same-date-a");
        let second = KotobaCid::from_bytes(b"mcp-list-same-date-b");
        let date = "2026-06-12T00:00:00Z";
        let tx_cid = mcp_tx_cid("email.list.same-date", &[owner_did]);
        let mut datoms = Vec::new();
        for email_cid in [second.clone(), first.clone()] {
            for (predicate, object) in [
                ("email/message_id", email_cid.to_multibase()),
                (
                    "email/body_cid",
                    KotobaCid::from_bytes(email_cid.to_multibase().as_bytes()).to_multibase(),
                ),
                ("email/date", date.to_string()),
            ] {
                datoms.push(KqeDatom::assert(
                    email_cid.clone(),
                    predicate.to_string(),
                    KqeValue::Text(object),
                    tx_cid.clone(),
                ));
            }
        }
        commit_mcp_datoms(
            &state,
            graph_cid,
            graph,
            first.clone(),
            datoms,
            tx_cid,
            None,
        )
        .await
        .unwrap();

        let mut expected = [first.to_multibase(), second.to_multibase()];
        expected.sort();
        let value = call_tool(
            MCP_TOOL_EMAIL_LIST,
            &json!({ "owner_did": owner_did, "limit": 2, "offset": 0 }),
            &state,
            None,
        )
        .await
        .unwrap();
        assert_eq!(value["total"], 2, "{value}");
        let emails = value["emails"].as_array().expect("emails");
        assert_eq!(emails.len(), 2, "{value}");
        assert_eq!(emails[0]["cid"], expected[0], "{value}");
        assert_eq!(emails[1]["cid"], expected[1], "{value}");
    }

    #[tokio::test]
    async fn call_tool_email_list_exposes_signal_metadata() {
        use kotoba_ingest::graph_cid_for;
        use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

        let state = test_state();
        let owner_did = "did:key:zEmailListSignalRecipient";
        let sender_did = "did:key:zEmailListSignalSender";
        let graph_cid = graph_cid_for(owner_did);
        let graph = graph_cid.to_multibase();
        let email_cid = KotobaCid::from_bytes(b"mcp-email-list-signal");
        let tx_cid = mcp_tx_cid("email.list.signal", &[owner_did]);
        let datoms = vec![
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
            ("email/message_id", email_cid.to_multibase()),
            ("email/from", sender_did.to_string()),
            (
                "email/body_cid",
                KotobaCid::from_bytes(b"body").to_multibase(),
            ),
            ("email/enc", ENC_SIGNAL_V1.to_string()),
            ("email/recipient_device", "device-1".to_string()),
        ]
        .into_iter()
        .map(|(predicate, object)| {
            KqeDatom::assert(
                email_cid.clone(),
                predicate.to_string(),
                KqeValue::Text(object),
                tx_cid.clone(),
            )
        })
        .collect();
        commit_mcp_datoms(
            &state,
            graph_cid,
            graph,
            email_cid.clone(),
            datoms,
            tx_cid,
            None,
        )
        .await
        .unwrap();

        let value = call_tool(
            MCP_TOOL_EMAIL_LIST,
            &json!({ "owner_did": owner_did }),
            &state,
            None,
        )
        .await
        .unwrap();
        let email = &value["emails"][0];
        assert_eq!(email["cid"], email_cid.to_multibase(), "{value}");
        assert_eq!(email["enc"], ENC_SIGNAL_V1, "{value}");
        assert_eq!(email["recipient_device"], "device-1", "{value}");
        assert_eq!(email["from"], sender_did, "{value}");
    }

    #[tokio::test]
    async fn call_tool_email_list_sanitizes_legacy_display_metadata() {
        use kotoba_ingest::graph_cid_for;
        use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

        let state = Arc::new(
            crate::server::KotobaState::new(None)
                .expect("state")
                .init_crypto()
                .await
                .expect("crypto"),
        );
        let owner_did = "did:key:zMcpEmailListSanitizeLegacyMetadata";
        let graph_cid = graph_cid_for(owner_did);
        let graph = graph_cid.to_multibase();
        let email_cid = KotobaCid::from_bytes(b"mcp-email-list-sanitize-legacy-metadata");
        let tx_cid = mcp_tx_cid("email.list.sanitize-legacy-metadata", &[owner_did]);
        let datoms = vec![
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
            ("email/message_id", email_cid.to_multibase()),
            (
                "email/body_cid",
                KotobaCid::from_bytes(b"mcp-email-list-sanitize-body").to_multibase(),
            ),
            ("email/from", "sender\n@example.test".to_string()),
            ("email/subject", "signal:v1:corrupt-envelope".to_string()),
        ]
        .into_iter()
        .map(|(predicate, object)| {
            KqeDatom::assert(
                email_cid.clone(),
                predicate.to_string(),
                KqeValue::Text(object),
                tx_cid.clone(),
            )
        })
        .collect();
        commit_mcp_datoms(
            &state,
            graph_cid,
            graph,
            email_cid.clone(),
            datoms,
            tx_cid,
            None,
        )
        .await
        .unwrap();

        let value = call_tool(
            MCP_TOOL_EMAIL_LIST,
            &json!({ "owner_did": owner_did }),
            &state,
            None,
        )
        .await
        .unwrap();
        assert_eq!(value["total"], 1, "{value}");
        let email = &value["emails"][0];
        assert_eq!(email["cid"], email_cid.to_multibase(), "{value}");
        assert_eq!(email["from"], "", "{value}");
        assert_eq!(email["subject"], "", "{value}");
    }

    #[tokio::test]
    async fn call_tool_email_list_skips_subjects_with_invalid_enc() {
        use kotoba_ingest::graph_cid_for;
        use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

        let state = test_state();
        let owner_did = "did:key:zEmailListInvalidSignalMetadata";
        let graph_cid = graph_cid_for(owner_did);
        let graph = graph_cid.to_multibase();
        let valid_email_cid = KotobaCid::from_bytes(b"mcp-email-list-valid-enc");
        let invalid_enc_cid = KotobaCid::from_bytes(b"mcp-email-list-invalid-enc");
        let tx_cid = mcp_tx_cid("email.list.invalid-signal-metadata", &[owner_did]);
        let datoms = vec![
            (
                valid_email_cid.clone(),
                "email/date",
                "2026-06-12T00:00:00Z".to_string(),
            ),
            (
                valid_email_cid.clone(),
                "email/message_id",
                valid_email_cid.to_multibase(),
            ),
            (
                valid_email_cid.clone(),
                "email/body_cid",
                KotobaCid::from_bytes(b"mcp-email-list-valid-enc-body").to_multibase(),
            ),
            (
                invalid_enc_cid.clone(),
                "email/date",
                "2026-06-13T00:00:00Z".to_string(),
            ),
            (
                invalid_enc_cid.clone(),
                "email/message_id",
                invalid_enc_cid.to_multibase(),
            ),
            (
                invalid_enc_cid.clone(),
                "email/body_cid",
                KotobaCid::from_bytes(b"mcp-email-list-invalid-enc-body").to_multibase(),
            ),
            (invalid_enc_cid, "email/enc", "unknown:v1".to_string()),
        ]
        .into_iter()
        .map(|(subject, predicate, object)| {
            KqeDatom::assert(
                subject,
                predicate.to_string(),
                KqeValue::Text(object),
                tx_cid.clone(),
            )
        })
        .collect();
        commit_mcp_datoms(
            &state,
            graph_cid,
            graph,
            valid_email_cid.clone(),
            datoms,
            tx_cid,
            None,
        )
        .await
        .unwrap();

        let value = call_tool(
            MCP_TOOL_EMAIL_LIST,
            &json!({ "owner_did": owner_did }),
            &state,
            None,
        )
        .await
        .unwrap();
        assert_eq!(value["total"], 1, "{value}");
        let email = &value["emails"][0];
        assert_eq!(email["cid"], valid_email_cid.to_multibase(), "{value}");
        assert!(email.get("enc").is_none(), "{value}");
        assert!(email.get("recipient_device").is_none(), "{value}");
    }

    #[tokio::test]
    async fn call_tool_email_list_skips_subjects_without_valid_body_cid() {
        use kotoba_ingest::graph_cid_for;
        use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

        let state = test_state();
        let owner_did = "did:key:zMcpEmailListInvalidBodyCid";
        let graph_cid = graph_cid_for(owner_did);
        let graph = graph_cid.to_multibase();
        let valid_email_cid = KotobaCid::from_bytes(b"mcp-list-valid-body-cid");
        let missing_body_cid = KotobaCid::from_bytes(b"mcp-list-missing-body-cid");
        let invalid_body_cid = KotobaCid::from_bytes(b"mcp-list-invalid-body-cid");
        let tx_cid = mcp_tx_cid("email.list.invalid-body-cid", &[owner_did]);
        let datoms = vec![
            (
                valid_email_cid.clone(),
                "email/message_id",
                valid_email_cid.to_multibase(),
            ),
            (
                valid_email_cid.clone(),
                "email/body_cid",
                KotobaCid::from_bytes(b"mcp-list-valid-body-cid-body").to_multibase(),
            ),
            (
                valid_email_cid.clone(),
                "email/date",
                "2026-06-12T00:00:00Z".to_string(),
            ),
            (
                missing_body_cid.clone(),
                "email/message_id",
                missing_body_cid.to_multibase(),
            ),
            (
                missing_body_cid,
                "email/date",
                "2026-06-13T00:00:00Z".to_string(),
            ),
            (
                invalid_body_cid.clone(),
                "email/message_id",
                invalid_body_cid.to_multibase(),
            ),
            (
                invalid_body_cid.clone(),
                "email/body_cid",
                "not-a-multibase-cid".to_string(),
            ),
            (
                invalid_body_cid,
                "email/date",
                "2026-06-14T00:00:00Z".to_string(),
            ),
        ]
        .into_iter()
        .map(|(subject, predicate, object)| {
            KqeDatom::assert(
                subject,
                predicate.to_string(),
                KqeValue::Text(object),
                tx_cid.clone(),
            )
        })
        .collect();
        commit_mcp_datoms(
            &state,
            graph_cid,
            graph,
            valid_email_cid.clone(),
            datoms,
            tx_cid,
            None,
        )
        .await
        .unwrap();

        let value = call_tool(
            MCP_TOOL_EMAIL_LIST,
            &json!({ "owner_did": owner_did }),
            &state,
            None,
        )
        .await
        .unwrap();
        assert_eq!(value["total"], 1, "{value}");
        assert_eq!(
            value["emails"][0]["cid"],
            valid_email_cid.to_multibase(),
            "{value}"
        );
    }

    #[tokio::test]
    async fn call_tool_email_list_skips_subjects_with_invalid_message_id() {
        use kotoba_ingest::graph_cid_for;
        use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

        let state = test_state();
        let owner_did = "did:key:zMcpEmailListInvalidMessageId";
        let graph_cid = graph_cid_for(owner_did);
        let graph = graph_cid.to_multibase();
        let valid_email_cid = KotobaCid::from_bytes(b"mcp-list-valid-message-id");
        let empty_message_id_cid = KotobaCid::from_bytes(b"mcp-list-empty-message-id");
        let control_message_id_cid = KotobaCid::from_bytes(b"mcp-list-control-message-id");
        let tx_cid = mcp_tx_cid("email.list.invalid-message-id", &[owner_did]);
        let datoms = vec![
            (
                valid_email_cid.clone(),
                "email/message_id",
                valid_email_cid.to_multibase(),
            ),
            (
                valid_email_cid.clone(),
                "email/body_cid",
                KotobaCid::from_bytes(b"mcp-list-valid-message-id-body").to_multibase(),
            ),
            (
                valid_email_cid.clone(),
                "email/date",
                "2026-06-12T00:00:00Z".to_string(),
            ),
            (
                empty_message_id_cid.clone(),
                "email/message_id",
                String::new(),
            ),
            (
                empty_message_id_cid.clone(),
                "email/body_cid",
                KotobaCid::from_bytes(b"mcp-list-empty-message-id-body").to_multibase(),
            ),
            (
                empty_message_id_cid,
                "email/date",
                "2026-06-13T00:00:00Z".to_string(),
            ),
            (
                control_message_id_cid.clone(),
                "email/message_id",
                "bad\nmessage-id".to_string(),
            ),
            (
                control_message_id_cid.clone(),
                "email/body_cid",
                KotobaCid::from_bytes(b"mcp-list-control-message-id-body").to_multibase(),
            ),
            (
                control_message_id_cid,
                "email/date",
                "2026-06-14T00:00:00Z".to_string(),
            ),
        ]
        .into_iter()
        .map(|(subject, predicate, object)| {
            KqeDatom::assert(
                subject,
                predicate.to_string(),
                KqeValue::Text(object),
                tx_cid.clone(),
            )
        })
        .collect();
        commit_mcp_datoms(
            &state,
            graph_cid,
            graph,
            valid_email_cid.clone(),
            datoms,
            tx_cid,
            None,
        )
        .await
        .unwrap();

        let value = call_tool(
            MCP_TOOL_EMAIL_LIST,
            &json!({ "owner_did": owner_did }),
            &state,
            None,
        )
        .await
        .unwrap();
        assert_eq!(value["total"], 1, "{value}");
        assert_eq!(
            value["emails"][0]["cid"],
            valid_email_cid.to_multibase(),
            "{value}"
        );
        assert_eq!(
            value["emails"][0]["message_id"],
            valid_email_cid.to_multibase(),
            "{value}"
        );
    }

    #[tokio::test]
    async fn call_tool_email_list_skips_subjects_with_invalid_date() {
        use kotoba_ingest::graph_cid_for;
        use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

        let state = test_state();
        let owner_did = "did:key:zMcpEmailListInvalidDate";
        let graph_cid = graph_cid_for(owner_did);
        let graph = graph_cid.to_multibase();
        let valid_email_cid = KotobaCid::from_bytes(b"mcp-list-valid-date");
        let empty_date_cid = KotobaCid::from_bytes(b"mcp-list-empty-date");
        let control_date_cid = KotobaCid::from_bytes(b"mcp-list-control-date");
        let oversized_date_cid = KotobaCid::from_bytes(b"mcp-list-oversized-date");
        let tx_cid = mcp_tx_cid("email.list.invalid-date", &[owner_did]);
        let datoms = vec![
            (
                valid_email_cid.clone(),
                "email/message_id",
                valid_email_cid.to_multibase(),
            ),
            (
                valid_email_cid.clone(),
                "email/body_cid",
                KotobaCid::from_bytes(b"mcp-list-valid-date-body").to_multibase(),
            ),
            (
                valid_email_cid.clone(),
                "email/date",
                "2026-06-12T00:00:00Z".to_string(),
            ),
            (
                empty_date_cid.clone(),
                "email/message_id",
                empty_date_cid.to_multibase(),
            ),
            (
                empty_date_cid.clone(),
                "email/body_cid",
                KotobaCid::from_bytes(b"mcp-list-empty-date-body").to_multibase(),
            ),
            (empty_date_cid, "email/date", String::new()),
            (
                control_date_cid.clone(),
                "email/message_id",
                control_date_cid.to_multibase(),
            ),
            (
                control_date_cid.clone(),
                "email/body_cid",
                KotobaCid::from_bytes(b"mcp-list-control-date-body").to_multibase(),
            ),
            (
                control_date_cid,
                "email/date",
                "2026-06-13\n00:00:00Z".to_string(),
            ),
            (
                oversized_date_cid.clone(),
                "email/message_id",
                oversized_date_cid.to_multibase(),
            ),
            (
                oversized_date_cid.clone(),
                "email/body_cid",
                KotobaCid::from_bytes(b"mcp-list-oversized-date-body").to_multibase(),
            ),
            (
                oversized_date_cid,
                "email/date",
                "x".repeat(MAX_EMAIL_DATE_LEN + 1),
            ),
        ]
        .into_iter()
        .map(|(subject, predicate, object)| {
            KqeDatom::assert(
                subject,
                predicate.to_string(),
                KqeValue::Text(object),
                tx_cid.clone(),
            )
        })
        .collect();
        commit_mcp_datoms(
            &state,
            graph_cid,
            graph,
            valid_email_cid.clone(),
            datoms,
            tx_cid,
            None,
        )
        .await
        .unwrap();

        let value = call_tool(
            MCP_TOOL_EMAIL_LIST,
            &json!({ "owner_did": owner_did }),
            &state,
            None,
        )
        .await
        .unwrap();
        assert_eq!(value["total"], 1, "{value}");
        assert_eq!(
            value["emails"][0]["cid"],
            valid_email_cid.to_multibase(),
            "{value}"
        );
        assert_eq!(value["emails"][0]["date"], "2026-06-12T00:00:00Z");
    }

    #[tokio::test]
    async fn call_tool_email_list_skips_subjects_with_non_text_metadata() {
        use kotoba_ingest::graph_cid_for;
        use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

        let state = test_state();
        let owner_did = "did:key:zMcpEmailListNonTextMetadata";
        let graph_cid = graph_cid_for(owner_did);
        let graph = graph_cid.to_multibase();
        let valid_email_cid = KotobaCid::from_bytes(b"mcp-list-valid-text-metadata");
        let non_text_date_cid = KotobaCid::from_bytes(b"mcp-list-non-text-date");
        let non_text_message_id_cid = KotobaCid::from_bytes(b"mcp-list-non-text-message-id");
        let non_text_body_cid = KotobaCid::from_bytes(b"mcp-list-non-text-body-cid");
        let non_text_enc_cid = KotobaCid::from_bytes(b"mcp-list-non-text-enc");
        let tx_cid = mcp_tx_cid("email.list.non-text-metadata", &[owner_did]);
        let datoms = vec![
            KqeDatom::assert(
                valid_email_cid.clone(),
                "email/message_id".to_string(),
                KqeValue::Text(valid_email_cid.to_multibase()),
                tx_cid.clone(),
            ),
            KqeDatom::assert(
                valid_email_cid.clone(),
                "email/body_cid".to_string(),
                KqeValue::Text(KotobaCid::from_bytes(b"mcp-list-valid-text-body").to_multibase()),
                tx_cid.clone(),
            ),
            KqeDatom::assert(
                valid_email_cid.clone(),
                "email/date".to_string(),
                KqeValue::Text("2026-06-12T00:00:00Z".to_string()),
                tx_cid.clone(),
            ),
            KqeDatom::assert(
                non_text_date_cid.clone(),
                "email/message_id".to_string(),
                KqeValue::Text(non_text_date_cid.to_multibase()),
                tx_cid.clone(),
            ),
            KqeDatom::assert(
                non_text_date_cid.clone(),
                "email/body_cid".to_string(),
                KqeValue::Text(
                    KotobaCid::from_bytes(b"mcp-list-non-text-date-body").to_multibase(),
                ),
                tx_cid.clone(),
            ),
            KqeDatom::assert(
                non_text_date_cid,
                "email/date".to_string(),
                KqeValue::Integer(1),
                tx_cid.clone(),
            ),
            KqeDatom::assert(
                non_text_message_id_cid.clone(),
                "email/message_id".to_string(),
                KqeValue::Integer(1),
                tx_cid.clone(),
            ),
            KqeDatom::assert(
                non_text_message_id_cid.clone(),
                "email/body_cid".to_string(),
                KqeValue::Text(
                    KotobaCid::from_bytes(b"mcp-list-non-text-message-id-body").to_multibase(),
                ),
                tx_cid.clone(),
            ),
            KqeDatom::assert(
                non_text_message_id_cid,
                "email/date".to_string(),
                KqeValue::Text("2026-06-13T00:00:00Z".to_string()),
                tx_cid.clone(),
            ),
            KqeDatom::assert(
                non_text_body_cid.clone(),
                "email/message_id".to_string(),
                KqeValue::Text(non_text_body_cid.to_multibase()),
                tx_cid.clone(),
            ),
            KqeDatom::assert(
                non_text_body_cid.clone(),
                "email/body_cid".to_string(),
                KqeValue::Integer(1),
                tx_cid.clone(),
            ),
            KqeDatom::assert(
                non_text_body_cid,
                "email/date".to_string(),
                KqeValue::Text("2026-06-14T00:00:00Z".to_string()),
                tx_cid.clone(),
            ),
            KqeDatom::assert(
                non_text_enc_cid.clone(),
                "email/message_id".to_string(),
                KqeValue::Text(non_text_enc_cid.to_multibase()),
                tx_cid.clone(),
            ),
            KqeDatom::assert(
                non_text_enc_cid.clone(),
                "email/body_cid".to_string(),
                KqeValue::Text(KotobaCid::from_bytes(b"mcp-list-non-text-enc-body").to_multibase()),
                tx_cid.clone(),
            ),
            KqeDatom::assert(
                non_text_enc_cid.clone(),
                "email/date".to_string(),
                KqeValue::Text("2026-06-15T00:00:00Z".to_string()),
                tx_cid.clone(),
            ),
            KqeDatom::assert(
                non_text_enc_cid,
                "email/enc".to_string(),
                KqeValue::Integer(1),
                tx_cid.clone(),
            ),
        ];
        commit_mcp_datoms(
            &state,
            graph_cid,
            graph,
            valid_email_cid.clone(),
            datoms,
            tx_cid,
            None,
        )
        .await
        .unwrap();

        let value = call_tool(
            MCP_TOOL_EMAIL_LIST,
            &json!({ "owner_did": owner_did }),
            &state,
            None,
        )
        .await
        .unwrap();
        assert_eq!(value["total"], 1, "{value}");
        assert_eq!(
            value["emails"][0]["cid"],
            valid_email_cid.to_multibase(),
            "{value}"
        );
    }

    #[tokio::test]
    async fn call_tool_email_list_skips_subjects_with_ambiguous_metadata() {
        use kotoba_ingest::graph_cid_for;
        use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

        let state = test_state();
        let owner_did = "did:key:zMcpEmailListAmbiguousMetadata";
        let graph_cid = graph_cid_for(owner_did);
        let graph = graph_cid.to_multibase();
        let valid_email_cid = KotobaCid::from_bytes(b"mcp-list-valid-unambiguous");
        let ambiguous_message_id_cid = KotobaCid::from_bytes(b"mcp-list-ambiguous-message-id");
        let ambiguous_body_cid = KotobaCid::from_bytes(b"mcp-list-ambiguous-body-cid");
        let tx_cid = mcp_tx_cid("email.list.ambiguous-metadata", &[owner_did]);
        let datoms = vec![
            (
                valid_email_cid.clone(),
                "email/message_id",
                valid_email_cid.to_multibase(),
            ),
            (
                valid_email_cid.clone(),
                "email/body_cid",
                KotobaCid::from_bytes(b"mcp-list-valid-unambiguous-body").to_multibase(),
            ),
            (
                valid_email_cid.clone(),
                "email/date",
                "2026-06-12T00:00:00Z".to_string(),
            ),
            (
                ambiguous_message_id_cid.clone(),
                "email/message_id",
                "<first@example.test>".to_string(),
            ),
            (
                ambiguous_message_id_cid.clone(),
                "email/message_id",
                "<second@example.test>".to_string(),
            ),
            (
                ambiguous_message_id_cid.clone(),
                "email/body_cid",
                KotobaCid::from_bytes(b"mcp-list-ambiguous-message-id-body").to_multibase(),
            ),
            (
                ambiguous_message_id_cid,
                "email/date",
                "2026-06-13T00:00:00Z".to_string(),
            ),
            (
                ambiguous_body_cid.clone(),
                "email/message_id",
                ambiguous_body_cid.to_multibase(),
            ),
            (
                ambiguous_body_cid.clone(),
                "email/body_cid",
                KotobaCid::from_bytes(b"mcp-list-ambiguous-body-a").to_multibase(),
            ),
            (
                ambiguous_body_cid.clone(),
                "email/body_cid",
                KotobaCid::from_bytes(b"mcp-list-ambiguous-body-b").to_multibase(),
            ),
            (
                ambiguous_body_cid,
                "email/date",
                "2026-06-14T00:00:00Z".to_string(),
            ),
        ]
        .into_iter()
        .map(|(subject, predicate, object)| {
            KqeDatom::assert(
                subject,
                predicate.to_string(),
                KqeValue::Text(object),
                tx_cid.clone(),
            )
        })
        .collect();
        commit_mcp_datoms(
            &state,
            graph_cid,
            graph,
            valid_email_cid.clone(),
            datoms,
            tx_cid,
            None,
        )
        .await
        .unwrap();

        let value = call_tool(
            MCP_TOOL_EMAIL_LIST,
            &json!({ "owner_did": owner_did }),
            &state,
            None,
        )
        .await
        .unwrap();
        assert_eq!(value["total"], 1, "{value}");
        assert_eq!(
            value["emails"][0]["cid"],
            valid_email_cid.to_multibase(),
            "{value}"
        );
    }

    #[tokio::test]
    async fn call_tool_email_read_rejects_invalid_email_cid_params() {
        let state = test_state();
        let owner_did = "did:key:zEmailReadCidValidation";

        for email_cid in [
            "",
            "   ",
            "bafy\ncid",
            "bafy cid",
            "bafyé",
            &"b".repeat(MAX_EMAIL_CID_LEN + 1),
            "not-a-multibase-cid",
        ] {
            let result = call_tool(
                MCP_TOOL_EMAIL_READ,
                &json!({ "owner_did": owner_did, "email_cid": email_cid }),
                &state,
                None,
            )
            .await;
            let (code, msg) = result.unwrap_err();
            assert_eq!(code, ERR_INVALID_PARAMS, "{email_cid:?}");
            assert!(msg.contains("email_cid"), "unexpected error: {msg}");
        }
    }

    #[tokio::test]
    async fn call_tool_email_list_and_read_reject_invalid_owner_did_params() {
        let state = test_state();
        let email_cid = KotobaCid::from_bytes(b"mcp-owner-did-validation").to_multibase();

        for owner_did in [
            "",
            "not-a-did",
            "did:key:zBad Owner",
            "did:key:zBad/Owner",
            &format!("did:key:z{}", "x".repeat(MAX_OWNER_DID_LEN)),
        ] {
            let list_result = call_tool(
                MCP_TOOL_EMAIL_LIST,
                &json!({ "owner_did": owner_did }),
                &state,
                None,
            )
            .await;
            let (list_code, list_msg) = list_result.unwrap_err();
            assert_eq!(list_code, ERR_INVALID_PARAMS, "{owner_did:?}");
            assert!(
                list_msg.contains("owner_did"),
                "unexpected error: {list_msg}"
            );

            let read_result = call_tool(
                MCP_TOOL_EMAIL_READ,
                &json!({ "owner_did": owner_did, "email_cid": email_cid }),
                &state,
                None,
            )
            .await;
            let (read_code, read_msg) = read_result.unwrap_err();
            assert_eq!(read_code, ERR_INVALID_PARAMS, "{owner_did:?}");
            assert!(
                read_msg.contains("owner_did"),
                "unexpected error: {read_msg}"
            );
        }
    }

    #[tokio::test]
    async fn call_tool_email_read_rejects_ambiguous_message_id_metadata() {
        use kotoba_ingest::graph_cid_for;
        use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

        let state = test_state();
        let owner_did = "did:key:zMcpEmailReadAmbiguousMessageId";
        let graph_cid = graph_cid_for(owner_did);
        let graph = graph_cid.to_multibase();
        let email_cid = KotobaCid::from_bytes(b"mcp-email-read-ambiguous-message-id");
        let email_cid_mb = email_cid.to_multibase();
        let tx_cid = mcp_tx_cid("email.read.ambiguous-message-id", &[owner_did]);
        let datoms = vec![
            ("email/message_id", "<first@example.test>".to_string()),
            ("email/message_id", "<second@example.test>".to_string()),
            (
                "email/body_cid",
                KotobaCid::from_bytes(b"mcp-email-read-ambiguous-message-id-body").to_multibase(),
            ),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
        ]
        .into_iter()
        .map(|(predicate, object)| {
            KqeDatom::assert(
                email_cid.clone(),
                predicate.to_string(),
                KqeValue::Text(object),
                tx_cid.clone(),
            )
        })
        .collect();
        commit_mcp_datoms(
            &state,
            graph_cid,
            graph,
            email_cid.clone(),
            datoms,
            tx_cid,
            None,
        )
        .await
        .unwrap();

        let result = call_tool(
            MCP_TOOL_EMAIL_READ,
            &json!({ "owner_did": owner_did, "email_cid": email_cid_mb }),
            &state,
            None,
        )
        .await;
        let (code, msg) = result.unwrap_err();
        assert_eq!(code, ERR_INTERNAL);
        assert!(
            msg.contains("multiple email/message_id values found"),
            "unexpected error: {msg}"
        );
    }

    #[tokio::test]
    async fn call_tool_email_read_legacy_body_decrypts_blob_bound_to_email_cid() {
        use kotoba_ingest::graph_cid_for;
        use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

        let state = Arc::new(
            crate::server::KotobaState::new(None)
                .expect("state")
                .init_crypto()
                .await
                .expect("crypto"),
        );
        let crypto = Arc::clone(state.crypto.as_ref().expect("crypto"));
        let owner_did = "did:key:zMcpLegacyBodyBoundRoundtrip";
        let graph_cid = graph_cid_for(owner_did);
        let graph = graph_cid.to_multibase();
        let email_cid = KotobaCid::from_bytes(b"mcp-legacy-body-bound-roundtrip");
        let email_cid_mb = email_cid.to_multibase();
        let body_text = "mcp body bound to this email cid";
        let body = crypto
            .encrypt_blob_bound(email_cid_mb.as_bytes(), body_text.as_bytes())
            .await
            .expect("bound body ciphertext");
        let blob = state.vault.put(bytes::Bytes::from(body)).await;
        let tx_cid = mcp_tx_cid("email.read.legacy.body-bound-roundtrip", &[owner_did]);
        let datoms = vec![
            ("email/message_id", email_cid_mb.clone()),
            ("email/body_cid", blob.cid.to_multibase()),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
            ("email/from", "sender@example.test".to_string()),
            ("email/to", "recipient@example.test".to_string()),
            ("email/subject", "Bound-body".to_string()),
        ]
        .into_iter()
        .map(|(predicate, object)| {
            KqeDatom::assert(
                email_cid.clone(),
                predicate.to_string(),
                KqeValue::Text(object),
                tx_cid.clone(),
            )
        })
        .collect();
        commit_mcp_datoms(
            &state,
            graph_cid,
            graph,
            email_cid.clone(),
            datoms,
            tx_cid,
            None,
        )
        .await
        .unwrap();

        let value = call_tool(
            MCP_TOOL_EMAIL_READ,
            &json!({ "owner_did": owner_did, "email_cid": email_cid_mb }),
            &state,
            None,
        )
        .await
        .unwrap();
        assert_eq!(value["email_cid"], email_cid_mb, "{value}");
        assert_eq!(value["body"], body_text, "{value}");
        assert_eq!(value["from"], "sender@example.test", "{value}");
        assert_eq!(value["subject"], "Bound-body", "{value}");
    }

    #[tokio::test]
    async fn call_tool_email_read_legacy_body_rejects_blob_bound_to_different_email_cid() {
        use kotoba_ingest::graph_cid_for;
        use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

        let state = Arc::new(
            crate::server::KotobaState::new(None)
                .expect("state")
                .init_crypto()
                .await
                .expect("crypto"),
        );
        let crypto = Arc::clone(state.crypto.as_ref().expect("crypto"));
        let owner_did = "did:key:zMcpLegacyBodyBoundSwap";
        let graph_cid = graph_cid_for(owner_did);
        let graph = graph_cid.to_multibase();
        let email_cid = KotobaCid::from_bytes(b"mcp-legacy-body-bound-target");
        let email_cid_mb = email_cid.to_multibase();
        let other_email_cid_mb =
            KotobaCid::from_bytes(b"mcp-legacy-body-bound-other").to_multibase();
        let swapped_body = crypto
            .encrypt_blob_bound(other_email_cid_mb.as_bytes(), b"swapped body")
            .await
            .expect("bound body ciphertext");
        let blob = state.vault.put(bytes::Bytes::from(swapped_body)).await;
        let tx_cid = mcp_tx_cid("email.read.legacy.body-bound-swap", &[owner_did]);
        let datoms = vec![
            ("email/message_id", email_cid_mb.clone()),
            ("email/body_cid", blob.cid.to_multibase()),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
        ]
        .into_iter()
        .map(|(predicate, object)| {
            KqeDatom::assert(
                email_cid.clone(),
                predicate.to_string(),
                KqeValue::Text(object),
                tx_cid.clone(),
            )
        })
        .collect();
        commit_mcp_datoms(
            &state,
            graph_cid,
            graph,
            email_cid.clone(),
            datoms,
            tx_cid,
            None,
        )
        .await
        .unwrap();

        let result = call_tool(
            MCP_TOOL_EMAIL_READ,
            &json!({ "owner_did": owner_did, "email_cid": email_cid_mb }),
            &state,
            None,
        )
        .await;
        let (code, msg) = result.unwrap_err();
        assert_eq!(code, ERR_INTERNAL);
        assert!(msg.contains("decrypt body"), "unexpected error: {msg}");
    }

    #[tokio::test]
    async fn call_tool_email_read_legacy_body_rejects_invalid_utf8_plaintext() {
        use kotoba_ingest::graph_cid_for;
        use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

        let state = Arc::new(
            crate::server::KotobaState::new(None)
                .expect("state")
                .init_crypto()
                .await
                .expect("crypto"),
        );
        let crypto = Arc::clone(state.crypto.as_ref().expect("crypto"));
        let owner_did = "did:key:zMcpLegacyInvalidUtf8Body";
        let graph_cid = graph_cid_for(owner_did);
        let graph = graph_cid.to_multibase();
        let email_cid = KotobaCid::from_bytes(b"mcp-legacy-invalid-utf8-body");
        let email_cid_mb = email_cid.to_multibase();
        let body = crypto
            .encrypt_blob_bound(email_cid_mb.as_bytes(), &[0xff, 0xfe, 0xfd])
            .await
            .expect("bound body ciphertext");
        let blob = state.vault.put(bytes::Bytes::from(body)).await;
        let tx_cid = mcp_tx_cid("email.read.legacy.invalid-utf8-body", &[owner_did]);
        let datoms = vec![
            ("email/message_id", email_cid_mb.clone()),
            ("email/body_cid", blob.cid.to_multibase()),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
        ]
        .into_iter()
        .map(|(predicate, object)| {
            KqeDatom::assert(
                email_cid.clone(),
                predicate.to_string(),
                KqeValue::Text(object),
                tx_cid.clone(),
            )
        })
        .collect();
        commit_mcp_datoms(
            &state,
            graph_cid,
            graph,
            email_cid.clone(),
            datoms,
            tx_cid,
            None,
        )
        .await
        .unwrap();

        let result = call_tool(
            MCP_TOOL_EMAIL_READ,
            &json!({ "owner_did": owner_did, "email_cid": email_cid_mb }),
            &state,
            None,
        )
        .await;
        let (code, msg) = result.unwrap_err();
        assert_eq!(code, ERR_INTERNAL);
        assert!(
            msg.contains("body is not valid UTF-8"),
            "unexpected error: {msg}"
        );
    }

    #[tokio::test]
    async fn call_tool_email_read_legacy_rejects_corrupt_encrypted_metadata() {
        let owner_did = "did:key:zMcpLegacyCorruptMetadata";
        let (state, _, email_cid_mb) = commit_legacy_email_fixture(
            owner_did,
            b"mcp-legacy-corrupt-metadata",
            b"valid body",
            "email.read.legacy.corrupt-metadata",
            [("email/from", "signal:v1:not-valid-ciphertext".to_string())],
        )
        .await;

        let result = call_tool(
            MCP_TOOL_EMAIL_READ,
            &json!({ "owner_did": owner_did, "email_cid": email_cid_mb }),
            &state,
            None,
        )
        .await;
        let (code, msg) = result.unwrap_err();
        assert_eq!(code, ERR_INTERNAL);
        assert!(msg.contains("decrypt from"), "unexpected error: {msg}");
    }

    #[tokio::test]
    async fn call_tool_email_read_legacy_rejects_ambiguous_display_metadata() {
        let owner_did = "did:key:zMcpLegacyAmbiguousDisplayMetadata";
        let (state, _, email_cid_mb) = commit_legacy_email_fixture(
            owner_did,
            b"mcp-legacy-ambiguous-display-metadata",
            b"valid body",
            "email.read.legacy.ambiguous-display",
            [
                ("email/subject", "First-subject".to_string()),
                ("email/subject", "Second-subject".to_string()),
            ],
        )
        .await;

        let result = call_tool(
            MCP_TOOL_EMAIL_READ,
            &json!({ "owner_did": owner_did, "email_cid": email_cid_mb }),
            &state,
            None,
        )
        .await;
        let (code, msg) = result.unwrap_err();
        assert_eq!(code, ERR_INTERNAL);
        assert!(
            msg.contains("multiple email/subject values found"),
            "unexpected error: {msg}"
        );
    }

    #[tokio::test]
    async fn call_tool_email_read_legacy_rejects_ambiguous_sender_metadata() {
        let owner_did = "did:key:zMcpLegacyAmbiguousSenderMetadata";
        let (state, _, email_cid_mb) = commit_legacy_email_fixture(
            owner_did,
            b"mcp-legacy-ambiguous-sender-metadata",
            b"valid body",
            "email.read.legacy.ambiguous-sender",
            [
                ("email/from", "first@example.test".to_string()),
                ("email/from", "second@example.test".to_string()),
            ],
        )
        .await;

        let result = call_tool(
            MCP_TOOL_EMAIL_READ,
            &json!({ "owner_did": owner_did, "email_cid": email_cid_mb }),
            &state,
            None,
        )
        .await;
        let (code, msg) = result.unwrap_err();
        assert_eq!(code, ERR_INTERNAL);
        assert!(
            msg.contains("multiple email/from values found"),
            "unexpected error: {msg}"
        );
    }

    #[tokio::test]
    async fn call_tool_email_read_legacy_rejects_ambiguous_recipient_metadata() {
        let owner_did = "did:key:zMcpLegacyAmbiguousRecipientMetadata";
        let (state, _, email_cid_mb) = commit_legacy_email_fixture(
            owner_did,
            b"mcp-legacy-ambiguous-recipient-metadata",
            b"valid body",
            "email.read.legacy.ambiguous-recipient",
            [
                ("email/to", "first-recipient@example.test".to_string()),
                ("email/to", "second-recipient@example.test".to_string()),
            ],
        )
        .await;

        let result = call_tool(
            MCP_TOOL_EMAIL_READ,
            &json!({ "owner_did": owner_did, "email_cid": email_cid_mb }),
            &state,
            None,
        )
        .await;
        let (code, msg) = result.unwrap_err();
        assert_eq!(code, ERR_INTERNAL);
        assert!(
            msg.contains("multiple email/to values found"),
            "unexpected error: {msg}"
        );
    }

    #[tokio::test]
    async fn call_tool_email_read_legacy_allows_duplicate_identical_display_metadata() {
        let owner_did = "did:key:zMcpLegacyDuplicateIdenticalDisplay";
        let body_text = "body with duplicate identical metadata";
        let (state, _, email_cid_mb) = commit_legacy_email_fixture(
            owner_did,
            b"mcp-legacy-duplicate-identical-display",
            body_text.as_bytes(),
            "email.read.legacy.duplicate-identical-display",
            [
                ("email/from", "sender@example.test".to_string()),
                ("email/from", "sender@example.test".to_string()),
                ("email/subject", "Same-subject".to_string()),
                ("email/subject", "Same-subject".to_string()),
            ],
        )
        .await;

        let value = call_tool(
            MCP_TOOL_EMAIL_READ,
            &json!({ "owner_did": owner_did, "email_cid": email_cid_mb }),
            &state,
            None,
        )
        .await
        .unwrap();
        assert_eq!(value["body"], body_text, "{value}");
        assert_eq!(value["from"], "sender@example.test", "{value}");
        assert_eq!(value["subject"], "Same-subject", "{value}");
    }

    #[tokio::test]
    async fn call_tool_email_read_legacy_allows_duplicate_encrypted_metadata_with_same_plaintext() {
        let state = Arc::new(
            crate::server::KotobaState::new(None)
                .expect("state")
                .init_crypto()
                .await
                .expect("crypto"),
        );
        let crypto = Arc::clone(state.crypto.as_ref().expect("crypto"));
        let owner_did = "did:key:zMcpLegacyDuplicateEncryptedDisplay";
        let body_text = "body with duplicate encrypted metadata";
        let subject_a = crypto
            .seal_field(b"email/subject", "Encrypted-same-subject")
            .await
            .expect("sealed subject a");
        let subject_b = crypto
            .seal_field(b"email/subject", "Encrypted-same-subject")
            .await
            .expect("sealed subject b");
        let (_, email_cid_mb) = commit_legacy_email_fixture_on_state(
            Arc::clone(&state),
            owner_did,
            b"mcp-legacy-duplicate-encrypted-display",
            body_text.as_bytes(),
            "email.read.legacy.duplicate-encrypted-display",
            [("email/subject", subject_a), ("email/subject", subject_b)],
        )
        .await;

        let value = call_tool(
            MCP_TOOL_EMAIL_READ,
            &json!({ "owner_did": owner_did, "email_cid": email_cid_mb }),
            &state,
            None,
        )
        .await
        .unwrap();
        assert_eq!(value["body"], body_text, "{value}");
        assert_eq!(value["subject"], "Encrypted-same-subject", "{value}");
    }

    #[tokio::test]
    async fn call_tool_email_read_legacy_allows_mixed_plaintext_and_encrypted_duplicate_metadata() {
        let state = Arc::new(
            crate::server::KotobaState::new(None)
                .expect("state")
                .init_crypto()
                .await
                .expect("crypto"),
        );
        let crypto = Arc::clone(state.crypto.as_ref().expect("crypto"));
        let owner_did = "did:key:zMcpLegacyMixedDuplicateDisplay";
        let body_text = "body with mixed duplicate metadata";
        let sealed_subject = crypto
            .seal_field(b"email/subject", "Mixed-same-subject")
            .await
            .expect("sealed subject");
        let (_, email_cid_mb) = commit_legacy_email_fixture_on_state(
            Arc::clone(&state),
            owner_did,
            b"mcp-legacy-mixed-duplicate-display",
            body_text.as_bytes(),
            "email.read.legacy.mixed-duplicate-display",
            [
                ("email/subject", "Mixed-same-subject".to_string()),
                ("email/subject", sealed_subject),
            ],
        )
        .await;

        let value = call_tool(
            MCP_TOOL_EMAIL_READ,
            &json!({ "owner_did": owner_did, "email_cid": email_cid_mb }),
            &state,
            None,
        )
        .await
        .unwrap();
        assert_eq!(value["body"], body_text, "{value}");
        assert_eq!(value["subject"], "Mixed-same-subject", "{value}");
    }

    #[tokio::test]
    async fn call_tool_email_read_legacy_rejects_mixed_plaintext_and_encrypted_duplicate_metadata_with_different_plaintext(
    ) {
        let state = Arc::new(
            crate::server::KotobaState::new(None)
                .expect("state")
                .init_crypto()
                .await
                .expect("crypto"),
        );
        let crypto = Arc::clone(state.crypto.as_ref().expect("crypto"));
        let owner_did = "did:key:zMcpLegacyConflictingMixedDisplay";
        let sealed_subject = crypto
            .seal_field(b"email/subject", "Mixed-encrypted-subject")
            .await
            .expect("sealed subject");
        let (_, email_cid_mb) = commit_legacy_email_fixture_on_state(
            Arc::clone(&state),
            owner_did,
            b"mcp-legacy-conflicting-mixed-display",
            b"valid body",
            "email.read.legacy.conflicting-mixed-display",
            [
                ("email/subject", "Mixed-plain-subject".to_string()),
                ("email/subject", sealed_subject),
            ],
        )
        .await;

        let result = call_tool(
            MCP_TOOL_EMAIL_READ,
            &json!({ "owner_did": owner_did, "email_cid": email_cid_mb }),
            &state,
            None,
        )
        .await;
        let (code, msg) = result.unwrap_err();
        assert_eq!(code, ERR_INTERNAL);
        assert!(
            msg.contains("multiple email/subject values found"),
            "unexpected error: {msg}"
        );
    }

    #[tokio::test]
    async fn call_tool_email_read_legacy_rejects_duplicate_encrypted_metadata_with_different_plaintext(
    ) {
        let state = Arc::new(
            crate::server::KotobaState::new(None)
                .expect("state")
                .init_crypto()
                .await
                .expect("crypto"),
        );
        let crypto = Arc::clone(state.crypto.as_ref().expect("crypto"));
        let owner_did = "did:key:zMcpLegacyConflictingEncryptedDisplay";
        let subject_a = crypto
            .seal_field(b"email/subject", "Encrypted-first-subject")
            .await
            .expect("sealed subject a");
        let subject_b = crypto
            .seal_field(b"email/subject", "Encrypted-second-subject")
            .await
            .expect("sealed subject b");
        let (_, email_cid_mb) = commit_legacy_email_fixture_on_state(
            Arc::clone(&state),
            owner_did,
            b"mcp-legacy-conflicting-encrypted-display",
            b"valid body",
            "email.read.legacy.conflicting-encrypted-display",
            [("email/subject", subject_a), ("email/subject", subject_b)],
        )
        .await;

        let result = call_tool(
            MCP_TOOL_EMAIL_READ,
            &json!({ "owner_did": owner_did, "email_cid": email_cid_mb }),
            &state,
            None,
        )
        .await;
        let (code, msg) = result.unwrap_err();
        assert_eq!(code, ERR_INTERNAL);
        assert!(
            msg.contains("multiple email/subject values found"),
            "unexpected error: {msg}"
        );
    }

    #[tokio::test]
    async fn call_tool_email_read_legacy_rejects_decrypted_metadata_outside_ingest_caps() {
        use kotoba_ingest::graph_cid_for;
        use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

        for (case, predicate, scope, plaintext, expected) in [
            (
                "oversized-from",
                "email/from",
                b"email/from" as &'static [u8],
                "f".repeat(MAX_LEGACY_ADDR_LEN + 1),
                "from exceeds 4096 bytes",
            ),
            (
                "control-subject",
                "email/subject",
                b"email/subject" as &'static [u8],
                "hello\nworld".to_string(),
                "subject must contain only visible ASCII characters",
            ),
        ] {
            let state = Arc::new(
                crate::server::KotobaState::new(None)
                    .expect("state")
                    .init_crypto()
                    .await
                    .expect("crypto"),
            );
            let crypto = Arc::clone(state.crypto.as_ref().expect("crypto"));
            let owner_did = format!("did:key:zMcpLegacyMetadata{case}");
            let graph_cid = graph_cid_for(&owner_did);
            let graph = graph_cid.to_multibase();
            let email_cid = KotobaCid::from_bytes(format!("mcp-legacy-metadata-{case}").as_bytes());
            let email_cid_mb = email_cid.to_multibase();
            let body = crypto
                .encrypt_blob_bound(email_cid_mb.as_bytes(), b"valid body")
                .await
                .expect("bound body ciphertext");
            let blob = state.vault.put(bytes::Bytes::from(body)).await;
            let sealed_metadata = crypto
                .seal_field(scope, &plaintext)
                .await
                .expect("sealed metadata");
            let tx_cid = mcp_tx_cid("email.read.legacy.invalid-metadata", &[&owner_did, case]);
            let datoms = vec![
                ("email/message_id", email_cid_mb.clone()),
                ("email/body_cid", blob.cid.to_multibase()),
                ("email/date", "2026-06-02T00:00:00Z".to_string()),
                (predicate, sealed_metadata),
            ]
            .into_iter()
            .map(|(predicate, object)| {
                KqeDatom::assert(
                    email_cid.clone(),
                    predicate.to_string(),
                    KqeValue::Text(object),
                    tx_cid.clone(),
                )
            })
            .collect();
            commit_mcp_datoms(
                &state,
                graph_cid,
                graph,
                email_cid.clone(),
                datoms,
                tx_cid,
                None,
            )
            .await
            .unwrap();

            let result = call_tool(
                MCP_TOOL_EMAIL_READ,
                &json!({ "owner_did": owner_did, "email_cid": email_cid_mb }),
                &state,
                None,
            )
            .await;
            let (code, msg) = result.unwrap_err();
            assert_eq!(code, ERR_INTERNAL);
            assert!(msg.contains(expected), "unexpected error: {msg}");
        }
    }

    #[tokio::test]
    async fn call_tool_email_read_returns_signal_envelope_without_server_decrypt() {
        use kotoba_ingest::graph_cid_for;
        use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

        let state = test_state();
        let sender_did = "did:key:zMcpSignalSender";
        let owner_did = "did:key:zMcpSignalRecipient";
        let graph_cid = graph_cid_for(owner_did);
        let graph = graph_cid.to_multibase();
        let signal_message = json!({
            "messageType": "directMessage",
            "senderDid": sender_did,
            "recipientDid": owner_did,
            "deviceId": "device-1",
            "ciphertextEnvelope": "sealed-mime",
            "timestamp": "2026-06-02T00:00:00Z"
        });
        let blob_ref = state
            .vault
            .put(bytes::Bytes::from(
                serde_json::to_vec(&signal_message).expect("signal message JSON"),
            ))
            .await;
        let body_cid = blob_ref.cid.to_multibase();
        let email_cid = crate::email_xrpc::signal_email_cid_for(
            sender_did,
            owner_did,
            "2026-06-02T00:00:00Z",
            &body_cid,
        );
        let email_cid_mb = email_cid.to_multibase();
        let tx_cid = mcp_tx_cid("email.read.signal", &[owner_did]);
        let datoms = vec![
            ("email/message_id", email_cid_mb.clone()),
            ("email/from", sender_did.to_string()),
            ("email/to", owner_did.to_string()),
            ("email/body_cid", body_cid),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
            ("email/thread_id", "thread-signal".to_string()),
            ("email/enc", ENC_SIGNAL_V1.to_string()),
        ]
        .into_iter()
        .map(|(predicate, object)| {
            KqeDatom::assert(
                email_cid.clone(),
                predicate.to_string(),
                KqeValue::Text(object),
                tx_cid.clone(),
            )
        })
        .collect();
        commit_mcp_datoms(
            &state,
            graph_cid,
            graph,
            email_cid.clone(),
            datoms,
            tx_cid,
            None,
        )
        .await
        .unwrap();

        let value = call_tool(
            MCP_TOOL_EMAIL_READ,
            &json!({ "owner_did": owner_did, "email_cid": email_cid_mb }),
            &state,
            None,
        )
        .await
        .unwrap();
        assert_eq!(value["email_cid"], email_cid_mb, "{value}");
        assert_eq!(value["enc"], ENC_SIGNAL_V1, "{value}");
        // Signal routing metadata is canonicalized from the validated envelope,
        // not from potentially stale mailbox datoms.
        assert_eq!(value["from"], sender_did, "{value}");
        assert_eq!(value["to"], owner_did, "{value}");
        assert_eq!(value["thread_id"], "thread-signal", "{value}");
        assert_eq!(value["signalMessage"], signal_message, "{value}");
        assert!(
            value.get("body").is_none(),
            "signal read must not expose server-decrypted body: {value}"
        );
    }

    #[tokio::test]
    async fn call_tool_email_read_omits_invalid_signal_thread_id() {
        use kotoba_ingest::graph_cid_for;
        use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

        for (case, thread_id) in [
            ("control-thread", "thread\nid".to_string()),
            ("oversized-thread", "t".repeat(MAX_THREAD_ID_LEN + 1)),
        ] {
            let state = test_state();
            let sender_did = format!("did:key:zMcpSignalInvalidThreadSender{case}");
            let owner_did = format!("did:key:zMcpSignalInvalidThreadRecipient{case}");
            let graph_cid = graph_cid_for(&owner_did);
            let graph = graph_cid.to_multibase();
            let signal_message = json!({
                "messageType": "directMessage",
                "senderDid": sender_did,
                "recipientDid": owner_did,
                "deviceId": "device-1",
                "ciphertextEnvelope": "sealed-mime",
                "timestamp": "2026-06-02T00:00:00Z"
            });
            let blob_ref = state
                .vault
                .put(bytes::Bytes::from(
                    serde_json::to_vec(&signal_message).expect("signal message JSON"),
                ))
                .await;
            let body_cid = blob_ref.cid.to_multibase();
            let email_cid = crate::email_xrpc::signal_email_cid_for(
                &sender_did,
                &owner_did,
                "2026-06-02T00:00:00Z",
                &body_cid,
            );
            let email_cid_mb = email_cid.to_multibase();
            let tx_cid = mcp_tx_cid("email.read.signal.invalid-thread", &[&owner_did, case]);
            let datoms = vec![
                ("email/message_id", email_cid_mb.clone()),
                ("email/from", sender_did),
                ("email/to", owner_did.clone()),
                ("email/body_cid", body_cid),
                ("email/date", "2026-06-02T00:00:00Z".to_string()),
                ("email/thread_id", thread_id),
                ("email/enc", ENC_SIGNAL_V1.to_string()),
            ]
            .into_iter()
            .map(|(predicate, object)| {
                KqeDatom::assert(
                    email_cid.clone(),
                    predicate.to_string(),
                    KqeValue::Text(object),
                    tx_cid.clone(),
                )
            })
            .collect();
            commit_mcp_datoms(
                &state,
                graph_cid,
                graph,
                email_cid.clone(),
                datoms,
                tx_cid,
                None,
            )
            .await
            .unwrap();

            let value = call_tool(
                MCP_TOOL_EMAIL_READ,
                &json!({ "owner_did": owner_did, "email_cid": email_cid_mb }),
                &state,
                None,
            )
            .await
            .unwrap();
            assert_eq!(value["thread_id"], "", "{value}");
            assert_eq!(value["signalMessage"], signal_message, "{value}");
        }
    }

    #[tokio::test]
    async fn call_tool_email_read_rejects_signal_envelope_for_different_recipient() {
        use kotoba_ingest::graph_cid_for;
        use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

        let state = test_state();
        let owner_did = "did:key:zMcpSignalMailboxOwner";
        let actual_recipient = "did:key:zMcpSignalOtherRecipient";
        let graph_cid = graph_cid_for(owner_did);
        let graph = graph_cid.to_multibase();
        let email_cid = KotobaCid::from_bytes(b"mcp-signal-recipient-mismatch");
        let email_cid_mb = email_cid.to_multibase();
        let signal_message = json!({
            "messageType": "directMessage",
            "senderDid": "did:key:zMcpSignalMismatchSender",
            "recipientDid": actual_recipient,
            "deviceId": "device-1",
            "ciphertextEnvelope": "sealed-mime",
            "timestamp": "2026-06-02T00:00:00Z"
        });
        let blob_ref = state
            .vault
            .put(bytes::Bytes::from(
                serde_json::to_vec(&signal_message).expect("signal message JSON"),
            ))
            .await;
        let tx_cid = mcp_tx_cid("email.read.signal.recipient-mismatch", &[owner_did]);
        let datoms = vec![
            ("email/message_id", email_cid_mb.clone()),
            ("email/from", "did:key:zMcpSignalMismatchSender".to_string()),
            ("email/to", owner_did.to_string()),
            ("email/body_cid", blob_ref.cid.to_multibase()),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
            ("email/enc", ENC_SIGNAL_V1.to_string()),
        ]
        .into_iter()
        .map(|(predicate, object)| {
            KqeDatom::assert(
                email_cid.clone(),
                predicate.to_string(),
                KqeValue::Text(object),
                tx_cid.clone(),
            )
        })
        .collect();
        commit_mcp_datoms(
            &state,
            graph_cid,
            graph,
            email_cid.clone(),
            datoms,
            tx_cid,
            None,
        )
        .await
        .unwrap();

        let err = call_tool(
            MCP_TOOL_EMAIL_READ,
            &json!({ "owner_did": owner_did, "email_cid": email_cid_mb }),
            &state,
            None,
        )
        .await
        .unwrap_err();
        assert_eq!(err.0, ERR_INTERNAL);
        assert!(err.1.contains("recipientDid"), "{err:?}");
        assert!(err.1.contains("owner_did"), "{err:?}");
    }

    #[tokio::test]
    async fn call_tool_email_read_rejects_signal_date_mismatch() {
        use kotoba_ingest::graph_cid_for;
        use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

        let state = test_state();
        let sender_did = "did:key:zMcpSignalDateSender";
        let owner_did = "did:key:zMcpSignalDateRecipient";
        let graph_cid = graph_cid_for(owner_did);
        let graph = graph_cid.to_multibase();
        let signal_message = json!({
            "messageType": "directMessage",
            "senderDid": sender_did,
            "recipientDid": owner_did,
            "deviceId": "device-1",
            "ciphertextEnvelope": "sealed-mime",
            "timestamp": "2026-06-02T00:00:00Z"
        });
        let blob_ref = state
            .vault
            .put(bytes::Bytes::from(
                serde_json::to_vec(&signal_message).expect("signal message JSON"),
            ))
            .await;
        let body_cid = blob_ref.cid.to_multibase();
        let email_cid = crate::email_xrpc::signal_email_cid_for(
            sender_did,
            owner_did,
            "2026-06-02T00:00:00Z",
            &body_cid,
        );
        let email_cid_mb = email_cid.to_multibase();
        let tx_cid = mcp_tx_cid("email.read.signal.date-mismatch", &[owner_did]);
        let datoms = vec![
            ("email/message_id", email_cid_mb.clone()),
            ("email/body_cid", body_cid),
            ("email/date", "2026-06-03T00:00:00Z".to_string()),
            ("email/enc", ENC_SIGNAL_V1.to_string()),
        ]
        .into_iter()
        .map(|(predicate, object)| {
            KqeDatom::assert(
                email_cid.clone(),
                predicate.to_string(),
                KqeValue::Text(object),
                tx_cid.clone(),
            )
        })
        .collect();
        commit_mcp_datoms(
            &state,
            graph_cid,
            graph,
            email_cid.clone(),
            datoms,
            tx_cid,
            None,
        )
        .await
        .unwrap();

        let err = call_tool(
            MCP_TOOL_EMAIL_READ,
            &json!({ "owner_did": owner_did, "email_cid": email_cid_mb }),
            &state,
            None,
        )
        .await
        .unwrap_err();
        assert_eq!(err.0, ERR_INTERNAL);
        assert!(err.1.contains("timestamp"), "{err:?}");
        assert!(err.1.contains("email/date"), "{err:?}");
    }

    #[tokio::test]
    async fn call_tool_email_read_rejects_signal_routing_datoms_that_mismatch_envelope() {
        use kotoba_ingest::graph_cid_for;
        use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

        let state = test_state();
        let sender_did = "did:key:zMcpSignalRoutingSender";
        let owner_did = "did:key:zMcpSignalRoutingRecipient";
        let graph_cid = graph_cid_for(owner_did);
        let graph = graph_cid.to_multibase();
        let signal_message = json!({
            "messageType": "directMessage",
            "senderDid": sender_did,
            "recipientDid": owner_did,
            "deviceId": "device-1",
            "ciphertextEnvelope": "sealed-mime",
            "timestamp": "2026-06-02T00:00:00Z"
        });
        let blob_ref = state
            .vault
            .put(bytes::Bytes::from(
                serde_json::to_vec(&signal_message).expect("signal message JSON"),
            ))
            .await;
        let body_cid = blob_ref.cid.to_multibase();
        let email_cid = crate::email_xrpc::signal_email_cid_for(
            sender_did,
            owner_did,
            "2026-06-02T00:00:00Z",
            &body_cid,
        );
        let email_cid_mb = email_cid.to_multibase();
        let tx_cid = mcp_tx_cid("email.read.signal.routing-mismatch", &[owner_did]);
        let datoms = vec![
            ("email/message_id", email_cid_mb.clone()),
            (
                "email/from",
                "did:key:zMcpSignalRoutingOtherSender".to_string(),
            ),
            ("email/to", owner_did.to_string()),
            ("email/body_cid", body_cid),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
            ("email/enc", ENC_SIGNAL_V1.to_string()),
        ]
        .into_iter()
        .map(|(predicate, object)| {
            KqeDatom::assert(
                email_cid.clone(),
                predicate.to_string(),
                KqeValue::Text(object),
                tx_cid.clone(),
            )
        })
        .collect();
        commit_mcp_datoms(
            &state,
            graph_cid,
            graph,
            email_cid.clone(),
            datoms,
            tx_cid,
            None,
        )
        .await
        .unwrap();

        let err = call_tool(
            MCP_TOOL_EMAIL_READ,
            &json!({ "owner_did": owner_did, "email_cid": email_cid_mb }),
            &state,
            None,
        )
        .await
        .unwrap_err();
        assert_eq!(err.0, ERR_INTERNAL);
        assert!(err.1.contains("senderDid"), "{err:?}");
        assert!(err.1.contains("email/from"), "{err:?}");
    }

    #[tokio::test]
    async fn call_tool_email_read_rejects_signal_to_datom_that_mismatches_envelope() {
        use kotoba_ingest::graph_cid_for;
        use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

        let state = test_state();
        let sender_did = "did:key:zMcpSignalToSender";
        let owner_did = "did:key:zMcpSignalToRecipient";
        let graph_cid = graph_cid_for(owner_did);
        let graph = graph_cid.to_multibase();
        let signal_message = json!({
            "messageType": "directMessage",
            "senderDid": sender_did,
            "recipientDid": owner_did,
            "deviceId": "device-1",
            "ciphertextEnvelope": "sealed-mime",
            "timestamp": "2026-06-02T00:00:00Z"
        });
        let blob_ref = state
            .vault
            .put(bytes::Bytes::from(
                serde_json::to_vec(&signal_message).expect("signal message JSON"),
            ))
            .await;
        let body_cid = blob_ref.cid.to_multibase();
        let email_cid = crate::email_xrpc::signal_email_cid_for(
            sender_did,
            owner_did,
            "2026-06-02T00:00:00Z",
            &body_cid,
        );
        let email_cid_mb = email_cid.to_multibase();
        let tx_cid = mcp_tx_cid("email.read.signal.to-mismatch", &[owner_did]);
        let datoms = vec![
            ("email/message_id", email_cid_mb.clone()),
            ("email/from", sender_did.to_string()),
            ("email/to", "did:key:zMcpSignalOtherRecipient".to_string()),
            ("email/body_cid", body_cid),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
            ("email/enc", ENC_SIGNAL_V1.to_string()),
        ]
        .into_iter()
        .map(|(predicate, object)| {
            KqeDatom::assert(
                email_cid.clone(),
                predicate.to_string(),
                KqeValue::Text(object),
                tx_cid.clone(),
            )
        })
        .collect();
        commit_mcp_datoms(
            &state,
            graph_cid,
            graph,
            email_cid.clone(),
            datoms,
            tx_cid,
            None,
        )
        .await
        .unwrap();

        let err = call_tool(
            MCP_TOOL_EMAIL_READ,
            &json!({ "owner_did": owner_did, "email_cid": email_cid_mb }),
            &state,
            None,
        )
        .await
        .unwrap_err();
        assert_eq!(err.0, ERR_INTERNAL);
        assert!(err.1.contains("recipientDid"), "{err:?}");
        assert!(err.1.contains("email/to"), "{err:?}");
    }

    #[tokio::test]
    async fn call_tool_email_read_rejects_ambiguous_signal_from_routing_datoms() {
        use kotoba_ingest::graph_cid_for;
        use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

        let state = test_state();
        let sender_did = "did:key:zMcpSignalAmbiguousFromSender";
        let owner_did = "did:key:zMcpSignalAmbiguousFromRecipient";
        let graph_cid = graph_cid_for(owner_did);
        let graph = graph_cid.to_multibase();
        let signal_message = json!({
            "messageType": "directMessage",
            "senderDid": sender_did,
            "recipientDid": owner_did,
            "deviceId": "device-1",
            "ciphertextEnvelope": "sealed-mime",
            "timestamp": "2026-06-02T00:00:00Z"
        });
        let blob_ref = state
            .vault
            .put(bytes::Bytes::from(
                serde_json::to_vec(&signal_message).expect("signal message JSON"),
            ))
            .await;
        let body_cid = blob_ref.cid.to_multibase();
        let email_cid = crate::email_xrpc::signal_email_cid_for(
            sender_did,
            owner_did,
            "2026-06-02T00:00:00Z",
            &body_cid,
        );
        let email_cid_mb = email_cid.to_multibase();
        let tx_cid = mcp_tx_cid("email.read.signal.ambiguous-from", &[owner_did]);
        let datoms = vec![
            ("email/message_id", email_cid_mb.clone()),
            ("email/from", sender_did.to_string()),
            ("email/from", "did:key:zMcpSignalOtherSender".to_string()),
            ("email/to", owner_did.to_string()),
            ("email/body_cid", body_cid),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
            ("email/enc", ENC_SIGNAL_V1.to_string()),
        ]
        .into_iter()
        .map(|(predicate, object)| {
            KqeDatom::assert(
                email_cid.clone(),
                predicate.to_string(),
                KqeValue::Text(object),
                tx_cid.clone(),
            )
        })
        .collect();
        commit_mcp_datoms(
            &state,
            graph_cid,
            graph,
            email_cid.clone(),
            datoms,
            tx_cid,
            None,
        )
        .await
        .unwrap();

        let err = call_tool(
            MCP_TOOL_EMAIL_READ,
            &json!({ "owner_did": owner_did, "email_cid": email_cid_mb }),
            &state,
            None,
        )
        .await
        .unwrap_err();
        assert_eq!(err.0, ERR_INTERNAL);
        assert!(
            err.1.contains("multiple email/from values found"),
            "{err:?}"
        );
    }

    #[tokio::test]
    async fn call_tool_email_read_rejects_invalid_signal_from_routing_datom() {
        use kotoba_ingest::graph_cid_for;
        use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

        let state = test_state();
        let sender_did = "did:key:zMcpSignalInvalidFromSender";
        let owner_did = "did:key:zMcpSignalInvalidFromRecipient";
        let graph_cid = graph_cid_for(owner_did);
        let graph = graph_cid.to_multibase();
        let signal_message = json!({
            "messageType": "directMessage",
            "senderDid": sender_did,
            "recipientDid": owner_did,
            "deviceId": "device-1",
            "ciphertextEnvelope": "sealed-mime",
            "timestamp": "2026-06-02T00:00:00Z"
        });
        let blob_ref = state
            .vault
            .put(bytes::Bytes::from(
                serde_json::to_vec(&signal_message).expect("signal message JSON"),
            ))
            .await;
        let body_cid = blob_ref.cid.to_multibase();
        let email_cid = crate::email_xrpc::signal_email_cid_for(
            sender_did,
            owner_did,
            "2026-06-02T00:00:00Z",
            &body_cid,
        );
        let email_cid_mb = email_cid.to_multibase();
        let tx_cid = mcp_tx_cid("email.read.signal.invalid-from", &[owner_did]);
        let datoms = vec![
            ("email/message_id", email_cid_mb.clone()),
            ("email/from", "did:key:zMcpSignalInvalid\nFrom".to_string()),
            ("email/to", owner_did.to_string()),
            ("email/body_cid", body_cid),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
            ("email/enc", ENC_SIGNAL_V1.to_string()),
        ]
        .into_iter()
        .map(|(predicate, object)| {
            KqeDatom::assert(
                email_cid.clone(),
                predicate.to_string(),
                KqeValue::Text(object),
                tx_cid.clone(),
            )
        })
        .collect();
        commit_mcp_datoms(
            &state,
            graph_cid,
            graph,
            email_cid.clone(),
            datoms,
            tx_cid,
            None,
        )
        .await
        .unwrap();

        let err = call_tool(
            MCP_TOOL_EMAIL_READ,
            &json!({ "owner_did": owner_did, "email_cid": email_cid_mb }),
            &state,
            None,
        )
        .await
        .unwrap_err();
        assert_eq!(err.0, ERR_INTERNAL);
        assert!(err.1.contains("invalid email/from"), "{err:?}");
    }

    #[tokio::test]
    async fn call_tool_email_read_rejects_ambiguous_signal_to_routing_datoms() {
        use kotoba_ingest::graph_cid_for;
        use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

        let state = test_state();
        let sender_did = "did:key:zMcpSignalAmbiguousToSender";
        let owner_did = "did:key:zMcpSignalAmbiguousToRecipient";
        let graph_cid = graph_cid_for(owner_did);
        let graph = graph_cid.to_multibase();
        let signal_message = json!({
            "messageType": "directMessage",
            "senderDid": sender_did,
            "recipientDid": owner_did,
            "deviceId": "device-1",
            "ciphertextEnvelope": "sealed-mime",
            "timestamp": "2026-06-02T00:00:00Z"
        });
        let blob_ref = state
            .vault
            .put(bytes::Bytes::from(
                serde_json::to_vec(&signal_message).expect("signal message JSON"),
            ))
            .await;
        let body_cid = blob_ref.cid.to_multibase();
        let email_cid = crate::email_xrpc::signal_email_cid_for(
            sender_did,
            owner_did,
            "2026-06-02T00:00:00Z",
            &body_cid,
        );
        let email_cid_mb = email_cid.to_multibase();
        let tx_cid = mcp_tx_cid("email.read.signal.ambiguous-to", &[owner_did]);
        let datoms = vec![
            ("email/message_id", email_cid_mb.clone()),
            ("email/from", sender_did.to_string()),
            ("email/to", owner_did.to_string()),
            ("email/to", "did:key:zMcpSignalOtherRecipient".to_string()),
            ("email/body_cid", body_cid),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
            ("email/enc", ENC_SIGNAL_V1.to_string()),
        ]
        .into_iter()
        .map(|(predicate, object)| {
            KqeDatom::assert(
                email_cid.clone(),
                predicate.to_string(),
                KqeValue::Text(object),
                tx_cid.clone(),
            )
        })
        .collect();
        commit_mcp_datoms(
            &state,
            graph_cid,
            graph,
            email_cid.clone(),
            datoms,
            tx_cid,
            None,
        )
        .await
        .unwrap();

        let err = call_tool(
            MCP_TOOL_EMAIL_READ,
            &json!({ "owner_did": owner_did, "email_cid": email_cid_mb }),
            &state,
            None,
        )
        .await
        .unwrap_err();
        assert_eq!(err.0, ERR_INTERNAL);
        assert!(err.1.contains("multiple email/to values found"), "{err:?}");
    }

    #[tokio::test]
    async fn call_tool_email_read_rejects_invalid_signal_to_routing_datom() {
        use kotoba_ingest::graph_cid_for;
        use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

        let state = test_state();
        let sender_did = "did:key:zMcpSignalInvalidToSender";
        let owner_did = "did:key:zMcpSignalInvalidToRecipient";
        let graph_cid = graph_cid_for(owner_did);
        let graph = graph_cid.to_multibase();
        let signal_message = json!({
            "messageType": "directMessage",
            "senderDid": sender_did,
            "recipientDid": owner_did,
            "deviceId": "device-1",
            "ciphertextEnvelope": "sealed-mime",
            "timestamp": "2026-06-02T00:00:00Z"
        });
        let blob_ref = state
            .vault
            .put(bytes::Bytes::from(
                serde_json::to_vec(&signal_message).expect("signal message JSON"),
            ))
            .await;
        let body_cid = blob_ref.cid.to_multibase();
        let email_cid = crate::email_xrpc::signal_email_cid_for(
            sender_did,
            owner_did,
            "2026-06-02T00:00:00Z",
            &body_cid,
        );
        let email_cid_mb = email_cid.to_multibase();
        let tx_cid = mcp_tx_cid("email.read.signal.invalid-to", &[owner_did]);
        let datoms = vec![
            ("email/message_id", email_cid_mb.clone()),
            ("email/from", sender_did.to_string()),
            ("email/to", "did:key:zMcpSignalInvalid\nTo".to_string()),
            ("email/body_cid", body_cid),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
            ("email/enc", ENC_SIGNAL_V1.to_string()),
        ]
        .into_iter()
        .map(|(predicate, object)| {
            KqeDatom::assert(
                email_cid.clone(),
                predicate.to_string(),
                KqeValue::Text(object),
                tx_cid.clone(),
            )
        })
        .collect();
        commit_mcp_datoms(
            &state,
            graph_cid,
            graph,
            email_cid.clone(),
            datoms,
            tx_cid,
            None,
        )
        .await
        .unwrap();

        let err = call_tool(
            MCP_TOOL_EMAIL_READ,
            &json!({ "owner_did": owner_did, "email_cid": email_cid_mb }),
            &state,
            None,
        )
        .await
        .unwrap_err();
        assert_eq!(err.0, ERR_INTERNAL);
        assert!(err.1.contains("invalid email/to"), "{err:?}");
    }

    #[tokio::test]
    async fn call_tool_email_read_rejects_invalid_enc_before_legacy_crypto() {
        use kotoba_ingest::graph_cid_for;
        use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

        let state = test_state();
        assert!(
            state.crypto.is_none(),
            "test must prove invalid enc is rejected before legacy crypto"
        );
        let owner_did = "did:key:zMcpEmailReadInvalidEnc";
        let graph_cid = graph_cid_for(owner_did);
        let graph = graph_cid.to_multibase();
        let email_cid = KotobaCid::from_bytes(b"mcp-email-read-invalid-enc");
        let email_cid_mb = email_cid.to_multibase();
        let tx_cid = mcp_tx_cid("email.read.invalid-enc", &[owner_did]);
        let datoms = vec![
            ("email/message_id", email_cid_mb.clone()),
            (
                "email/body_cid",
                KotobaCid::from_bytes(b"mcp-invalid-enc-body").to_multibase(),
            ),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
            ("email/enc", "unknown:v1".to_string()),
        ]
        .into_iter()
        .map(|(predicate, object)| {
            KqeDatom::assert(
                email_cid.clone(),
                predicate.to_string(),
                KqeValue::Text(object),
                tx_cid.clone(),
            )
        })
        .collect();
        commit_mcp_datoms(
            &state,
            graph_cid,
            graph,
            email_cid.clone(),
            datoms,
            tx_cid,
            None,
        )
        .await
        .unwrap();

        let err = call_tool(
            MCP_TOOL_EMAIL_READ,
            &json!({ "owner_did": owner_did, "email_cid": email_cid_mb }),
            &state,
            None,
        )
        .await
        .unwrap_err();
        assert_eq!(err.0, ERR_INTERNAL);
        assert!(err.1.contains("invalid email/enc"), "{err:?}");
        assert!(!err.1.contains("crypto not initialised"), "{err:?}");
    }

    #[tokio::test]
    async fn call_tool_email_read_rejects_invalid_body_cid() {
        use kotoba_ingest::graph_cid_for;
        use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

        let state = test_state();
        let owner_did = "did:key:zMcpEmailReadInvalidBodyCid";
        let graph_cid = graph_cid_for(owner_did);
        let graph = graph_cid.to_multibase();
        let email_cid = KotobaCid::from_bytes(b"mcp-email-read-invalid-body-cid");
        let email_cid_mb = email_cid.to_multibase();
        let tx_cid = mcp_tx_cid("email.read.invalid-body-cid", &[owner_did]);
        let datoms = vec![
            ("email/message_id", email_cid_mb.clone()),
            ("email/body_cid", "not a multibase cid".to_string()),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
        ]
        .into_iter()
        .map(|(predicate, object)| {
            KqeDatom::assert(
                email_cid.clone(),
                predicate.to_string(),
                KqeValue::Text(object),
                tx_cid.clone(),
            )
        })
        .collect();
        commit_mcp_datoms(
            &state,
            graph_cid,
            graph,
            email_cid.clone(),
            datoms,
            tx_cid,
            None,
        )
        .await
        .unwrap();

        let err = call_tool(
            MCP_TOOL_EMAIL_READ,
            &json!({ "owner_did": owner_did, "email_cid": email_cid_mb }),
            &state,
            None,
        )
        .await
        .unwrap_err();
        assert_eq!(err.0, ERR_INTERNAL);
        assert!(err.1.contains("invalid body_cid multibase"), "{err:?}");
    }

    #[tokio::test]
    async fn call_tool_email_read_rejects_conflicting_body_cid_metadata() {
        let owner_did = "did:key:zMcpEmailReadConflictingBodyCid";
        let (state, _, email_cid_mb) = commit_legacy_email_fixture(
            owner_did,
            b"mcp-email-read-conflicting-body-cid",
            b"valid body",
            "email.read.conflicting-body-cid",
            [(
                "email/body_cid",
                KotobaCid::from_bytes(b"mcp-email-read-other-body-cid").to_multibase(),
            )],
        )
        .await;

        let err = call_tool(
            MCP_TOOL_EMAIL_READ,
            &json!({ "owner_did": owner_did, "email_cid": email_cid_mb }),
            &state,
            None,
        )
        .await
        .unwrap_err();
        assert_eq!(err.0, ERR_INTERNAL);
        assert!(
            err.1.contains("multiple email/body_cid values found"),
            "{err:?}"
        );
    }

    #[tokio::test]
    async fn call_tool_email_read_rejects_non_text_body_cid() {
        use kotoba_ingest::graph_cid_for;
        use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

        let state = test_state();
        let owner_did = "did:key:zMcpEmailReadNonTextBodyCid";
        let graph_cid = graph_cid_for(owner_did);
        let graph = graph_cid.to_multibase();
        let email_cid = KotobaCid::from_bytes(b"mcp-email-read-non-text-body-cid");
        let email_cid_mb = email_cid.to_multibase();
        let tx_cid = mcp_tx_cid("email.read.non-text-body-cid", &[owner_did]);
        let datoms = vec![
            KqeDatom::assert(
                email_cid.clone(),
                "email/message_id".to_string(),
                KqeValue::Text(email_cid_mb.clone()),
                tx_cid.clone(),
            ),
            KqeDatom::assert(
                email_cid.clone(),
                "email/body_cid".to_string(),
                KqeValue::Integer(1),
                tx_cid.clone(),
            ),
            KqeDatom::assert(
                email_cid.clone(),
                "email/date".to_string(),
                KqeValue::Text("2026-06-02T00:00:00Z".to_string()),
                tx_cid.clone(),
            ),
        ];
        commit_mcp_datoms(
            &state,
            graph_cid,
            graph,
            email_cid.clone(),
            datoms,
            tx_cid,
            None,
        )
        .await
        .unwrap();

        let err = call_tool(
            MCP_TOOL_EMAIL_READ,
            &json!({ "owner_did": owner_did, "email_cid": email_cid_mb }),
            &state,
            None,
        )
        .await
        .unwrap_err();
        assert_eq!(err.0, ERR_INTERNAL);
        assert!(err.1.contains("invalid body_cid multibase"), "{err:?}");
    }

    #[tokio::test]
    async fn call_tool_email_read_uses_latest_valid_date_metadata() {
        use kotoba_ingest::graph_cid_for;
        use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

        let state = test_state();
        let sender_did = "did:key:zMcpSignalLatestDateSender";
        let owner_did = "did:key:zMcpSignalLatestDateRecipient";
        let graph_cid = graph_cid_for(owner_did);
        let graph = graph_cid.to_multibase();
        let signal_message = json!({
            "messageType": "directMessage",
            "senderDid": sender_did,
            "recipientDid": owner_did,
            "deviceId": "device-1",
            "ciphertextEnvelope": "sealed-mime",
            "timestamp": "2026-06-02T00:00:00Z"
        });
        let blob_ref = state
            .vault
            .put(bytes::Bytes::from(
                serde_json::to_vec(&signal_message).expect("signal message JSON"),
            ))
            .await;
        let body_cid = blob_ref.cid.to_multibase();
        let email_cid = crate::email_xrpc::signal_email_cid_for(
            sender_did,
            owner_did,
            "2026-06-02T00:00:00Z",
            &body_cid,
        );
        let email_cid_mb = email_cid.to_multibase();
        let tx_cid = mcp_tx_cid("email.read.latest-date", &[owner_did]);
        let datoms = vec![
            ("email/message_id", email_cid_mb.clone()),
            ("email/from", sender_did.to_string()),
            ("email/to", owner_did.to_string()),
            ("email/body_cid", body_cid),
            ("email/date", "2026-06-01T00:00:00Z".to_string()),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
            ("email/enc", ENC_SIGNAL_V1.to_string()),
        ]
        .into_iter()
        .map(|(predicate, object)| {
            KqeDatom::assert(
                email_cid.clone(),
                predicate.to_string(),
                KqeValue::Text(object),
                tx_cid.clone(),
            )
        })
        .collect();
        commit_mcp_datoms(
            &state,
            graph_cid,
            graph,
            email_cid.clone(),
            datoms,
            tx_cid,
            None,
        )
        .await
        .unwrap();

        let value = call_tool(
            MCP_TOOL_EMAIL_READ,
            &json!({ "owner_did": owner_did, "email_cid": email_cid_mb }),
            &state,
            None,
        )
        .await
        .unwrap();
        assert_eq!(value["date"], "2026-06-02T00:00:00Z", "{value}");
        assert_eq!(value["signalMessage"], signal_message, "{value}");
    }

    #[tokio::test]
    async fn call_tool_email_read_skips_invalid_date_metadata() {
        use kotoba_ingest::graph_cid_for;
        use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

        let state = test_state();
        let sender_did = "did:key:zMcpSignalInvalidDateSender";
        let owner_did = "did:key:zMcpSignalInvalidDateRecipient";
        let graph_cid = graph_cid_for(owner_did);
        let graph = graph_cid.to_multibase();
        let signal_message = json!({
            "messageType": "directMessage",
            "senderDid": sender_did,
            "recipientDid": owner_did,
            "deviceId": "device-1",
            "ciphertextEnvelope": "sealed-mime",
            "timestamp": "2026-06-02T00:00:00Z"
        });
        let blob_ref = state
            .vault
            .put(bytes::Bytes::from(
                serde_json::to_vec(&signal_message).expect("signal message JSON"),
            ))
            .await;
        let body_cid = blob_ref.cid.to_multibase();
        let email_cid = crate::email_xrpc::signal_email_cid_for(
            sender_did,
            owner_did,
            "2026-06-02T00:00:00Z",
            &body_cid,
        );
        let email_cid_mb = email_cid.to_multibase();
        let tx_cid = mcp_tx_cid("email.read.invalid-date", &[owner_did]);
        let datoms = vec![
            ("email/message_id", email_cid_mb.clone()),
            ("email/from", sender_did.to_string()),
            ("email/to", owner_did.to_string()),
            ("email/body_cid", body_cid),
            ("email/date", "2026-06-02\n00:00:00Z".to_string()),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
            ("email/enc", ENC_SIGNAL_V1.to_string()),
        ]
        .into_iter()
        .map(|(predicate, object)| {
            KqeDatom::assert(
                email_cid.clone(),
                predicate.to_string(),
                KqeValue::Text(object),
                tx_cid.clone(),
            )
        })
        .collect();
        commit_mcp_datoms(
            &state,
            graph_cid,
            graph,
            email_cid.clone(),
            datoms,
            tx_cid,
            None,
        )
        .await
        .unwrap();

        let value = call_tool(
            MCP_TOOL_EMAIL_READ,
            &json!({ "owner_did": owner_did, "email_cid": email_cid_mb }),
            &state,
            None,
        )
        .await
        .unwrap();
        assert_eq!(value["date"], "2026-06-02T00:00:00Z", "{value}");
        assert_eq!(value["signalMessage"], signal_message, "{value}");
    }

    #[tokio::test]
    async fn call_tool_email_read_skips_oversized_date_metadata() {
        use kotoba_ingest::graph_cid_for;
        use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

        let state = test_state();
        let sender_did = "did:key:zMcpSignalOversizedDateSender";
        let owner_did = "did:key:zMcpSignalOversizedDateRecipient";
        let graph_cid = graph_cid_for(owner_did);
        let graph = graph_cid.to_multibase();
        let signal_message = json!({
            "messageType": "directMessage",
            "senderDid": sender_did,
            "recipientDid": owner_did,
            "deviceId": "device-1",
            "ciphertextEnvelope": "sealed-mime",
            "timestamp": "2026-06-02T00:00:00Z"
        });
        let blob_ref = state
            .vault
            .put(bytes::Bytes::from(
                serde_json::to_vec(&signal_message).expect("signal message JSON"),
            ))
            .await;
        let body_cid = blob_ref.cid.to_multibase();
        let email_cid = crate::email_xrpc::signal_email_cid_for(
            sender_did,
            owner_did,
            "2026-06-02T00:00:00Z",
            &body_cid,
        );
        let email_cid_mb = email_cid.to_multibase();
        let tx_cid = mcp_tx_cid("email.read.oversized-date", &[owner_did]);
        let datoms = vec![
            ("email/message_id", email_cid_mb.clone()),
            ("email/from", sender_did.to_string()),
            ("email/to", owner_did.to_string()),
            ("email/body_cid", body_cid),
            ("email/date", "x".repeat(MAX_EMAIL_DATE_LEN + 1)),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
            ("email/enc", ENC_SIGNAL_V1.to_string()),
        ]
        .into_iter()
        .map(|(predicate, object)| {
            KqeDatom::assert(
                email_cid.clone(),
                predicate.to_string(),
                KqeValue::Text(object),
                tx_cid.clone(),
            )
        })
        .collect();
        commit_mcp_datoms(
            &state,
            graph_cid,
            graph,
            email_cid.clone(),
            datoms,
            tx_cid,
            None,
        )
        .await
        .unwrap();

        let value = call_tool(
            MCP_TOOL_EMAIL_READ,
            &json!({ "owner_did": owner_did, "email_cid": email_cid_mb }),
            &state,
            None,
        )
        .await
        .unwrap();
        assert_eq!(value["date"], "2026-06-02T00:00:00Z", "{value}");
        assert_eq!(value["signalMessage"], signal_message, "{value}");
    }

    #[tokio::test]
    async fn call_tool_email_read_rejects_oversized_date_as_missing_record() {
        use kotoba_ingest::graph_cid_for;
        use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

        let state = test_state();
        let owner_did = "did:key:zMcpEmailReadOversizedDateOnly";
        let graph_cid = graph_cid_for(owner_did);
        let graph = graph_cid.to_multibase();
        let email_cid = KotobaCid::from_bytes(b"mcp-email-read-oversized-date-only");
        let email_cid_mb = email_cid.to_multibase();
        let body_cid = KotobaCid::from_bytes(b"mcp-email-read-oversized-date-body").to_multibase();
        let tx_cid = mcp_tx_cid("email.read.oversized-date-only", &[owner_did]);
        let datoms = vec![
            ("email/message_id", email_cid_mb.clone()),
            ("email/body_cid", body_cid),
            ("email/date", "x".repeat(MAX_EMAIL_DATE_LEN + 1)),
        ]
        .into_iter()
        .map(|(predicate, object)| {
            KqeDatom::assert(
                email_cid.clone(),
                predicate.to_string(),
                KqeValue::Text(object),
                tx_cid.clone(),
            )
        })
        .collect();
        commit_mcp_datoms(
            &state,
            graph_cid,
            graph,
            email_cid.clone(),
            datoms,
            tx_cid,
            None,
        )
        .await
        .unwrap();

        let result = call_tool(
            MCP_TOOL_EMAIL_READ,
            &json!({ "owner_did": owner_did, "email_cid": email_cid_mb }),
            &state,
            None,
        )
        .await;
        let (code, msg) = result.unwrap_err();
        assert_eq!(code, ERR_NOT_FOUND);
        assert!(
            msg.contains("email_cid not found in mailbox"),
            "unexpected error: {msg}"
        );
    }

    #[tokio::test]
    async fn call_tool_email_read_rejects_multiple_body_cids() {
        use kotoba_ingest::graph_cid_for;
        use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

        let state = test_state();
        let owner_did = "did:key:zMcpEmailReadMultipleBodyCids";
        let graph_cid = graph_cid_for(owner_did);
        let graph = graph_cid.to_multibase();
        let email_cid = KotobaCid::from_bytes(b"mcp-email-read-multiple-body-cids");
        let email_cid_mb = email_cid.to_multibase();
        let tx_cid = mcp_tx_cid("email.read.multiple-body-cids", &[owner_did]);
        let datoms = vec![
            ("email/message_id", email_cid_mb.clone()),
            (
                "email/body_cid",
                KotobaCid::from_bytes(b"mcp-body-cid-a").to_multibase(),
            ),
            (
                "email/body_cid",
                KotobaCid::from_bytes(b"mcp-body-cid-b").to_multibase(),
            ),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
        ]
        .into_iter()
        .map(|(predicate, object)| {
            KqeDatom::assert(
                email_cid.clone(),
                predicate.to_string(),
                KqeValue::Text(object),
                tx_cid.clone(),
            )
        })
        .collect();
        commit_mcp_datoms(
            &state,
            graph_cid,
            graph,
            email_cid.clone(),
            datoms,
            tx_cid,
            None,
        )
        .await
        .unwrap();

        let err = call_tool(
            MCP_TOOL_EMAIL_READ,
            &json!({ "owner_did": owner_did, "email_cid": email_cid_mb }),
            &state,
            None,
        )
        .await
        .unwrap_err();
        assert_eq!(err.0, ERR_INTERNAL);
        assert!(
            err.1.contains("multiple email/body_cid values found"),
            "{err:?}"
        );
    }

    #[tokio::test]
    async fn call_tool_email_read_rejects_mixed_signal_and_invalid_enc() {
        use kotoba_ingest::graph_cid_for;
        use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

        let state = test_state();
        let owner_did = "did:key:zMcpEmailReadMixedEnc";
        let graph_cid = graph_cid_for(owner_did);
        let graph = graph_cid.to_multibase();
        let email_cid = KotobaCid::from_bytes(b"mcp-email-read-mixed-enc");
        let email_cid_mb = email_cid.to_multibase();
        let tx_cid = mcp_tx_cid("email.read.mixed-enc", &[owner_did]);
        let datoms = vec![
            ("email/message_id", email_cid_mb.clone()),
            (
                "email/body_cid",
                KotobaCid::from_bytes(b"mcp-mixed-enc-body").to_multibase(),
            ),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
            ("email/enc", ENC_SIGNAL_V1.to_string()),
            ("email/enc", "unknown:v1".to_string()),
        ]
        .into_iter()
        .map(|(predicate, object)| {
            KqeDatom::assert(
                email_cid.clone(),
                predicate.to_string(),
                KqeValue::Text(object),
                tx_cid.clone(),
            )
        })
        .collect();
        commit_mcp_datoms(
            &state,
            graph_cid,
            graph,
            email_cid.clone(),
            datoms,
            tx_cid,
            None,
        )
        .await
        .unwrap();

        let err = call_tool(
            MCP_TOOL_EMAIL_READ,
            &json!({ "owner_did": owner_did, "email_cid": email_cid_mb }),
            &state,
            None,
        )
        .await
        .unwrap_err();
        assert_eq!(err.0, ERR_INTERNAL);
        assert!(err.1.contains("invalid email/enc"), "{err:?}");
    }

    #[tokio::test]
    async fn call_tool_email_read_rejects_non_text_enc() {
        use kotoba_ingest::graph_cid_for;
        use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

        let state = test_state();
        let owner_did = "did:key:zMcpEmailReadNonTextEnc";
        let graph_cid = graph_cid_for(owner_did);
        let graph = graph_cid.to_multibase();
        let email_cid = KotobaCid::from_bytes(b"mcp-email-read-non-text-enc");
        let email_cid_mb = email_cid.to_multibase();
        let tx_cid = mcp_tx_cid("email.read.non-text-enc", &[owner_did]);
        let datoms = vec![
            KqeDatom::assert(
                email_cid.clone(),
                "email/message_id".to_string(),
                KqeValue::Text(email_cid_mb.clone()),
                tx_cid.clone(),
            ),
            KqeDatom::assert(
                email_cid.clone(),
                "email/body_cid".to_string(),
                KqeValue::Text(KotobaCid::from_bytes(b"mcp-non-text-enc-body").to_multibase()),
                tx_cid.clone(),
            ),
            KqeDatom::assert(
                email_cid.clone(),
                "email/date".to_string(),
                KqeValue::Text("2026-06-02T00:00:00Z".to_string()),
                tx_cid.clone(),
            ),
            KqeDatom::assert(
                email_cid.clone(),
                "email/enc".to_string(),
                KqeValue::Integer(1),
                tx_cid.clone(),
            ),
        ];
        commit_mcp_datoms(
            &state,
            graph_cid,
            graph,
            email_cid.clone(),
            datoms,
            tx_cid,
            None,
        )
        .await
        .unwrap();

        let err = call_tool(
            MCP_TOOL_EMAIL_READ,
            &json!({ "owner_did": owner_did, "email_cid": email_cid_mb }),
            &state,
            None,
        )
        .await
        .unwrap_err();
        assert_eq!(err.0, ERR_INTERNAL);
        assert!(err.1.contains("invalid email/enc"), "{err:?}");
    }

    #[tokio::test]
    async fn call_tool_email_read_rejects_signal_body_cid_swapped_after_send() {
        use kotoba_ingest::graph_cid_for;
        use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

        let state = test_state();
        let sender_did = "did:key:zMcpSignalBodySender";
        let owner_did = "did:key:zMcpSignalBodyRecipient";
        let graph_cid = graph_cid_for(owner_did);
        let graph = graph_cid.to_multibase();
        let signal_message = json!({
            "messageType": "directMessage",
            "senderDid": sender_did,
            "recipientDid": owner_did,
            "deviceId": "device-1",
            "ciphertextEnvelope": "sealed-mime",
            "timestamp": "2026-06-02T00:00:00Z"
        });
        let original_blob = state
            .vault
            .put(bytes::Bytes::from(
                serde_json::to_vec(&signal_message).expect("signal message JSON"),
            ))
            .await;
        let mut swapped_message = signal_message.clone();
        swapped_message["ciphertextEnvelope"] = json!("sealed-mime-swapped");
        let swapped_blob = state
            .vault
            .put(bytes::Bytes::from(
                serde_json::to_vec(&swapped_message).expect("signal message JSON"),
            ))
            .await;
        let original_body_cid = original_blob.cid.to_multibase();
        let swapped_body_cid = swapped_blob.cid.to_multibase();
        let email_cid = crate::email_xrpc::signal_email_cid_for(
            sender_did,
            owner_did,
            "2026-06-02T00:00:00Z",
            &original_body_cid,
        );
        let email_cid_mb = email_cid.to_multibase();
        let tx_cid = mcp_tx_cid("email.read.signal.body-cid-swap", &[owner_did]);
        let datoms = vec![
            ("email/message_id", email_cid_mb.clone()),
            ("email/body_cid", swapped_body_cid),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
            ("email/enc", ENC_SIGNAL_V1.to_string()),
        ]
        .into_iter()
        .map(|(predicate, object)| {
            KqeDatom::assert(
                email_cid.clone(),
                predicate.to_string(),
                KqeValue::Text(object),
                tx_cid.clone(),
            )
        })
        .collect();
        commit_mcp_datoms(
            &state,
            graph_cid,
            graph,
            email_cid.clone(),
            datoms,
            tx_cid,
            None,
        )
        .await
        .unwrap();

        let err = call_tool(
            MCP_TOOL_EMAIL_READ,
            &json!({ "owner_did": owner_did, "email_cid": email_cid_mb }),
            &state,
            None,
        )
        .await
        .unwrap_err();
        assert_eq!(err.0, ERR_INTERNAL);
        assert!(err.1.contains("body_cid"), "{err:?}");
        assert!(err.1.contains("email_cid"), "{err:?}");
    }

    #[tokio::test]
    async fn call_tool_email_read_rejects_corrupt_signal_envelope_blob() {
        use kotoba_ingest::graph_cid_for;
        use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

        let state = test_state();
        let owner_did = "did:key:zMcpSignalCorruptEnvelope";
        let graph_cid = graph_cid_for(owner_did);
        let graph = graph_cid.to_multibase();
        let email_cid = KotobaCid::from_bytes(b"mcp-signal-corrupt-envelope");
        let email_cid_mb = email_cid.to_multibase();
        let blob_ref = state
            .vault
            .put(bytes::Bytes::from_static(b"not-json"))
            .await;
        let tx_cid = mcp_tx_cid("email.read.signal.corrupt", &[owner_did]);
        let datoms = vec![
            ("email/message_id", email_cid_mb.clone()),
            ("email/body_cid", blob_ref.cid.to_multibase()),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
            ("email/enc", ENC_SIGNAL_V1.to_string()),
        ]
        .into_iter()
        .map(|(predicate, object)| {
            KqeDatom::assert(
                email_cid.clone(),
                predicate.to_string(),
                KqeValue::Text(object),
                tx_cid.clone(),
            )
        })
        .collect();
        commit_mcp_datoms(
            &state,
            graph_cid,
            graph,
            email_cid.clone(),
            datoms,
            tx_cid,
            None,
        )
        .await
        .unwrap();

        let result = call_tool(
            MCP_TOOL_EMAIL_READ,
            &json!({ "owner_did": owner_did, "email_cid": email_cid_mb }),
            &state,
            None,
        )
        .await;
        let (code, msg) = result.unwrap_err();
        assert_eq!(code, ERR_INTERNAL);
        assert!(
            msg.contains("invalid signal envelope JSON"),
            "unexpected error: {msg}"
        );
    }

    #[tokio::test]
    async fn call_tool_email_read_rejects_malformed_signal_envelope_object() {
        use kotoba_ingest::graph_cid_for;
        use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

        let state = test_state();
        let owner_did = "did:key:zMcpSignalMalformedEnvelope";
        let graph_cid = graph_cid_for(owner_did);
        let graph = graph_cid.to_multibase();
        let email_cid = KotobaCid::from_bytes(b"mcp-signal-malformed-envelope");
        let email_cid_mb = email_cid.to_multibase();
        let blob_ref = state
            .vault
            .put(bytes::Bytes::from_static(
                br#"{"messageType":"directMessage"}"#,
            ))
            .await;
        let tx_cid = mcp_tx_cid("email.read.signal.malformed", &[owner_did]);
        let datoms = vec![
            ("email/message_id", email_cid_mb.clone()),
            ("email/body_cid", blob_ref.cid.to_multibase()),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
            ("email/enc", ENC_SIGNAL_V1.to_string()),
        ]
        .into_iter()
        .map(|(predicate, object)| {
            KqeDatom::assert(
                email_cid.clone(),
                predicate.to_string(),
                KqeValue::Text(object),
                tx_cid.clone(),
            )
        })
        .collect();
        commit_mcp_datoms(
            &state,
            graph_cid,
            graph,
            email_cid.clone(),
            datoms,
            tx_cid,
            None,
        )
        .await
        .unwrap();

        let result = call_tool(
            MCP_TOOL_EMAIL_READ,
            &json!({ "owner_did": owner_did, "email_cid": email_cid_mb }),
            &state,
            None,
        )
        .await;
        let (code, msg) = result.unwrap_err();
        assert_eq!(code, ERR_INTERNAL);
        assert!(
            msg.contains("invalid signal envelope JSON"),
            "unexpected error: {msg}"
        );
    }

    #[tokio::test]
    async fn call_tool_email_read_rejects_policy_invalid_signal_envelope() {
        use kotoba_ingest::graph_cid_for;
        use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

        let state = test_state();
        let owner_did = "did:key:zMcpSignalPolicyInvalidEnvelope";
        let graph_cid = graph_cid_for(owner_did);
        let graph = graph_cid.to_multibase();
        let email_cid = KotobaCid::from_bytes(b"mcp-signal-policy-invalid-envelope");
        let email_cid_mb = email_cid.to_multibase();
        let signal_message = json!({
            "messageType": "directMessage",
            "senderDid": "did:key:zSender",
            "recipientDid": owner_did,
            "deviceId": "device-1",
            "ciphertextEnvelope": "",
            "timestamp": "2026-06-02T00:00:00Z"
        });
        let blob_ref = state
            .vault
            .put(bytes::Bytes::from(
                serde_json::to_vec(&signal_message).expect("signal message JSON"),
            ))
            .await;
        let tx_cid = mcp_tx_cid("email.read.signal.policy-invalid", &[owner_did]);
        let datoms = vec![
            ("email/message_id", email_cid_mb.clone()),
            ("email/body_cid", blob_ref.cid.to_multibase()),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
            ("email/enc", ENC_SIGNAL_V1.to_string()),
        ]
        .into_iter()
        .map(|(predicate, object)| {
            KqeDatom::assert(
                email_cid.clone(),
                predicate.to_string(),
                KqeValue::Text(object),
                tx_cid.clone(),
            )
        })
        .collect();
        commit_mcp_datoms(
            &state,
            graph_cid,
            graph,
            email_cid.clone(),
            datoms,
            tx_cid,
            None,
        )
        .await
        .unwrap();

        let result = call_tool(
            MCP_TOOL_EMAIL_READ,
            &json!({ "owner_did": owner_did, "email_cid": email_cid_mb }),
            &state,
            None,
        )
        .await;
        let (code, msg) = result.unwrap_err();
        assert_eq!(code, ERR_INTERNAL);
        assert!(msg.contains("invalid signal envelope JSON"));
        assert!(msg.contains("ciphertextEnvelope"));
    }

    #[tokio::test]
    async fn call_tool_email_read_rejects_group_message_without_group_id() {
        use kotoba_ingest::graph_cid_for;
        use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

        let state = test_state();
        let owner_did = "did:key:zMcpSignalGroupMissingGroupId";
        let graph_cid = graph_cid_for(owner_did);
        let graph = graph_cid.to_multibase();
        let email_cid = KotobaCid::from_bytes(b"mcp-signal-group-missing-group-id");
        let email_cid_mb = email_cid.to_multibase();
        let signal_message = json!({
            "messageType": "groupMessage",
            "senderDid": "did:key:zSender",
            "recipientDid": owner_did,
            "deviceId": "device-1",
            "ciphertextEnvelope": "c2VhbGVk",
            "timestamp": "2026-06-02T00:00:00Z"
        });
        let blob_ref = state
            .vault
            .put(bytes::Bytes::from(
                serde_json::to_vec(&signal_message).expect("signal message JSON"),
            ))
            .await;
        let tx_cid = mcp_tx_cid("email.read.signal.group-missing-group-id", &[owner_did]);
        let datoms = vec![
            ("email/message_id", email_cid_mb.clone()),
            ("email/body_cid", blob_ref.cid.to_multibase()),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
            ("email/enc", ENC_SIGNAL_V1.to_string()),
        ]
        .into_iter()
        .map(|(predicate, object)| {
            KqeDatom::assert(
                email_cid.clone(),
                predicate.to_string(),
                KqeValue::Text(object),
                tx_cid.clone(),
            )
        })
        .collect();
        commit_mcp_datoms(
            &state,
            graph_cid,
            graph,
            email_cid.clone(),
            datoms,
            tx_cid,
            None,
        )
        .await
        .unwrap();

        let result = call_tool(
            MCP_TOOL_EMAIL_READ,
            &json!({ "owner_did": owner_did, "email_cid": email_cid_mb }),
            &state,
            None,
        )
        .await;
        let (code, msg) = result.unwrap_err();
        assert_eq!(code, ERR_INTERNAL);
        assert!(msg.contains("invalid signal envelope JSON"));
        assert!(msg.contains("groupId"));
    }

    #[tokio::test]
    async fn call_tool_email_read_signal_mail_without_body_cid_returns_not_found() {
        use kotoba_ingest::graph_cid_for;
        use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

        let state = test_state();
        let owner_did = "did:key:zMcpSignalMissingBodyCid";
        let graph_cid = graph_cid_for(owner_did);
        let graph = graph_cid.to_multibase();
        let email_cid = KotobaCid::from_bytes(b"mcp-signal-missing-body-cid");
        let email_cid_mb = email_cid.to_multibase();
        let tx_cid = mcp_tx_cid("email.read.signal.missing-body", &[owner_did]);
        let datoms = vec![
            ("email/message_id", email_cid_mb.clone()),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
            ("email/enc", ENC_SIGNAL_V1.to_string()),
        ]
        .into_iter()
        .map(|(predicate, object)| {
            KqeDatom::assert(
                email_cid.clone(),
                predicate.to_string(),
                KqeValue::Text(object),
                tx_cid.clone(),
            )
        })
        .collect();
        commit_mcp_datoms(
            &state,
            graph_cid,
            graph,
            email_cid.clone(),
            datoms,
            tx_cid,
            None,
        )
        .await
        .unwrap();

        let result = call_tool(
            MCP_TOOL_EMAIL_READ,
            &json!({ "owner_did": owner_did, "email_cid": email_cid_mb }),
            &state,
            None,
        )
        .await;
        let (code, msg) = result.unwrap_err();
        assert_eq!(code, ERR_NOT_FOUND);
        assert!(
            msg.contains("email/body_cid not found"),
            "unexpected error: {msg}"
        );
    }

    #[tokio::test]
    async fn call_tool_email_read_missing_email_cid_returns_not_found_before_body_lookup() {
        use kotoba_ingest::graph_cid_for;
        use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

        let state = test_state();
        let owner_did = "did:key:zMcpEmailReadMissingCid";
        let graph_cid = graph_cid_for(owner_did);
        let graph = graph_cid.to_multibase();
        let existing_email_cid = KotobaCid::from_bytes(b"mcp-existing-email-cid");
        let missing_email_cid = KotobaCid::from_bytes(b"mcp-missing-email-cid");
        let tx_cid = mcp_tx_cid("email.read.missing-cid", &[owner_did]);
        let datoms = vec![
            KqeDatom::assert(
                existing_email_cid.clone(),
                "email/message_id".to_string(),
                KqeValue::Text(existing_email_cid.to_multibase()),
                tx_cid.clone(),
            ),
            KqeDatom::assert(
                existing_email_cid.clone(),
                "email/date".to_string(),
                KqeValue::Text("2026-06-02T00:00:00Z".to_string()),
                tx_cid.clone(),
            ),
            KqeDatom::assert(
                existing_email_cid.clone(),
                "email/body_cid".to_string(),
                KqeValue::Text(KotobaCid::from_bytes(b"body").to_multibase()),
                tx_cid.clone(),
            ),
        ];
        commit_mcp_datoms(
            &state,
            graph_cid,
            graph,
            existing_email_cid,
            datoms,
            tx_cid,
            None,
        )
        .await
        .unwrap();

        let result = call_tool(
            MCP_TOOL_EMAIL_READ,
            &json!({
                "owner_did": owner_did,
                "email_cid": missing_email_cid.to_multibase()
            }),
            &state,
            None,
        )
        .await;
        let (code, msg) = result.unwrap_err();
        assert_eq!(code, ERR_NOT_FOUND);
        assert!(
            msg.contains("email_cid not found in mailbox"),
            "unexpected error: {msg}"
        );
    }

    #[tokio::test]
    async fn call_tool_email_read_ignores_non_email_subject_datoms_when_checking_existence() {
        use kotoba_ingest::graph_cid_for;
        use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

        let state = test_state();
        let owner_did = "did:key:zMcpEmailReadNonEmailSubject";
        let graph_cid = graph_cid_for(owner_did);
        let graph = graph_cid.to_multibase();
        let cid = KotobaCid::from_bytes(b"mcp-non-email-subject");
        let tx_cid = mcp_tx_cid("email.read.non-email-subject", &[owner_did]);
        let datoms = vec![KqeDatom::assert(
            cid.clone(),
            "profile/name".to_string(),
            KqeValue::Text("not an email".to_string()),
            tx_cid.clone(),
        )];
        commit_mcp_datoms(&state, graph_cid, graph, cid.clone(), datoms, tx_cid, None)
            .await
            .unwrap();

        let result = call_tool(
            MCP_TOOL_EMAIL_READ,
            &json!({
                "owner_did": owner_did,
                "email_cid": cid.to_multibase()
            }),
            &state,
            None,
        )
        .await;
        let (code, msg) = result.unwrap_err();
        assert_eq!(code, ERR_NOT_FOUND);
        assert!(
            msg.contains("email_cid not found in mailbox"),
            "unexpected error: {msg}"
        );
    }

    #[tokio::test]
    async fn call_tool_email_read_ignores_enc_only_subject_when_checking_existence() {
        use kotoba_ingest::graph_cid_for;
        use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

        let state = test_state();
        let owner_did = "did:key:zMcpEmailReadEncOnlySubject";
        let graph_cid = graph_cid_for(owner_did);
        let graph = graph_cid.to_multibase();
        let cid = KotobaCid::from_bytes(b"mcp-enc-only-subject");
        let tx_cid = mcp_tx_cid("email.read.enc-only-subject", &[owner_did]);
        let datoms = vec![KqeDatom::assert(
            cid.clone(),
            "email/enc".to_string(),
            KqeValue::Text(ENC_SIGNAL_V1.to_string()),
            tx_cid.clone(),
        )];
        commit_mcp_datoms(&state, graph_cid, graph, cid.clone(), datoms, tx_cid, None)
            .await
            .unwrap();

        let result = call_tool(
            MCP_TOOL_EMAIL_READ,
            &json!({
                "owner_did": owner_did,
                "email_cid": cid.to_multibase()
            }),
            &state,
            None,
        )
        .await;
        let (code, msg) = result.unwrap_err();
        assert_eq!(code, ERR_NOT_FOUND);
        assert!(
            msg.contains("email_cid not found in mailbox"),
            "unexpected error: {msg}"
        );
    }

    #[tokio::test]
    async fn call_tool_sparql_query_invalid_cacao_b64_errors() {
        let state = test_state();
        let result = call_tool(
            MCP_TOOL_SPARQL_QUERY,
            &json!({
                "graph":     "graph1",
                "sparql":    "SELECT ?s WHERE { ?s <role> \"admin\" }",
                "cacao_b64": "not-valid-base64!!!"
            }),
            &state,
            None,
        )
        .await;
        let (code, _) = result.unwrap_err();
        assert_eq!(code, ERR_INVALID_PARAMS);
    }

    // ── kotoba_multi_hop ─────────────────────────────────────────────────────

    #[tokio::test]
    async fn call_tool_multi_hop_missing_graph_errors() {
        let state = test_state();
        let result = call_tool(
            MCP_TOOL_MULTI_HOP,
            &json!({
                "start": "start-cid"
            }),
            &state,
            None,
        )
        .await;
        let (code, _) = result.unwrap_err();
        assert_eq!(code, ERR_INVALID_PARAMS);
    }

    #[tokio::test]
    async fn call_tool_multi_hop_missing_start_errors() {
        let state = test_state();
        let result = call_tool(
            MCP_TOOL_MULTI_HOP,
            &json!({
                "graph": "graph1"
            }),
            &state,
            None,
        )
        .await;
        let (code, _) = result.unwrap_err();
        assert_eq!(code, ERR_INVALID_PARAMS);
    }

    #[tokio::test]
    async fn call_tool_multi_hop_empty_graph_returns_empty() {
        let state = test_state();
        let result = call_tool(
            MCP_TOOL_MULTI_HOP,
            &json!({
                "graph": "empty-graph-cid",
                "start": "start-cid"
            }),
            &state,
            None,
        )
        .await;
        assert!(result.is_ok(), "{result:?}");
        let v = result.unwrap();
        assert_eq!(v["count"], 0);
        assert!(v["hops"].is_array());
    }

    #[tokio::test]
    async fn call_tool_multi_hop_max_hops_clamped_to_8() {
        let state = test_state();
        // max_hops=100 should be silently clamped to 8 (no error)
        let result = call_tool(
            MCP_TOOL_MULTI_HOP,
            &json!({
                "graph":    "empty-graph-cid",
                "start":    "start-cid",
                "max_hops": 100
            }),
            &state,
            None,
        )
        .await;
        assert!(result.is_ok(), "{result:?}");
    }

    #[tokio::test]
    async fn call_tool_multi_hop_invalid_cacao_b64_errors() {
        let state = test_state();
        let result = call_tool(
            MCP_TOOL_MULTI_HOP,
            &json!({
                "graph":     "graph1",
                "start":     "start-cid",
                "cacao_b64": "!!not-base64!!"
            }),
            &state,
            None,
        )
        .await;
        let (code, _) = result.unwrap_err();
        assert_eq!(code, ERR_INVALID_PARAMS);
    }
}
