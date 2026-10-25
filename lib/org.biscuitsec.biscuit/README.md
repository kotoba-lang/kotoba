# org-biscuitsec

**A token anyone can attenuate offline, that anyone can verify with no
secret at all.**

**The delegation centre of this workspace** (root ADR-2608180200): new
principal-to-principal delegation is written here, and every other capability
format keeps a named, narrower role.

## Kotoba effect join

`biscuit.kotoba-logic/authorize` is the bounded five-origin guard used at an
effect boundary:

```text
Amu static effect
  AND VM concrete intent
  AND attenuated Biscuit grant
  AND local policy
  AND current runtime world/availability
  => concrete runtime capability
```

Amu facts arrive in a content-bound `:kotoba.compiler-facts/v1` envelope.
Biscuit facts are first reduced to `grant:` facts by `biscuit.kotoba`; token
facts and rules are then hidden from policy saturation, so a token cannot
impersonate `amu:`, `policy:`, or `runtime:` provenance. Only the local
authorizer's generated allow policy can produce a capability. Every outcome is
receipted without embedding the bearer token.

`biscuit.effective/authorize` remains the compatibility guard for the earlier
three-term semantics. When handed semantics v2 it fails closed with
`:logic-authorizer-required`; new hosts cannot accidentally skip Amu or runtime
evidence by calling the legacy surface.

Origin plane of [biscuitsec.org](https://www.biscuitsec.org) — the format is
Biscuit's, so the repo is named for where it comes from, not for what it does
here. This is a **clean-room decision core**, not a port.

```clojure
(require '[biscuit.token :as bt] '[biscuit.authorizer :as az])

(def t (bt/authority {:facts '[[right "prices" read] [user "alice"]]
                      :next-public-key (:public k1)
                      :root-private-key (:private root) :sign-fn sign}))

;; Attenuate with a key the ISSUER does not hold and has never seen.
(def narrowed (bt/append t {:checks '[{:body [[operation read]]}]
                            :next-public-key (:public k2)
                            :private-key (:private k1) :sign-fn sign}))

(az/authorize narrowed {:root-public-key (:public root) :verify-fn verify
                        :facts '[[operation read]]
                        :policies '[{:kind :allow :body [[user "alice"]]}]})
;; => {:allowed? true :verified? true :reason :allowed-by-policy}
```

## The one difference from a macaroon, and it decides deployments

    authority block   signed by root key,   carries next-public-key
    block 1           signed by key 0,      carries next-public-key
    block n           signed by key n-1,    carries next-public-key

A macaroon chains an HMAC, so **only the holder of the root secret can
verify**. A biscuit chains public keys, so a verifier needs only the root
*public* key — which means any node, worker or browser can verify a token it
was handed **without being trusted with anything**. In a fleet where
verification happens at the edge, that is the property that matters.

## Attenuation is monotone because of scoping, not etiquette

A later block may add facts, rules and checks. What stops it widening the
token is that a check is evaluated against **the authority block's facts plus
its own, and nothing later** — so a block cannot inject the fact that
satisfies an earlier block's check.

An implementation gets this wrong by pooling every fact into one set, and
every ordinary test still passes, because ordinary tokens have no reason to
lie to themselves. There is a test here that fails **only** when the pool is
shared.

## Checks are the token's; policies are the verifier's

- **checks** live in the token and must all pass — what the holder, and
  everyone who attenuated after, restricted themselves to.
- **policies** live in the authorizer; the first that matches decides.

So **there is no `allow` inside a token**: a token cannot allow itself. And
`:no-policy-matched` is reported distinctly from `:denied-by-policy` — both
refuse, and telling them apart is what says *your policy set has a hole*
rather than *your rule fired*.

Order is fixed: **verify → checks → policies.** Running policies first would
let a token whose signature does not verify reach a rule that says `allow`.

## Where it sits, repo-wide

Five capability surfaces were measured across the fleet (root ADR-2608180200)
and **four of them are not delegation at all** — which is why they never
needed one format and why naming what each *is* was most of the work:

| surface | what it actually is | revocation |
|---|---|---|
| `kotoba-lang/kotoba-lang` `capability-semantics.edn` | the **semantics**: `requested ∩ delegated ∩ local-policy` | at effect time |
| `kotoba-lang/amu` `{:allow #{[:cap/call n]}}` | compile-time **admission** — what code may even ask for | signer set |
| `kotoba-lang/aiueos` `capability-plan.kotoba` | a machine-local **capability table** (slot/generation/type/rights/owner) | **generation bump** |
| `kotoba-lang/kototama` `component-authority` | a signed **epoch feed** for placement and revocation | monotonic epoch |
| **here** | **delegation between principals** | — |

The last column is the finding worth carrying: **a biscuit cannot revoke**,
and two of the other four already can. So revocation rides the generation and
epoch planes that exist rather than becoming a revocation list nobody serves.

`biscuit.kotoba/->delegated` is the concrete seam. The semantics had four
terms and three owners; **`delegated` had no wire**, and that slot is what
"biscuit is the centre" means — not that biscuit replaces the semantics.

```clojure
(bk/->delegated token kinds)
;; => {:grants [{:grant/kind :graph-read
;;               :grant/resources ["kotoba://graph/acme"]
;;               :grant/expires "2026-09-01T00:00:00Z" :grant/id "biscuit:…"}]
;;     :grant/rejected [{:kind :kernel/format-disk :resource "/dev/sda"}]}
```

It maps to `:grant/*` and never to `:cap/*`: a capability is what a handler
receives **after** intersection, and a token that produced one directly would
have skipped the step the semantics says is not optional. A kind outside the
closed `:kinds` set is **rejected, not ignored** — ignoring silently drops a
restriction the issuer meant, so the failure is toward less authority and is
visible in `:grant/rejected`.

## The guarded call — the slice that makes it the centre

`biscuit.effective/authorize` answers what a host actually asks — *may this
call proceed* — and it needs **the token, the root public key, the local
policy and a clock. No secret, on any branch.** That is what lets it run in a
Worker, a browser or on an untrusted mirror, and it is the entire reason the
centre is biscuit and not macaroon.

```clojure
(eff/authorize {:semantics semantics :token t
                :root-public-key pk :verify-fn verify
                :requested {:cap/kind :graph-read :cap/resource "kotoba://graph/acme"}
                :local-policy {:policy/allow [...] :policy/forbid-wildcard true}
                :now now :call "graph/read"})
;; => {:allowed? true :reason :granted
;;     :capability {:cap/kind :graph-read :cap/resource "…" :cap/provenance :biscuit}
;;     :receipt {:receipt/at … :receipt/call … :receipt/cap … :receipt/outcome :allowed}}
```

`:token` is a `biscuit.token` model **or a decoded wire token**
(`biscuit.wire/decode-token`). Each is verified over the payload it was signed
over — the EDN payload for a model, the v3 protobuf bytes via
`biscuit.wire/verify` for a wire token. A `biscuit.wire/token->model` result is
refused as `:wire-model-not-verifiable`: the signed bytes are gone, so nothing
can check it.

`holder` folds across blocks and may only narrow (`biscuit.kotoba/->delegated`):
a later block may address a bearer token or repeat the holder; a later block
naming a different holder, or one block naming two, confers nothing and is
refused by name (`:holder-readdressed` / `:holder-ambiguous`).

**The rules are read, not restated.** `authorize` takes the semantics map and
branches on its `:rules`; copying `:unknown-kind :deny` into a `case` here
would make this a second statement of the language's policy. A contract test
loads the real `lang/capability-semantics.edn` and fails when the rule set
changes shape — and **refuses rather than passing when it cannot read the
file**, because a contract test that cannot see the contract has not checked
one.

**Every attempt is receipted, including the denials.**
`:attempt-always-receipted true` is in the semantics, and a guard that logs
what it allowed and forgets what it refused cannot answer the only question
an incident asks.

## Scored against the alternatives

Root ADR-2608180200, 0–5, weighted for this workspace:

| | offline | **verify w/o secret** | attenuation | expressiveness | revocation | wire maturity | implemented here | total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **biscuit** | 5 | **5** | 5 | **5** | 3 | 2 | 4 | **29** |
| UCAN | 5 | 5 | 5 | 3 | 4 | 4 | 4 | **30** |
| CACAO | 5 | 5 | 2 | 2 | 3 | 4 | 5 | 26 |
| VC/VP | 5 | 5 | 0 | 4 | 4 | 5 | 4 | 27 |
| macaroon | 5 | **0** | 5 | 3 | 2 | 2 | 4 | 21 |
| mTLS / X.509 | 4 | 5 | 0 | 1 | 2 | 5 | 3 | 20 |
| OAuth2 / JWT | 4 | 4 | 0 | 2 | 1 | 5 | 3 | 19 |
| bearer token | 0 | 0 | 0 | 0 | 5 | 5 | 5 | 15 |

**UCAN scores one point higher and was not chosen.** The gap is wire maturity
and revocation; biscuit wins expressiveness by two, and this workspace speaks
Datalog — so delegation conditions written in Datalog are worth more here than
elsewhere. The table is recorded as the *reason*, not as the decision.

## The Datalog, and why it is not a second copy of `kotoba-lang/datalog`

| | `kotoba-lang/datalog` | here |
|---|---|---|
| facts | **EAV triples**, indexed | **n-ary** `[pred t …]`, no index |
| source | a database value | a token's blocks |
| size | the corpus | tens of facts |
| termination | range-restricted | range-restricted **plus a budget** |

Flattening n-ary facts into triples to reuse the EAV engine means inventing
entity ids the token never had. These two cannot substitute for each other,
so they are two things (ADR-2607299700 reads the other way). **The trigger to
revisit is a third n-ary evaluator.**

The budget is a safety property, not a tuning knob — an authorizer runs
attacker-supplied rules, and exceeding it is a **distinct outcome**
(`:budget-exceeded`), never an empty result set. A truncated derivation that
answered *no facts* would deny for the wrong reason today and allow for the
wrong reason tomorrow. An **unsafe rule** — a head variable the body never
binds — is refused rather than skipped, for the party who can fix it.

## Two wires, one decider

`biscuit.authority/->grant` maps a verified token onto
`kotoba-lang/authority`, exactly as `macaroon.authority` does. Only
`scope` / `before` / `holder` facts are read **for granting**; everything
else stays available to checks and policies. Ignoring is safe in exactly one
direction and this is that direction — **an unread fact cannot widen a
grant.**

Within a block, scope facts are alternatives; **across blocks they narrow.**
Meeting every fact separately — how this was first written — makes a block
with two scopes reach nothing: safe, and wrong.

## What it refuses, by name

- **Silently weakening a token while writing it.** `biscuit.wire` writes a
  facts-only Biscuit v3 authority block and refuses unsupported terms. Rules,
  checks and expressions are not accepted by that writer until the decoder
  can enforce them too; dropping a restriction would mint more authority
  than the issuer requested.
- **Expressions** (`Op` / `OpUnary` / `OpBinary` / `OpClosure`). Rules and
  checks are counted, not decoded. This is where a partial decoder would do
  real damage — an operator it silently dropped is a *check that no longer
  restricts*, which reads as a more permissive token rather than an error.
- **Crypto.** `sign-fn` / `verify-fn` injected, no default Ed25519.
- **Third-party blocks.** Refused in `append` rather than approximated.

## Real Ed25519, on both runtimes

Most of the suite injects a deterministic stand-in and says so: the chain
properties hold for any signature scheme. One suite does not.
`biscuit.real-crypto-test` uses **the platform's own Ed25519** —
`java.security.Signature` on the JVM, `node:crypto` under nbb, with the
public key derived from a stored seed by `kotoba-lang/org-ietf-ed25519`
rather than by generating a fresh pair. It checks that the payload this
library asks to be signed is one Ed25519 actually signs and actually
verifies, that a 64-byte signature comes back, and that a guarded call is
decided **holding only the root public key**.

It also holds the forgery a stand-in makes easy to miss: a token minted
entirely by an attacker, naming their own successor key, is **internally
perfectly consistent** — a well-formed biscuit in every respect. It verifies
under its own root and is worthless under ours, and the only thing separating
the two is the root key the edge was given.

## It reads and writes tokens across the `biscuit-auth` boundary

Every other suite here checks this library against itself. `biscuit.wire`
checks it against the reference implementation, using that project's own
`samples/current` fixtures:

```clojure
(w/blocks-with-facts (w/decode-token (sample "test001_basic")))
;; facts => [["right" "file1" "read"] ["right" "file2" "read"] ["right" "file1" "write"]]

(w/verify (w/decode-token (sample "test001_basic")) root-public-key verify-bytes)
;; => {:ok? true :blocks 2}
```

and the three negative samples — a different root key, an altered signature
byte, reordered blocks — are all refused.

The reverse direction is checked too: `encode-authority-token` mints a v3
protobuf token, and the official Rust `biscuit-auth` CLI opens it, prints its
`scope` / `before` / `holder` facts, and reports a successful public-key
check. This is deliberately stronger than the in-repo writer→reader round
trip, which remains in the portable JVM and nbb suites as a regression test.

**The signature byte order was decided by the sample, not by me.** The spec's
v0 section lists the payload parts as data, next key, algorithm; the v1
section orders them data, algorithm, next key. Rather than pick one and
produce plausible verifications, both are expressible and `test001_basic.bc`
was allowed to decide: `data ‖ alg(LE32) ‖ next_key` verifies, and there is a
test asserting the **other order fails**, because a positive result nothing
could have failed proves nothing.

## Where the root key comes from, computed

Verification needs one root public key, which moves the problem one step
out: the edge has to learn *which* key, and a key baked into a bundle cannot
rotate while a key fetched from a mutable place can be swapped silently.

`npm run bench:keydist` computes the trade rather than asserting it. The unit
is fetches, because on an edge a fetch is a round trip and everything else is
noise beside it (1M verifications/month, quarterly rotation, 400 cold starts
a day):

| option | fetches/mo | verifiable rotation | a compromised distribution point can |
|---|---:|---|---|
| baked into the bundle | **0** | no | swap the key for everyone, silently |
| KV / mutable lookup | **360,000** | no | swap the key for everyone, silently |
| `did:web` | 12,000 | no | swap the key, silently |
| `did:webvh` | 16,000 | **YES** | withhold or serve stale — **cannot introduce a key** |
| **signed rotation log** | **12,000** | **YES** | withhold or serve stale — **cannot introduce a key** |

The mutable lookup is thirty times the cost of the alternatives **and**
unverifiable, which is the combination worth naming. The two verifiable
options cost the same order; one adds DNS and HTTPS to the auth path
(root ADR-2608039000 spent effort removing exactly that) and the other adds
nothing new — because it is the shape `kotobase.storage.signed-head`, IPNS v2
and `kototama.component-authority` already are, and the shape a biscuit
itself uses internally: **each record names the key that may sign the next
one.**

`biscuit.rootkey` is that log. A record commits to the **digest** of the key
allowed to sign its successor, so a reader trusting record *n* can verify
*n+1* without trusting the host it arrived from. An attacker who takes the
publishing location can withhold records or serve old ones; they cannot
introduce a key nobody committed to. `did:webvh` can still be the transport —
it just is not the authority.

Publishing is `publish` (records are immutable and content-addressed, plus
one tip naming the newest) and reading is `resolve-log` (walk back from the
tip to genesis, then verify forward). **The tip needs no signature**, for the
argument the packed block plane makes for its own unsigned tip
(root ADR-2608170300): a planted tip resolves, and then fails verification,
because every record is still checked against its predecessor's commitment
and against the hash link. What a hostile tip *can* do is withhold — serve an
old tip and hide a rotation — which is a liveness failure, not an authority
one, and a caller that cares compares `:seq` against what it last saw. There
is a test for the planted tip that asserts both halves: it resolves, and it
does not verify.

The walk is bounded (a tip comes from a host that may be hostile, so `prev`
is an unbounded pointer chase it controls), cycles are refused, and a
withheld record is refused rather than leaving the reader with a shorter,
still-verifying chain.

Two failures this shape already cost the fleet once (`signed-head`, 2026-08-04)
are tests here: a record must **name what it is the key for** (or a host
answers subject B with subject A's genuinely-signed record and nothing was
forged), and the signer must be constrained by something **outside** the
record (or the check is *somebody signed this*, which any keypair satisfies).

## Revocation, which this library computes and does not distribute

Per the spec, a block's revocation identifier **is its signature**. So
`revocation-ids` needs no clock and no contact with the issuer, and
`revoked?` is a set membership test:

```clojure
(w/revoked? token #{parent-signature})   ;; => true, for every token derived from it
```

Two properties come free and both matter. A revocation identifies a **tail**,
not a holder — revoking the authority block kills everything derived from it,
revoking a later block kills only the attenuations carrying it, and the
revoker never has to know what was derived. And it is **offline**: a verifier
holding the set refuses without asking anyone, which is the same property
`biscuit.rootkey` gives key discovery.

**Where the set comes from is not decided here.** Root ADR-2608180200 puts
it on the planes that already carry monotonic signed state —
`kototama.component-authority`'s epoch feed and aiueos's capability
generations — rather than inventing a revocation list nobody serves. Those
two can already revoke; a biscuit could not, and this is the half that lets
them.

## Verification

`kbb -M:test` and `npm run test:nbb` — **49 tests, 120 assertions**, both
green. Shown red on ten real defects and green again with each reverted:

| broken | failures |
|---|---:|
| facts pooled across all blocks (attenuation stops being monotone) | 2 |
| the signature stops covering `next-public-key` | 2 |
| the Datalog budget truncates instead of refusing | 1 |
| a later block can extend an expiry | 2 |
| a kind outside the closed set is admitted instead of rejected | 3 |
| a later block may add kinds and resources (attenuation stops being only-attenuation) | 3 |
| the local-policy term is dropped from the intersection | 1 |
| denials are not receipted | 7 |
| the contract file is unreadable (must fail, not pass) | 1 |
| a block may also validate against the key **it names** | 1 |

The second was **found by the exercise**: nothing had checked that a block
cannot be spliced onto a different continuation. The attack it permits is
complete — rewrite a signed block's `next-public-key` to a key you control,
append blocks you sign, and the chain verifies. That test now exists, and it
is the strongest one in the suite.

Two attempted breaks first appeared to pass unbroken and had simply not
applied — indentation mismatches in the edit. **A no-op break looks exactly
like a missing test**, and the only way to tell them apart is to diff the
file you claim to have broken. One of the two was real when redone (denials
went unreceipted in seven places); the other — "a later block can extend an expiry" — first
appeared to pass unbroken. The edit had silently not applied (indentation
mismatch). **A no-op break looks exactly like a missing test**, and the only
way to tell them apart is to diff the file you claim to have broken.
