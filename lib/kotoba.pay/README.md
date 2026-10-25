# pay

**On-chain creator-payment rail primitives (USDC on Base L2) — pure
kotoba-lang (`.cljk`), zero network I/O, zero key custody.**

Re-homed from `@etzhayyim/sdk`'s payment surface (`pay.ts`: `pay()` /
`payStream()` / `splitDistribute()` / escrow) as a **vendor-neutral
kotoba-lang common library** — superproject ADR-2607092700. The move
resolves a structural mismatch: the etzhayyim substrate's payment-purpose
doctrine prohibits external `tip` / `subscription` / `purchase`, which is
exactly what vendor creator platforms (jk-luxury `club-shinshi`,
`net-babiniku`) need to settle. Vendor apps now consume this library under
their own operating entity (JK株式会社 / "Shinshi Inc."); etzhayyim keeps
its donation-only rail on its own side of the substrate axis.

## What it provides (pure, tested)

- **USDC units** — `parse-usdc` / `format-usdc` (6-decimal base units,
  truncating parse matching the original `parseUsdc`).
- **Streaming flow rates** — `flow-rate-per-second "10.00 / month"`
  (Superfluid-shaped, adapter-agnostic).
- **Revenue splits** — `split-allocations` / `creator-platform-split`
  (the 80/20 creator take; rounding dust goes to the creator; totals are
  invariant).
- **Monetization capability** — the signed / scoped / expiring / revocable
  payment-authorization shape from ADR-2607071000
  (`net.babiniku.monetization.capability`), generalized: `capability-errors`,
  `valid-capability?`, `expired?`.
- **Receipts + entitlement** — `->receipt` (bigint-safe string amounts on
  the wire) and `entitle`, the **verify-before-honor** decision: an
  entitlement is granted only when a host-supplied on-chain verification
  confirms the settlement. Never grant on an unverified claim — the exact
  gap (`verify()` unimplemented) that kept the original SDK's monetization
  HARD-held.
- **`PayRail` protocol** — the injected seam for every on-chain effect,
  with `unprovisioned-rail` as the honest default (every operation HOLDs
  with `:pay/unprovisioned-capability`; never fake a settlement).
- **`pay.rail.base-l2`** — the FIRST REAL RAIL. One-shot USDC transfer on
  Base L2 as an ERC-4337 UserOperation, via
  [kotoba-lang/base-l2](https://github.com/kotoba-lang/base-l2). It
  provisions exactly one of the six methods:

  | method | |
  |---|---|
  | `-pay!` | **real** — `transfer(address,uint256)` through the caller's bundle |
  | `-pay-stream!` / `-pay-stream-stop!` | HOLD — no Superfluid adapter exists |
  | `-split-distribute!` | HOLD — no 0xSplits adapter exists |
  | `-escrow-open!` / `-escrow-release!` | HOLD — no Safe-escrow adapter exists |

  The five HOLD **byte-identically to `unprovisioned-rail`**, asserted by a
  test, so nothing downstream can tell a not-yet-built rail from a
  not-yet-built method. A rail that quietly answered all six would be worse
  than the unprovisioned one, because a HOLD is visible and a fabricated
  receipt is not.

  Refusals are holds, not exceptions — `:pay/unresolvable-payee`,
  `:pay/invalid-amount`, `:pay/settlement-reverted` — so a caller cannot
  swallow one in a `try` and proceed. An unresolvable payee never falls back
  to `:to` itself, a zero address, or a default: USDC sent to a guessed
  address is not recoverable. Transport failures (RPC down, bundler
  unreachable) are *not* payment decisions and propagate.

## What it deliberately does NOT do

- No chain RPC, no PDS writes, no HTTP — *the core does none of these*, and
  that is still true: `pay.rail.base-l2` is pure over an injected bundler and
  an injected transport, so it moves no bytes itself either. Hosts back
  `PayRail` with real adapters:
  [kotoba-lang/base-l2](https://github.com/kotoba-lang/base-l2)
  (JSON-RPC + ERC-4337 sponsored writes — **now wired, for `-pay!`**),
  [kotoba-lang/treasury](https://github.com/kotoba-lang/treasury)
  (on-chain USDC verification + append-only ledger),
  [kotoba-lang/wallet](https://github.com/kotoba-lang/wallet)
  (non-custodial signing). Superfluid / 0xSplits / Safe-escrow adapters are
  still follow-ups; until then those rail methods HOLD honestly.
- No private keys. Signing stays on the payer's device (passkey smart
  wallet or non-custodial wallet) — a platform-held signing key is
  prohibited by design, same as the original SDK's rule.
- No fiat. Fiat rails (ISO 8583 / ISO 20022) live in
  [kotoba-lang/kessai](https://github.com/kotoba-lang/kessai) — a sibling,
  not a dependency. A consuming app can run crypto + fiat dual-rail by
  composing both.

## x402 (HTTP 402) protocol — `pay.x402`

The `pay.x402` namespace implements the **x402** open micropayment protocol
that Cloudflare's [Monetization Gateway](https://blog.cloudflare.com/monetization-gateway/)
standardizes — in-band `402 Payment Required`, price + asset + pay-to in the
response, buyer pays a stablecoin and re-requests with an `X-PAYMENT` header,
facilitator verifies, resource served with an `X-PAYMENT-RESPONSE` receipt. No
redirect, no checkout, no seller onboarding — and it works for autonomous
**agent** buyers, not just human wallets.

We are our **own facilitator** (via kotoba-lang/treasury's on-chain verify)
instead of a closed vendor service, so this is not gated on any waitlist and
settles on Base L2 / USDC we already control. Pure protocol codec, same
zero-dep / zero-I/O / zero-custody invariants as the rest of the lib:

- `payment-requirements` / `challenge` — build the 402 body (price via
  `parse-usdc`, micros on the wire).
- `encode-header` / `decode-header` — portable UTF-8 base64 for the
  `X-PAYMENT` / `X-PAYMENT-RESPONSE` envelopes (JSON stays with the host to
  keep zero-dep).
- `payload-errors` / `acceptable?` — pure validation of a decoded payment
  against the requirements (scheme / network / recipient / amount / expiry) for
  both the canonical `exact` EIP-3009 scheme and a `transaction` (tx-hash)
  scheme that maps 1:1 onto the existing treasury/verify path.
- `authorize` — the verify-before-serve decision (the x402 form of `entitle`):
  serve only when the host confirms on-chain settlement, else hold at 402.

Design: superproject ADR-2607093100.

## Facilitator gateway — `pay.facilitator`

`pay.facilitator` is the pure brain of a central x402 **facilitator/gateway**
service (deployed as `gftdcojp/nexus-x402`, superproject ADR-2607093300). Where
`pay.x402` is the wire codec, this is the multi-seller **rules engine** + the
standard x402 facilitator decisions:

- **Rules engine** — a seller registry (`{:seller :method :path-prefix :usd
  :pay-to :chain :scheme}`, first structural match wins). Many sellers
  (shinshi / murakumo / kotobase, each with its OWN treasury) share one
  facilitator that holds no keys: `match-rule`, `rule->requirements`.
- **`verify`** — the x402 `/verify` decision (`{:isValid :invalidReason
  :payer}`): pure shape/economic checks + the host's on-chain verdict.
- **`settle`** — the x402 `/settle` decision (reuses `authorize`).
- **`gate`** — the end-to-end gateway decision (`:pass` / `:challenge` /
  `:serve` / `:hold`), transport-independent.
- **`discovery`** — the `/.well-known/x402` facilitator discovery document.

All pure — the host (nexus-x402) injects on-chain verify/settle via
kotoba-lang/treasury + base-l2. This lets sellers delegate verification to one
edge-hosted facilitator instead of each vendoring the whole gate.

### Opening the registry to third parties

Everything above already worked with one seller: the operator. Admitting
*other people's* sellers is the change that turns the operator from the
counterparty on every flow into the market those flows run through — the
structural move a system-dynamics pass over
[`kotoba-lang/dynamics`](https://github.com/kotoba-lang/dynamics)' archetype
catalog ranked third of six for the three-sphere economy
(com-junkawasaki/root adr-ledger seq 66, 2026-07-25), grounded in Visa earning
$40B on **$17T of other people's transactions** and in ERC-20's real leverage
being that every later token project became free demand surface for Ethereum.

Two things had to be true first, and one of them was a live hole:

- **`match-rule` treats `:seller nil` as "matches ANY seller".** Fine with one
  tenant. An authorization hole the moment anyone else can add a rule —
  nexus-x402 routes `/gateway/<seller>/<path>`, so a single wildcard rule would
  collect payment across every seller's namespace. `open-registry-rule-errors`
  rejects it (plus reserved/malformed seller ids, relative prefixes, and the
  namespace-swallowing `"/"`). `rule-errors` is unchanged — existing
  single-tenant callers are unaffected.
- **Shadowed rules.** First-match-wins is intended semantics, but a seller who
  registers a specific price behind a general one gets silently underpaid.
  `shadowed-rules` reports it at registration instead of at reconciliation.

`register-seller` is **all-or-nothing** (a half-registered seller is worse than
an unregistered one), refuses registering on someone else's behalf, refuses a
prefix already covered by a *different* seller's rule, and appends at the end
so **existing sellers always keep priority over newcomers** — registration can
never re-route traffic that already had a home.

```clojure
(fac/register-seller rules "acme"
  [{:method "GET" :path-prefix "/acme/reports/" :usd "0.25" :pay-to "0xAcmeTreasury"}])
;; => {:admitted? true :rules [...] :warnings []}
```

### The protocol fee is recorded, not collected

`protocol-fee` computes 500 bps (5% — the same cut ADR-2607995000's membrane
table already applies to fiat/USDC→credits, so the economy has *one* fee
number) in exact integer USDC micros, floored, on `:maxAmountRequired`. An
unparseable amount yields `nil`, never `0`.

`:collectible?` is **always false**, and the reason rides in-band rather than
in a comment: this facilitator holds zero keys by design, payment goes buyer →
the seller's own treasury directly, and an x402 requirement carries exactly one
`payTo`. Splitting a payment atomically would need a splitter contract that is
not deployed, and deploying one that custodies third-party money is a separate,
higher-stakes decision. So this is the **record** layer only — the same
record / custody / governance separation ADR-2607995000 §2 already applies to
the treasury. Anything that reads a non-nil `:amount-micros` as revenue
*received* is wrong.

`settlement-record` carries the seller on every row, which makes **acceptance
density** — how many distinct sellers have ever settled — a ledger query rather
than an assertion. That count is **1** today, and the growth analysis named it
the binding constraint on the whole economy.

### Sellers can price in credits, not only USDC

`credits-requirements` / `rule->accepts` / `credits-gate` let a seller price a
resource in **murakumo credits**, in USDC, or in both. A 402 then carries both
options in x402's own `accepts` array — USDC first, so a buyer with no credits
account is never stuck reading past the option they cannot use. The pre-credits
`:requirements` key is unchanged, so callers that never look at `:accepts`
behave exactly as before.

This required amending an accepted ADR, which is worth stating plainly rather
than burying: **ADR-2607995000's membrane table is exhaustive** ("ここに無い流れ
は禁止") and holder-to-holder credits payment was not in it, so it was forbidden.
`adr-ledger` seq 73 adds exactly one row — credits → third-party seller,
credits-denominated — and changes nothing else. Still forbidden, untouched:
credits→fiat/USDC (both directions), credits↔EN, EN↔USDC.

**Transferability is not redeemability.** A credit paid to a seller still cannot
leave the economy, so §1's structural non-speculation proof (neither internal
unit is redeemable, therefore neither can be an investment) survives intact. The
requirement payload carries `:redeemable false` in-band so a seller integrating
against it cannot book received credits as money without ignoring a field that
says not to.

`credits-gate` is deliberately **separate from `gate`** rather than a branch
inside it: `gate` routes to `pay.x402/authorize`, whose whole job is validating
an on-chain payload (asset, network, `payTo` address, EIP-3009 authorization). A
credits payment has none of those, and a validator forced to accept two
unrelated payload shapes is one refactor away from accepting an on-chain payload
with a credits verdict attached.

It also **cannot decide affordability**. `credits-verdict` is host-injected
exactly like `onchain-verdict`, computed from
`murakumo.infer.credits/balances` + `ledger-violations`; a missing verdict is
treated as insufficient, never as sufficient. And `:serve` returns a
`:transfer` **to be recorded**, not one performed — this layer holds no ledger
and moves nothing, the same custody-free stance it takes for USDC.

`credits-accepting-sellers` counts distinct sellers who accept credits from the
registry. **0 today.**

## Consumers

- `jk-luxury/club-shinshi` — creator subscription / PPV / tip (the
  `:hyp/club-shinshi-creator-take` gate: creator GMV > ExoClick ad
  revenue).
- `jk-luxury/net-babiniku` — character subscribe / tip / PPV
  (ADR-2607062200's proposal shapes map 1:1 onto the capability here).

## Dev

```bash
kbb -M:test    # cognitect test-runner
kbb -M:lint    # clj-kondo, errors fail
```

Apache-2.0.
