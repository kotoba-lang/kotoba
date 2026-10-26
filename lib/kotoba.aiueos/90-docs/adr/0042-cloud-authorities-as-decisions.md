# ADR-0042 — The first cloud client is a decision, not a socket

Date: 2026-08-18

## Status

Accepted and executable. It implements the decision layer of ADR-0041's two
remote authorities. It implements none of that ADR's gap ledger steps 1–5 and
reaches no network.

## Context

ADR-0041 named kotobase the storage authority and murakumo the inference
authority, and said both arrive through the capability broker under the
ADR-0030 origin allowlist. **Nothing checked that.** The allowlist was
admission-time scoping plus a per-URL check in `aiueos.net`; above it there was
no shape for what a cloud request even is, so "arrives through the broker" was
prose a provider could satisfy or not without anything noticing.

Four holes, each of which every future provider would otherwise have to know
about on its own:

1. **A CID is a claim about bytes, and a response is bytes.** Nothing compared
   the two, so a gateway returning the wrong block returned it successfully.
2. **kotobase's `PUT /ipfs/:cid` takes raw CIDv1 only** (root ADR-2608148200).
   An object whose identity CID is dag-cbor is archived under the *raw* CID of
   the same bytes; sending the identity CID earns a 400 `not-raw-sha256`. That
   is a decision available before the request, and this repository is where
   decisions live.
3. **The model alias is a redirect.** `murakumo-main` resolves through a
   mutable KV entry to an endpoint. An allowlist that admitted
   `api.murakumo.cloud` would otherwise authorise whatever that entry names
   next, which is the whole point of having an allowlist.
4. **`alias-for` is not the model to request.** Sending the concrete id the
   alias currently points at freezes the machine at whatever was serving the
   moment it resolved — exactly what root ADR-2607173100 exists to prevent.

## Decision

`aiueos.cloud` states both authorities as decisions. A **plan** is a request
this policy would allow; an **admission** is a verdict about a response a
provider already received. Nothing opens a socket, as in `aiueos.ota`.

- **The plan carries the digest the CID commits to**, and `admit-block` refuses
  a response whose observed digest differs.
- **A response with no digest is denied**, not admitted. The provider not
  having measured is a different fact from the bytes being right, and only one
  of them is a pass (root ADR-2608136000, questions 1 and 2).
- **`plan-block-write` refuses a non-raw CID before the request**, naming the
  codec it found.
- **`admit-model` re-checks the resolved endpoint** against the same allowlist
  that admitted the resolver.
- **The request carries the alias.** An override is honoured — an operator
  pinning a model deliberately is the first step of the root resolution order —
  except for the one override that never is: the id the alias currently
  resolves to.
- **The URL is checked twice**: once when planning, and again at call time
  through `aiueos.net/guarded-fetch`, the function every other provider calls.
  Planning-time approval is not a ticket the call site stops checking.
- **CIDv1 decoding is inlined narrowly.** aiueos is dependency-minimal by
  invariant, so it does not take `kotoba-lang/io-multiformats` — which remains
  the workspace authority for the format and is where a general codec belongs.
  What is inlined is the one shape kotobase and the IPFS gateways emit
  (multibase base32-lower, v1, sha2-256), and it **refuses a codec whose varint
  continues into a second byte** rather than reading the multihash out of the
  wrong offset.

Contract: `resources/aiueos/cloud_contract.edn`, including four named
assurance gaps.

## Executable evidence

- `kbb -M:test -n aiueos.cloud-test`: **24 tests, 68 assertions, 0
  failures**. The CIDs and digests in it were computed outside the code under
  test, so the decoder is checked against an independent oracle rather than
  against itself.
- **Both directions shown, not asserted.** Two deliberate mutations, each
  producing exactly the failure it should and no other:
  - `admit-block` allowing a response that reported no digest → only
    `a-provider-that-did-not-hash-does-not-get-a-pass` fails (2 assertions);
  - dropping the resolved-endpoint re-check → only
    `an-endpoint-the-allowlist-never-admitted-is-refused` fails.
- Full suite: **540 tests, 9103 assertions, 19 failures** — the *same 19 test
  names* as the unmodified tree (516 / 9035 / 19). They are `aiueos.tcb-test`
  classpath assertions that fail under the `:test` alias's extra jars, and the
  test itself says so. The production path `kbb -M:tcb-check` is
  `{:valid? true :files 36 :external 5 :classpath 9 :properties 6}`.

## `aiueos.net` was not in the TCB inventory

Found while adding `src/aiueos/cloud.cljc` to it. `aiueos.net` is the per-URL
check every fetch provider shares — compromising it grants exactly the reach
the operator's allowlist exists to bound — and it had never been pinned. Both
files are now inventoried; `:tcb/files` goes 34 → 36. This is the same class as
`a610ae2` ("the six new decision files were outside the inventory") and is
evidence that the inventory needs a rule about *what must be in it*, not only a
digest check for what already is.

## Remaining boundary

- **No socket.** ADR-0041's gap ledger steps 1–5 (address configuration, DNS,
  TCP as a stream, TLS, HTTP) are untouched. Nothing in this repository has yet
  contacted `kotobase.net` or `api.murakumo.cloud`.
- **This namespace does not hash.** `admit-block` compares a digest the
  provider reports; whether the provider hashed the bytes it actually received
  is the provider's claim, exactly as with `aiueos.ota`'s artifact digests.
- **The alias resolver's answer is not authenticated.** Its endpoint is
  re-checked against the allowlist, but believing the response at all needs
  TLS — step 4.

Next is a hosted-profile provider that executes these plans against the real
endpoints. That is what turns "this policy would allow it" into "this machine
did it", and it is the first point at which a receipt can name bytes that
actually crossed a wire.
