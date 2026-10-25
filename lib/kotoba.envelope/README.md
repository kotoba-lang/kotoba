# envelope

**One object, one content key, many wrapped copies of it.**

The encryption envelope under [kotobase.net](https://kotobase.net)'s Drive and
Mail (ADR-2607263000 D3–D5, in `com-junkawasaki/root`). An object is encrypted
once, under a random 256-bit content key. That key is never stored — only
copies of it wrapped to each recipient's X25519 public key. **Sharing re-wraps
the key; it never re-encrypts the object.**

```clojure
(require '[envelope.seal :as seal] '[envelope.model :as m])

(-> (seal/seal-object "drv:abc" (map utf8 ["chunk 0" "chunk 1"])
                      [{:id "did:key:z6Mk…" :pub alice-x25519-pub}])
    (.then (fn [{:keys [envelope chunks]}]
             ;; `chunks` are ciphertext; `envelope` is safe to store on a
             ;; server that must not be able to read the object.
             (seal/share-with envelope (seal/entry-for envelope "did:key:z6Mk…")
                              alice-priv {:id "did:key:z6Mb…" :pub bob-pub}))))
```

## Two halves, split at the crypto boundary

| ns | runtime | role |
|---|---|---|
| `envelope.model` | portable `.cljc` | the shape and every decision that needs no crypto: nonce derivation, AAD, recipients, revoke, link grants |
| `envelope.seal` | ClojureScript, `Promise`-returning | the bytes: AES-256-GCM, X25519 + HKDF-SHA256 |
| `envelope.seal-jvm` | JVM, synchronous `.cljc` | the identical wire format via JCA and `kotoba-lang/org-signal` |
| `envelope.seal-sync` | ClojureScript on a Node-compatible host (kbb/nbb), synchronous | the identical wire format, classical **and** hybrid, for callers that cannot take a Promise |

`seal` is `.cljs` rather than `.cljc` because Web Crypto has no synchronous
API — the same reason `kotoba-lang/org-signal` keeps sibling JVM and CLJS
ratchets instead of one reader-conditional file. It runs where the object
actually is: a Cloudflare Worker and a browser.

`seal-sync` is `seal-jvm`'s surface, function for function, for JVM-free
command-line clients (kbb is nbb; `bonsai.private-repo` is the first caller),
plus the hybrid wraps `seal-jvm` cannot open. X25519 is org-signal's and
ML-KEM is `envelope.kem`'s — the module `envelope.qualify` measures, whose
corrupted-ciphertext check now has to be refused by this opener too. AES-GCM,
the HMAC under HKDF, and randomness are `node:crypto` (OpenSSL — the same
provider Web Crypto is on Node): org-signal has no synchronous HKDF and Web
Crypto no synchronous anything, and the portable alternatives are refused by
rules already written down (`kotoba-lang/security` keeps AEAD/HKDF
platform-native, and `org-nist-aes` / `org-ietf-x25519` say of themselves that
they are not constant-time). It asserts the same fixed chunk vector as the
other two backends, and its test seals on each backend and opens on the
other.

`seal-jvm` is the client backend for JVM desktop processes such as Cloud
Itonami. It uses only the JDK crypto provider plus the workspace-owned
`kotoba-lang/org-signal`; a fixed ciphertext vector is asserted in both test
suites so either runtime changing nonce, AAD, UTF-8, or GCM tag layout fails.

X25519 and HKDF come from **`kotoba-lang/org-signal`** (audited
`@noble/curves`; Web Crypto HMAC). This repo does not reimplement them — a
second X25519 in this workspace would be a second one to get wrong.

`envelope.kem` adds the post-quantum half (`@noble/post-quantum`'s ML-KEM-768,
FIPS 203) for the `:x25519+ml-kem-768` KEM. Its docstring records why it lives
here rather than in `org-signal` (which implements X3DH, not PQXDH), and that
consolidating the workspace's three thin ML-KEM bindings is an open
opportunity.

The split is not cosmetic: the rules that decide whether this is secure —
nonce uniqueness, what the AEAD binds, what a revoke does *not* accomplish —
all live in the pure half, so they are testable on every runtime this
workspace targets, without a crypto runtime. `chunk-nonce` and `chunk-aad`
are verified to agree byte-for-byte between the JVM and ClojureScript.

## What the construction actually promises

- **Nonces are derived, never stored.** `epoch (4 bytes BE) || chunk index
  (8 bytes BE)`. GCM's one unforgivable failure is nonce reuse under a key;
  a deterministic counter makes that a property you check by reading the
  code rather than a probability you argue about. Rewriting a chunk in place
  bumps the epoch, so the rewrite gets a nonce nothing under this key has
  used — `bump-epoch` records the old epoch per chunk so untouched chunks
  keep opening.
- **The AEAD binds position, object and length.** Chunk AAD is
  `kotoba/envelope|version|object-id|epoch|index|chunk-count`. Swapping two
  chunks, replaying an old one, moving a chunk between objects, or
  truncating the object all fail to open rather than opening as something
  plausible. Each of those is a test.
- **A wrap is bound to its object and recipient**, so a wrap harvested from
  one envelope cannot be pasted into another to forge access. Also a test.
- **Revocation is honest.** `m/revoke` returns `:requires-rotation? true`
  whenever the recipient was actually present. Deleting a wrap stops someone
  deriving the content key *again*; it does not make them forget one they
  already derived. A caller that ignores the flag has built revocation
  theatre.
- **Public links are recipients too** — a link is a keypair nobody is. The
  private half goes in the URL **fragment** (`#`), which browsers never send
  to the origin; the envelope keeps only the public half. Revoking a link
  deletes its entry, and that works precisely because the link holder only
  ever had the link key, not the content key.
- **A wrap can be post-quantum, and cannot be silently downgraded to one
  that is not.** `:x25519` wraps the content key to X25519 alone, so a wrap
  harvested today opens once a CRQC exists — and the wrap *is* the object's
  confidentiality. `:x25519+ml-kem-768` derives the wrap key by HKDF over
  **both** shared secrets, so an attacker has to break both; a hybrid is never
  weaker than the classical construction it extends. The KEM is bound into the
  wrap's AAD, so a classical wrap cannot be presented where a hybrid one was
  intended, and `unwrap-with` reads the construction off the entry rather than
  negotiating it — there is no fallback path, because a fallback is the
  downgrade. Each hybrid recipient costs 1088 bytes (the ML-KEM ciphertext).
  Tests cover a wrong X25519 half, a wrong ML-KEM half, and a substituted
  encapsulation, each of which must fail on its own.
- **Identical plaintext does not deduplicate.** The content key is fresh per
  object, so two seals of the same bytes are different ciphertext.
  ADR-2607263000 D4 chose that over convergent encryption, which would leak
  whether two users hold the same file. There is a test so the property is
  not lost by accident.

## Opening an envelope with a passkey

`envelope.passkey` turns a WebAuthn PRF output into a recipient.

**A passkey cannot decrypt.** WebAuthn has no decrypt operation; a passkey
signs. What it does have is the PRF extension, which returns the *same* 32
bytes for the same (credential, salt) — and that secret is the only thing an
authenticator will give you.

So the identity is not derived from it. Deriving an X25519 key straight from the
PRF output is shorter, and it welds that identity to one credential forever: lose
the passkey and the key is gone, and you can neither add a second passkey nor
rotate the first. Instead the identity is an ordinary random X25519 key, and the
PRF output wraps it. `kotoba-lang/webauthn`'s `prf-envelope` already describes
this shape with `:salt-ref` and `:wrapped-ref`.

```clojure
(require '[envelope.passkey :as pk] '[envelope.seal :as seal])

(def id (pk/generate-identity))                    ; random X25519, the real key
(pk/seal-identity id prf-output)                   ; -> Promise<wrap map>, store it
(pk/open-identity wrap prf-output)                 ; -> Promise<priv>, rejects on the wrong passkey

(seal/seal-object "obj-1" [bytes] [(pk/recipient did id)])
```

Two passkeys can wrap the same identity, and both open it — that is the property
the wrapped design buys, and the test that says so is what separates it from the
derived shortcut.

The browser call is not here. `navigator.credentials.get` and the PRF extension
belong to the host (`kotoba-lang/webauthn`'s `derive-prf!` port); this namespace
takes bytes and returns recipients, so it runs unchanged wherever the rest of
`envelope` does.

`seal/wrap-under-key` and `seal/unwrap-under-key` are the symmetric siblings of
`wrap-bytes`: not every secret arrives as a public key, and a PRF output is the
case that forced them. Both pass the secret through HKDF with a salt rather than
using it as an AES key directly, so one secret used for two purposes does not
produce one key.

## Not in scope

- **Filename and path metadata are not encrypted** by this library. Doing so
  makes an S3-compatible surface's keys opaque, which is a product decision
  (ADR-2607263000, open questions), not a crypto one.
- **No key storage, transport or identity.** Where a recipient's private key
  lives, and how a device gets one, is `kotoba-lang/org-signal` +
  ADR-2607022330 (key backup / device link) territory.
- **No chunking policy.** `chunk-count` says how many chunks a length makes;
  actually splitting, uploading and reassembling belongs to the Drive client.

## Qualifying the ML-KEM module

`kotoba.security.crypto-policy/evaluate-pq-provider` decides whether a
post-quantum provider counts, and it will not infer that from an algorithm
label or a version string: it wants a module digest it can bind to, known
answers, encapsulation and decapsulation shown separately, invalid
ciphertext rejected, and a module load that fails closed.

```sh
npm run qualify:ml-kem
```

`envelope.qualify` produces that evidence by running the module, and
produces none of it when it cannot run — an evidence map with fields
missing is refused by that evaluator, which is the point.

- The **known answers are not ours**. `test/vectors/ml-kem-768-known-answers.edn`
  is extracted from `kotoba-lang/security`, which generated them with
  BouncyCastle 1.81 from a seeded DRBG. A module checked against its own
  output agrees always; agreeing with a different implementation is the only
  result that means anything. They are copied rather than read across the
  checkout because a test whose input lives in a sibling repo reports a pass
  when the sibling is absent — `:source/sha256` is what makes the copy
  answerable.
- **Encapsulation has no known answer** — ML-KEM encapsulation is randomised.
  What is shown instead is that this module's encapsulation opens under the
  decapsulation key another implementation made.
- **The module alone cannot reject a corrupted ciphertext.** ML-KEM's
  implicit rejection returns a *different* shared secret rather than an
  error, so rejection is measured one layer up, where it actually happens:
  corrupt the encapsulation inside a real hybrid wrap and require the AEAD
  to refuse.
- `@noble/post-quantum` is pinned to an exact version rather than a range.
  A range makes the deployed provider unmeasured, and the digest binds to a
  module, not to a version. What the digest does **not** cover is
  `@noble/hashes` and `@noble/curves`, which `ml-kem.js` imports; those are
  covered only by the known-answer test, which cannot pass with a broken
  SHAKE.

`wrap-bytes-hybrid` / `unwrap-bytes-hybrid` are the hybrid siblings of
`wrap-bytes` / `unwrap-bytes`: same construction as `wrap-for-hybrid`, with
the AAD as a parameter. kotobase's recipient-bound disclosure
(ADR-2609061400) binds `binding(grant)`, a CID this repo cannot compute, and
a second hybrid wrap written to get a different AAD in is the drift
`wrap-bytes` was factored out to prevent. Which construction opens a wrap is
read off the wrap: neither opener will accept the other's output.

`envelope.sealed-key` frames one such wrap as one byte string — version,
ephemeral public key, ML-KEM ciphertext, IV, AEAD output — so a protocol
that has to *put* the wrap somewhere has an ordering both ends agree on
before either has done any crypto. Both ends live here on purpose: if the
key service and the query client each wrote their own framing, the first
disagreement between them would surface as an AEAD failure, which is what a
forged wrap looks like too. The recipient's own public keys are not carried;
they enter the KEM transcript instead, so the binding is cryptographic
rather than a field to compare.

## Where the recipient's own keys live — `envelope.keystore`

A wrapped key delivered to a hybrid recipient opens only if BOTH secrets are
present, so a store that holds one of them holds nothing usable.
`envelope.passkey` already answers this for the classical half — the identity
is an ordinary random X25519 key and a passkey's PRF output *wraps* it rather
than becoming it, so the identity outlives any one credential.
`envelope.keystore` is the same idea for a hybrid pair.

```clojure
(-> (keystore/generate-identity)
    (.then #(keystore/seal-record % prf-output salt))
    (.then store-it-somewhere))

;; later, as the :keys! port of kotoba-lang/ayatori's disclosure opener
(keystore/unlocker records prf-output)
```

What it stores is a **record**, not a key: public material, a status and two
wraps, which is safe on a server that must not be able to read anything. The
unlock secret is supplied per call and is never held.

**The fingerprint is derived, not assigned.** A record's identity is its
keys: `fingerprint` hashes the two public keys, and both wraps are sealed
with that fingerprint in their AAD. Relabelling a record or editing its
public material changes the AAD, so it stops opening — the binding between
"who this is" and "what opens it" is cryptographic rather than a field
somebody remembered to compare. A disclosure grant's `:recipient-key` should
be this value: the protocol requires the issuer to bind the recipient's
encryption-key fingerprint independently of anything the requester says, and
a derived one is what both sides compute from the same bytes.

Refusals, by name: an unknown record version, a `:key/status` that is
anything other than `:active` (including one this code has never heard of —
`kotoba.security.key-status` owns that vocabulary and the test iterates *its*
set), a stored name that is not what the stored public keys hash to, a wrong
unlock secret, and the two halves exchanged for one another. One consistency
check survives the unwrap: FIPS 203 puts the encapsulation key inside the
decapsulation key, so a recovered ML-KEM secret that does not match the
record's `:pq-pub` is refused. There is no equivalent for the X25519 half
without a scalar multiplication this repo does not expose, which is why the
AAD carries the fingerprint of both.

`unlocker` distinguishes absent from refused: an unknown fingerprint resolves
to `nil`, a present-but-revoked record *rejects*. "There is no such
recipient" and "that recipient's key is revoked" are different answers and
arrive differently.

## Test

```sh
npm install
kbb --backend sci --classpath "src:test:../org-signal/src:../security/src" \
    scripts/run-tests.cljk
```

91 tests / 249 assertions (measured 2026-10-07; 78 / 203 before
`envelope.seal-sync`), all against real Web
Crypto, real X25519 and real ML-KEM-768 — no fake ciphers. The negative
cases (wrong key, flipped bit, reordered chunks, truncation, relocated
chunk, pasted wrap, substituted encapsulation, wrong AAD, either KEM half
alone, revoked status, relabelled record) are the point; the round trip is
the easy part.

The runner has two floors, and the second was earned. Namespaces come from
disk, because a list falls behind the suite and reports the subset as a
pass. That is not enough: while `envelope.keystore-test` was being written,
seven of its twelve `deftest` forms were swallowed into a preceding form by
one unbalanced paren. The file parsed, the namespace loaded, the runner ran
what was left and printed `0 failures` — the suite total went up, just by
less than it should have. So every `(deftest` at the start of a line in a
test file must now correspond to a registered test var, and a mismatch exits
**2**: could-not-measure is neither a pass nor a failure. The JVM-only
`seal_jvm_test.cljc` is excluded by name with its reason, and the runner
refuses if that exclusion ever outlives its subject.

`../security/src` is on the path for `kotoba.security.crypto-policy` and
`kotoba.security.key-status`: the provider qualification is judged by that
evaluator, and the key statuses a store may unlock come from that vocabulary,
rather than by copies of either living here. It is declared in `deps.edn`
under the `:test` alias so the fleet gate builds the same classpath from the
same pins.

The npm packages are `dependencies`, not `devDependencies`, and that
distinction is load-bearing rather than cosmetic: `src/envelope/kem.cljk` and
`src/envelope/qualify.cljk` import `@noble/post-quantum` directly, so it is a
runtime dependency of those namespaces. The fleet gate runs `npm install
--omit=dev`, which — measured 2026-09-06 — installs nothing, **exits 0**, and
leaves the suite to die on `Cannot find module`. The gate script has a
function devoted to catching exactly that (`NPM-DEPS 0/0 present, 3
devDependencies omitted by --omit=dev`), which is how this was found before
the gate was registered rather than after.
