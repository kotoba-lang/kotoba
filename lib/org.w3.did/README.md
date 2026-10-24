# org-w3-did

`kotoba-lang/org-w3-did` is a small EDN-first DID library.

It keeps DID identifiers and DID Documents as ordinary Clojure data. The scope is
parsing, deterministic document construction, and local resolution for `did:key`
Ed25519 keys and `did:web` documents.

## Usage

```clojure
(require '[did.core :as did])

(did/parse "did:web:example.com:users:alice#keys-1")
;; => {:did "did:web:example.com:users:alice"
;;     :method "web"
;;     :method-id "example.com:users:alice"
;;     :fragment "keys-1"}

(did/did-web-document "example.com" {:path ["users" "alice"]})
;; => {:@context ["https://www.w3.org/ns/did/v1"]
;;     :id "did:web:example.com:users:alice"
;;     :verificationMethod [] ...}
```

## Scope

- DID / DID URL parsing
- DID Document EDN construction
- `did:key` Ed25519 document from multicodec 0xed01 public keys
- `did:web` id / well-known URL helpers

Out of scope: remote HTTP resolution, signing, verification, JSON-LD expansion,
and key derivation. Those belong in crypto-specific libraries such as
`kotoba-lang/ed25519`.

## Why only `did:key` and `did:web`

This is a deliberate split, not an unfinished one. The decision record is
**ADR-2608200400** in the superproject (`com-junkawasaki/root`); the summary:

| plane | method | what it answers |
|---|---|---|
| **identity** | `did:key` | who signs. Fixed for the life of the subject |
| **naming** | `did:web` | where to find a human-readable address. Holds no key |

`did:key` is the primitive identity of kotoba and kotobase because it is the only
DID method in which **the identifier *is* the verification material** rather than a
commitment to it. `did:cid`, `did:scid`, `did:webvh` and `did:webplus` are all
self-certifying, but their identifier is a *hash of a document that contains* the
key — so resolving them requires I/O. In `kotoba/pure` there is no ambient
authority, which makes that I/O a capability, which in turn makes every identity
check an effect (see ADR-2608160200 on when an Execution CID may be a memo key).

`did:web` is a **name**, not an identity (ADR-2608148200, ADR-2608039950). It never
carries a key here: `did:web:kotobase.net:tenant:<user>` and `…:org:<org>` identify
an account and an organisation, and the `did:key` in the same viewer is what signs.

### On the two-layer standards footing (measured 2026-08-20 — re-measure, don't quote)

The encoding this library implements and the method name it implements are on
**different tracks**, and it is worth keeping them apart:

- **Multikey — Ed25519 MUST start with the two-byte prefix `0xed01`** — is normative
  in **Controlled Identifiers v1.0, a W3C Recommendation since 2025-05-15**. That is
  what `did-key-document` / `public-key->did-key` implement, and it is REC-stable.
- **`did:key` itself is a W3C-CCG draft at v0.9**, is not in the DIF/ToIP Recommended
  DID Methods set, and is the input document for the *Ephemeral* category of the
  (still draft) W3C DID Methods WG charter — a category defined as key information
  *without key rotation*.

So: the bytes are standardised, the method label is not. Say "`did:key` plus a
rotation plane" when describing this outward; `did:key` alone reads as dev/test.

### What is intentionally elsewhere

| want | goes to | state |
|---|---|---|
| verifiable key rotation | `did:webvh` — DIF Recommended, v1.0 | repo `foundation-identity-didwebvh` named but **not created** |
| delegation | `kotoba-lang/org-biscuitsec` + `authority` | landed (ADR-2608180200) |
| content-addressed subject identity | `kotoba-lang/nekko` RID | landed; ≅ `did:cid` |
| signing / verification | `kotoba-lang/ed25519`, `org-chainagnostic-cacao` | landed |

`did:peer`, `did:jwk`, `did:pkh`, `did:plc` and `did:scid` are not implemented here
and there is no measured need for them yet. Adding one is a decision, not a gap —
record it before writing the parser.

## Test

```bash
kbb -M:test
```

## License

Apache-2.0
