# Becoming an ENGI/EN L1 witness — participation terms (draft)

**Status: internal draft, not yet distributed to any external party.**
This document exists so the operator (`com-junkawasaki`) has a concrete,
reviewed starting point *before* approaching any real prospective witness
operator — it is a technical/participation specification, not a public
announcement, and nothing in it should be read as an offer, solicitation,
or guarantee. See [ADR-2607994000](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2607994000-engi-l1-permissionless-staking-equivocation-slashing.md)
for the full design rationale.

## What a witness does

A witness runs a node that participates in `kotoba-lang/engi`'s L1
(chained-HotStuff BFT, [ADR-2607993000](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2607993000-engi-l1-byzantine-consensus-en-currency.md)):
voting on which batches ("blocks") of ENGI/EN mutual-credit transfers
become finalized. This is a small, narrow-scope job — one operation
(vote on block validity/order) over one domain (ENGI/EN transfers). It is
**not** a general-purpose blockchain validator role, and there is no other
workload riding on this consensus today.

## How to participate (permissionless — no application/approval step)

1. Hold a `did:key` identity (self-generated, no registration with the
   operator required).
2. **For the `:ordering` role, post nothing.** The bond floor for ordering
   is **0** (`inga.stake/bootstrap-ordering-min-bond`) — see "Bond
   requirement" below for why, and for what would change it. For the
   `:recompute` role, bond external collateral (USDC on Base L2, reusing
   the existing kotobase-ecosystem off-ramp boundary,
   [ADR-2607101100](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2607101100-engi-mutual-credit-kotobase-native-design.md)
   §4) meeting that role's floor. **No escrow contract is deployed, so
   `:recompute` bonding is still not possible today**; `:ordering`
   participation no longer waits on one.
3. Once bonded and past the next epoch boundary, your `did:key` is
   automatically part of the witness set — no vote by existing witnesses,
   no application to `com-junkawasaki`, is required or possible under this
   design.
4. Run the witness node software (vote-signing + the wire protocol over
   `murakumo/overlay`) and begin voting on proposed blocks.

## Bond requirement — asymmetric by role (revised 2026-07-25)

An earlier draft of this document quoted a single **`min-bond`: 500
(USDC-equivalent)** across both roles. That figure has been withdrawn,
because it could not be justified and it was the binding barrier to entry:
it was quoted while no escrow contract existed to accept it, and the count
of external witnesses who have ever bonded is **0**.

The floor is now sized to what each role actually guards.

### `:ordering` — floor **0**

A bond exists to make an attack's upside smaller than the collateral it
forfeits. Sizing one therefore requires knowing what a successful attack is
worth. For ordering, the protocol cannot know that:

- EN is **non-priced, non-redeemable, and convertible to nothing**
  (ADR-2607995000 §1 membrane rules). There is no exchange rate to size a
  bond against.
- This is *not* a claim that equivocation is harmless. A counterparty who
  hands over real goods for double-spent EN loses something real. But that
  loss is **the counterparty's own private valuation of those goods** —
  unpriced, and unavailable to the protocol.
- Putting an external price on EN in order to compute a bond would reopen
  exactly the back door ADR-2607995000 §3 closed when it repealed
  per-transfer external-asset fees.

So the ordering floor is a **governance parameter, not a formula** — set by
the same stake-weighted 2/3 vote used for block finality (ADR-2607994000
Decision #8), with a bootstrap value of 0 and an **objective trigger** for
revisiting it rather than a number chosen to look prudent.

**The trigger:** the first EN transfer between two agents where neither is
the operator. As of 2026-07-25 that count is measurable rather than
assumed — `engi.metrics/funnel-from-entities` reports
`:external-counterparties` from the ledger itself, and
`bin/engi_metrics.cljk` runs it against live kotobase.net. When that stops
being empty, there is something for an equivocation to extract, and the
floor gets revisited with real data instead of a guess.

**The honest cost, stated rather than buried:** an unbonded witness set has
**no Sybil resistance**. Anyone can mint arbitrarily many `did:key`s for
free. `inga.stake/quorum-met?` therefore returns
`{:basis :counted-unbonded :sybil-resistant? false}` in that regime — a
**liveness arrangement among an enumerated roster, not Byzantine security**,
and the code refuses to let a caller read it as the latter. Do not run this
regime once there is value at stake; that is what the trigger is for.

### `:recompute` — floor set by the payment custodian

Here the value at risk *is* already denominated in the bond asset: a buyer
paid real USDC for an inference, and the witness attests it was computed
honestly. A fixed floor is straightforwardly correct, and it applies from
the first paid request. `inga.stake/default-bond-policy` deliberately leaves
this **nil** rather than inventing a number — the floor belongs to whoever
custodies the compute payments (cloud-murakumo), and a nil floor means the
role is **not admissible** until a policy supplies one (fail-closed).

Collateral, where posted, is **at risk** — see "Risks" below. It is not a
deposit held for safekeeping; it is explicitly slashable.

## Expected returns (no guarantee, no fixed rate)

ENGI/EN cannot mint new EN as a witness reward — doing so would break its
core net-zero invariant.

The per-finalized-transfer external fee this document previously described
(ADR-2607994000 Decision #7) was **repealed** by ADR-2607995000 §3: charging
an external-asset fee per EN transfer puts an external price tag on EN's
movement, which breaks the non-pricing invariant through the back door.

What replaced it: witness duty is **labour**, and labour mints **credits**
(murakumo memory×time) at a flat rate per finalized block — deliberately not
proportional to EN volume, since proportionality is what would re-attach a
price to EN. Be clear-eyed about what that means for an external
participant: **credits are non-redeemable by design** (ADR-2607995000 §1
forbids credits→fiat), so they are compensation usable inside this economy,
not income convertible outside it. ADR-2607995000 says so in its own
Consequences section rather than leaving you to discover it.

If external-asset compensation is required, the path is a stake-weighted 2/3
governance vote to pay for the service out of real on-ramp revenue — which
means it is bounded by revenue that, as of this writing, is **0 active
Stripe subscriptions and 0 settled x402 payments**. No rate is offered here
because there is nothing yet to pay one from.

Do not treat participation as an investment with an expected yield.

## Risks (read before considering real participation)

- **This is early-stage, experimental infrastructure.** The consensus and
  staking namespaces moved to [`kotoba-lang/inga`](https://github.com/kotoba-lang/inga)
  on 2026-08-03 (`inga.consensus` / `inga.stake` / `inga.power`); they run
  over real WebSockets in inga's own harness but have **no production
  deployment, no external security audit, and no long-running history**.
- **Your bond can be slashed** for equivocation (signing two conflicting
  votes at the same height), and for nothing else. Silence, network
  failure, censorship, disagreeing with a majority and declining to judge
  are all explicitly NOT slashable (ADR-2607994000 Decision #5,
  ADR-2608055000). Run your signing key carefully — a compromised or
  duplicated signing key is the realistic way this happens, not deliberate
  misbehavior.

- **Read this one before committing funds: the CHAIN cannot check the
  proof, so a human key can act on a claim.** `inga.stake` and
  `inga.power` verify equivocation evidence cryptographically off-chain,
  and `inga.power` refuses a slash whose evidence is missing, names
  someone else, fails signature verification, or has already been punished.
  The escrow contract holding your collateral **cannot re-run that check**:
  EVM's `ecrecover` is secp256k1-only and Ed25519 verification is not
  implemented on-chain. So on-chain, a slash is an assertion by the
  `arbiter` key, not a proof.

  What stands between you and a baseless confiscation, as of the
  2026-08-05 rewrite of `engi-witness-escrow`:

  - a **timelock** (≥1 day, ≤30 days) between the claim and any movement
    of funds, with the evidence reference published at claim time — you
    learn of an accusation, and can answer it, before the money moves;
  - a **guardian** key, separate from the arbiter, that can veto a pending
    slash but can never create one, and which rotates itself so the
    arbiter cannot remove it;
  - **vetoed evidence is spent** — the same claim cannot be resubmitted.

  That is forced delay, forced publicity and split authority. **It is not
  adjudication**, and you should not treat it as such: two colluding keys
  can still confiscate a bond that no proof supports. The permanent fix is
  on-chain verification of the proof itself, at which point both keys
  should disappear rather than be narrowed. Until then, assess who holds
  those keys as carefully as you assess the protocol.

- **The arbiter can also freeze your exit, not just take your bond.** A
  pending slash blocks withdrawal. `expireSlash` bounds any single
  proposal — anyone, not just the operator, can clear a stale one — but it
  does not bound a *sequence*. An arbiter willing to keep re-proposing,
  with a fresh evidence reference each time (which costs it nothing), can
  keep you from exiting indefinitely, in cycles of roughly the slash
  timelock plus a 7-day execution window. The guardian can veto each one,
  but only if it is present and willing every cycle.

  No arrangement of the contract's functions closes this. Any bond that
  can be slashed can be frozen by an accusation, and the only thing that
  makes an accusation accountable is being able to **check** it — exactly
  what the contract cannot do today. Assume, when you bond, that your
  ability to leave depends on the arbiter choosing not to do this.
- **No guaranteed liquidity or return of principal.** Unbonding has a
  mandatory delay (`unbond-delay-epochs`, currently 3) before withdrawal,
  and a **pending slash blocks withdrawal** for as long as the timelock
  plus a 7-day execution window — after which anyone, not just the
  operator, may expire the proposal and unblock your exit.

  Two things the 2026-08-05 escrow rewrite fixed, which you would
  otherwise have had to take on trust: the unbonding delay now has an
  **immutable 30-day ceiling** that governance cannot raise, and your
  maturity deadline is **snapshot when you request unbonding**, so a later
  change to the delay cannot extend an exit already in progress. Before
  that, one call could have frozen every bond holder out of their own
  funds permanently.
- **No regulatory or legal review has been performed** on any of this —
  anyone considering real participation, on either side, should treat that
  as entirely open and get their own advice before committing real funds.
- **Parameters (bond floors, unbond delay, compensation) can change** via
  governance vote among current witnesses — participation terms are not
  fixed for the life of the system. In particular, the `:ordering` floor of
  0 is explicitly expected to rise once the trigger above fires.
- **While the `:ordering` floor is 0, that role's quorum is a head count
  with no Sybil resistance** (`:basis :counted-unbonded`). It is a liveness
  arrangement among an enumerated roster, not Byzantine fault tolerance.
  Anyone relying on this for safety today would be relying on something
  that is not there, which is why the code returns
  `:sybil-resistant? false` in-band rather than a bare boolean.

## Non-goals of this document

This is not a pitch deck, not a token sale, and not a request for funds.
It is a technical specification of a not-yet-deployed mechanism, written
so that *if* the operator later decides to approach real prospective
witness operators, the terms being offered are the ones actually reviewed
and designed (ADR-2607994000) rather than improvised in conversation.
