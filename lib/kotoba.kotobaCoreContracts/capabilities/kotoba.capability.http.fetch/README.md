# capability-http-fetch

Atomic authority package for `http/fetch`.

- imports: `#{:http-fetch}`
- effects: `#{:network-read}`
- default policy: `:autonomous`
- semantic definition CID: `bafyreigwzveiuxfkyk7tgf2eu7suzkhyj4532gyvpc7hcsa6adzcag55va`
- hash contract CID: `bafkreiflhj3fslsbh7okdas2fzlhmogai64x6p3lkla6gtr7berbp7ftvi`
- provider status: `contract-only` — **and the reason changed on 2026-09-06**.
  See "Why this is still contract-only" below.

The repository name is a discovery alias. The semantic definition CID is the
immutable import identity. Importing it does not grant runtime authority:
Tamaki must request it explicitly and Kototama must admit the sealed envelope.

## The first effect that leaves the machine

The eight capabilities that ship a provider today are `:pure-compute`,
`:codec`, `:crypto`, `:randomness` and `:clock`. **Not one of them can reach
anything**, so not one of them needed an egress policy and not one of them has
one.

That difference is the whole design. An unconstrained `http/fetch` is not a
narrower authority than `process/spawn`; it is a wider one with a friendlier
name. So the policy IS the capability here, and it lives in three places on
purpose:

| where | what it holds |
|---|---|
| `egress.cljc` | the decision, pure — every refusal reachable in a test with no socket |
| `provider.clj` | the effect, closed over one policy taken at construction |
| `artifacts/provider.core.wasm` | the fail-closed core |

### The guest cannot widen its own egress

`provider` closes over the allowlist. The guest hands in a URL and nothing
else — there is no field in the ABI through which it could pass a policy, and
`the-policy-is-closed-over-and-not-an-argument` asserts that rather than
trusting the table to stay that shape.

### The core fails closed

Every other reference core does the work: sha256 hashes, xorshift produces
bytes, the clock reads a counter. A wasm core has no socket and no amount of
code here gives it one, so this one returns `-3` from every call. An embedder
that links it and forgets to bind a host implementation gets "no provider" —
never silence, and never a zero-length body that reads as a successful empty
response. A capability whose unbound state is indistinguishable from an empty
answer is one that appears to work while reaching nothing.

```
http_fetch(url-ptr, url-len, out-ptr, out-cap) -> i32
  >= 0  bytes written
  -1    refused by egress policy      (a decision was made)
  -2    transport failed              (a request went out and did not return)
  -3    no host provider bound        (nothing was attempted)
```

Three negatives because they are three different facts. `bin/itonami` keeps the
same two apart in its exit codes and says why: "'The server said no' is a
measurement; 'nothing was listening' is not" (ADR-2608136000).

### Deny by default, and `no-policy` is its own answer

A provider built without an allowlist refuses everything with
`:egress/no-policy`, **not** `:egress/host-not-allowed`.
`manifest/bot-allowances.edn` states the same floor for spending — "no policy
is not permission" — and the distinction matters for the same reason: an
operator who forgot to write a policy and an operator whose policy excludes
this host have different next actions.

Five refusals, five reasons: `:egress/no-policy`, `:egress/host-not-allowed`,
`:egress/scheme-not-allowed`, `:egress/method-not-allowed`,
`:egress/unparsable-url`. Each is pinned by a test, because a negative test
that asserts only "it was refused" counts a refusal for any cause as the one it
meant to exercise.

### What the policy is careful about

- **userinfo cannot carry an allowed name.**
  `https://api.murakumo.cloud@evil.example/` has authority
  `api.murakumo.cloud@evil.example` and **host** `evil.example`.
- **a suffix is not a match.** `api.murakumo.cloud.evil.example` is refused.
- **redirects are never followed.** A 302 to a host outside the allowlist would
  carry the request there with the policy already satisfied — the decision was
  made about the first URL and executed against the second. Following redirects
  would make `admit` advisory.
- **a write is not this capability.** `POST`/`PUT`/`DELETE` are refused:
  `:capability/effects` says `#{:network-read}`, and admitting a write would
  make that declaration false. Writes are `capability-http-post`, a different
  definition CID and therefore a different grant.
- **the body has a cap the caller cannot raise.**

## Why this is still `contract-only`

Not for want of a provider, and **no longer because of the allowlist**. This
section said the opposite earlier on 2026-09-06 and was overtaken the same day:
ADR-2609062600 stage 3 changed `kotoba-core-contracts` so that
`reference-implemented-allowlist` gates only the *unsigned* concession.

> The allowlist gates the UNSIGNED concession, not effectful capabilities as
> such. Something that carries a real attestation has a publisher who can be
> revoked, which is the property the allowlist was standing in for.

So an attested `http/fetch` provider **can** be `:reference-implemented` today.
`why-this-package-is-still-contract-only` measures that rather than asserting
it, in three directions: `:reference-unsigned` is refused with
`:reference-implemented-not-allowlisted`, an attestation over a *different*
artifact is refused with `:attestation-does-not-bind-this-artifact`, and an
envelope binding **this** artifact leaves **no** problem the pure authority can
decide.

The old paragraph was prose, so nothing failed when it stopped being true. That
is why the reason is now a test.

Two things remain, and neither is code:

1. **`amu sign-output-set` signs an amu output set**, binding
   `:output-set-sha256` and `:provenance-sha256`. This core is a hand-written
   `.wat` compiled by `wasm-tools` and is not one.
2. **No signing key is designated for capability publication.** Which key may
   publish a capability is an owner decision (ADR-2609062600).

The manifest therefore keeps `:contract-only`, with no `:path` and no
`:sha256`, which is what the contract requires of that status.

## Build the core

```sh
wasm-tools parse wasm/http_fetch.wat -o artifacts/provider.core.wasm
shasum -a 256 artifacts/provider.core.wasm
```

## Test

```sh
kbb -M:test
```

19 tests / 51 assertions, no socket opened by any of them.
