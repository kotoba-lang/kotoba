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
//!
//! Lives in `kotoba-query` (the query/MV engine) so the incremental
//! [`SocialCapitalView`] MaterializedView reducer and the [`SocialCapitalLedger`]
//! share one decay primitive; `kotoba-server::social` re-exports this module.

use crate::datom::{Datom, Value};
use crate::delta::Delta;
use kotoba_core::cid::KotobaCid;
use std::collections::HashMap;

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
    debug_assert!(
        half_life_epochs > 0,
        "half_life must be > 0 (else no decay = usury)"
    );
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

// ── Mint engine (the upstream of the loop, ADR-2606082100 §3/§4) ──────────────
//
// Turns *validated* value-acts into `social/mint|burn` Datoms. Validation is
// enforced by the type system: a `Validated*` value cannot be constructed from an
// unvalidated act (spec §7 — "minting on assertion alone is prohibited"). The
// actual I/O that produces these inputs (anchor-chain `eth_getLogs` for terminal
// ClaimStakeEscrow state, CitationLedger hits, KaizenObserver wellbecoming-Δ) is a
// thin server-side job (follow-up); the deterministic weighing + Datom emission
// lives here so it is testable and replay-stable.

#[inline]
fn sat_i64(x: i128) -> i64 {
    if x > i64::MAX as i128 {
        i64::MAX
    } else if x < i64::MIN as i128 {
        i64::MIN
    } else {
        x as i64
    }
}

/// Economic params — the `social/capital/params/active` blob (spec §1). Weights
/// are integer **milli-weights** (×1000) so all minting math is deterministic
/// integer (no persisted floats). Council-attested + method-versioned in production.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct MintParams {
    pub half_life_epochs: u64,
    /// points per validated disclosure (1000 = 1.0).
    pub w_disclosure_milli: i64,
    /// points per unit wellbecoming-Δ (2000 = 2.0; long-term > disclosure).
    pub w_wellbecoming_milli: i64,
    /// extra disclosure points per CitationLedger hit (100 = 0.1).
    pub citation_bonus_milli: i64,
    /// burn > original mint for falsified disclosure (1500 = 1.5 — asymmetric downside).
    pub burn_falsified_mult_milli: i64,
}

impl Default for MintParams {
    fn default() -> Self {
        // spec §1 reference defaults.
        Self {
            half_life_epochs: HALF_LIFE_EPOCHS,
            w_disclosure_milli: 1_000,
            w_wellbecoming_milli: 2_000,
            citation_bonus_milli: 100,
            burn_falsified_mult_milli: 1_500,
        }
    }
}

/// A disclosure that PASSED validation — terminal honest ClaimStakeEscrow state
/// (`Refunded`/`Upheld`) AND witness quorum met. Cannot be constructed otherwise
/// (spec §7). Holds the validated count + CitationLedger hits for weighing.
#[derive(Clone, Debug)]
pub struct ValidatedDisclosure {
    pub did: KotobaCid,
    pub epoch: u64,
    pub n_validated: i64,
    pub citation_hits: i64,
}

impl ValidatedDisclosure {
    /// Returns `None` unless the disclosure reached a terminal honest on-chain
    /// state, the witness quorum was met, and there is ≥1 validated disclosure.
    pub fn new(
        did: KotobaCid,
        epoch: u64,
        n_validated: i64,
        citation_hits: i64,
        terminal_honest: bool,
        witness_quorum_met: bool,
    ) -> Option<Self> {
        if terminal_honest && witness_quorum_met && n_validated > 0 && citation_hits >= 0 {
            Some(Self {
                did,
                epoch,
                n_validated,
                citation_hits,
            })
        } else {
            None
        }
    }

    /// Mint smic = `SCALE·(w_disclosure·n_validated + citation_bonus·hits)` (spec §3a).
    pub fn mint_smic(&self, p: &MintParams) -> i64 {
        let units_milli = (p.w_disclosure_milli as i128) * (self.n_validated as i128)
            + (p.citation_bonus_milli as i128) * (self.citation_hits as i128);
        sat_i64((SCALE as i128) * units_milli / 1_000)
    }

    /// The `social/mint/disclosure/<epoch>` Datom to commit, or `None` if smic ≤ 0.
    pub fn mint_datom(&self, p: &MintParams, graph: &KotobaCid) -> Option<Datom> {
        let smic = self.mint_smic(p);
        (smic > 0).then(|| {
            Datom::assert(
                self.did.clone(),
                MintSource::Disclosure.mint_predicate(self.epoch),
                Value::Integer(smic),
                graph.clone(),
            )
        })
    }
}

/// A Council Lv6+ ≥3 attested wellbecoming measurement (KaizenObserver Δ, ADR-0075).
/// `delta` may be ±: positive mints, negative burns (Council-attested harm).
/// Cannot be constructed without the attestation (spec §3b/§4).
#[derive(Clone, Debug)]
pub struct ValidatedWellbecoming {
    pub did: KotobaCid,
    pub epoch: u64,
    pub delta: i64,
}

impl ValidatedWellbecoming {
    pub fn new(did: KotobaCid, epoch: u64, delta: i64, council_attested: bool) -> Option<Self> {
        council_attested.then_some(Self { did, epoch, delta })
    }

    /// Mint smic for `Δ > 0`: `SCALE·w_wellbecoming·Δ` (spec §3b). 0 if `Δ ≤ 0`.
    pub fn mint_smic(&self, p: &MintParams) -> i64 {
        if self.delta <= 0 {
            return 0;
        }
        sat_i64((SCALE as i128) * (p.w_wellbecoming_milli as i128) * (self.delta as i128) / 1_000)
    }

    /// Burn smic for `Δ < 0`: `SCALE·w_wellbecoming·|Δ|` (spec §4). 0 if `Δ ≥ 0`.
    pub fn burn_smic(&self, p: &MintParams) -> i64 {
        if self.delta >= 0 {
            return 0;
        }
        sat_i64(
            (SCALE as i128)
                * (p.w_wellbecoming_milli as i128)
                * (self.delta.unsigned_abs() as i128)
                / 1_000,
        )
    }

    /// The `social/mint/wellbecoming/<e>` (Δ>0) or `social/burn/<e>` (Δ<0) Datom,
    /// or `None` for Δ == 0.
    pub fn datom(&self, p: &MintParams, graph: &KotobaCid) -> Option<Datom> {
        use std::cmp::Ordering::*;
        match self.delta.cmp(&0) {
            Greater => Some(Datom::assert(
                self.did.clone(),
                MintSource::Wellbecoming.mint_predicate(self.epoch),
                Value::Integer(self.mint_smic(p)),
                graph.clone(),
            )),
            Less => Some(Datom::assert(
                self.did.clone(),
                burn_predicate(self.epoch),
                Value::Integer(self.burn_smic(p)),
                graph.clone(),
            )),
            Equal => None,
        }
    }
}

/// A disclosure later FALSIFIED (the agent's own claim lost a challenge =
/// `Slashed` on the anchor chain). Drives the asymmetric "嘘で損" burn (spec §4).
#[derive(Clone, Debug)]
pub struct Falsification {
    pub did: KotobaCid,
    pub epoch: u64,
    pub count: i64,
}

impl Falsification {
    /// Burn smic = `SCALE·burn_falsified_mult·w_disclosure·count` (spec §4) —
    /// more than the truth earned, so lying is net-negative.
    pub fn burn_smic(&self, p: &MintParams) -> i64 {
        let num = (p.burn_falsified_mult_milli as i128)
            * (p.w_disclosure_milli as i128)
            * (self.count as i128);
        sat_i64((SCALE as i128) * num / 1_000_000) // two milli divisions
    }

    pub fn burn_datom(&self, p: &MintParams, graph: &KotobaCid) -> Option<Datom> {
        let smic = self.burn_smic(p);
        (smic > 0).then(|| {
            Datom::assert(
                self.did.clone(),
                burn_predicate(self.epoch),
                Value::Integer(smic),
                graph.clone(),
            )
        })
    }
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
    EpochRegression {
        last: u64,
        got: u64,
    },
    /// A burn cannot exceed the live (decayed) balance (conservation).
    InsufficientBalance {
        available: i64,
        requested: i64,
    },
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
            return Err(LedgerError::InsufficientBalance {
                available,
                requested: smic,
            });
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
            return Err(LedgerError::EpochRegression {
                last: self.last_epoch,
                got: epoch,
            });
        }
        self.last_epoch = epoch;
        self.entries.push(Entry {
            did,
            op,
            smic,
            epoch,
            reference,
        });
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

/// Incremental, decayed per-DID social-capital balance maintained directly from
/// the `social/mint|burn/<epoch>` **Datom stream** — the MaterializedView that
/// DENOMINATES the Mishmar retainer (ADR-2606082100 Part C; spec §5).
///
/// Geometric half-life decay is NOT Datalog-expressible, so this is a **custom
/// reducer** sibling of [`crate::mv::MaterializedView`] rather than a
/// `DatalogProgram` MV: feed it every commit's `Delta`s via [`apply`] (alongside
/// `MvRegistry::maintain`), then read a DID's decayed capital via [`capital`] or
/// a root's `SC_root` via [`capital_sum`].
///
/// State per DID is `(last_epoch, balance_smic_at_last_epoch)` — the spec §2
/// incremental recurrence, advanced lazily to the read epoch. Assumes epochs are
/// monotone per DID (the ledger enforces this); retracts are ignored (the social
/// log is append-only — mint/burn are never retracted).
///
/// [`apply`]: SocialCapitalView::apply
/// [`capital`]: SocialCapitalView::capital
/// [`capital_sum`]: SocialCapitalView::capital_sum
pub struct SocialCapitalView {
    lambda_q: i64,
    /// entity (DID cid) → (last_epoch, balance_smic at last_epoch)
    balances: HashMap<KotobaCid, (u64, i64)>,
}

impl Default for SocialCapitalView {
    fn default() -> Self {
        Self::new()
    }
}

impl SocialCapitalView {
    pub fn new() -> Self {
        Self {
            lambda_q: lambda_q(HALF_LIFE_EPOCHS),
            balances: HashMap::new(),
        }
    }

    pub fn with_half_life(half_life_epochs: u64) -> Self {
        Self {
            lambda_q: lambda_q(half_life_epochs),
            balances: HashMap::new(),
        }
    }

    /// Parse a social predicate → `(is_mint, epoch)`, or `None` if not a
    /// `social/mint/{disclosure,wellbecoming}/<e>` or `social/burn/<e>` attribute.
    fn parse_attr(attr: &str) -> Option<(bool, u64)> {
        if let Some(rest) = attr.strip_prefix("social/mint/") {
            // rest = "disclosure/<e>" | "wellbecoming/<e>"
            let epoch = rest.rsplit('/').next()?.parse().ok()?;
            Some((true, epoch))
        } else if let Some(rest) = attr.strip_prefix("social/burn/") {
            Some((false, rest.parse().ok()?))
        } else {
            None
        }
    }

    /// Apply a commit's `Delta`s. Asserted `social/mint|burn` Datoms with an
    /// `Integer(smic > 0)` value update the affected DID's decayed balance
    /// (decay forward to the event epoch, then add/sub, clamp ≥ 0). All other
    /// Datoms (and retracts) are ignored. Returns the DIDs touched this call.
    pub fn apply(&mut self, deltas: &[Delta]) -> Vec<KotobaCid> {
        let mut touched = Vec::new();
        for d in deltas {
            if !d.is_assert() {
                continue;
            }
            let Some((is_mint, epoch)) = Self::parse_attr(d.attribute()) else {
                continue;
            };
            let smic = match &d.datom.v {
                Value::Integer(n) if *n > 0 => *n,
                _ => continue,
            };
            let did = d.entity().clone();
            let entry = self.balances.entry(did.clone()).or_insert((epoch, 0));
            if epoch > entry.0 {
                entry.1 = decay_idle(entry.1, epoch - entry.0, self.lambda_q);
                entry.0 = epoch;
            }
            if is_mint {
                entry.1 = entry.1.saturating_add(smic);
            } else {
                entry.1 = entry.1.saturating_sub(smic).max(0);
            }
            entry.1 = entry.1.max(0);
            touched.push(did);
        }
        touched
    }

    /// Decayed social capital (smic) for `did` at `now_epoch` — the read surface
    /// Part C retainer routing + witness-weighting consume. `0` for unknown DIDs.
    pub fn capital(&self, did: &KotobaCid, now_epoch: u64) -> i64 {
        match self.balances.get(did) {
            Some((last, bal)) => {
                decay_idle(*bal, now_epoch.saturating_sub(*last), self.lambda_q).max(0)
            }
            None => 0,
        }
    }

    /// `SC_root(rootCid, e)` (spec §6): Σ social capital of a root's originating
    /// DIDs at `now_epoch`, the numerator of the retainer-allocation share.
    pub fn capital_sum<'a>(
        &self,
        dids: impl IntoIterator<Item = &'a KotobaCid>,
        now_epoch: u64,
    ) -> i64 {
        dids.into_iter()
            .map(|d| self.capital(d, now_epoch))
            .fold(0i64, i64::saturating_add)
    }

    /// Number of DIDs with tracked balance.
    pub fn tracked_dids(&self) -> usize {
        self.balances.len()
    }

    pub fn lambda_q(&self) -> i64 {
        self.lambda_q
    }
}

// ── Mint job (validate → weigh → emit; the I/O entry of the loop, §3/§4) ──────
//
// `SocialMintJob` is the deterministic pipeline a server-side job runs each epoch:
// RAW observations → validation gates (Validated*) → mint engine → social/* Datoms.
// Observations that fail validation (not terminal-honest, no quorum, not
// Council-attested) are silently dropped — never minted (spec §7). The actual I/O
// that produces these observations (anchor-chain `eth_getLogs` for terminal escrow
// state + slashes, the CitationLedger, the KaizenObserver wellbecoming feed) is a
// server wrapper that fills these structs and calls `run_epoch` (follow-up).

/// A raw observed disclosure (pre-validation). `terminal_honest` =
/// Refunded/Upheld on the anchor-chain ClaimStakeEscrow; `witness_quorum_met` =
/// ≥K-of-N kotoba-datomic attestation.
#[derive(Clone, Debug)]
pub struct ObservedDisclosure {
    pub did: KotobaCid,
    pub epoch: u64,
    pub n_validated: i64,
    pub citation_hits: i64,
    pub terminal_honest: bool,
    pub witness_quorum_met: bool,
}

/// A raw observed wellbecoming measurement (KaizenObserver Δ, pre-validation).
#[derive(Clone, Debug)]
pub struct ObservedWellbecoming {
    pub did: KotobaCid,
    pub epoch: u64,
    pub delta: i64,
    pub council_attested: bool,
}

/// The per-epoch mint pipeline. Holds the economic params + the social graph CID
/// the emitted Datoms are written under.
pub struct SocialMintJob {
    params: MintParams,
    graph: KotobaCid,
}

impl SocialMintJob {
    pub fn new(params: MintParams, graph: KotobaCid) -> Self {
        Self { params, graph }
    }

    pub fn params(&self) -> &MintParams {
        &self.params
    }

    /// Validate + weigh one epoch's observations → the `social/mint|burn` Datoms to
    /// commit. Drops any observation that fails its validation gate (no minting on
    /// assertion alone). Falsifications (`Slashed` on the anchor chain) burn directly.
    pub fn run_epoch(
        &self,
        disclosures: &[ObservedDisclosure],
        wellbecomings: &[ObservedWellbecoming],
        falsifications: &[Falsification],
    ) -> Vec<Datom> {
        let mut out = Vec::new();
        for d in disclosures {
            if let Some(v) = ValidatedDisclosure::new(
                d.did.clone(),
                d.epoch,
                d.n_validated,
                d.citation_hits,
                d.terminal_honest,
                d.witness_quorum_met,
            ) {
                out.extend(v.mint_datom(&self.params, &self.graph));
            }
        }
        for w in wellbecomings {
            if let Some(v) =
                ValidatedWellbecoming::new(w.did.clone(), w.epoch, w.delta, w.council_attested)
            {
                out.extend(v.datom(&self.params, &self.graph));
            }
        }
        for f in falsifications {
            out.extend(f.burn_datom(&self.params, &self.graph));
        }
        out
    }
}

// ── Retainer allocation (the downstream of the loop, ADR-2606082100 §6) ───────
//
// Social capital is the DENOMINATOR of the donation pool: the epoch's
// donation-funded retainer is split across pins proportional to the social
// capital of each pin's originating agents. This is the precise sense in which
// "how you generate social capital IS the economic system" — it literally decides
// which rootCids the covenant pays to keep alive, and how much.

/// One pin's origin set for retainer allocation (spec §6). `origin_dids` are the
/// DIDs whose validated disclosure/wellbecoming produced the data under
/// `root_cid` — sourced from `social/origin/<root_cid>` Datoms (an index built
/// like [`SocialCapitalView`]; a follow-up). Here taken as input.
#[derive(Clone, Debug)]
pub struct PinOrigin {
    pub pin_id: KotobaCid,
    pub root_cid: KotobaCid,
    pub origin_dids: Vec<KotobaCid>,
}

/// A pin's computed retainer share for an epoch.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct RetainerShare {
    pub pin_id: KotobaCid,
    /// `SC_root(root_cid, epoch)` in smic — Σ social capital of the pin's origin DIDs.
    pub sc_root: i64,
    /// mKOTO retainer = `pool · sc_root / Σ sc_root` (floor).
    pub retainer_mkoto: i64,
}

/// Allocate the epoch's donation-funded retainer pool (`pool_mkoto`) across `pins`
/// **proportional to the social capital of each pin's originating agents** (spec §6):
///
/// `retainer(pin) = pool · SC_root(pin) / Σ SC_root`,  `SC_root = Σ_{did∈origins} SC(did,e)`.
///
/// Returns `(shares, remainder)`. Floor division is **conserving**:
/// `Σ shares + remainder == pool_mkoto`; the undistributed `remainder` (dust)
/// rolls to the next epoch — never minted (no inflation). When total social
/// capital is 0, nothing is funded and the whole pool rolls over: data with no
/// validated social value is not paid to be kept alive.
pub fn allocate_retainer(
    pins: &[PinOrigin],
    view: &SocialCapitalView,
    now_epoch: u64,
    pool_mkoto: i64,
) -> (Vec<RetainerShare>, i64) {
    let sc: Vec<i64> = pins
        .iter()
        .map(|p| view.capital_sum(p.origin_dids.iter(), now_epoch))
        .collect();
    let total: i128 = sc.iter().map(|&x| x as i128).sum();
    let mut distributed: i128 = 0;
    let mut shares = Vec::with_capacity(pins.len());
    for (p, &sc_root) in pins.iter().zip(sc.iter()) {
        let r = if total > 0 {
            sat_i64((pool_mkoto as i128) * (sc_root as i128) / total)
        } else {
            0
        };
        distributed += r as i128;
        shares.push(RetainerShare {
            pin_id: p.pin_id.clone(),
            sc_root,
            retainer_mkoto: r,
        });
    }
    let remainder = sat_i64(pool_mkoto as i128 - distributed);
    (shares, remainder)
}

// ── L6 settlement (RetainerShare → pinner mKOTO credit, ADR-2605260004 lander) ─
//
// The allocated retainer is paid to the PINNER (the agent keeping the data alive),
// even though the SHARE is sized by the originating agents' social capital. mKOTO
// is internal accounting — non-transferable, redeemable only for kotoba services;
// settlement only CREDITS (adds to) a pinner's balance, never moves balance between
// DIDs (§2(b)). The actual wallet write (kotoba-server `Econ`, async + persisted)
// is a thin wrapper over these deterministic credits (follow-up).

/// A retainer credit to one pinner's mKOTO balance. Multiple pins held by the same
/// pinner aggregate into a single credit.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct RetainerCredit {
    pub pinner_did: KotobaCid,
    pub mkoto: i64,
}

/// L6 settlement: fold allocated [`RetainerShare`]s into per-pinner mKOTO credits.
/// `pinner_of(pin_id)` resolves a pin to its pinner DID (from the MishmarBondEscrow
/// `Pinned` event, observed read-only). Shares with no resolvable pinner or a
/// non-positive amount are skipped (and excluded from `total`). Deterministic order
/// (by pinner CID string). Conserving: `total == Σ credited ≤ Σ shares`.
pub fn settle_retainer(
    shares: &[RetainerShare],
    pinner_of: impl Fn(&KotobaCid) -> Option<KotobaCid>,
) -> (Vec<RetainerCredit>, i64) {
    use std::collections::BTreeMap;
    let mut by_pinner: BTreeMap<String, (KotobaCid, i64)> = BTreeMap::new();
    let mut total: i64 = 0;
    for s in shares {
        if s.retainer_mkoto <= 0 {
            continue;
        }
        let Some(pinner) = pinner_of(&s.pin_id) else {
            continue;
        };
        let entry = by_pinner.entry(pinner.to_string()).or_insert((pinner, 0));
        entry.1 = entry.1.saturating_add(s.retainer_mkoto);
        total = total.saturating_add(s.retainer_mkoto);
    }
    let credits = by_pinner
        .into_values()
        .map(|(pinner_did, mkoto)| RetainerCredit { pinner_did, mkoto })
        .collect();
    (credits, total)
}

/// Apply retainer credits to an mKOTO balance map — **additive only** (the credit
/// is non-transferable; there is no debit-from-another-DID path here). Mirrors the
/// effect of crediting `kotoba-server::Econ` balances.
pub fn apply_retainer_credits(balances: &mut HashMap<KotobaCid, i64>, credits: &[RetainerCredit]) {
    for c in credits {
        let b = balances.entry(c.pinner_did.clone()).or_insert(0);
        *b = b.saturating_add(c.mkoto);
    }
}

// ── Observation indexes (feed retainer/settlement with real data, §5/§6) ──────
//
// Two incremental reducers (siblings of SocialCapitalView) that project the
// observed anchor-chain `Pinned` events + `social/origin` Datoms into the lookups
// the downstream needs: pin→pinner (for settle_retainer) and rootCid→origin-DIDs
// (for allocate_retainer's SC_root). Pure, deterministic, no external dep — the
// Datoms are produced by the kotoba-side observation projection (read+verify).

/// Predicate: a pin's pinner DID. `Datom{ e: pinId, a: PIN_PINNER_PRED, v: Cid(pinner) }`.
pub const PIN_PINNER_PRED: &str = "mishmar/pin/pinner";
/// Predicate: a pin's rootCid. `Datom{ e: pinId, a: PIN_ROOT_PRED, v: Cid(rootCid) }`.
pub const PIN_ROOT_PRED: &str = "mishmar/pin/root";
/// Predicate: a pin's posted bond, in mKOTO. `Datom{ e: pinId, a: PIN_BOND_PRED, v: Integer(bond) }`.
/// Observed from the `Pinned` event's `uint256 bond` field (saturating into i64,
/// same convention as the smic ledger). Feeds [`eligible_replica`] (ADR-002 §1).
pub const PIN_BOND_PRED: &str = "mishmar/pin/bond";
/// Predicate: a root's originating DID (many per root). `Datom{ e: rootCid, a: ORIGIN_PRED, v: Cid(did) }`.
pub const ORIGIN_PRED: &str = "social/origin";

/// pin → (pinner, rootCid, bond), projected from observed `Pinned` events. Feeds
/// [`settle_retainer`] (`pinner_of`), [`build_pin_origins`] (`root_of`), and
/// [`eligible_replica`] (`bond_of`, ADR-002).
#[derive(Default)]
pub struct PinIndex {
    pinner: HashMap<KotobaCid, KotobaCid>,
    root: HashMap<KotobaCid, KotobaCid>,
    bond: HashMap<KotobaCid, i64>,
}

impl PinIndex {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn apply(&mut self, deltas: &[Delta]) {
        for d in deltas {
            if !d.is_assert() {
                continue;
            }
            match d.attribute() {
                PIN_PINNER_PRED => {
                    if let Value::Cid(target) = &d.datom.v {
                        self.pinner.insert(d.entity().clone(), target.clone());
                    }
                }
                PIN_ROOT_PRED => {
                    if let Value::Cid(target) = &d.datom.v {
                        self.root.insert(d.entity().clone(), target.clone());
                    }
                }
                PIN_BOND_PRED => {
                    if let Value::Integer(n) = &d.datom.v {
                        self.bond.insert(d.entity().clone(), *n);
                    }
                }
                _ => {}
            }
        }
    }

    pub fn pinner_of(&self, pin_id: &KotobaCid) -> Option<KotobaCid> {
        self.pinner.get(pin_id).cloned()
    }

    pub fn root_of(&self, pin_id: &KotobaCid) -> Option<KotobaCid> {
        self.root.get(pin_id).cloned()
    }

    /// Observed bond (mKOTO) for a pin, if a `mishmar/pin/bond` Datom was seen.
    pub fn bond_of(&self, pin_id: &KotobaCid) -> Option<i64> {
        self.bond.get(pin_id).copied()
    }

    /// Pins with a known root (eligible for retainer allocation).
    pub fn pin_ids(&self) -> Vec<KotobaCid> {
        self.root.keys().cloned().collect()
    }
}

/// ADR-002 §1 — the replica-admission membrane, as a pure predicate over the
/// already-projected `mishmar/pin/*` Datoms (read+verify; no chain access here).
///
/// A DID is an **eligible replica** for `root` iff it holds at least one observed
/// pin on that root whose bond ≥ `min_bond_mkoto`. This is *admission* only:
/// reputation (social capital) ranks among the eligible but never widens this set.
///
/// `min_bond_mkoto == 0` ⇒ open neighbourhood (today's behaviour, the default in
/// the ADR-001 replication policy): any pinner of `root` qualifies. A pin with no
/// observed bond Datom counts as bond `0`, so it only qualifies when the floor is
/// itself `0`.
pub fn eligible_replica(
    did: &KotobaCid,
    root: &KotobaCid,
    min_bond_mkoto: i64,
    pins: &PinIndex,
) -> bool {
    pins.pin_ids().into_iter().any(|pin| {
        pins.root_of(&pin).as_ref() == Some(root)
            && pins.pinner_of(&pin).as_ref() == Some(did)
            && pins.bond_of(&pin).unwrap_or(0) >= min_bond_mkoto
    })
}

/// rootCid → originating DIDs (deduped, insertion order), projected from
/// `social/origin` Datoms. Feeds [`allocate_retainer`]'s `SC_root`.
#[derive(Default)]
pub struct OriginIndex {
    origins: HashMap<KotobaCid, Vec<KotobaCid>>,
}

impl OriginIndex {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn apply(&mut self, deltas: &[Delta]) {
        for d in deltas {
            if !d.is_assert() || d.attribute() != ORIGIN_PRED {
                continue;
            }
            let Value::Cid(did) = &d.datom.v else {
                continue;
            };
            let v = self.origins.entry(d.entity().clone()).or_default();
            if !v.contains(did) {
                v.push(did.clone());
            }
        }
    }

    pub fn origins_of(&self, root: &KotobaCid) -> &[KotobaCid] {
        self.origins.get(root).map(Vec::as_slice).unwrap_or(&[])
    }
}

/// Build [`PinOrigin`] records (for [`allocate_retainer`]) from the two indexes:
/// each pin's origins = `OriginIndex::origins_of(PinIndex::root_of(pin))`. Pins
/// with no known root are dropped.
pub fn build_pin_origins(
    pin_ids: &[KotobaCid],
    pins: &PinIndex,
    origins: &OriginIndex,
) -> Vec<PinOrigin> {
    pin_ids
        .iter()
        .filter_map(|pid| {
            let root = pins.root_of(pid)?;
            Some(PinOrigin {
                pin_id: pid.clone(),
                root_cid: root.clone(),
                origin_dids: origins.origins_of(&root).to_vec(),
            })
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::datom::Datom;

    // ── pure decay primitives ────────────────────────────────────────────

    #[test]
    fn redeemable_is_always_zero() {
        assert_eq!(redeemable_usd_micros(), 0);
    }

    #[test]
    fn lambda_q_h30_matches_spec() {
        // spec §2: H=30 → LAMBDA_Q ≈ 977_159 (f64 round, ±1 smic).
        assert!(
            (lambda_q(30) - 977_159).abs() <= 1,
            "lambda_q(30)={}",
            lambda_q(30)
        );
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
        let half = start / 2;
        assert!((after - half).abs() <= SCALE, "after={after} half={half}");
    }

    #[test]
    fn idle_and_step_track_float_truth() {
        let lq = lambda_q(30);
        let start = 500 * SCALE;
        let gap = 10u64;
        let truth = (start as f64 * 0.5_f64.powf(gap as f64 / 30.0)).round() as i64;
        let mut step = start;
        for _ in 0..gap {
            step = step_social_capital(step, 0, 0, lq);
        }
        let idle = decay_idle(start, gap, lq);
        let tol = (truth / 100_000).max(64);
        assert!(
            (step - truth).abs() <= tol,
            "step={step} truth={truth} tol={tol}"
        );
        assert!(
            (idle - truth).abs() <= tol,
            "idle={idle} truth={truth} tol={tol}"
        );
    }

    #[test]
    fn step_clamps_non_negative_and_applies_flow() {
        let lq = lambda_q(30);
        assert_eq!(step_social_capital(0, 0, 100, lq), 0);
        assert_eq!(step_social_capital(0, 5 * SCALE, 0, lq), 5 * SCALE);
    }

    // ── ledger ────────────────────────────────────────────────────────────

    #[test]
    fn mint_then_balance_decays_over_time() {
        let mut l = SocialCapitalLedger::new();
        l.mint(
            "did:key:alice",
            MintSource::Disclosure,
            100 * SCALE,
            0,
            "attest-1",
        )
        .unwrap();
        assert_eq!(l.balance("did:key:alice", 0), 100 * SCALE);
        let later = l.balance("did:key:alice", 30);
        assert!((later - 50 * SCALE).abs() <= SCALE, "later={later}");
    }

    #[test]
    fn disclosure_and_wellbecoming_both_accumulate() {
        let mut l = SocialCapitalLedger::new();
        l.mint("did:key:bob", MintSource::Disclosure, 10 * SCALE, 1, "d1")
            .unwrap();
        l.mint("did:key:bob", MintSource::Wellbecoming, 20 * SCALE, 1, "w1")
            .unwrap();
        assert_eq!(l.balance("did:key:bob", 1), 30 * SCALE);
    }

    #[test]
    fn burn_cannot_exceed_balance_conservation() {
        let mut l = SocialCapitalLedger::new();
        l.mint("did:key:carol", MintSource::Disclosure, 10 * SCALE, 0, "d1")
            .unwrap();
        let err = l
            .burn("did:key:carol", 11 * SCALE, 0, "falsified-1")
            .unwrap_err();
        assert!(matches!(err, LedgerError::InsufficientBalance { .. }));
        l.burn("did:key:carol", 10 * SCALE, 0, "falsified-2")
            .unwrap();
        assert_eq!(l.balance("did:key:carol", 0), 0);
    }

    #[test]
    fn non_transferable_by_construction() {
        let mut l = SocialCapitalLedger::new();
        l.mint("did:key:a", MintSource::Disclosure, 50 * SCALE, 0, "d")
            .unwrap();
        assert_eq!(l.balance("did:key:b", 0), 0);
        assert_eq!(l.balance("did:key:a", 0), 50 * SCALE);
    }

    #[test]
    fn epoch_regression_rejected() {
        let mut l = SocialCapitalLedger::new();
        l.mint("did:key:a", MintSource::Disclosure, SCALE, 5, "d1")
            .unwrap();
        let err = l
            .mint("did:key:a", MintSource::Disclosure, SCALE, 4, "d2")
            .unwrap_err();
        assert_eq!(err, LedgerError::EpochRegression { last: 5, got: 4 });
    }

    #[test]
    fn predicates_match_spec() {
        assert_eq!(
            MintSource::Disclosure.mint_predicate(7),
            "social/mint/disclosure/7"
        );
        assert_eq!(
            MintSource::Wellbecoming.mint_predicate(7),
            "social/mint/wellbecoming/7"
        );
        assert_eq!(burn_predicate(7), "social/burn/7");
        assert_eq!(capital_predicate(7), "social/capital/7");
    }

    #[test]
    fn deterministic_replay() {
        let build = || {
            let mut l = SocialCapitalLedger::new();
            l.mint("did:key:x", MintSource::Disclosure, 30 * SCALE, 0, "d")
                .unwrap();
            l.mint("did:key:x", MintSource::Wellbecoming, 70 * SCALE, 10, "w")
                .unwrap();
            l.burn("did:key:x", 20 * SCALE, 20, "b").unwrap();
            l.balance("did:key:x", 40)
        };
        assert_eq!(build(), build());
    }

    // ── SocialCapitalView (the MV reducer) ────────────────────────────────

    fn did(seed: &str) -> KotobaCid {
        KotobaCid::from_bytes(seed.as_bytes())
    }

    fn mint_delta(d: &KotobaCid, src: MintSource, smic: i64, epoch: u64) -> Delta {
        Delta::assert_datom(Datom::assert(
            d.clone(),
            src.mint_predicate(epoch),
            Value::Integer(smic),
            did("g:social"),
        ))
    }

    fn burn_delta(d: &KotobaCid, smic: i64, epoch: u64) -> Delta {
        Delta::assert_datom(Datom::assert(
            d.clone(),
            burn_predicate(epoch),
            Value::Integer(smic),
            did("g:social"),
        ))
    }

    #[test]
    fn view_parse_attr() {
        assert_eq!(
            SocialCapitalView::parse_attr("social/mint/disclosure/12"),
            Some((true, 12))
        );
        assert_eq!(
            SocialCapitalView::parse_attr("social/mint/wellbecoming/3"),
            Some((true, 3))
        );
        assert_eq!(
            SocialCapitalView::parse_attr("social/burn/9"),
            Some((false, 9))
        );
        assert_eq!(SocialCapitalView::parse_attr("kg/claim/role"), None);
        assert_eq!(SocialCapitalView::parse_attr("social/capital/5"), None); // output, not input
    }

    #[test]
    fn view_mint_accumulates_and_decays() {
        let mut v = SocialCapitalView::new();
        let alice = did("did:key:alice");
        v.apply(&[mint_delta(&alice, MintSource::Disclosure, 100 * SCALE, 0)]);
        assert_eq!(v.capital(&alice, 0), 100 * SCALE);
        // one half-life later → ~half
        let later = v.capital(&alice, 30);
        assert!((later - 50 * SCALE).abs() <= SCALE, "later={later}");
        assert_eq!(v.tracked_dids(), 1);
    }

    #[test]
    fn view_disclosure_plus_wellbecoming_same_epoch() {
        let mut v = SocialCapitalView::new();
        let bob = did("did:key:bob");
        v.apply(&[
            mint_delta(&bob, MintSource::Disclosure, 10 * SCALE, 2),
            mint_delta(&bob, MintSource::Wellbecoming, 20 * SCALE, 2),
        ]);
        assert_eq!(v.capital(&bob, 2), 30 * SCALE);
    }

    #[test]
    fn view_burn_reduces_clamped() {
        let mut v = SocialCapitalView::new();
        let c = did("did:key:carol");
        v.apply(&[mint_delta(&c, MintSource::Disclosure, 10 * SCALE, 0)]);
        v.apply(&[burn_delta(&c, 4 * SCALE, 0)]);
        assert_eq!(v.capital(&c, 0), 6 * SCALE);
        // over-burn clamps at 0, never negative
        v.apply(&[burn_delta(&c, 100 * SCALE, 0)]);
        assert_eq!(v.capital(&c, 0), 0);
    }

    #[test]
    fn view_ignores_non_social_and_retracts() {
        let mut v = SocialCapitalView::new();
        let a = did("did:key:a");
        // non-social datom
        let other = Delta::assert_datom(Datom::assert(
            a.clone(),
            "kg/claim/role".to_string(),
            Value::Text("admin".into()),
            did("g"),
        ));
        // retracted mint (append-only log never retracts; ignored)
        let retract = Delta::retract_datom(Datom::assert(
            a.clone(),
            MintSource::Disclosure.mint_predicate(0),
            Value::Integer(50 * SCALE),
            did("g:social"),
        ));
        v.apply(&[other, retract]);
        assert_eq!(v.capital(&a, 0), 0);
        assert_eq!(v.tracked_dids(), 0);
    }

    #[test]
    fn view_capital_sum_is_sc_root() {
        let mut v = SocialCapitalView::new();
        let a = did("did:key:a");
        let b = did("did:key:b");
        v.apply(&[
            mint_delta(&a, MintSource::Disclosure, 30 * SCALE, 0),
            mint_delta(&b, MintSource::Wellbecoming, 70 * SCALE, 0),
        ]);
        // SC_root over {a, b} = 100 points; unknown DID contributes 0.
        let root = [a.clone(), b.clone(), did("did:key:unknown")];
        assert_eq!(v.capital_sum(root.iter(), 0), 100 * SCALE);
    }

    #[test]
    fn view_unknown_did_is_zero() {
        let v = SocialCapitalView::new();
        assert_eq!(v.capital(&did("did:key:nobody"), 100), 0);
    }

    // ── Observation indexes (pin→pinner, social/origin) ───────────────────

    fn cid_datom(e: &KotobaCid, attr: &str, v: &KotobaCid) -> Delta {
        Delta::assert_datom(Datom::assert(
            e.clone(),
            attr.to_string(),
            Value::Cid(v.clone()),
            did("g"),
        ))
    }

    #[test]
    fn pin_index_maps_pinner_and_root() {
        let pin = did("pinA");
        let pinner = did("did:key:peggy");
        let root = did("rootA");
        let mut idx = PinIndex::new();
        idx.apply(&[
            cid_datom(&pin, PIN_PINNER_PRED, &pinner),
            cid_datom(&pin, PIN_ROOT_PRED, &root),
        ]);
        assert_eq!(idx.pinner_of(&pin), Some(pinner));
        assert_eq!(idx.root_of(&pin), Some(root));
        assert_eq!(idx.pinner_of(&did("unknown")), None);
        assert_eq!(idx.pin_ids(), vec![pin]);
    }

    fn int_datom(e: &KotobaCid, attr: &str, v: i64) -> Delta {
        Delta::assert_datom(Datom::assert(
            e.clone(),
            attr.to_string(),
            Value::Integer(v),
            did("g"),
        ))
    }

    fn bonded_pin(idx: &mut PinIndex, pin: &str, pinner: &KotobaCid, root: &KotobaCid, bond: i64) {
        let p = did(pin);
        idx.apply(&[
            cid_datom(&p, PIN_PINNER_PRED, pinner),
            cid_datom(&p, PIN_ROOT_PRED, root),
            int_datom(&p, PIN_BOND_PRED, bond),
        ]);
    }

    #[test]
    fn pin_index_tracks_bond() {
        let pin = did("pinA");
        let mut idx = PinIndex::new();
        idx.apply(&[int_datom(&pin, PIN_BOND_PRED, 5_000)]);
        assert_eq!(idx.bond_of(&pin), Some(5_000));
        assert_eq!(idx.bond_of(&did("unknown")), None);
    }

    #[test]
    fn eligible_replica_admits_when_bond_meets_floor() {
        let peggy = did("did:key:peggy");
        let root = did("rootA");
        let mut idx = PinIndex::new();
        bonded_pin(&mut idx, "pinA", &peggy, &root, 5_000);
        // exactly-at and above the floor admit; below rejects.
        assert!(eligible_replica(&peggy, &root, 5_000, &idx));
        assert!(eligible_replica(&peggy, &root, 1, &idx));
        assert!(!eligible_replica(&peggy, &root, 5_001, &idx));
    }

    #[test]
    fn eligible_replica_open_neighbourhood_when_floor_zero() {
        // min_bond == 0 ⇒ today's open behaviour: any pinner of root qualifies,
        // even with no observed bond Datom (bond defaults to 0).
        let peggy = did("did:key:peggy");
        let root = did("rootA");
        let pin = did("pinA");
        let mut idx = PinIndex::new();
        idx.apply(&[
            cid_datom(&pin, PIN_PINNER_PRED, &peggy),
            cid_datom(&pin, PIN_ROOT_PRED, &root),
        ]);
        assert!(eligible_replica(&peggy, &root, 0, &idx));
        // ...but a positive floor rejects the unbonded pin.
        assert!(!eligible_replica(&peggy, &root, 1, &idx));
    }

    #[test]
    fn eligible_replica_is_scoped_to_root_and_did() {
        let peggy = did("did:key:peggy");
        let mallory = did("did:key:mallory");
        let root_a = did("rootA");
        let root_b = did("rootB");
        let mut idx = PinIndex::new();
        bonded_pin(&mut idx, "pinA", &peggy, &root_a, 5_000);
        // peggy is bonded on root_a, not root_b; mallory is bonded nowhere.
        assert!(eligible_replica(&peggy, &root_a, 5_000, &idx));
        assert!(!eligible_replica(&peggy, &root_b, 5_000, &idx));
        assert!(!eligible_replica(&mallory, &root_a, 5_000, &idx));
    }

    #[test]
    fn eligible_replica_takes_max_bond_across_pins() {
        // Two pins by the same DID on the same root: the larger bond decides.
        let peggy = did("did:key:peggy");
        let root = did("rootA");
        let mut idx = PinIndex::new();
        bonded_pin(&mut idx, "pinSmall", &peggy, &root, 1_000);
        bonded_pin(&mut idx, "pinBig", &peggy, &root, 9_000);
        assert!(eligible_replica(&peggy, &root, 9_000, &idx));
        assert!(!eligible_replica(&peggy, &root, 9_001, &idx));
    }

    #[test]
    fn origin_index_collects_dedups_dids() {
        let root = did("rootA");
        let a = did("did:key:a");
        let b = did("did:key:b");
        let mut idx = OriginIndex::new();
        idx.apply(&[
            cid_datom(&root, ORIGIN_PRED, &a),
            cid_datom(&root, ORIGIN_PRED, &b),
            cid_datom(&root, ORIGIN_PRED, &a), // dup ignored
        ]);
        assert_eq!(idx.origins_of(&root), &[a, b]);
        assert_eq!(idx.origins_of(&did("rootless")), &[] as &[KotobaCid]);
    }

    #[test]
    fn indexes_feed_allocation_and_settlement_end_to_end() {
        // observed Pinned + origin Datoms → indexes → PinOrigin → allocate → settle.
        let a = did("did:key:a");
        let b = did("did:key:b");
        let peggy = did("did:key:peggy");
        let rootA = did("rootA");
        let rootB = did("rootB");
        let pinA = did("pinA");
        let pinB = did("pinB");

        let mut pins = PinIndex::new();
        pins.apply(&[
            cid_datom(&pinA, PIN_PINNER_PRED, &peggy),
            cid_datom(&pinA, PIN_ROOT_PRED, &rootA),
            cid_datom(&pinB, PIN_PINNER_PRED, &peggy),
            cid_datom(&pinB, PIN_ROOT_PRED, &rootB),
        ]);
        let mut origins = OriginIndex::new();
        origins.apply(&[
            cid_datom(&rootA, ORIGIN_PRED, &a),
            cid_datom(&rootB, ORIGIN_PRED, &b),
        ]);

        // social capital: a=30, b=70
        let mut view = SocialCapitalView::new();
        view.apply(&[
            mint_delta(&a, MintSource::Disclosure, 30 * SCALE, 0),
            mint_delta(&b, MintSource::Disclosure, 70 * SCALE, 0),
        ]);

        let pin_origins = build_pin_origins(&[pinA.clone(), pinB.clone()], &pins, &origins);
        assert_eq!(pin_origins.len(), 2);
        let (shares, _) = allocate_retainer(&pin_origins, &view, 0, 1_000); // 300 / 700
                                                                            // settle via the PinIndex pinner resolver — both pins → peggy → 1000 total.
        let (credits, total) = settle_retainer(&shares, |pin| pins.pinner_of(pin));
        assert_eq!(total, 1_000);
        assert_eq!(credits.len(), 1);
        assert_eq!(credits[0].pinner_did, peggy);
        assert_eq!(credits[0].mkoto, 1_000);
    }

    // ── Mint engine (the upstream of the loop) ────────────────────────────

    #[test]
    fn mint_params_defaults_match_spec() {
        let p = MintParams::default();
        assert_eq!(p.half_life_epochs, 30);
        assert_eq!(p.w_disclosure_milli, 1_000); // 1.0
        assert_eq!(p.w_wellbecoming_milli, 2_000); // 2.0
        assert_eq!(p.citation_bonus_milli, 100); // 0.1/hit
        assert_eq!(p.burn_falsified_mult_milli, 1_500); // 1.5
    }

    #[test]
    fn disclosure_validation_gate_enforced() {
        let d = did("did:key:a");
        // not terminal-honest → None (cannot mint from unvalidated disclosure)
        assert!(ValidatedDisclosure::new(d.clone(), 0, 2, 5, false, true).is_none());
        // quorum not met → None
        assert!(ValidatedDisclosure::new(d.clone(), 0, 2, 5, true, false).is_none());
        // n_validated 0 → None
        assert!(ValidatedDisclosure::new(d.clone(), 0, 0, 5, true, true).is_none());
        // valid → Some
        assert!(ValidatedDisclosure::new(d, 0, 2, 5, true, true).is_some());
    }

    #[test]
    fn disclosure_mint_smic_weighs_count_plus_citations() {
        let p = MintParams::default();
        // 2 validated + 5 citation hits → 1.0*2 + 0.1*5 = 2.5 points
        let d = ValidatedDisclosure::new(did("did:key:a"), 0, 2, 5, true, true).unwrap();
        assert_eq!(d.mint_smic(&p), 2_500_000); // 2.5 * SCALE
    }

    #[test]
    fn wellbecoming_gate_and_sign_split() {
        let p = MintParams::default();
        let d = did("did:key:w");
        // not council-attested → None
        assert!(ValidatedWellbecoming::new(d.clone(), 0, 3, false).is_none());
        // Δ>0 mints w*Δ = 2.0*3 = 6 points; burn 0
        let pos = ValidatedWellbecoming::new(d.clone(), 0, 3, true).unwrap();
        assert_eq!(pos.mint_smic(&p), 6 * SCALE);
        assert_eq!(pos.burn_smic(&p), 0);
        // Δ<0 burns w*|Δ| = 2.0*2 = 4 points; mint 0
        let neg = ValidatedWellbecoming::new(d, 0, -2, true).unwrap();
        assert_eq!(neg.mint_smic(&p), 0);
        assert_eq!(neg.burn_smic(&p), 4 * SCALE);
    }

    #[test]
    fn falsification_burn_is_asymmetric() {
        let p = MintParams::default();
        // 2 falsified → 1.5 * 1.0 * 2 = 3 points burned (> the 2 they'd have earned)
        let f = Falsification {
            did: did("did:key:liar"),
            epoch: 0,
            count: 2,
        };
        assert_eq!(f.burn_smic(&p), 3 * SCALE);
    }

    #[test]
    fn mint_datoms_drive_the_view_end_to_end() {
        // The loop closes: validated acts → Datoms → SocialCapitalView → capital.
        let p = MintParams::default();
        let g = did("g:social:2026");
        let alice = did("did:key:alice");

        let disc = ValidatedDisclosure::new(alice.clone(), 0, 2, 5, true, true).unwrap(); // 2.5
        let wb = ValidatedWellbecoming::new(alice.clone(), 0, 3, true).unwrap(); // +6.0

        let mut datoms = Vec::new();
        datoms.extend(disc.mint_datom(&p, &g));
        datoms.extend(wb.datom(&p, &g));
        assert_eq!(datoms.len(), 2);

        let deltas: Vec<Delta> = datoms.into_iter().map(Delta::assert_datom).collect();
        let mut view = SocialCapitalView::new();
        view.apply(&deltas);

        // capital = 2.5 + 6.0 = 8.5 points
        assert_eq!(view.capital(&alice, 0), 8_500_000);
    }

    #[test]
    fn wellbecoming_zero_delta_emits_no_datom() {
        let p = MintParams::default();
        let w = ValidatedWellbecoming::new(did("did:key:z"), 0, 0, true).unwrap();
        assert!(w.datom(&p, &did("g")).is_none());
    }

    // ── Mint job (validate → weigh → emit) ───────────────────────────────

    #[test]
    fn job_emits_datoms_for_valid_observations_only() {
        let job = SocialMintJob::new(MintParams::default(), did("g:social"));
        let a = did("did:key:a");
        let b = did("did:key:b");
        let disclosures = vec![
            // valid: 2 validated + 5 hits = 2.5 pts
            ObservedDisclosure {
                did: a.clone(),
                epoch: 0,
                n_validated: 2,
                citation_hits: 5,
                terminal_honest: true,
                witness_quorum_met: true,
            },
            // INVALID: no witness quorum → dropped
            ObservedDisclosure {
                did: b.clone(),
                epoch: 0,
                n_validated: 9,
                citation_hits: 9,
                terminal_honest: true,
                witness_quorum_met: false,
            },
        ];
        let wellbecomings = vec![
            // valid +5 → 10 pts
            ObservedWellbecoming {
                did: a.clone(),
                epoch: 0,
                delta: 5,
                council_attested: true,
            },
            // INVALID: not council-attested → dropped
            ObservedWellbecoming {
                did: b.clone(),
                epoch: 0,
                delta: 99,
                council_attested: false,
            },
        ];
        let datoms = job.run_epoch(&disclosures, &wellbecomings, &[]);
        // only a's two valid acts emit (b dropped both)
        assert_eq!(datoms.len(), 2);

        let deltas: Vec<Delta> = datoms.into_iter().map(Delta::assert_datom).collect();
        let mut v = SocialCapitalView::new();
        v.apply(&deltas);
        assert_eq!(v.capital(&a, 0), 12_500_000); // 2.5 + 10.0
        assert_eq!(v.capital(&b, 0), 0); // all dropped
    }

    #[test]
    fn job_falsification_burns() {
        let job = SocialMintJob::new(MintParams::default(), did("g:social"));
        let a = did("did:key:a");
        // mint 5 pts then falsify 2 (burn 3) in the same epoch run
        let disc = vec![ObservedDisclosure {
            did: a.clone(),
            epoch: 0,
            n_validated: 5,
            citation_hits: 0,
            terminal_honest: true,
            witness_quorum_met: true,
        }];
        let fals = vec![Falsification {
            did: a.clone(),
            epoch: 0,
            count: 2,
        }];
        let datoms = job.run_epoch(&disc, &[], &fals);
        let deltas: Vec<Delta> = datoms.into_iter().map(Delta::assert_datom).collect();
        let mut v = SocialCapitalView::new();
        v.apply(&deltas);
        assert_eq!(v.capital(&a, 0), 2 * SCALE); // 5.0 minted − 3.0 burned
    }

    // ── Retainer allocation (the downstream of the loop) ──────────────────

    fn pin(id: &str, root: &str, origins: &[&KotobaCid]) -> PinOrigin {
        PinOrigin {
            pin_id: did(id),
            root_cid: did(root),
            origin_dids: origins.iter().map(|d| (*d).clone()).collect(),
        }
    }

    #[test]
    fn retainer_is_proportional_to_social_capital() {
        let a = did("did:key:a");
        let b = did("did:key:b");
        let mut v = SocialCapitalView::new();
        v.apply(&[
            mint_delta(&a, MintSource::Disclosure, 30 * SCALE, 0), // SC_root(pinA) = 30
            mint_delta(&b, MintSource::Disclosure, 70 * SCALE, 0), // SC_root(pinB) = 70
        ]);
        let pins = [pin("pinA", "rootA", &[&a]), pin("pinB", "rootB", &[&b])];
        let (shares, remainder) = allocate_retainer(&pins, &v, 0, 1_000);
        assert_eq!(shares[0].retainer_mkoto, 300); // 1000 · 30/100
        assert_eq!(shares[1].retainer_mkoto, 700); // 1000 · 70/100
        assert_eq!(remainder, 0);
    }

    #[test]
    fn retainer_conserves_pool() {
        let a = did("did:key:a");
        let b = did("did:key:b");
        let c = did("did:key:c");
        let mut v = SocialCapitalView::new();
        // 1/1/1 split of a pool not divisible by 3 → dust remainder, conserved.
        v.apply(&[
            mint_delta(&a, MintSource::Disclosure, 1 * SCALE, 0),
            mint_delta(&b, MintSource::Disclosure, 1 * SCALE, 0),
            mint_delta(&c, MintSource::Disclosure, 1 * SCALE, 0),
        ]);
        let pins = [
            pin("p1", "r1", &[&a]),
            pin("p2", "r2", &[&b]),
            pin("p3", "r3", &[&c]),
        ];
        let pool = 1_000;
        let (shares, remainder) = allocate_retainer(&pins, &v, 0, pool);
        let sum: i64 = shares.iter().map(|s| s.retainer_mkoto).sum();
        assert_eq!(
            sum + remainder,
            pool,
            "Σ shares + remainder == pool (conserving)"
        );
        assert_eq!(remainder, 1); // 1000 = 333+333+333 + 1 dust
    }

    #[test]
    fn retainer_zero_capital_funds_nothing_and_rolls_over() {
        let v = SocialCapitalView::new(); // no capital minted
        let pins = [pin("p1", "r1", &[&did("did:key:a")])];
        let (shares, remainder) = allocate_retainer(&pins, &v, 0, 5_000);
        assert_eq!(shares[0].retainer_mkoto, 0);
        assert_eq!(
            remainder, 5_000,
            "whole pool rolls over when no validated social value"
        );
    }

    #[test]
    fn retainer_root_sums_multiple_origin_dids() {
        let a = did("did:key:a");
        let b = did("did:key:b");
        let mut v = SocialCapitalView::new();
        v.apply(&[
            mint_delta(&a, MintSource::Disclosure, 20 * SCALE, 0),
            mint_delta(&b, MintSource::Wellbecoming, 30 * SCALE, 0),
        ]);
        // one pin whose root was originated by BOTH a and b → SC_root = 50
        let pins = [pin("p1", "r1", &[&a, &b])];
        let (shares, _) = allocate_retainer(&pins, &v, 0, 999);
        assert_eq!(shares[0].sc_root, 50 * SCALE);
        assert_eq!(shares[0].retainer_mkoto, 999); // sole pin → whole pool
    }

    // ── L6 settlement ─────────────────────────────────────────────────────

    fn share(pin: &str, sc_root: i64, mkoto: i64) -> RetainerShare {
        RetainerShare {
            pin_id: did(pin),
            sc_root,
            retainer_mkoto: mkoto,
        }
    }

    #[test]
    fn settlement_aggregates_per_pinner() {
        // peggy holds pinA(300)+pinB(200); quinn holds pinC(500).
        let peggy = did("did:key:peggy");
        let quinn = did("did:key:quinn");
        let shares = [
            share("pinA", 0, 300),
            share("pinB", 0, 200),
            share("pinC", 0, 500),
        ];
        let resolve = |pin: &KotobaCid| {
            if *pin == did("pinA") || *pin == did("pinB") {
                Some(peggy.clone())
            } else if *pin == did("pinC") {
                Some(quinn.clone())
            } else {
                None
            }
        };
        let (credits, total) = settle_retainer(&shares, resolve);
        assert_eq!(total, 1_000);
        // deterministic order by pinner CID string; find each.
        let peggy_c = credits.iter().find(|c| c.pinner_did == peggy).unwrap();
        let quinn_c = credits.iter().find(|c| c.pinner_did == quinn).unwrap();
        assert_eq!(peggy_c.mkoto, 500); // 300+200 aggregated
        assert_eq!(quinn_c.mkoto, 500);
    }

    #[test]
    fn settlement_skips_unresolved_pin_and_conserves() {
        let peggy = did("did:key:peggy");
        let shares = [share("pinA", 0, 300), share("orphan", 0, 999)];
        let resolve = |pin: &KotobaCid| (*pin == did("pinA")).then(|| peggy.clone());
        let (credits, total) = settle_retainer(&shares, resolve);
        // orphan pin (no pinner) excluded → total counts only the resolved 300.
        assert_eq!(total, 300);
        assert_eq!(credits.len(), 1);
        assert_eq!(credits[0].mkoto, 300);
    }

    #[test]
    fn settlement_apply_credits_is_additive_non_transferable() {
        let peggy = did("did:key:peggy");
        let credits = vec![RetainerCredit {
            pinner_did: peggy.clone(),
            mkoto: 500,
        }];
        let mut balances: std::collections::HashMap<KotobaCid, i64> =
            std::collections::HashMap::new();
        balances.insert(peggy.clone(), 100); // existing balance
        apply_retainer_credits(&mut balances, &credits);
        assert_eq!(balances[&peggy], 600); // additive credit, no debit-from-other path
                                           // a DID never named in credits is untouched (no transfer exists).
        assert!(!balances.contains_key(&did("did:key:other")));
    }

    #[test]
    fn settlement_end_to_end_from_allocation() {
        // allocate → settle → apply: the full downstream.
        let a = did("did:key:a");
        let b = did("did:key:b");
        let mut v = SocialCapitalView::new();
        v.apply(&[
            mint_delta(&a, MintSource::Disclosure, 30 * SCALE, 0),
            mint_delta(&b, MintSource::Disclosure, 70 * SCALE, 0),
        ]);
        let pins = [pin("pinA", "rootA", &[&a]), pin("pinB", "rootB", &[&b])];
        let (shares, _) = allocate_retainer(&pins, &v, 0, 1_000); // 300 / 700
                                                                  // both pins kept by the same pinner "zed" → aggregates to the full pool.
        let zed = did("did:key:zed");
        let (credits, total) = settle_retainer(&shares, |_pin| Some(zed.clone()));
        assert_eq!(total, 1_000);
        let mut balances = std::collections::HashMap::new();
        apply_retainer_credits(&mut balances, &credits);
        assert_eq!(balances[&zed], 1_000);
    }

    #[test]
    fn retainer_tracks_decay_over_epochs() {
        // As one agent's capital decays, its pin's share shrinks relative to a
        // freshly-minting agent — the allocation re-weights toward current value.
        let a = did("did:key:a");
        let b = did("did:key:b");
        let mut v = SocialCapitalView::new();
        v.apply(&[mint_delta(&a, MintSource::Disclosure, 100 * SCALE, 0)]);
        v.apply(&[mint_delta(&b, MintSource::Disclosure, 100 * SCALE, 30)]); // b mints a half-life later
        let pins = [pin("pa", "ra", &[&a]), pin("pb", "rb", &[&b])];
        // at epoch 30: a decayed to ~50, b is 100 → b gets ~2x a's share.
        let (shares, _) = allocate_retainer(&pins, &v, 30, 3_000);
        assert!(
            shares[1].retainer_mkoto > shares[0].retainer_mkoto,
            "fresh b > decayed a"
        );
        // a ≈ 1000, b ≈ 2000 (±rounding from the ~50/100 split)
        assert!(
            (shares[0].retainer_mkoto - 1_000).abs() <= 20,
            "a={}",
            shares[0].retainer_mkoto
        );
        assert!(
            (shares[1].retainer_mkoto - 2_000).abs() <= 20,
            "b={}",
            shares[1].retainer_mkoto
        );
    }
}
