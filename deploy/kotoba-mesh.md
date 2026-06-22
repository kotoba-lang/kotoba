# KOTOBA Mesh — deployment

How to roll out the WASM hosting fabric described in
[`docs/ADR-kotoba-mesh-wasm-hosting.md`](../docs/ADR-kotoba-mesh-wasm-hosting.md).

There is **no central control plane to deploy** (no NATS, no k8s control plane).
A node *is* `kotoba serve`; the lattice self-forms over libp2p gossipsub. This is
the no-central-master invariant (CLAUDE.md) carried into hosting.

## Status (M1 → M4)

M4 (wadm) adds, on top of M1–M3:

- `kotoba-lattice::control` — desired state as **control-graph datoms**
  (`app_to_quads` / `desired_from_quads`); the durable wadm SSOT.
- `LatticeMessage::PutApp` — live propagation of desired state to every node's
  reconciler (`LatticeController::set_desired`).
- `kotoba-server::net_actor` — the reconcile loop runs on the node: emits
  auctions for shortfalls, closes them (awards), and **places winners by
  executing the component on the WASM host** (`StartComponent` → fetch artifact
  by CID → `WasmExecutor::execute` → advertise as `hosted`). Missing artifacts
  are skipped (bitswap pulls them; a later round retries).
- `kotoba app deploy` prints the content-addressed control datoms to ingest.

Verify the full wadm loop (no cluster):

```bash
cargo run -p kotoba-lattice --example mesh_wadm   # manifest→datoms→desired→auction→place→converge
```

Remaining (M5+): auto-ingest deploy datoms / PutApp into a running node,
`kotoba component push` (artifact → block store), CACAO link gating, and
kotoba-clj multi-export (`on-http`/`on-kse`) codegen.

## Status (M1 + M2 + M3)

M3 adds, on top of the core below:

- **server participation** (`kotoba-server::net_actor`, `--features p2p`): joins
  the lattice — `subscribe_lattice`, periodic Heartbeat publish, and auto-bid on
  auctions over gossipsub. Node DID from the libp2p peer id; labels from
  `KOTOBA_NODE_LABELS`; advertised caps = the kotoba:kais host-imports.
- **CLI** (`kotoba` binary):
  - `kotoba component build <file.clj>` — Clojure (default) → WASM component →
    canonical CID (CIDv1 dag-cbor sha2-256). Verified: `reply.clj` → 1511-byte
    component → `bafyrei…`.
  - `kotoba app deploy <manifest.edn>` — compile every component, print the
    fully content-addressed desired state.
  - `kotoba lattice ps` — local lattice participation config.

Remaining (M4): `StartComponent → WasmExecutor` execution + pushing desired
state into the control graph for cross-node reconciliation.

### Core (M1 + M2)

Implemented now:

- `kotoba-lattice` (pure control-plane core):
  - `protocol` — gossipsub message types + reserved topics + deterministic auction ids
  - `manifest` — EDN app manifest parser (Clojure-default components, ADR §14)
  - `reconcile` — leader-less reconcile + auction scoring + deterministic award
  - `node` — stateful `LatticeController`: fleet tracking (heartbeat TTL) + the
    continuous tick→auction→bid→award→place loop + **self-healing** on node loss,
    behind a transport-agnostic `Transport` trait
- `kotoba-net::lattice` (M2 gossipsub binding):
  - `subscribe_lattice` (5 control topics) + `decode_lattice` + `impl Transport
    for KotobaSwarm` — the swarm IS a lattice transport (no NATS, no central broker)

Verify without a cluster:

```bash
cargo run -p kotoba-lattice --example mesh_reconcile   # one-shot placement
cargo run -p kotoba-lattice --example mesh_node        # control loop + self-heal
cargo test -p kotoba-lattice                            # 22 tests
cargo test -p kotoba-net --lib lattice                  # gossipsub binding
```

Remaining (ADR §12 M3–M4): run the loop inside the `kotoba-server` swarm event
loop, compile `.clj` → component CID on deploy (`kotoba-clj`), and the
`kotoba app` / `kotoba lattice` CLI subcommands.

## Node roles

Each node opts into roles via `KOTOBA_NODE_ROLES` (default `pin,compute`):

| role | meaning |
|---|---|
| `pin` | serve content-addressed blocks (artifacts + datoms) |
| `compute` | host & execute WASM components — **auction-eligible** |
| `relay` | firehose / NAT relay peer |

## Bring up a lattice

```bash
# Node A (seed)
KOTOBA_NODE_ROLES=pin,compute kotoba serve --listen /ip4/0.0.0.0/udp/4001/quic-v1

# Node B/C (join via Kademlia bootstrap to A's multiaddr)
KOTOBA_PEERS="/dns4/nodeA/udp/4001/quic-v1/p2p/<peerid>" \
KOTOBA_NODE_ROLES=pin,compute kotoba serve
```

Nodes advertise `Heartbeat{caps, labels, free_gas, hosted}` on
`kotoba/lat/heartbeat`. Placement labels come from node config
(e.g. `KOTOBA_NODE_LABELS=zone=jp,tier=edge`).

## Deploy an app

```bash
cd examples/kotoba-mesh-app

# 1. compile the default-language (Clojure) components → content-addressed CIDs
kotoba component build reply.clj          # kotoba-clj → wasm component → CID

# 2. commit desired state (the EDN manifest) to the control graph
kotoba app deploy kotoba.app.edn

# 3. any reconciler diffs desired vs observed, runs auctions, places components
kotoba lattice ps
kotoba app status kotodama-bot
```

Self-healing: if a hosting node's heartbeat disappears, observed count drops and
the next reconcile re-auctions the lost instances automatically — no operator
action, no central scheduler.

## Kubernetes (optional)

The mesh does **not** require Kubernetes. If you want managed pods, run the same
`kotoba serve` binary in the existing manifests (`deploy/deployment.yaml`,
`deploy/configmap.yaml`) with `KOTOBA_NODE_ROLES` set — pods join the same
libp2p lattice as bare-metal nodes. k8s here is just a process supervisor, not
the control plane.
