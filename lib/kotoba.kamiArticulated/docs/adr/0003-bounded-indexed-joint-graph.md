# ADR 0003: Bounded indexed joint graph

Status: implemented and qualified

`joint-graph-valid` now delegates to an order-independent indexed validator.
The admitted profile contains 1 through 128 uniquely named links and exactly
`links - 1` joints. Link and joint declaration order has no semantic effect.
The bound is enforced by compiler typed ABI v10's purpose-specific compact
values and the worst admitted validation path remains inside the
non-replenishable 512-call fuel budget. General maps and ADTs retain their
smaller limits.

The validator builds persistent `:string-index` values for link, joint, and
child identities and a persistent `:disjoint-set-i64` forest. Duplicate or
missing link names fail closed. Each joint then resolves
its parent and child through that sealed index, rejects missing identities,
duplicate joint names, and a child already owned by an earlier joint, and
unions the two indices through the bounded runtime operation. Finding both
endpoints in the same union-find component rejects self-edges and cycles.

With `n - 1` admitted edges, no cycle, and every endpoint resolved to one of
the `n` links, the undirected graph is connected. Unique child ownership gives
every non-root link at most one directed parent. Thus multiple parents,
cycles, disconnected components, unknown references, and duplicate identities
are rejected without depending on source order or performing an unbounded
ancestor traversal.

Qualification retains the real cartpole and hizukue CLJC-oracle matrix and the
existing unsafe graph matrix. It additionally admits a deliberately scrambled
four-link tree and a maximum-size 128-link chain whose link and joint lists
are both reversed. The same `.kotoba` module passes through the reference
evaluator, restricted JavaScript, and actual browser-hosted typed Wasm without
increasing any general compiler/runtime limit. A 129-link chain is explicitly
rejected in all three execution paths.

Evidence is the repository `kbb -M:test` gate covering the reference
evaluator, restricted JavaScript, and actual browser-hosted typed Wasm.
