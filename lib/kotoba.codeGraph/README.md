# code-graph

**C2/C3 storage projection for content-addressed Kotoba code.**

Admission, verification, disclosure, merge, retention and execution logic for
the code graph: definitions, types, artifacts, analysis cache, namespace
commits, execution receipts and identities, query receipts, identity
migrations and retention pins — plus the derived datom and retention streams.

Pure `.cljc`, no third-party dependencies. Cryptographic block verification is
**host-injected** as `(verify cid block)`, so this library never picks a hash
implementation and verification stays mandatory on admission.

## Namespaces

| ns | role |
|---|---|
| `code-graph.core` | the complete synchronous API |
| `code-graph.async` | promise/completion-aware facade over the same API |
| `code-graph.evidence` | the `kotobase.evidence` planes for the records here |

`code-graph.async/run!` materializes the graph through a store whose methods may
return host async values, runs any existing `code-graph.core` operation against a
local oracle, then flushes only its document and append deltas. So there is no
async duplicate of every function, and admission/verification/disclosure/merge/
retention/execution keep **one** implementation.

Use `promise-runtime` in ClojureScript. Synchronous hosts and tests can use
`immediate-runtime`; other hosts may inject the same resolve/then/all algebra.

## Provenance

Extracted from [`kotoba-lang/kotobase`](https://github.com/kotoba-lang/kotobase)
on 2026-07-26 per **ADR-2607201600 decision 6** (kotobase Merkle-LSM / IStore
retirement).

`kotoba-lang/kotobase` is being dissolved: it is not the datom engine but the
IStore client seam (its own README says so), and the datom client the retirement
calls for already exists as `kotoba-lang/kotobase-client`. The code graph was
**47% of that repo (808 LOC) and is unrelated to the IStore core being retired**,
so it is moved out ahead of dissolution rather than retired with it.

Namespaces were renamed on extraction (`kotobase.code-graph` → `code-graph.core`,
`kotobase.code-graph-async` → `code-graph.async`). Nothing referenced the old
names in code — the only fleet-wide references were docstrings.

### Known coupling

This library is still an **IStore consumer**: `kotobase.store` for the injected
seam, `kotobase.local` for the pure oracle. Extraction makes that dependency
explicit and visible to the IStore freeze gate instead of hiding it inside the
repo being retired — it does not remove it. Migrating this repo onto the datom
plane is tracked under ADR-2607201600 M6.

## Test

```bash
kbb -M -m kotoba.security.adoption   # shared security adoption
kbb -M:test                          # JVM
kbb -M:lint
```

ClojureScript promise path:

```bash
kbb -M:cljs-test -m cljs.main \
  -co '{:target :nodejs :output-to "target/async-node.js" :optimizations :none}' \
  -c code-graph.async-node
node target/async-node.js
```

## Evidence

A **query receipt** embeds the version 1 `kotobase.execution-contract` record
the read produced, whole. It used to carry none, which left this plane five
fields short of being evidence of a query execution —
`kotobase.evidence` measures that distance — and the fix was never a better
adapter: a caller that cannot supply a receipt has not run a governed
execution, and a record about a read nobody can re-derive is a claim rather
than evidence. The embedded receipt is cross-checked against the facts the
record already carries: its result root must be the receipt's `:result-cid`
and its plan digest the identity's `:plan-cid`, or the two halves describe
different executions.

`code-graph.evidence` defines the two planes for the records written here and
hands them to `kotobase.evidence`, which lifts them under one rule: the
supplement must be exactly the fields the source does not carry. Those
carriers live here rather than in kotobase because this library depends on
kotobase — a carrier there could only be a dependency cycle or a copy of these
shapes, and a copy of a shape is what that namespace exists to stop being
necessary.

`query-plane`'s supplement is now empty.

## Execution contract entrypoints

Neutral descriptors are imported from `kotoba.core.execution` (core-contracts).
Component/WIT profiles and unchanged mixed v1 identity/lease codecs are imported
from `kotoba.abi.component` (abi). The old `kotoba.abi.contract` facade remains
readable for existing callers; new production imports select their owner.
The [integration contract](spec/execution-profile-integration.edn) records this
cutover. Existing v1 blocks/WIT/CIDs remain unchanged; v2 neutral identities
require a verified target binding and fresh CID/signature. This change does not
enable v2 runtime admission or claim Q9/native qualification.
