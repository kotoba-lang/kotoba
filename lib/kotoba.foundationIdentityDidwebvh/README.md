# foundation-identity-didwebvh

**`did:webvh` v1.0** — the DID method that makes multi-party control a *method
rule* instead of an operational promise. Portable `.cljc`; no HTTP, no clock,
no key material.

The name is the origin plane: the specification's authority is
[identity.foundation](https://identity.foundation/didwebvh/v1.0/), so
`identity.foundation` reversed is `foundation-identity`, and the subject is
`didwebvh`. (Formerly `did:tdw`.)

## Why this exists, in one paragraph

`did:key` is this workspace's primitive identity and stays that way
(root ADR-2608200400): it is the only method whose identifier *is* the
verification material, so resolving it costs no I/O. What it cannot do is
rotate, revoke, or record who approved a change. `did:webvh` is the other half
— a hash-chained, signed log with pre-rotation and an **m-of-n witness
threshold that resolvers enforce**. Identity stays a key; naming and rotation
move here.

## The one thing to understand before using it

**`updateKeys` is not a multisig.** Several keys may be listed and *any one of
them* signs a valid entry — the list is a set of equals. There is a test that
demonstrates exactly this, on purpose:

```clojure
(deftest any-single-update-key-signs-a-valid-entry ...)
```

`m-of-n` lives in the `witness` parameter, and it is a resolver rule:

```clojure
{"threshold" 3
 "witnesses" [{"id" "did:key:z…Security"}
              {"id" "did:key:z…Legal"}
              {"id" "did:key:z…Operations"}
              {"id" "did:key:z…Auditor"}
              {"id" "did:key:z…Recovery"}]}
```

Fewer than `threshold` weight of valid witness proofs and the update does not
resolve. `weight` defaults to 1, so the shape above is plain 3-of-5.

## Namespaces

| ns | what it owns |
|---|---|
| `didwebvh.hash` | the ONE hash the method uses, over three different inputs |
| `didwebvh.did` | the DID string and its transformation into two URLs |
| `didwebvh.params` | parameter inheritance, pre-rotation, portability |
| `didwebvh.proof` | `eddsa-jcs-2022` as the method constrains it |
| `didwebvh.witness` | the threshold, and `did-witness.json` |
| `didwebvh.entry` | building and signing one log entry |
| `didwebvh.log` | verifying a whole log — which is what resolution is |
| `didwebvh.signer` | an in-process signer, for development and tests only |

## Usage

```clojure
(require '[didwebvh.entry :as entry]
         '[didwebvh.hash :as h]
         '[didwebvh.log :as log]
         '[didwebvh.signer :as signer])

(def update-key (signer/from-seed my-seed))       ; or an HSM: {:multikey :sign-fn}
(def next-key   (signer/from-seed my-next-seed))

(def genesis
  (-> (entry/genesis
       {:version-time "2026-08-20T00:00:00Z"
        :parameters {"method" h/method-1-0
                     "scid" h/scid-placeholder          ; the literal {SCID}
                     "updateKeys" [(:multikey update-key)]
                     "nextKeyHashes" [(h/key-hash (:multikey next-key))]
                     "portable" true
                     "witness" {"threshold" 3 "witnesses" [...]}}
        :state {"@context" ["https://www.w3.org/ns/did/v1"]
                "id" (str "did:webvh:" h/scid-placeholder ":did.example.com")}})
      (entry/sign update-key)))

;; each witness, wherever it lives:
(entry/witness-proof (get genesis "versionId") their-signer)

(log/verify [genesis] {:witness-file [{"versionId" (get genesis "versionId")
                                       "proof" [p1 p2 p3]}]
                       :now (quot (System/currentTimeMillis) 1000)})
;; => {:ok? true :did "did:webvh:Qm…:did.example.com" :scid "Qm…" :state {…}}
```

## Three details that are easy to get silently wrong

1. **The entry hash and the proof sign DIFFERENT documents.** The hash is taken
   over the entry with `versionId` set to the *previous* versionId (the SCID,
   for the first entry). The proof is over the entry with its *own final*
   versionId. `entry/hash-input` and `entry/proof-input` are named so the
   difference is visible at every call site.
2. **`nextKeyHashes` hashes the multikey STRING**, not the key bytes it
   encodes. Hashing the decoded bytes yields a stable, plausible, wrong value —
   every pre-rotation check fails and both sides look like well-formed hashes.
3. **The authorized signer of an entry is not that entry's `updateKeys`.**
   Without pre-rotation it is the *previous* entry's set (rotation is an act of
   the current holder). With pre-rotation it is this entry's own set, which is
   admissible only because the previous entry committed to their hashes.

## Signing where the key must not be in this process

`entry/sign-async` and `entry/witness-proof-async` (ClojureScript only) take
a signer whose `sign-fn` returns a Promise of the signature — WebCrypto's
`crypto.subtle.sign` over a non-extractable key, a KMS, an HSM behind a
call. They produce byte-for-byte the entry `sign` produces with the same key
(Ed25519 is deterministic; `test/didwebvh/async_test.cljk` asserts the
equality against Node's WebCrypto). A Cloudflare Worker uses this path: the
pure signer costs about half a second per signature there, WebCrypto
milliseconds, and the private key never leaves the platform.

## Verifying where the Ed25519 must not be in this process

`log/verify` is one pure loop, and it cannot await anything: each entry has to
be decided before the next entry's authorized keys are known. So the
asynchronous path answers the same questions twice.

```clojure
(require '[didwebvh.log :as log] '[didwebvh.subtle :as subtle])

(log/verify-async entries {:witness-file wf :expect-did did :now now
                           :verify-signature-async subtle/verify-signature})
;; => Promise of exactly what `verify` returns
```

`verify-async` runs `verify` once with a collector that says **true** to every
signature, which can only let the loop travel further than the real answers
would; the questions it gathers are therefore a superset of the ones that
matter. It answers them all in parallel, then runs the identical loop again
with the real verdicts. Running the same code path both times is what keeps
the two from drifting; the price is one extra pass of JCS and SHA-256, which
is microseconds beside the Ed25519 it removes. In a Worker that is a few
milliseconds per signature instead of a few hundred.

Every check except the signature is arithmetic on the document, so
`:verify-signature` — `(fn [public-key hash-data signature] -> boolean)` — is
the only seam this needs, and `proof/verify`, `witness/verify` and `verify`
all take it. A memo table, a counter or a platform verifier substitutes there.

**A verifier that could not run has not decided that a signature is bad.**
`didwebvh.subtle` maps no error to `false`, and `verify-async` rejects rather
than returning `{:ok? false}`, because reporting a valid log as forged
because Ed25519 was unavailable is the worse failure of the two. Callers must
distinguish a rejected promise from an `{:ok? false}` result.

## What this library does NOT do

- **No fetching.** The log, the witness file and `now` are arguments. That is
  what lets the same code run in a resolver, in a CI gate, and in a guest with
  no network.
- **No key custody.** `entry/sign` takes `{:multikey :sign-fn}`, so an HSM, a
  KMS or a threshold signer substitutes without this library holding a seed.
  `didwebvh.signer` is the in-process implementation and is the wrong one for
  an organization root key.
- **No IDNA2008.** A non-ASCII domain is *refused*, not punycoded. An
  approximately-correct IDNA implementation maps two names onto one URL, and
  the failure surfaces as somebody else's DID document. Callers hold the
  A-label.
- **No JSON I/O.** Entries are Clojure data with string keys, which is what JCS
  canonicalization consumes. Reading and writing `did.jsonl` belongs to the
  host.

## Cryptography

`eddsa-jcs-2022` only — the sole cryptosuite v1.0 admits — and it comes from
`kotoba-lang/org-w3-vc-data-integrity`, which implements W3C vc-di-eddsa
section by section. SHA-256 only (multihash `0x12`), read off the multihash
prefix rather than assumed.

## Test — on both runtimes, because `.cljc` is a claim about two

```bash
kbb -M:test          # JVM  (or -M:dev:test against sibling west checkouts)
npm install && npm run test:nbb   # ClojureScript, via nbb
```

25 tests, 59 assertions, identical on both. Every negative breaks exactly one
rule and re-runs the positive unbroken; the suite has been mutation-tested
(disable the witness threshold, the pre-rotation commitment, or the
portability check, and only the tests naming those rules go red).

**Running the second runtime found two real bugs the first could not.** Both
primitives branch at the reader — `multiformats.core/sha256` is MessageDigest
on the JVM and @noble/hashes in JS; `ed25519.core` is JCA and node:crypto — and
so does character handling. `(int c)` is a code point on the JVM and a numeric
coercion in ClojureScript, so `(int "3")` is 3 and `(int "a")` is 0. Under cljs
that made percent-decoding produce garbage, and made `ascii?` — the guard that
REFUSES a non-ASCII domain rather than punycoding it wrongly — answer true for
every input, silently. A refusal that cannot fire looks exactly like an input
that passed.

## License

Apache-2.0
