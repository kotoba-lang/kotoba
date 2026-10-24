# ADR 0002: Bounded structured URDF records and canonical joint graph

Status: implemented and qualified

ADR 0003 supersedes only this ADR's canonical-order and 12-link graph bound;
the nominal record and inertia safety contracts below remain current.

`src/urdf_query.kotoba` now assembles four nominal, immutable value shapes:
`:kami/pose`, `:kami/inertia-tensor`, `:kami/link-reference`, and
`:kami/joint-reference`. Pose owns two fixed-width f64 triples. Inertia owns
all six finite f64 tensor components atomically. Before sealing, the tensor is
bounded to component magnitude `1e12` and must satisfy nonnegative diagonal,
all three nonnegative second-order principal minors, and a nonnegative 3x3
determinant under sealed f64 semantics. Link and joint reference records own
the strings required to establish graph identity. A missing, malformed,
non-finite, incomplete, over-limit, or non-positive-semidefinite tensor returns
typed none; no partial record is observable.

`joint-graph-valid` admits a deliberately bounded canonical tree profile. It
accepts 1 through 12 uniquely named links and exactly `links - 1` uniquely
named joints. Links are in topological order: joint `i` must connect a parent
already present in link prefix `0..i` to link `i + 1`. Consequently every
non-root link has exactly one parent and cycles, self-edges, unknown
references, duplicate IDs, duplicate children, and disconnected components
fail closed. The ordering requirement is part of this profile rather than an
implicit dependence on source order.

The 12-link limit keeps validation within the language's sealed 512-call fuel
budget even on the restricted JavaScript backend. Arbitrarily ordered or
larger URDF graphs require a bounded indexed graph collection and a linear
validator; they remain an explicit scale extension and are not silently
accepted by this profile.

Qualification compares `cartpole.urdf` and `hizukue.urdf` with the retained
CLJC oracle across the Kotoba reference evaluator, restricted JavaScript, and
actual browser-hosted typed Wasm. A negative matrix rejects duplicate link
names, unknown parents, self-edges, duplicate children, cycles, missing child
attributes, over-limit graphs, negative diagonal inertia, indefinite inertia,
and over-limit inertia. Compiler ADRs 0021 and 0022 seal nested descriptor
trust and the `string=? -> :i64` contract required by these values.

Evidence: kotoba-lang/compiler PR #141 merged as
`0dc6fc7df3b8d79b7eb39649f50fb2d87e03de82`; `kbb -M:test` passes 11 tests / 60
assertions with zero failures or errors.
