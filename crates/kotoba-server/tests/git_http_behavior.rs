//! HTTP-surface behaviour of the git endpoints: protocol guard + auth gates.
//!
//! This binary deliberately sets **no** git env vars, so the node runs at its
//! defaults — `KOTOBA_DEFAULT_VISIBILITY` unset ⇒ private reads, and anonymous
//! push disabled. That lets us assert the gates actually reject unauthenticated
//! access (the inverse of the happy-path clone/push tests, which opt into
//! public reads + anon push).

use std::sync::Arc;

use kotoba_server::build_router;
use kotoba_server::server::KotobaState;

async fn boot() -> String {
    let state = Arc::new(KotobaState::new(None).expect("KotobaState::new"));
    let router = build_router(state);
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    tokio::spawn(async move {
        axum::serve(listener, router).await.unwrap();
    });
    format!("http://127.0.0.1:{}", addr.port())
}

#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
async fn protocol_guard_and_auth_gates() {
    let base = boot().await;
    let client = reqwest::Client::new();

    // 1. info/refs without ?service= → only the smart protocol is supported.
    let r = client
        .get(format!("{base}/git/repo/info/refs"))
        .send()
        .await
        .unwrap();
    assert_eq!(r.status().as_u16(), 403, "missing ?service= must be 403");

    // 2. Private read (no auth) → denied (4xx, not a 200 advertisement).
    let r = client
        .get(format!("{base}/git/repo/info/refs?service=git-upload-pack"))
        .send()
        .await
        .unwrap();
    assert!(
        r.status().is_client_error(),
        "private read without auth must be denied, got {}",
        r.status()
    );

    // 3. Push discovery (no auth, anon push off) → denied.
    let r = client
        .get(format!(
            "{base}/git/repo/info/refs?service=git-receive-pack"
        ))
        .send()
        .await
        .unwrap();
    assert_eq!(
        r.status().as_u16(),
        401,
        "receive-pack discovery without operator auth must be 401"
    );

    // 4. receive-pack POST (no auth) → rejected at the gate, before body parse.
    let r = client
        .post(format!("{base}/git/repo/git-receive-pack"))
        .body(Vec::<u8>::new())
        .send()
        .await
        .unwrap();
    assert_eq!(r.status().as_u16(), 401, "unauthenticated push must be 401");
}
