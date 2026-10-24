# kotobase-storage-ipfs

Provider-neutral IPFS immutable-block transport for Kotobase.

This library has no dependency on a particular node daemon, HTTP RPC API, or
mutable-name service. It accepts two injected, Promise-returning operations:

```clojure
(ipfs/open
 {:client
  {:put-block! (fn [expected-cid bytes] ... stored-cid-promise)
   :get-block  (fn [cid] ... bytes-or-nil-promise)}})
```

The client may use an embedded implementation, a browser implementation, a
remote pinning service, or another IPFS-compatible transport. Returned bytes
remain untrusted; compose this adapter with
`kotobase.storage.verify/async-verifying-block-store` at the application
boundary.

## Blocks and refs are different planes

The adapter intentionally implements `IBlockStore` only. A mutable database
head requires agreement and rollback protection; those guarantees cannot be
inferred from content-addressed block transport or mutable naming.

Compose blocks with a separately selected ref provider:

```clojure
(storage/compose
 {:blocks (ipfs/open {:client block-client})
  :refs linearizable-ref-store})
```

The signed commit DAG remains canonical truth. Discovery mechanisms may point
at a candidate frontier, but they are not used by this adapter and are not a
correctness dependency.

## A concrete client: kotobase.net's own archive, over UnixFS + CARv2

`kotobase.storage.ipfs-kotobase` is a `{:put-block! :get-block}` client
backed by kotobase.net's first-party `PUT/GET /ipfs/:cid` archive
(`kotobase.archive-put` in `net-kotobase/control-plane/kotobase-api-gateway-cljs`).
That endpoint enforces a **4 MiB per-object ceiling** (it buffers the body
in Worker memory to hash it — a Worker property, not a B2 one). Rather than
widening that endpoint, `bin/large_put.cljk` shows the other fix: never ask
it to accept an object anywhere near that size.

```
                              unixfs.file/build
  <file, any size>  ───────────────────────────▶  {:cid root :blocks [...]}
                                                    (256 KiB raw leaves,
                                                     small dag-pb parents —
                                                     every block ≪ 4 MiB)
                                    │
                                    ▼
              kotobase.storage.ipfs-kotobase/open  ──▶  PUT /ipfs/:cid  (per block)
                                    │                    ipld.car.v2/pack, PUT too
                                    │                    WHEN the pack itself is
                                    │                    still ≤4 MiB (a read-side
                                    │                    optimisation only — never
                                    │                    silently skipped, always
                                    │                    logged when it doesn't fit)
                                    ▼
                          unixfs.file/read-file      ◀── GET /ipfs/:cid (per block)
                       (re-hashes every block; a          fetched fresh over the
                        byte-identical reassembly         network, not read back
                        is the only thing "verified"      from local memory
                        means)
```

The archive endpoint itself is unmodified and still fail-closed: it still
refuses anything over 4 MiB, still re-hashes every body it accepts. What
changed is what gets asked of it.

### The identity/location split (root ADR-2608148200)

`PUT /ipfs/:cid` accepts **only raw CIDv1(sha2-256)**. A UnixFS leaf's CID
already is one, but a dag-pb parent node's is not. `ipfs-kotobase` computes
the RAW CID of each block's own bytes as the archive **Location**, PUTs
there, and — only when identity and location differ — remembers the
mapping so `get-block` can still be asked for the identity CID. `put-block!`
always resolves to the identity CID it was given: the split is invisible
above this namespace, and the `kotobase.storage.ipfs` adapter's own
`stored-cid == cid` check is what proves that (`test/ipfs_kotobase_test.cljk`).

```clojure
(require '[kotobase.storage.ipfs :as ipfs]
         '[kotobase.storage.ipfs-kotobase :as ipfs-kotobase])

(def client (ipfs-kotobase/open {:base-url "https://kotobase.net" :token token}))
(def adapter (ipfs/open {:client client}))
;; adapter is a normal kotobase.storage.core/IBlockStore from here.
```

**Never pass the token on argv** (`ps` exposes it to every process on the
machine) — `bin/large_put.cljk` reads it from a file path named by
`KOTOBASE_ARCHIVE_TOKEN_FILE`.

### Try it: `bin/large_put.cljk`

```sh
# multiformats.core needs @noble/hashes -- kbb -Spath resolves SOURCE,
# not node_modules, so `npm install` once wherever io-multiformats lands:
IO_MF="$(kbb -Spath -M:cljs-test | tr : $'\n' | grep io-multiformats)"
(cd "${IO_MF%/src}" && npm install)

KOTOBASE_ARCHIVE_TOKEN_FILE=/path/to/token \
NODE_PATH="${IO_MF%/src}/node_modules" \
  kbb --backend sci --classpath "$(kbb -Spath -M:cljs-test)" bin/large_put.cljk /path/to/large/file
```

It chunks the file, uploads every block (and the CARv2 pack, when it still
fits under the ceiling), fetches everything back over the network, and
refuses to call it a success unless the reassembled bytes are identical to
the original file.

### `bin/mock_archive_server.cljk` — the same round trip without live credentials

A local, loopback HTTP double of the archive's raw-CID contract (4 MiB
ceiling, digest check, no auth). It needs the same `NODE_PATH` as above
(it also uses `multiformats.core`):

```sh
IO_MF="$(kbb -Spath -M:cljs-test | tr : $'\n' | grep io-multiformats)"
NODE_PATH="${IO_MF%/src}/node_modules" \
  kbb --backend sci --classpath "$(kbb -Spath -M:cljs-test)" bin/mock_archive_server.cljk &
```

Then point `bin/large_put.cljk` at it with `KOTOBASE_BASE_URL=http://localhost:8998`
(any token file still satisfies `-main`'s check; the double does not verify
it) to exercise the entire pipeline — chunking, upload, CARv2 pack, network
fetch, UnixFS reassembly, byte comparison — without a working
`KOTOBASE_ARCHIVE_TOKEN`. See
`.claude/skills/secrets-location-map/references/kotobase.md` in the
superproject for why that credential is not reliably available today.

## A second concrete client: any real Kubo node, over `kotobase.storage.ipfs-kubo`

`ipfs-kotobase` (above) talks back to kotobase.net's own archive — a cache
round trip, not a distinct storage substrate. `kotobase.storage.ipfs-kubo`
is the client that actually reaches an independently operated Kubo
(go-ipfs) node's HTTP RPC + gateway (self-hosted, or a Kubo-RPC-compatible
pinning provider), over `kotoba-lang/io-ipfs`'s pure Kubo protocol model:

```clojure
(require '[kotobase.storage.ipfs :as ipfs]
         '[kotobase.storage.ipfs-kubo :as ipfs-kubo])

(def client (ipfs-kubo/open {:api-url "https://ipfs-rpc.example"
                              :gateway-url "https://ipfs-gateway.example"
                              :token token}))
(def adapter (ipfs/open {:client client}))
;; adapter is a normal kotobase.storage.core/IBlockStore from here --
;; compose it with a ref store per the "Blocks and refs are different
;; planes" section above.
```

Kubo's own computed CID for a block usually matches the caller-assigned
identity CID (single raw leaves, `cid-version=1` defaults `raw-leaves` to
true), but is not guaranteed to byte-for-byte across Kubo versions/configs
-- this client keeps the same small identity->location map as
`ipfs-kotobase` for the rare block where it doesn't, and `put-block!`
always resolves to the identity CID regardless.

This is the client `kotoba-lang/kotobase-storage-d1`'s `KOTOBASE_AUTHORITY=ipfs`
option wires in as an additional, non-default block provider (superproject
ADR-2608281000 Decision 2: "ベースは分散型、中央集権は効率化のための cache").

## A third concrete client: no daemon at all, over `kotobase.storage.ipfs-native`

`ipfs-kubo` (above) removes the kotobase.net roundtrip but still requires
every deployer to run and lifecycle-manage a separate Go binary (Kubo) --
a per-platform download, its own process supervision, alongside the JS/nbb
process that actually wants to store a block. `kotobase.storage.ipfs-native`
is the kubo-independent alternative the owner asked for after `ipfs-kubo`
landed: a peer-to-peer block store that runs IN this process, over plain
TCP sockets to OTHER instances of this same client. Zero external
processes, zero npm/vendor SDK dependency (an `npm install helia`
in-process alternative was evaluated first -- see "Why not Helia" below).

```clojure
(require '[kotobase.storage.ipfs :as ipfs]
         '[kotobase.storage.ipfs-native :as native])

;; Node A holds a block. Node B has never seen it and is configured with A
;; as a peer.
(def a (native/open {:node-id "a" :port 15900}))
(def b (native/open {:node-id "b" :port 15901
                      :peers [{:id "a" :host "127.0.0.1" :port 15900}]}))

((:put-block! a) cid bytes)
((:get-block b) cid) ;; => Promise<bytes>, fetched over a real TCP round
                      ;;    trip to A the first time; served from B's own
                      ;;    local cache on every call after that

(def adapter (ipfs/open {:client b}))
;; adapter is a normal kotobase.storage.core/IBlockStore from here.
```

It reuses two pieces this workspace already had, unmodified:
[`kotoba-lang/wire`](https://github.com/kotoba-lang/wire) for the real TCP
socket I/O + EDN framing (the same library `kotoba-lang/io-libp2p`'s own
`kotoba.net.transport.tcp` and `kotoba-lang/dtn` already run real sockets
on), and `kotoba.net.bitswap/respond-to-want`
(`kotoba-lang/io-libp2p`) for the want/have intersection. Neither of those
two, on their own, moves block BYTES over any wire -- confirmed by reading
their source, not assumed (`kotoba.net.bitswap`'s own docstring: "No block
transfer over any wire"; `kotoba.net.transport.tcp` only ever exchanges
want-lists/have-lists too). The `:block-get`/`:block-data` request/response
pair this client adds on top is what actually moves bytes (base64-encoded,
since `kotoba-lang/wire`'s frame is `pr-str`'d EDN text).

**Precisely what this is not**: not the real IPFS/libp2p bitswap wire
protocol (`/ipfs/bitswap/1.2.0`) -- it cannot exchange blocks with Kubo,
js-ipfs/Helia, or any other IPFS implementation, only with other instances
of this same client. No transport encryption/authentication (every
configured peer is trusted as given, matching `kotoba.net.transport.tcp`'s
own documented scope). No peer discovery/DHT (`:peers` is configured up
front). No CID verification of fetched bytes -- like `ipfs-kubo` and
`ipfs-kotobase`, that is the caller's job via
`kotobase.storage.verify/async-verifying-block-store` (see the top of this
README). This is an operator-controlled mesh (e.g. your own fleet nodes),
not a hardened open-Internet transport, and not a way to reach the public
IPFS network.

`kotoba-lang/io-libp2p` also ships a real, publicly-interoperable
TCP+Noise+Yamux libp2p stack verified against live Kubo/go-libp2p peers --
but its socket driver (`kotoba.net.libp2p.socket`/`dial`/`node`) is
JVM-only (`.clj`), while this whole library is `nbb`/ClojureScript.
Reaching for it would mean porting that socket layer to Node, or making
this one client JVM-only inside an otherwise all-cljs library -- both a
bigger lift than the daemon-independence this client is solving for.
`kotoba.wire.tcp` (already Node-native) is what this client actually uses.

Qualified with real sockets between node handles in one process
(`test/ipfs_native_test.cljk`, distinct TCP ports, genuine `node:net`
connections) AND a real two-OS-process demo
(`bin/native_node_demo.cljk`, mirroring `io-libp2p`'s own
`tcp_demo.cljs` pattern: spawns a real child `nbb` process, verifies via
its own printed stdout). NOT yet run across independent machines/fleet
nodes -- that is a deployment follow-up.

### Standard Helia / Kubo interoperability

`kotobase.storage.ipfs-helia/open!` embeds Helia 7 and implements the same
provider-neutral client shape as the other transports. Helia supplies the
standard libp2p and `/ipfs/bitswap/1.2.0` protocols, so this client exchanges
CID-addressed blocks with both Kubo and other Helia nodes without requiring a
Kubo daemon in the application process. `:peers` accepts standard multiaddrs;
`:connect!` supports later peer additions; `:close!` stops the embedded node.

The earlier nbb probe incorrectly treated two different Helia surfaces as one:
Helia 7's `createHelia` returns the node synchronously (then `start` is awaited),
while `blockstore.get` returns an async iterator. The adapter handles both shapes and
has an injected-node test plus a real two-implementation Kubo/Helia Bitswap
qualification. `ipfs-native` remains useful for a small operator-controlled
mesh, but only `ipfs-helia` is the embedded standards-interoperable transport.

## Test

```sh
kbb --backend sci --classpath "$(kbb -Spath -M:cljs-test)" test/run.cljk
kbb --backend sci --classpath "$(kbb -Spath -M:cljs-test)" test/ipfs_kotobase_test.cljk
kbb --backend sci --classpath "$(kbb -Spath -M:cljs-test)" test/ipfs_kubo_test.cljk
kbb --backend sci --classpath "$(kbb -Spath -M:cljs-test)" test/ipfs_native_test.cljk
kbb --backend sci --classpath "$(kbb -Spath -M:cljs-test)" test/ipfs_helia_test.cljk
./bin/helia_kubo_interop.sh
NBB_CP="$(kbb -Spath -M:cljs-test)" kbb --backend sci bin/native_node_demo.cljk
```
