# kotobase-storage-kura

`kotobase.storage` over the [kura](https://github.com/kotoba-lang/kura) shard
plane, so every consumer already speaking that contract — including DataLad
datasets reaching it through `kotoba-annex` — gets kura without learning a new
API. Design: [ADR-2607299200](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2607299200-kura-erasure-coded-storage-network.edn).

The ADR described this repo as "a thin layer holding none of the decisions".
Writing it surfaced two facts that description did not account for. Both are
load-bearing, and both are corrections to the ADR rather than to the code.

## 1. kura cannot provide refs, and does not pretend to

`kotobase.storage` is two protocols: immutable CID blocks, and a mutable ref
with compare-and-set. kura is a shard plane — objects, placement groups,
erasure coding — with no linearizable CAS primitive anywhere in it. A backend
that declared `:single-writer-ref` and shrugged would be doing exactly what
`kotobase.storage/ref-profiles` warns about: *an ignored precondition returns
success.*

So `open` **requires** a `:ref-store` delegate — another `kotobase.storage`
backend that really has a CAS — and this adapter reports **that delegate's**
ref profile rather than inventing one. Without a delegate it refuses to
construct.

Blocks come from kura. Refs come from something that can do refs. Nothing
claims to do both.

## 2. kura's 1.625× does not apply at kotobase block sizes

kotobase cuts blocks at 16–128 KB. Erasure-coding a 128 KB block at k=16 gives
8 KB shards, twenty-six of them, and a read that touches sixteen nodes — for
128 KB. A replica costs one request.

| block size | strategy | multiplier | reads |
|---|---|---|---|
| 64 KiB | replication ×3 | 3.0 | 1 |
| 64 MiB | erasure k=16/n=26 | 1.625 | 16 |

So there is an `:erasure-threshold-bytes` (default 1 MiB, where sixteen shard
reads start to amortise): at or above it, erasure-code; below it, replicate.

**Quoting 1.625× to a consumer whose blocks are all 64 KB would be a lie about
what they are buying** — it is 3× for that workload. `effective-multiplier`
reports what a real distribution actually costs, because the honest number for
a mixed workload is a mixture and not either constant:

```clojure
(sut/effective-multiplier pol sizes)
;; {:blocks 100 :multiplier 2.06 :erasure-coded 10 :replicated 90 ...}
```

## Async CARv2 path

`kotobase.storage.kura.async/open` is the Worker/Node path for an asynchronous
Kura fleet. It packs verified blocks into bounded CARv2 objects, puts each
archive through `kura.node.object/put-object!>`, then publishes a durable
CID-to-frame manifest through a linearizable CAS catalog. One
content-addressed manifest block is shared by every CID in the pack, while
each CID gets its own CAS pointer; batch reads fetch each shared manifest only
once. The shard placement and LRC geometry are recorded so a process restart
can address the original nodes after the fleet grows.
Pack objects can be shared by concurrent identical writes, so this adapter
never deletes a pack as rollback or after losing a catalog CAS. Catalog-aware
garbage collection must verify that no CID refs point to an object before
removing it.

Reads request only the CAR frame's data-shard ranges when every Kura node
advertises true range reads. If one range is missing or unreachable, the
adapter fetches only that stripe's local data and parity ranges and XORs the
requested slice. It falls back to full Kura object reconstruction only if
local recovery also fails; that path verifies the archive digest before the
requested block is returned. Both paths verify the block with the injected
`:verify-block` function. The verifier is required because CAR framing supports
CIDv1 codecs such as dag-pb, while the CAR helper's built-in hashing currently
covers raw and dag-cbor blocks.
`repair-block!>` verifies and repairs the containing Kura pack and returns a
local receipt candidate with bytes rewritten and recorded placement. A
coordinator must add the signed order, provider identity and repair deadline
before using that evidence in YATA reward scoring.

The namespace defaults to 4 MiB CAR packs and a 4 MiB Kura stripe ceiling.
Small packs choose a smaller one-stripe geometry, so their erasure overhead
stays near the configured LRC multiplier instead of padding every object to a
large fixed stripe. This reduces block-level requests and catalog lookups per
archive; it does not establish lower end-to-end latency or TCO.

The adapter receives `:plan-placement` from the coordinator. The callback must
use Kura's deterministic placement policy, including region/failure-domain
caps and the committed regional-demand generation. The current async
`kura-node` pin depends on an older Kura commit that does not contain
`kura.placement`; keeping the coordinator placement module injected avoids
silently compiling against a different copy/version of those decisions. The
callback is mandatory, but a signed order and placement-generation migration
path are still not wired into this draft.

The Node tests exercise async range recovery with in-memory shard stores and
catalog-index recovery after closing and reopening a test-only file-backed
catalog. The restart case keeps the fake shard stores alive in process memory,
so it qualifies catalog serialization and lookup across a backend reopen; it
does not qualify durable Kura shard storage, multi-writer CAS, or a deployed
catalog implementation.
This adapter remains an implementation draft until its production async store,
CID codec, and range-read paths are exercised. It does not enable customer-data
mode: `kura-node` still requires signed-order admission and coordinator-key
wiring before the service can accept those writes.

## Durability is the fleet's, not the code's

`durability-report` delegates to `kura.node.store/audit`. The question a
kotobase consumer asks is how durable their data is, and the answer is how many
genuinely independent failure domains the fleet has — not what the erasure
code's parameters say. A fleet of pseudo-nodes on one account reports one
domain here, which is the point.

## Tests

```bash
python3 scripts/test-hosts.py /absolute/github/workspaces/kura-tests
```

This command runs the JVM suite and the emitted Node bundle from the pinned
ClojureScript compiler. It checks that every test namespace is actually run,
including the async suite, and records the source-view byte hashes. The
compiled suite uses the shared `kotoba.test.cljs` bridge from the immutable
Kotoba monorepo package; the existing JVM/SCI API is unchanged. These are
compatibility-host checks. Amu native/Wasm, production Kura shard durability,
multi-writer catalog qualification and signed-order admission remain separate.
No live fleet, endpoint, token or deployment is changed by these tests.

The suite runs `kotobase.storage.contract/verify` — the upstream conformance
suite — so passing is a statement about the contract, not about this repo's
own opinion of it.

## License

Apache-2.0. See `LICENSE`.
