# kotoba-mesh-app — KOTOBA Mesh sample app

A minimal [KOTOBA Mesh](../../docs/ADR-kotoba-mesh-wasm-hosting.md) application.
Everything is one language family:

- **manifest** = EDN (`kotoba.app.edn`)
- **components** = Clojure (`*.clj`, compiled by `kotoba-clj` — the **default**
  mesh language, ADR §14)
- **data / queries** = Datomic / Datalog (`kqe-assert!` / `kqe-query`)

## Files

| file | role |
|---|---|
| `kotoba.app.edn` | app manifest: 2 components, triggers, a CACAO link, placement |
| `reply.clj` | HTTP-triggered Clojure component (default language) |

## Try the control loop (no cluster needed)

The placement brain (manifest → reconcile → auction → award) runs as a pure demo:

```bash
cargo run -p kotoba-lattice --example mesh_reconcile
```

Expected: both components parse as `lang=Clojure`, reconcile asks for `+2 ingest`
and `+1 reply`, the `reply` auction only draws bids from nodes that advertise
`cap/llm`, and the fleet converges.

## Deploy onto a real lattice

See [`deploy/kotoba-mesh.md`](../../deploy/kotoba-mesh.md). In short:

```bash
kotoba component build reply.clj      # → kotoba-clj compiles to a wasm component CID
kotoba app deploy     kotoba.app.edn  # commit desired state to the control graph
kotoba lattice ps                     # watch nodes pick up the work via auction
```
