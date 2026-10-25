# nekko

*(旧 kotoba-rad — 2026-07-16 rename。根っこ＝sovereign identity/RID の根。namespaces も nekko.* に移行済み (2026-07-16))*

Sovereign repo identity, delegate authorization, and signed refs — the
"Radicle-equivalent" half of ADR-2607072200 (`kotoba-git-kotoba-rad-on-
kotobase-peer`, superproject `90-docs/adr/`). `kotoba-git` is the sibling
"git-equivalent" half (content-addressed blob/tree/commit objects).

## What this is

- **`kotoba-rad.identity`** — `genesis!`: an RID (repo identity) is the CID
  of its own genesis block `{did, created}`, using the same `io-ipld`
  DAG-CBOR content-addressing `kotoba-git` uses for objects (one CID scheme
  across both repos, rather than a separate ad-hoc implementation).

  > **This RID is `did:cid` in all but spelling** (measured 2026-08-20, ADR-2608200400).
  > `did:cid` — a DIF Recommended DID Method — uses `CIDv1(base32, JCS(seed document))`;
  > an RID is the CID of a DAG-CBOR genesis block. Same construction, different codec
  > and multibase. So the work of interoperating is a **mapping**, not a second
  > implementation, and every part it needs is already in the fleet
  > (`io-multiformats`, `org-ietf-jcs`, `io-ipfs`, `io-filecoin-signer`).
  >
  > It is also why an RID is **not** the identity that signs. The CID commits to a
  > document that contains a `did:key`; the `did:key` is what holds the key. Resolving
  > an RID needs I/O, so it cannot be the primitive identity of a `kotoba/pure` program
  > — the same reason `did:cid`, `did:scid` and `did:webvh` are not.
- **`kotoba-rad.journal`** — an append-only, hash-chained log of identity
  events, built directly on `kotoba-lang/chain`. `chain`'s single-parent,
  opaque-state design is exactly a linear identity journal (as opposed to
  `kotoba-git`'s commit DAG, which needs N parents for merges) — this repo
  does not reimplement chaining, it just instantiates one `chain` per RID.
- **`kotoba-rad.delegate`** — folds the journal into the current
  authorized-delegate set. The owner is always authorized; every
  `delegate-add`/`delegate-remove` entry must itself be signed by an
  *already*-authorized did:key (verified with real Ed25519, not assumed) —
  so authority can only be delegated forward from the genesis owner, never
  self-granted.
- **`kotoba-rad.sigref`** — signed attestations that `ref-name` currently
  points at `commit-cid` for a given `rid` (Radicle's `rad/sigrefs`
  equivalent), signed/verified with real Ed25519 over canonical CBOR.
- **`kotoba-rad.recipient-grant`** (R2, ADR-2606280300 'Private object
  store') — grant a repo's symmetric epoch key to a recipient's **X25519**
  public key (a key-agreement key, distinct from their Ed25519 signing
  did:key) via an ephemeral-static sealed box (ECDH → HKDF → AES-256-GCM).
  `rotate` mints a new epoch key and re-grants it to the *current* recipient
  set only — so **revocation is epoch rotation, not deletion of already
  distributed ciphertext** (that ADR's Security model exactly): a dropped
  recipient keeps the old-epoch ciphertext they already hold but gets no new
  grant. X25519 + AES-256-GCM are synchronous on both hosts (JCA on the JVM,
  node:crypto on nbb), cross-verified: a grant sealed on one host opens on
  the other.
- **`nekko.recipient-grant-async`** — the same grant for hosts whose only
  crypto is *asynchronous* SubtleCrypto: browsers, Cloudflare Workers, and
  node's WebCrypto. Every fn returns a `js/Promise`; the wire format is
  identical (same X25519 DER prefixes, the same `SHA-256(shared || info)` wrap
  key — not HKDF — and the same 12-byte zero iv with `ciphertext||tag`). It
  exists as a sibling rather than a branch because the sync namespace's
  primitives are synchronous by construction and `nekko.bytes` reaches for
  `js/Buffer` + node:crypto, neither of which a browser has; for that reason
  this namespace carries its own byte helpers and requires nothing.
  `test/nekko/recipient_grant_async_test.cljk` (`npm run test:async`, the
  first coverage of any kind over the :cljs branch) proves both directions
  under nbb — the one runtime with both backends live — and a
  WebCrypto-sealed fixture is frozen into the JVM suite so `kbb -M:test`
  guards the format too. Verified 2026-07-30 on all three hosts: JCA,
  node:crypto and WebCrypto open each other's grants.
- **`nekko.keyslot`** — wrap one long-lived secret under N independent *unlock
  factors*, so any one opens it and losing one loses nothing: a mailbox's
  X25519 private key held under one slot per enrolled WebAuthn PRF credential
  plus a recovery code (cloud-itonami ADR-0038). HKDF-SHA-256 per slot with a
  fresh random salt, AES-256-GCM with a fresh random iv, and the non-secret
  factor id bound in as `additionalData` so whoever *stores* slots cannot
  relabel or transplant one. **Client-only on purpose — there is no `.cljc`
  sibling and there should not be one**, because a server-side unwrap path is
  exactly the capability zero-access removes. Note the deliberate difference
  from `recipient-grant`: that one's zero iv is safe because its key is a
  single-use ephemeral ECDH output, whereas a keyslot key is derived from a
  long-lived factor secret and recurs on every rewrap, so copying the zero iv
  here would reuse (key, iv) and break GCM. A test asserts that two wraps of
  identical inputs differ.
- **`nekko.key-journal`** — a signed, hash-chained history of one mailbox's key
  events, so a server that swaps the published mailbox public key is *detected*
  rather than trusted (cloud-itonami ADR-0038's sharpest residual risk). One
  32-byte root secret, generated client-side and living only inside
  `nekko.keyslot` ciphertext, derives both halves by HKDF: the X25519 mailbox
  key and the Ed25519 seed that signs every entry. So any device that opens one
  keyslot derives the journal public key **itself** and verifies the chain from
  genesis — it never has to be told which signer to trust, which is exactly what
  a malicious server would want to tell it. The server holds no keyslot and so
  cannot produce an entry that verifies. `extends-pinned?` covers the other
  attack a forger-proof chain still allows: serving a *truncated* history to undo
  a revocation. Chaining and CIDs are `nekko.journal`/`chain.core`; this adds
  only the signature layer. Client-only on purpose, like `keyslot`. Ed25519 is
  `@noble/curves` rather than `ed25519.core`, whose cljs branch needs
  node:crypto and so cannot run in a browser. **Tested under real
  ClojureScript, not nbb** (`npm run test:cljs`): `chain.core`'s non-genesis
  commits encode `prev` as an `ipld` deftype whose field sci cannot read, so
  under nbb every commit after genesis throws — an nbb limitation, not a browser
  one, and the real consumer is a browser bundle anyway. That suite runs from a
  bare clone; getting there meant bumping all seven git pins, which were
  collectively stale enough that the git-dep path did not work at all under
  cljs while the west workspace did.
- **`nekko.recovery-code`** — the keyslot factor a person keeps on paper: 128
  bits as 26 Crockford base32 characters plus a check character, grouped in
  fives. Crockford because it is built for transcription — I, L and O are not
  in the alphabet and read back as 1, 1 and 0, so the classic confusions decode
  correctly instead of failing. The check character exists for a specific
  cruelty a keyslot would otherwise inflict: a slot answers only "did this open
  it", identically for a wrong code and a mistyped one, so without a checksum a
  fat-fingered character is indistinguishable from "your mail is gone". It is
  a position-weighted sum mod 37, weighted so transposing two characters does
  not cancel out. Portable `.cljc` with no host crypto — randomness is injected
  by the caller, so the JVM and the browser produce the same code and the tests
  are deterministic.
- **`kotoba-rad.private-object`** (R2) — the object envelope: AES-256-GCM a
  git object's bytes under the epoch key, so the **replicated blob is
  ciphertext** (replication id = ciphertext CID) while the plaintext CID is
  kept as authority-scoped verification metadata (`open` checks the recovered
  bytes hash back to it). A peer without an epoch-key grant can replicate the
  ciphertext but never read it. This is R2's classical confidentiality; the
  R4 PQ target (hybrid X25519+ML-KEM) layers over the same grant shape.
- **`nekko.private-object-async`** — the same envelope for hosts whose only
  crypto is asynchronous SubtleCrypto, which for cloud-itonami means the
  Cloudflare Email Worker: the one place a message is ever in the clear. Same
  `{:epoch :plaintext-cid :iv :ct}` byte for byte, so an object sealed by the
  Worker opens on the JVM drain and vice versa — proven both directions under
  nbb rather than assumed. `plaintext-cid` earns its keep here: the GCM tag
  proves nobody edited the ciphertext, but proves nothing about which plaintext
  the sealer *meant*, and anyone holding the content key can produce a
  perfectly valid envelope around a message they wrote. A test does exactly
  that and asserts the refusal.
- **`kotoba-rad.bytes`** — portable byte/hex/AES helpers (JVM byte-array /
  nbb Uint8Array), the R2 crypto's host seam.
- **`kotoba-rad.push-gate`** — `authorize-push?`, a pure predicate
  reimplementing what the deleted Rust `kotoba-git`'s `push_gate`/
  `RadRegistry` used to enforce server-side: a proposed ref update is
  authorized only if its sigref's fields match, its signature verifies, and
  its signer is currently an authorized delegate.
- **`kotoba-rad.announce`** — `sign-announce-fn`/`verify-announce-fn`,
  adapters plugging straight into `kotoba-lang/p2p`'s pluggable
  `:sign-announce`/`:verify-announce?` `new-node` hooks. A p2p head-announce
  (`{:graph :head-cid :seq ...}`) is exactly a sigref shape (ref-name =
  graph, commit = head-cid, ts = seq), so no new signing primitive was
  needed — only this adapter. Neither repo depends on the other; they
  compose through p2p's documented plain-map message shape, the same way
  `kotoba-git`/`kotoba-rad` compose with each other.
- **`nekko.biscuit-delegate`** + **`nekko.push-gate/authorize-push-biscuit`**
  — a second, journal-free authorization scheme: the owner signs a Biscuit
  (`kotoba-lang/org-biscuitsec`) rooted at the owner's did:key, granting push
  scopes (`push-resource` / `push-resource-wildcard`, parsed by the
  `kotoba-lang/authority` lattice) and naming the delegate's did as the only
  key that may append. The delegate presents it with a sigref, or attenuates
  it: narrower scopes, an earlier expiry, and — once — a `holder`. A token
  addressed to one holder is never re-addressed (`:holder-readdressed`), a
  block claiming more than its parent refuses the token
  (`:escalation-attempted`), an un-addressed token pushes nothing
  (`:holder-absent`), and `:now` is required (no clock is a denial). Every
  refusal returns its reason. Sub-delegation is: owner grants un-addressed to
  A's key, A narrows and addresses it to B.
  Until 2026-09-24 this was a CACAO chain (`cacao-delegate`,
  `cacao.core/verify-chain`). Superproject adr-2609241800 ended CACAO as a
  grant format — it is accepted only where Authn exchanges it for a session —
  so the CACAO predicates are gone and a CACAO presented at this gate is
  refused as `:cacao-not-accepted`.
  This is a different trust model from `nekko.delegate`, not a replacement —
  the journal is a shared, queryable ledger of who's *currently* authorized
  (supports revocation); a Biscuit is a capability the holder carries
  themselves (no revocation beyond its expiry, but no journal lookup either).
- **`kotoba-rad.canonical`** — threshold synthesis over independently valid
  sigrefs. Duplicate votes by one delegate count once; invalid or unauthorized
  signatures are ignored; different commits both reaching quorum is an
  explicit split-quorum error rather than an arrival-order choice.
- **`nekko.ref-event`** — the Datom-authoritative bridge: signs and admits
  causal peer-ref events carrying `old`, `new`, `prev`, `seq`, and the Git
  closure manifest. Each DID/ref namespace advances independently; admission
  verifies signature, delegate membership, contiguous history, old-target
  continuity, and an injected bonsai closure check before projection.
- **`nekko.canonical-projection`** — materializes canonical refs from current
  peer namespaces and delegate threshold. Canonical, unresolved, and split-
  quorum outcomes produce deterministic IPLD receipts containing every input
  event CID; network arrival order is never a tie-breaker.

`kotoba-rad` only ever deals in plain CID strings for refs/commits (never a
`kotoba-git` object directly), so the two repos stay decoupled — either can
evolve independently, and `authorize-push?` can gate any content-addressed
system's ref updates, not just `kotoba-git`'s.

## What this deliberately is NOT (yet)

- **No real transport for replication.** `kotoba-rad.announce` +
  `kotoba-lang/p2p`'s `:sign-announce`/`:verify-announce?` hooks give
  signed/verified head announces, and this is now verified end-to-end for
  real (not just unit-tested in isolation): a delegate signing a real
  2-node `chain.core` history via these hooks converges the receiver
  (bitswap/hydrate actually ran) to the signed head, and the receiver
  correctly rejects a real, valid, further-ahead but *unsigned* announce
  from the same peer. Getting there required fixing a genuine classpath
  conflict — `kotoba-lang/p2p` pinned `chain` at a pre-rename SHA
  (`commit-dag.core`) that broke the moment a real application also
  depended on `kotoba-rad` (pinned at a post-rename SHA); p2p now tracks
  the same SHA this repo does (`kotoba-lang/p2p` PR #2). What's still
  missing is a real transport: p2p only ships an in-memory loopback
  reference transport; a real QUIC/WebRTC/WebTransport adapter is a host
  follow-up, not attempted here or there.
- **No token revocation.** `nekko.biscuit-delegate` covers granting and
  verifying delegated push tokens (including sub-delegation and scope-
  escalation refusal), but a token is only invalidated by its own
  `before` — there's no equivalent of `nekko.delegate/remove-delegate!`
  for a token holder (short-lived tokens re-issued on a schedule would be
  the usual fix; not built here).
- **No richer protected-branch policy beyond fast-forward.**
  `authorize-push?`/`authorize-push-biscuit` check *who* signed, not
  policy about *what* ref updates are allowed once someone's authorized —
  `kotoba-git.ref-policy/set-ref-guarded!` now composes identity + the
  fast-forward-only shape check into one call (an injected `authorized?`
  predicate, no dependency from `kotoba-git` back onto this repo), but
  nothing yet adds richer policy on top (required reviewers, branch
  naming rules, etc.).
- **No Git remote helper yet.** The signed peer-ref and canonical Datom core is
  implemented, but `git-remote-kotoba` ref-list/fetch/push and pack negotiation
  remain the G3 application/CLI layer.

## Usage

```clojure
(require '[kotoba-rad.identity :as identity]
         '[kotoba-rad.delegate :as delegate]
         '[kotoba-rad.sigref :as sigref]
         '[kotoba-rad.push-gate :as push-gate]
         '[ed25519.core :as ed])

(def store (atom {}))
(def put! (fn [cid bytes] (swap! store assoc cid bytes)))
(def get-fn (fn [cid] (get @store cid)))

(def owner-seed (byte-array 32 (byte 1))) ; real callers: securely-random 32 bytes
(def owner-did (ed/did-key-from-seed owner-seed))
(def rid (identity/genesis! put! owner-did (System/currentTimeMillis)))

;; delegate a collaborator
(def collab-seed (byte-array 32 (byte 2)))
(def collab-did (ed/did-key-from-seed collab-seed))
(def journal-head (delegate/add-delegate! put! get-fn nil owner-did owner-seed collab-did
                                           (System/currentTimeMillis)))

;; the collaborator signs a ref update and it's authorized
(def sr (sigref/sign collab-seed rid "refs/heads/main" "commit-cid-here"
                      (System/currentTimeMillis)))
(push-gate/authorize-push? get-fn journal-head owner-did rid "refs/heads/main"
                            "commit-cid-here" sr) ;=> true

;; wiring signed head-announces into a kotoba-lang/p2p node (verified
;; end-to-end: a signed announce converges the receiver for real; an
;; unsigned one is rejected even when it's a real, valid, further-ahead head):
(require '[kotoba-rad.announce :as announce]
         '[kotoba.p2p.sync :as sync])
(sync/new-node "my-peer" store
               {:sign-announce (announce/sign-announce-fn owner-seed rid)
                :verify-announce? (announce/verify-announce-fn get-fn journal-head
                                                                owner-did rid)})

;; journal-free authorization via a Biscuit rooted at the owner instead:
(require '[nekko.biscuit-delegate :as bd])
(def grant (bd/grant owner-seed {:resources [(bd/push-resource-wildcard rid)]
                                 :next-did collab-did :holder collab-did
                                 :expires "2099-01-01T00:00:00Z"}))
(def sr2 (sigref/sign collab-seed rid "refs/heads/main" "commit-cid-here" 2))
(push-gate/authorize-push-biscuit grant owner-did rid "refs/heads/main"
                                  "commit-cid-here" sr2 {:now "2026-09-24T00:00:00Z"})
;=> {:allowed? true :holder collab-did}, no journal consulted
```

## Note on ClojureScript

`ed25519.core` and (transitively) parts of this repo's crypto-touching
namespaces (`delegate`, `sigref`, `push-gate`, `announce`, `biscuit-delegate`) are Clojure/JVM-only today —
the upstream `org-ietf-ed25519` repo has no `:cljs` branch. `.cljc` file
extensions here match sibling convention, but only `kbb -M:test`
actually exercises this repo; there is no ClojureScript CI job.

## Testing

```
kbb -M:test          # against the pinned :git/sha deps
kbb -M:local:test    # against sibling checkouts in ../ (same-monorepo dev)
```
