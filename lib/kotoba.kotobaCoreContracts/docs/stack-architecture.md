# kotoba-core-contracts: stack integration

Status: accepted architecture direction, 2026-10-10. This document and
[composition metadata](../spec/stack-integration.edn) describe ownership and
future boundaries; they do not change runtime schemas or certify migration.

## Responsibility

Owns existing source/package/capability boundaries. Target-neutral execution descriptors are implemented in `kotoba.core.execution`; Component/WIT profiles and the unchanged mixed v1 compatibility codec remain in `kotoba.abi.component`. This repository does not absorb language, VM or protocol semantics. Existing codec/crypto/I/O dependencies must be measured per entrypoint before claiming a contract-only closure.

## Contract dependency direction

Arrows are consumer → contract dependency. These are intended entrypoint
boundaries, not whole-repository imports already achieved.

```mermaid
flowchart LR
  Owner["kotoba-core-contracts: Source, package and capability contracts"]
  Owner --> D0["focused codec and identity contracts"]
```

The measured selected-owner production dependencies at base `e2b3a74f959142da054605b5c1c053a19edac494`
are none among the selected 13 owners.
This selection excludes other libraries; alias-only build/test imports remain
separate in the [full observation](https://github.com/kotoba-lang/kotoba-lang/blob/main/lang/stack-dependency-observation.edn).

## Shared architecture and refactor rules

- [Whole stack and distributed flow](https://github.com/kotoba-lang/kotoba-lang/blob/main/docs/stack-architecture-target-neutral.ja.md)
- [Machine-readable architecture direction](https://github.com/kotoba-lang/kotoba-lang/blob/main/lang/stack-architecture-target-neutral.edn)
- [Current measured dependency graph](https://github.com/kotoba-lang/kotoba-lang/blob/main/docs/stack-dependencies-current.md)
- [Coordinated refactor procedure](https://github.com/kotoba-lang/kotoba-lang/blob/main/docs/stack-refactor-procedure.md)
- [Japanese presentation](https://github.com/kotoba-lang/kotoba-lang/blob/main/docs/presentations/kotoba-lisp-machine.ja.md)

Target, host, distribution and consistency are independent selection axes; their
Cartesian product is not a support matrix. Unknown/unqualified profiles fail
closed. Preserve existing wire keys, CID rules and reader compatibility until
a versioned migration. Migrate whole components and public closures; Q9 is
JVM-free. Qualify actual artifacts, denied paths, limits and receipts per
target × host × operation × consistency.

Keep source dependencies, artifact flow, runtime composition and service
relationships separate. No readiness follows for debugger/live editing, heap
image restoration, selfhost, C-free production or physical hardware.

The implemented API boundary is specified in [execution-contract.edn](../spec/execution-contract.edn). Neutral source closure is measured separately from repository dependency closure. Existing package/codec helpers remain separate entrypoints.
