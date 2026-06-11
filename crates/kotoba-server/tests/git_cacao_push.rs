//! Push authorization via a **CACAO capability** (`git.receive/push`).
//!
//! Instead of anonymous push or an operator Bearer JWT, the client presents a
//! CACAO — a signed, capability-scoped delegation — in the `x-kotoba-cacao`
//! header. The server accepts the push iff the CACAO grants `git.receive/push`
//! on scope `git/repo/<repo>` and is rooted at the operator DID. This is the
//! governance-delegable push-authority path.

use std::path::Path;
use std::process::Command;
use std::sync::Arc;

use base64::{engine::general_purpose::STANDARD as B64, engine::general_purpose::URL_SAFE_NO_PAD, Engine};
use ed25519_dalek::{Signer, SigningKey};
use kotoba_auth::did_key::ed25519_pubkey_to_did_key;
use kotoba_auth::{Cacao, CacaoHeader, CacaoPayload, CacaoSig};
use kotoba_server::build_router;
use kotoba_server::server::KotobaState;

/// Deterministic operator key for the test (32-byte hex seed).
const SEED_HEX: &str = "1111111111111111111111111111111111111111111111111111111111111111";

fn build_cacao(scope: &str, capability: &str, aud: &str, nonce: &str) -> String {
    let sk = SigningKey::from_bytes(&hex::decode(SEED_HEX).unwrap().try_into().unwrap());
    let did = ed25519_pubkey_to_did_key(sk.verifying_key().as_bytes());
    let mut cacao = Cacao {
        h: CacaoHeader { t: "caip122".into() },
        p: CacaoPayload {
            iss: did.clone(),
            aud: aud.to_string(),
            issued_at: "2026-05-26T00:00:00Z".into(),
            expiry: Some("2099-01-01T00:00:00Z".into()),
            nonce: nonce.into(),
            domain: "kotoba.git".into(),
            statement: None,
            version: "1".into(),
            resources: vec![
                format!("kotoba://graph/{scope}"),
                format!("kotoba://can/{capability}"),
            ],
        },
        s: CacaoSig { t: "EdDSA".into(), s: String::new() },
    };
    let sig: ed25519_dalek::Signature = sk.sign(cacao.siwe_message().as_bytes());
    cacao.s.s = URL_SAFE_NO_PAD.encode(sig.to_bytes());
    let mut cbor = Vec::new();
    ciborium::into_writer(&cacao, &mut cbor).unwrap();
    B64.encode(&cbor)
}

fn operator_did() -> String {
    let sk = SigningKey::from_bytes(&hex::decode(SEED_HEX).unwrap().try_into().unwrap());
    ed25519_pubkey_to_did_key(sk.verifying_key().as_bytes())
}

/// Run git; return Ok(stdout) on success, Err(stderr) on failure (so callers
/// can assert *both* outcomes).
fn git(cwd: &Path, header: Option<&str>, args: &[&str]) -> Result<String, String> {
    let mut cmd = Command::new("git");
    if let Some(h) = header {
        cmd.arg("-c").arg(format!("http.extraHeader=x-kotoba-cacao: {h}"));
    }
    let out = cmd
        .args(args)
        .current_dir(cwd)
        .env("GIT_CONFIG_GLOBAL", "/dev/null")
        .env("GIT_CONFIG_SYSTEM", "/dev/null")
        .env("GIT_TERMINAL_PROMPT", "0")
        .env("GIT_AUTHOR_NAME", "t")
        .env("GIT_AUTHOR_EMAIL", "t@t")
        .env("GIT_COMMITTER_NAME", "t")
        .env("GIT_COMMITTER_EMAIL", "t@t")
        .output()
        .expect("spawn git");
    if out.status.success() {
        Ok(String::from_utf8_lossy(&out.stdout).trim().to_string())
    } else {
        Err(String::from_utf8_lossy(&out.stderr).to_string())
    }
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn push_authorized_by_cacao_capability() {
    if Command::new("git").arg("--version").output().is_err() {
        eprintln!("skipping: git CLI not available");
        return;
    }

    // Deterministic operator identity. AgentIdentity::from_env only honors the
    // seed when all three vars are present, and takes the DID verbatim — so we
    // set KOTOBA_AGENT_DID to the did:key derived from the same seed the CACAO
    // is signed with. NO anon push, NO public read.
    std::env::set_var("KOTOBA_AGENT_ED25519_HEX", SEED_HEX);
    std::env::set_var(
        "KOTOBA_AGENT_X25519_HEX",
        "2222222222222222222222222222222222222222222222222222222222222222",
    );
    std::env::set_var("KOTOBA_AGENT_DID", operator_did());
    std::env::remove_var("KOTOBA_GIT_ALLOW_ANON_PUSH");
    std::env::remove_var("KOTOBA_DEFAULT_VISIBILITY");

    let state = Arc::new(KotobaState::new(None).expect("KotobaState::new"));
    assert_eq!(
        state.operator_did,
        operator_did(),
        "server operator DID must derive from the same seed the CACAO is signed with"
    );
    let probe = Arc::clone(&state);
    let router = build_router(Arc::clone(&state));
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    tokio::spawn(async move {
        axum::serve(listener, router).await.unwrap();
    });
    let url = format!("http://127.0.0.1:{}/git/cacaorepo", addr.port());
    let did = operator_did();

    let work = std::env::temp_dir().join(format!(
        "kotoba-git-cacao-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    let src = work.join("src");
    std::fs::create_dir_all(&src).unwrap();
    git(&src, None, &["init", "-q", "-b", "main", "."]).unwrap();
    std::fs::write(src.join("f.txt"), b"cacao-gated\n").unwrap();
    git(&src, None, &["add", "."]).unwrap();
    git(&src, None, &["commit", "-q", "-m", "c1"]).unwrap();
    let head = git(&src, None, &["rev-parse", "HEAD"]).unwrap();

    // 1. NEGATIVE: no credential at all → push rejected.
    let no_cred = git(&src, None, &["push", "-q", &url, "main:refs/heads/main"]);
    assert!(no_cred.is_err(), "push with no credential must be rejected");

    // 2. NEGATIVE: a CACAO granting only `datom:read` → wrong capability → rejected.
    let read_cacao = build_cacao("git/repo/cacaorepo", "datom:read", &did, "n-read");
    let wrong_cap = git(
        &src,
        Some(&read_cacao),
        &["push", "-q", &url, "main:refs/heads/main"],
    );
    assert!(wrong_cap.is_err(), "a datom:read CACAO must not authorize push");

    // 3. POSITIVE: a CACAO granting `git.receive/push` on this repo → accepted.
    let push_cacao = build_cacao("git/repo/cacaorepo", "git.receive/push", &did, "n-push");
    git(
        &src,
        Some(&push_cacao),
        &["push", "-q", &url, "main:refs/heads/main"],
    )
    .expect("git.receive/push CACAO must authorize the push");

    // The ref landed in the projection.
    let conn = probe.git_connection("cacaorepo").await;
    let git_store = kotoba_git::GitStore::new(&conn, &*probe.block_store);
    assert_eq!(
        kotoba_git::resolve_ref(&git_store.db(), "refs/heads/main").map(|o| o.to_hex()),
        Some(head)
    );

    let _ = std::fs::remove_dir_all(&work);
    std::env::remove_var("KOTOBA_AGENT_ED25519_HEX");
    std::env::remove_var("KOTOBA_AGENT_X25519_HEX");
    std::env::remove_var("KOTOBA_AGENT_DID");
}
