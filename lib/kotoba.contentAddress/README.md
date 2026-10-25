# content-address

**A document's identity is its bytes.** This is the small library an
application uses to stop identifying its resources by path.

```
identity   :kotoba.app/bundle-cid   raw CIDv1 of the document      bafkrei…
naming     :kotoba.app/latest       key-derived IPNS name          k51…
location   :published {:archive …}  a host that answered a GET     https://…
```

The three are different things and this library keeps them apart. A location
can move, go away, or be replaced without the bytes changing — so it never
appears in a `:kotoba.*` attribute, and a manifest that carries only a URL is
reported as **not addressed**, not as fine.

The design has a name: **content addressing** (対語は location addressing).
Links are *merkle links*, the mutable pointer is a *self-certifying name*,
and the whole shape is *location-independent*. See the superproject's
`manifest/concept-vocabulary.edn` entry `:content-addressing`, and
ADR-2608157000 for why apps in this workspace are built this way.

> ⚠ IPLD paths (`/ipld/{cid}/a/b`) exist and are fine — they are resolution
> paths through a DAG, not locations. "Not path-based" constrains what
> identifies a resource, not how you walk into one.

## Use it

```bash
# What is this document's identity? (pure, no network)
kbb --backend sci --classpath src bin/content_address.cljk address dist/index.html

# Publish: address → archive PUT → GET back → compare bytes → record it
KOTOBASE_ARCHIVE_TOKEN=… kbb --backend sci --classpath src bin/content_address.cljk \
  publish dist/index.html --manifest kotoba.app.edn

# Is the address still true? (fetches and re-derives)
kbb --backend sci --classpath src bin/content_address.cljk verify kotoba.app.edn

# Which manifests identify by content, and which only by location?
kbb --backend sci --classpath src bin/content_address.cljk audit $(git ls-files '*kotoba.app.edn')
```

From Clojure/ClojureScript:

```clojure
(require '[content-address.core :as ca]
         '[content-address.archive :as archive])

(archive/address html)          ;; => {:cid "bafkrei…" :size 816065 :octets [...]}
(ca/embed-url cid)              ;; => "ipfs://bafkrei…"
(ca/addressed? manifest)        ;; => true / false — the measurement predicate
(ca/problems manifest)          ;; => [] or [{:problem :no-content-address …}]
```

`publish!` is **fail-closed**: it PUTs, GETs the object back, and compares
the returned bytes with what it sent. A `201` on its own is not evidence —
the failure worth preventing is a manifest recording an address that nothing
serves.

Exit codes are three-valued: **0** answered yes, **1** answered no, **2**
could not answer. A check that could not run must not look like a pass.

## Boundaries — what this is not

| Concern | Owner |
|---|---|
| The layer table (L0 address … L5 application) | [`kotoba-lang/kotoba-protocol`](https://github.com/kotoba-lang/kotoba-protocol) — spec-first, zero deps |
| L2 graph commits (`chain.core/commit!`) | [`kotoba-lang/chain`](https://github.com/kotoba-lang/chain) |
| IPNS records, DHT publish | [`kotoba-lang/tech-ipfs-specs-ipns`](https://github.com/kotoba-lang/tech-ipfs-specs-ipns) (`.cljc`), `kotobase-client` (cljs) |
| Gateway semantics | [`kotoba-lang/tech-ipfs-specs-http-gateway`](https://github.com/kotoba-lang/tech-ipfs-specs-http-gateway) |
| Storing the bytes | kotobase.net (`PUT /ipfs/{cid}`), B2, IPFS |

This library composes those into the one path an application actually walks,
and adds nothing they already do. It does **not** hash inside `core` (that is
`digest`, the only platform-specific namespace), does not resolve names, and
does not own a block store.

## Two facts the archive imposes

1. **`PUT /ipfs/{cid}` takes raw CIDv1 only** (codec `0x55`). A dag-cbor
   identity — an L2 graph commit, `bafy…` — must be archived under the *raw*
   CID of the same bytes. `same-object?` exists so that pair is read as one
   object under two codecs, not as two identities (ADR-2608148200).
2. **4 MiB cap.** Larger documents belong on the large-object plane.

## Verified against reality

The addressing is checked against objects that exist, not only against
itself:

- `sha256("hello world")` → `bafkreifzjut3te2nhyekklss27nh3k72ysco7y32koao5eei66wof36n5e`,
  the value IPFS itself publishes for that input.
- the live 816,065-byte `cloud.itonami.app` appview: fetched from
  `kotobase.net`, re-hashed, and the CID it is stored under reproduced exactly.

```bash
# 18 tests / 270 assertions, no network. The interpreter paths are not
# optional — see "The decision core" below for why the runner refuses to
# start without them.
kbb --backend sci --classpath src:test:resources:../kotoba-kir/src:../kotoba-hir/src \
    test/run_tests.cljk
```

## Runtime

Portable `.cljc`, ClojureScript/nbb first (that is where the appview build
steps run), JVM supported through the same source. The only platform-specific
namespace is `content-address.digest`.

## The decision core

The judgements — is this a raw CID, are these two CIDs one object, is the
archive going to refuse this — are written a second time in
[`kotoba/address_core.kotoba`](kotoba/address_core.kotoba) and shipped
compiled as `resources/content_address/address_core.kir.edn`.

They are decidable from a CID *string* and two integers, with no collections
and no capability, which is exactly what belongs in a decision core. The
octet arithmetic (base32, sha2-256, the multihash header) stays in
`core.cljc`, where collections belong.

Two implementations of one decision is a mirror, and a mirror is only honest
while something fails when the halves disagree:

```bash
# 18 tests / 270 assertions. Fails to LOAD without the interpreter,
# rather than quietly running the pure tests alone.
kbb --backend sci --classpath src:test:resources:../kotoba-kir/src:../kotoba-hir/src \
    test/run_tests.cljk

kbb -M:kir      # regenerate the artifact after editing the .kotoba
```

Checked by breaking it: `digest-start` 7 → 8, recompiled, 34 failures;
restored, 0. A parity test that has never been red has not been tested.

`core.cljc` still computes — it does not call the guest — because a runtime
dependency on the interpreter would land on every appview build step that
uses this library, and that ergonomics is what made it adoptable. The parity
test is what makes that safe, so it is not optional: it runs on the same
command as everything else.
