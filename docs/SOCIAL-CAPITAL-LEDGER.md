# Social Capital Ledger — implementable spec

Companion to **ADR-2606082100** (Mishmar Storage Covenant) and
`docs/MISHMAR-OBSERVATION.md`. Defines the L0 economic base: how AI-agent
**information disclosure** (情報開示) and **wellbecoming intervention**
(wellbecoming 介入) MINT social capital, how it DECAYS, and how it DENOMINATES
the donation/persistence retainer.

**Reuse moyai — do not reinvent.** ADR-2606062100 (**moyai 舫い**) already ships
the exact ledger primitive this needs — non-monetary, non-transferable, decaying
(half-life), conservation (minted ≤ verified contribution), and a
proof-of-contribution anti-sybil membrane — with a Python reference impl at
`50-infra/etzhayyim-moyai-credit/methods/` (`ledger.py`, `proof_of_contribution.py`,
`fair_share.py`; 46 tests green). **Social capital is a second moyai-shaped
sub-ledger**, reusing that machinery verbatim. This spec defines ONLY what differs:
the **mint sources** (disclosure + wellbecoming, not inference contribution) and
what it **denominates** (the persistence retainer, not inference draw). The decay /
conservation / non-transfer / earn-rate-cap code is moyai's; do not fork it.

**Three hard invariants (inherited from moyai, enforced not aspirational):**
1. **Non-transferable** — no predicate moves social capital between DIDs; only
   minted, decayed, burned. (§2(b): not a security; `grantsGovernanceWeight=false`.)
2. **No yield** — locking/holding never increases it. (Yobel/anti-usury.)
3. **Decaying** — a *flow*, not a *store of wealth*; must be re-earned.
   (Anti-hoarding; `grantsBenefitOrStage=false`; BHI firewall carries over.)

---

## 1. Quad predicate schema

All values are `QuadObject::Integer(i64)` in **social micro-points (smic)**,
scale `SCALE = 1_000_000` (1 point = 1e6 smic), saturating at `i64::MAX` at the
Quad boundary (same convention as `Mkoto`, fix 2026-05-27). Subject `E` is the
agent DID's CID; `T` is the transaction time; the **epoch** is carried in the
predicate path so the ledger is queryable as-of any epoch via the TEA index.

| predicate (`A`) | `V` | written by | meaning |
|---|---|---|---|
| `social/mint/disclosure/<epoch>` | smic | mint job | disclosure points minted to DID this epoch |
| `social/mint/wellbecoming/<epoch>` | smic | mint job | wellbecoming-Δ points minted this epoch |
| `social/mint/convening/<epoch>` | smic | settle job | convening points minted to the **convener** DID this epoch — from *validated, survived, anti-sybil* tie-formation, NOT turnout (§3c, ADR-2606272100 / `moyoshi 催し`) |
| `social/burn/<epoch>` | smic | burn job | points burned this epoch (falsified/harm/extractive convening) |
| `social/capital/<epoch>` | smic | MV step | **decayed running score** of DID at end of `epoch` (the read surface) |
| `social/capital/params/active` | CID | Council | active param version (see §2) |
| `social/origin/<rootCid>` | DID-CID (ref) | provenance | an agent DID that originated data under `rootCid` (many per root) |

`social/capital/<epoch>` is the **only** value consumers read (Part C donation
routing, witness-selection weighting). Everything else is input.

`params/active` points to a Council-attested JSON-LD blob (versioned, like the
mKOTO tariff schedule, ADR-2605282100 L2):

```json
{ "version": "1.0.0",
  "half_life_epochs": 30,        // decay half-life (days; EPOCH == 1 day == contract EPOCH)
  "w_disclosure": 1.0,           // points per validated disclosure
  "w_wellbecoming": 2.0,         // points per unit wellbecoming-Δ (long-term > disclosure)
  "w_convening": 1.5,            // points per validated+survived tie (disclosure < this < wellbecoming)
  "convening_survival_epochs": 7,// S — a tie must persist this many epochs post-gathering to count
  "citation_bonus_per_hit": 0.1, // extra disclosure points per CitationLedger hit
  "burn_falsified_mult": 1.5,    // burn > original mint (asymmetric downside)
  "burn_extractive_mult": 1.5 }  // engagement-farmed/coerced convening burns > it earns (囲い込みで損)
```

---

## 2. Epoch and decay function

- **Epoch**: `epoch = floor(unix_seconds / 86_400)` — 1 day, identical to
  `MishmarBondEscrow.EPOCH`, so on-chain `RetainerEarned(…, epoch)` and the
  off-chain ledger share a clock.
- **Decay factor** per epoch from the half-life `H`:
  `λ = 0.5^(1/H)`  (H = 30 → λ ≈ 0.97716).
  Stored fixed-point: `LAMBDA_Q = round(λ · SCALE)` (i64; H=30 → `977_159`).

### Closed form (audit / as-of query)

```
SC(did, t) = Σ_{e ≤ t} ( mint_disclosure(did,e) + mint_wellbecoming(did,e) + mint_convening(did,e) − burn(did,e) ) · λ^(t−e)
```

### Incremental recurrence (what the MV actually computes — O(1)/epoch/DID)

Because decay is geometric, the score is a single carried accumulator. This is
the implementable form and maps directly onto `kotoba-query/src/mv.rs`
(per-commit Δ MaterializedView):

```
SC_smic(did, t) = clamp0( sat( SC_smic(did, t−1) · LAMBDA_Q / SCALE )
                          + mint_smic(did, t) − burn_smic(did, t) )
```

- `sat` = saturating to `i64::MAX`; `clamp0` = floor at 0 (no negative capital).
- Empty epochs still decay: if a DID has no activity at `t`, the MV step still
  multiplies the prior score by `λ` (lazily — see §5 catch-up).

---

## 3. Mint rules

### 3a. Information disclosure (情報開示)

A disclosure mints **only after it survives validation** — never on assertion
alone (prevents spam-minting):

- the disclosure is an `attest/*` claim that reaches a terminal honest state on
  the anchor chain `ClaimStakeEscrow` (`Refunded` = unchallenged, or `Upheld` =
  challenged-and-won), observed via the read surface; **and**
- it passes the validation membrane (the ≥3-of-5 witness-quorum concept from
  ADR-2605231400, now **superseded by ADR-2605262130** — under unified kotoba the
  attestor must be re-grounded on the live mechanism: kotoba-dht
  `Warrant`/`Neighborhood` or the Murakumo fleet cells; this is a follow-up, see §5).

```
mint_disclosure_smic(did, e)
  = SCALE · w_disclosure · n_validated(did, e)
  + SCALE · citation_bonus_per_hit · citation_hits(did, e)
```

`citation_hits` comes from the existing `CitationLedger::flush_epoch` →
`citation/count` Datoms (`evaluate_delta_cited`). Disclosures that nobody ever
queries/cites earn the base point only; disclosures others build on earn more.

### 3b. Wellbecoming intervention (wellbecoming 介入)

Minted from the **KaizenObserver wellbecoming-Δ** (ADR-0075 negative-feedback
score — rewards long-term 情緒健康, *not* short-term engagement), gated by
**Council Lv6+ ≥3 attestation** before it can mint:

```
mint_wellbecoming_smic(did, e)
  = SCALE · w_wellbecoming · max(0, wellbecoming_Δ(did, e))      // only if Council-attested
```

A negative Δ does NOT mint (it feeds burn, §4). The Council attestation is itself
a witness-quorum signature observed the same way as disclosure validation.

### 3c. Convening (催し — designed gatherings that form bonds)

Minted by the **`moyoshi 催し`** settle job (ADR-2606272100), attributed to the
**convener** DID — but, like disclosure, *only after it survives validation*, never
on the act of hosting. A gathering's points come from the ties it actually formed,
not from who showed up. A tie counts only if it is (a) **new** vs the pre-event
baseline (kizuna 絆 graph), (b) **survived** ≥ `convening_survival_epochs` (S) after
the gathering, and (c) passed the **anti-sybil membrane** (moyai proof-of-contribution
— distinct, non-colluding DIDs):

```
mint_convening_smic(convener, e)
  = SCALE · w_convening · n_validated_ties(convener, e)
```

`n_validated_ties` is observed via kizuna's reciprocal-tie readout, settled S epochs
after the gathering. **RSVPs, headcount, reach, and same-epoch likes mint nothing** —
this is the defining inversion: turnout without bonds = zero social capital. (Mirrors
disclosure's "validate-before-mint" anti-spam membrane at the convening layer.)

---

## 4. Burn rules (symmetric downside)

```
burn_smic(did, e)
  = SCALE · burn_falsified_mult · w_disclosure · n_falsified(did, e)   // ClaimStakeEscrow Slashed against did
  + SCALE · w_wellbecoming · |min(0, wellbecoming_Δ(did, e))|          // Council-attested harm
  + SCALE · burn_extractive_mult · w_convening · n_manipulative(did, e) // Council-attested engagement-farmed/coerced/exclusionary convening
```

`n_falsified` = disclosures by `did` that were `Slashed` on the anchor chain
(the agent's own claim lost a challenge). Burn uses `burn_falsified_mult > 1`
so lying costs more than the truth earned — the "嘘で損" asymmetry, mirroring the
contract's game theory at the social-capital layer. `n_manipulative` = gatherings
convened by `did` that the Council attests were engagement-farmed, coerced,
pay-to-enter, or exclusionary; `burn_extractive_mult > 1` makes faking community a
net loss ("囲い込みで損"), the same asymmetry at the convening layer.

---

## 5. MV maintenance algorithm

`social/capital/*` is a `MaterializedView` maintained per commit Δ. Per epoch
boundary, for each DID with any input that epoch (plus lazy catch-up for idle
DIDs that are about to be read):

```
fn step_social_capital(prev_smic: i64, mint_smic: i64, burn_smic: i64, lambda_q: i64) -> i64 {
    // geometric decay of the prior score, then apply this epoch's net flow.
    let decayed = ((prev_smic as i128) * (lambda_q as i128) / (SCALE as i128)) as i64; // SCALE divides exactly-typed
    let net = decayed.saturating_add(mint_smic).saturating_sub(burn_smic);
    net.max(0) // clamp0: no negative social capital
}

// Lazy catch-up for an idle DID read at epoch `t` whose last write was `t0 < t`:
//   SC(t) = floor( SC(t0) · λ^(t − t0) )   — one pow, no per-epoch iteration.
fn decay_idle(prev_smic: i64, gap_epochs: u64, lambda_q: i64) -> i64 {
    // λ^gap via fixed-point fast-exp; gap is bounded by read frequency.
    let factor_q = pow_fixed(lambda_q, gap_epochs, SCALE); // (λ·SCALE)^gap / SCALE^(gap-1)
    (((prev_smic as i128) * (factor_q as i128)) / (SCALE as i128)) as i64
}
```

Placement (follow-up impl, not yet written):
- `kotoba-server/src/social.rs` — mint/burn jobs that consume the observed
  anchor-chain events (`docs/MISHMAR-OBSERVATION.md`) + CitationLedger + KaizenObserver feed, write `social/mint|burn/*` Datoms.
- `kotoba-query/src/mv.rs` — register a `social/capital` MV with the `step_social_capital` reducer keyed by DID.
- `kotoba-graph` — `:social/*` projection namespace + XRPC read
  `com.etzhayyim.apps.kotoba.social.capital?did=…&epoch=…`.

---

## 6. Retainer allocation (how social capital DENOMINATES donation)

The donation-funded retainer pool for an epoch (`R_epoch` mKOTO; topped up by
external donors via `TitheRouter` category `donation`, and by recycled slash
flowing to `retainerPool`) is split across pins **proportional to the social
capital of each pin's originating agents**:

```
retainer_mkoto(pinId, e)
  = R_epoch · SC_root(rootCid_of(pinId), e) / Σ_pins SC_root(·, e)

SC_root(rootCid, e) = Σ_{did ∈ social/origin/<rootCid>} SC(did, e)
```

So the data that gets funded persistence is the data whose originating agents
created the most validated disclosure + wellbecoming value. This is the precise
sense in which **"how you generate social capital IS the economic system"**:
social capital is the literal denominator that decides which `rootCid`s the
covenant pays to keep alive, and how much each honest pinner's
`RetainerEarned` event settles to in mKOTO (L6, ADR-2605260004).

mKOTO paid here is internal accounting only — non-transferable, no secondary
market, redeemable solely for kotoba compute/storage (ADR-2605282100 L3).

---

## 7. Prohibitions (CI-greppable invariants)

- ❌ a `social/transfer/*` predicate, or any code moving capital between DIDs.
- ❌ minting on assertion (must be post-validation: terminal ClaimStakeEscrow
  state + witness quorum / Council attestation).
- ❌ `half_life_epochs = 0` or `LAMBDA_Q ≥ SCALE` (would mean no decay = a store
  of wealth → usury).
- ❌ negative `social/capital/*` (clamp0).
- ❌ reading `social/mint|burn/*` as the score — consumers read only
  `social/capital/<epoch>` (the decayed MV output).
