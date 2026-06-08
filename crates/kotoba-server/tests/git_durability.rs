//! Durability: a pushed repo survives the loss of its in-memory projection.
//!
//! With a `KseStore` configured (`KOTOBA_STORE_PATH`), a push persists the
//! repo's snapshot-manifest pointer durably and the manifest + object blocks
//! live in the block store. We then **drop the resident `Connection`** (the
//! datomic projection) — exactly what a process restart loses — and clone
//! again. The clone forces `git_connection` to rehydrate the projection purely
//! from the durable manifest, proving the repo is reconstructable from
//! datomic-snapshot + IPFS blocks rather than living only in RAM.

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
async fn pushed_repo_survives_projection_loss() {
    if Command::new("git").arg("--version").output().is_err() {
        eprintln!("skipping: git CLI not available");
        return;
    }

    // The server roots its KseStore at parent(KOTOBA_STORE_PATH), so give the
    // store path a *unique* parent dir to isolate this run's durable pointers.
    let base = std::env::temp_dir().join(format!(
        "kotoba-git-durable-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    let store_path = base.join("store");
    std::fs::create_dir_all(&store_path).unwrap();

    // KseStore (mutable pointer boundary) → file-backed so the snapshot pointer
    // is durable. Reads public, push anonymous.
    std::env::set_var("KOTOBA_STORE_PATH", &store_path);
    std::env::set_var("KOTOBA_DEFAULT_VISIBILITY", "public");
    std::env::set_var("KOTOBA_GIT_ALLOW_ANON_PUSH", "1");

    let state = Arc::new(KotobaState::new(None).expect("KotobaState::new"));
    assert!(
        state.kse_store.is_some(),
        "KOTOBA_STORE_PATH should yield a KseStore (durable pointer boundary)"
    );
    let probe = Arc::clone(&state);
    let router = build_router(Arc::clone(&state));
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    tokio::spawn(async move {
        axum::serve(listener, router).await.unwrap();
    });
    let url = format!("http://127.0.0.1:{}/git/durable", addr.port());

    let work = std::env::temp_dir().join(format!(
        "kotoba-git-durable-work-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    let src = work.join("src");
    std::fs::create_dir_all(&src).unwrap();

    git(&src, &["init", "-q", "-b", "main", "."]);
    std::fs::write(src.join("data.txt"), b"durable content\n").unwrap();
    git(&src, &["add", "."]);
    git(&src, &["commit", "-q", "-m", "c1"]);
    let head = git(&src, &["rev-parse", "HEAD"]);
    git(&src, &["push", "-q", &url, "main:refs/heads/main"]);

    // ── Simulate a restart: discard the resident datomic projection. ──────────
    {
        let mut repos = probe.git_repos.write().await;
        assert!(repos.contains_key("durable"), "repo should be resident after push");
        repos.clear();
    }

    // Clone now: the server must rehydrate "durable" from the persisted manifest.
    git(&work, &["clone", "-q", &url, "clone"]);
    let got = std::fs::read_to_string(work.join("clone").join("data.txt")).unwrap();
    assert_eq!(got, "durable content\n");
    let cloned_head = git(&work.join("clone"), &["rev-parse", "HEAD"]);
    assert_eq!(cloned_head, head, "rehydrated tip must equal the pushed tip");

    let _ = std::fs::remove_dir_all(&work);
    let _ = std::fs::remove_dir_all(&base);
}
