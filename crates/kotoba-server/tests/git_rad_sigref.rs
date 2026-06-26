//! End-to-end ADR-2606251200 (a): a real `git push`, authorized by a repo's
//! **kotoba-rad delegate** (not the node operator), lands a signed **sigref**
//! attestation back in that repo's identity journal.
//!
//! Chain under test:
//!   journal (`KOTOBA_RAD_JOURNAL_DIR`) declares `:rad/delegate` = a did:key
//!     → push_gate resolves repo → RID → delegates → `verify_cacao_rad_push`
//!     → receive_pack ingests the pack
//!     → `rad_attest_push` appends `:rad/sigref { head, by, sig }` to the journal.
//!
//! The delegate is listed in the kotoba-rad `z<hex>` form while the CACAO issuer
//! is the W3C `z6Mk…` form for the SAME key — so this also exercises the
//! cross-encoding `did_keys_equal` bridge through the live HTTP path.

use std::path::Path;
use std::process::Command;
use std::sync::Arc;

use base64::{
    engine::general_purpose::STANDARD as B64, engine::general_purpose::URL_SAFE_NO_PAD, Engine,
};
use ed25519_dalek::{Signer, SigningKey};
use kotoba_auth::did_key::{ed25519_pubkey_to_did_key, ed25519_pubkey_to_did_key_hex};
use kotoba_auth::{Cacao, CacaoHeader, CacaoPayload, CacaoSig};
use kotoba_server::build_router;
use kotoba_server::server::KotobaState;

const OPERATOR_SEED: &str = "1111111111111111111111111111111111111111111111111111111111111111";
const DELEGATE_SEED: &str = "3333333333333333333333333333333333333333333333333333333333333333";
const RID: &str = "bafrid0000000000000000000000000000000000000000000000000000";

fn signing_key(seed_hex: &str) -> SigningKey {
    SigningKey::from_bytes(&hex::decode(seed_hex).unwrap().try_into().unwrap())
}

fn did_std(seed_hex: &str) -> String {
    ed25519_pubkey_to_did_key(signing_key(seed_hex).verifying_key().as_bytes())
}

fn did_hex(seed_hex: &str) -> String {
    ed25519_pubkey_to_did_key_hex(signing_key(seed_hex).verifying_key().as_bytes())
}

/// CACAO granting `git.receive/push` on `git/repo/<RID>`, issued by the delegate
/// (`DELEGATE_SEED`, standard form), audience = node operator.
fn delegate_push_cacao(aud: &str, nonce: &str) -> String {
    let sk = signing_key(DELEGATE_SEED);
    let mut cacao = Cacao {
        h: CacaoHeader {
            t: "caip122".into(),
        },
        p: CacaoPayload {
            iss: did_std(DELEGATE_SEED),
            aud: aud.to_string(),
            issued_at: "2026-06-26T00:00:00Z".into(),
            expiry: Some("2099-01-01T00:00:00Z".into()),
            nonce: nonce.into(),
            domain: "kotoba.git".into(),
            statement: None,
            version: "1".into(),
            resources: vec![
                format!("kotoba://graph/git/repo/{RID}"),
                "kotoba://can/git.receive/push".into(),
            ],
        },
        s: CacaoSig {
            t: "EdDSA".into(),
            s: String::new(),
        },
    };
    let sig: ed25519_dalek::Signature = sk.sign(cacao.siwe_message().as_bytes());
    cacao.s.s = URL_SAFE_NO_PAD.encode(sig.to_bytes());
    let mut cbor = Vec::new();
    ciborium::into_writer(&cacao, &mut cbor).unwrap();
    B64.encode(&cbor)
}

fn git(cwd: &Path, header: Option<&str>, args: &[&str]) -> Result<String, String> {
    let mut cmd = Command::new("git");
    if let Some(h) = header {
        cmd.arg("-c")
            .arg(format!("http.extraHeader=x-kotoba-cacao: {h}"));
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
async fn rad_delegate_push_writes_sigref() {
    if Command::new("git").arg("--version").output().is_err() {
        eprintln!("skipping: git CLI not available");
        return;
    }

    let work = std::env::temp_dir().join(format!(
        "kotoba-rad-sigref-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    let journal_dir = work.join("rad");
    std::fs::create_dir_all(&journal_dir).unwrap();
    let journal = journal_dir.join("aburi.identity.journal.edn");

    // Genesis journal: delegate listed in the rad z<hex> form (cross-encoding).
    let genesis = format!(
        "[{rid:?} :rad/type :identity 1 :add]\n\
         [{rid:?} :rad/name \"aburi\" 1 :add]\n\
         [{rid:?} :rad/repo \"github.com/etzhayyim/com-etzhayyim-aburi\" 1 :add]\n\
         [{rid:?} :rad/delegate {dele:?} 1 :add]\n",
        rid = RID,
        dele = did_hex(DELEGATE_SEED),
    );
    std::fs::write(&journal, &genesis).unwrap();

    // Server identity = OPERATOR_SEED; the registry reads our journal dir; no anon.
    std::env::set_var("KOTOBA_AGENT_ED25519_HEX", OPERATOR_SEED);
    std::env::set_var(
        "KOTOBA_AGENT_X25519_HEX",
        "2222222222222222222222222222222222222222222222222222222222222222",
    );
    std::env::set_var("KOTOBA_AGENT_DID", did_std(OPERATOR_SEED));
    std::env::set_var("KOTOBA_RAD_JOURNAL_DIR", &journal_dir);
    std::env::remove_var("KOTOBA_GIT_ALLOW_ANON_PUSH");
    std::env::remove_var("KOTOBA_DEFAULT_VISIBILITY");

    let state = Arc::new(KotobaState::new(None).expect("KotobaState::new"));
    let operator_did = state.operator_did.clone();
    let router = build_router(Arc::clone(&state));
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    tokio::spawn(async move {
        axum::serve(listener, router).await.unwrap();
    });
    // Push to the human name; the registry maps it → RID.
    let url = format!("http://127.0.0.1:{}/git/aburi", addr.port());

    let src = work.join("src");
    std::fs::create_dir_all(&src).unwrap();
    git(&src, None, &["init", "-q", "-b", "main", "."]).unwrap();
    std::fs::write(src.join("f.txt"), b"sovereign\n").unwrap();
    git(&src, None, &["add", "."]).unwrap();
    git(&src, None, &["commit", "-q", "-m", "c1"]).unwrap();

    // NEGATIVE: a CACAO from a NON-delegate key (operator seed) must be rejected
    // by the rad-rooted gate — sovereignty is the repo's delegates, not whoever.
    let stranger = {
        // sign a push CACAO with the OPERATOR seed (not a delegate of this repo)
        let sk = signing_key(OPERATOR_SEED);
        let mut c = Cacao {
            h: CacaoHeader {
                t: "caip122".into(),
            },
            p: CacaoPayload {
                iss: did_std(OPERATOR_SEED),
                aud: operator_did.clone(),
                issued_at: "2026-06-26T00:00:00Z".into(),
                expiry: Some("2099-01-01T00:00:00Z".into()),
                nonce: "stranger".into(),
                domain: "kotoba.git".into(),
                statement: None,
                version: "1".into(),
                resources: vec![
                    format!("kotoba://graph/git/repo/{RID}"),
                    "kotoba://can/git.receive/push".into(),
                ],
            },
            s: CacaoSig {
                t: "EdDSA".into(),
                s: String::new(),
            },
        };
        let sig: ed25519_dalek::Signature = sk.sign(c.siwe_message().as_bytes());
        c.s.s = URL_SAFE_NO_PAD.encode(sig.to_bytes());
        let mut cbor = Vec::new();
        ciborium::into_writer(&c, &mut cbor).unwrap();
        B64.encode(&cbor)
    };
    let denied = git(
        &src,
        Some(&stranger),
        &["push", "-q", &url, "main:refs/heads/main"],
    );
    assert!(
        denied.is_err(),
        "a non-delegate CACAO must be rejected by the rad-rooted gate"
    );

    // POSITIVE: the delegate's CACAO authorizes the push.
    let cacao = delegate_push_cacao(&operator_did, "push-1");
    git(
        &src,
        Some(&cacao),
        &["push", "-q", &url, "main:refs/heads/main"],
    )
    .expect("delegate CACAO must authorize the push");

    // A-3: the journal now carries a signed sigref for this RID.
    let after = std::fs::read_to_string(&journal).unwrap();
    assert!(
        after.contains(&format!("[\"sigref:{RID}\" :rad/type :sigref")),
        "expected a sigref datom, journal:\n{after}"
    );
    assert!(
        after.contains(":rad/sig "),
        "sigref must carry the push CACAO as :rad/sig"
    );
    assert!(
        after.contains(&format!(":rad/by \"{}\"", did_std(DELEGATE_SEED))),
        "sigref :rad/by must be the delegate (CACAO issuer)"
    );

    let _ = std::fs::remove_dir_all(&work);
    std::env::remove_var("KOTOBA_AGENT_ED25519_HEX");
    std::env::remove_var("KOTOBA_AGENT_X25519_HEX");
    std::env::remove_var("KOTOBA_AGENT_DID");
    std::env::remove_var("KOTOBA_RAD_JOURNAL_DIR");
}
