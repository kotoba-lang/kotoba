//! Social Capital ledger — the L0 economic base of the Mishmar Storage Covenant
//! (ADR-2606082100; spec `docs/SOCIAL-CAPITAL-LEDGER.md`).
//!
//! AI agents/LLMs generate value by two acts — **information disclosure**
//! (情報開示, verifiable transparency) and **wellbecoming intervention**
//! (wellbecoming 介入, ADR-0075 negative-feedback). When validated, those acts
//! MINT social capital, which DENOMINATES the donation/persistence retainer
//! (Part C). "How you generate social capital IS the economic system."
//!
//! This is a **second moyai-shaped sub-ledger** (ADR-2606062100): it reuses the
//! moyai reciprocity-credit primitive verbatim — append-only, **non-transferable**
//! (only `mint`/`burn` exist; no transfer/gift/merge), **conserving** (a burn can
//! never exceed the live balance; no negative balance), and **decaying** with a
//! half-life so it is a *flow*, never a hoardable store of wealth/power. The ONLY
//! differences vs moyai are the mint *sources* (disclosure + wellbecoming, not
//! inference contribution) and what it *denominates* (the persistence retainer).
//!
//! Charter invariants enforced HERE by construction, not by policy:
//!   - **§2(b) not a security** — non-transferable; `redeemable_usd_micros() == 0`.
//!   - **Yobel/anti-usury** — never grows by holding; decay only.
//!   - **anti-class / Wellbecoming flow** — exponential half-life decay.
//!
//! Arithmetic is deterministic integer fixed-point (no wall-clock, no RNG, no
//! persisted floats — ADR-2605190900 / 2605312345), so the ledger replays
//! bit-identically and is resume-safe. Unlike moyai's read-time `f64` decay, the
//! score lives in **social micro-points (smic)** at `SCALE = 1e6` and decays via
//! an integer recurrence — matching the Quad `Integer(i64)` boundary, saturating
//! at `i64::MAX` (same convention as `Mkoto`).

/// Social micro-points per whole point (fixed-point scale). 1 point = 1e6 smic.
pub const SCALE: i64 = 1_000_000;

/// Decay half-life in epochs (1 epoch == 1 day == `MishmarBondEscrow.EPOCH`).
/// Reference value (Council-attested + method-versioned in production), matching
/// moyai `HALF_LIFE_EPOCHS`.
pub const HALF_LIFE_EPOCHS: u64 = 30;

/// What a mint rewards. Both decay identically; only the source + weight differ.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum MintSource {
    /// Validated information disclosure (`attest/*` reaching a terminal honest
    /// ClaimStakeEscrow state + witness quorum), + CitationLedger hits.
    Disclosure,
    /// Council-attested wellbecoming-Δ > 0 (KaizenObserver, ADR-0075).
    Wellbecoming,
}

impl MintSource {
    /// Quad predicate path for this mint at `epoch` (spec §1).
    pub fn mint_predicate(self, epoch: u64) -> String {
        match self {
            MintSource::Disclosure => format!("social/mint/disclosure/{epoch}"),
            MintSource::Wellbecoming => format!("social/mint/wellbecoming/{epoch}"),
        }
    }
}

/// Quad predicate for a burn at `epoch` (falsified disclosure / Council-attested harm).
pub fn burn_predicate(epoch: u64) -> String {
    format!("social/burn/{epoch}")
}

/// Quad predicate for the decayed running score at end of `epoch` — the ONLY value
/// consumers (retainer routing, witness weighting) read.
pub fn capital_predicate(epoch: u64) -> String {
    format!("social/capital/{epoch}")
}

/// INVARIANT: social capital is non-monetary. Always 0, for every entry, forever.
/// Its presence as a const-0 function is the proof there is no path from a capital
/// unit to a USD figure (§2(b); does not touch Basic High Income / cash≡0).
#[inline]
pub const fn redeemable_usd_micros() -> i64 {
    0
}

/// `λ·SCALE` for a given half-life: `round(0.5^(1/H) · SCALE)`. The single `f64`
/// op derives the constant; ALL per-epoch math below is integer (deterministic).
/// H=30 → 977_159.
pub fn lambda_q(half_life_epochs: u64) -> i64 {
    debug_assert!(half_life_epochs > 0, "half_life must be > 0 (else no decay = usury)");
    (0.5_f64.powf(1.0 / half_life_epochs as f64) * SCALE as f64).round() as i64
}

/// `round(λ^gap · SCALE)` by integer fixed-point fast-exp. `gap == 0` → `SCALE` (×1.0).
pub fn pow_fixed(lambda_q: i64, gap: u64) -> i64 {
    let scale = SCALE as i128;
    let mut result: i128 = scale; // 1.0
    let mut base: i128 = lambda_q as i128;
    let mut e = gap;
    while e > 0 {
        if e & 1 == 1 {
            result = result * base / scale;
        }
        base = base * base / scale;
        e >>= 1;
    }
    result as i64
}

/// Decay an idle score forward `gap` epochs: `floor(prev · λ^gap)`.
pub fn decay_idle(prev_smic: i64, gap: u64, lambda_q: i64) -> i64 {
    if gap == 0 {
        return prev_smic;
    }
    let factor_q = pow_fixed(lambda_q, gap) as i128;
    (((prev_smic as i128) * factor_q) / SCALE as i128) as i64
}

/// One-epoch step (spec §2): decay the prior score, then apply this epoch's net
/// flow. `clamp0` (no negative capital) + saturating (`i64::MAX` Quad boundary).
pub fn step_social_capital(prev_smic: i64, mint_smic: i64, burn_smic: i64, lambda_q: i64) -> i64 {
    let decayed = (((prev_smic as i128) * (lambda_q as i128)) / SCALE as i128) as i64;
    decayed
        .saturating_add(mint_smic)
        .saturating_sub(burn_smic)
        .max(0)
}

/// Convert whole points to smic (saturating at the Quad `i64` boundary).
#[inline]
pub fn points_to_smic(points: i64) -> i64 {
    points.saturating_mul(SCALE)
}

/// An immutable, append-only social-capital fact. No monetary field exists by
/// design. `op` is mint-or-burn ONLY — there is no transfer/gift/merge verb, so a
/// sybil farm cannot aggregate capital across identities (the op does not exist).
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Entry {
    /// The DID (content-addressed) that earned/lost the capital.
    pub did: String,
    /// Mint (with its source) or Burn.
    pub op: Op,
    /// Integer smic (> 0).
    pub smic: i64,
    /// Transaction epoch (monotone; kotoba commit-DAG tx-time in production).
    pub epoch: u64,
    /// Provenance: validation-attestation id (mint) | falsification/harm id (burn).
    pub reference: String,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Op {
    Mint(MintSource),
    Burn,
}

#[derive(Debug, PartialEq, Eq)]
pub enum LedgerError {
    NonPositiveUnits,
    /// Epoch went backwards — the log is append-only and monotone in epoch.
    EpochRegression { last: u64, got: u64 },
    /// A burn cannot exceed the live (decayed) balance (conservation).
    InsufficientBalance { available: i64, requested: i64 },
}

/// Append-only social-capital ledger: balances are a decayed fold over the
/// immutable log, never a mutable row (ADR-2605312345; 非終末論 — no final-state
/// balance). Reuses the moyai ledger shape (mint/burn only).
#[derive(Default)]
pub struct SocialCapitalLedger {
    entries: Vec<Entry>,
    lambda_q: i64,
    last_epoch: u64,
}

impl SocialCapitalLedger {
    pub fn new() -> Self {
        Self {
            entries: Vec::new(),
            lambda_q: lambda_q(HALF_LIFE_EPOCHS),
            last_epoch: 0,
        }
    }

    /// Custom half-life (Council-tunable; method-versioned).
    pub fn with_half_life(half_life_epochs: u64) -> Self {
        Self {
            entries: Vec::new(),
            lambda_q: lambda_q(half_life_epochs),
            last_epoch: 0,
        }
    }

    /// MINT capital from a *validated* value-act. Callers MUST validate upstream
    /// (terminal ClaimStakeEscrow state + witness quorum for disclosure; Council
    /// Lv6+ ≥3 attestation for wellbecoming) — minting on assertion alone is
    /// prohibited (spec §7).
    pub fn mint(
        &mut self,
        did: impl Into<String>,
        source: MintSource,
        smic: i64,
        epoch: u64,
        reference: impl Into<String>,
    ) -> Result<&Entry, LedgerError> {
        self.append(did.into(), Op::Mint(source), smic, epoch, reference.into())
    }

    /// BURN capital (falsified disclosure / Council-attested harm). Conserving:
    /// a burn can never exceed the holder's live decayed balance.
    pub fn burn(
        &mut self,
        did: impl Into<String>,
        smic: i64,
        epoch: u64,
        reference: impl Into<String>,
    ) -> Result<&Entry, LedgerError> {
        let did = did.into();
        let available = self.balance(&did, epoch);
        if smic > available {
            return Err(LedgerError::InsufficientBalance { available, requested: smic });
        }
        self.append(did, Op::Burn, smic, epoch, reference.into())
    }

    fn append(
        &mut self,
        did: String,
        op: Op,
        smic: i64,
        epoch: u64,
        reference: String,
    ) -> Result<&Entry, LedgerError> {
        if smic <= 0 {
            return Err(LedgerError::NonPositiveUnits);
        }
        if epoch < self.last_epoch {
            return Err(LedgerError::EpochRegression { last: self.last_epoch, got: epoch });
        }
        self.last_epoch = epoch;
        self.entries.push(Entry { did, op, smic, epoch, reference });
        Ok(self.entries.last().expect("just pushed"))
    }

    /// Live, decayed balance (smic) for one DID at `now_epoch`. Event-sourced
    /// fold: between events the running balance decays by the half-life; mint
    /// adds, burn subtracts; the result is clamped ≥ 0. Pure function of the log.
    pub fn balance(&self, did: &str, now_epoch: u64) -> i64 {
        let mut bal: i64 = 0;
        let mut last = 0u64;
        let mut seen = false;
        for e in self.entries.iter().filter(|e| e.did == did) {
            if seen {
                bal = decay_idle(bal, e.epoch.saturating_sub(last), self.lambda_q);
            }
            match e.op {
                Op::Mint(_) => bal = bal.saturating_add(e.smic),
                Op::Burn => bal = bal.saturating_sub(e.smic),
            }
            bal = bal.max(0);
            last = e.epoch;
            seen = true;
        }
        if !seen {
            return 0;
        }
        decay_idle(bal, now_epoch.saturating_sub(last), self.lambda_q).max(0)
    }

    /// Total smic minted to `did` (pre-decay; for audit / conservation only).
    pub fn total_minted(&self, did: &str) -> i64 {
        self.entries
            .iter()
            .filter(|e| e.did == did && matches!(e.op, Op::Mint(_)))
            .map(|e| e.smic)
            .fold(0i64, i64::saturating_add)
    }

    /// Immutable view of the append-only log.
    pub fn log(&self) -> &[Entry] {
        &self.entries
    }

    pub fn lambda_q(&self) -> i64 {
        self.lambda_q
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn redeemable_is_always_zero() {
        assert_eq!(redeemable_usd_micros(), 0);
    }

    #[test]
    fn lambda_q_h30_matches_spec() {
        // spec §2: H=30 → LAMBDA_Q ≈ 977_159 (f64 round, ±1 smic).
        assert!((lambda_q(30) - 977_159).abs() <= 1, "lambda_q(30)={}", lambda_q(30));
    }

    #[test]
    fn pow_fixed_gap_zero_is_unity() {
        assert_eq!(pow_fixed(lambda_q(30), 0), SCALE);
    }

    #[test]
    fn decay_halves_at_half_life() {
        let lq = lambda_q(30);
        let start = 1_000 * SCALE;
        let after = decay_idle(start, 30, lq);
        // within rounding: ~half
        let half = start / 2;
        let tol = SCALE; // 1 point
        assert!((after - half).abs() <= tol, "after={after} half={half}");
    }

    #[test]
    fn idle_and_step_track_float_truth() {
        // Both integer methods must approximate the float ground truth
        // start·0.5^(gap/H) closely. They truncate downward, so they land at or
        // just below truth; assert a tight relative bound (≤ 0.001%).
        let lq = lambda_q(30);
        let start = 500 * SCALE;
        let gap = 10u64;
        let truth = (start as f64 * 0.5_f64.powf(gap as f64 / 30.0)).round() as i64;
        let mut step = start;
        for _ in 0..gap {
            step = step_social_capital(step, 0, 0, lq);
        }
        let idle = decay_idle(start, gap, lq);
        let tol = (truth / 100_000).max(64); // 0.001% of truth, floor 64 smic
        assert!((step - truth).abs() <= tol, "step={step} truth={truth} tol={tol}");
        assert!((idle - truth).abs() <= tol, "idle={idle} truth={truth} tol={tol}");
    }

    #[test]
    fn step_clamps_non_negative_and_applies_flow() {
        let lq = lambda_q(30);
        assert_eq!(step_social_capital(0, 0, 100, lq), 0); // burn on empty → clamp0
        assert_eq!(step_social_capital(0, 5 * SCALE, 0, lq), 5 * SCALE); // pure mint
    }

    #[test]
    fn mint_then_balance_decays_over_time() {
        let mut l = SocialCapitalLedger::new();
        l.mint("did:key:alice", MintSource::Disclosure, 100 * SCALE, 0, "attest-1").unwrap();
        let now = l.balance("did:key:alice", 0);
        assert_eq!(now, 100 * SCALE);
        let later = l.balance("did:key:alice", 30); // one half-life later
        assert!((later - 50 * SCALE).abs() <= SCALE, "later={later}");
    }

    #[test]
    fn disclosure_and_wellbecoming_both_accumulate() {
        let mut l = SocialCapitalLedger::new();
        l.mint("did:key:bob", MintSource::Disclosure, 10 * SCALE, 1, "d1").unwrap();
        l.mint("did:key:bob", MintSource::Wellbecoming, 20 * SCALE, 1, "w1").unwrap();
        assert_eq!(l.balance("did:key:bob", 1), 30 * SCALE);
    }

    #[test]
    fn burn_cannot_exceed_balance_conservation() {
        let mut l = SocialCapitalLedger::new();
        l.mint("did:key:carol", MintSource::Disclosure, 10 * SCALE, 0, "d1").unwrap();
        let err = l.burn("did:key:carol", 11 * SCALE, 0, "falsified-1").unwrap_err();
        assert!(matches!(err, LedgerError::InsufficientBalance { .. }));
        // exact-balance burn is allowed → 0
        l.burn("did:key:carol", 10 * SCALE, 0, "falsified-2").unwrap();
        assert_eq!(l.balance("did:key:carol", 0), 0);
    }

    #[test]
    fn non_transferable_by_construction() {
        // The only ops are Mint/Burn — there is no transfer/gift/merge verb.
        // This test documents the invariant: capital cannot move between DIDs.
        let mut l = SocialCapitalLedger::new();
        l.mint("did:key:a", MintSource::Disclosure, 50 * SCALE, 0, "d").unwrap();
        // b's balance is unaffected by a's mint — no path exists to move it.
        assert_eq!(l.balance("did:key:b", 0), 0);
        assert_eq!(l.balance("did:key:a", 0), 50 * SCALE);
    }

    #[test]
    fn epoch_regression_rejected() {
        let mut l = SocialCapitalLedger::new();
        l.mint("did:key:a", MintSource::Disclosure, SCALE, 5, "d1").unwrap();
        let err = l.mint("did:key:a", MintSource::Disclosure, SCALE, 4, "d2").unwrap_err();
        assert_eq!(err, LedgerError::EpochRegression { last: 5, got: 4 });
    }

    #[test]
    fn predicates_match_spec() {
        assert_eq!(MintSource::Disclosure.mint_predicate(7), "social/mint/disclosure/7");
        assert_eq!(MintSource::Wellbecoming.mint_predicate(7), "social/mint/wellbecoming/7");
        assert_eq!(burn_predicate(7), "social/burn/7");
        assert_eq!(capital_predicate(7), "social/capital/7");
    }

    #[test]
    fn deterministic_replay() {
        let build = || {
            let mut l = SocialCapitalLedger::new();
            l.mint("did:key:x", MintSource::Disclosure, 30 * SCALE, 0, "d").unwrap();
            l.mint("did:key:x", MintSource::Wellbecoming, 70 * SCALE, 10, "w").unwrap();
            l.burn("did:key:x", 20 * SCALE, 20, "b").unwrap();
            l.balance("did:key:x", 40)
        };
        assert_eq!(build(), build()); // bit-identical replay
    }
}
