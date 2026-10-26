# 0030 — Every network-reaching capability requires an origin allowlist, not just `net/fetch`

Status: accepted
Date: 2026-08-11
Closes: [aiueos#144](https://github.com/kotoba-lang/aiueos/issues/144) finding 1
Root authority: `com-junkawasaki/root` ADR-2800004300 (host-plane audit, 2026-08)

## Context

`aiueos.policy` refused to grant `:net/fetch` while
`:aiueos.policy/net-allow` was empty, and that refusal was written as a test of
one capability **name**:

```clojure
net-would-grant? (or (contains? resolved :net/fetch)
                     (contains? granted :net/fetch))
```

Four more capabilities reach the network, and they were named as such **in the
same file** — `surface-bound-provider-caps`: `:http/get-stream`,
`:object/get-stream`, `:object/put-block`, `:object/compare-and-set-ref`. None
of them appeared in the test above, so the same component granted `:net/fetch`
was confined to an operator allowlist, and granted `:http/get-stream` was
confined by nothing.

This is not an ambient-authority hole: the component still needs an explicit
per-component grant and a provider on the active surface. What was missing is
**scoping**, and the classification was incomplete in the fail-open direction —
the dominant defect shape the 2026-08 host-plane audit found across this stack
(a hand-maintained classification, copied, with nothing reconciling the copies).

The previous session filed this rather than fixing it, because the grant
semantics reach beyond this repo. That remains true for request-time
enforcement (below); it is not true for admission, which is this repo's own
decision to make.

## Decision

1. `network-reaching-caps` is the one place the question "does this grant let a
   component originate network requests?" is answered. It is **derived**:

   ```clojure
   (into #{:net/fetch} (remove local-only-provider-caps) surface-bound-provider-caps)
   ```

   A capability added to `surface-bound-provider-caps` is therefore
   network-reaching **until someone writes it into `local-only-provider-caps`**.
   The omission direction is fail-closed, and there is no second list to drift
   against the first.

2. `local-only-provider-caps` is empty today and documents why: a capability
   that is local on one surface and remote on another belongs in the
   network-reaching set, because admission happens before a surface is chosen.

3. The `:net-allow-empty` violation now names the capability that triggered it
   rather than the single word `net/fetch`.

4. A grant that includes a network-reaching capability carries the origin scope
   it was admitted under, on the decision:

   ```clojure
   :aiueos/detail {:net {:capabilities #{:object/put-block}
                         :allow #{"objects.example"}}}
   ```

   Admission has already refused an empty allowlist, so `:allow` is never empty
   when this key is present. A provider binding therefore does not have to
   re-read the policy to learn what `aiueos.net/url-allowed?` must be called
   with.

## This is a breaking change, and the break is the point

A deployment that granted `:http/get-stream`, `:object/get-stream`,
`:object/put-block` or `:object/compare-and-set-ref` **without**
`:aiueos/net-allow` was admitted before and is denied now, with
`:net-allow-empty` naming the capability. The migration is one line of policy:
name the origins that capability is allowed to reach.

The in-repo instance of exactly this migration is
`component-provider-requires-explicit-grant-and-named-surface`, whose
grant-case policy now carries `:aiueos/net-allow #{"objects.example"}`.

## What this does NOT close

**Request-time enforcement is still repo-external.** `net-url-allowed?` has no
caller in any `get-stream` path, because aiueos hosts no network implementation
at all — it decides and supplies named providers; `kototama`'s
`kototama.aiueos-adapter` and `kotoba-lang/provider` implement them. This ADR
gives those implementations the scope on the decision (item 4) and the shared
decision function (`aiueos.net/url-allowed?`); it cannot make them call it.
That call site is the remaining half of aiueos#144 finding 1 and belongs to the
provider repos.

**Finding 2 of aiueos#144 is untouched** — `forbid-effects` classifies
"is this network?" from the manifest's self-declared `:aiueos/effects`. Its
severity was already downgraded in the issue: link-time `UnlinkableException`
structurally enforces capability possession regardless of what the manifest
claims.

## Evidence

- `kbb -M:test` — **428 tests / 1,295 assertions, 0 failures**
  (baseline on `634af93`: 425 / 1,256 / 0).
- Mutation: narrowing `network-reaching-caps` back to `#{:net/fetch}` produces
  **19 failures**, including both new tests. The gate was verified to fail
  before it was landed.
- `network-reaching-caps-require-an-origin-allowlist` drives its cases from
  `surface-bound-provider-caps` + `:net/fetch` — the **input** to the
  classification, not `network-reaching-caps` itself. Driving it from the output
  would let a narrowed classification narrow its own test and stay green.
- `qualification/tcb-inventory.edn` records the new `src/aiueos/policy.cljc`
  digest; the TCB gate failed until it did, which is the supply-chain gate
  behaving as designed.
