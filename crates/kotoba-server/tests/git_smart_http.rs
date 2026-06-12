//! End-to-end: a **real `git` client** clones, pushes and fetches against the
//! kotoba server's git smart-HTTP endpoints, and every object is verified to
//! have landed as an IPFS block + `:git/*` Datom projection (datomic).
//!
//! This is the integration proof for "git fully supported on kotoba datomic +
//! IPFS": no GitHub, no on-disk git repo on the server side — the server stores
//! objects as content-addressed blocks and serves the wire protocol from them.

use std::path::Path;
use std::process::Command;
use std::sync::Arc;

use kotoba_server::build_router;
use kotoba_server::server::KotobaState;

/// Run `git` in `cwd` with a hermetic environment (no user/system config, no
/// credential prompt). Panics with captured stderr on failure.
fn git(cwd: &Path, args: &[&str]) -> String {
    let out = Command::new("git")
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
        .expect("failed to spawn git");
    assert!(
        out.status.success(),
        "git {args:?} failed:\nstdout: {}\nstderr: {}",
        String::from_utf8_lossy(&out.stdout),
        String::from_utf8_lossy(&out.stderr),
    );
    String::from_utf8_lossy(&out.stdout).trim().to_string()
}

fn git_available() -> bool {
    Command::new("git").arg("--version").output().is_ok()
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn real_git_clone_push_fetch_over_kotoba() {
    if !git_available() {
        eprintln!("skipping: git CLI not available");
        return;
    }

    // Reads are public; push is anonymous (local-dev posture) so the real git
    // client needs no credentials. These gates are exercised by the handlers.
    std::env::set_var("KOTOBA_DEFAULT_VISIBILITY", "public");
    std::env::set_var("KOTOBA_GIT_ALLOW_ANON_PUSH", "1");

    // ── Boot the kotoba server (in-memory block store; no Kubo). ──────────────
    let state = Arc::new(KotobaState::new(None).expect("KotobaState::new"));
    let state_probe = Arc::clone(&state);
    let router = build_router(Arc::clone(&state));
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    tokio::spawn(async move {
        axum::serve(listener, router).await.unwrap();
    });
    let repo_url = format!("http://127.0.0.1:{}/git/demo", addr.port());

    // ── Scratch workspace. ────────────────────────────────────────────────────
    let work = std::env::temp_dir().join(format!(
        "kotoba-git-e2e-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    let src = work.join("src");
    let clone = work.join("clone");
    std::fs::create_dir_all(&src).unwrap();

    // ── Build a source repo with one commit and push it to kotoba. ────────────
    git(&src, &["init", "-q", "-b", "main", "."]);
    std::fs::write(src.join("hello.txt"), b"hello kotoba\n").unwrap();
    git(&src, &["add", "."]);
    git(&src, &["commit", "-q", "-m", "first"]);
    let head1 = git(&src, &["rev-parse", "HEAD"]);

    git(&src, &["push", "-q", &repo_url, "main:refs/heads/main"]);

    // The push must have materialised objects in datomic + IPFS. Probe directly.
    {
        let conn = state_probe.git_connection("demo").await;
        let git_store = kotoba_git::GitStore::new(&conn, &*state_probe.block_store);
        let db = git_store.db();
        let objs = kotoba_git::all_objects(&db);
        assert!(
            objs.len() >= 3,
            "expected >=3 objects (blob+tree+commit) projected as datoms, got {}",
            objs.len()
        );
        // Every projected object round-trips byte-exact from its IPFS block.
        for (oid, _cid) in &objs {
            let framed = git_store.materialize_framed(&db, *oid).unwrap();
            assert_eq!(kotoba_git::GitOid::of_framed(&framed), *oid);
        }
        // The pushed ref resolves to the client's HEAD.
        assert_eq!(
            kotoba_git::resolve_ref(&db, "refs/heads/main").map(|o| o.to_hex()),
            Some(head1.clone())
        );
    }

    // ── Clone it back with a fresh git and verify the content + tip. ──────────
    git(&work, &["clone", "-q", &repo_url, "clone"]);
    let cloned = std::fs::read_to_string(clone.join("hello.txt")).unwrap();
    assert_eq!(cloned, "hello kotoba\n");
    let cloned_head = git(&clone, &["rev-parse", "HEAD"]);
    assert_eq!(cloned_head, head1, "cloned tip must equal pushed tip");

    // ── Second commit on the source, push, then incremental fetch in clone. ───
    std::fs::write(src.join("hello.txt"), b"hello kotoba v2\n").unwrap();
    git(&src, &["add", "."]);
    git(&src, &["commit", "-q", "-m", "second"]);
    let head2 = git(&src, &["rev-parse", "HEAD"]);
    git(&src, &["push", "-q", &repo_url, "main:refs/heads/main"]);

    git(&clone, &["fetch", "-q", "origin"]);
    let fetched_tip = git(&clone, &["rev-parse", "origin/main"]);
    assert_eq!(
        fetched_tip, head2,
        "incremental fetch must deliver the new tip"
    );

    // ── Clean up scratch dir (best-effort). ──────────────────────────────────
    let _ = std::fs::remove_dir_all(&work);
}
