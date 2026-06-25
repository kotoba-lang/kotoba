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
//! crash-survivable cache, not the ledger of record.
//!
//! **All EN movement is durable.** Two append-only logs sit beside the cache:
//! `engi-transfers.jsonl` (peer-countersigned [`kotoba_dht::MutualCreditTransfer`]s)
//! and `engi-fees.jsonl` (operator fee/settlement moves from `charge` / `credit` /
//! `batch_credit` / `refund`). A lost or corrupt balance cache is **rebuilt by
//! replaying both logs**, so the durable record — not the JSON cache — is the sole
//! source of EN movement. (Fees are operator-attested, not peer-countersigned:
//! the payer authorizes via its CACAO-authed write, not an Ed25519 transfer
//! signature. Turning fees into a 2-party countersigning handshake is a separate
//! protocol change, deliberately not done here.)

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

/// Resolve an agent DID to its 32-byte Ed25519 public key for verifying
/// mutual-credit countersignatures. R2 supports `did:key` (the scheme
/// `AgentIdentity` mints); other methods (`did:plc`, `did:web`) resolve to
/// `None` until their resolution is wired. Used by the gossip-receive path and
/// the `engi.transfer` endpoint to reject forged transfers before projecting,
/// and as `kotoba_dht::audit_peer_chain`'s `resolve` closure.
pub fn resolve_did_pubkey(did: &str) -> Option<[u8; 32]> {
    kotoba_auth::parse_ed25519_did_key(did).ok()
}

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

/// A durable record of an **operator fee / settlement** EN movement — a net-zero
/// `from → to` move from `charge` / `credit` / `batch_credit` / `refund`. These
/// are NOT peer-countersigned transfers (the payer authorizes via its CACAO-authed
/// write, not an Ed25519 transfer signature), so they live in a separate log from
/// the countersigned transfer record. Logging them makes the durable record the
/// **sole source of EN movement**: a lost balance cache recovers fee balances too.
#[derive(serde::Serialize, serde::Deserialize, Clone, Debug)]
struct EnFeeMove {
    from: String,
    to: String,
    amount: i64,
    /// Provenance tag (`charge` / `credit` / `settlement` / `refund`) — metadata
    /// for audit/debug; recovery only needs `from`/`to`/`amount`.
    kind: String,
}

#[derive(Default)]
struct Inner {
    /// Per-DID balances; may be negative down to the DID's credit limit. Σ == 0.
    balances: HashMap<String, i64>,
    /// Per-DID credit limits (override of `default_credit_limit`).
    limits: HashMap<String, i64>,
    /// The **durable record** of every countersigned transfer projected here, in
    /// arrival order — loaded from the append-only transfer log at boot and grown
    /// by [`Engi::project_transfer`]. This is the canonical mutual-credit history
    /// the balance cache is derived from (and the source a validator audits / a
    /// boot rebuild replays). Fee paths (`charge`/`credit`) do NOT append here —
    /// they are not countersigned transfers (folding them in is a deferred ADR
    /// follow-up).
    transfers: Vec<MutualCreditTransfer>,
}

pub struct Engi {
    write_cost: i64,
    read_cost: i64,
    operator_did: String,
    default_credit_limit: i64,
    inner: RwLock<Inner>,
    persist_path: Option<PathBuf>,
    /// Append-only JSONL log of countersigned transfers (sibling of the balance
    /// JSON: `${KOTOBA_STORE_PATH}/engi-transfers.jsonl`). Durable canonical
    /// record; the balance JSON is a fast cache rebuilt from this if lost.
    transfer_log_path: Option<PathBuf>,
    /// Append-only JSONL log of operator fee / settlement EN moves
    /// (`${KOTOBA_STORE_PATH}/engi-fees.jsonl`). Replayed alongside the transfer
    /// log on cache loss so fee balances recover too.
    fee_log_path: Option<PathBuf>,
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
        let transfer_log_path = persist_path
            .as_ref()
            .map(|p| p.with_file_name("engi-transfers.jsonl"));
        let fee_log_path = persist_path
            .as_ref()
            .map(|p| p.with_file_name("engi-fees.jsonl"));

        let inner = Self::load(
            persist_path.as_ref(),
            transfer_log_path.as_ref(),
            fee_log_path.as_ref(),
        );

        Arc::new(Self {
            write_cost,
            read_cost,
            operator_did,
            default_credit_limit,
            inner: RwLock::new(inner),
            persist_path,
            transfer_log_path,
            fee_log_path,
        })
    }

    /// Load the persisted ledger at boot: the balance/limit **cache** (fast path)
    /// plus the durable record — the **transfer log** (countersigned transfers)
    /// and the **fee log** (operator fee/settlement moves). If the balance cache
    /// is absent, the balances are **rebuilt by replaying both logs** — together
    /// they are the sole source of EN movement, so a lost/corrupt cache fully
    /// recovers (transfers *and* fee balances).
    fn load(
        persist_path: Option<&PathBuf>,
        transfer_log_path: Option<&PathBuf>,
        fee_log_path: Option<&PathBuf>,
    ) -> Inner {
        let (mut balances, limits, had_cache) = Self::load_balances(persist_path);
        let transfers = Self::load_transfer_log(transfer_log_path);
        let fees = Self::load_fee_log(fee_log_path);

        if !had_cache && (!transfers.is_empty() || !fees.is_empty()) {
            // Recovery: the fast cache is gone but the durable logs aren't —
            // reconstruct balances by replaying every EN movement. Order doesn't
            // matter: each move is an additive net-zero (from −= amt, to += amt).
            for t in &transfers {
                if t.body.amount > 0 && t.body.spender != t.body.receiver {
                    Self::apply_to_map(
                        &mut balances,
                        &t.body.spender,
                        &t.body.receiver,
                        t.body.amount,
                    );
                }
            }
            for m in &fees {
                if m.amount > 0 && m.from != m.to {
                    Self::apply_to_map(&mut balances, &m.from, &m.to, m.amount);
                }
            }
            tracing::info!(
                transfers = transfers.len(),
                fees = fees.len(),
                "engi: balance cache absent — rebuilt all balances from the durable transfer + fee logs"
            );
        }

        Inner {
            balances,
            limits,
            transfers,
        }
    }

    /// Load the durable fee log (append-only JSONL, one [`EnFeeMove`] per line).
    /// A torn/garbled trailing line (crash mid-append) is skipped with a warning.
    fn load_fee_log(fee_log_path: Option<&PathBuf>) -> Vec<EnFeeMove> {
        let Some(lp) = fee_log_path else {
            return Vec::new();
        };
        let Ok(s) = std::fs::read_to_string(lp) else {
            return Vec::new();
        };
        let mut out = Vec::new();
        for (i, line) in s.lines().enumerate() {
            if line.trim().is_empty() {
                continue;
            }
            match serde_json::from_str::<EnFeeMove>(line) {
                Ok(m) => out.push(m),
                Err(e) => tracing::warn!(
                    line = i + 1, error = %e,
                    "engi: skipping unparseable fee-log line (likely a torn append)"
                ),
            }
        }
        out
    }

    /// Load the balance/limit cache JSON. Returns `(balances, limits, had_cache)`
    /// where `had_cache` is `true` iff the file existed and parsed. A corrupt file
    /// is backed up to `*.corrupt` and treated as a cache miss (so recovery from
    /// the transfer log can kick in) rather than silently erased.
    fn load_balances(
        persist_path: Option<&PathBuf>,
    ) -> (HashMap<String, i64>, HashMap<String, i64>, bool) {
        let Some(pp) = persist_path else {
            return (HashMap::new(), HashMap::new(), false);
        };
        match std::fs::read_to_string(pp) {
            Ok(s) => match serde_json::from_str::<Persisted>(&s) {
                Ok(p) => (p.balances, p.limits, true),
                Err(e) => {
                    let backup = pp.with_extension("json.corrupt");
                    let _ = std::fs::rename(pp, &backup);
                    tracing::error!(
                        path = ?pp, backup = ?backup, error = %e,
                        "engi: ledger file is corrupt — backed up; rebuilding balances from the transfer log if present"
                    );
                    (HashMap::new(), HashMap::new(), false)
                }
            },
            Err(_) => (HashMap::new(), HashMap::new(), false), // missing → first boot
        }
    }

    /// Load the durable transfer log (append-only JSONL, one
    /// [`MutualCreditTransfer`] per line). A torn/garbled trailing line (from a
    /// crash mid-append) is skipped with a warning rather than aborting the load,
    /// so one bad line never costs the whole history.
    fn load_transfer_log(transfer_log_path: Option<&PathBuf>) -> Vec<MutualCreditTransfer> {
        let Some(lp) = transfer_log_path else {
            return Vec::new();
        };
        let Ok(s) = std::fs::read_to_string(lp) else {
            return Vec::new(); // missing → no transfers yet
        };
        let mut out = Vec::new();
        for (i, line) in s.lines().enumerate() {
            if line.trim().is_empty() {
                continue;
            }
            match serde_json::from_str::<MutualCreditTransfer>(line) {
                Ok(t) => out.push(t),
                Err(e) => tracing::warn!(
                    line = i + 1, error = %e,
                    "engi: skipping unparseable transfer-log line (likely a torn append)"
                ),
            }
        }
        out
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
        // Durable fee/settlement record so a lost cache recovers this move too.
        self.append_fee_log(from, to, amount, "transfer");
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
        let mut applied: Vec<(String, i64)> = Vec::new();
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
            applied.push((did.clone(), *amount));
        }
        let snapshot = Self::persisted(&g);
        drop(g);
        self.persist(snapshot);
        // Durable settlement record (operator → recipient per applied credit).
        for (did, amount) in &applied {
            self.append_fee_log(&op, did, *amount, "settlement");
        }
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
        // Append to the durable record (in-memory + on-disk log) so the transfer
        // survives a lost balance cache and is auditable / replayable.
        g.transfers.push(t.clone());
        let snapshot = Self::persisted(&g);
        drop(g);
        self.persist(snapshot);
        self.append_transfer_log(t);
    }

    /// Snapshot of the durable transfer record (every countersigned transfer
    /// projected here, in order). The input a validator audits via
    /// `kotoba_dht::audit_peer_chain` and that `rebuild_from_transfers` replays.
    pub async fn transfers(&self) -> Vec<MutualCreditTransfer> {
        self.inner.read().await.transfers.clone()
    }

    /// Number of transfers in the durable record.
    pub async fn transfer_count(&self) -> usize {
        self.inner.read().await.transfers.len()
    }

    /// Audit the durable transfer record for **insolvency** — any agent whose
    /// accumulated gossiped transfers drove its balance below its credit limit.
    /// Because `project_transfer` applies transfers unconditionally (it mirrors
    /// committed facts), a peer that overspends is only caught here, by replaying
    /// the record against each agent's effective limit. An empty result means the
    /// projected ledger is solvent. (Chain forks are out of scope — they need
    /// per-DID `ChainEntry`s, not the flat transfer record.)
    pub async fn audit_solvency(&self) -> Vec<kotoba_dht::InsolvencyFinding> {
        let g = self.inner.read().await;
        let transfers = g.transfers.clone();
        kotoba_dht::audit_transfers(&transfers, |did| self.limit_for(&g, did))
    }

    /// Detect **double-spend forks** in the durable transfer record — any agent
    /// that signed two distinct transfers pinning the same chain position
    /// (`spender_prev`). Works over the gossip-accumulated record, so it catches a
    /// peer's double-spend without a separate per-DID chain sync. Empty = no fork
    /// seen.
    pub async fn detect_forks(&self) -> Vec<kotoba_dht::TransferFork> {
        let g = self.inner.read().await;
        kotoba_dht::detect_transfer_forks(&g.transfers)
    }

    /// Turn every current violation (insolvency + double-spend fork) into a
    /// **signed, gossip-ready** `kotoba_dht::Warrant`, closing the validator loop:
    /// detection → an evidence-bearing accusation the neighborhood can act on
    /// (`ValidationRule::DoubleSpend`, K/2 warrants → eviction). `signing_key` is
    /// the validating node's key; `validator_id` its NodeId/pubkey bytes. The
    /// accused is each offender's resolved `did:key` pubkey; the evidence is the
    /// offending `transfer_id`. Offenders whose DID does not resolve are skipped
    /// (can't name an accused). Pure over a snapshot — no side effects.
    pub async fn pending_warrants(
        &self,
        signing_key: &ed25519_dalek::SigningKey,
        validator_id: Vec<u8>,
        ts: u64,
    ) -> Vec<kotoba_dht::Warrant> {
        use kotoba_dht::{mutual_credit_warrant, ValidationRule};
        let mut out = Vec::new();
        for f in self.audit_solvency().await {
            if let Some(pk) = resolve_did_pubkey(&f.did) {
                out.push(mutual_credit_warrant(
                    pk.to_vec(),
                    f.transfer_id,
                    ValidationRule::DoubleSpend,
                    validator_id.clone(),
                    ts,
                    signing_key,
                ));
            }
        }
        for fork in self.detect_forks().await {
            if let (Some(pk), Some(evidence)) =
                (resolve_did_pubkey(&fork.spender), fork.transfer_ids.first())
            {
                out.push(mutual_credit_warrant(
                    pk.to_vec(),
                    evidence.clone(),
                    ValidationRule::DoubleSpend,
                    validator_id.clone(),
                    ts,
                    signing_key,
                ));
            }
        }
        out
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
        Self::apply_to_map(&mut g.balances, spender, receiver, amount);
    }

    /// Net-zero move on a bare balance map (used by the in-memory cache and by the
    /// boot-time rebuild-from-log, which has no `Inner` yet).
    fn apply_to_map(
        balances: &mut HashMap<String, i64>,
        spender: &str,
        receiver: &str,
        amount: i64,
    ) {
        let sb = balances.get(spender).copied().unwrap_or(0);
        balances.insert(spender.to_string(), sb.saturating_sub(amount));
        let rb = balances.get(receiver).copied().unwrap_or(0);
        balances.insert(receiver.to_string(), rb.saturating_add(amount));
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

    /// Append one transfer to the durable JSONL log in a single `write_all`
    /// (one line = one record), so a concurrent reader sees whole lines and a
    /// crash can at most leave a torn trailing line (skipped on next load).
    /// Best-effort: failures are logged, never panic the projection.
    fn append_transfer_log(&self, t: &MutualCreditTransfer) {
        let Some(lp) = &self.transfer_log_path else {
            return;
        };
        let mut line = match serde_json::to_string(t) {
            Ok(s) => s,
            Err(e) => {
                tracing::warn!(error = %e, "engi: failed to serialize transfer — not logged");
                return;
            }
        };
        line.push('\n');
        use std::io::Write;
        match std::fs::OpenOptions::new()
            .append(true)
            .create(true)
            .open(lp)
        {
            Ok(mut f) => {
                if let Err(e) = f.write_all(line.as_bytes()) {
                    tracing::warn!(path = ?lp, error = %e, "engi: failed to append transfer log");
                }
            }
            Err(e) => tracing::warn!(path = ?lp, error = %e, "engi: failed to open transfer log"),
        }
    }

    /// Append one fee/settlement move to the durable JSONL fee log (one line per
    /// move, single `write_all`). Best-effort; a `None` path (no persistence
    /// configured) is a no-op so in-memory ledgers are unaffected.
    fn append_fee_log(&self, from: &str, to: &str, amount: i64, kind: &str) {
        let Some(lp) = &self.fee_log_path else {
            return;
        };
        if amount <= 0 || from == to {
            return;
        }
        let mv = EnFeeMove {
            from: from.to_string(),
            to: to.to_string(),
            amount,
            kind: kind.to_string(),
        };
        let mut line = match serde_json::to_string(&mv) {
            Ok(s) => s,
            Err(e) => {
                tracing::warn!(error = %e, "engi: failed to serialize fee move — not logged");
                return;
            }
        };
        line.push('\n');
        use std::io::Write;
        match std::fs::OpenOptions::new()
            .append(true)
            .create(true)
            .open(lp)
        {
            Ok(mut f) => {
                if let Err(e) = f.write_all(line.as_bytes()) {
                    tracing::warn!(path = ?lp, error = %e, "engi: failed to append fee log");
                }
            }
            Err(e) => tracing::warn!(path = ?lp, error = %e, "engi: failed to open fee log"),
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

    #[test]
    fn resolve_did_pubkey_roundtrips_did_key_and_rejects_others() {
        // An AgentIdentity's DID is a did:key over its Ed25519 key — resolution
        // must recover exactly that pubkey (the verify path depends on it).
        let id = kotoba_vault::AgentIdentity::generate_ephemeral();
        assert_eq!(
            resolve_did_pubkey(&id.did),
            Some(id.verifying_key().to_bytes())
        );
        // Non-did:key methods are not resolvable in R2.
        assert!(resolve_did_pubkey("did:plc:abc123").is_none());
        assert!(resolve_did_pubkey("not-a-did").is_none());
    }

    fn engi_persisted(write_cost: i64, op: &str, persist_path: Option<PathBuf>) -> Arc<Engi> {
        // Derive the transfer log path next to the balance file (as `from_env`
        // does) so persistence tests exercise the durable transfer log too, and
        // load from disk on construction (matching `from_env`, not a blank Inner).
        let transfer_log_path = persist_path
            .as_ref()
            .map(|p| p.with_file_name("engi-transfers.jsonl"));
        let fee_log_path = persist_path
            .as_ref()
            .map(|p| p.with_file_name("engi-fees.jsonl"));
        let inner = Engi::load(
            persist_path.as_ref(),
            transfer_log_path.as_ref(),
            fee_log_path.as_ref(),
        );
        Arc::new(Engi {
            write_cost,
            read_cost: 0,
            operator_did: op.to_string(),
            default_credit_limit: 1000,
            inner: RwLock::new(inner),
            persist_path,
            transfer_log_path,
            fee_log_path,
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
            transfer_log_path: None,
            fee_log_path: None,
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

        let reloaded = Engi::load(Some(&pp), None, None);
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

    /// Unique temp dir per test (avoid cross-test file collisions).
    fn tmp_store(tag: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!("kotoba-engi-{tag}-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        dir
    }

    #[tokio::test]
    async fn transfer_log_persists_record_and_balances_across_restart() {
        let dir = tmp_store("xferlog");
        let pp = dir.join("engi-ledger.json");
        {
            let e = engi_persisted(10, "did:key:op", Some(pp.clone()));
            e.project_transfer(&mk_transfer("did:key:a", "did:key:b", 300))
                .await;
            e.project_transfer(&mk_transfer("did:key:b", "did:key:c", 100))
                .await;
            assert_eq!(e.transfer_count().await, 2);
        }
        // A fresh Engi over the same paths reloads the durable record + balances.
        let e2 = engi_persisted(10, "did:key:op", Some(pp.clone()));
        assert_eq!(
            e2.transfer_count().await,
            2,
            "transfer record survives restart"
        );
        assert_eq!(e2.transfers().await.len(), 2);
        assert_eq!(e2.balance("did:key:a").await, -300);
        assert_eq!(e2.balance("did:key:b").await, 200);
        assert_eq!(e2.balance("did:key:c").await, 100);
        assert!(e2.ledger().await.is_balanced());
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[tokio::test]
    async fn balances_rebuild_from_transfer_log_when_cache_is_lost() {
        let dir = tmp_store("rebuild");
        let pp = dir.join("engi-ledger.json");
        {
            let e = engi_persisted(10, "did:key:op", Some(pp.clone()));
            e.project_transfer(&mk_transfer("did:key:a", "did:key:b", 250))
                .await;
        }
        // Lose the fast balance cache but keep the durable transfer log.
        std::fs::remove_file(&pp).unwrap();
        assert!(pp.with_file_name("engi-transfers.jsonl").exists());

        let e2 = engi_persisted(10, "did:key:op", Some(pp.clone()));
        // Balances reconstructed by replaying the durable log.
        assert_eq!(e2.balance("did:key:a").await, -250);
        assert_eq!(e2.balance("did:key:b").await, 250);
        assert!(e2.ledger().await.is_balanced());
        assert_eq!(e2.transfer_count().await, 1);
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[tokio::test]
    async fn torn_transfer_log_line_is_skipped_not_fatal() {
        let dir = tmp_store("torn");
        let pp = dir.join("engi-ledger.json");
        let log = pp.with_file_name("engi-transfers.jsonl");
        {
            let e = engi_persisted(10, "did:key:op", Some(pp.clone()));
            e.project_transfer(&mk_transfer("did:key:a", "did:key:b", 10))
                .await;
        }
        // Simulate a crash mid-append: a torn/garbage trailing line.
        use std::io::Write;
        let mut f = std::fs::OpenOptions::new().append(true).open(&log).unwrap();
        f.write_all(b"{ this is not complete json").unwrap();
        drop(f);
        // Force the rebuild-from-log path so the torn line is parsed.
        std::fs::remove_file(&pp).unwrap();

        let e2 = engi_persisted(10, "did:key:op", Some(pp.clone()));
        // The one good transfer survives; the torn line is skipped.
        assert_eq!(e2.transfer_count().await, 1);
        assert_eq!(e2.balance("did:key:a").await, -10);
        assert!(e2.ledger().await.is_balanced());
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[tokio::test]
    async fn audit_solvency_flags_overspend_in_the_projected_record() {
        // `engi()` uses default_credit_limit = 1000. Two 700-EN spends drive a to
        // -1400, past the limit — the projection applied them unconditionally, so
        // the audit is what catches it.
        let e = engi(10, "did:key:op");
        e.project_transfer(&mk_transfer("did:key:a", "did:key:b", 700))
            .await;
        e.project_transfer(&mk_transfer("did:key:a", "did:key:b", 700))
            .await;
        let findings = e.audit_solvency().await;
        assert_eq!(findings.len(), 1);
        assert_eq!(findings[0].did, "did:key:a");
        assert_eq!(findings[0].balance_after, -1400);
        assert_eq!(findings[0].credit_limit, 1000);

        // A within-limit record audits clean.
        let e2 = engi(10, "did:key:op");
        e2.project_transfer(&mk_transfer("did:key:a", "did:key:b", 500))
            .await;
        assert!(e2.audit_solvency().await.is_empty());
    }

    #[tokio::test]
    async fn detect_forks_catches_double_spend_in_projected_record() {
        // a projects two DISTINCT transfers both from the genesis position
        // (mk_transfer pins prev = None) → a double-spend fork.
        let e = engi(10, "did:key:op");
        e.project_transfer(&mk_transfer("did:key:a", "did:key:b", 100))
            .await;
        e.project_transfer(&mk_transfer("did:key:a", "did:key:c", 100))
            .await;
        let forks = e.detect_forks().await;
        assert_eq!(forks.len(), 1);
        assert_eq!(forks[0].spender, "did:key:a");
        assert_eq!(forks[0].transfer_ids.len(), 2);

        // A single spender→one-receiver record (even repeated identical gossip)
        // is not a fork.
        let e2 = engi(10, "did:key:op");
        let t = mk_transfer("did:key:a", "did:key:b", 100);
        e2.project_transfer(&t).await;
        e2.project_transfer(&t).await; // identical id → deduped, no fork
        assert!(e2.detect_forks().await.is_empty());
    }

    #[tokio::test]
    async fn pending_warrants_signs_a_verifiable_warrant_for_a_fork() {
        use ed25519_dalek::{Signature, Verifier};
        let a = kotoba_vault::AgentIdentity::generate_ephemeral();
        let b = kotoba_vault::AgentIdentity::generate_ephemeral();
        let c = kotoba_vault::AgentIdentity::generate_ephemeral();
        let validator = kotoba_vault::AgentIdentity::generate_ephemeral();
        let e = engi(10, "did:key:op");

        // `a` (a real did:key) double-spends from genesis: two distinct transfers
        // both pinning prev = None → a fork.
        e.project_transfer(&mk_transfer(&a.did, &b.did, 100)).await;
        e.project_transfer(&mk_transfer(&a.did, &c.did, 100)).await;
        assert_eq!(e.detect_forks().await.len(), 1);

        let validator_id = validator.verifying_key().to_bytes().to_vec();
        let warrants = e
            .pending_warrants(&validator.signing_key, validator_id.clone(), 42)
            .await;
        assert_eq!(warrants.len(), 1, "one warrant for the fork");
        let w = &warrants[0];
        assert_eq!(w.rule_id, kotoba_dht::ValidationRule::DoubleSpend as u8);
        // accused = a's pubkey, resolved from its did:key.
        assert_eq!(w.accused, a.verifying_key().to_bytes().to_vec());
        assert_eq!(w.validator, validator_id);
        // The signature verifies under the validator's key.
        let sig: [u8; 64] = w.sig.as_slice().try_into().unwrap();
        assert!(validator
            .verifying_key()
            .verify(
                &kotoba_dht::warrant_signing_bytes(w),
                &Signature::from_bytes(&sig)
            )
            .is_ok());

        // A clean record (no violation) emits no warrants.
        let e2 = engi(10, "did:key:op");
        e2.project_transfer(&mk_transfer(&a.did, &b.did, 100)).await;
        assert!(e2
            .pending_warrants(&validator.signing_key, validator_id, 0)
            .await
            .is_empty());
    }

    #[tokio::test]
    async fn fee_balances_rebuild_from_fee_log_when_cache_is_lost() {
        let dir = tmp_store("feelog");
        let pp = dir.join("engi-ledger.json");
        {
            let e = engi_persisted(10, "did:key:op", Some(pp.clone()));
            e.charge("did:key:ext", 120).await.unwrap(); // ext -120, op +120
            e.batch_credit(&[("did:key:r".into(), 40)]).await; // r +40, op -40
            assert_eq!(e.balance("did:key:ext").await, -120);
            assert_eq!(e.balance("did:key:r").await, 40);
            assert_eq!(e.balance("did:key:op").await, 80);
        }
        // Lose the fast balance cache but keep the durable fee log.
        std::fs::remove_file(&pp).unwrap();
        assert!(pp.with_file_name("engi-fees.jsonl").exists());

        let e2 = engi_persisted(10, "did:key:op", Some(pp.clone()));
        // Fee + settlement balances recovered from the durable fee log.
        assert_eq!(e2.balance("did:key:ext").await, -120);
        assert_eq!(e2.balance("did:key:r").await, 40);
        assert_eq!(e2.balance("did:key:op").await, 80);
        assert!(e2.ledger().await.is_balanced());
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[tokio::test]
    async fn cache_loss_recovers_both_transfers_and_fees() {
        let dir = tmp_store("bothlogs");
        let pp = dir.join("engi-ledger.json");
        {
            let e = engi_persisted(10, "did:key:op", Some(pp.clone()));
            e.project_transfer(&mk_transfer("did:key:a", "did:key:b", 300))
                .await; // a -300, b +300
            e.charge("did:key:a", 50).await.unwrap(); // a -50 (fee), op +50
        }
        std::fs::remove_file(&pp).unwrap();

        let e2 = engi_persisted(10, "did:key:op", Some(pp.clone()));
        // Transfer-derived AND fee-derived balances both recovered.
        assert_eq!(e2.balance("did:key:a").await, -350);
        assert_eq!(e2.balance("did:key:b").await, 300);
        assert_eq!(e2.balance("did:key:op").await, 50);
        assert!(e2.ledger().await.is_balanced());
        // The countersigned transfer is still in the transfer record (auditable).
        assert_eq!(e2.transfer_count().await, 1);
        let _ = std::fs::remove_dir_all(&dir);
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

        let inner = Engi::load(Some(&pp), None, None);
        assert!(inner.balances.is_empty());
        assert!(
            pp.with_extension("json.corrupt").exists(),
            "corrupt file must be preserved as .corrupt, not silently dropped"
        );

        let _ = std::fs::remove_dir_all(&dir);
    }
}
