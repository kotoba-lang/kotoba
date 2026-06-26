//! Git **smart-HTTP** endpoints — let a real `git` client clone, fetch and push
//! against kotoba, with every object landing as an IPFS block + `:git/*` Datom
//! projection (ADR-2606015000 made the git ↔ kotoba bridge; this opens it to the
//! network).
//!
//! Routes (mounted by `build_router`):
//!
//! | Method | Path                              | Handler            | git op |
//! |--------|-----------------------------------|--------------------|--------|
//! | GET    | `/git/:repo/info/refs?service=…`  | [`info_refs`]      | discovery |
//! | POST   | `/git/:repo/git-upload-pack`      | [`upload_pack`]    | clone / fetch |
//! | POST   | `/git/:repo/git-receive-pack`     | [`receive_pack`]   | push |
//!
//! `:repo` names a per-repo [`kotoba_datomic::Connection`] (the queryable git
//! projection) paired with the node's shared `block_store` (the lossless,
//! content-addressed object bytes) — i.e. **datomic + IPFS**, the substrate the
//! whole crate is built on. The wire protocol itself lives in
//! [`kotoba_git::wire`]; this module is the thin HTTP/auth shell around it.
//!
//! ## AuthZ
//!
//! * **Reads** (clone/fetch) are gated by the node read policy
//!   (`KOTOBA_DEFAULT_VISIBILITY`), reusing [`graph_auth::check_read_access`] —
//!   the same gate as the firehose.
//! * **Push** is gated by [`graph_auth::require_operator_auth`] (a Bearer JWT
//!   whose `sub` is the operator DID) — pushing mutates the node's git state, so
//!   it requires operator authority by default. Set
//!   `KOTOBA_GIT_ALLOW_ANON_PUSH=1` to allow anonymous push (local dev / tests).

use std::sync::Arc;

use axum::{
    body::{Body, Bytes},
    extract::{Path, Query, State},
    http::{header, HeaderMap, StatusCode},
    response::{IntoResponse, Response},
};
use serde::Deserialize;
use std::io::Read;

use crate::graph_auth::{self, AccessDenied};
use crate::server::KotobaState;
use kotoba_core::cid::KotobaCid;
use kotoba_git::wire::{self, GitService};
use kotoba_git::GitStore;

/// Cap on a single request body (pack upload). 1 GiB matches the per-object
/// inflate cap in `kotoba-git` and bounds memory for a push.
pub const GIT_BODY_LIMIT: usize = 1 << 30;

#[derive(Debug, Deserialize)]
pub struct InfoRefsQuery {
    service: Option<String>,
}

/// `GET /git/:repo/info/refs?service=git-upload-pack|git-receive-pack`
pub async fn info_refs(
    State(state): State<Arc<KotobaState>>,
    Path(repo): Path<String>,
    Query(q): Query<InfoRefsQuery>,
    headers: HeaderMap,
) -> Response {
    // Only the smart protocol is supported (no dumb-HTTP file serving).
    let Some(service) = q.service.as_deref().and_then(GitService::from_query) else {
        return (
            StatusCode::FORBIDDEN,
            "only the git smart HTTP protocol is supported (missing ?service=)",
        )
            .into_response();
    };

    // Gate by service: discovery for push must pass the push gate.
    let gate = match service {
        GitService::UploadPack => read_gate(&state, &headers).await,
        GitService::ReceivePack => push_gate(&state, &headers, &repo),
    };
    if let Err(e) = gate {
        return e.into_response();
    }

    let conn = state.git_connection(&repo).await;
    let git = GitStore::new(&conn, &*state.block_store);
    match wire::advertise_refs(&git, service) {
        Ok(body) => smart_response(
            &format!("application/x-{}-advertisement", service.as_str()),
            body,
        ),
        Err(e) => git_error(e),
    }
}

/// `POST /git/:repo/git-upload-pack` (clone / fetch).
pub async fn upload_pack(
    State(state): State<Arc<KotobaState>>,
    Path(repo): Path<String>,
    headers: HeaderMap,
    body: Bytes,
) -> Response {
    if let Err(e) = read_gate(&state, &headers).await {
        return e.into_response();
    }
    let body = match decode_body(&headers, body) {
        Ok(b) => b,
        Err(e) => return e.into_response(),
    };

    let conn = state.git_connection(&repo).await;
    let git = GitStore::new(&conn, &*state.block_store);
    match wire::upload_pack(&git, &body) {
        Ok(out) => smart_response("application/x-git-upload-pack-result", out),
        Err(e) => git_error(e),
    }
}

/// `POST /git/:repo/git-receive-pack` (push).
pub async fn receive_pack(
    State(state): State<Arc<KotobaState>>,
    Path(repo): Path<String>,
    headers: HeaderMap,
    body: Bytes,
) -> Response {
    if let Err(e) = push_gate(&state, &headers, &repo) {
        return e.into_response();
    }
    let body = match decode_body(&headers, body) {
        Ok(b) => b,
        Err(e) => return e.into_response(),
    };

    let conn = state.git_connection(&repo).await;
    let git = GitStore::new(&conn, &*state.block_store);
    match wire::receive_pack(&git, &body).await {
        Ok(out) => {
            // Persist the updated projection (objects are already durable blocks;
            // this snapshots the oid↔cid index + refs and records the pointer).
            state.git_persist(&repo, &git).await;
            // A-3: record the new head as a signed rad sigref (best-effort).
            rad_attest_push(&repo, &headers, &git);
            smart_response("application/x-git-receive-pack-result", out)
        }
        Err(e) => git_error(e),
    }
}

// ── helpers ────────────────────────────────────────────────────────────────

/// The CACAO credential git carries, if any. git sets it via
/// `git -c http.extraHeader="x-kotoba-cacao: <b64>"`. A custom header (not the
/// `Authorization` Bearer) so it never collides with an operator JWT.
fn cacao_header(headers: &HeaderMap) -> Option<&str> {
    headers.get("x-kotoba-cacao").and_then(|v| v.to_str().ok())
}

/// Read gate: node default visibility (`KOTOBA_DEFAULT_VISIBILITY`), reusing the
/// firehose's `check_read_access`. A CACAO read credential (capability
/// `datom:read`) may ride in the `x-kotoba-cacao` header. No nonce store: a
/// clone reuses the same credential across `info/refs` + `upload-pack`.
async fn read_gate(state: &KotobaState, headers: &HeaderMap) -> Result<(), (StatusCode, String)> {
    // Sentinel all-zero CID → node default visibility (not a registered graph).
    let visibility = state.graph_visibility(&KotobaCid([0u8; 36])).await;
    graph_auth::check_read_access(
        &visibility,
        headers,
        cacao_header(headers),
        Some(&state.operator_did),
        None,
    )
    .map_err(AccessDenied::into_response)
}

/// The process-wide kotoba-rad delegate registry, projected once from
/// `KOTOBA_RAD_JOURNAL_DIR` (ADR-2606251200 A-1/A-2). Empty when the var is unset,
/// in which case the push gate uses the operator-rooted path — purely additive.
fn rad_registry() -> &'static crate::rad_registry::RadRegistry {
    static REG: std::sync::OnceLock<crate::rad_registry::RadRegistry> = std::sync::OnceLock::new();
    REG.get_or_init(crate::rad_registry::RadRegistry::from_env)
}

/// The CACAO issuer DID (`p.iss`), for the `:rad/by` of a sigref attestation.
fn cacao_issuer(cacao_b64: &str) -> Option<String> {
    use base64::{engine::general_purpose::STANDARD as B64, Engine as _};
    let cbor = B64.decode(cacao_b64).ok()?;
    kotoba_auth::Cacao::from_cbor(&cbor).ok().map(|c| c.p.iss)
}

/// A-3: record the just-pushed head as a signed rad sigref (ADR-2606251200).
/// Best-effort — a write-back failure must NEVER fail the push, so this only
/// logs. Attests only a rad-bound repo (delegates present) pushed with a CACAO:
/// the CACAO is the member signature (no-server-key — the server only verifies).
fn rad_attest_push(repo: &str, headers: &HeaderMap, git: &GitStore<'_>) {
    let Some(cacao_b64) = cacao_header(headers) else {
        return;
    };
    let reg = rad_registry();
    let Some(rad) = reg.resolve(repo) else {
        return;
    };
    if rad.delegates.is_empty() {
        return;
    }
    let db = git.db();
    let head_oid = kotoba_git::resolve_ref(&db, "refs/heads/main")
        .or_else(|| kotoba_git::resolve_ref(&db, "HEAD"));
    let Some(oid) = head_oid else {
        return;
    };
    let head_cid = match git.object_cid(&db, oid) {
        Ok(c) => c.to_multibase(),
        Err(_) => return,
    };
    let by = cacao_issuer(cacao_b64).unwrap_or_default();
    match reg.attest_sigref(repo, &head_cid, &by, cacao_b64) {
        Ok(tx) => tracing::info!(
            repo = %repo, rid = %rad.rid, head = %head_cid, tx,
            "kotoba-rad: sigref attested"
        ),
        Err(e) => tracing::warn!(
            repo = %repo, error = %e,
            "kotoba-rad: sigref attestation failed (push still succeeded)"
        ),
    }
}

/// Push gate, in precedence order:
/// 1. `KOTOBA_GIT_ALLOW_ANON_PUSH=1` — open (local dev / tests).
/// 2. **Sovereign (rad-rooted)**: if `repo` resolves to a registered kotoba-rad
///    identity *with delegates*, a CACAO granting `git.receive/push` on scope
///    `git/repo/<RID>` rooted at one of that repo's own `:rad/delegates`
///    (ADR-2606251200 A-2) — push authority is the repo's, not the node's.
/// 3. A CACAO granting `git.receive/push` on `git/repo/<repo>`, rooted at the
///    operator DID — the legacy operator-delegable path (un-bound repos).
/// 4. An operator Bearer JWT (`sub == operator_did`).
fn push_gate(
    state: &KotobaState,
    headers: &HeaderMap,
    repo: &str,
) -> Result<(), (StatusCode, String)> {
    if std::env::var("KOTOBA_GIT_ALLOW_ANON_PUSH").as_deref() == Ok("1") {
        return Ok(());
    }
    if let Some(cacao_b64) = cacao_header(headers) {
        // Sovereign path: a repo with registered rad delegates governs its own push.
        if let Some(rad) = rad_registry().resolve(repo) {
            if !rad.delegates.is_empty() {
                return graph_auth::verify_cacao_rad_push(
                    cacao_b64,
                    &rad.rid,
                    &rad.delegates,
                    Some(&state.operator_did),
                    None, // git reuses the credential across info/refs + receive-pack
                )
                .map_err(AccessDenied::into_response);
            }
        }
        let scope = format!("git/repo/{repo}");
        return graph_auth::verify_cacao_capability(
            cacao_b64,
            "git.receive/push",
            &scope,
            &state.operator_did,
            Some(&state.operator_did),
            None, // git reuses the credential across info/refs + receive-pack
        )
        .map_err(AccessDenied::into_response);
    }
    graph_auth::require_operator_auth(headers, &state.operator_did)
}

/// Decompress the body if the client sent `Content-Encoding: gzip` (git does
/// this for larger upload-pack requests).
fn decode_body(headers: &HeaderMap, body: Bytes) -> Result<Vec<u8>, (StatusCode, String)> {
    let gzipped = headers
        .get(header::CONTENT_ENCODING)
        .and_then(|v| v.to_str().ok())
        .map(|v| v.eq_ignore_ascii_case("gzip"))
        .unwrap_or(false);
    if !gzipped {
        return Ok(body.to_vec());
    }
    let mut out = Vec::new();
    flate2::read::GzDecoder::new(&body[..])
        .read_to_end(&mut out)
        .map_err(|e| {
            (
                StatusCode::BAD_REQUEST,
                format!("malformed gzip request body: {e}"),
            )
        })?;
    Ok(out)
}

/// Build a smart-HTTP response with the right content-type and no-cache headers
/// (git is strict about caching the dynamic protocol endpoints).
fn smart_response(content_type: &str, body: Vec<u8>) -> Response {
    Response::builder()
        .status(StatusCode::OK)
        .header(header::CONTENT_TYPE, content_type)
        .header(
            header::CACHE_CONTROL,
            "no-cache, max-age=0, must-revalidate",
        )
        .body(Body::from(body))
        .expect("static header values are valid")
}

fn git_error(e: kotoba_git::GitError) -> Response {
    tracing::warn!(error = %e, "git smart-HTTP request failed");
    (StatusCode::BAD_REQUEST, format!("git protocol error: {e}")).into_response()
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;

    fn gzip(data: &[u8]) -> Vec<u8> {
        let mut enc = flate2::write::GzEncoder::new(Vec::new(), flate2::Compression::default());
        enc.write_all(data).unwrap();
        enc.finish().unwrap()
    }

    #[test]
    fn decode_body_passes_through_plain_and_inflates_gzip() {
        let payload = b"0032want 1111111111111111111111111111111111111111\n0000".to_vec();

        // No Content-Encoding → returned verbatim.
        let plain = decode_body(&HeaderMap::new(), Bytes::from(payload.clone())).unwrap();
        assert_eq!(plain, payload);

        // Content-Encoding: gzip → inflated back to the original bytes.
        let mut h = HeaderMap::new();
        h.insert(header::CONTENT_ENCODING, "gzip".parse().unwrap());
        let got = decode_body(&h, Bytes::from(gzip(&payload))).unwrap();
        assert_eq!(got, payload);

        // Case-insensitive ("GZIP") is also handled.
        let mut h = HeaderMap::new();
        h.insert(header::CONTENT_ENCODING, "GZIP".parse().unwrap());
        assert_eq!(
            decode_body(&h, Bytes::from(gzip(&payload))).unwrap(),
            payload
        );
    }

    #[test]
    fn decode_body_rejects_corrupt_gzip() {
        let mut h = HeaderMap::new();
        h.insert(header::CONTENT_ENCODING, "gzip".parse().unwrap());
        let err = decode_body(&h, Bytes::from_static(b"not actually gzip")).unwrap_err();
        assert_eq!(err.0, StatusCode::BAD_REQUEST);
    }
}
