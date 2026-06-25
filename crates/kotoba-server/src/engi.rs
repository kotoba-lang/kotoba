//! ENGI (縁起) — agent-centric **mutual-credit** ledger. Unit: **EN (縁)**.
//!
//! Renamed/redesigned from the former mint/burn `econ`/mKOTO ledger
//! (ADR-2606013400 → net-zero revision). Rationale: kotoba's substrate is
//! agent-centric (per-agent Source Chains, Warrant/Neighborhood validation, no
//! central master, no global consensus — ADR-001 "multi-writer without a global
//! consensus/ledger, agent-centric like Holochain"). A *minted, scarce* token
//! contradicts that (it needs global consensus on supply + a single total order
//! to prevent double-spend). The scarce/settled money already lives across the
//! boundary in etzhayyim (USDC on Base L2). So kotoba's internal unit is a
//! **mutual-credit** accounting of contribution, exactly like Holochain's
//! HoloFuel — and exactly what "縁起" (dependent origination) names: value has
//! no independent substance, it exists only as a *relation* between two agents.
//!
//! Model (net-zero):
//!   * `transfer(from → to, amount)` is the only primitive: `from -= amount`,
//!     `to += amount`. The sum of all balances is therefore an **invariant 0**
//!     (`EngiLedger::is_balanced`). Nothing is minted; nothing is burned.
//!   * A balance may go **negative** down to the account's **credit limit**.
//!     That bounds spam (a write debits the writer; once they hit their limit
//!     they must *earn* EN — by being cited / providing storage or compute —
//!     before writing more), replacing the old "buy tokens from the operator".
//!   * A **write fee** (`charge`) is `transfer(writer → operator, cost)`: the
//!     node provides the substrate, the writer pays for it. The operator self-
//!     writing is a transfer-to-self = free. `refund` reverses it.
//!   * Settlement / royalties (`batch_credit`) are transfers **from** the
//!     operator account (the node redistributes collected fees / extends
//!     credit), so the ledger stays net-zero.
//!
//! Units: 1 KOTO = 1_000_000 EN (matches `attestation.rs` /
//! `kotoba_query::citation::MKOTO_PER_KOTO`; the legacy `m`-prefix that wrongly
//! implied milli is dropped — EN is the base internal unit).
//!
//! Env:
//!   KOTOBA_WRITE_COST_EN     write fee per datom (default 10; 0 = off).
//!                            Falls back to KOTOBA_WRITE_COST_MKOTO_PER_DATOM.
//!   KOTOBA_READ_COST_EN      read fee per read op (default 0 = off).
//!   KOTOBA_CREDIT_LIMIT_EN   default per-agent credit limit (max negative).
//!   KOTOBA_STORE_PATH        dir for `engi-ledger.json` persistence.
//!
//! Persistence: balances + per-agent credit limits are written atomically
//! (temp file + rename) to `${KOTOBA_STORE_PATH}/engi-ledger.json` on each
//! change and reloaded at boot. A file that fails to parse is backed up to
//! `engi-ledger.json.corrupt` rather than silently discarded.
//!
//! ## Source of truth: the Source Chain, not this map (engi-mutual-credit-on-chain)
//!
//! As of the mesh-distributed mutual-credit work, the **canonical** record of an
//! EN movement is a countersigned [`kotoba_dht::MutualCreditTransfer`] appended to
//! both parties' per-DID Source Chains (`kotoba_dht::engi_chain`), Holochain-
//! HoloFuel style. A balance is *derived* by replaying those chains — there is no
//! authoritative global ledger. **This `Engi` map is a materialized projection /
//! cache** of that replay: [`Engi::project_transfer`] applies one chain-validated
//! transfer, and [`Engi::rebuild_from_transfers`] reconstructs the cache from a
//! complete transfer set at boot. The local JSON is a fast read surface and
//! crash-survivable cache, not the ledger of record. (The legacy `charge` /
//! `credit` / `batch_credit` fee paths still mutate the cache directly; folding
//! them onto countersigned transfers is the follow-up that makes the chain the
//! *sole* source of EN movement.)

use kotoba_dht::MutualCreditTransfer;
use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::Arc;
use tokio::sync::RwLock;

/// Recommended production per-datom write fee, in EN (matches the `assert = 10`
/// gas unit). Enable by setting `KOTOBA_WRITE_COST_EN`. The env **defaults to
/// `0` (disabled)** when unset so existing writers are unaffected until the
/// operator turns the economy on.
pub const RECOMMENDED_WRITE_COST_EN: i64 = 10;

/// Default per-agent credit limit (how far a balance may go negative) when no
/// explicit limit has been set for the DID. Spam is bounded by this: a fresh
/// agent may spend down to `-DEFAULT_CREDIT_LIMIT_EN` before it must earn EN.
pub const DEFAULT_CREDIT_LIMIT_EN: i64 = 1_000_000;

/// Reputation→credit conversion: mKOTO of **staked attestation reputation** that
/// grant **1 EN** of additional write credit. Chosen so the self-attestation
/// floor (`MIN_STAKE_SELF_ATTESTED` = 1,000 KOTO = 1e9 mKOTO) maps to exactly
/// `DEFAULT_CREDIT_LIMIT_EN`, and a verified-entity stake (5,000 KOTO) to 5×
/// that. The stake is a reputation signal (an attestation Datom), **not** an EN
/// transfer — it never moves balances, only widens how far the staked DID may
/// go into credit. Higher reputation ⇒ more write headroom before a 402.
pub const STAKE_MKOTO_PER_CREDIT_EN: u64 = 1_000;

/// Snapshot of the ledger's accounting at a point in time.
///
/// Invariant for a correctly-functioning mutual-credit ledger: `net == 0`.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct EngiLedger {
    /// Sum of **all** balances. Mutual-credit invariant: this is always 0.
    pub net: i64,
    /// Sum of positive balances (== sum of |negative balances|): the volume of
    /// credit currently extended / in use across the network.
    pub outstanding: i64,
    /// Number of accounts with a recorded balance.
    pub accounts: usize,
}

impl EngiLedger {
    /// True iff the net-zero invariant `net == 0` holds. A `false` here means
    /// the in-memory accounting has drifted — worth surfacing to operators.
    pub fn is_balanced(&self) -> bool {
        self.net == 0
    }
}

#[derive(serde::Serialize, serde::Deserialize, Default)]
struct Persisted {
    balances: HashMap<String, i64>,
    limits: HashMap<String, i64>,
}

#[derive(Default)]
struct Inner {
    /// Per-DID balances; may be negative down to the DID's credit limit. Σ == 0.
    balances: HashMap<String, i64>,
    /// Per-DID credit limits (override of `default_credit_limit`).
    limits: HashMap<String, i64>,
}

pub struct Engi {
    write_cost: i64,
    read_cost: i64,
    operator_did: String,
    default_credit_limit: i64,
    inner: RwLock<Inner>,
    persist_path: Option<PathBuf>,
}

impl Engi {
    /// Construct from env. The operator is an ordinary account (the node /
    /// substrate provider) with an effectively-unlimited credit limit, so its
    /// own writes and the credit it extends never block.
    pub fn from_env(operator_did: String) -> Arc<Self> {
        let write_cost = std::env::var("KOTOBA_WRITE_COST_EN")
            .or_else(|_| std::env::var("KOTOBA_WRITE_COST_MKOTO_PER_DATOM"))
            .ok()
            .and_then(|v| v.trim().parse::<i64>().ok())
            .unwrap_or(0)
            .max(0);

        let read_cost = std::env::var("KOTOBA_READ_COST_EN")
            .ok()
            .and_then(|v| v.trim().parse::<i64>().ok())
            .unwrap_or(0)
            .max(0);

        let default_credit_limit = std::env::var("KOTOBA_CREDIT_LIMIT_EN")
            .ok()
            .and_then(|v| v.trim().parse::<i64>().ok())
            .filter(|v| *v >= 0)
            .unwrap_or(DEFAULT_CREDIT_LIMIT_EN);

        let persist_path = std::env::var("KOTOBA_STORE_PATH")
            .ok()
            .map(|p| PathBuf::from(p).join("engi-ledger.json"));

        let inner = Self::load(persist_path.as_ref());

        Arc::new(Self {
            write_cost,
            read_cost,
            operator_did,
            default_credit_limit,
            inner: RwLock::new(inner),
            persist_path,
        })
    }

    /// Load the persisted ledger. A missing file is a normal first boot. A file
    /// that exists but fails to parse is backed up to `*.corrupt` and treated as
    /// empty, so a corrupt write never silently erases recoverable balances.
    fn load(persist_path: Option<&PathBuf>) -> Inner {
        let Some(pp) = persist_path else {
            return Inner::default();
        };
        match std::fs::read_to_string(pp) {
            Ok(s) => match serde_json::from_str::<Persisted>(&s) {
                Ok(p) => Inner {
                    balances: p.balances,
                    limits: p.limits,
                },
                Err(e) => {
                    let backup = pp.with_extension("json.corrupt");
                    let _ = std::fs::rename(pp, &backup);
                    tracing::error!(
                        path = ?pp, backup = ?backup, error = %e,
                        "engi: ledger file is corrupt — backed up and starting empty; \
                         restore the backup manually to recover balances"
                    );
                    Inner::default()
                }
            },
            Err(_) => Inner::default(), // missing file → first boot
        }
    }

    pub fn enabled(&self) -> bool {
        self.write_cost > 0
    }

    /// Per-datom write fee in EN (kept method name for the econ XRPC endpoint).
    pub fn cost_per_datom(&self) -> i64 {
        self.write_cost
    }

    /// Per-read fee in EN (0 = reads are free).
    pub fn read_cost(&self) -> i64 {
        self.read_cost
    }

    /// Write fee in EN for a transaction of `datom_count` datoms.
    pub fn cost_for(&self, datom_count: usize) -> i64 {
        self.write_cost.saturating_mul(datom_count as i64)
    }

    pub async fn balance(&self, did: &str) -> i64 {
        *self.inner.read().await.balances.get(did).unwrap_or(&0)
    }

    /// The effective credit limit (max negative balance) for `did`.
    pub async fn credit_limit(&self, did: &str) -> i64 {
        let g = self.inner.read().await;
        self.limit_for(&g, did)
    }

    /// Set an explicit credit limit for `did` (operator action — reputation /
    /// stake driven). Callers must enforce operator auth before calling.
    pub async fn set_credit_limit(&self, did: &str, limit: i64) {
        let mut g = self.inner.write().await;
        g.limits.insert(did.to_string(), limit.max(0));
        let snapshot = Self::persisted(&g);
        drop(g);
        self.persist(snapshot);
    }

    /// The credit limit (in EN) earned by a staked attestation reputation of
    /// `stake_mkoto`. Scales linearly at [`STAKE_MKOTO_PER_CREDIT_EN`] and is
    /// floored at [`DEFAULT_CREDIT_LIMIT_EN`] so a staked DID never gets *less*
    /// headroom than an unstaked one. Saturates rather than overflowing on an
    /// absurd stake.
    pub fn credit_limit_for_stake(stake_mkoto: u64) -> i64 {
        let derived = (stake_mkoto / STAKE_MKOTO_PER_CREDIT_EN).min(i64::MAX as u64) as i64;
        derived.max(DEFAULT_CREDIT_LIMIT_EN)
    }

    /// Wire a staked attestation into the ledger: raise `did`'s credit limit to
    /// reflect `stake_mkoto`, **monotonically** — a new (or smaller) attestation
    /// never claws back headroom the DID already earned, so reputation only
    /// accrues. Returns the effective limit. This is the reputation → write-
    /// headroom link the spam bound was designed around (a fresh agent gets the
    /// default; a staked one earns more before hitting a 402). No EN moves.
    pub async fn raise_credit_limit_for_stake(&self, did: &str, stake_mkoto: u64) -> i64 {
        let derived = Self::credit_limit_for_stake(stake_mkoto);
        let mut g = self.inner.write().await;
        let new = self.limit_for(&g, did).max(derived);
        g.limits.insert(did.to_string(), new);
        let snapshot = Self::persisted(&g);
        drop(g);
        self.persist(snapshot);
        new
    }

    fn limit_for(&self, g: &Inner, did: &str) -> i64 {
        if did == self.operator_did {
            // The operator/provider extends credit and writes the node's own
            // substrate — effectively unlimited (/4 keeps `bal + limit` from
            // overflowing i64 even when the operator is deep in credit).
            return i64::MAX / 4;
        }
        g.limits
            .get(did)
            .copied()
            .unwrap_or(self.default_credit_limit)
    }

    /// The mutual-credit primitive: move `amount` EN from `from` to `to`.
    /// `from -= amount`, `to += amount` — net-zero by construction. Fails with
    /// `Err((needed, available))` if `from` lacks the credit headroom. Returns
    /// `from`'s new balance on success. A non-positive amount or a self-transfer
    /// is a no-op.
    pub async fn transfer(&self, from: &str, to: &str, amount: i64) -> Result<i64, (i64, i64)> {
        if amount <= 0 || from == to {
            return Ok(self.balance(from).await);
        }
        let mut g = self.inner.write().await;
        let from_bal = g.balances.get(from).copied().unwrap_or(0);
        let limit = self.limit_for(&g, from);
        // How much `from` can still send before hitting `-limit`.
        let available = from_bal.saturating_add(limit);
        if amount > available {
            return Err((amount, available));
        }
        let new_from = from_bal - amount;
        let to_bal = g.balances.get(to).copied().unwrap_or(0);
        g.balances.insert(from.to_string(), new_from);
        g.balances
            .insert(to.to_string(), to_bal.saturating_add(amount));
        let snapshot = Self::persisted(&g);
        drop(g);
        self.persist(snapshot);
        Ok(new_from)
    }

    /// Charge `payer` a fee (write or read) by transferring it to the operator.
    /// The operator is exempt (self-transfer = free). Returns `Ok(remaining)` or
    /// `Err((needed, available_credit))` for an HTTP 402.
    pub async fn charge(&self, payer: &str, cost: i64) -> Result<i64, (i64, i64)> {
        if payer == self.operator_did || cost <= 0 {
            return Ok(self.balance(payer).await);
        }
        let op = self.operator_did.clone();
        self.transfer(payer, &op, cost).await
    }

    /// Reverse a previously charged fee (commit failed after charge): transfer
    /// it back from the operator to `payer`. Charge + equal refund is net-zero.
    pub async fn refund(&self, payer: &str, amount: i64) {
        if payer == self.operator_did || amount <= 0 {
            return;
        }
        let op = self.operator_did.clone();
        let _ = self.transfer(&op, payer, amount).await;
    }

    /// Operator extends (or claws back) credit to `did`. Positive: transfer
    /// operator → did. Negative: claw back up to the DID's positive balance
    /// (never forces a DID into the negative). Returns the DID's new balance.
    /// Callers must enforce operator auth before calling. Kept name for the
    /// econ XRPC `credit` endpoint.
    pub async fn credit(&self, did: &str, amount: i64) -> i64 {
        if did == self.operator_did {
            return self.balance(did).await;
        }
        let op = self.operator_did.clone();
        if amount > 0 {
            let _ = self.transfer(&op, did, amount).await;
        } else if amount < 0 {
            let bal = self.balance(did).await;
            let take = (-amount).min(bal.max(0));
            let _ = self.transfer(did, &op, take).await;
        }
        self.balance(did).await
    }

    /// Atomically apply many operator→recipient credits in one locked, one
    /// persisted batch (settlement). A partial crash can't leave some recipients
    /// credited and others not. The operator entry and non-positive amounts are
    /// skipped. Returns the total EN transferred into recipients.
    pub async fn batch_credit(&self, credits: &[(String, i64)]) -> i64 {
        let op = self.operator_did.clone();
        let mut g = self.inner.write().await;
        let mut total = 0i64;
        for (did, amount) in credits {
            if did == &op || *amount <= 0 {
                continue;
            }
            let to_bal = g.balances.get(did).copied().unwrap_or(0);
            g.balances
                .insert(did.clone(), to_bal.saturating_add(*amount));
            // Operator extends the credit (its balance falls); ledger stays net-zero.
            let op_bal = g.balances.get(&op).copied().unwrap_or(0);
            g.balances.insert(op.clone(), op_bal - *amount);
            total = total.saturating_add(*amount);
        }
        let snapshot = Self::persisted(&g);
        drop(g);
        self.persist(snapshot);
        total
    }

    /// Project one **chain-validated** countersigned transfer into the cache:
    /// debit the spender, credit the receiver. Net-zero by construction and
    /// applied **unconditionally** — the transfer is already a committed fact on
    /// both parties' Source Chains (its credit-limit/solvency was enforced at
    /// append time by `kotoba_dht::EngiChain::record_spend`), so the projection
    /// must mirror it rather than re-judge it. This is the entry point the gossip
    /// / chain-replay path calls per observed transfer. A non-positive amount or a
    /// self-transfer is a no-op. Persisted so the cache survives restart.
    pub async fn project_transfer(&self, t: &MutualCreditTransfer) {
        let amount = t.body.amount;
        if amount <= 0 || t.body.spender == t.body.receiver {
            return;
        }
        let mut g = self.inner.write().await;
        Self::apply_transfer(&mut g, &t.body.spender, &t.body.receiver, amount);
        let snapshot = Self::persisted(&g);
        drop(g);
        self.persist(snapshot);
    }

    /// Rebuild the entire balance cache by replaying `transfers` from an empty
    /// map — the boot-time projection of the EN mutual-credit ledger from the
    /// Source Chains. `transfers` must be the *complete* set of EN movements
    /// (every countersigned transfer across the agents this node tracks); the
    /// result is exactly net-zero. Per-agent credit limits are preserved (they are
    /// reputation state, not EN). One locked, one persisted write.
    ///
    /// Note: until the legacy fee paths (`charge` / `batch_credit`) are themselves
    /// countersigned transfers, a node that uses those must seed `transfers` with
    /// their equivalents, or call this only on a node whose EN moves are all
    /// on-chain — otherwise fee balances are not represented here.
    pub async fn rebuild_from_transfers(&self, transfers: &[MutualCreditTransfer]) {
        let mut g = self.inner.write().await;
        g.balances.clear();
        for t in transfers {
            if t.body.amount <= 0 || t.body.spender == t.body.receiver {
                continue;
            }
            Self::apply_transfer(&mut g, &t.body.spender, &t.body.receiver, t.body.amount);
        }
        let snapshot = Self::persisted(&g);
        drop(g);
        self.persist(snapshot);
    }

    /// Net-zero balance move inside a held write lock: `spender -= amount`,
    /// `receiver += amount` (saturating). Shared by both projection paths.
    fn apply_transfer(g: &mut Inner, spender: &str, receiver: &str, amount: i64) {
        let sb = g.balances.get(spender).copied().unwrap_or(0);
        g.balances.insert(spender.to_string(), sb.saturating_sub(amount));
        let rb = g.balances.get(receiver).copied().unwrap_or(0);
        g.balances
            .insert(receiver.to_string(), rb.saturating_add(amount));
    }

    /// Ledger snapshot for audit: `{ net (==0), outstanding, accounts }`.
    pub async fn ledger(&self) -> EngiLedger {
        let g = self.inner.read().await;
        let mut net = 0i64;
        let mut outstanding = 0i64;
        for v in g.balances.values() {
            net = net.saturating_add(*v);
            if *v > 0 {
                outstanding = outstanding.saturating_add(*v);
            }
        }
        EngiLedger {
            net,
            outstanding,
            accounts: g.balances.len(),
        }
    }

    fn persisted(g: &Inner) -> Persisted {
        Persisted {
            balances: g.balances.clone(),
            limits: g.limits.clone(),
        }
    }

    /// Persist atomically: write a sibling temp file, then rename over the live
    /// file (atomic on POSIX), so a concurrent reader or a crash never observes
    /// a half-written file. Failures are logged rather than swallowed.
    fn persist(&self, snapshot: Persisted) {
        let Some(pp) = &self.persist_path else {
            return;
        };
        let s = match serde_json::to_string(&snapshot) {
            Ok(s) => s,
            Err(e) => {
                tracing::warn!(error = %e, "engi: failed to serialize ledger — not persisted");
                return;
            }
        };
        let tmp = pp.with_extension("json.tmp");
        if let Err(e) = std::fs::write(&tmp, &s) {
            tracing::warn!(path = ?tmp, error = %e, "engi: failed to write temp ledger file — not persisted");
            return;
        }
        if let Err(e) = std::fs::rename(&tmp, pp) {
            tracing::warn!(path = ?pp, error = %e, "engi: failed to atomically rename ledger file — not persisted");
            let _ = std::fs::remove_file(&tmp);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn engi(write_cost: i64, op: &str) -> Arc<Engi> {
        engi_persisted(write_cost, op, None)
    }

    fn engi_persisted(write_cost: i64, op: &str, persist_path: Option<PathBuf>) -> Arc<Engi> {
        Arc::new(Engi {
            write_cost,
            read_cost: 0,
            operator_did: op.to_string(),
            default_credit_limit: 1000,
            inner: RwLock::new(Inner::default()),
            persist_path,
        })
    }

    #[tokio::test]
    async fn transfer_is_net_zero_and_respects_credit_limit() {
        let e = engi(10, "did:key:op");
        // a has default limit 1000 → can go to -1000.
        assert_eq!(e.transfer("did:key:a", "did:key:b", 600).await, Ok(-600));
        assert_eq!(e.balance("did:key:a").await, -600);
        assert_eq!(e.balance("did:key:b").await, 600);
        // Net-zero invariant holds.
        let l = e.ledger().await;
        assert_eq!(l.net, 0);
        assert!(l.is_balanced());
        assert_eq!(l.outstanding, 600);
        // a can send 400 more (down to -1000), but not 401.
        assert_eq!(
            e.transfer("did:key:a", "did:key:b", 401).await,
            Err((401, 400))
        );
        assert_eq!(e.transfer("did:key:a", "did:key:b", 400).await, Ok(-1000));
        assert!(e.ledger().await.is_balanced());
    }

    #[tokio::test]
    async fn charge_transfers_fee_to_operator_and_stays_balanced() {
        let e = engi(10, "did:key:op");
        // External writer pays a write fee → operator earns it; net-zero.
        assert_eq!(e.charge("did:key:ext", 30).await, Ok(-30));
        assert_eq!(e.balance("did:key:ext").await, -30);
        assert_eq!(e.balance("did:key:op").await, 30);
        assert!(e.ledger().await.is_balanced());
    }

    #[tokio::test]
    async fn operator_write_is_free_self_transfer() {
        let e = engi(10, "did:key:op");
        // Operator paying itself is a no-op (free node self-write), unlimited.
        assert_eq!(e.charge("did:key:op", e.cost_for(1_000_000)).await, Ok(0));
        assert_eq!(e.balance("did:key:op").await, 0);
        assert!(e.ledger().await.is_balanced());
    }

    #[tokio::test]
    async fn charge_blocked_when_credit_limit_exhausted() {
        let e = engi(10, "did:key:op"); // default limit 1000
        assert!(e.charge("did:key:ext", 1000).await.is_ok()); // ext now at -1000
                                                              // Over the limit — rejected, balances unchanged.
        assert_eq!(e.charge("did:key:ext", 1).await, Err((1, 0)));
        assert_eq!(e.balance("did:key:ext").await, -1000);
        assert!(e.ledger().await.is_balanced());
    }

    #[tokio::test]
    async fn refund_reverses_charge_net_zero() {
        let e = engi(10, "did:key:op");
        e.charge("did:key:ext", 30).await.unwrap();
        e.refund("did:key:ext", 30).await;
        assert_eq!(e.balance("did:key:ext").await, 0);
        assert_eq!(e.balance("did:key:op").await, 0);
        let l = e.ledger().await;
        assert!(l.is_balanced());
        assert_eq!(l.outstanding, 0);
    }

    #[tokio::test]
    async fn batch_credit_is_atomic_and_net_zero() {
        let e = engi(10, "did:key:op");
        let total = e
            .batch_credit(&[
                ("did:key:a".into(), 40),
                ("did:key:b".into(), 25),
                ("did:key:op".into(), 99), // operator skipped
                ("did:key:c".into(), 0),   // zero skipped
            ])
            .await;
        assert_eq!(total, 65);
        assert_eq!(e.balance("did:key:a").await, 40);
        assert_eq!(e.balance("did:key:b").await, 25);
        // Operator extended the credit → its balance is -65; net-zero overall.
        assert_eq!(e.balance("did:key:op").await, -65);
        let l = e.ledger().await;
        assert!(l.is_balanced());
        assert_eq!(l.outstanding, 65);
    }

    #[tokio::test]
    async fn credit_endpoint_extends_and_claws_back() {
        let e = engi(10, "did:key:op");
        assert_eq!(e.credit("did:key:ext", 100).await, 100);
        assert_eq!(e.balance("did:key:op").await, -100);
        // Claw back 30; never forces ext negative.
        assert_eq!(e.credit("did:key:ext", -30).await, 70);
        // Clawing back more than the positive balance only takes what's there.
        assert_eq!(e.credit("did:key:ext", -1000).await, 0);
        assert!(e.ledger().await.is_balanced());
    }

    #[tokio::test]
    async fn disabled_when_write_cost_zero() {
        let e = engi(0, "did:key:op");
        assert!(!e.enabled());
        // cost 0 → charge always succeeds (no fee taken).
        assert_eq!(e.charge("did:key:ext", e.cost_for(99)).await, Ok(0));
        assert_eq!(e.balance("did:key:ext").await, 0);
    }

    #[tokio::test]
    async fn cost_scales_with_datom_count() {
        let e = engi(10, "did:key:op");
        assert_eq!(e.cost_for(0), 0);
        assert_eq!(e.cost_for(5), 50);
    }

    #[tokio::test]
    async fn set_credit_limit_overrides_default() {
        let e = engi(10, "did:key:op");
        e.set_credit_limit("did:key:vip", 5000).await;
        assert_eq!(e.credit_limit("did:key:vip").await, 5000);
        // vip can now spend down to -5000.
        assert_eq!(e.charge("did:key:vip", 5000).await, Ok(-5000));
        assert_eq!(e.charge("did:key:vip", 1).await, Err((1, 0)));
    }

    #[test]
    fn credit_limit_for_stake_floors_at_default_and_scales() {
        // Self-attest floor (1,000 KOTO = 1e9 mKOTO) maps to exactly the default.
        assert_eq!(
            Engi::credit_limit_for_stake(1_000 * 1_000_000),
            DEFAULT_CREDIT_LIMIT_EN
        );
        // Verified-entity stake (5,000 KOTO) → 5× the default.
        assert_eq!(
            Engi::credit_limit_for_stake(5_000 * 1_000_000),
            5 * DEFAULT_CREDIT_LIMIT_EN
        );
        // Below the floor (or zero stake) still yields the default, never less.
        assert_eq!(Engi::credit_limit_for_stake(0), DEFAULT_CREDIT_LIMIT_EN);
        // A huge stake scales up without overflowing into a negative i64.
        let huge = Engi::credit_limit_for_stake(u64::MAX);
        assert!(huge > 5 * DEFAULT_CREDIT_LIMIT_EN);
    }

    #[tokio::test]
    async fn raise_credit_limit_for_stake_is_monotonic_and_widens_headroom() {
        // Use the production default so the floor matches the wired behaviour
        // (the `engi()` helper hard-codes a tiny 1000 default for other tests).
        let e = Arc::new(Engi {
            write_cost: 10,
            read_cost: 0,
            operator_did: "did:key:op".to_string(),
            default_credit_limit: DEFAULT_CREDIT_LIMIT_EN,
            inner: RwLock::new(Inner::default()),
            persist_path: None,
        });
        let agent = "did:key:agent";
        // Default headroom: can spend to -1_000_000, the 1_000_001st EN blocks.
        assert_eq!(e.credit_limit(agent).await, DEFAULT_CREDIT_LIMIT_EN);

        // A verified-entity stake lifts the limit to 5× the default.
        let limit = e
            .raise_credit_limit_for_stake(agent, 5_000 * 1_000_000)
            .await;
        assert_eq!(limit, 5 * DEFAULT_CREDIT_LIMIT_EN);
        assert_eq!(e.credit_limit(agent).await, 5 * DEFAULT_CREDIT_LIMIT_EN);
        // The widened headroom is real: a charge that would exceed the default
        // now succeeds, and net-zero still holds.
        assert_eq!(
            e.charge(agent, 5 * DEFAULT_CREDIT_LIMIT_EN).await,
            Ok(-5 * DEFAULT_CREDIT_LIMIT_EN)
        );
        assert!(e.ledger().await.is_balanced());

        // A later, smaller attestation never claws back earned headroom.
        let after = e
            .raise_credit_limit_for_stake(agent, 1_000 * 1_000_000)
            .await;
        assert_eq!(
            after,
            5 * DEFAULT_CREDIT_LIMIT_EN,
            "reputation only accrues"
        );
    }

    #[tokio::test]
    async fn persist_is_atomic_and_reloads() {
        let dir = std::env::temp_dir().join(format!("kotoba-engi-test-{}", std::process::id()));
        let _ = std::fs::create_dir_all(&dir);
        let pp = dir.join("engi-ledger.json");
        let _ = std::fs::remove_file(&pp);

        {
            let e = engi_persisted(10, "did:key:op", Some(pp.clone()));
            e.set_credit_limit("did:key:ext", 9000).await;
            e.charge("did:key:ext", 120).await.unwrap(); // ext -120, op +120
            assert!(
                !pp.with_extension("json.tmp").exists(),
                "temp file must be renamed away after persist"
            );
        }

        let reloaded = Engi::load(Some(&pp));
        assert_eq!(reloaded.balances.get("did:key:ext").copied(), Some(-120));
        assert_eq!(reloaded.balances.get("did:key:op").copied(), Some(120));
        assert_eq!(reloaded.limits.get("did:key:ext").copied(), Some(9000));
        // Reloaded ledger is still net-zero.
        let net: i64 = reloaded.balances.values().sum();
        assert_eq!(net, 0);

        let _ = std::fs::remove_dir_all(&dir);
    }

    fn mk_transfer(spender: &str, receiver: &str, amount: i64) -> MutualCreditTransfer {
        // Projection mirrors a *committed* chain fact, so it never inspects the
        // signatures — a dummy-signed body exercises the net-zero cache math.
        MutualCreditTransfer {
            body: kotoba_dht::TransferBody {
                spender: spender.to_string(),
                receiver: receiver.to_string(),
                amount,
                spender_prev: None,
                receiver_prev: None,
                nonce: 0,
                ts: 0,
            },
            spender_sig: Vec::new(),
            receiver_sig: Vec::new(),
        }
    }

    #[tokio::test]
    async fn project_transfer_is_net_zero_and_persists() {
        let e = engi(10, "did:key:op");
        e.project_transfer(&mk_transfer("did:key:a", "did:key:b", 300))
            .await;
        assert_eq!(e.balance("did:key:a").await, -300);
        assert_eq!(e.balance("did:key:b").await, 300);
        let l = e.ledger().await;
        assert!(l.is_balanced(), "projection keeps the ledger net-zero");
        assert_eq!(l.outstanding, 300);

        // A second transfer accumulates; still net-zero.
        e.project_transfer(&mk_transfer("did:key:b", "did:key:c", 100))
            .await;
        assert_eq!(e.balance("did:key:b").await, 200);
        assert_eq!(e.balance("did:key:c").await, 100);
        assert!(e.ledger().await.is_balanced());
    }

    #[tokio::test]
    async fn project_transfer_bypasses_credit_limit_mirroring_chain_fact() {
        // The chain already authorised this (possibly via reputation headroom the
        // local node doesn't track); the projection must apply it regardless of
        // the tiny default limit, unlike `transfer`/`charge`.
        let e = engi(10, "did:key:op"); // default limit 1000
        e.project_transfer(&mk_transfer("did:key:a", "did:key:b", 50_000))
            .await;
        assert_eq!(e.balance("did:key:a").await, -50_000);
        assert_eq!(e.balance("did:key:b").await, 50_000);
        assert!(e.ledger().await.is_balanced());
    }

    #[tokio::test]
    async fn project_transfer_ignores_non_positive_and_self() {
        let e = engi(10, "did:key:op");
        e.project_transfer(&mk_transfer("did:key:a", "did:key:b", 0))
            .await;
        e.project_transfer(&mk_transfer("did:key:a", "did:key:a", 100))
            .await;
        assert_eq!(e.balance("did:key:a").await, 0);
        assert_eq!(e.balance("did:key:b").await, 0);
    }

    #[tokio::test]
    async fn rebuild_from_transfers_replays_to_net_zero_and_keeps_limits() {
        let e = engi(10, "did:key:op");
        e.set_credit_limit("did:key:a", 9_000).await; // reputation state, must survive
        let transfers = vec![
            mk_transfer("did:key:a", "did:key:b", 300),
            mk_transfer("did:key:b", "did:key:c", 100),
            mk_transfer("did:key:a", "did:key:c", 50),
        ];
        e.rebuild_from_transfers(&transfers).await;
        assert_eq!(e.balance("did:key:a").await, -350);
        assert_eq!(e.balance("did:key:b").await, 200);
        assert_eq!(e.balance("did:key:c").await, 150);
        let l = e.ledger().await;
        assert!(l.is_balanced());
        assert_eq!(l.outstanding, 350);
        // Credit limits are reputation, not EN — preserved across a rebuild.
        assert_eq!(e.credit_limit("did:key:a").await, 9_000);
    }

    #[tokio::test]
    async fn rebuild_from_transfers_is_idempotent_from_clean_state() {
        let e = engi(10, "did:key:op");
        let transfers = vec![mk_transfer("did:key:a", "did:key:b", 42)];
        e.rebuild_from_transfers(&transfers).await;
        e.rebuild_from_transfers(&transfers).await; // replay again — clears first
        assert_eq!(e.balance("did:key:a").await, -42);
        assert_eq!(e.balance("did:key:b").await, 42);
        assert!(e.ledger().await.is_balanced());
    }

    #[tokio::test]
    async fn corrupt_ledger_file_is_backed_up_not_lost() {
        let dir = std::env::temp_dir().join(format!("kotoba-engi-corrupt-{}", std::process::id()));
        let _ = std::fs::create_dir_all(&dir);
        let pp = dir.join("engi-ledger.json");
        std::fs::write(&pp, b"{ not valid json").unwrap();

        let inner = Engi::load(Some(&pp));
        assert!(inner.balances.is_empty());
        assert!(
            pp.with_extension("json.corrupt").exists(),
            "corrupt file must be preserved as .corrupt, not silently dropped"
        );

        let _ = std::fs::remove_dir_all(&dir);
    }
}
