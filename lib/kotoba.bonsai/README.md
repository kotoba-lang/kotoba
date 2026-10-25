# bonsai

*(旧 kotoba-git — 2026-07-16 rename。盆栽＝人が木を意図的に仕立てる craft ＝ object DAG を操る道具。namespaces も bonsai.* に移行済み (2026-07-16))*

A content-addressed git object model (blob/tree/commit) and mutable ref
store, represented as **native `arrangement` (Datomic-shaped) datoms** —
not a separate content-addressed block store bolted onto the side of the
`kotobase-peer` stack. A blob/tree/commit's *subject* IS its own content
hash; `io-multiformats`/`org-ietf-cbor`/`io-ipld` contribute only their
pure canonical-encoding/hashing functions to derive that identity —
nothing is persisted through them. Git is a schema *within* the Datomic-
shaped foundation, not a store beside it.

This is the "git-equivalent" half of ADR-2607072200 (`kotoba-git-kotoba-rad-
on-kotobase-peer`, superproject `90-docs/adr/`, see its addendum for this
redesign). `nekko` is the sibling "Radicle-equivalent" half (sovereign
identity, delegates, signed refs).

## What this is

The B2 Git-command adapter and its cache/authority boundaries are documented in
[docs/b2-git.md](docs/b2-git.md). It uses `kotoba-b2://BUCKET/GENESIS-CID`, the
existing Git transport bridge, Bonsai object codecs and Nekko signed ref events.

- **`bonsai.repo`** — `empty-repo` (a fresh `arrangement` db) and
  `persist!` (snapshot the *whole* repo — objects and refs together — to
  durable storage via `arrangement.core/commit!`), and `repo/restore`
  (materializes the complete persisted db, distinct from B2 lazy retrieval).
  A repo is one db;
  object subjects are content hashes, ref subjects are repo ids —
  disjoint namespaces, so both coexist without collision.
- **`bonsai.object`** — `write-blob`/`read-blob` (raw, 0x55 codec),
  `write-tree`/`read-tree` and `write-commit`/`read-commit`. Every write
  function is a pure `(fn [db ...] -> [db' cid])`, threaded the same way
  `bonsai.refs` already was. Commits carry a `parents` vector (0, 1,
  or N), so merge commits are representable — a real commit *DAG*, not a
  linear chain. `commit/tree` is asserted as a genuine `ipld/link`, so
  `arrangement.core/refs-to` answers "which commits reference this tree"
  for free — a reverse graph query with zero extra code, the concrete
  payoff of living inside the Datomic-shaped store instead of beside it.
- **`bonsai.log`** — `ancestors` (full DAG reachability), `log`
  (first-parent history, newest-first), and `missing-since` (every commit/
  tree/blob CID reachable from a head that isn't already in a `have` set —
  the object-negotiation primitive a push/pull/pack exchange needs). Reads
  straight out of the same `db` `bonsai.object` writes into.
- **`bonsai.refs`** — `refs/heads/main`-style mutable pointers as
  quads in the same `db` (`set-ref`/`get-ref`/`list-refs`) — the mutable-
  pointer-over-immutable-DAG pattern Datomic itself uses for its own
  indexes.
- **`bonsai.ref-policy`** — `fast-forward?` and `set-ref-ff-only!`:
  whether moving a ref from one commit to another is a fast-forward (the
  old target is nil, equal to the new one, or one of its ancestors in the
  commit DAG — computed via `bonsai.log/ancestors`), and a variant of
  `set-ref` that throws (leaving the ref untouched) rather than silently
  allowing a non-fast-forward move. This is *shape* policy (is this
  update a rewind/diverge?), independent of and composable with
  `nekko`'s *identity* policy (who signed off on it) — and
  `set-ref-guarded!` now composes the two into one call: it takes a
  caller-supplied 0-arg `authorized?` predicate (typically a partial
  application of `nekko.push-gate/authorize-push?` or
  `authorize-push-cacao?`, but this namespace has no dependency on
  `nekko` to make that work — any predicate does), checks it
  *before* the fast-forward check, and throws `ex-info` with a `:reason`
  of `:unauthorized` or `:not-fast-forward` so a caller can report the
  two differently (e.g. HTTP 403 vs 409).
- **`bonsai.git-object`** — byte-exact Git loose-object compatibility seam.
  It frames arbitrary blob/tree/commit/tag bodies as
  `<type> <size>\0<body>`, computes the real Git SHA-1 OID, stores the exact
  framed bytes under a raw CID, and projects the verified OID↔CID bridge into
  the same arrangement db. Reads recompute CID, OID, framing, declared size,
  and bridge membership before returning bytes. Golden blob vectors and live
  `git hash-object` conformance tests run on the JVM and under kbb alike; on
  ClojureScript the OID is pure `kotoba.bytes.sha1`, not Node's `crypto`.
- **`bonsai.git-codec`** — typed Git tree and commit body codecs with canonical
  modes, raw SHA-1 names, Git ordering, ordered parents, exact identities,
  continuation headers, and messages; checked against real Git.
- **`bonsai.loose-object`** — bounded zlib encode/decode for complete loose
  object files. Git reads codec output directly from `.git/objects`, and the
  decoder reads what `git hash-object -w` writes. On ClojureScript the zlib is
  `org-ietf-deflate`, not Node's `zlib`.
- **`bonsai.pack`** and **`bonsai.delta`** — PACK v2 write/read,
  OFS/REF delta resolution, delta application, and idx v2 generation with
  fanout, CRC32, offsets, and checksums. Output passes `git verify-pack`, and
  a pack `git pack-objects` writes (deltas included) decodes to git's OIDs.
  On ClojureScript SHA-1, CRC-32 and inflate are the pure `kotoba.bytes.sha1`
  and `org-ietf-deflate`.
- **`bin/git-remote-kotoba`** — executable remote helper using Git's `connect`
  capability for upload-pack/receive-pack. Local URLs open a bare repo directly;
  `kotoba://` URLs use an isolated SHA-256-keyed cache plus the explicit
  `KOTOBA_GIT_ADAPTER fetch|push <remote> <path>` lifecycle. Adapter execution
  is argv-only (no shell interpolation), completes hydration before the Git
  byte stream begins, and publishes only after successful receive-pack.
- **`bin/kotoba-git-reference-adapter`** — filesystem reference adapter proving
  network-shaped `kotoba://host/repo` clone/fetch/push and cache refresh. A
  production adapter replaces its mirror fetch/push with CID block hydration,
  closure verification, and `nekko.ref-event` admission.
- **`bin/kotobase-http-git-adapter`** — HTTPS production-client adapter. It
  GETs/PUTs Git bundles at `/git/v1/repos/<rid>/bundle`, supplies Authorization
  through curl stdin rather than argv, and binds uploads to a SHA-256 digest and
  complete ref projection. HTTP is restricted to an explicit loopback test.
- **`bin/kotobase-private-git-adapter`** — the encrypted private-Git adapter
  (`bonsai.private-remote`): the service sees two IPLD blocks and a head event,
  never a bundle or a key. See *Private Git on kotobase.net* below.
- **`bin/kotoba-git-recipient`** / **`bin/kotoba-biscuit-mint`** — the local
  recipient key store (`bonsai.recipient-store`) and the service-token →
  repository-Biscuit exchange the adapter reads its credential from.
- **`bonsai.private-repo`** (composition layer; `envelope.seal-jvm` on the
  JVM, `envelope.seal-sync` on kbb) — seals a complete Git
  bundle with `kotoba-lang/envelope`, addresses randomized ciphertext as a raw
  IPLD CID, and addresses the recipient-scoped descriptor as DAG-CBOR. Sharing
  re-wraps the existing content key without touching ciphertext; revocation is
  only exposed as epoch rotation with a fresh key and ciphertext. Exact
  fetch/push/share/rotate/advertise rights are authorized by an attenuable
  Biscuit, while IPNI advertisements contain only the ciphertext CID and an
  opaque caller-supplied context id. Storage and discovery transports are
  injected, so GitHub, Radicle, and git.kotobase.net remain optional adapters.

## What this deliberately is NOT (yet)

- **No deployed kotobase Git server route yet.** Local/materialized Git CLI
  interoperability now covers typed objects, loose files, pack/index/delta,
  upload-pack/receive-pack, and `git-remote-kotoba`. The helper currently opens
  a bare repository path or a configured lifecycle adapter; the included
  adapter may be filesystem-backed or use the included HTTPS client. The
  corresponding kotobase.net route and durable `nekko.ref-event` transaction
  are still pending. Smart HTTP discovery and partial-clone filters are also
  pending. Native `bonsai.object` CIDs remain unchanged.

### Remote-helper adapter contract

```bash
export PATH="$PWD/bin:$PATH"
export KOTOBA_GIT_CACHE=/absolute/private/cache
export KOTOBA_GIT_ADAPTER=/absolute/path/to/kotobase-adapter
export KOTOBA_GIT_AUTHORIZATION='CACAO <base64-dag-cbor>'

git clone kotoba://git.kotobase.net/<rid>
git push kotoba://git.kotobase.net/<rid> main
```

The adapter is invoked without a shell:

```text
<adapter> fetch <remote-url> <materialized-bare-path>
<adapter> push  <remote-url> <materialized-bare-path>
```

`fetch` must leave a complete verified bare repository at the supplied path.
`push` runs only after `git-receive-pack` succeeds and must verify the resulting
Git closure before publishing blocks and advancing signed peer refs. Network
remotes fail closed unless both an absolute cache root and adapter are set.

HTTPS wire contract:

```text
GET /git/v1/repos/<urlencoded-rid>/bundle
  Authorization: CACAO ... | Bearer ...
  -> 200 application/x-git-bundle | 404 unborn repository

PUT /git/v1/repos/<urlencoded-rid>/bundle
  Authorization: CACAO ... | Bearer ...
  Content-Type: application/x-git-bundle
  X-Kotoba-Bundle-SHA256: <64 lowercase hex>
  X-Kotoba-Refs-EDN-B64: <base64url complete ref projection>
```

The server must authenticate before reading the body, recompute the digest,
verify bundle closure and ref policy, persist all blocks, admit signed peer-ref
events, and acknowledge only after bundle and ref state are durably readable.
- **No transport/replication wiring in this repo.** `missing-since` gives
  the object diff a sync protocol needs, and `kotoba-lang/p2p` (gossip
  fanout + bitswap-style delta-sync + `chain/verify-chain`, now with
  pluggable signed head-announce hooks — see `nekko.announce`) is
  the actual sync layer, but `bonsai` itself has no dependency on
  `p2p` and no code wiring the two together; that composition lives in
  whatever application uses both.
- **No claim that the current hosted bundle route is end-to-end encrypted.**
  `bonsai.private-repo` is a tested provider-neutral client/storage primitive.
  The existing `/git/v1/repos/:rid/bundle` route still accepts plaintext Git
  bundles until a client and server negotiate the private snapshot media type;
  using that hosted route is not proof that private plaintext stayed off the
  operator boundary.
- **No push authorization built into `bonsai.refs` itself.** Deciding
  *who's* allowed is still `nekko`'s job (`authorize-push?`/
  `authorize-push-cacao?`) — verified end-to-end in an integration script
  (see the ADR's Verification addendum) — and `bonsai.refs/set-ref`
  on its own still enforces nothing. `bonsai.ref-policy/
  set-ref-guarded!` now composes identity + shape into one call (see
  above), so a caller no longer has to hand-order the two checks
  themselves — but `set-ref-guarded!` still takes `authorized?` as an
  injected predicate; `bonsai` still has zero dependency on
  `nekko`.
- **No recursive/fixpoint Datalog for history walks.** `arrangement.datalog`
  is a conjunctive-join query layer, not (yet) a transitive-closure one
  (ADR-2607022600 flags "Datalog fixpoint" as a follow-up) — `ancestors`/
  `log`/`missing-since` still walk the DAG by hand rather than expressing
  reachability as one Datalog query.

## Private Git on kotobase.net

`kotobase-private-git-adapter` is a `KOTOBA_GIT_ADAPTER` for
`/git/v1/repos/:rid/private/{blocks,head}`
(kotobase-api-gateway-cljs `kotobase.git-private-snapshot`):

- **push**: `git bundle create --all` of the cache → `private/seal-snapshot`
  (hybrid X25519 + ML-KEM-768, to this machine's recipient plus
  `KOTOBA_GIT_RECIPIENTS`) → `PUT …/blocks/<descriptor-cid>` (DAG-CBOR) and
  `PUT …/blocks/<ciphertext-cid>` (raw), each with `X-Kotoba-Git-Operation:
  push` → `PUT …/head {snapshot_cid, operation "push", expected_heads}`.
- **fetch**: `GET …/head` → `GET` both blocks → `restore-snapshot` (both CIDs,
  canonical descriptor, repository, and the head event) → `open-snapshot` →
  `git clone --mirror` / `git fetch --prune` from the bundle into the cache.
- Every request carries `Authorization: Biscuit <token>` (the gateway reads
  the scheme case-insensitively, `kotobase.biscuit-grant/header-token`), with
  the token re-read from `KOTOBA_GIT_BISCUIT_FILE` per request — a Biscuit
  lives 15 minutes and may be replaced mid-push. Never from argv.
- **Concurrency is Git-shaped.** The cache records the tip it was fetched
  from; a push names that tip as parent and `expected_heads`, so a remote that
  moved in between refuses it (fetch, merge, push again). A head with several
  tips — pushes the service kept apart instead of ordering — fails closed on
  fetch and on push, naming the tips. No winner is picked.
- Writer feeds, IPNS and IPNI advertisement are not sent (all optional on the
  head PUT).
- **Launching from any cwd**: the bin scripts are `#!/usr/bin/env kbb`
  launchers. kbb resolves the project from the script's *real* path (a symlink
  on `PATH` is fine, a copy is not), so `src/`, the pinned `:git/sha` deps
  and their npm modules — installed by kbb under `~/.gitlibs` and put on
  `NODE_PATH` — resolve wherever git starts the adapter. (Running them as
  `kbb --backend sci --classpath …` is what loses `NODE_PATH`; don't.)
- **CID hashing** runs on node:crypto's SHA-256, installed through
  io-multiformats' `install-sha256!` seam, which proves it against the
  portable digest before accepting it (and `bonsai.sha256-seam-test` pins the
  golden CIDs through it). For a 17 MB bundle under kbb, measured 2026-10-07:
  seal 52 ms, verify 29 ms, open 38 ms; with the portable digest the same
  steps take 26 s, 52 s and 49 s.

Operator setup (one machine; nothing secret in argv or shell history):

```sh
export PATH="/path/to/bonsai/bin:$PATH"

# 1. recipient keys (once per machine): ~/.config/kotoba/rad/recipient.edn, 0600
kotoba-git-recipient init          # prints only the public descriptor
kotoba-git-recipient show          # the same, later; share it to be sealed to

# 2. a repository Biscuit (15 min) from a kb_sa_ service token kept in a 0600 file
export KOTOBA_SERVICE_TOKEN_FILE=~/.config/kotoba/rad/service-token
export KOTOBA_TENANT_ID=<tenant id>
export KOTOBA_GIT_REPOSITORY=rad:cloud-murakumo
export KOTOBA_GIT_BISCUIT_FILE=~/.config/kotoba/rad/cloud-murakumo.biscuit
kotoba-biscuit-mint                # POST https://auth.kotoba.cloud/v1/biscuit/token

# 3. the remote
export KOTOBA_GIT_CACHE=~/.cache/kotoba/git
export KOTOBA_GIT_ADAPTER="$(command -v kotobase-private-git-adapter)"
git remote add kotobase kotoba://kotobase.net/rad:cloud-murakumo
git push kotobase main             # and: git clone kotoba://kotobase.net/rad:cloud-murakumo
```

**authn's `mutation-guard` does not reject this.** `POST /v1/biscuit/token`
runs under `mutation-guard` (`authn/src/authn/worker.cljk`), which passes a
request when `safe-browser-mutation?` holds, and that is true for *any*
request carrying an authorization credential: `authorization-credential?` is
`bearer-token` or `biscuit-token`, i.e. `Authorization: Bearer
<[A-Za-z0-9._~-]{20,2048}>` (or `Biscuit <[A-Za-z0-9_-]{80,8192}>`). Only a
request without one must be same-origin JSON (`Origin` equal to the authn
audience or `https://<base-domain>` and `Content-Type` containing
`application/json`). So a CLI needs no `Origin`. What it does need: the
service token must be `kb_sa_…`, 40–256 characters
(`enterprise/verify-service-token`), active, and of the tenant named in
`tenantId` (`principal!`), and the requested permissions must be within the
service account's (`biscuit/mint`: `grantable?`). A token that does not match
the Bearer pattern falls through to the browser check and gets
`403 same-origin application/json request required`.

## Usage

```clojure
(require '[bonsai.repo :as repo]
         '[bonsai.object :as obj]
         '[bonsai.log :as log]
         '[bonsai.refs :as refs])

(def db0 (repo/empty-repo))
(let [[db1 blob] (obj/write-blob db0 (.getBytes "hello\n" "UTF-8"))
      [db2 tree] (obj/write-tree db1 [{:name "hello.txt" :cid blob :kind :blob}])
      [db3 commit] (obj/write-commit db2 {:tree tree :parents []
                                           :author "did:key:z..." :message "initial"
                                           :ts (System/currentTimeMillis)})
      db (refs/set-ref db3 "my-repo" "refs/heads/main" commit)]
  (refs/get-ref db "my-repo" "refs/heads/main")          ;=> commit
  (log/log db commit)                                    ;=> [{:cid commit :tree tree ...}]
  (log/missing-since db commit #{})                       ;=> #{commit tree blob}

  ;; persist the whole repo (objects + refs together)
  (let [store (atom {})
        put! (fn [cid bytes] (swap! store assoc cid bytes))]
    (repo/persist! put! db nil))

  ;; identity + shape composed into one guarded update (nekko optional):
  ;; (require '[bonsai.ref-policy :as policy])
  ;; (policy/set-ref-guarded! db "my-repo" "refs/heads/main" commit
  ;;                           #(nekko.push-gate/authorize-push?
  ;;                              get-fn journal-head owner-did rid
  ;;                              "refs/heads/main" commit sr))
  )
```

## Testing

```
kbb -M:test          # against the pinned :git/sha deps
kbb -M:local:test    # against sibling checkouts in ../ (same-monorepo dev)
npm install && npm run test:cljs   # real ClojureScript (shadow-cljs node-test), not just .cljc-named
```

`kbb` is nbb — there is no JVM under it — and `kbb -M:test` runs the whole
suite, real-`git` conformance included (`kotoba.process` is spawnSync there).
`bonsai.private-repo` runs there on `envelope.seal-sync`, the synchronous
JVM-free backend of `kotoba-lang/envelope` (same wire format as
`envelope.seal-jvm` and the browser's `envelope.seal`), which also wraps hybrid
X25519 + ML-KEM-768 recipients (`seal-snapshot` with `:kem
:x25519+ml-kem-768`); the JVM refuses a hybrid snapshot rather than sealing it
classically.

`test/private_git_adapter_test.cljk` drives the private adapter end to end
with real `git` against `test/private_git_stub.cljk`, a child-process stub of
`/private/{blocks,head}` that validates with `bonsai.private-wire` as the
gateway does: push, clone, incremental push, a stale push refused, two racing
pushes left as two tips (the adapter refuses them), a key that was not sealed
to, a tampered block (refused by the stub, and by the client when a stub
serves it anyway), a wrong Biscuit, the key store, and `kotoba-biscuit-mint`
against a local authn stub. Nothing contacts kotobase.net or
auth.kotoba.cloud.

The `bin/` scripts (`git-remote-kotoba` and both adapters) run under kbb,
which is nbb — JVM-free — so they are tested there, end to end with real
`git`, by their own runner:

```
kbb --backend sci --classpath "src:test:$(kbb -Spath)" test/run_remote_helper.cljk
```

They were babashka scripts until `204c18e` rewrote their shebangs from `bb`
to `kbb` without porting them; from then until this runner existed none of
the three could start (`load-file` / `babashka.process` / `java.*` do not
exist under nbb), and nothing noticed, because the only test that drove
them ran on the JVM.

Review qualification: the kbb helper runner passes 8 tests / 58 assertions,
including incremental fetch, a binary object, actual HTTP bundle digest, Unicode
repository-name encoding, padded refs, signal propagation and refusal before an
unsupported service handshake. The original JVM test bodies remain under their
`:clj` branch; they were not executed in this qualification. The repository
suite now runs pack/loose-object conformance under kbb; private-repo still
needs the synchronous-envelope portability follow-up.

Pack review also covers actual Git-written REF_DELTA and OFS_DELTA packs and
Git verification of Bonsai-generated indexes for both. Sizes use exact integer
arithmetic up to 2^53 − 1, instead of JavaScript's wrapping 32-bit shifts.
Malformed sizes, truncated entries/copy operands, reserved types and trailing
pack data fail closed; delta output cannot exceed its declared result size.
This qualification is kbb/Node, not a browser or an amu guest execution.

HTTP adapter failures clean their temporary bundle files. Authorization values
with control characters, quotes or backslashes are refused before curl runs.
A remote 404 with nonempty cached refs fails rather than serving stale data;
an empty bootstrap cache can still represent a new remote. Bundles are hashed
in 64 KiB chunks. This verifies transport, not production signed-ref admission
or a live service deployment.

Unlike `nekko` (which pulls in JVM-only `ed25519.core`/`cacao.core`),
`bonsai` has no non-portable dependency, so it runs real ClojureScript
CI (`gen-shadow-cljs-edn.bb` resolves `shadow-cljs.edn`'s `:source-paths`
from `kbb -Spath`, so cljs always tests the exact pinned versions
`kbb -M:test` does — never a hand-duplicated, driftable list).
Wiring this up caught two genuine portability bugs the `.cljc` extension
alone didn't guarantee: `bonsai.repo`'s `identity-blind`/
`identity-encrypt` had to become real `js/Promise`-returning functions on
cljs (`arrangement.core`'s own cljs code path calls `.then` directly on
`encrypt-fn`'s return value — Web Crypto's AEAD has no sync primitive),
and comparing two typed-array-backed `seq`s directly (`(= (seq a) (seq
b))`) is unreliable in cljs even when the underlying bytes are identical
— `(= (vec a) (vec b))` is the portable comparison (matching
`io-multiformats`'s own test convention).
