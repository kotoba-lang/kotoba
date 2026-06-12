//! Delta-compressed push: exercise the packfile **delta ingest** path with a
//! pack a *real* git produced.
//!
//! Two commits whose large blobs differ by one line — git's `pack-objects`
//! deltifies the second blob against the first (OFS_DELTA), so the pushed pack
//! is not all-full-objects. The server's streaming ingest must resolve those
//! deltas and store byte-exact objects. We verify by (a) cloning back the exact
//! content and (b) confirming both blob versions round-trip byte-exact from
//! their IPFS blocks on the server.

use std::path::Path;
use std::process::Command;
use std::sync::Arc;

use kotoba_server::build_router;
use kotoba_server::server::KotobaState;

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
        .expect("spawn git");
    assert!(
        out.status.success(),
        "git {args:?} failed:\n{}",
        String::from_utf8_lossy(&out.stderr)
    );
    String::from_utf8_lossy(&out.stdout).trim().to_string()
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn real_git_delta_compressed_push_ingests_correctly() {
    if Command::new("git").arg("--version").output().is_err() {
        eprintln!("skipping: git CLI not available");
        return;
    }
    std::env::set_var("KOTOBA_DEFAULT_VISIBILITY", "public");
    std::env::set_var("KOTOBA_GIT_ALLOW_ANON_PUSH", "1");

    let state = Arc::new(KotobaState::new(None).expect("KotobaState::new"));
    let probe = Arc::clone(&state);
    let router = build_router(Arc::clone(&state));
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    tokio::spawn(async move {
        axum::serve(listener, router).await.unwrap();
    });
    let url = format!("http://127.0.0.1:{}/git/delta", addr.port());

    let work = std::env::temp_dir().join(format!(
        "kotoba-git-delta-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    let src = work.join("src");
    std::fs::create_dir_all(&src).unwrap();
    git(&src, &["init", "-q", "-b", "main", "."]);

    // Six commits of a *growing* file: each version shares a long common prefix
    // with the previous one (only new lines appended, identical line content),
    // which `pack-objects` deltifies (copy whole base + append). Verified to
    // produce delta chains with `git verify-pack`.
    let versions: Vec<(String, String)> = (1..=6)
        .map(|n| {
            let content: String = (0..n * 1500).map(|i| format!("line {i}\n")).collect();
            std::fs::write(src.join("big.txt"), &content).unwrap();
            git(&src, &["add", "."]);
            git(&src, &["commit", "-q", "-m", &format!("c{n}")]);
            let blob = git(&src, &["rev-parse", "HEAD:big.txt"]);
            (blob, content)
        })
        .collect();
    let head = git(&src, &["rev-parse", "HEAD"]);
    let latest = versions.last().unwrap().1.clone();

    // Push all six commits at once → the pack send-pack builds carries deltas.
    git(&src, &["push", "-q", &url, "main:refs/heads/main"]);

    // Server side: EVERY blob version round-trips byte-exact. A mishandled delta
    // would corrupt at least one version's bytes, so this is a real delta-ingest
    // correctness check, not just "the tip is there".
    {
        let conn = probe.git_connection("delta").await;
        let gs = kotoba_git::GitStore::new(&conn, &*probe.block_store);
        let db = gs.db();
        for (hex, want) in &versions {
            let oid = kotoba_git::GitOid::from_hex(hex).unwrap();
            let obj = gs
                .materialize_object(&db, oid)
                .expect("blob present after delta ingest");
            assert_eq!(
                &String::from_utf8_lossy(&obj.body),
                want,
                "blob {hex} byte-exact"
            );
            assert_eq!(
                obj.oid().to_hex(),
                *hex,
                "recomputed oid matches (fidelity)"
            );
        }
        assert_eq!(
            kotoba_git::resolve_ref(&db, "refs/heads/main").map(|o| o.to_hex()),
            Some(head.clone())
        );
    }

    // Clone back: the checked-out content equals the latest version.
    git(&work, &["clone", "-q", &url, "clone"]);
    assert_eq!(
        std::fs::read_to_string(work.join("clone").join("big.txt")).unwrap(),
        latest
    );

    let _ = std::fs::remove_dir_all(&work);
}
