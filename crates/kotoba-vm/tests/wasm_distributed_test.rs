//! Integration tests: WASM Component Model compute driven by the cross-node
//! `DistributedPregelRunner`.
//!
//! These exercise the wiring added so that a compiled WASM guest can run as the
//! per-vertex compute of the *distributed* runner (not just the in-process
//! `WasmPregelRunner`). The same `wasm_compute_fn` that backs the single-node
//! runner is handed to `DistributedPregelRunner::run`, so:
//!
//!   * each node runs the WASM guest only on its locally-owned vertices, and
//!   * any message a guest emits for a non-local `dst` is captured by the runner
//!     and pushed onto `outbound_tx` (which the server layer gossips over
//!     libp2p via `KotobaSwarm::send_pregel_message`).
//!
//! The cross-node *message bus* itself is covered by
//! `distributed_cross_node_test.rs` (in-memory relay) and `kotoba-net`'s
//! `swarm_gossip_test.rs` (real libp2p). Here we prove the **compute** half:
//! WASM actually executes inside the distributed runner, on each node.
//!
//! Tests self-skip when `cargo-component` / `wasm32-wasip2` are unavailable
//! (mirrors `wasm_pregel.rs`'s own integration test).

use std::sync::Arc;

use kotoba_vm::distributed::{DistributedMessage, DistributedPregelRunner};
use kotoba_vm::pregel::{Message, VertexId};
use kotoba_vm::{wasm_compute_fn, wasm_vertex_gas_and_quads};
use kotoba_runtime::WasmExecutor;

use tokio::sync::mpsc;
use tokio::time::{sleep, Duration};

// ---------------------------------------------------------------------------
// Test 1: WASM runs as the compute of a single distributed-runner vertex
// ---------------------------------------------------------------------------

#[tokio::test]
async fn wasm_runs_on_distributed_runner_single_node() {
    let Some(wasm_bytes) = build_guest_component() else {
        eprintln!("skipping: cargo-component / wasm guest unavailable");
        return;
    };
    let wasm_bytes = Arc::new(wasm_bytes);
    let executor = Arc::new(WasmExecutor::new(10_000_000).expect("executor"));

    // A distributed runner with a single locally-owned WASM vertex.
    let (_in_tx, _out_rx, mut runner) = DistributedPregelRunner::channel_pair(64);
    let vid = VertexId::from("wasm::node-A");
    runner.add_local_vertex(vid.clone(), Vec::new());

    // Seed the vertex with the ctx CBOR (carried in the message payload).
    runner.graph.inject_message(Message {
        src: VertexId::from("__seed__"),
        dst: vid.clone(),
        payload: make_ctx_cbor("pregel-graph", b"hello distributed wasm"),
    });

    let compute = wasm_compute_fn(
        Arc::clone(&executor),
        "wasm_distributed_single_cid",
        Arc::clone(&wasm_bytes),
        "did:plc:kotoba-distributed-test",
    );

    // echo-assert guest asserts 1 quad and returns {"status":"ok"} → halts after
    // one superstep.
    let results = runner.run(compute, 8).await;
    assert_eq!(
        results.len(),
        1,
        "echo-assert guest should halt after exactly 1 distributed superstep"
    );
    assert_eq!(
        results[0].active_count, 1,
        "the seeded WASM vertex should be active in superstep 1"
    );

    // The WASM guest actually executed: its accumulated state is persisted on the
    // vertex, with gas burned and one quad asserted.
    let state = runner
        .graph
        .vertex(&vid)
        .map(|v| v.state.clone())
        .expect("local vertex must exist after run");
    let (gas, quads) =
        wasm_vertex_gas_and_quads(&state).expect("vertex state must decode as WASM state");
    assert!(gas > 0, "WASM execution should consume gas, got {gas}");
    assert_eq!(quads, 1, "echo-assert guest should accumulate exactly 1 quad");
}

// ---------------------------------------------------------------------------
// Test 2: compute is distributed — two nodes each run WASM on their own vertex
// ---------------------------------------------------------------------------

#[tokio::test]
async fn wasm_compute_distributed_across_two_nodes() {
    let Some(wasm_bytes) = build_guest_component() else {
        eprintln!("skipping: cargo-component / wasm guest unavailable");
        return;
    };
    let wasm_bytes = Arc::new(wasm_bytes);
    let executor = Arc::new(WasmExecutor::new(10_000_000).expect("executor"));

    // Two runners wired together through bidirectional relays — exactly the role
    // `KotobaSwarm` gossip plays in production (see distributed_cross_node_test).
    let (in1_tx, out1_rx, mut runner1) = DistributedPregelRunner::channel_pair(64);
    let (in2_tx, out2_rx, mut runner2) = DistributedPregelRunner::channel_pair(64);

    let vid_a = VertexId::from("wasm::node-1::A");
    let vid_b = VertexId::from("wasm::node-2::B");

    // Vertex ownership is partitioned: node1 owns A, node2 owns B. Each node only
    // computes WASM for its locally-owned vertex.
    runner1.add_local_vertex(vid_a.clone(), Vec::new());
    runner2.add_local_vertex(vid_b.clone(), Vec::new());

    let relay_1to2 = spawn_relay(out1_rx, in2_tx);
    let relay_2to1 = spawn_relay(out2_rx, in1_tx);

    // Seed each node's vertex with its own ctx.
    runner1.graph.inject_message(Message {
        src: VertexId::from("__seed__"),
        dst: vid_a.clone(),
        payload: make_ctx_cbor("graph-node1", b"work for node 1"),
    });
    runner2.graph.inject_message(Message {
        src: VertexId::from("__seed__"),
        dst: vid_b.clone(),
        payload: make_ctx_cbor("graph-node2", b"work for node 2"),
    });

    let compute1 = wasm_compute_fn(
        Arc::clone(&executor),
        "wasm_distributed_node1_cid",
        Arc::clone(&wasm_bytes),
        "did:plc:node-1",
    );
    let compute2 = wasm_compute_fn(
        Arc::clone(&executor),
        "wasm_distributed_node2_cid",
        Arc::clone(&wasm_bytes),
        "did:plc:node-2",
    );

    // Drive both nodes. They execute independently; the echo-assert guest emits
    // no inter-vertex messages, so nothing crosses the relay this round.
    let r1 = runner1.run(compute1, 8).await;
    let r2 = runner2.run(compute2, 8).await;
    sleep(Duration::from_millis(20)).await;

    assert_eq!(r1.len(), 1, "node1 WASM vertex halts after 1 superstep");
    assert_eq!(r2.len(), 1, "node2 WASM vertex halts after 1 superstep");

    // Both nodes computed WASM locally — proof that compute is distributed across
    // instances (each node ran the guest only for the vertex it owns).
    for (label, runner, vid) in [
        ("node1", &runner1, &vid_a),
        ("node2", &runner2, &vid_b),
    ] {
        let state = runner
            .graph
            .vertex(vid)
            .map(|v| v.state.clone())
            .unwrap_or_else(|| panic!("{label}: local vertex must exist"));
        let (gas, quads) = wasm_vertex_gas_and_quads(&state)
            .unwrap_or_else(|| panic!("{label}: vertex state must decode"));
        assert!(gas > 0, "{label}: WASM should burn gas, got {gas}");
        assert_eq!(quads, 1, "{label}: should accumulate 1 quad");
    }

    // Clean up the relays.
    drop(runner1);
    drop(runner2);
    let f1 = relay_1to2.await.expect("relay 1→2 joins");
    let f2 = relay_2to1.await.expect("relay 2→1 joins");
    // echo-assert emits no remote messages; true cross-node WASM message-passing
    // is gated on a guest ABI that lets a guest address other vertices (follow-up).
    assert_eq!(f1, 0, "echo-assert guest emits no remote messages (node1→node2)");
    assert_eq!(f2, 0, "echo-assert guest emits no remote messages (node2→node1)");
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/// Forward every outbound message of one runner to another runner's inbound
/// channel (the role `KotobaSwarm` plays in production). Returns the number of
/// messages forwarded.
fn spawn_relay(
    mut outbound_rx: mpsc::Receiver<DistributedMessage>,
    inbound_tx: mpsc::Sender<DistributedMessage>,
) -> tokio::task::JoinHandle<usize> {
    tokio::spawn(async move {
        let mut forwarded = 0usize;
        while let Some(msg) = outbound_rx.recv().await {
            if inbound_tx.send(msg).await.is_err() {
                break;
            }
            forwarded += 1;
        }
        forwarded
    })
}

fn make_ctx_cbor(graph: &str, args: &[u8]) -> Vec<u8> {
    use std::collections::BTreeMap;
    let mut map: BTreeMap<&str, ciborium::Value> = BTreeMap::new();
    map.insert("graph", ciborium::Value::Text(graph.to_string()));
    map.insert("session_cid", ciborium::Value::Null);
    map.insert("args_cbor", ciborium::Value::Bytes(args.to_vec()));
    let mut buf = Vec::new();
    ciborium::into_writer(&map, &mut buf).expect("cbor encode");
    buf
}

/// Build the `kotoba-guest` echo-assert Component (mirrors the helper in
/// `wasm_pregel.rs`'s own tests). Returns `None` if the toolchain is missing.
fn build_guest_component() -> Option<Vec<u8>> {
    use std::process::Command;
    let manifest = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let workspace = manifest.parent().unwrap().parent().unwrap();

    let status = Command::new("cargo")
        .args([
            "component",
            "build",
            "--manifest-path",
            "crates/kotoba-guest/Cargo.toml",
            "--target",
            "wasm32-wasip2",
            "--release",
            "--quiet",
        ])
        .current_dir(workspace)
        .status();

    let Ok(s) = status else {
        eprintln!("cargo component not available — skipping WASM distributed test");
        return None;
    };
    if !s.success() {
        eprintln!("kotoba-guest build failed — skipping WASM distributed test");
        return None;
    }

    let wasm_path = workspace.join("target/wasm32-wasip2/release/kotoba_echo_assert.wasm");
    if wasm_path.exists() {
        return Some(std::fs::read(wasm_path).expect("read wasm"));
    }
    let alt = workspace.join("target/wasm32-wasip2/release/kotoba_guest.wasm");
    if alt.exists() {
        return Some(std::fs::read(alt).expect("read wasm"));
    }
    let entries = std::fs::read_dir(workspace.join("target/wasm32-wasip2/release")).ok()?;
    for e in entries.flatten() {
        let p = e.path();
        if p.extension().map(|x| x == "wasm").unwrap_or(false) {
            let name = p.file_name().unwrap().to_string_lossy();
            if name.contains("kotoba") || name.contains("echo") || name.contains("guest") {
                return Some(std::fs::read(&p).expect("read wasm"));
            }
        }
    }
    None
}
