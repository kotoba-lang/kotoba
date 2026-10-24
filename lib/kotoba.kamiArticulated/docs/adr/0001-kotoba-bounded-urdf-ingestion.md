# ADR 0001: Kotoba bounded URDF ingestion slice

Status: qualified

`src/urdf_query.kotoba` owns the pure XML ingestion slice that can already be
expressed with the sealed Kotoba XML and decimal ABIs. It queries robot name,
ordered link names, typed finite mass values, ordered joint name, kind, parent,
and child attributes, typed finite lower, upper, effort, and velocity limits,
and fixed-width typed inertial-origin, joint-origin, and joint-axis vectors.
ADR 0002 extends this slice with atomic Pose/Inertia/Link/Joint records and a
bounded canonical joint-tree validator. It still does not replace the
downstream physics solver or admit arbitrarily ordered and unbounded graphs.

The query module is authority-free and has no DOM, filesystem, network, entity,
DTD, selector, or callback access. It inherits the compiler's 65,536-byte,
2,048-node, depth-32, 32-attribute, and 32-path-segment limits. Missing string
attributes are typed `[:option :string]`; missing, malformed, or non-finite
numeric attributes are typed `[:option :f64]` none. Malformed or excessive XML
traps.

Qualification compares both committed real fixtures, `cartpole.urdf` and
`hizukue.urdf`, against the existing CLJC `parse-urdf` oracle. The same
`.kotoba` source and input are executed by the Kotoba reference evaluator,
restricted JavaScript, and actual typed Wasm through the pinned compiler's
browser host. Robot/link/joint identity, joint topology, and mass attribute
vectors agree exactly.

This establishes real URDF ingestion without claiming that every general URDF
ordering or the full CLJC physics path has been migrated. The remaining
language/domain boundary is scalable indexed graph assembly; the physics
solver remains a separate Kami engine provider boundary.

Evidence: kotoba-lang/compiler PR #138 merged as
`d950713d7a27094371f1b3085a63df6a5b51c7de`; this repository pins that exact
commit. `kbb -M:test` passes 9 tests and 45 assertions, including both real
fixtures across the CLJC oracle, Kotoba reference evaluator, restricted
JavaScript, and actual typed Wasm browser host.
