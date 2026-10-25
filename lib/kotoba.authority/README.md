# authority

**The capability lattice that `capability-semantics.edn` specifies.** Scopes as
segment paths, `covers?` as a partial order, `meet` as attenuation — and every
authority string already on the wire in this fleet as a rendering of it.

Portable `.cljc`, zero runtime dependencies, no crypto. Runs on the JVM and in
a Cloudflare Worker from the same source.

```clojure
(require '[authority.scope :as scope]
         '[authority.grant :as grant]
         '[authority.chain :as chain])

(chain/authorize
  {:chain     [(grant/grant {:scopes ["kotoba://graph/*"]  :expires "2026-09-01T00:00:00Z"})
               (grant/grant {:scopes ["kotoba://graph/g1"] :holder "did:key:zBob"})]
   :requested "kotoba://graph/g1"
   :holder    "did:key:zBob"
   :now       "2026-08-15T00:00:00Z"})
;; => {:authority/allowed?  true
;;     :authority/reason    :granted
;;     :authority/effective {:grant/scopes #{["kotoba" "graph" "g1"]}
;;                           :grant/expires "2026-09-01T00:00:00Z" …}
;;     :authority/attempts  []
;;     :authority/depth     2}
```

## Why this exists

Every capability check in the fleet asks the same question — does what the
holder was granted cover what they are asking for — and it is written once per
URI scheme, each time as a string equality with a trailing-`*` special case.
Measured 2026-08-15, that is **eight schemes**:

```
kotoba://can/ (180)   kotoba://graph/ (91)   kotoba://op/ (27)
kotoba://org/ (18)    kotoba://cap/ (17)     kotoba://authority/ (3)
kotoba://tenant/ (1)  kotoba-rad://<rid>/push/<ref>
```

That shape has a failure mode it cannot see. `cacao.core/covers?` strips the
`*` and calls `starts-with?`:

```clojure
(covers? "kotoba://graph/alice*" "kotoba://graph/alice-evil")  ;=> true
```

Today's minters happen to always place the `*` after a `/`, so the hazard is
latent rather than live. But it is latent **in the comparison**, which means
every future minter has to hold an invariant by hand that nothing checks. Here
a scope is `["kotoba" "graph" "alice"]`, segments compare by `=`, and there is
no substring left to confuse. Prefix confusion is not rejected — it is
unrepresentable.

`authority.scope-test/a-wildcard-cannot-confuse-a-prefix` pins both directions:
the confusing pair is refused, and the genuine wildcard still reaches it.

## The theorem

    effective = meet(link₀, link₁, … linkₙ)

`meet` is the greatest lower bound of `covers?`, so the fold is covered by
every link **by construction**. A link claiming more than its parent does not
have to be rejected for the result to be safe — it contributes nothing,
because there is no value the fold could produce that some link did not
already grant.

`cacao.core/verify-chain` instead *checks* each pair and reports the leaf's
resources as effective. That is correct while every pair verified, and one
forgotten branch away from not being. Here escalation is arithmetically
absent, and `:authority/attempts` still reports every attempt — safety from
the algebra, evidence from the report, neither standing in for the other.

### A gap this closes on the way

`cacao.core/link-problems` compares expiries only `(when (and (:exp parent)
(:exp child)))`, so a child link carrying **no** `exp` under a bounded parent
is never reported. Here an absent bound is `+∞` and `meet` takes the minimum,
so an unbounded child cannot extend a bounded parent — and `grant/escalation`
reports the attempt anyway.

## The wire does not change

`render` reproduces the existing strings byte for byte and `parse` accepts
them, so adopting this is a **replacement for the comparison, not a migration
of the tokens**. All eight schemes round-trip; see
`authority.scope-test/the-wire-round-trips-byte-for-byte`.

## Fail-closed, without a sentinel

There is no `::denied` value. A grant reaching nothing is the empty antichain,
and `covered?` on it is false through the ordinary code path rather than a
special case — `nil` punning to *allow* is how a missing policy becomes a
public database, and a sentinel is only safe while every caller remembers to
test for it.

Consequently:

| input | result |
|---|---|
| unparseable resource string | not a scope; `parse-all` reports it in `:rejected` |
| empty chain | `grant/nothing`, reason `:empty-chain` |
| no trusted clock | denied, reason `:expired-or-no-trusted-time` |
| holder mismatch | denied, reason `:wrong-holder` |
| in scope, live, right holder | `:granted` |

A caller that ignores `:rejected` is **narrowed**, never widened.

## What this does not do

**It does not authenticate anything.** No signature is verified, no key is
read, and no parent-audience → child-issuer linkage is checked. Those belong
to `cacao.core/verify-chain`. A fold of unverified links is a fold of whatever
the presenter wrote.

This boundary is stated in `authority.chain`'s own docstring as well, because
a library that looks like the check and is not on the path where the check
happens is exactly the gap the superproject found in `kotobase.guarded`.

## Boundary with the nearest repositories

| repo | question it answers |
|---|---|
| **authority** (here) | how much authority does this grant confer, and does it reach what is asked |
| `kotoba-lang/policy` | do this subject's attributes satisfy a rule (ABAC/RBAC, combining algorithms) |
| `kotoba-lang/authorization` | request → decision facade, with a durable decision ledger |
| `org-chainagnostic-cacao` | is this token genuine, unexpired and unreplayed (CAIP-122 / SIWE, Ed25519) |
| `kotoba-lang/security` | fleet-wide assurance controls: ABAC, information flow, one-shot effect grants |

`policy` decides from attributes; this decides from *held authority*, and the
two compose — a policy may narrow a grant, never widen it, which is `meet`.

## Complexity

`covers?` is O(depth) with early exit. `meet-sets` is O(|a|·|b|) before
normalisation, and normalisation keeps grants as antichains — a handful of
scopes in practice — so a delegation chain folds in time linear in its length.
No allocation on the deny path.

## Pure Kotoba: `authority.lattice`

[`src/authority/lattice.kotoba`](src/authority/lattice.kotoba) is the same
lattice for a Kotoba guest (root ADR-2610082200 §16: everything below the
kotoba app runs in pure Kotoba). `authority.scope` stays as the general oracle,
the way kotoba-lang/text keeps `text.cljk` beside `bounded_text.kotoba`.

It works on the resource string itself (`kotoba://graph/g1`), because a scope
vector mixes string segments with the keyword `:*` and a Kotoba vector holds
one type; `parse` and `render` are inverses on every valid scope, so nothing is
lost. `valid?`, `covers?`, `meet` (`""` when incomparable) and `covered?` keep
the oracle's laws. It needs only `kotoba.lang.bounded-text`, so `deps.edn` pins
kotoba-lang/text at a commit that has it.

```bash
kbb --backend sci --classpath "src:$(kbb -Spath)" scripts/lattice-oracle-cases.cljk
```

asks `authority.scope` every question the Kotoba tests assert (37 cases on
2026-10-09, all agree). The tests themselves run on Wasm:
`kotoba -M compile src/authority/lattice.kotoba --source-path src ... --target
wasm32-browser --fuel 1000000`, then each `test-*` export in a fresh instance
(8/8). `kotoba -M test` stops on the js target (`unsupported KIR node`) and the
native targets do not yet qualify typed string sets.

### `authority.delegation`

[`src/authority/delegation.kotoba`](src/authority/delegation.kotoba) is
`authority.chain/authorize` for a guest, on top of `authority.lattice`. It
answers the same reason in the same order (1 granted … 6 out-of-scope, plus 7
for a malformed chain). A chain is three typed maps keyed 0..n-1 — scope sets,
holders, expiries — because a list of records is outside the value profile and
`[:list T]` has no count. It never builds a meet of sets: scopes form a tree,
so the meet of every link covers a request exactly when every link covers it.

```bash
kbb --backend sci --classpath "src:$(kbb -Spath)" scripts/delegation-oracle-cases.cljk
```

asks the oracle the same 22 questions (all agree, 2026-10-09). On Wasm the five
`test-*` pass with `--fuel 5000000`.

## Test

```bash
kbb -M:test                       # 37 tests, 122 assertions (JVM)
kbb --backend sci --classpath src test/cljs_smoke.cljk   # the same laws under ClojureScript
```

The order laws (reflexivity, antisymmetry, transitivity, greatest-lower-bound)
are enumerated exhaustively over a twelve-scope universe — 144 pairs, 1,728
triples — rather than sampled, and the fold theorem over all 343 three-link
chains. A property that holds here holds because it was checked.

Both discriminating mutations were run against a broken copy and produced
exactly the intended failure and no other:

| mutation | test that failed |
|---|---|
| segment compare → `starts-with?` (restores the `cacao` semantics) | `a-wildcard-cannot-confuse-a-prefix` |
| absent child bound → unbounded (restores the `link-problems` gap) | `an-unbounded-child-cannot-outlive-a-bounded-parent`, `the-tightest-expiry-in-the-chain-wins-wherever-it-sits` |

## Migrating the decision core to `.kotoba`

`scope/covers?` is a pure decision over two sequences of segments — the shape
the superproject's decision-core rule asks for. It is `.cljc` today because
its consumers are `.cljc` (`kotobase`, `security`, `nekko`) and `.cljs` (the
edge Worker), and the collection layer (`normalize`, `meet-sets`) is exactly
the part that rule says stays behind.

The blocker for the pairwise core is `kotoba-kir`'s native admission gate,
which is word-typed: a scope is a sequence of strings, so it qualifies on
`:compiler` / `:kotoba-wasm` / `:kotoba-cljs` but not `:native-aot`. That is a
backend gap, not a language ceiling — do not read this note as a design
constraint.

Written to make the move cheap: no atoms, no host interop, no exceptions on
the decision path, and every failure already a value.

## Target-neutral and distributed stack architecture

Owns scope coverage, attenuation and delegation algebra, independent of target ABI and deployment host. Cryptographic authenticity and data identity do not substitute for authorization. Language capability meaning remains with its existing catalog owner; this model does not become a compiler, network or policy engine.

See the [owner integration guide and dependency direction](docs/stack-architecture.md),
[composition metadata](spec/stack-integration.edn), and
[whole-stack refactor procedure](https://github.com/kotoba-lang/kotoba-lang/blob/main/docs/stack-refactor-procedure.md).
The direction is adopted; runtime contract migration and qualification remain
explicit, separately verified work. Tier labels are responsibility axes, not
a single dependency ranking.
