//! XRPC handlers for compiling and running `.kotoba` Kotoba/EDN source.
//!
//! Where `mesh.deploy` gossips pre-built lattice messages, these endpoints take
//! raw `.kotoba` *source* — the same Kotoba profile the compiler accepts for
//! `app.kotoba` scripts — and turn it into a WebAssembly core module:
//!
//!   com.etzhayyim.apps.kotoba.mesh.compile — source → wasm bytes (POST)
//!   com.etzhayyim.apps.kotoba.mesh.run     — source → compile → run → i64 (POST)
//!
//! Both are **operator-gated** (same as `media.*`). `mesh.run` instantiates the
//! emitted core module on a plain wasmtime engine with **no host imports**
//! (no kqe/kse/auth/llm), so a compiled program is pure compute over i64 args,
//! and execution is bounded by wasmtime **fuel** so untrusted source can never
//! hang the host. CPU-bound compile+run is offloaded to a blocking task so it
//! does not stall the async runtime.

pub const NSID_MESH_COMPILE: &str = "com.etzhayyim.apps.kotoba.mesh.compile";
pub const NSID_MESH_RUN: &str = "com.etzhayyim.apps.kotoba.mesh.run";

use axum::{
    extract::State,
    http::{HeaderMap, StatusCode},
    response::IntoResponse,
    Json,
};
use serde::Deserialize;
use serde_json::json;
use std::sync::Arc;

use kotoba_core::cid::KotobaCid;

use crate::server::KotobaState;

// ── limits ──────────────────────────────────────────────────────────────────────

/// 256 KiB of source — generous for a single `.kotoba` cell, far below any
/// reasonable script.
const MAX_SOURCE_LEN: usize = 256 * 1024;
/// JSON framing headroom over [`MAX_SOURCE_LEN`].
pub const MESH_BODY_LIMIT: usize = 512 * 1024;
const MAX_ARGS: usize = 16;
const MAX_FUNC_LEN: usize = 256;
/// Default fuel budget for `mesh.run` (≈ one fuel unit per wasm instruction).
const DEFAULT_FUEL: u64 = 50_000_000;
/// Hard ceiling so a caller-supplied `fuel` can't request an unbounded run.
const MAX_FUEL: u64 = 1_000_000_000;

fn default_prelude() -> bool {
    true
}

fn default_func() -> String {
    "main".to_string()
}

// ── shared validation ──────────────────────────────────────────────────────────────

fn resolve_reader_target(
    s: Option<&str>,
) -> Result<kotoba_clj::ReaderTarget, (StatusCode, String)> {
    match s {
        None => Ok(kotoba_clj::ReaderTarget::Kotoba),
        Some(t) => kotoba_clj::ReaderTarget::parse(t).ok_or((
            StatusCode::BAD_REQUEST,
            "readerTarget must be one of kotoba,clj,cljs".to_string(),
        )),
    }
}

fn validate_source(src: &str) -> Result<(), (StatusCode, String)> {
    if src.trim().is_empty() {
        return Err((
            StatusCode::BAD_REQUEST,
            "source must not be empty".to_string(),
        ));
    }
    if src.len() > MAX_SOURCE_LEN {
        return Err((
            StatusCode::PAYLOAD_TOO_LARGE,
            format!("source exceeds {MAX_SOURCE_LEN} bytes"),
        ));
    }
    // Source is code: newlines/tabs are expected. Only reject a NUL byte, which
    // is never valid in `.kotoba` text and can confuse downstream tooling.
    if src.bytes().any(|b| b == 0) {
        return Err((
            StatusCode::BAD_REQUEST,
            "source contains a NUL byte".to_string(),
        ));
    }
    Ok(())
}

fn validate_func(func: &str) -> Result<(), (StatusCode, String)> {
    if func.trim().is_empty() || func.len() > MAX_FUNC_LEN {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("func must be 1–{MAX_FUNC_LEN} bytes"),
        ));
    }
    if func.bytes().any(|b| b.is_ascii_whitespace() || b == 0) {
        return Err((
            StatusCode::BAD_REQUEST,
            "func must not contain whitespace".to_string(),
        ));
    }
    Ok(())
}

/// Compile `source` to wasm bytes, mapping a compile failure to a 400 (the
/// caller's source is at fault).
fn compile(
    source: &str,
    prelude: bool,
    target: kotoba_clj::ReaderTarget,
) -> Result<Vec<u8>, (StatusCode, String)> {
    let result = if prelude {
        kotoba_clj::compile_str_with_prelude_and_reader_target(source, target)
    } else {
        kotoba_clj::compile_str_with_reader_target(source, target)
    };
    result.map_err(|e| (StatusCode::BAD_REQUEST, format!("compile error: {e}")))
}

// ── mesh.compile ──────────────────────────────────────────────────────────────────

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct MeshCompileBody {
    pub source: String,
    #[serde(default = "default_prelude")]
    pub prelude: bool,
    pub reader_target: Option<String>,
}

pub async fn mesh_compile(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Json(body): Json<MeshCompileBody>,
) -> impl IntoResponse {
    use base64::Engine as _;

    if let Err((code, msg)) =
        crate::graph_auth::require_operator_auth(&headers, &state.operator_did)
    {
        return (code, Json(json!({ "error": msg }))).into_response();
    }
    if let Err((code, msg)) = validate_source(&body.source) {
        return (code, Json(json!({ "error": msg }))).into_response();
    }
    let target = match resolve_reader_target(body.reader_target.as_deref()) {
        Ok(t) => t,
        Err((code, msg)) => return (code, Json(json!({ "error": msg }))).into_response(),
    };

    let wasm = match compile(&body.source, body.prelude, target) {
        Ok(w) => w,
        Err((code, msg)) => return (code, Json(json!({ "error": msg }))).into_response(),
    };

    let cid = KotobaCid::from_bytes(&wasm).to_multibase();
    let wasm_b64 = base64::engine::general_purpose::STANDARD.encode(&wasm);
    Json(json!({
        "wasmB64": wasm_b64,
        "cid":     cid,
        "bytes":   wasm.len(),
    }))
    .into_response()
}

// ── mesh.run ────────────────────────────────────────────────────────────────────────

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct MeshRunBody {
    pub source: String,
    #[serde(default = "default_func")]
    pub func: String,
    #[serde(default)]
    pub args: Vec<i64>,
    #[serde(default = "default_prelude")]
    pub prelude: bool,
    pub reader_target: Option<String>,
    /// Optional fuel override; clamped to `[1, MAX_FUEL]`.
    pub fuel: Option<u64>,
}

pub async fn mesh_run(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Json(body): Json<MeshRunBody>,
) -> impl IntoResponse {
    if let Err((code, msg)) =
        crate::graph_auth::require_operator_auth(&headers, &state.operator_did)
    {
        return (code, Json(json!({ "error": msg }))).into_response();
    }
    if let Err((code, msg)) = validate_source(&body.source) {
        return (code, Json(json!({ "error": msg }))).into_response();
    }
    if let Err((code, msg)) = validate_func(&body.func) {
        return (code, Json(json!({ "error": msg }))).into_response();
    }
    if body.args.len() > MAX_ARGS {
        return (
            StatusCode::BAD_REQUEST,
            Json(json!({ "error": format!("at most {MAX_ARGS} args") })),
        )
            .into_response();
    }
    let target = match resolve_reader_target(body.reader_target.as_deref()) {
        Ok(t) => t,
        Err((code, msg)) => return (code, Json(json!({ "error": msg }))).into_response(),
    };

    let wasm = match compile(&body.source, body.prelude, target) {
        Ok(w) => w,
        Err((code, msg)) => return (code, Json(json!({ "error": msg }))).into_response(),
    };
    let cid = KotobaCid::from_bytes(&wasm).to_multibase();

    let fuel = body.fuel.unwrap_or(DEFAULT_FUEL).clamp(1, MAX_FUEL);
    let func = body.func.clone();
    let args = body.args.clone();

    // CPU-bound: instantiate + run on a blocking task so we don't stall the
    // async runtime, and so the fuel-bounded trap is contained.
    let run = tokio::task::spawn_blocking(move || {
        kotoba_clj::run::run_with_fuel(&wasm, &func, &args, fuel)
    })
    .await;

    match run {
        Ok(Ok(result)) => {
            Json(json!({ "result": result, "cid": cid, "fuel": fuel })).into_response()
        }
        Ok(Err(e)) => (
            // A trap / out-of-fuel / missing-export is the caller's program at
            // fault, not a server fault.
            StatusCode::BAD_REQUEST,
            Json(json!({ "error": format!("run error: {e}"), "cid": cid })),
        )
            .into_response(),
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({ "error": format!("run task failed: {e}") })),
        )
            .into_response(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn nsids_have_kotoba_mesh_prefix() {
        for nsid in [NSID_MESH_COMPILE, NSID_MESH_RUN] {
            assert!(nsid.starts_with("com.etzhayyim.apps.kotoba.mesh."));
            assert!(!nsid.ends_with('.'));
            assert!(nsid.chars().all(|c| c.is_ascii_lowercase() || c == '.'));
        }
    }

    #[test]
    fn reader_target_defaults_to_kotoba_and_parses_known() {
        assert_eq!(
            resolve_reader_target(None).unwrap(),
            kotoba_clj::ReaderTarget::Kotoba
        );
        assert_eq!(
            resolve_reader_target(Some("cljs")).unwrap(),
            kotoba_clj::ReaderTarget::Cljs
        );
        assert!(resolve_reader_target(Some("cobol")).is_err());
    }

    #[test]
    fn validate_source_rejects_empty_oversized_and_nul() {
        assert!(validate_source("(defn main [x] x)").is_ok());
        assert!(validate_source("   ").is_err());
        assert!(validate_source("a\0b").is_err());
        let (code, _) = validate_source(&"x".repeat(MAX_SOURCE_LEN + 1)).unwrap_err();
        assert_eq!(code, StatusCode::PAYLOAD_TOO_LARGE);
    }

    #[test]
    fn validate_func_rejects_empty_whitespace_and_oversized() {
        assert!(validate_func("main").is_ok());
        assert!(validate_func("").is_err());
        assert!(validate_func("two words").is_err());
        assert!(validate_func(&"f".repeat(MAX_FUNC_LEN + 1)).is_err());
    }

    #[test]
    fn compile_then_run_roundtrips_via_helpers() {
        let wasm = compile(
            "(defn main [a b] (+ (* a a) b))",
            true,
            kotoba_clj::ReaderTarget::Kotoba,
        )
        .unwrap();
        let out = kotoba_clj::run::run_with_fuel(&wasm, "main", &[6, 5], DEFAULT_FUEL).unwrap();
        assert_eq!(out, 41);
    }

    #[test]
    fn compile_surfaces_source_error_as_bad_request() {
        let (code, _) =
            compile("(defn main [", true, kotoba_clj::ReaderTarget::Kotoba).unwrap_err();
        assert_eq!(code, StatusCode::BAD_REQUEST);
    }
}
