# checkpointer

`kotoba-lang/checkpointer` — a JVM (Clojure) sidecar implementing the
LangGraph `MstCheckpointSaver` wire protocol over a Unix socket. A Python
`MstCheckpointSaver` sends msgpack-framed requests here; this sidecar
projects each checkpoint payload to an atproto-shaped MST, builds a
deterministic CAR, returns the root CID synchronously, and enqueues the CAR
for IPFS pin + L2 anchor.

Depends on sibling `kotoba-lang` packages: `kotoba-lang/ipfs` (blob pin, via
an injected `IHttp`), `kotoba-lang/pqh` (AEAD envelope for at-rest
encryption), `kotoba-lang/mst` (MST layer/fanout math), and
`kotoba-lang/multiformats` (CIDs/varints).

## Provenance

Relocated 2026-07-01 from `etzhayyim/root:20-actors/etzhayyim-sdk/src/
{checkpointer,checkpointer-bin}.ts` to `kotoba-lang/checkpointer` per the
org-taxonomy library-placement rule (any library/substrate code belongs in
`kotoba-lang`, ADR-2606302300 / ADR-2607011830). Design authority remains
ADR-2605171800 (revise) Stages 1-2 and ADR-2605172100, both in
`etzhayyim/root`.

Zero etzhayyim-specific coupling beyond two default config values
(`socketPath: "/run/etzhayyim/checkpointer.sock"`, `stateDir: ~/.etzhayyim/
checkpointer`) — both are ordinary overridable defaults, not hardcoded
constants.

The initial relocation was a **physical move only** (TypeScript unchanged,
no dedicated tests existed in `etzhayyim-sdk` to bring along). A Clojure
port then landed and is now the only implementation: the TypeScript
(`src/*.ts` + committed `dist/`) was deleted per ADR-2607012200 (the
`kotoba-lang` org's pure-Clojure admission rule). No in-tree consumer
imported the npm package; the sidecar runs as a JVM daemon.

## Clojure port

`src/kotoba/lang/checkpointer/` is a full port of the sidecar,
namespace-per-concern under `kotoba.lang.checkpointer.*`:
`dagcbor` / `blockmap` / `mst` / `car` / `commit` (the MST+CAR pipeline) /
`msgpack` / `crypto` / `keystore` / `index` / `spool` / `fsutil` / `pin` /
`http-jdk` / `dispatch` (pure op-dispatch core) / `sidecar` (Unix-socket
server) / `cli` (env-var resolution + entrypoint, mirrors
`checkpointer-bin.ts`).

**`.cljc` pure core + `.clj` injected/host I/O (ADR-2607012200 layer
test).** Per this org's admission rule (ADR-2606302300 §Step-1 / the
`ipfs`-exemplar recipe in ADR-2607012200), the wire-protocol records, the
msgpack codec, `indexKey`-style pure helpers, the MST/CAR/dag-cbor pipeline,
and the AEAD wrap/unwrap ORCHESTRATION (`dagcbor` / `blockmap` / `mst` /
`car` / `commit` / `msgpack` / `crypto` / the pure half of `index` /
`dispatch`) are `.cljc`. Several of these (`dagcbor`/`car`/`msgpack`/
`crypto`) are whole-file `#?(:clj (do ...))`-wrapped with throwing `:cljs`
stubs rather than genuinely dual-target — `dagcbor`/`car` because they call
`multiformats.core`'s CID/hash functions, which are THEMSELVES documented
`:clj`-only there (content addressing runs build/server-side, not in the
browser — the exact precedent this wrap pattern is borrowed from);
`crypto` because it wraps `kotoba.lang.pqh.crypto`, itself JVM-only (Bouncy
Castle, no Web Crypto XChaCha20-Poly1305 coverage, per `pqh`'s own README)
and not yet ported to `.cljc` upstream; `msgpack` because a faithful cljs
byte-level port (`js/DataView`/`BigInt` in place of `ByteBuffer`/
`BigInteger`) needs its own cljs-side vector verification, deferred as a
reasonable independent follow-up rather than attempted under this pass. See
each namespace's own docstring for its specific rationale.

Genuine host-specific I/O stays `.clj`: `spool`/`fsutil`/`keystore` (real
`java.nio.file` calls), `pin` (JVM `future`-based fire-and-forget
threading), `http-jdk` (a `java.net.http.HttpClient`-backed reference
`IHttp` adapter), `sidecar` (the real Unix-domain-socket server — JDK
`java.net.UnixDomainSocketAddress`/`ServerSocketChannel`), and `cli` (env-var
resolution + JVM shutdown-hook process bootstrapping). None of these have a
browser/cljs equivalent to be portable toward; see each namespace's
docstring for the specific "why".

**The MST/CAR determinism contract, and how it was verified.**
`checkpointer.ts`'s `#commitMst` carries an explicit, load-bearing
correctness contract: *same (cell_did, checkpoint_id, payload bytes) => same
rootCid, bit for bit* — a silent divergence here is a content-addressing
correctness bug, not a crash, and was treated as the highest-risk part of
this whole port. No pure-Clojure MST-algorithm or CAR-serialization library
existed anywhere in `kotoba-lang` at the time of this port, so three
building blocks were composed:

- **`kotoba.lang.checkpointer.dagcbor`** — a definite-length dag-cbor codec
  WITH CBOR tag-42 CID-link support (`{cid: ...}` -> tag(42) + a byte string
  prefixed with `0x00` + the CID's raw bytes), matching
  `@atproto/lex-cbor`'s exact encoding profile (canonical map-key sort:
  shorter-key-first then bytewise; safe-integers-only; no floats/no other
  tags). `kotoba-lang/dag-cbor` (`cbor.core`) does everything BUT the CID
  link (it's an intentionally link-free, zero-transitive-dep codec) — MST
  nodes and the checkpoint `ref` record both embed CID links (`l`/`v`/`t`/
  `blob`), so this namespace is a small, independently-verified extension
  of the same profile rather than a fork or a private-internals reach-in.
  Whether to upstream tag-42 support into `kotoba-lang/dag-cbor` itself is
  a reasonable follow-up, not done here to avoid touching a shared
  dependency mid-port.
- **`kotoba.lang.checkpointer.mst`** — the Merkle Search Tree itself
  (node/leaf representation, `add` with layer-promotion/subtree-splitting,
  `getUnstoredBlocks` diffing), a full port of `@atproto/repo`'s
  `src/mst/mst.ts` (read directly from this repo's own installed
  `node_modules`, not from memory). The **layer/fanout math**
  (`leadingZerosOnHash`'s 2-bit-group leading-zero count over SHA-256(key),
  and `countPrefixLen`'s key-prefix-compression helper) is NOT
  reimplemented here — it's delegated to the already-existing
  `io.github.kotoba-lang/mst` (`mst.core`, a separate shared repo), reused
  directly rather than writing a second copy of load-bearing hash math.
  One discrepancy was found and NOT silently adopted: `mst.core/key-valid?`
  caps MST keys at 256 chars, but the real `@atproto/repo`
  `isValidMstKey` (`src/mst/util.ts`) caps at 1024 — using the 256 cap
  would reject valid long checkpoint IDs the real system accepts, so this
  port keeps its own 1024-correct `valid-mst-key?` instead (see
  `kotoba.lang.checkpointer.mst`'s namespace docstring); the 256-vs-1024
  gap looks like a bug worth fixing upstream in `kotoba-lang/mst`.
- **`kotoba.lang.checkpointer.car`** — CAR v1 file writer (varint-prefixed
  header + CID-addressed block stream), a port of `@atproto/repo`'s
  `src/car.ts`, built on `kotoba-lang/multiformats` for CIDs/varints/base32
  (which already had the needed `cidv1-dag-cbor` — codec `0x71` — function,
  no extension needed there).

**Verification discipline**: every byte-level claim above was checked
against THIS repo's own installed `@atproto/repo` / `@atproto/lex-cbor` /
`@atproto/lex-data`, called directly via `node -e`/a generator script
(`scripts/gen-mst-vectors.mjs` -> `test/kotoba/lang/checkpointer/
mst_vectors.edn`) — never hand-typed. Cases covered, all byte-for-byte
(root CID *and* full CAR bytes, not just the CID):
  - an **empty tree** (`mst_empty`);
  - a **single-entry tree** via the full `commit-mst` pipeline, both the
    plain-payload path (`commit_single_small`, blobCount=0) and the
    >16 KiB blob-ref-indirection path (`commit_single_large_blobref`,
    blobCount=1, two blocks);
  - a **deliberately multi-layer tree** (`mst_multi_entry_split`, searched
    via the real `leadingZerosOnHash` for a mix of layer-0/1/2 keys so the
    final tree has `root_layer=2` — i.e. genuine `createChild`/
    `createParent`/`splitAround` structure, not just a flat run of leaves).

  No gap was found requiring a documented shortfall — every vector matched
  byte-for-byte on the first algorithmically-correct attempt (see
  `test/kotoba/lang/checkpointer/{dagcbor,mst,commit}_test.clj`).

**msgpack**: no pure-Clojure msgpack library existed in `kotoba-lang`
either. `kotoba.lang.checkpointer.msgpack` is hand-rolled (covers nil/bool/
int-all-widths-incl-full-uint64-via-BigInteger/float32(decode-only)/
float64/str/bin/array/map; no extension types, which this protocol never
uses) rather than pulling in a JVM library (e.g. `org.msgpack:msgpack-core`)
— msgpack's format is materially simpler than CBOR's (no canonical-sort, no
link concept), and this sidecar's own deployment model (long-lived JVM
daemon, not a `bb` script) removes the one reason a Java dependency might
have been preferred. Unlike the MST/CAR layer, msgpack here is a WIRE
PROTOCOL with no content-addressing determinism contract — the correctness
bar is round-trip fidelity + interop with a real msgpack implementation
(Python's `msgpack`, `@msgpack/msgpack`), not byte-identical output, though
byte-identity is what's actually achieved for the representative value
shapes checked (`test/kotoba/lang/checkpointer/msgpack_vectors.edn`'s
`:msgpack_vectors`, generated the same way via `@msgpack/msgpack`).

**Unix-domain-socket server**: JDK 16+'s native support
(`java.net.UnixDomainSocketAddress` + `ServerSocketChannel.open(
StandardProtocolFamily/UNIX)`) — zero extra dependency, verified with a
standalone spike before building `kotoba.lang.checkpointer.sidecar` around
it. This is deliberately NOT behind an injectable protocol the way the IPFS
HTTP transport is (`kotoba.lang.ipfs/IHttp`, reused here with a new JDK
`HttpClient`-backed reference adapter, `kotoba.lang.checkpointer.http-jdk`,
including a minimal multipart/form-data encoder for Kubo's `/api/v0/add`) —
running a Unix-socket server IS this process's job, not an abstractable I/O
seam. What IS kept independently testable is everything around the socket:
`kotoba.lang.checkpointer.dispatch/handle-request` is a plain
Request-map-in/Response-map-out function, directly callable in tests with
an injected `env` (fake/temp-dir-backed collaborators, see
`dispatch_test.clj`) with no socket involved at all, plus a true end-to-end
test (`sidecar_test.clj`) that starts a real Unix-socket server, connects a
real client, sends a framed msgpack `put` request, and confirms the
response's `mst_root_cid` matches `commit-mst` computed directly for the
same input.

## Development

```bash
kbb -M:lint      # clj-kondo (errors fail)
kbb -M:test      # cognitect test-runner
kbb -M:run       # run the sidecar (kotoba.lang.checkpointer.cli)
```

MST/CAR/msgpack cross-language vectors live under
`test/kotoba/lang/checkpointer/*_vectors.edn`, generated via
`scripts/gen-mst-vectors.mjs` against the real `@atproto/repo` /
`@msgpack/msgpack` (install those ad hoc — the committed vectors are the
source of truth; the script is provenance).

## License

Apache 2.0 + Charter Compliance Rider v3.6 (`/CHARTER-RIDER.md`).
