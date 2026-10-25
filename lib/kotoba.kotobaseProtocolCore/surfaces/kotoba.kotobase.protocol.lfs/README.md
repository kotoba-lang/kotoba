# kotobase-lfs

The Git LFS wire, as a pure `.cljc` engine over an injected
`kotobase.storage.object` provider.

This repo owns the *protocol* and nothing else. What exists, where the bytes
go, and what an object is called all belong to
[`kotobase-storage`](https://github.com/kotoba-lang/kotobase-storage). Same
split as [`kotoba-annex`](https://github.com/kotoba-lang/kotoba-annex), which
speaks the other ecosystem's wire over the same plane — LFS and git-annex are
two spellings of one problem, not two stores (superproject ADR-2608012600).

```
kotobase.lfs.pointer   the blob that is committed instead of the bytes
kotobase.lfs.batch     request validation + response construction (no store)
kotobase.lfs.engine    batch/verify answered against a storage provider
```

```clojure
;; synchronous store — stat and grant resolved for you
(engine/handle-batch
 (let [ctx {:objects-base "https://kotobase.net/git/v1/repos/<rid>/info/lfs/objects"
            :expires-in 900
            :max-object-bytes (* 5 1024 1024 1024)
            :quota (fn [{:keys [new-bytes new-objects]}] nil)}]
   (assoc ctx :stat (engine/stat-fn store)
              :grant (engine/proxy-grant-fn ctx)))
 body)
;=> {:status 200 :body {:transfer "basic" :objects [...] :hash_algo "sha256"}}
```

## The engine does no I/O

On a Cloudflare Worker `-stat-object` and any SigV4 presign return Promises,
so an engine that called the store inline would pass on the JVM and hand back
unresolved promises in production. The caller resolves first and the engine
decides from values:

```clojure
(def parsed (batch/parse-request body))              ; pure
(def stats  (await (stat-every (:objects parsed))))  ; caller awaits
(def needs  (engine/grants-needed parsed ctx stat))  ; exactly what needs one
(def grants (await (presign-every needs)))           ; caller awaits
(engine/handle-batch (assoc ctx :stat stat :grant grant) body)
```

`grants-needed` and the response share one decision function, so they cannot
disagree about which objects get an action.

## An LFS oid IS the CID

`oid sha256:<hex>` and `CIDv1(raw, sha2-256)` carry the same digest, so the
conversion is a pure function and there is no registry to keep in sync. The
engine refuses an oid it cannot convert rather than storing bytes under a name
nothing can resolve.

## Three things the tests hold in place

**An upload of an object the server already has omits `actions` entirely.**
Not an empty map, not an upload href the client is expected to ignore.
Omission is how the protocol says *already uploaded*; anything else makes
every client re-push everything it already pushed.

**LFS is an HTTP-status protocol.** A 200 carrying `{ok: false}` reads as
success to every LFS client. The kotobase datom plane speaks the opposite
(XRPC) convention on the same host, so the two must not share a response
helper — the mirror image of the client-side bug in ADR-2607175000 (3).

**Quota is decided before any grant is issued**, on the bytes not yet stored.
Once a presigned URL is out, the server has no further say in whether those
bytes arrive.

Locking is not implemented and answers `501`. A `200` with an empty lock list
would tell a client its lock succeeded while nothing enforces anything.

## Test

```sh
kbb -M:test
```

23 tests / 71 assertions on the JVM. The engine, the pointer codec and the
in-memory provider are also exercised under `nbb`, because the deployment
target is a Cloudflare Worker and "passes on the JVM" is not evidence for it.
