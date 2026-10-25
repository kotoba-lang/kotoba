# dango

**団子 (dango): dumplings on a skewer.** Each dumpling is one block; the skewer
is the hash link that holds them in order; handing authority on is sliding one
more dumpling onto the end. `dango` is **kotoba's delegation credential: a
signed chain of IPLD blocks whose bodies are S-expressions** — Biscuit's
offline attenuation without Datalog.

The name is a metaphor, not a description, so it is stated here and registered
in the superproject's `manifest/concept-vocabulary.edn` (`:dango-capability-chain`).

Decision: com-junkawasaki/root
`90-docs/adr/2609242100-capability-chain-is-ipld-sexpr-biscuit-is-an-adapter.kotoba`.

## One block

```clojure
{:prev     <parent block CID>            ; nil only at the root
 :grant    {:caps   #{[:data/read "kotoba://storage/<tenant-did>/ds"]}
            :holder "did:key:z6Mk…"
            :before 1790000000}
 :caveats  [[:and [:<= :req/bytes 1000000] [:prefix? :req/path "ds/raw/"]]]
 :next-key <ed25519 public key>}          ; the key that may sign the next block
;; + a signature over the block's dag-cbor bytes by the parent's :next-key
```

A block is one dag-cbor node (io-ipld `kotoba.value.v1`) and is identified by
its CID. A token is the chain as a CAR. The shape is data:
`resources/dango/block-shape.edn`.

## Use

```clojure
(require '[dango.chain :as chain])

(def token                                   ; Authn mints the root
  (chain/root {:issuer-seed issuer-seed
               :grant {:caps #{[:data/read "kotoba://storage/<did>/ds/*"]}
                       :before 1800000000}
               :caveats [] :next-seed bearer-seed}))

(def narrowed                                ; the bearer narrows it, offline
  (chain/attenuate token {:grant {:caps #{[:data/read "kotoba://storage/<did>/ds/raw/*"]}
                                  :holder "did:key:z6MkAgent" :before 1750000000}
                          :caveats [[:<= :req/bytes 1000000]]
                          :next-seed agent-seed}))

(chain/verify (chain/present narrowed) {:roots #{issuer-public-key} :revoked #{}
                        :request {:req/kind :data/read :req/resource "kotoba://storage/<did>/ds/raw/a"
                                  :req/now 1700000000 :req/holder "did:key:z6MkAgent"
                                  :req/bytes 4096}})
;; => {:dango/allowed? true :dango/reason :granted :dango/cids [...] :dango/effective {...}}
```

The holder keeps `{:blocks :proof}`; a verifier is shown `(chain/present
token)` = `{:blocks :seal}` — the proof key's signature over the last block's
bytes, so the proof never leaves the holder (Biscuit's sealed token). Checking
a seal needs only signature VERIFICATION, which is what lets the native
verifier do it. `chain/encode-token` / `decode-token` move either as one
canonical value.

## Deciding at an edge — in this order, first failure wins

### External user roots in the CLJK host

`chain/verify` also accepts `:root-verifier`, a trusted host function receiving
`{:bytes canonical-root-bytes :cid computed-root-cid :signature root-signature}`.
Only literal `true` accepts the root. Resolve asynchronous wallet verification
against current chain state first, then bind the adapter to those exact bytes,
CID and signature. Never load the function or its verdict from a presentation.
With the adapter present, legacy `:roots` cannot override a refusal. All other
chain, seal, revocation, attenuation and caveat checks still run locally.

This is a CLJK host extension. The native `.kotoba` verifier continues to use
Ed25519 roots; it does not implement Ethereum RPC or wallet verification.

| stage | refused as |
|---|---|
| every block decodes canonically and is well-formed (caveats included) | `:dango/malformed-block` `:dango/malformed-caveat` `:dango/unknown-operator` `:dango/unknown-fact` `:dango/caveat-too-large` |
| 1–16 blocks | `:dango/empty-chain` `:dango/chain-too-long` |
| every `:prev` links the previous block's CID | `:dango/broken-link` |
| every signature verifies under the parent's `:next-key`, the root under a trusted root | `:dango/bad-signature` |
| a holder, once set, is never changed | `:dango/holder-readdressed` |
| no block CID is revoked | `:dango/revoked` |
| the seal verifies under the last `:next-key` (a truncated chain cannot be sealed) | `:dango/bad-seal` |
| the request names a kind, a resource and a time | `:dango/malformed-request` |
| `authority.chain/authorize` over the meet of all blocks | `:dango/not-covered` `:dango/expired` `:dango/wrong-holder` |
| every caveat of every block holds | `:dango/caveat-false` |

A block's CID is computed from the bytes received, never from a re-encoding,
so there is no "CID mismatch": tampering is a `:bad-signature`.

Caveats (`dango.caveat`) are keyword-headed vectors —
`[:and [:<= :req/bytes 10] [:prefix? :req/path "ds/"]]` — never lists, and a
closed, total, **three-valued** predicate
language: a fact the request does not carry, or operands of different types,
make a comparison *unknown*, and `not` / `and` / `or` keep unknown unknown
(Kleene). Only a final `true` holds. Two-valued logic here would be fail-open:
`[:not [:= :req/kind :data/write]]` would hold for a request with no kind.

Capabilities become authority scopes with the kind as the first segment —
`[:data/read "kotoba://storage/<did>/ds"]` → `["data.read" "kotoba" "storage"
"<did>" "ds"]` — so kinds never cover each other. `:before` / `:req/now` are
epoch seconds, compared as 12-digit zero-padded strings (string order =
numeric order), because `authority.grant` compares instants as strings.

## Boundaries

- **`kotoba-lang/authority`** is the lattice (`covers?`, `meet`, `fold`). dango
  does not re-implement it; dango adds what authority says it does not do —
  CID, linkage and signature checks — and the caveat evaluator.
- **`kotoba-lang/osaho`** owns DefCID; the caveat vocabulary is meant to be a
  checked pure definition there, so its version is a CID.
- **Biscuit** stays a wire adapter at the outer boundary (transcoded at Authn).
  Until the one-time edge cutover, service edges take Biscuit only
  (adr-2609241800).
- No Datalog, and no dependency on Microsoft Entra. Tenants are DIDs.

## Status

**Portable reference implementation (2026-09-24).** `.cljk`, runs under kbb /
nbb / ClojureScript (Workers) from the same source. Built: mint, attenuate,
verify (all ten stages above), the caveat evaluator, token codec.

```
kbb --backend sci --classpath "src:resources:test:<deps src dirs>" run-tests.cljk
```

where `<deps src dirs>` are the `src` of authority, io-ipld (+ `resources`),
io-multiformats, org-ietf-cbor, org-nist-sha2, org-ietf-ed25519,
org-ietf-x25519, text, coll, edn, dev-protobuf and test from the west
checkouts. 55 assertions; each safety check was removed once in a copy and
the suite went red at the test named for it (proof, three-valued `not`,
revocation, holder rule, caveats).

**The caveat evaluator in Kotoba: `src/dango/caveat_wire.kotoba`** (2026-09-24).
It decides a caveat straight from its `kotoba.value.v1` bytes: a host grants
one byte region holding the caveat followed by the request (a value.v1 map of
`:req/*` facts), and `(holds-wire base len split)` answers 1 holds / 0 does
not / 3 malformed / 4 too large. Nothing is built — the CBOR is read in place
— so there is no ADT at the export and no ADT node budget. Same validation
(vocabulary, arity, depth 16, 256 nodes) and the same three-valued
evaluation as the `.cljk`, which stays the oracle.

```
CP="src:resources:test:<deps src dirs>"
AMU=../amu KBB_ENGINE=../org-babashka-nbb/cli.js kbb --backend sci --classpath "$CP" test/native_wire_parity.cljk            # exit 0: 27/27 agree
AMU=../amu KBB_ENGINE=../org-babashka-nbb/cli.js kbb --backend sci --classpath "$CP" test/native_wire_parity.cljk --control  # exit 0: two-valued not disagrees on exactly the 4 unknown-* cases
```

Each case is encoded by the real codec, answered by the oracle, and run as
its own native process on the same bytes (loader `g:<hex>` / `gl:0`). Exit 1
= a disagreement (named), exit 2 = could not answer (never a pass). The 27
cases include refusals (unknown operator / fact, arity, a list, depth 20,
300 nodes, an int64-wrapped literal). Measured on aarch64-macos with amu
`386e3d27` and its toolchain at main; x86_64 not measured.

**Fuel is the caller's budget.** The loader default is 512 function entries
per run (kotoba-lang `lang/limits.edn` `:profile/native`); a four-fact
request already needs ~650 and a 300-node caveat ~9,600, so the runner sets
`KEXE_FUEL` explicitly and prints the most any case used. Running out
surfaces only as SIGTRAP today (named traps are that ADR's P4).

Recorded divergences from the oracle, neither of which lets a caveat hold:
a form both malformed and over the node budget answers 3 where the oracle
says 4 (this pass stops at the first malformed term); a form nested past
~31 caveat levels answers 3 where the oracle says 4 (the CBOR walk's
nesting bound, 64, is reached before the depth check).

**The chain verifier in Kotoba: `src/dango/chain_wire.kotoba`** (2026-09-24).
`(verify-presentation base len)` over the value.v1 bytes of
`[presentation roots revoked request]` (revoked entries are 36-byte binary
CIDs) answers the oracle's reason as a code (1 granted, 10–26 the refusals —
table in the file). What runs where:

- **CIDs in the guest** — `src/dango/sha256.kotoba`, FIPS 180-4 over the
  granted bytes, allocation-free (the state and a 16-word schedule window are
  parameters; a vector-based first version exhausted the loader's 4,096
  vectors on three small blocks).
- **Signatures by capability** — `identity/verify` (wire 2), Ed25519 over
  spans of the same region named by address; the loader checks every span
  against its grant table. The native provider is kotoba-lang/amu#1075.
- **Authority without building the meet** — the scopes that cover one
  request form a chain, so the meet of all blocks covers it exactly when
  every block has a cap that covers it; expiry, then holder, then coverage,
  as `authority.chain/authorize` orders them.

```
KEXE_LOADER_SOURCE=<amu with #1075>/tools/kexe_loader.c \
AMU=../amu KBB_ENGINE=../org-babashka-nbb/cli.js kbb --backend sci --classpath "$CP" test/native_chain_parity.cljk            # exit 0: 42/42 agree
... test/native_chain_parity.cljk --control  # exit 0: without the expiry check, exactly the 2 expired cases disagree
```

42 real presentations — granted, every refusal the oracle has (16 distinct
reasons), hand-signed malformed blocks the minting code would refuse, a
16-block chain and a 17-block one — agree 42/42 on aarch64-macos; the most
fuel any case used is ~148,000 (the 16-block chain), so an edge sets
`KEXE_FUEL`. A loader without the wire 2 provider answers exit 2, never a
pass.

Porting it found three bugs in the oracle, now fixed there with tests: a
negative `:before` meant "no expiry"; the kind was one `ns.name` segment, so
`:a.b/c` and `:a/b.c` were one kind; an invalid scope was dropped instead of
refused. And the token format moved: a verifier is shown a SEAL (the last
key's signature), never the proof seed, because a verifier that only
verifies cannot derive a public key from a seed.

Not enforced by the native reader: canonical CBOR (it reads the first match
of a duplicated key; the oracle refuses). Every such block is signed by the
key allowed to sign it, so this cannot widen authority, but it is a
divergence the parity suite does not cover.

**Not yet:** `wasm32-browser` (Workers) — `unsupported typed Wasm expression`
on the caveat program, `internal compiler error` on the earlier tree-based
one (kotoba-lang/amu#1073) — so Workers run the `.cljk`. Until that lands
and amu#1075 merges, the `.cljk` stays the oracle and no consumer cuts over.

Also not built: the revocation list's home, per-surface fact vocabularies,
Authn minting, and the one-time edge cutover (adr-2609241800 stays in force
until then).
