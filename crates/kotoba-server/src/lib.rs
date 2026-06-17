#![allow(
    clippy::approx_constant,
    clippy::assertions_on_constants,
    clippy::await_holding_lock,
    clippy::items_after_test_module,
    clippy::needless_borrows_for_generic_args,
    clippy::too_many_arguments,
    clippy::type_complexity,
    clippy::unnecessary_literal_unwrap,
    clippy::unnecessary_min_or_max,
    clippy::useless_vec,
    rustdoc::broken_intra_doc_links,
    rustdoc::invalid_html_tags
)]

pub mod access_receipt;
pub mod account_xrpc;
pub mod attestation;
pub mod availability_xrpc;
pub mod cc_xrpc;
pub mod dht_audit;
pub mod dht_transport;
pub mod did_bridge;
pub mod dna_integrity;
pub mod econ;
pub mod email_xrpc;
pub mod evm_rpc;
pub mod fingerprint;
pub mod firehose;
pub mod git_http;
pub mod graph_auth;
pub mod key_share;
pub mod kg;
pub mod kotobase_xrpc;
pub mod mcp;
pub mod media_xrpc;
pub mod mishmar_observe;
#[cfg(feature = "p2p")]
pub mod net_actor;
pub mod nonce_store;
pub mod pds_session;
pub mod pds_xrpc;
pub mod pre_proxy;
pub mod realtime;
pub mod server;
pub mod signal_xrpc;
pub mod social;
pub mod social_economy;
pub mod social_xrpc;
pub mod xrpc;

use axum::{
    extract::DefaultBodyLimit,
    middleware,
    routing::{get, post},
    Router,
};
use std::sync::Arc;

use crate::server::KotobaState;
use tower_http::trace::TraceLayer;

#[cfg(test)]
mod tests {
    use super::xrpc::*;

    // ── NSID format invariants ─────────────────────────────────────────────

    const ALL_NSIDS: &[&str] = &[
        NSID_DATOM_CREATE,
        NSID_QUAD_CREATE,
        NSID_QUAD_RETRACT,
        NSID_GRAPH_QUERY,
        super::kg::NSID_KG_SPARQL,
        NSID_DATOMIC_TRANSACT,
        NSID_DATOMIC_DATOMS,
        NSID_DATOMIC_PULL,
        NSID_DATOMIC_Q,
        NSID_DATOMIC_WITH,
        NSID_DATOMIC_HISTORY,
        NSID_DATOMIC_ENTITY,
        NSID_DATOMIC_IDENT,
        NSID_DATOMIC_ENTID,
        NSID_COMMIT_GET,
        NSID_COMMIT_STORE,
        NSID_INVOKE_RUN,
        NSID_INFER_RUN,
        NSID_WEIGHT_PUT,
        NSID_WEIGHT_GET,
        NSID_LORA_APPLY,
        NSID_EMBED_CREATE,
        NSID_NODE_STATUS,
        NSID_DID_DOCUMENT_PUBLISH,
        NSID_BLOCK_PUT,
        NSID_BLOCK_GET,
        NSID_AGENT_RUN,
        NSID_AGENT_SYNC_OPEN,
        NSID_AGENT_SYNC_ADV,
        NSID_AGENT_SYNC_CLOSE,
        NSID_VAULT_PUT,
        NSID_VAULT_GET,
        // email
        super::email_xrpc::NSID_EMAIL_LIST,
        super::email_xrpc::NSID_EMAIL_READ,
        super::email_xrpc::NSID_EMAIL_INGEST,
        super::email_xrpc::NSID_EMAIL_SEND,
        // attestation
        super::attestation::NSID_ATTEST_CLAIM,
        super::attestation::NSID_ATTEST_CHALLENGE,
        super::attestation::NSID_ATTEST_QUERY,
        super::attestation::NSID_REQUEST_LOG,
        // cc vector search
        super::cc_xrpc::NSID_CC_SEARCH,
        super::cc_xrpc::NSID_CC_RAG,
        super::cc_xrpc::NSID_CC_INGEST,
        super::cc_xrpc::NSID_CC_STATUS,
        // hybrid web search (lexical + semantic + authority)
        super::cc_xrpc::NSID_WEB_SEARCH,
        super::cc_xrpc::NSID_SEARCH_REINDEX,
        // multimodal cross-modal search
        super::media_xrpc::NSID_MEDIA_SEARCH,
        super::media_xrpc::NSID_MEDIA_INGEST,
        super::media_xrpc::NSID_MEDIA_STATUS,
    ];

    #[test]
    fn all_nsids_have_kotoba_prefix() {
        for nsid in ALL_NSIDS {
            assert!(
                nsid.starts_with("com.etzhayyim.apps.kotoba."),
                "NSID does not start with com.etzhayyim.apps.kotoba.: {nsid}"
            );
        }
    }

    #[test]
    fn all_nsids_are_unique() {
        let mut seen = std::collections::HashSet::new();
        for nsid in ALL_NSIDS {
            assert!(seen.insert(*nsid), "duplicate NSID: {nsid}");
        }
    }

    #[test]
    fn all_nsids_lowercase_dotted() {
        for nsid in ALL_NSIDS {
            assert!(
                nsid.chars().all(|c| c.is_ascii_lowercase() || c == '.'),
                "NSID must be lowercase+dots: {nsid}"
            );
        }
    }

    // ── kotobase NSID invariants ───────────────────────────────────────────

    #[test]
    fn kotobase_nsids_have_kotobase_prefix() {
        for nsid in super::kotobase_xrpc::ALL_NSIDS {
            assert!(
                nsid.starts_with("com.etzhayyim.apps.kotobase."),
                "kotobase NSID does not start with com.etzhayyim.apps.kotobase.: {nsid}"
            );
        }
    }

    #[test]
    fn kotobase_nsids_are_unique() {
        let mut seen = std::collections::HashSet::new();
        for nsid in super::kotobase_xrpc::ALL_NSIDS {
            assert!(seen.insert(*nsid), "duplicate kotobase NSID: {nsid}");
        }
    }

    // ── Router construction ────────────────────────────────────────────────

    #[test]
    fn build_router_does_not_panic() {
        let state = super::server::KotobaState::new(None)
            .expect("KotobaState::new should succeed in test env");
        let _router = super::build_router(std::sync::Arc::new(state));
    }

    // ── NSID detailed format checks ───────────────────────────────────────

    #[test]
    fn all_nsids_no_trailing_dot() {
        for nsid in ALL_NSIDS {
            assert!(!nsid.ends_with('.'), "NSID must not end with dot: {nsid}");
        }
    }

    #[test]
    fn all_nsids_have_at_least_four_segments() {
        for nsid in ALL_NSIDS {
            let segments: Vec<&str> = nsid.split('.').collect();
            assert!(
                segments.len() >= 4,
                "NSID should have at least 4 dot-separated segments: {nsid}"
            );
        }
    }

    #[test]
    fn all_nsids_start_with_ai_etzhayyim_apps() {
        for nsid in ALL_NSIDS {
            assert!(
                nsid.starts_with("com.etzhayyim.apps."),
                "NSID does not start with com.etzhayyim.apps.: {nsid}"
            );
        }
    }

    #[test]
    fn all_nsids_no_consecutive_dots() {
        for nsid in ALL_NSIDS {
            assert!(
                !nsid.contains(".."),
                "NSID must not contain consecutive dots: {nsid}"
            );
        }
    }

    #[test]
    fn all_nsids_no_uppercase() {
        for nsid in ALL_NSIDS {
            assert!(
                !nsid.chars().any(|c| c.is_uppercase()),
                "NSID must not contain uppercase: {nsid}"
            );
        }
    }

    #[test]
    fn kotobase_nsids_have_at_least_four_segments() {
        for nsid in super::kotobase_xrpc::ALL_NSIDS {
            let segments: Vec<&str> = nsid.split('.').collect();
            assert!(
                segments.len() >= 4,
                "kotobase NSID should have >= 4 segments: {nsid}"
            );
        }
    }

    #[test]
    fn kotobase_nsids_no_consecutive_dots() {
        for nsid in super::kotobase_xrpc::ALL_NSIDS {
            assert!(
                !nsid.contains(".."),
                "kotobase NSID must not contain consecutive dots: {nsid}"
            );
        }
    }

    #[tokio::test]
    async fn generic_xrpc_dispatch_resolves() {
        use axum::http::Request;
        use tower::ServiceExt;

        let state = std::sync::Arc::new(super::server::KotobaState::new(None).expect("state"));
        let app = super::build_router(state);

        let req = Request::builder()
            .method("POST")
            .uri("/xrpc/com.etzhayyim.apps.yata.some_method")
            .body(axum::body::Body::empty())
            .unwrap();

        let response = app.oneshot(req).await.unwrap();
        // Since we provided empty body, we expect a 400 Bad Request or 401 Unauthorized,
        // but definitely NOT a 404 Not Found (which means no route matched)
        assert_ne!(response.status(), axum::http::StatusCode::NOT_FOUND);
    }

    /// HTTP-level emit_cid: the feature flows through the REAL router (routing +
    /// body parse + handler + JSON serialization), and the returned result_cid is
    /// fetchable from the node's block store. Stronger than the direct-handler
    /// unit tests, which bypass routing and middleware.
    #[tokio::test]
    async fn datomic_q_emit_cid_round_trips_over_http() {
        use kotoba_core::store::BlockStore as _;
        use tower::ServiceExt;
        std::env::set_var("KOTOBA_IPFS", "off");
        std::env::set_var("KOTOBA_IPNS_REQUIRE_SIGNATURE", "false");
        type Cid = kotoba_core::cid::KotobaCid;

        let state = std::sync::Arc::new(super::server::KotobaState::new(None).expect("state"));

        // Seed Alice/admin into a public graph in the node's own store.
        let graph = Cid::from_bytes(b"http-emit-cid-graph");
        let tx = Cid::from_bytes(b"http-emit-cid-tx");
        let e = Cid::from_bytes(b"http-alice");
        kotoba_datomic::distributed::DistributedCommitWriter::new(
            &*state.block_store,
            &*state.ipns_registry,
        )
        .commit_datoms(kotoba_datomic::distributed::CommitDatomsRequest {
            merge_parents: None,
            ipns_name: distributed_graph_ipns_name(&graph),
            graph: graph.clone(),
            covering_datoms: None,
            datoms: vec![
                kotoba_datomic::Datom::assert(
                    e.clone(),
                    ":person/name".into(),
                    kotoba_edn::EdnValue::string("Alice"),
                    tx.clone(),
                ),
                kotoba_datomic::Datom::assert(
                    e,
                    ":person/role".into(),
                    kotoba_edn::EdnValue::string("admin"),
                    tx.clone(),
                ),
            ],
            expected_parent: None,
            tx_cid: Some(tx),
            author: "did:key:zHttpSeed".into(),
            seq: 1,
            valid_until: "2030-01-01T00:00:00Z".into(),
            ttl_secs: Some(60),
            cacao_proof_cid: None,
            ipns_controller_did: None,
            ipns_signing_key: None,
        })
        .unwrap();
        state.graph_registry.write().await.insert(
            graph.clone(),
            (
                "http".into(),
                kotoba_core::named_graph::GraphVisibility::Public,
            ),
        );

        let app = super::build_router(std::sync::Arc::clone(&state));
        let uri = format!("/xrpc/{}", NSID_DATOMIC_Q);
        let body = serde_json::json!({
            "graph": graph.to_multibase(),
            "query_edn": "[:find ?name ?role :where [?e :person/name ?name] [?e :person/role ?role]]",
            "emit_cid": true,
        });
        let resp = app.oneshot(post_json(&uri, body)).await.unwrap();
        assert_eq!(resp.status(), axum::http::StatusCode::OK);
        let v = body_json(resp).await;
        // Rows came through the full stack…
        assert_eq!(
            v["rows_edn"],
            serde_json::json!([[r#""Alice""#, r#""admin""#]]),
            "body={v}"
        );
        // …and result_cid is present and fetchable from the block store by CID.
        let result_cid = v["result_cid"]
            .as_str()
            .expect("result_cid present in HTTP response");
        let kcid = Cid::from_multibase(result_cid).expect("multibase CID");
        assert!(
            state.block_store.get(&kcid).unwrap().is_some(),
            "result envelope must be fetchable by CID after an HTTP emit_cid query"
        );
    }

    // ── HTTP integration: PDS session PoP + zero-access endpoints (ADR-2606015000) ──

    async fn body_json(resp: axum::response::Response) -> serde_json::Value {
        let bytes = axum::body::to_bytes(resp.into_body(), usize::MAX)
            .await
            .unwrap();
        serde_json::from_slice(&bytes).unwrap_or(serde_json::Value::Null)
    }

    fn post_json(uri: &str, body: serde_json::Value) -> axum::http::Request<axum::body::Body> {
        axum::http::Request::builder()
            .method("POST")
            .uri(uri)
            .header("content-type", "application/json")
            .body(axum::body::Body::from(body.to_string()))
            .unwrap()
    }

    /// Build a valid did:key session PoP (compact EdDSA JWS) for an integration test.
    fn make_didkey_pop() -> String {
        use base64::{engine::general_purpose::URL_SAFE_NO_PAD as B64U, Engine as _};
        use ed25519_dalek::{Signer, SigningKey};
        let sk = SigningKey::from_bytes(&[7u8; 32]);
        let did = kotoba_auth::did_key::ed25519_pubkey_to_did_key(&sk.verifying_key().to_bytes());
        let header = B64U.encode(b"{\"alg\":\"EdDSA\"}");
        let payload = B64U.encode(format!("{{\"iss\":\"{did}\",\"exp\":9999999999}}").as_bytes());
        let signing_input = format!("{header}.{payload}");
        let sig = sk.sign(signing_input.as_bytes());
        format!("{signing_input}.{}", B64U.encode(sig.to_bytes()))
    }

    #[tokio::test]
    async fn pds_session_verify_accepts_valid_didkey_pop() {
        use tower::ServiceExt;
        let app = super::build_router(std::sync::Arc::new(
            super::server::KotobaState::new(None).expect("state"),
        ));
        let uri = format!("/xrpc/{}", super::pds_xrpc::NSID_PDS_SESSION_VERIFY);
        let resp = app
            .oneshot(post_json(
                &uri,
                serde_json::json!({ "token": make_didkey_pop() }),
            ))
            .await
            .unwrap();
        assert_eq!(resp.status(), axum::http::StatusCode::OK);
        let v = body_json(resp).await;
        assert_eq!(v["valid"], serde_json::Value::Bool(true), "body={v}");
        assert!(v["did"].as_str().unwrap().starts_with("did:key:z6Mk"));
    }

    #[tokio::test]
    async fn pds_session_verify_rejects_garbage_token() {
        use tower::ServiceExt;
        let app = super::build_router(std::sync::Arc::new(
            super::server::KotobaState::new(None).expect("state"),
        ));
        let uri = format!("/xrpc/{}", super::pds_xrpc::NSID_PDS_SESSION_VERIFY);
        let resp = app
            .oneshot(post_json(&uri, serde_json::json!({ "token": "not.a.jws" })))
            .await
            .unwrap();
        assert_eq!(resp.status(), axum::http::StatusCode::UNAUTHORIZED);
        assert_eq!(
            body_json(resp).await["valid"],
            serde_json::Value::Bool(false)
        );
    }

    #[tokio::test]
    async fn account_wrapped_ark_put_requires_auth() {
        use tower::ServiceExt;
        let app = super::build_router(std::sync::Arc::new(
            super::server::KotobaState::new(None).expect("state"),
        ));
        let uri = format!(
            "/xrpc/{}",
            super::account_xrpc::NSID_ACCOUNT_PUT_WRAPPED_ARK
        );
        // No Authorization header → owner-auth must reject (not 404, not 200).
        let resp = app
            .oneshot(post_json(
                &uri,
                serde_json::json!({ "did": "did:web:etzhayyim.com:actor:alice", "credentialId": "cred-1", "wrappedArk": "AAAA" }),
            ))
            .await
            .unwrap();
        assert_eq!(resp.status(), axum::http::StatusCode::UNAUTHORIZED);
    }

    #[tokio::test]
    async fn signal_resolve_identity_unknown_returns_404() {
        use tower::ServiceExt;
        let app = super::build_router(std::sync::Arc::new(
            super::server::KotobaState::new(None).expect("state"),
        ));
        let uri = format!(
            "/xrpc/{}?did=did:key:zUnknownActor",
            super::signal_xrpc::NSID_SIGNAL_RESOLVE_IDENTITY
        );
        let req = axum::http::Request::builder()
            .method("GET")
            .uri(&uri)
            .body(axum::body::Body::empty())
            .unwrap();
        let resp = app.oneshot(req).await.unwrap();
        // No binding stored for this DID → 404 (route matched, not 404-no-route).
        assert_eq!(resp.status(), axum::http::StatusCode::NOT_FOUND);
    }

    #[tokio::test]
    async fn signal_publish_identity_requires_auth() {
        use tower::ServiceExt;
        let app = super::build_router(std::sync::Arc::new(
            super::server::KotobaState::new(None).expect("state"),
        ));
        let uri = format!("/xrpc/{}", super::signal_xrpc::NSID_SIGNAL_PUBLISH_IDENTITY);
        // No Authorization header → publish must reject (not store unauthenticated).
        let resp = app
            .oneshot(post_json(
                &uri,
                serde_json::json!({
                    "did": "did:key:zAlice",
                    "signalIdentityKey": "AAAA",
                    "signalDhKey": "AAAA",
                    "signalRegistrationId": 1,
                    "createdAt": "2026-06-02T00:00:00Z",
                    "signature": "AAAA"
                }),
            ))
            .await
            .unwrap();
        assert_eq!(resp.status(), axum::http::StatusCode::UNAUTHORIZED);
    }

    #[tokio::test]
    async fn account_wrapped_ark_put_then_get_roundtrip() {
        use base64::{engine::general_purpose::URL_SAFE_NO_PAD as B64U, Engine as _};
        use tower::ServiceExt;
        let app = super::build_router(std::sync::Arc::new(
            super::server::KotobaState::new(None).expect("state"),
        ));
        let did = "did:web:etzhayyim.com:actor:rt";
        // jwt_sub/jwt_exp_elapsed are signature-agnostic (edge BFF is the trust
        // boundary), so a sub-only, exp-less bearer authenticates as `did`.
        let payload_b64 = B64U.encode(format!("{{\"sub\":\"{did}\"}}").as_bytes());
        let bearer = format!("Bearer x.{payload_b64}.x");
        let wrapped = "QUFBQUFBQUFBQUFB"; // opaque wrap blob (server stores verbatim)

        // PUT — store the wrapped ARK.
        let put_uri = format!(
            "/xrpc/{}",
            super::account_xrpc::NSID_ACCOUNT_PUT_WRAPPED_ARK
        );
        let put_req = axum::http::Request::builder()
            .method("POST")
            .uri(&put_uri)
            .header("content-type", "application/json")
            .header("authorization", &bearer)
            .body(axum::body::Body::from(
                serde_json::json!({ "did": did, "credentialId": "cred-rt", "wrappedArk": wrapped })
                    .to_string(),
            ))
            .unwrap();
        let put_resp = app.clone().oneshot(put_req).await.unwrap();
        assert_eq!(
            put_resp.status(),
            axum::http::StatusCode::OK,
            "put should succeed"
        );

        // GET — same opaque blob comes back (shelf roundtrip through the same state).
        let get_uri = format!(
            "/xrpc/{}?did={}&credentialId=cred-rt",
            super::account_xrpc::NSID_ACCOUNT_GET_WRAPPED_ARK,
            did
        );
        let get_req = axum::http::Request::builder()
            .method("GET")
            .uri(&get_uri)
            .header("authorization", &bearer)
            .body(axum::body::Body::empty())
            .unwrap();
        let get_resp = app.oneshot(get_req).await.unwrap();
        assert_eq!(
            get_resp.status(),
            axum::http::StatusCode::OK,
            "get should succeed"
        );
        let v = body_json(get_resp).await;
        assert_eq!(
            v["wrappedArk"],
            serde_json::Value::String(wrapped.to_string())
        );
        assert_eq!(v["did"], serde_json::Value::String(did.to_string()));
    }

    #[tokio::test]
    async fn account_wrapped_ark_get_missing_returns_404() {
        use base64::{engine::general_purpose::URL_SAFE_NO_PAD as B64U, Engine as _};
        use tower::ServiceExt;
        let app = super::build_router(std::sync::Arc::new(
            super::server::KotobaState::new(None).expect("state"),
        ));
        let did = "did:web:etzhayyim.com:actor:nobody";
        let payload_b64 = B64U.encode(format!("{{\"sub\":\"{did}\"}}").as_bytes());
        let bearer = format!("Bearer x.{payload_b64}.x");
        // Authenticated, but no wrap was ever stored for this (did, credentialId).
        let uri = format!(
            "/xrpc/{}?did={}&credentialId=never-stored",
            super::account_xrpc::NSID_ACCOUNT_GET_WRAPPED_ARK,
            did
        );
        let req = axum::http::Request::builder()
            .method("GET")
            .uri(&uri)
            .header("authorization", &bearer)
            .body(axum::body::Body::empty())
            .unwrap();
        let resp = app.oneshot(req).await.unwrap();
        assert_eq!(resp.status(), axum::http::StatusCode::NOT_FOUND);
    }

    #[tokio::test]
    async fn account_wrapped_ark_rejects_cross_account_access() {
        // The wrapped-ARK store is opaque, but read/write is still gated to the
        // owning member (require_owner_auth: sub == did). A valid token for one
        // account must NOT read or overwrite another account's wrap — otherwise an
        // authenticated member could harvest every other member's key-custody blob
        // or clobber it. This pins that access-control boundary end-to-end.
        use base64::{engine::general_purpose::URL_SAFE_NO_PAD as B64U, Engine as _};
        use tower::ServiceExt;
        let app = super::build_router(std::sync::Arc::new(
            super::server::KotobaState::new(None).expect("state"),
        ));

        let bob = "did:web:etzhayyim.com:actor:bob";
        let alice = "did:web:etzhayyim.com:actor:alice";
        let bob_bearer = format!(
            "Bearer x.{}.x",
            B64U.encode(format!("{{\"sub\":\"{bob}\"}}").as_bytes())
        );
        let alice_bearer = format!(
            "Bearer x.{}.x",
            B64U.encode(format!("{{\"sub\":\"{alice}\"}}").as_bytes())
        );
        let wrapped = "Qk9CX1dSQVA"; // bob's opaque wrap

        // Bob stores his own wrap (baseline).
        let put_uri = format!(
            "/xrpc/{}",
            super::account_xrpc::NSID_ACCOUNT_PUT_WRAPPED_ARK
        );
        let put = app
            .clone()
            .oneshot(
                axum::http::Request::builder()
                    .method("POST")
                    .uri(&put_uri)
                    .header("content-type", "application/json")
                    .header("authorization", &bob_bearer)
                    .body(axum::body::Body::from(
                        serde_json::json!({ "did": bob, "credentialId": "cred-b", "wrappedArk": wrapped })
                            .to_string(),
                    ))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(put.status(), axum::http::StatusCode::OK);

        // Alice (validly authenticated as herself) tries to READ bob's wrap → 401.
        let get_uri = format!(
            "/xrpc/{}?did={}&credentialId=cred-b",
            super::account_xrpc::NSID_ACCOUNT_GET_WRAPPED_ARK,
            bob
        );
        let cross_get = app
            .clone()
            .oneshot(
                axum::http::Request::builder()
                    .method("GET")
                    .uri(&get_uri)
                    .header("authorization", &alice_bearer)
                    .body(axum::body::Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(
            cross_get.status(),
            axum::http::StatusCode::UNAUTHORIZED,
            "alice must not read bob's wrapped ARK"
        );

        // Alice tries to OVERWRITE bob's wrap → 401.
        let cross_put = app
            .clone()
            .oneshot(
                axum::http::Request::builder()
                    .method("POST")
                    .uri(&put_uri)
                    .header("content-type", "application/json")
                    .header("authorization", &alice_bearer)
                    .body(axum::body::Body::from(
                        serde_json::json!({ "did": bob, "credentialId": "cred-b", "wrappedArk": "RVZJTA" })
                            .to_string(),
                    ))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(
            cross_put.status(),
            axum::http::StatusCode::UNAUTHORIZED,
            "alice must not overwrite bob's wrapped ARK"
        );

        // Bob can still read his own, unmodified, wrap (non-vacuous + not clobbered).
        let bob_get = app
            .oneshot(
                axum::http::Request::builder()
                    .method("GET")
                    .uri(&get_uri)
                    .header("authorization", &bob_bearer)
                    .body(axum::body::Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(bob_get.status(), axum::http::StatusCode::OK);
        let v = body_json(bob_get).await;
        assert_eq!(
            v["wrappedArk"],
            serde_json::Value::String(wrapped.to_string()),
            "bob's wrap must be intact (alice's overwrite was rejected)"
        );
    }

    #[tokio::test]
    async fn signal_identity_publish_then_resolve_didkey_roundtrip() {
        use base64::{engine::general_purpose::URL_SAFE_NO_PAD as B64U, Engine as _};
        use ed25519_dalek::SigningKey;
        use kotoba_signal::SignalBinding;
        use tower::ServiceExt;

        let app = super::build_router(std::sync::Arc::new(
            super::server::KotobaState::new(None).expect("state"),
        ));

        // did:key issuer — the binding is signed by the very key the DID encodes,
        // so resolve verifies it trustlessly (no external resolution).
        let did_sk = SigningKey::from_bytes(&[5u8; 32]);
        let did = kotoba_auth::ed25519_pubkey_to_did_key(&did_sk.verifying_key().to_bytes());
        let signal = kotoba_signal::identity::IdentityKeyPair::generate().public_key();
        let binding = SignalBinding::from_identity(&did, &signal, 99, "2026-06-02T00:00:00Z");
        let sig = binding.sign(&did_sk);

        let sub_b64 = B64U.encode(format!("{{\"sub\":\"{did}\"}}").as_bytes());
        let bearer = format!("Bearer x.{sub_b64}.x");

        // PUBLISH — store the DID-signed binding (verified on publish for did:key).
        let pub_uri = format!("/xrpc/{}", super::signal_xrpc::NSID_SIGNAL_PUBLISH_IDENTITY);
        let pub_req = axum::http::Request::builder()
            .method("POST")
            .uri(&pub_uri)
            .header("content-type", "application/json")
            .header("authorization", &bearer)
            .body(axum::body::Body::from(
                serde_json::json!({
                    "did": did,
                    "signalIdentityKey": B64U.encode(&binding.signal_identity_key),
                    "signalDhKey": B64U.encode(&binding.signal_dh_key),
                    "signalRegistrationId": 99,
                    "createdAt": "2026-06-02T00:00:00Z",
                    "signature": B64U.encode(&sig),
                })
                .to_string(),
            ))
            .unwrap();
        let pub_resp = app.clone().oneshot(pub_req).await.unwrap();
        assert_eq!(
            pub_resp.status(),
            axum::http::StatusCode::OK,
            "publish should succeed"
        );
        assert_eq!(
            body_json(pub_resp).await["verifiedOnPublish"],
            serde_json::Value::Bool(true)
        );

        // RESOLVE — the stored binding verifies against the did:key (trustless).
        let res_uri = format!(
            "/xrpc/{}?did={}",
            super::signal_xrpc::NSID_SIGNAL_RESOLVE_IDENTITY,
            did
        );
        let res_req = axum::http::Request::builder()
            .method("GET")
            .uri(&res_uri)
            .body(axum::body::Body::empty())
            .unwrap();
        let res_resp = app.oneshot(res_req).await.unwrap();
        assert_eq!(
            res_resp.status(),
            axum::http::StatusCode::OK,
            "resolve should succeed"
        );
        let v = body_json(res_resp).await;
        assert_eq!(v["verified"], serde_json::Value::Bool(true), "body={v}");
        assert_eq!(v["did"], serde_json::Value::String(did));
    }

    #[tokio::test]
    async fn pds_session_verify_empty_token_returns_400() {
        use tower::ServiceExt;
        let app = super::build_router(std::sync::Arc::new(
            super::server::KotobaState::new(None).expect("state"),
        ));
        let uri = format!("/xrpc/{}", super::pds_xrpc::NSID_PDS_SESSION_VERIFY);
        let resp = app
            .oneshot(post_json(&uri, serde_json::json!({ "token": "" })))
            .await
            .unwrap();
        assert_eq!(resp.status(), axum::http::StatusCode::BAD_REQUEST);
    }

    /// Build a compact EdDSA JWS session PoP for a did:key issuer (resolves with no
    /// network). `sign_sk` lets a test sign with a key other than the DID's, to drive
    /// the invalid branch.
    fn make_didkey_pop_signed_by(
        did_sk: &ed25519_dalek::SigningKey,
        sign_sk: &ed25519_dalek::SigningKey,
        exp: u64,
    ) -> String {
        use base64::{engine::general_purpose::URL_SAFE_NO_PAD as B64U, Engine as _};
        use ed25519_dalek::Signer;
        let did =
            kotoba_auth::did_key::ed25519_pubkey_to_did_key(&did_sk.verifying_key().to_bytes());
        let header =
            B64U.encode(serde_json::to_vec(&serde_json::json!({ "alg": "EdDSA" })).unwrap());
        let payload = B64U.encode(
            serde_json::to_vec(&serde_json::json!({ "iss": did, "sub": did, "exp": exp })).unwrap(),
        );
        let signing_input = format!("{header}.{payload}");
        let sig = sign_sk.sign(signing_input.as_bytes());
        format!("{signing_input}.{}", B64U.encode(sig.to_bytes()))
    }

    #[tokio::test]
    async fn pds_session_verify_valid_didkey_token_returns_200() {
        // End-to-end through the public XRPC endpoint: a valid did:key PoP must map
        // to 200 + valid:true + the issuer DID echoed. The verify_session_pop unit is
        // solid; this pins the handler's verdict→status wiring and the did:key
        // resolution path (no network needed for did:key).
        use ed25519_dalek::SigningKey;
        use tower::ServiceExt;
        let app = super::build_router(std::sync::Arc::new(
            super::server::KotobaState::new(None).expect("state"),
        ));
        let sk = SigningKey::from_bytes(&[11u8; 32]);
        let did = kotoba_auth::did_key::ed25519_pubkey_to_did_key(&sk.verifying_key().to_bytes());
        let token = make_didkey_pop_signed_by(&sk, &sk, 99_999_999_999); // far-future exp vs real clock
        let uri = format!("/xrpc/{}", super::pds_xrpc::NSID_PDS_SESSION_VERIFY);
        let resp = app
            .oneshot(post_json(&uri, serde_json::json!({ "token": token })))
            .await
            .unwrap();
        assert_eq!(
            resp.status(),
            axum::http::StatusCode::OK,
            "valid PoP must return 200"
        );
        let v = body_json(resp).await;
        assert_eq!(v["valid"], serde_json::Value::Bool(true), "body={v}");
        assert_eq!(v["did"], serde_json::Value::String(did));
    }

    #[tokio::test]
    async fn pds_session_verify_invalid_token_returns_401() {
        // The failure branch of the verdict→status mapping: a PoP whose signature is
        // by the wrong key (valid Ed25519, wrong signer) must return 401 + valid:false
        // through the endpoint — not 200, and not a 500.
        use ed25519_dalek::SigningKey;
        use tower::ServiceExt;
        let app = super::build_router(std::sync::Arc::new(
            super::server::KotobaState::new(None).expect("state"),
        ));
        let victim = SigningKey::from_bytes(&[12u8; 32]);
        let attacker = SigningKey::from_bytes(&[13u8; 32]);
        // iss = victim's did:key, but signed by the attacker.
        let token = make_didkey_pop_signed_by(&victim, &attacker, 99_999_999_999);
        let uri = format!("/xrpc/{}", super::pds_xrpc::NSID_PDS_SESSION_VERIFY);
        let resp = app
            .oneshot(post_json(&uri, serde_json::json!({ "token": token })))
            .await
            .unwrap();
        assert_eq!(
            resp.status(),
            axum::http::StatusCode::UNAUTHORIZED,
            "invalid PoP must return 401"
        );
        assert_eq!(
            body_json(resp).await["valid"],
            serde_json::Value::Bool(false)
        );
    }

    #[tokio::test]
    async fn account_put_invalid_credential_id_returns_400() {
        use base64::{engine::general_purpose::URL_SAFE_NO_PAD as B64U, Engine as _};
        use tower::ServiceExt;
        let app = super::build_router(std::sync::Arc::new(
            super::server::KotobaState::new(None).expect("state"),
        ));
        let did = "did:web:etzhayyim.com:actor:badcred";
        let payload_b64 = B64U.encode(format!("{{\"sub\":\"{did}\"}}").as_bytes());
        let bearer = format!("Bearer x.{payload_b64}.x");
        // Authenticated, but credentialId has a path-traversal slash → 400 (validation).
        let uri = format!(
            "/xrpc/{}",
            super::account_xrpc::NSID_ACCOUNT_PUT_WRAPPED_ARK
        );
        let req = axum::http::Request::builder()
            .method("POST")
            .uri(&uri)
            .header("content-type", "application/json")
            .header("authorization", &bearer)
            .body(axum::body::Body::from(
                serde_json::json!({ "did": did, "credentialId": "bad/slash", "wrappedArk": "AAAA" }).to_string(),
            ))
            .unwrap();
        let resp = app.oneshot(req).await.unwrap();
        assert_eq!(resp.status(), axum::http::StatusCode::BAD_REQUEST);
    }

    #[tokio::test]
    async fn signal_publish_didkey_bad_signature_rejected() {
        use base64::{engine::general_purpose::URL_SAFE_NO_PAD as B64U, Engine as _};
        use ed25519_dalek::SigningKey;
        use kotoba_signal::SignalBinding;
        use tower::ServiceExt;

        let app = super::build_router(std::sync::Arc::new(
            super::server::KotobaState::new(None).expect("state"),
        ));
        let did_sk = SigningKey::from_bytes(&[6u8; 32]);
        let did = kotoba_auth::ed25519_pubkey_to_did_key(&did_sk.verifying_key().to_bytes());
        let signal = kotoba_signal::identity::IdentityKeyPair::generate().public_key();
        let binding = SignalBinding::from_identity(&did, &signal, 1, "2026-06-02T00:00:00Z");
        // Corrupt the signature → publish must reject a forged did:key binding (400),
        // since did:key bindings are verified on publish (trustless).
        let mut sig = binding.sign(&did_sk);
        sig[0] ^= 0xFF;

        let sub_b64 = B64U.encode(format!("{{\"sub\":\"{did}\"}}").as_bytes());
        let bearer = format!("Bearer x.{sub_b64}.x");
        let uri = format!("/xrpc/{}", super::signal_xrpc::NSID_SIGNAL_PUBLISH_IDENTITY);
        let req = axum::http::Request::builder()
            .method("POST")
            .uri(&uri)
            .header("content-type", "application/json")
            .header("authorization", &bearer)
            .body(axum::body::Body::from(
                serde_json::json!({
                    "did": did,
                    "signalIdentityKey": B64U.encode(&binding.signal_identity_key),
                    "signalDhKey": B64U.encode(&binding.signal_dh_key),
                    "signalRegistrationId": 1,
                    "createdAt": "2026-06-02T00:00:00Z",
                    "signature": B64U.encode(&sig),
                })
                .to_string(),
            ))
            .unwrap();
        let resp = app.oneshot(req).await.unwrap();
        assert_eq!(
            resp.status(),
            axum::http::StatusCode::BAD_REQUEST,
            "forged did:key binding must be rejected on publish"
        );
    }

    #[tokio::test]
    async fn signal_publish_didkey_valid_signature_by_wrong_key_rejected() {
        // The IMPERSONATION vector (distinct from the corrupted-bytes test above):
        // an attacker who controls their own key wants to publish a binding for a
        // VICTIM's did:key — a DID they do not control. They present a perfectly
        // valid Ed25519 signature, just produced by the WRONG key, and forge the
        // bearer's `sub` (the JWT layer is signature-agnostic at this boundary). The
        // server resolves the victim's did:key to the victim's pubkey and verifies
        // the binding against it, so a structurally-valid-but-wrong-signer signature
        // must still be rejected. A malformed signature passing for a different
        // reason would not prove this.
        use base64::{engine::general_purpose::URL_SAFE_NO_PAD as B64U, Engine as _};
        use ed25519_dalek::SigningKey;
        use kotoba_signal::SignalBinding;
        use tower::ServiceExt;

        let app = super::build_router(std::sync::Arc::new(
            super::server::KotobaState::new(None).expect("state"),
        ));
        let victim_sk = SigningKey::from_bytes(&[7u8; 32]);
        let victim_did =
            kotoba_auth::ed25519_pubkey_to_did_key(&victim_sk.verifying_key().to_bytes());
        let attacker_sk = SigningKey::from_bytes(&[8u8; 32]); // a DIFFERENT key
        let signal = kotoba_signal::identity::IdentityKeyPair::generate().public_key();
        let binding = SignalBinding::from_identity(&victim_did, &signal, 1, "2026-06-02T00:00:00Z");
        // Valid signature — but by the attacker, not the key the victim DID encodes.
        let sig = binding.sign(&attacker_sk);

        // Forge the bearer to claim the victim DID (passes require_signal_auth; the
        // binding-signature check is the gate that must still stop impersonation).
        let sub_b64 = B64U.encode(format!("{{\"sub\":\"{victim_did}\"}}").as_bytes());
        let bearer = format!("Bearer x.{sub_b64}.x");
        let uri = format!("/xrpc/{}", super::signal_xrpc::NSID_SIGNAL_PUBLISH_IDENTITY);
        let req = axum::http::Request::builder()
            .method("POST")
            .uri(&uri)
            .header("content-type", "application/json")
            .header("authorization", &bearer)
            .body(axum::body::Body::from(
                serde_json::json!({
                    "did": victim_did,
                    "signalIdentityKey": B64U.encode(&binding.signal_identity_key),
                    "signalDhKey": B64U.encode(&binding.signal_dh_key),
                    "signalRegistrationId": 1,
                    "createdAt": "2026-06-02T00:00:00Z",
                    "signature": B64U.encode(&sig),
                })
                .to_string(),
            ))
            .unwrap();
        let resp = app.oneshot(req).await.unwrap();
        assert_eq!(
            resp.status(),
            axum::http::StatusCode::BAD_REQUEST,
            "a valid signature by a non-DID key must not let an attacker publish a binding for that DID"
        );
    }
}

pub fn build_router(state: Arc<KotobaState>) -> Router {
    // Access-receipt writer (ADR-sealed-cold-tier R1): single background task
    // batching read receipts into audit-graph commits. Idempotent.
    access_receipt::spawn_receipt_writer(Arc::clone(&state));
    // Wire the realtime cold-lane bridge (ADR-2606060001): periodic durable
    // game snapshots are content-addressed into the block store + announced on
    // the KSE LiveBus. Idempotent; per-frame traffic never touches either.
    realtime::install_cold_lane(state.block_store.clone(), state.journal.clone());
    // Optionally run a real kotoba:kge component as the room sim (room swap).
    #[cfg(feature = "realtime-wasm")]
    if let Ok(path) = std::env::var("KOTOBA_RT_KGE_COMPONENT") {
        match std::fs::read(&path) {
            Ok(bytes) => realtime::install_kge_component(bytes),
            Err(e) => tracing::warn!(path, error = %e, "KOTOBA_RT_KGE_COMPONENT unreadable"),
        }
    }
    Router::new()
        .route("/_app/meta", get(xrpc::health))
        .route(
            &format!("/xrpc/{}", access_receipt::NSID_AUDIT_LIST),
            get(access_receipt::audit_list_receipts),
        )
        .route(
            &format!("/xrpc/{}", access_receipt::NSID_AUDIT_ANCHOR),
            get(access_receipt::audit_anchor_payload),
        )
        .route(
            &format!("/xrpc/{}", access_receipt::NSID_AUDIT_VERIFY),
            get(access_receipt::audit_verify_chain),
        )
        .route(
            &format!("/xrpc/{}", key_share::NSID_KEY_REQUEST_SHARE),
            post(key_share::key_request_share),
        )
        .route(
            &format!("/xrpc/{}", key_share::NSID_KEY_DEPOSIT_SHARE),
            post(key_share::key_deposit_share),
        )
        .route(
            &format!("/xrpc/{}", key_share::NSID_KEY_CUSTODIAN_INFO),
            get(key_share::key_custodian_info),
        )
        .route(
            &format!("/xrpc/{}", key_share::NSID_KEY_REPORT_RELEASE),
            post(key_share::key_report_unreceipted_release),
        )
        .route("/health", get(xrpc::health))
        .route(
            &format!("/xrpc/{}", xrpc::NSID_DATOM_CREATE),
            post(xrpc::datom_create),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_QUAD_CREATE),
            post(xrpc::quad_create),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_INVOKE_RUN),
            post(xrpc::invoke_run),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_NODE_STATUS),
            get(xrpc::node_status),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_BLOCK_PUT),
            // 32 MiB base64 + JSON framing overhead
            post(xrpc::block_put).layer(DefaultBodyLimit::max(34 * 1024 * 1024)),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_BLOCK_GET),
            get(xrpc::block_get),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_IPNS_HEAD),
            get(xrpc::ipns_head),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_IPNS_PUBLISH),
            post(xrpc::ipns_publish),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_COMMIT_GET),
            get(xrpc::commit_get),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_COMMIT_STORE),
            post(xrpc::commit_store),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_GRAPH_QUERY),
            get(xrpc::graph_query),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_ECON_BALANCE),
            post(xrpc::econ_balance),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_ECON_CREDIT),
            post(xrpc::econ_credit),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_WEIGHT_PUT),
            // 512 MiB base64 tensor + JSON framing overhead
            post(xrpc::weight_put).layer(DefaultBodyLimit::max(530 * 1024 * 1024)),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_QUAD_RETRACT),
            post(xrpc::quad_retract),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_DATOMIC_TRANSACT),
            post(xrpc::datomic_transact),
        )
        .route(
            "/xrpc/com.etzhayyim.apps.kotoba.node.register",
            post(xrpc::node_register),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_DATOMIC_DATOMS),
            post(xrpc::datomic_datoms),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_DATOMIC_SEEK_DATOMS),
            post(xrpc::datomic_seek_datoms),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_DATOMIC_INDEX_RANGE),
            post(xrpc::datomic_index_range),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_DATOMIC_INDEX_PULL),
            post(xrpc::datomic_index_pull),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_DATOMIC_PULL),
            post(xrpc::datomic_pull),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_DATOMIC_PULL_MANY),
            post(xrpc::datomic_pull_many),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_DATOMIC_Q),
            // Explicit 1 MiB cap on query bodies (tighter than the 2 MiB axum
            // default) — query_edn/inputs are small; bounds parse/alloc cost.
            post(xrpc::datomic_q).layer(DefaultBodyLimit::max(1024 * 1024)),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_DATOMIC_WITH),
            post(xrpc::datomic_with),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_DATOMIC_AS_OF),
            post(xrpc::datomic_as_of),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_DATOMIC_SINCE),
            post(xrpc::datomic_since),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_DATOMIC_SYNC),
            post(xrpc::datomic_sync),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_DATOMIC_HISTORY),
            post(xrpc::datomic_history),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_DATOMIC_TX),
            post(xrpc::datomic_tx),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_DATOMIC_TX_RANGE),
            post(xrpc::datomic_tx_range),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_DATOMIC_LOG),
            post(xrpc::datomic_log),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_DATOMIC_BASIS_T),
            post(xrpc::datomic_basis_t),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_DATOMIC_DB_STATS),
            post(xrpc::datomic_db_stats),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_DATOMIC_GC),
            post(xrpc::datomic_gc),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_DATOMIC_ENTITY),
            post(xrpc::datomic_entity),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_DATOMIC_IDENT),
            post(xrpc::datomic_ident),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_DATOMIC_ENTID),
            post(xrpc::datomic_entid),
        )
        // ── ai.gftd.apps.kotobase.* aliases (canonical public NSIDs) ─────────
        // Same handlers; the CF Worker at kotobase.net also uses these NSIDs.
        // Registering them here means local dev and production share one namespace.
        .route(
            "/xrpc/ai.gftd.apps.kotobase.datomic.transact",
            post(xrpc::datomic_transact),
        )
        .route(
            "/xrpc/ai.gftd.apps.kotobase.datomic.q",
            post(xrpc::datomic_q).layer(DefaultBodyLimit::max(1024 * 1024)),
        )
        .route(
            "/xrpc/ai.gftd.apps.kotobase.datomic.pull",
            post(xrpc::datomic_pull),
        )
        .route(
            "/xrpc/ai.gftd.apps.kotobase.datomic.pullMany",
            post(xrpc::datomic_pull_many),
        )
        .route(
            "/xrpc/ai.gftd.apps.kotobase.datomic.datoms",
            post(xrpc::datomic_datoms),
        )
        .route(
            "/xrpc/ai.gftd.apps.kotobase.datomic.seekDatoms",
            post(xrpc::datomic_seek_datoms),
        )
        .route(
            "/xrpc/ai.gftd.apps.kotobase.datomic.indexRange",
            post(xrpc::datomic_index_range),
        )
        .route(
            "/xrpc/ai.gftd.apps.kotobase.datomic.indexPull",
            post(xrpc::datomic_index_pull),
        )
        .route(
            "/xrpc/ai.gftd.apps.kotobase.datomic.entity",
            post(xrpc::datomic_entity),
        )
        .route(
            "/xrpc/ai.gftd.apps.kotobase.datomic.ident",
            post(xrpc::datomic_ident),
        )
        .route(
            "/xrpc/ai.gftd.apps.kotobase.datomic.entid",
            post(xrpc::datomic_entid),
        )
        .route(
            "/xrpc/ai.gftd.apps.kotobase.datomic.asOf",
            post(xrpc::datomic_as_of),
        )
        .route(
            "/xrpc/ai.gftd.apps.kotobase.datomic.since",
            post(xrpc::datomic_since),
        )
        .route(
            "/xrpc/ai.gftd.apps.kotobase.datomic.sync",
            post(xrpc::datomic_sync),
        )
        .route(
            "/xrpc/ai.gftd.apps.kotobase.datomic.history",
            post(xrpc::datomic_history),
        )
        .route(
            "/xrpc/ai.gftd.apps.kotobase.datomic.tx",
            post(xrpc::datomic_tx),
        )
        .route(
            "/xrpc/ai.gftd.apps.kotobase.datomic.txRange",
            post(xrpc::datomic_tx_range),
        )
        .route(
            "/xrpc/ai.gftd.apps.kotobase.datomic.log",
            post(xrpc::datomic_log),
        )
        .route(
            "/xrpc/ai.gftd.apps.kotobase.datomic.basisT",
            post(xrpc::datomic_basis_t),
        )
        .route(
            "/xrpc/ai.gftd.apps.kotobase.datomic.dbStats",
            post(xrpc::datomic_db_stats),
        )
        .route(
            "/xrpc/ai.gftd.apps.kotobase.datomic.with",
            post(xrpc::datomic_with),
        )
        .route(
            "/xrpc/ai.gftd.apps.kotobase.graph.query",
            post(xrpc::graph_query),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_VC_ISSUE),
            post(xrpc::vc_issue),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_VC_PRESENT),
            post(xrpc::vc_present),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_DID_DOCUMENT_PUBLISH),
            post(xrpc::did_document_publish),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_DIDCOMM_SEND),
            post(xrpc::didcomm_send),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_ATPROTO_REPO_WRITE),
            post(xrpc::atproto_repo_write),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_WEIGHT_GET),
            get(xrpc::weight_get),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_LORA_APPLY),
            // 128 MiB LoRA adapter base64 + JSON framing overhead
            post(xrpc::lora_apply).layer(DefaultBodyLimit::max(136 * 1024 * 1024)),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_EMBED_CREATE),
            post(xrpc::embed_create),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_INFER_RUN),
            post(xrpc::infer_run),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_AGENT_RUN),
            post(xrpc::agent_run),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_AGENT_SYNC_OPEN),
            post(xrpc::agent_sync_open),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_AGENT_SYNC_ADV),
            post(xrpc::agent_sync_advance),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_AGENT_SYNC_CLOSE),
            post(xrpc::agent_sync_close),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_VAULT_PUT),
            post(xrpc::vault_put),
        )
        .route(
            &format!("/xrpc/{}", xrpc::NSID_VAULT_GET),
            get(xrpc::vault_get),
        )
        .route(&format!("/xrpc/{}", kg::NSID_KG_ENTITY), get(kg::kg_entity))
        .route(
            &format!("/xrpc/{}", kg::NSID_KG_CATALOG),
            get(kg::kg_catalog),
        )
        .route(&format!("/xrpc/{}", kg::NSID_KG_EMBED), post(kg::kg_embed))
        .route(&format!("/xrpc/{}", kg::NSID_KG_SEARCH), get(kg::kg_search))
        .route(
            &format!("/xrpc/{}", kg::NSID_KG_QUERY),
            post(kg::kg_query).layer(DefaultBodyLimit::max(1024 * 1024)),
        )
        .route(
            &format!("/xrpc/{}", kg::NSID_KG_MV_REGISTER),
            post(kg::kg_mv_register),
        )
        .route(
            &format!("/xrpc/{}", kg::NSID_KG_MV_RESULT),
            post(kg::kg_mv_result),
        )
        .route(
            &format!("/xrpc/{}", kg::NSID_KG_SPARQL),
            post(kg::kg_sparql),
        )
        .route(
            &format!("/xrpc/{}", kg::NSID_KG_INGEST),
            post(kg::kg_ingest),
        )
        .route(
            &format!("/xrpc/{}", kg::NSID_KG_INGEST_BATCH),
            post(kg::kg_ingest_batch),
        )
        // ── ai.gftd.apps.kotobase.kg.* aliases (canonical public NSIDs) ──────
        .route(
            &format!("/xrpc/{}", kg::NSID_KG_INGEST_ALIAS),
            post(kg::kg_ingest),
        )
        .route(
            &format!("/xrpc/{}", kg::NSID_KG_INGEST_BATCH_ALIAS),
            post(kg::kg_ingest_batch),
        )
        .route(
            &format!("/xrpc/{}", kg::NSID_KG_DELETE),
            post(kg::kg_delete),
        )
        .route(
            &format!("/xrpc/{}", kg::NSID_KG_COMMIT),
            post(kg::kg_commit),
        )
        // MCP body limit: 50 MB to allow kotoba_wasm_run with large WASM payloads
        .route(
            "/mcp",
            post(mcp::mcp_handler).layer(DefaultBodyLimit::max(50 * 1024 * 1024)),
        )
        // ── kotobase multi-tenant pinning service (ADR-2605260001) ──────────
        .route(
            &format!("/xrpc/{}", kotobase_xrpc::NSID_ACCOUNT_CREATE),
            post(kotobase_xrpc::handle_account_create),
        )
        .route(
            &format!("/xrpc/{}", kotobase_xrpc::NSID_ACCOUNT_STATUS),
            post(kotobase_xrpc::handle_account_status),
        )
        .route(
            &format!("/xrpc/{}", kotobase_xrpc::NSID_PIN_CREATE),
            post(kotobase_xrpc::handle_pin_create),
        )
        .route(
            &format!("/xrpc/{}", kotobase_xrpc::NSID_PIN_LIST),
            post(kotobase_xrpc::handle_pin_list),
        )
        .route(
            &format!("/xrpc/{}", kotobase_xrpc::NSID_PIN_DELETE),
            post(kotobase_xrpc::handle_pin_delete),
        )
        .route(
            &format!("/xrpc/{}", kotobase_xrpc::NSID_USAGE_GET),
            post(kotobase_xrpc::handle_usage_get),
        )
        .route(
            &format!("/xrpc/{}", kotobase_xrpc::NSID_PRE_REVOKE),
            post(kotobase_xrpc::handle_pre_revoke),
        )
        // ── Common Crawl vector search / RAG ───────────────────────────────
        .route(
            &format!("/xrpc/{}", social_xrpc::NSID_SOCIAL_CAPITAL),
            get(social_xrpc::social_capital),
        )
        .route(
            &format!("/xrpc/{}", cc_xrpc::NSID_CC_SEARCH),
            get(cc_xrpc::cc_search),
        )
        .route(
            &format!("/xrpc/{}", cc_xrpc::NSID_CC_RAG),
            post(cc_xrpc::cc_rag),
        )
        .route(
            &format!("/xrpc/{}", cc_xrpc::NSID_CC_INGEST),
            post(cc_xrpc::cc_ingest),
        )
        .route(
            &format!("/xrpc/{}", cc_xrpc::NSID_CC_STATUS),
            get(cc_xrpc::cc_status),
        )
        // ── Hybrid web search (lexical + semantic + authority) ─────────────
        .route(
            &format!("/xrpc/{}", cc_xrpc::NSID_WEB_SEARCH),
            get(cc_xrpc::web_search),
        )
        .route(
            &format!("/xrpc/{}", cc_xrpc::NSID_SEARCH_REINDEX),
            post(cc_xrpc::search_reindex),
        )
        // ── Multimodal cross-modal search ──────────────────────────────────
        .route(
            &format!("/xrpc/{}", media_xrpc::NSID_MEDIA_SEARCH),
            get(media_xrpc::media_search),
        )
        .route(
            &format!("/xrpc/{}", media_xrpc::NSID_MEDIA_INGEST),
            post(media_xrpc::media_ingest)
                .layer(DefaultBodyLimit::max(media_xrpc::MEDIA_INGEST_BODY_LIMIT)),
        )
        .route(
            &format!("/xrpc/{}", media_xrpc::NSID_MEDIA_STATUS),
            get(media_xrpc::media_status),
        )
        // ── Email E2E XRPC ──────────────────────────────────────────────────
        .route(
            &format!("/xrpc/{}", email_xrpc::NSID_EMAIL_LIST),
            get(email_xrpc::email_list),
        )
        .route(
            &format!("/xrpc/{}", email_xrpc::NSID_EMAIL_READ),
            get(email_xrpc::email_read),
        )
        .route(
            &format!("/xrpc/{}", email_xrpc::NSID_EMAIL_INGEST),
            // 33 MiB raw email base64 + JSON framing overhead
            post(email_xrpc::email_ingest).layer(DefaultBodyLimit::max(36 * 1024 * 1024)),
        )
        .route(
            &format!("/xrpc/{}", email_xrpc::NSID_EMAIL_SEND),
            // up to 256 recipients × 1 MiB Signal envelope + JSON framing
            post(email_xrpc::email_send).layer(DefaultBodyLimit::max(300 * 1024 * 1024)),
        )
        // ── Signal Protocol E2E (com.etzhayyim.signal.*) ─────────────────────────
        .route(
            &format!("/xrpc/{}", signal_xrpc::NSID_SIGNAL_REGISTER_PREKEYS),
            // 256 KiB: two 64 KiB bundles + DID/device_id fields + JSON framing
            post(signal_xrpc::register_prekeys).layer(DefaultBodyLimit::max(256 * 1024)),
        )
        .route(
            &format!("/xrpc/{}", signal_xrpc::NSID_SIGNAL_GET_PREKEY_BUNDLE),
            get(signal_xrpc::get_prekey_bundle),
        )
        .route(
            &format!("/xrpc/{}", signal_xrpc::NSID_SIGNAL_SEND_MESSAGE),
            post(signal_xrpc::send_message),
        )
        .route(
            &format!("/xrpc/{}", signal_xrpc::NSID_SIGNAL_SEND_GROUP_MESSAGE),
            post(signal_xrpc::send_group_message),
        )
        .route(
            &format!("/xrpc/{}", signal_xrpc::NSID_SIGNAL_DISTRIBUTE_SENDER_KEY),
            post(signal_xrpc::distribute_sender_key),
        )
        .route(
            &format!("/xrpc/{}", signal_xrpc::NSID_SIGNAL_PUBLISH_IDENTITY),
            post(signal_xrpc::publish_signal_identity),
        )
        .route(
            &format!("/xrpc/{}", signal_xrpc::NSID_SIGNAL_RESOLVE_IDENTITY),
            get(signal_xrpc::resolve_signal_identity),
        )
        // ── Account key custody (wrapped-ARK store, ADR-2606014000 L1) ──────
        .route(
            &format!("/xrpc/{}", account_xrpc::NSID_ACCOUNT_PUT_WRAPPED_ARK),
            post(account_xrpc::put_wrapped_ark),
        )
        .route(
            &format!("/xrpc/{}", account_xrpc::NSID_ACCOUNT_GET_WRAPPED_ARK),
            get(account_xrpc::get_wrapped_ark),
        )
        // ── PDS session auth (ADR-2606015000 — PDS-on-kotoba refactor) ──────
        .route(
            &format!("/xrpc/{}", pds_xrpc::NSID_PDS_SESSION_VERIFY),
            post(pds_xrpc::session_verify),
        )
        // ── Attestation ────────────────────────────────────────────────────
        .route(
            &format!("/xrpc/{}", attestation::NSID_ATTEST_CLAIM),
            post(attestation::attest_claim),
        )
        .route(
            &format!("/xrpc/{}", attestation::NSID_ATTEST_CHALLENGE),
            post(attestation::attest_challenge),
        )
        .route(
            &format!("/xrpc/{}", attestation::NSID_ATTEST_QUERY),
            get(attestation::attest_query),
        )
        .route(
            &format!("/xrpc/{}", attestation::NSID_REQUEST_LOG),
            get(attestation::request_log_query),
        )
        // ── Firehose egress (D): SSE live-tail + JSON cursor paging over LiveBus ──
        .route(
            &format!("/xrpc/{}", firehose::NSID_SYNC_SUBSCRIBE),
            get(firehose::subscribe),
        )
        .route(
            &format!("/xrpc/{}", firehose::NSID_SYNC_EVENTS),
            get(firehose::events),
        )
        .route(
            &format!("/xrpc/{}", firehose::NSID_SYNC_EVENTS_FROM_COMMITS),
            get(firehose::events_from_commits),
        )
        .route(
            &format!("/xrpc/{}", firehose::NSID_SYNC_EVENTS_ALL_GRAPHS),
            get(firehose::events_all_graphs),
        )
        // ── Realtime ingress (ADR-2606060001): bidirectional WebSocket (T1) ──
        // The bus is per-room and isolated from the firehose/gossip above.
        .route(
            &format!("/xrpc/{}", realtime::NSID_SYNC_CONNECT),
            get(realtime::ws_connect),
        )
        // ── Git smart-HTTP (clone / fetch / push over datomic + IPFS) ───────
        .route("/git/:repo/info/refs", get(git_http::info_refs))
        .route(
            "/git/:repo/git-upload-pack",
            post(git_http::upload_pack).layer(DefaultBodyLimit::max(git_http::GIT_BODY_LIMIT)),
        )
        .route(
            "/git/:repo/git-receive-pack",
            post(git_http::receive_pack).layer(DefaultBodyLimit::max(git_http::GIT_BODY_LIMIT)),
        )
        // ── Generic XRPC dispatch ──────────────────────────────────────────
        .route(
            &format!(
                "/xrpc/{}",
                crate::availability_xrpc::NSID_AVAILABILITY_CHALLENGE
            ),
            post(crate::availability_xrpc::availability_challenge),
        )
        .route("/xrpc/:nsid", post(xrpc::generic_invoke))
        .route_layer(middleware::from_fn_with_state(
            Arc::clone(&state),
            fingerprint::fingerprint_middleware,
        ))
        .with_state(state)
        .layer(TraceLayer::new_for_http())
}

/// Start the kotoba server, blocking until shutdown.
/// All configuration is read from environment variables (same as the binary).
pub async fn run() -> anyhow::Result<()> {
    use std::sync::Arc;

    tracing::info!(
        definition = "Datom[CID/T] × EAVT × Pregel[BSP] × Datalog[Δ] × LLM × WASM/WIT",
        "kotoba starting"
    );

    let inference_engine: Option<server::InferenceFn> = if let Ok(_url) =
        std::env::var("KOTOBA_INFERENCE_URL")
    {
        let model =
            std::env::var("KOTOBA_INFERENCE_MODEL").unwrap_or_else(|_| "gemma4:e4b".to_string());
        tracing::info!(_url, model, "HTTP inference engine active");
        let engine = kotoba_llm::HttpInferEngine::from_env()
            .map_err(|e| anyhow::anyhow!("HttpInferEngine init failed: {e}"))?;
        let engine = Arc::new(engine);
        let fn_: server::InferenceFn =
            Arc::new(move |prompt: &str, max_tokens: usize| engine.generate(prompt, max_tokens));
        Some(fn_)
    } else if std::env::var("KOTOBA_LOAD_GEMMA").is_ok() {
        #[cfg(feature = "local-inference")]
        {
            use kotoba_llm::GemmaRunner;
            tracing::info!(
                "loading Gemma 2 2B IT from HuggingFace Hub (first run downloads ~5 GB)..."
            );
            let runner = Arc::new(std::sync::Mutex::new(
                GemmaRunner::load()
                    .await
                    .map_err(|e| anyhow::anyhow!("Gemma load failed: {e}"))?,
            ));
            tracing::info!("Gemma 2 2B IT loaded");
            let engine: server::InferenceFn = Arc::new(move |prompt: &str, max_tokens: usize| {
                runner
                    .lock()
                    .unwrap_or_else(|e| e.into_inner())
                    .generate(prompt, max_tokens)
            });
            Some(engine)
        }
        #[cfg(not(feature = "local-inference"))]
        {
            tracing::warn!(
                "KOTOBA_LOAD_GEMMA is set but the `local-inference` feature is not enabled.\n\
                     Rebuild with: cargo build -p kotoba-server --features local-inference"
            );
            None
        }
    } else {
        None
    };

    let state = server::KotobaState::new(inference_engine)?;
    let state = state.init_crypto().await?;
    // Make the operator-trusted PRE substrate live (persistent grants).
    // Additive — does not change the quad read/write path (ADR-2605240001 §28.5).
    let state = state.init_pre_key_registry().await;

    // IPFS daemon liveness probe — non-fatal but logs a clear warning so the
    // operator notices when Kubo isn't reachable.  Skipped when KOTOBA_IPFS=off.
    let ipfs_off = std::env::var("KOTOBA_IPFS")
        .map(|v| v.eq_ignore_ascii_case("off") || v == "0" || v.eq_ignore_ascii_case("false"))
        .unwrap_or(false);
    if !ipfs_off {
        let probe = kotoba_store::KuboBlockStore::from_env();
        match probe.probe_version().await {
            Ok((ver, commit)) => tracing::info!(
                kubo_version = %ver,
                kubo_commit  = %commit,
                "IPFS daemon reachable"
            ),
            Err(e) => tracing::warn!(
                error  = %e,
                hint   = "set KOTOBA_IPFS=off to silence, or start `ipfs daemon`",
                "IPFS daemon NOT reachable — block writes/reads will fall back to hot cache only"
            ),
        }
    }

    tracing::info!(
        version  = state.version,
        node_id  = %hex::encode(state.local_node_id.0),
        did      = %state.operator_did,
        "KSE LiveBus + Shelf + KDHT Neighborhood ready"
    );

    state.register_node().await;

    #[cfg(feature = "p2p")]
    let state = if std::env::var("KOTOBA_NO_SWARM").is_err() {
        use kotoba_net::KotobaSwarm;
        use kotoba_vm::distributed::DistributedPregelRunner;

        let (pregel_inbound_tx, pregel_outbound_rx, pregel_runner) =
            DistributedPregelRunner::channel_pair(1024);
        let state = state.attach_pregel(pregel_runner);

        let listen_port: u16 = std::env::var("KOTOBA_P2P_PORT")
            .ok()
            .and_then(|p| p.parse().ok())
            .unwrap_or(0);
        let listen_addr = kotoba_net::quic_addr(listen_port);

        // A node with the `relay` role is a designated public helper: it bridges
        // the firehose gossip AND runs the libp2p Circuit Relay v2 server so NAT'd
        // (donated/edge) peers can reach the mesh through it. AutoNAT + DCUtR +
        // relay-client are always on, so edge nodes need no extra config.
        let relay_server = state
            .node_roles
            .iter()
            .any(|r| matches!(r, server::NodeRole::Relay));
        let nat_cfg = kotoba_net::NatConfig { relay_server };

        // Persistent libp2p identity: a 32-byte hex seed in KOTOBA_P2P_ED25519_HEX
        // pins the PeerId (and relay reservations / addresses) across restarts.
        // Kept separate from the CACAO/DID agent key by design. Absent/invalid →
        // ephemeral per-boot identity (previous behaviour).
        let swarm_result = match std::env::var("KOTOBA_P2P_ED25519_HEX") {
            Ok(seed_hex) => match kotoba_net::ed25519_keypair_from_hex(&seed_hex) {
                Ok(kp) => KotobaSwarm::with_config(kp, listen_addr, nat_cfg).await,
                Err(e) => {
                    tracing::warn!(
                        "KOTOBA_P2P_ED25519_HEX invalid ({e}); using ephemeral identity"
                    );
                    KotobaSwarm::new_with_config(listen_addr, nat_cfg).await
                }
            },
            Err(_) => KotobaSwarm::new_with_config(listen_addr, nat_cfg).await,
        };

        match swarm_result {
            Ok(mut swarm) => {
                // Advertise externally reachable address(es) (comma-separated
                // multiaddrs). REQUIRED for a relay-server node to be usable: a
                // relay only includes addresses in its reservation responses if
                // it has confirmed external addresses, otherwise clients reject
                // the reservation with `NoAddressesInReservation`. Where AutoNAT
                // cannot confirm (e.g. a known public IP / port-forward), set this.
                if let Ok(ext_str) = std::env::var("KOTOBA_P2P_EXTERNAL_ADDR") {
                    for entry in ext_str.split(',') {
                        let entry = entry.trim();
                        if entry.is_empty() {
                            continue;
                        }
                        match entry.parse::<kotoba_net::Multiaddr>() {
                            Ok(addr) => {
                                swarm.add_external_address(addr.clone());
                                tracing::info!(%addr, "advertising external address");
                            }
                            Err(e) => tracing::warn!("invalid external multiaddr: {e}"),
                        }
                    }
                }

                if let Ok(peers_str) = std::env::var("KOTOBA_BOOTSTRAP_PEERS") {
                    let mut bootstrapped = false;
                    for entry in peers_str.split(',') {
                        let entry = entry.trim();
                        if entry.is_empty() {
                            continue;
                        }
                        if let Some((pid_str, addr_str)) = entry.split_once('@') {
                            match (
                                pid_str.trim().parse::<kotoba_net::PeerId>(),
                                addr_str.trim().parse::<kotoba_net::Multiaddr>(),
                            ) {
                                (Ok(peer_id), Ok(addr)) => {
                                    swarm.add_peer(peer_id, addr.clone());
                                    tracing::info!(%peer_id, %addr, "added bootstrap peer");
                                    bootstrapped = true;
                                }
                                (Err(e), _) => tracing::warn!("invalid peer_id: {e}"),
                                (_, Err(e)) => tracing::warn!("invalid multiaddr: {e}"),
                            }
                        }
                    }
                    if bootstrapped {
                        swarm.bootstrap().ok();
                        tracing::info!("Kademlia bootstrap triggered");
                    }
                }

                // Edge/NAT'd nodes: take a Circuit Relay v2 reservation on each
                // configured relay (`peerid@multiaddr`, comma-separated) so peers
                // can reach us via the relay; DCUtR then upgrades to a direct link.
                if let Ok(relays_str) = std::env::var("KOTOBA_RELAY_PEERS") {
                    for entry in relays_str.split(',') {
                        let entry = entry.trim();
                        if entry.is_empty() {
                            continue;
                        }
                        if let Some((pid_str, addr_str)) = entry.split_once('@') {
                            match (
                                pid_str.trim().parse::<kotoba_net::PeerId>(),
                                addr_str.trim().parse::<kotoba_net::Multiaddr>(),
                            ) {
                                (Ok(peer_id), Ok(addr)) => {
                                    swarm.add_peer(peer_id, addr.clone());
                                    match swarm.reserve_relay_with_peer(peer_id, addr.clone()) {
                                        Ok(()) => tracing::info!(
                                            %peer_id, %addr,
                                            "reserving Circuit Relay v2 slot"
                                        ),
                                        Err(e) => tracing::warn!(
                                            %peer_id, %addr,
                                            "relay reservation failed: {e}"
                                        ),
                                    }
                                }
                                (Err(e), _) => tracing::warn!("invalid relay peer_id: {e}"),
                                (_, Err(e)) => tracing::warn!("invalid relay multiaddr: {e}"),
                            }
                        }
                    }
                }

                let (publish_tx, publish_rx) =
                    tokio::sync::mpsc::channel::<(String, Vec<u8>)>(1024);

                let journal_arc = Arc::clone(&state.journal);
                let block_store_arc = Arc::clone(&state.block_store);
                let quad_store_arc = Arc::clone(&state.quad_store);
                // Same `relay` role drives both the firehose bridge and the
                // libp2p relay server (computed above as `relay_server`).
                let relay = relay_server;

                tokio::spawn(net_actor::run(
                    swarm,
                    publish_rx,
                    journal_arc,
                    pregel_inbound_tx,
                    pregel_outbound_rx,
                    block_store_arc,
                    quad_store_arc,
                    state.pre_key_registry.clone(),
                    relay,
                ));

                tracing::info!("kotoba-net swarm started (QUIC + GossipSub + Kademlia)");
                state.attach_gossip(publish_tx)
            }
            Err(e) => {
                tracing::warn!(err = %e, "swarm init failed — running without p2p");
                state
            }
        }
    } else {
        tracing::info!("KOTOBA_NO_SWARM set — skipping p2p swarm");
        state
    };
    #[cfg(not(feature = "p2p"))]
    let state = {
        if std::env::var("KOTOBA_NO_SWARM").is_err() {
            tracing::info!("p2p swarm disabled at compile time; rebuild with --features p2p to enable libp2p networking");
        }
        state
    };

    if std::env::var("KOTOBA_GMAIL_CLIENT_ID").is_ok() {
        if let Some(ref crypto) = state.crypto {
            let cr = Arc::clone(crypto);
            let vt = Arc::clone(&state.vault);
            let qs = Arc::clone(&state.quad_store);
            tokio::spawn(kotoba_ingest::gmail_poll_loop(cr, vt, qs));
        }
    }

    if std::env::var("KOTOBA_JETSTREAM").is_ok() {
        let journal_arc = Arc::clone(&state.journal);
        let quad_store_arc = Arc::clone(&state.quad_store);
        tokio::spawn(kotoba_graph::run_jetstream_client(
            journal_arc,
            quad_store_arc,
        ));
        tracing::info!("Jetstream client started");
    }

    if std::env::var("KOTOBA_SUBSCRIBE_REPOS").is_ok() {
        let journal_arc = Arc::clone(&state.journal);
        let quad_store_arc = Arc::clone(&state.quad_store);
        let block_store_arc = Arc::clone(&state.block_store);
        let gossip_tx = state.gossip_tx.clone();
        tokio::spawn(kotoba_graph::run_subscribe_repos(
            journal_arc,
            quad_store_arc,
            block_store_arc,
            gossip_tx,
        ));
        tracing::info!("subscribeRepos firehose client started");
    }

    let state = Arc::new(state);

    // Warm the resident `db_before` cache for every registered graph in the
    // background, so the first `datomic.transact` after this (re)start is a cache
    // HIT instead of an inline O(graph) cold `db_from_head` scan on the request
    // path (ADR-2605302130 / kotoba#19). Spawned — never blocks serve. This is the
    // best-effort, all-graphs auto-warm (single pass, no retry).
    tokio::spawn(Arc::clone(&state).warm_datomic_live_caches());

    // Targeted retry backstop over the auto-warm above: for explicitly-configured
    // large graphs, re-warm OFF the request path with bounded exponential-backoff
    // retry so a transient cold-load failure (the cold-start failure yukkuri hit on
    // `yukkuri-kg-v3`) does not leave the graph permanently cold. Comma-separated
    // graph CIDs in `KOTOBA_DATOMIC_WARM_GRAPHS`; idempotent vs the auto-warm
    // (each warm skips a graph already resident at the same head).
    if let Ok(graphs) = std::env::var("KOTOBA_DATOMIC_WARM_GRAPHS") {
        for spec in graphs.split(',').map(str::trim).filter(|s| !s.is_empty()) {
            let Some(graph_cid) = kotoba_core::cid::KotobaCid::from_multibase(spec) else {
                tracing::warn!(graph = %spec, "KOTOBA_DATOMIC_WARM_GRAPHS: invalid graph CID, skipping");
                continue;
            };
            let state = Arc::clone(&state);
            tokio::spawn(async move {
                let ipns_name = xrpc::distributed_graph_ipns_name(&graph_cid);
                let graph_mb = graph_cid.to_multibase();
                let mut backoff_secs = 2u64;
                for attempt in 1..=6u32 {
                    match xrpc::warm_datomic_resident_cache(&state, &graph_cid, &ipns_name).await {
                        Ok(outcome) => {
                            tracing::info!(graph = %graph_mb, ?outcome, attempt, "datomic resident cache warm");
                            break;
                        }
                        Err(e) => {
                            tracing::warn!(graph = %graph_mb, attempt, err = %e, "datomic resident cache warm failed; retrying");
                            tokio::time::sleep(std::time::Duration::from_secs(backoff_secs)).await;
                            backoff_secs = (backoff_secs * 2).min(60);
                        }
                    }
                }
            });
        }
    }

    let app = build_router(Arc::clone(&state));

    let port = std::env::var("KOTOBA_PORT")
        .ok()
        .and_then(|p| p.parse::<u16>().ok())
        .unwrap_or(8080);
    let addr = std::net::SocketAddr::from(([0, 0, 0, 0], port));

    tracing::info!(%addr, "kotoba listening");
    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, app).await?;
    Ok(())
}
