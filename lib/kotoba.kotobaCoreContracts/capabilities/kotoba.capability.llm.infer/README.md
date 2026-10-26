# capability-llm-infer

Atomic authority package for `llm/infer`.

- imports: `#{:llm-infer}`
- effects: `#{:data-egress :network-write :llm-inference}`
- default policy: `:approval-required`
- semantic definition CID: `bafyreiaekn6d2xkw44js36amyaf27drj5tmrwuhp2pa27fddhxtjfr2t4q`
- hash contract CID: `bafkreiflhj3fslsbh7okdas2fzlhmogai64x6p3lkla6gtr7berbp7ftvi`
- provider status: `contract-only` — **and the reason changed on 2026-09-06**.
  See "Why this is still contract-only" below.

The repository name is a discovery alias. The semantic definition CID is the
immutable import identity. Importing it does not grant runtime authority:
Tamaki must request it explicitly and Kototama must admit the sealed envelope.

## Three effects, three questions

`capability-http-fetch` declares one effect and asks one question. This one
declares three and asks three:

| effect | the question | the bound |
|---|---|---|
| `:network-write` | may this endpoint be reached at all | `:allow-endpoints` |
| `:data-egress` | how much may leave this machine | `:max-prompt-bytes` |
| `:llm-inference` | how much work may be bought | `:max-output-tokens` |

The policy lives in three places, the same three as `http/fetch`:

| where | what it holds |
|---|---|
| `admission.cljc` | the decision, pure — every refusal reachable with no socket |
| `provider.clj` | the effect, closed over one policy taken at construction |
| `artifacts/provider.core.wasm` | the fail-closed core |

## An absent ceiling is not an infinite ceiling

`:llm-inference` is a metered effect: a grant with no ceiling is authority over
someone's money that nobody bounded. So a policy that names endpoints and
models but no `:max-output-tokens` refuses with `:infer/unbounded` — **not**
`:infer/no-policy`, because the operator who wrote allowlists and forgot a
ceiling is somewhere else than the one who wrote nothing.

This is the one place this package deliberately defaults **opposite** to
`cloud.itonami.app.bot-bounds`, and both docstrings name the other so the
difference is stated rather than discovered:

- `bot-bounds` is *enforced when set, reported when absent*. It caps work that
  is already authorised and already paid for under the operator's own key;
  defaulting it to zero would stop live bots on nobody's decision.
- this package is *deny by default*. It is not a cap on authorised work, it IS
  the authorisation.

## The alias trap: resolve first, then admit

The workspace's model SSoT is an alias (`murakumo-main`) that resolves to an
endpoint, and the endpoint moves. A policy written about the **alias** decides
about a name while the request goes wherever that name resolves today — the
decision made about one thing and executed against another, which is the same
shape as following an HTTP redirect after the allowlist has already said yes.

So `admit` takes the **resolved** endpoint and refuses
`:infer/endpoint-unresolved` when it is absent. An alias passed where an
endpoint belongs is refused as unparsable, not resolved.

**This capability resolves nothing.** Resolution is a network *read* and
belongs to `http/fetch` — a different definition CID and therefore a different
grant. There is no default resolver and no default endpoint: baking the alias
host in would make a network read from inside a capability granted a network
write, and freeze a value AGENTS.md says repeatedly not to freeze.

A corollary that the tests pin: **a model outside `:allow-models` never reaches
the resolver.** Otherwise a guest could drive the host into performing network
reads for names the policy already rejects.

## Three things the guest cannot pass

| | why it is in the closure |
|---|---|
| the **policy** | a guest that could pass one could widen its own authority |
| the **endpoint** | a guest that could pass one could send its prompt anywhere |
| the **credential** | a guest that could read one could spend it elsewhere |

The third is specific to this capability. `http/fetch` reads public URLs;
`llm/infer` writes to a metered endpoint under someone's key. If the key
travelled through the ABI it would be in guest memory, and the capability would
be handing out the very thing it exists to hold. The ABI is six `i32`s and can
carry none of the three.

## The core fails closed

```
llm_infer(model-ptr, model-len, prompt-ptr, prompt-len, out-ptr, out-cap) -> i32
  >= 0  bytes written
  -1    refused by policy           (a decision was made)
  -2    transport failed            (a request went out and did not return)
  -3    no host provider bound      (nothing was attempted)
```

Unbound returns `-3`. The hazard is sharper here than for `http/fetch`: an
unbound fetch could look like an empty HTTP response, but an unbound
`llm/infer` would look like **a model that had nothing to say**, which is a
thing models actually do. A capability whose unbound state is indistinguishable
from a real answer is one that appears to work while reaching nothing.

## Eight refusals, eight facts, plus one the provider adds

`:infer/no-policy`, `:infer/unbounded`, `:infer/endpoint-unresolved`,
`:infer/unparsable-endpoint`, `:infer/scheme-not-allowed`,
`:infer/endpoint-not-allowed`, `:infer/model-not-allowed`,
`:infer/prompt-too-large` — each pinned by a test that names it, because a
negative test asserting only "it was refused" counts a refusal for any cause as
the one it meant to exercise (ADR-2608136000 §6).

The provider adds `:infer/no-request-encoder`. `:request-body-fn` is required
and has no default: an inference request's JSON differs per vendor, so a
default would freeze one vendor into an authority package, and hand-writing
that JSON here would put string escaping in the one file whose whole job is
care about what leaves the machine.

## What the policy is careful about

- **the prompt is measured in bytes, not characters.** 400 kana are 1,200 UTF-8
  bytes; a bound measured in characters lets three times its stated size out.
- **an oversized prompt is refused, not truncated.** Truncating would send a
  different prompt than the caller wrote and report success — exactly wrong for
  `:data-egress`.
- **the output ceiling narrows and never raises.** A caller asking for more
  gets the ceiling *and* `:narrowed? true`, so the fact stays visible.
  (`bot-bounds/cap`'s rule, restated where the grant is made.)
- **userinfo cannot carry an allowed name.**
  `https://api.murakumo.cloud@evil.example/` has host `evil.example`.
- **a suffix is not a match.** `api.murakumo.cloud.evil.example` is refused.
- **redirects are never followed**, for the same reason the alias is never
  followed.

## Why this is still `contract-only`

Not for want of a provider, and **no longer because of the allowlist**. Until
2026-09-06 the authority excluded effectful capabilities from
`:reference-implemented` as such; ADR-2609062600 stage 3 changed
`kotoba-core-contracts` so that the allowlist gates only the *unsigned*
concession:

> The allowlist gates the UNSIGNED concession, not effectful capabilities as
> such. Something that carries a real attestation has a publisher who can be
> revoked, which is the property the allowlist was standing in for.

So an attested `llm/infer` provider **can** be `:reference-implemented` today.
`why-this-package-is-still-contract-only` measures exactly that, in both
directions: `:reference-unsigned` is refused with
`:reference-implemented-not-allowlisted`, an attestation over a *different*
artifact is refused with `:attestation-does-not-bind-this-artifact`, and an
envelope binding **this** artifact leaves **no** problem the pure authority can
decide.

Two things remain, and neither is code:

1. **`amu sign-output-set` signs an amu output set**, binding
   `:output-set-sha256` and `:provenance-sha256`. This core is a hand-written
   `.wat` compiled by `wasm-tools` and is not one.
2. **No signing key is designated for capability publication.** Which key may
   publish a capability is an owner decision (ADR-2609062600), and picking one
   is not something to do quietly inside a package that exists to bound
   authority.

The manifest therefore keeps `:contract-only`, with no `:path` and no
`:sha256`, which is what the contract requires of that status.

## Build the core

```sh
wasm-tools parse wasm/llm_infer.wat -o artifacts/provider.core.wasm
shasum -a 256 artifacts/provider.core.wasm
```

## Test

```sh
kbb -M:test
```

27 tests / 90 assertions, no socket opened by any of them.
