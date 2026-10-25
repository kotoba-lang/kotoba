# kotobase-protocol-ipq

**IPQ/1 — bounded, verifiable selection over HTTP.** A trustless gateway
answers *give me this CID*. This surface answers *run this traversal and give
me the blocks that prove the result* — the operation kotobase's query plane
already performs, and the one it had no way to offer or to advertise.

```
GET  /ipq/v1                                              profile, limits, encodings, identity
GET  /ipq/v1/selection/{root-cid}?selector=<base64url dag-cbor>
HEAD likewise
```

```clojure
(require '[kotobase.protocols.ipq :as ipq])

(ipq/handle ctx {:method :get
                 :path (str "/ipq/v1/selection/" root)
                 :query {"selector" param}})
;; => {:status 200
;;     :headers {"content-type" "application/vnd.ipld.car"
;;               "x-ipq-profile" "1" "x-ipq-matches" "1" "x-ipq-blocks" "2"}
;;     :body "…" :body-encoding :base64}
```

The handler is a **pure cljc function** over an injected block port —
`(handle ctx req) → resp`. No network I/O, no host JSON, no crypto dependency.
Authentication and transport belong to the deploy shell, exactly as in
[`kotobase-protocol-ipfs`](https://github.com/kotoba-lang/kotobase-protocol-ipfs).

## `find` and `grep` over an IPQ snapshot

`kotobase.protocols.ipq.fs` is the client-side seam from a verified IPQ/1 CAR
to the filesystem capabilities existing Kotoba commands already call. It does
not put HTTP or IPLD traversal inside `find` or `grep`:

```
IPQ/1 CAR → replay selector and verify CIDs
          → versioned KotobaFsSnapshot ADL
          → validated immutable path table
          → wire 34 fs/browse + wire 35 fs/app-data providers
          → unchanged find / grep guest
```

### Two snapshot versions, and why there are two

A **version 1** snapshot inlines every file as UTF-8 `text`. One block is the
whole answer: when it arrives there is nothing further to fetch, and for a tree
that fits in a block that is the better arrangement, not a lesser one.

It is also bounded by `maxBytes`. That bounds the *answer*, but because the
files are inside it, it bounded the *tree* as well — and a filesystem snapshot
format that cannot describe a 40 MiB directory is not describing filesystems.

A **version 2** entry may instead NAME its bytes:

```clojure
{"path" "/workspace/docs/readme.txt" "type" "file"
 "cid" "bafkrei…" "size" 17}          ; raw CIDv1 over sha2-256
```

The snapshot becomes a manifest whose size grows with the number of files
rather than their bytes. Identical files share a CID and are fetched once, an
unchanged file stays in the disk cache across releases, and one edited document
no longer invalidates its 599 neighbours.

Naming content costs a block port, so `mount` takes one:

```clojure
(ipq-fs/mount {:car-bytes car :root root :scope-root "/workspace"
               :adl-capability snapshot-adl
               :blocks {:get (fn [cid] {:bytes (fetch-block cid)})}})
```

This namespace still holds no authority of its own — the host injects the port,
the same shape `ipq/handle` takes. A manifest that names content without one is
refused as `:blocks-port-required` rather than mounted into a tree whose files
turn out to be unreadable a call later. Every block is then checked against the
CID it was asked for, the size the manifest declared, and the text contract it
will be served under, each with its own refusal.

### Writing one

```bash
kbb --backend sci bin/ipq_fs_materialize.cljk snapshot \
  --tree ./public --scope-root /public \
  --car snapshot.car --blocks-dir ./blocks

kbb --backend sci bin/ipq_fs_materialize.cljk materialize \
  --car snapshot.car --root bafkrei… --scope-root /public \
  --blocks-dir ./blocks
```

`--blocks-dir` is a directory of `<cid>` files — the same layout the bytes
plane stores at `ipld/{cid}`, so a host that has fetched blocks by whatever
means it is entitled to can point the CLI at them. Fetch authority stays
outside this command: it opens no sockets, here or anywhere.

The CLI installs the host's SHA-256 through `multiformats.core/install-sha256!`
at module scope. Without it every CID it computes AND every CID it verifies
runs the portable digest, which SCI interprets: measured on 82 real documents,
202 ms a file against 0.7 ms to read the file. `sha256-provider` answers
`:installed` rather than `:portable`, and the suite asserts that, because the
failure it prevents is silent — everything still works, 180x slower.

`--blocks-dir` is required when writing, because every entry this writer emits
NAMES its bytes; a run that put them nowhere would have produced a manifest describing
content no reader can reach. The writer then mounts what it just wrote,
through the same reader production uses, before reporting success.

Both versions are read; version 2 is written. Budgets follow the same split —
`:max-inline-content-bytes` is derived from IPQ's per-response ceiling because
those bytes are already in hand, while `:max-referenced-bytes` bounds what a
manifest *orders* and is answered from the manifest alone, before the first
fetch.

```clojure
(require '[kotobase.protocols.ipq.fs :as ipq-fs])

(def identity
  {:root expected-root
   :scope-root "/workspace"
   ;; In production this can be an ipld.schema/wasm-adl-capability.
   :adl-capability snapshot-adl})

;; Default host path: the bounded verified cache is checked before network I/O.
(def providers
  (ipq-fs/provider-registry identity #(fetch-ipq-car expected-root)))
(def mount
  (ipq-fs/default-mount identity #(fetch-ipq-car expected-root)))

(ipq-fs/browse mount "/workspace")
;; => "docs\t1\nREADME.md\t0"

(ipq-fs/app-data mount "/workspace/README.md")
;; => "..."

(ipq-fs/provider-registry mount)
;; => {34 {:request-type :string :result-type :string :invoke ...}
;;     35 {:request-type :string :result-type :string :invoke ...}}

;; A host needing an isolated lifetime/trust boundary can instead use an
;; explicit CID-scoped cache. Reuse the same capability value.
(def cache (ipq-fs/create-mount-cache 16))
(or (ipq-fs/lookup-mount cache identity) ; before network access
    (ipq-fs/mount-cached cache
                         (assoc identity :car-bytes (fetch-ipq-car expected-root))))
;; receipt :cache is :miss on verification and :hit on reuse.
```

The mount accepts exactly one root match and rejects unused CAR blocks. The ADL
must declare version 1 and is executed with explicit fuel, output-node, output-
byte, depth, and determinism limits. Its logical result is then checked again:
paths are canonical and scope-confined, parents must exist as directories,
duplicates and unknown fields are refused, and total entries/content are
bounded. The provider is read-only and currently implements the operations
needed by `find` and `grep`: browse, full text read, `EXISTS`, and `STAT`.
`RANGE` and `WRITE` are named refusals, not accidental pathname reads.
Directory children are sorted and indexed once at mount time, so recursive
browse is linear in the visited tree rather than entries × directories. The
default process cache is bounded to 16 immutable mounts; an explicit cache can
isolate a shorter host/trust lifetime. Call `mount` directly when every newly
supplied CAR must itself be audited for unused blocks.

On the SCI/Node command runtime, a verified snapshot is atomically materialized
under `${KOTOBA_IPQ_FS_CACHE:-~/.cache/kotoba/ipq-fs/v1}/<root-cid>/tree`.
Files are `0444`, directories are `0555`, and `receipt.json` pins every relative
path, byte count, and SHA-256 digest. The returned mount drops file text from
both path and children indexes; wire 35 reads the materialized regular file and
checks its digest. Existing roots are fully revalidated before reuse, staging
directories are never published, symlinks are refused, and the oldest root is
evicted after the bounded 16-root cache is exceeded. JVM use retains the pure
in-memory mount until the same disk adapter is supplied for that host.

### Agent and toolcall entrypoint

An agent materializes an immutable IPQ snapshot once, then points ordinary
local read tools at the returned `:local-root`. The command verifies the CAR,
root CID, selector, ADL version, snapshot shape, and disk receipt before it
prints a usable path:

```bash
kbb --backend sci bin/ipq_fs_materialize.cljk \
  materialize --car /tmp/selection.car --root <root-cid> \
  --scope-root /workspace
# {:status :materialized, :local-root ".../<root-cid>/tree", ...}
```

`--cache-root DIR` overrides `KOTOBA_IPQ_FS_CACHE` for an isolated run. Unknown,
missing, and repeated options are refused; failures print
`REFUSE<TAB><problem><TAB><message>` and exit 2. The command never fetches the
CAR itself: HTTP authority and authentication remain with the caller. It also
does not apply to a mutable worktree. Use the workspace's normal local/indexed
tools there; a CID snapshot and a live checkout are different consistency
contracts.

### Git project and team contract

A team shares snapshot identity in the project, not the generated cache. Commit
this strict manifest as `.kotoba/ipq.edn`:

```clojure
{:schema "kotoba.ipq.git-project.v1"
 :snapshots
 {"docs" {:root "<root-cid>"
           :scope-root "/workspace"}}}
```

Then every teammate or agent can materialize the same named snapshot from the
same Git commit:

```bash
kbb --backend sci bin/ipq_fs_materialize.cljk \
  git-materialize --project /path/to/project --snapshot docs \
  --car /tmp/selection.car
```

Git mode resolves the repository top level, reads the manifest from
`HEAD:.kotoba/ipq.edn`, and records the full commit SHA, project, manifest, and
snapshot name in the receipt. An untracked or modified manifest is refused;
unrelated worktree changes are allowed because they cannot change the committed
snapshot identity. `--root` and `--scope-root` are refused in this mode so a
toolcall cannot silently override the team's reviewed values.

The CAR remains an explicit local input and the verified tree remains under the
per-user cache. Do not add either to Git. Git distributes the small declarative
identity; IPQ distributes content-addressed bytes; the local materializer owns
the generated read-only tree. A project can name multiple snapshots without
sharing developer-specific cache paths or credentials.

## What a 200 from here means, exactly

The body is a CARv1 holding the blocks a bounded IPLD selector touched, root
first. Every one was rehashed before it was decoded, and the caller can replay
the same selector against the archive alone and reach the same matches without
trusting this server:

```clojure
(trustless/replay-selection car-bytes root selector-bytes ipq/limits)
;; => {:matches [{:path ["child" "title"] :value "selected"}]
;;     :loaded [root leaf] :unused []}
```

That round trip is the repo's central test. Without it this is an endpoint
that returns some bytes.

**It does not mean the answer is complete.** Replay proves that a named
traversal ran over verified bytes. Proving that a database range or a Datalog
answer omits nothing needs authenticated index boundaries, which do not exist
yet (kotobase `docs/adr/2609060000-ipld-adl-selector-car-boundaries.md`). That
is the whole reason the profile number is on the wire: this is IPQ/1, and a
later profile carrying completeness proofs would be a different number, not a
silently better version of this one.

## Why a separate path rather than `?selector=` on `/ipfs/`

kotobase ADR-2609060000, verbatim: *An arbitrary `?selector=` endpoint
returning CARv2 is a custom protocol, not automatically a standard trustless
gateway. Negotiate supported forms and versions explicitly.* Overloading
`/ipfs/` would make a non-standard response indistinguishable from a standard
one to a client that guessed wrong. `/ipq/v1/` says which protocol answered.

The two sections below are the rest of that sentence: which forms and versions
are refused, and which protocol identifier this address answers for.

## Discovery

`ipni.metadata/ipq-selection-http-bytes` (in
[`io-ipni-specs`](https://github.com/kotoba-lang/io-ipni-specs)) is the
advertisement half: protocol identifier `0x300940`
(`transport-ipq-selection-http`) then one uvarint profile number. The code sits
in the multicodec **private use area** (`0x300000–0x3FFFFF`, "reserved for
internal use by applications"), offset by `0x0940` — the next free slot in the
registered transport family, which is what a registration would ask for.
Announcing an unregistered code outside that range would be squatting on a
registry we do not own.

`GET /ipq/v1` states the same identity, and that is what closes the loop. An
index hands a client a protocol identifier and an address, not a promise that
the two belong together; before this, the only way to confirm the address
matched the identifier was to send a selection and see whether what came back
looked like one.

```json
"ipni": {"protocol": 3148096,
         "name": "transport-ipq-selection-http",
         "privateUseArea": {"from": 3145728, "to": 4194303},
         "registrationRequest": 2368,
         "metadata": {"ipq": "c092c0010101",
                      "advertised": "a01200c092c0010101"}}
```

Both codes are published because only one of them is ever on the wire, and a
client that saw `0x300940` and no explanation would have to guess which
registry it came from. `metadata` is hex, and it is the framing an
advertisement carries — `uvarint(protocol) ++ uvarint(payload-length) ++
payload`, measured against go-libipni v0.8.2 rather than read off IPNI.md's
prose, which omits the length the reference requires. `ipq` is this protocol's
entry alone; `advertised` is the whole Metadata field kotobase publishes, the
trustless gateway entry `a01200` first because `0x0920 < 0x300940` and the spec
asks for increasing protocol order.

This repo does not require `ipni` and does not advertise; publishing is the
deploy shell's business. Stating the constants here rather than importing them
is deliberate — the handler has three dependencies and the advertising half is
not one of them — and the test pins every number, including the derivation of
the metadata bytes from the profile, so a profile bump that forgot the bytes
goes red rather than advertising IPQ/1 for a surface that is no longer IPQ/1.
What no test here can pin is the other repo: nothing imports `ipni.metadata`,
so a change made only there is a change nobody here will notice. That is the
price of the three-dependency handler, and it is paid knowingly.

## `Accept` is answered, not ignored

This surface makes exactly one representation, so negotiation is a yes or a
406 rather than a choice:

| `Accept` | |
|---|---|
| absent, empty, `*/*`, `application/*` | served — nothing in the field to refuse |
| `application/vnd.ipld.car`, with or without `version=1` | served |
| `application/vnd.ipld.car;version=2` | **406** — the descriptor publishes `car-version: 1` |
| `application/json`, `application/vnd.ipld.raw`, any other concrete type | **406** |
| `application/vnd.ipld.car;q=0, */*` | **406** — that field says *anything but a CAR* |

`order` and `dups` are the trustless gateway's parameters. They are ignored
rather than refused, because this is not a gateway and a 406 for every
parameter that registry grows would be a surface that stops working on someone
else's schedule. `version` is negotiated because the descriptor publishes it.

Quality values are read only for `q=0`, which is an exclusion rather than a
ranking — there is one representation here and nothing to rank — and the
qvalue that decides is the one on the most specific range that covers us, so
`application/vnd.ipld.car;q=0, */*` is refused while `application/json;q=0,
*/*` is served.

`GET /ipq/v1` is not negotiated. It is how a client learns what to ask for, and
refusing to describe the surface because the client's `Accept` named the
surface's own media type would close the only way back out of a wrong guess.
RFC 9110 permits answering anyway, and that is the reading taken.

## Refusals that are not the same refusal

| status | error | means |
|---|---|---|
| 400 | `selector-required` | no `?selector=` |
| 400 | `selector-not-base64url` | a character outside the alphabet — never dropped |
| 400 | `selector-not-dag-cbor` | base64url decoded, and the bytes are not CBOR |
| 400 | `invalid-selector` | decodes as CBOR, but outside the supported subset |
| 404 | `root-not-held` | this store never had the graph |
| 404 | `missing-block` | it has the root and is missing an interior block |
| 404 | `unknown-ipq-path` | an `/ipq/` path this deployment does not serve — named, not a bare 404 |
| 406 | `accept-not-satisfiable` | an `Accept` naming a type, or a CAR version, this surface does not make |
| 413 | `resource-limit` | a budget was exhausted **mid-traversal** |
| 501 | `block-port-required` | `ctx` carries no `:blocks` port — about the deployment, not the graph |
| 502 | `cid-mismatch` | a stored block does not hash to its key |
| 502 | `unsupported-block-encoding` | the store returned an encoding this surface will not guess at |

The two 404s are both true and they are not interchangeable: one is a question
about content we do not hold, the other is a partially-collected store, and
only the second is something an operator can act on.

`resource-limit` is never a truncated 200. An incomplete retrieval that
returns 200 is the failure this surface exists to avoid.

`accept-not-satisfiable` is decided ahead of the selector, so a request that is
wrong twice hears about the larger problem first: a client that cannot read the
representation gains nothing from having its selector validated.

## Budgets are published, not merely enforced

`GET /ipq/v1` carries `maxBlocks`, `maxBytes`, `maxDepth` and `maxMatches`. A
client that cannot read the budget before building a selector can only discover
it by being refused, and a refusal it did not anticipate is indistinguishable
from a server fault.

## Test

```bash
kbb -M:test                                        # JVM
kbb --backend sci bin/run_tests.cljk                  # SCI/Node (first-class)
```

The filesystem provider's cache and recursive-browse costs have a reproducible
SCI benchmark.  It prints EDN medians and includes the pre-index browse algorithm
as its control:

```bash
kbb --backend sci bench/ipq_fs.cljk
```

Both halves run the same `.cljc`.

## Namespace

`kotobase.protocols.ipq`, matching the other surface repos. Repo name and
namespace need not match, and renaming would break consumers for no benefit.

Split per superproject ADR-2608051000 (`1 repo = 1 capability`): this surface
needs a selector engine and a CAR codec, and pulling those into the
low-privilege gateway repo is exactly what that rule exists to prevent.
