# Chain-agnostic CACAO and SIWE

[![CI](https://github.com/kotoba-lang/cacao/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/cacao/actions/workflows/ci.yml)

Two self-custodied authentication/capability protocols live here:

- `cacao.*`: CAIP-122-shaped CACAO mint and verify for `did:key` / Ed25519.
- `siwe.*`: strict EIP-4361 Sign-In with Ethereum for EOA accounts, using the
  EIP-191 personal-sign envelope, Keccak-256, secp256k1 recovery and EIP-55
  addresses.

They intentionally share a repository, not a signature format. The historical
CACAO plaintext resembles SIWE but is Ed25519-signed and is not an Ethereum
wallet signature. `siwe.*` is the interoperable Ethereum path.

## EIP-4361 SIWE (`siwe.core`, `siwe.edge`)

This is a first-party protocol implementation rather than a wrapper around a
JavaScript SIWE package:

- `siwe.core` parses and renders the EIP-4361 ABNF, enforces bounded canonical
  LF-only messages, and checks relying-party `scheme`, `domain`, `URI`, `nonce`
  and chain bindings.
- `siwe.edge` implements ERC-191 hashing, low-S secp256k1 public-key recovery,
  EIP-55 checksumming and the issued/not-before/expiration window.
- Successful verification yields a chain-bound
  `did:pkh:eip155:<chain-id>:<address>` principal. Sessions bind to that address,
  not ENS or another mutable resolution.

The only cryptographic dependencies are `@noble/curves` and `@noble/hashes`.
They supply curve and hash primitives; the message grammar and relying-party
policy are implemented here. Runtime consumers must install the exact versions
listed in `package.json`.

The current verifier is explicitly **EOA-only**. A claimed smart-contract wallet
does not silently fall back to EOA recovery. A host that supports contract
accounts must add a chain-specific ERC-1271 `isValidSignature` path and define
session invalidation for contract state changes.

```clojure
(require '[siwe.core :as siwe]
         '[siwe.edge :as siwe-edge])

(def plaintext
  (siwe/format-message
   {:scheme "https"
    :domain "auth.example.com"
    :address "0x..."
    :statement "Sign in. This request does not send a transaction."
    :uri "https://auth.example.com/sign-in"
    :version "1"
    :chain-id "1"
    :nonce "A1b2C3d4E5f6"
    :issued-at "2026-08-26T03:00:00Z"
    :expiration-time "2026-08-26T03:05:00Z"}))

(siwe-edge/verify plaintext "0x<r-s-v>"
                  {:scheme "https"
                   :domain "auth.example.com"
                   :uri "https://auth.example.com/sign-in"
                   :nonce "A1b2C3d4E5f6"
                   :chain-ids #{"1"}})
```

Run `kbb -M:test` for the portable grammar suite and
`npm run test:siwe-edge` for real ERC-191/secp256k1 recovery.

## CACAO (`cacao.*`)

A CACAO is a self-sovereign, signed, expiring capability carrying an issuer
DID, an audience, a nonce/expiry and a `resources` grant, serialized as CBOR
(`{h,p,s}`) and Ed25519-signed. It's the **no-server-key** authorization for
kotoba / kotobase (datom-transact leashes, `kotobase:pin`, …): minted in the
holder's OWN runtime, presented as an opaque `cacao_b64`, never a platform key.

```clojure
(require '[cacao.core :as cacao])

(def c (cacao/mint
         {:seed seed-bytes                 ; raw 32-byte Ed25519 seed; iss = its did:key
          :aud "did:key:zNODE"
          :iat "2026-06-27T00:00:00Z" :exp "2026-07-27T00:00:00Z" :nonce "n1"
          :resources ["kotoba://can/kotobase:pin" "kotoba://graph/did:key:z…"]}))
;; => {:cacao-b64 "…" :iss "did:key:z6Mk…" :siwe "…"}

(cacao/verify (:cacao-b64 c))      ;=> {:valid? true :iss "did:key:z6Mk…" :payload {…}}
(cacao/auth-header c)              ;=> {:authorization "CACAO …" :x-kotoba-did "did:key:z6Mk…"}
```

- **`mint`** derives `iss` from the seed (issuer binding — you never pass it),
  builds the canonical SIWE plaintext, signs it, and emits the CBOR CACAO. The
  `p` field order is signature-significant, so the CBOR is order-preserving.
- **`verify`** decodes, reconstructs the SIWE plaintext, and checks the EdDSA
  signature under the issuer did:key. Exception-safe — malformed input → `{:valid? false}`.
- **`auth-header`** gives the `Authorization: CACAO …` + `x-kotoba-did` headers.

## Nonce-replay protection — `:nonce-store`

`mint` embeds a `nonce`, but a valid, unexpired CACAO captured anywhere (logs,
network transit, a compromised intermediate) can otherwise be replayed
verbatim until its `exp`. `verify`/`verify-chain` accept an optional
`:nonce-store` — a `NonceStore` (a one-method protocol: atomic
`check-and-record!`) — that rejects a CACAO whose `[iss nonce]` has already
been seen:

```clojure
(def store (cacao/fresh-nonce-store))     ; an atom over a set of [iss nonce]

(cacao/verify cacao-b64 {:nonce-store store})  ;=> {:valid? true ...}
(cacao/verify cacao-b64 {:nonce-store store})  ;=> {:valid? false ...}  ; replay
```

`fresh-nonce-store` gives a plain, in-process atom (thread-safe, not
persisted). **When `:nonce-store` is omitted, `verify`/`verify-chain`
synthesize a throwaway store for that one call** — this keeps the no-store
arity crash-free and (for `verify-chain`) still catches two links of the
*same* chain sharing a nonce, but it provides **no protection against the
same CACAO being replayed across separate calls** — there is nothing for a
brand-new, discarded-on-return store to have seen before. Real cross-call
protection requires the caller to retain a store (module-level for a
long-running process, or a durable `NonceStore` impl — e.g. wrapping Redis or
a DB row with a `UNIQUE` constraint — for cross-process/cross-restart
protection) and pass it in explicitly on every call. **This library only
defines the check/record contract; where (if anywhere) it's persisted is
entirely the host's decision** — callers that currently omit `:nonce-store`
(e.g. `kotoba-lang/kotoba`'s `launcher.clj`) get no replay protection until
they're updated to supply one.

The replay key is always `[iss nonce]`, never the bare nonce string, because
a nonce is only meaningful scoped to the issuer that chose it — two
independent issuers coincidentally minting with the same nonce string is not
a replay.

## Delegation chains — `verify-chain`

`verify-chain` verifies an ORDERED delegation chain — a vector of `cacao_b64`
strings, root first, leaf last. Each link is a CACAO whose `aud` names the
delegate; that delegate re-issues the next link with its own key:

```clojure
(cacao/verify-chain [root-b64 mid-b64 leaf-b64] {:now "2026-07-02T00:00:00Z"})
;; => {:chain/valid? true
;;     :chain/problems []
;;     :chain/root-iss "did:key:z6Mk…"        ; root issuer (the delegating authority)
;;     :chain/holder "did:key:z6Mk…"          ; leaf aud (who may present the chain)
;;     :chain/resources #{"kotoba://cap/host/ledger-append/ledger:main"}
;;     :chain/expires "2026-07-10T00:00:00Z"  ; min exp across the chain
;;     :chain/depth 3}
```

Chain validity requires, per link and per parent→child pair:

- **signature**: every link verifies under its own issuer did:key (`verify`);
- **linkage**: child `iss` == parent payload `aud` — the delegate re-issues;
- **attenuation**: child `resources` ⊆ parent `resources` under `covers?` —
  exact string match, or a parent trailing-`*` wildcard
  (`kotoba://cap/<kind>/*` covers `kotoba://cap/<kind>/<r>`). A child may only
  narrow, never escalate;
- **expiry ordering**: child `exp` <= parent `exp` when both are present;
- **freshness** (optional `:now`): every link satisfies `iat <= now < exp`
  (each bound enforced when the field is present), so expired or
  not-yet-valid links reject the chain.

`verify-chain` also accepts `:nonce-store` (see above); every link's
`[iss nonce]` is checked against the SAME store instance for that one call,
so two links of the same chain sharing a nonce are rejected too, not only
replay of the whole chain across separate `verify-chain` calls.

On failure the result is `{:chain/valid? false :chain/problems [...]}` with
per-link problem maps (`:chain/invalid-signature`, `:chain/broken-linkage`,
`:chain/resource-escalation`, `:chain/expiry-extended`, `:chain/expired`,
`:chain/not-yet-valid`, `:chain/nonce-replay`, `:chain/malformed-input`). Malformed input never
throws. `:chain/resources` is the LEAF's effective resource set — the
narrowest scope in the chain — which downstream (crypto-free) layers such as
`kotoba.lang.capability-cacao` map to capability grants.

Built on **com-junkawasaki/ed25519-clj** (sign / did:key) +
**com-junkawasaki/dag-cbor-clj** (order-preserving CBOR). No native deps,
babashka-friendly.

## `kotoba` CLI — wallet-first ID / CACAO

A tiny CLI (`bin/kotoba`, or `kbb -M -m cacao.cli …`) over the identity
stack. Pure argument handling lives in `src/cacao/cli.cljk` (portable `.cljc`);
all crypto + IO (SecureRandom, base64, `java.time` instants, and the `ed25519` /
`cacao` requires) sits behind `#?(:clj …)`. JCA supplies Ed25519 sign/verify and
`ed25519.core` derives the public key in pure Clojure, so there is no native
crypto dependency.

The default public identity path starts from the user's existing wallet. It
derives a chain-bound `did:pkh` from the public address, with Base mainnet as
the default chain. The CLI never requests a wallet private key; SIWE proves
control when entering a relying service.

```bash
$ bin/kotoba id --address 0xA00366234D29d4F882088048c0B2fa0dB7302D4E
did:pkh:eip155:8453:0xa00366234d29d4f882088048c0b2fa0db7302d4e
```

The older `seed`, `did`, and Ed25519 CACAO commands remain available for
internal actors and compatibility, but they are no longer presented as the
human login default.

> `kbb -M:kotoba …` is **unavailable**. babashka was retired as this workspace's
> script host (ADR-2607173000), and that conversion also deleted the `bb.edn`
> which supplied this CLI's deps and source paths; `scripts/tasks.edn` was left
> a literal empty registry (ADR-2608131600). `bin/kotoba` itself exec'd
> `kbb -m cacao.cli` until 2026-08-13 and now execs `kbb -M -m cacao.cli`;
> a seed → `did:key:z6Mk…` round trip through it was verified that day.

```bash
# 1. Mint a fresh Ed25519 seed. THIS IS SECRET — the stderr warning tells you so;
#    only the base64 seed goes to stdout. Store it safely, never commit it.
$ bin/kotoba seed
# SECRET Ed25519 seed — store it safely; anyone with it IS you.
# Its public did:key:  did:key:z6Mk…
AAECAwQF…=

# 2. Derive the public did:key from a seed (safe to publish).
$ bin/kotoba did --seed "AAECAwQF…="
did:key:z6MkehRgf7yJbgaGfYsdoAsKdBPE3dj2CYhowQdcjqSJgvVd

# 3. Mint a CACAO (iss is DERIVED from the seed; iat=now, exp=now+ttl).
$ bin/kotoba cacao --seed "AAECAwQF…=" --aud did:key:zNODE \
    --resource "kotoba://can/kotobase:pin" --ttl-h 24 --nonce n1
# minted CACAO — iss did:key:z6Mk…
#   aud=did:key:zNODE exp=2026-07-03T00:00:00Z resources=["kotoba://can/kotobase:pin"]
<cacao_b64 on stdout>
```

`--resource` is repeatable; `--ttl-h` defaults to 24; `--nonce` defaults to
random. `bin/kotoba help` prints full usage.

## Edge namespaces (`cacao.edge.*`, CLJS-only)

`cacao.core` is portable `.cljc`, but its `:cljs` branch targets **Node**
(`js/Buffer`, `ed25519.core`'s synchronous `node:crypto`). A Cloudflare
Workers isolate has neither, so a Worker cannot use it. `cacao.edge.*` is the
Worker-native half — WebCrypto (`crypto.subtle` Ed25519), zero npm, with
hand-ported base58btc and definite-length CBOR because those have no WebCrypto
equivalent:

| ns | role |
|---|---|
| `cacao.edge.verify` | verify a presented CACAO (signature + temporal window). Returns a Promise. |
| `cacao.edge.mint` | mint a CACAO from a `sign-fn` (msg-bytes → Promise\<sig-bytes\>), for the WebAuthn-passkey → server-held did:key bridge. Returns a Promise. |
| `cacao.edge.base58` / `cacao.edge.cbor` | the wire pieces both of the above need. |

Both halves produce and accept the same wire format — a CACAO minted on the
JVM by `cacao.core/mint` verifies at the edge and vice versa
(`test/edge_smoke.cljk` covers the edge round trip; run it with
`kbb --backend sci --classpath src:test test/edge_smoke.cljk` on Node ≥ 20).

A CACAO minted by `cacao.edge.mint` is **server-custodied, passkey-gated** —
not a non-custodial wallet. `cacao.edge.verify` cannot tell the two apart
(that is the point: the API surface needs no changes), so the custody model
must be documented by whoever mints, not detected by whoever verifies.

## Correctness

`kbb -M:test` (61 tests / 229 assertions, verified 2026-08-13; the `kbb -M:test`
that used to be listed alongside it is unavailable, see above): mint→verify
round-trip + issuer binding, tamper
rejection, SIWE plaintext shape, header shape, `:now` freshness, nonce-replay
protection (fresh nonce succeeds + is recorded, exact replay rejected,
distinct nonces both succeed, cross-issuer nonce-string reuse is not a false
collision, a tampered CACAO can't burn a real nonce, the store-omitted
fallback stays crash-free but doesn't protect across calls), plus the
delegation-chain suite (real minted 2- and 3-link chains, tampered middle
link, resource escalation, expiry ordering, broken iss/aud linkage, `:now`
freshness, chain-level nonce-replay — both cross-call and intra-chain
reuse, malformed input), plus the `cacao.cli` suite (arg parsing, validation,
deterministic seed→did, mint→verify round-trip, ttl/nonce defaults) → 33
tests / 147 assertions green.

## License

Apache-2.0.
