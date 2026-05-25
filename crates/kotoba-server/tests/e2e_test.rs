//! E2E integration tests for kotoba-server.
//!
//! Each test spawns the axum router on a random OS-assigned port, fires HTTP
//! requests with `reqwest`, and asserts on the JSON response.  The server is
//! dropped at the end of each test via a tokio `JoinHandle` abort.
//!
//! A deterministic stub `InferenceFn` satisfies agent.run / infer.run so these
//! tests run without a real LLM or network dependency.

use std::sync::Arc;

use kotoba_server::{build_router, server::KotobaState};
use serde_json::{json, Value};

// ── Stub inference engine ─────────────────────────────────────────────────────

fn stub_engine() -> kotoba_runtime::host::InferenceFn {
    Arc::new(|prompt: &str, _max: usize| -> anyhow::Result<String> {
        if prompt.contains("Thought") || prompt.is_empty() {
            Ok("Thought: done.\nAction: Finish[stub answer]".into())
        } else {
            Ok(format!("stub: {prompt}"))
        }
    })
}

// ── Server fixture ────────────────────────────────────────────────────────────

struct TestServer {
    base_url: String,
    handle:   tokio::task::JoinHandle<()>,
    client:   reqwest::Client,
}

impl TestServer {
    async fn start(with_inference: bool) -> Self {
        let engine = if with_inference { Some(stub_engine()) } else { None };
        let state  = KotobaState::new(engine).expect("KotobaState::new");
        let app    = build_router(Arc::new(state));

        let listener = tokio::net::TcpListener::bind("127.0.0.1:0")
            .await
            .expect("bind");
        let port = listener.local_addr().unwrap().port();
        let base_url = format!("http://127.0.0.1:{port}");

        let handle = tokio::spawn(async move {
            axum::serve(listener, app).await.ok();
        });

        // brief settle — axum::serve is ready immediately after spawn
        tokio::time::sleep(std::time::Duration::from_millis(5)).await;

        Self {
            base_url,
            handle,
            client: reqwest::Client::new(),
        }
    }

    async fn get(&self, path: &str) -> (u16, Value) {
        let r = self.client
            .get(format!("{}{}", self.base_url, path))
            .send()
            .await
            .expect("GET");
        let status = r.status().as_u16();
        let body: Value = r.json().await.unwrap_or(Value::Null);
        (status, body)
    }

    async fn post(&self, path: &str, body: Value) -> (u16, Value) {
        let r = self.client
            .post(format!("{}{}", self.base_url, path))
            .json(&body)
            .send()
            .await
            .expect("POST");
        let status = r.status().as_u16();
        let resp: Value = r.json().await.unwrap_or(Value::Null);
        (status, resp)
    }

    async fn post_auth(&self, path: &str, body: Value, token: &str) -> (u16, Value) {
        let r = self.client
            .post(format!("{}{}", self.base_url, path))
            .header("Authorization", format!("Bearer {token}"))
            .json(&body)
            .send()
            .await
            .expect("POST");
        let status = r.status().as_u16();
        let resp: Value = r.json().await.unwrap_or(Value::Null);
        (status, resp)
    }
}

impl Drop for TestServer {
    fn drop(&mut self) {
        self.handle.abort();
    }
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[tokio::test]
async fn health_returns_ok() {
    let s = TestServer::start(false).await;
    let (status, body) = s.get("/health").await;
    assert_eq!(status, 200);
    assert_eq!(body["status"], "ok");
    assert!(body["version"].as_str().is_some());
}

#[tokio::test]
async fn app_meta_returns_ok() {
    let s = TestServer::start(false).await;
    let (status, body) = s.get("/_app/meta").await;
    assert_eq!(status, 200);
    assert_eq!(body["status"], "ok");
}

#[tokio::test]
async fn node_status_returns_node_id() {
    let s = TestServer::start(false).await;
    let (status, body) = s.get("/xrpc/ai.gftd.apps.kotoba.node.status").await;
    assert_eq!(status, 200);
    assert!(body["node_id"].as_str().is_some(), "node_id missing: {body}");
}

#[tokio::test]
async fn quad_create_returns_journal_cid() {
    let s = TestServer::start(false).await;
    let (status, body) = s.post(
        "/xrpc/ai.gftd.apps.kotoba.quad.create",
        json!({ "graph": "e2e", "subject": "alice", "predicate": "knows", "object": "bob" }),
    ).await;
    assert_eq!(status, 200, "{body}");
    assert_eq!(body["status"], "ok");
    assert!(body["journal_cid"].as_str().is_some());
}

#[tokio::test]
async fn graph_query_empty_graph_returns_zero() {
    use kotoba_core::cid::KotobaCid;
    let s = TestServer::start(false).await;
    let cid = KotobaCid::from_bytes(b"nonexistent-graph-xyz").to_multibase();
    let (status, body) = s.get(
        &format!("/xrpc/ai.gftd.apps.kotoba.graph.query?graph={cid}")
    ).await;
    assert_eq!(status, 200, "{body}");
    assert_eq!(body["count"], 0);
}

#[tokio::test]
async fn graph_query_after_create_returns_quad() {
    use kotoba_core::cid::KotobaCid;
    let s = TestServer::start(false).await;

    s.post(
        "/xrpc/ai.gftd.apps.kotoba.quad.create",
        json!({ "graph": "qtest", "subject": "x", "predicate": "rel", "object": "y" }),
    ).await;

    let graph_cid = KotobaCid::from_bytes(b"qtest").to_multibase();
    let (status, body) = s.get(
        &format!("/xrpc/ai.gftd.apps.kotoba.graph.query?graph={graph_cid}")
    ).await;
    assert_eq!(status, 200, "{body}");
    assert!(body["count"].as_u64().unwrap_or(0) >= 1, "expected ≥1 quad: {body}");
}

#[tokio::test]
async fn quad_retract_returns_ok() {
    let s = TestServer::start(false).await;
    let (status, body) = s.post(
        "/xrpc/ai.gftd.apps.kotoba.quad.retract",
        json!({ "graph": "e2e", "subject": "alice", "predicate": "knows", "object": "bob" }),
    ).await;
    assert_eq!(status, 200, "{body}");
    assert_eq!(body["status"], "ok");
}

#[tokio::test]
async fn block_put_and_get_roundtrip() {
    use base64::{Engine as _, engine::general_purpose::STANDARD as B64};
    let s = TestServer::start(false).await;

    let payload = b"kotoba e2e block";
    let (status, put) = s.post(
        "/xrpc/ai.gftd.apps.kotoba.block.put",
        json!({ "data_b64": B64.encode(payload) }),
    ).await;
    assert_eq!(status, 200, "{put}");
    let cid = put["cid"].as_str().expect("cid");

    let (status2, get) = s.get(
        &format!("/xrpc/ai.gftd.apps.kotoba.block.get?cid={cid}")
    ).await;
    assert_eq!(status2, 200, "{get}");
    let bytes = B64.decode(get["data_b64"].as_str().expect("data_b64")).unwrap();
    assert_eq!(bytes, payload);
}

#[tokio::test]
async fn commit_store_and_get_roundtrip() {
    use kotoba_core::cid::KotobaCid;
    let s = TestServer::start(false).await;
    let graph_cid = KotobaCid::from_bytes(b"commit-e2e").to_multibase();

    s.post(
        "/xrpc/ai.gftd.apps.kotoba.quad.create",
        json!({ "graph": "commit-e2e", "subject": "s", "predicate": "p", "object": "o" }),
    ).await;

    let (status, store) = s.post(
        "/xrpc/ai.gftd.apps.kotoba.commit.store",
        json!({ "graph": graph_cid, "author": "did:plc:e2e", "seq": 1 }),
    ).await;
    assert_eq!(status, 200, "{store}");
    assert!(store["cid"].as_str().is_some());

    let (status2, get) = s.get(
        &format!("/xrpc/ai.gftd.apps.kotoba.commit.get?graph={graph_cid}")
    ).await;
    assert_eq!(status2, 200, "{get}");
    assert_eq!(get["seq"], 1);
    assert_eq!(get["author"], "did:plc:e2e");
}

#[tokio::test]
async fn embed_create_returns_quad_cid() {
    use kotoba_core::cid::KotobaCid;
    let s = TestServer::start(false).await;
    let graph_cid = KotobaCid::from_bytes(b"embed-e2e").to_multibase();
    let (status, body) = s.post(
        "/xrpc/ai.gftd.apps.kotoba.embed.create",
        json!({
            "text": "hello kotoba",
            "doc_cid": "doc1",
            "model_cid": "model1",
            "graph": graph_cid
        }),
    ).await;
    assert_eq!(status, 200, "{body}");
    assert_eq!(body["status"], "ok");
    assert!(body["dims"].as_u64().unwrap_or(0) > 0);
}

#[tokio::test]
async fn infer_run_with_stub_engine() {
    let s = TestServer::start(true).await;
    let (status, body) = s.post(
        "/xrpc/ai.gftd.apps.kotoba.infer.run",
        json!({ "prompt": "what is kotoba?", "max_new_tokens": 32 }),
    ).await;
    assert_eq!(status, 200, "{body}");
    assert_eq!(body["status"], "ok");
    assert!(body["output"].as_str().map(|s| !s.is_empty()).unwrap_or(false));
}

#[tokio::test]
async fn infer_run_without_engine_returns_503() {
    let s = TestServer::start(false).await;
    let (status, _) = s.post(
        "/xrpc/ai.gftd.apps.kotoba.infer.run",
        json!({ "prompt": "hello" }),
    ).await;
    assert_eq!(status, 503);
}

#[tokio::test]
async fn agent_run_with_stub_engine_completes() {
    let s = TestServer::start(true).await;
    let (status, body) = s.post(
        "/xrpc/ai.gftd.apps.kotoba.agent.run",
        json!({ "task": "test: 2+2?", "max_steps": 3, "max_tokens": 64 }),
    ).await;
    assert_eq!(status, 200, "{body}");
    assert_eq!(body["status"], "ok");
    assert!(body["session_cid"].as_str().is_some());
    assert!(body["supersteps"].as_u64().unwrap_or(0) >= 1);
}

#[tokio::test]
async fn agent_run_without_engine_returns_503() {
    let s = TestServer::start(false).await;
    let (status, _) = s.post(
        "/xrpc/ai.gftd.apps.kotoba.agent.run",
        json!({ "task": "x" }),
    ).await;
    assert_eq!(status, 503);
}

// ── MCP ───────────────────────────────────────────────────────────────────────

#[tokio::test]
async fn mcp_initialize_returns_protocol_version() {
    let s = TestServer::start(false).await;
    let (status, body) = s.post(
        "/mcp",
        json!({ "jsonrpc": "2.0", "id": 1, "method": "initialize", "params": null }),
    ).await;
    assert_eq!(status, 200);
    assert_eq!(body["result"]["protocolVersion"], "2024-11-05");
    assert_eq!(body["result"]["serverInfo"]["name"], "kotoba");
}

#[tokio::test]
async fn mcp_tools_list_returns_six_tools() {
    let s = TestServer::start(false).await;
    let (status, body) = s.post(
        "/mcp",
        json!({ "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": null }),
    ).await;
    assert_eq!(status, 200);
    let tools = body["result"]["tools"].as_array().expect("tools");
    assert_eq!(tools.len(), 6);
}

#[tokio::test]
async fn mcp_ping_returns_empty_result() {
    let s = TestServer::start(false).await;
    let (status, body) = s.post(
        "/mcp",
        json!({ "jsonrpc": "2.0", "id": 5, "method": "ping" }),
    ).await;
    assert_eq!(status, 200);
    assert!(body["result"].is_object());
    assert!(body.get("error").is_none());
}

#[tokio::test]
async fn mcp_tools_call_quad_create_ok() {
    let s = TestServer::start(false).await;
    let (status, body) = s.post_auth(
        "/mcp",
        json!({
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {
                "name": "kotoba_quad_create",
                "arguments": { "graph": "mcp-g", "subject": "s", "predicate": "p", "object": "o" }
            }
        }),
        "test-token",
    ).await;
    assert_eq!(status, 200, "{body}");
    assert!(body.get("error").is_none(), "unexpected error: {body}");
    assert!(body["result"].is_object());
}

#[tokio::test]
async fn mcp_tools_call_without_auth_returns_error() {
    let s = TestServer::start(false).await;
    let (status, body) = s.post(
        "/mcp",
        json!({
            "jsonrpc": "2.0", "id": 4, "method": "tools/call",
            "params": {
                "name": "kotoba_quad_create",
                "arguments": { "graph": "g", "subject": "s", "predicate": "p", "object": "o" }
            }
        }),
    ).await;
    assert_eq!(status, 200);
    assert!(body["error"].is_object(), "expected JSON-RPC error");
    assert_eq!(body["error"]["code"], -32001);
}

// ── WASM invoke.run (skips if cargo-component unavailable) ────────────────────

#[tokio::test]
async fn invoke_run_wasm_guest_via_xrpc() {
    let Some(wasm_bytes) = build_guest_component() else {
        eprintln!("cargo-component unavailable — skipping invoke_run_wasm_guest_via_xrpc");
        return;
    };
    use base64::{Engine as _, engine::general_purpose::STANDARD as B64};

    let mut ctx = Vec::new();
    {
        use std::collections::BTreeMap;
        let mut map: BTreeMap<&str, ciborium::Value> = BTreeMap::new();
        map.insert("graph",       ciborium::Value::Text("e2e-wasm-graph".into()));
        map.insert("session_cid", ciborium::Value::Null);
        map.insert("args_cbor",   ciborium::Value::Bytes(b"e2e test".to_vec()));
        ciborium::into_writer(&map, &mut ctx).unwrap();
    }

    let s = TestServer::start(false).await;
    let (status, body) = s.post(
        "/xrpc/ai.gftd.apps.kotoba.invoke.run",
        json!({
            "program_cid":  "be2e_wasm_invoke",
            "program_type": "wasm-node",
            "agent_did":    "did:plc:e2e",
            "wasm_b64":     B64.encode(&wasm_bytes),
            "ctx_b64":      B64.encode(&ctx),
        }),
    ).await;

    assert_eq!(status, 200, "{body}");
    assert_eq!(body["status"], "ok");
    assert!(body["gas_used"].as_u64().unwrap_or(0) > 0);
    assert!(body["assert_count"].as_u64().unwrap_or(0) >= 1, "{body}");

    let out_bytes = B64.decode(body["output_b64"].as_str().expect("output_b64")).unwrap();
    let out: ciborium::Value = ciborium::from_reader(out_bytes.as_slice()).unwrap();
    if let ciborium::Value::Map(pairs) = out {
        let status_val = pairs.iter().find_map(|(k, v)| {
            if k == &ciborium::Value::Text("status".into()) { v.as_text().map(|s| s.to_string()) } else { None }
        });
        assert_eq!(status_val.as_deref(), Some("ok"));
    } else {
        panic!("output CBOR not a map");
    }
}

// ── Helper ────────────────────────────────────────────────────────────────────

fn build_guest_component() -> Option<Vec<u8>> {
    use std::process::Command;
    let manifest   = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let workspace  = manifest.parent().unwrap().parent().unwrap();
    let status = Command::new("cargo")
        .args(["component", "build",
               "--manifest-path", "crates/kotoba-guest/Cargo.toml",
               "--target", "wasm32-wasip2", "--release", "--quiet"])
        .current_dir(workspace)
        .status();
    let Ok(s) = status else { return None; };
    if !s.success() { return None; }
    let p = workspace.join("target/wasm32-wasip2/release/kotoba_echo_assert.wasm");
    if p.exists() { return std::fs::read(p).ok(); }
    let alt = workspace.join("target/wasm32-wasip2/release/kotoba_guest.wasm");
    if alt.exists() { return std::fs::read(alt).ok(); }
    let dir = std::fs::read_dir(workspace.join("target/wasm32-wasip2/release")).ok()?;
    for e in dir.flatten() {
        let p = e.path();
        if p.extension().map(|x| x == "wasm").unwrap_or(false) {
            let n = p.file_name().unwrap().to_string_lossy();
            if n.contains("kotoba") || n.contains("echo") || n.contains("guest") {
                return std::fs::read(&p).ok();
            }
        }
    }
    None
}
