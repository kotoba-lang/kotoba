//! Write-cost economy — datomic writes cost mKOTO (ADR-2606013400).
//!
//! Every `datomic.transact` debits the writing DID's mKOTO balance by
//! `cost_per_datom × datom_count`; an insufficient balance rejects the write
//! with HTTP 402. This turns the soft-auth write surface into an economically
//! gated one: an external writer must hold (be credited) mKOTO to write, so
//! spam is costly. The node operator (the owner DID) is the mint and is
//! exempt/unlimited so the node's own substrate writes never block.
//!
//! Units: 1 KOTO = 1_000_000_000 mKOTO (matches `attestation.rs`).
//!
//! Env:
//!   KOTOBA_WRITE_COST_MKOTO_PER_DATOM   cost per datom (default 10; 0 = off)
//!   KOTOBA_STORE_PATH                   dir for `econ-balances.json` persistence
//!
//! Persistence: non-operator balances are written to
//! `${KOTOBA_STORE_PATH}/econ-balances.json` on each change and reloaded at
//! boot, so credited balances survive restarts. The operator's unlimited
//! balance is re-seeded at boot (never persisted).

use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::Arc;
use tokio::sync::RwLock;

/// Recommended production per-datom write cost in mKOTO (10 mKOTO/datom,
/// matching the `assert = 10` gas unit). Set
/// `KOTOBA_WRITE_COST_MKOTO_PER_DATOM` to this (or any value) to enable the
/// economy. The env **defaults to `0` (disabled)** when unset so unit/e2e tests
/// and existing CACAO writers are unaffected unless cost is explicitly turned on.
pub const RECOMMENDED_COST_PER_DATOM_MKOTO: i64 = 10;

pub struct Econ {
    cost_per_datom: i64,
    operator_did: String,
    balances: RwLock<HashMap<String, i64>>,
    persist_path: Option<PathBuf>,
}

impl Econ {
    /// Construct from env. The operator DID is seeded with an unlimited balance
    /// (node owner = mint); persisted non-operator balances are reloaded.
    pub fn from_env(operator_did: String) -> Arc<Self> {
        // Default 0 (disabled) when unset — opt-in via env so tests / existing
        // CACAO writers are unaffected until the operator turns cost on
        // (RECOMMENDED_COST_PER_DATOM_MKOTO is the suggested production value).
        let cost_per_datom = std::env::var("KOTOBA_WRITE_COST_MKOTO_PER_DATOM")
            .ok()
            .and_then(|v| v.trim().parse::<i64>().ok())
            .unwrap_or(0)
            .max(0);

        let persist_path = std::env::var("KOTOBA_STORE_PATH")
            .ok()
            .map(|p| PathBuf::from(p).join("econ-balances.json"));

        let mut balances: HashMap<String, i64> = persist_path
            .as_ref()
            .and_then(|pp| std::fs::read_to_string(pp).ok())
            .and_then(|s| serde_json::from_str(&s).ok())
            .unwrap_or_default();

        // Operator genesis — unlimited; never debited, never persisted.
        balances.insert(operator_did.clone(), i64::MAX);

        Arc::new(Self {
            cost_per_datom,
            operator_did,
            balances: RwLock::new(balances),
            persist_path,
        })
    }

    pub fn enabled(&self) -> bool {
        self.cost_per_datom > 0
    }

    pub fn cost_per_datom(&self) -> i64 {
        self.cost_per_datom
    }

    /// Cost in mKOTO for a transaction asserting/retracting `datom_count` datoms.
    pub fn cost_for(&self, datom_count: usize) -> i64 {
        self.cost_per_datom.saturating_mul(datom_count as i64)
    }

    pub async fn balance(&self, did: &str) -> i64 {
        *self.balances.read().await.get(did).unwrap_or(&0)
    }

    /// Charge `did` `cost` mKOTO for a write. The operator is exempt (unlimited).
    /// Returns `Ok(remaining)` or `Err((needed, current_balance))`.
    pub async fn charge(&self, did: &str, cost: i64) -> Result<i64, (i64, i64)> {
        if did == self.operator_did {
            return Ok(i64::MAX);
        }
        if cost <= 0 {
            return Ok(self.balance(did).await);
        }
        let mut b = self.balances.write().await;
        let bal = *b.get(did).unwrap_or(&0);
        if bal < cost {
            return Err((cost, bal));
        }
        let remaining = bal - cost;
        b.insert(did.to_string(), remaining);
        let snapshot = Self::snapshot(&b, &self.operator_did);
        drop(b);
        self.persist(snapshot);
        Ok(remaining)
    }

    /// Refund a previously charged amount (used if a commit fails after charge).
    pub async fn refund(&self, did: &str, amount: i64) {
        if did == self.operator_did || amount <= 0 {
            return;
        }
        let mut b = self.balances.write().await;
        let bal = b.get(did).copied().unwrap_or(0).saturating_add(amount);
        b.insert(did.to_string(), bal);
        let snapshot = Self::snapshot(&b, &self.operator_did);
        drop(b);
        self.persist(snapshot);
    }

    /// Operator-mint: credit (or debit, if negative) a DID's balance. Returns
    /// the new balance. Callers must enforce operator auth before calling.
    pub async fn credit(&self, did: &str, amount: i64) -> i64 {
        let mut b = self.balances.write().await;
        let bal = b.get(did).copied().unwrap_or(0).saturating_add(amount).max(0);
        b.insert(did.to_string(), bal);
        let snapshot = Self::snapshot(&b, &self.operator_did);
        drop(b);
        self.persist(snapshot);
        bal
    }

    fn snapshot(b: &HashMap<String, i64>, operator_did: &str) -> HashMap<String, i64> {
        b.iter()
            .filter(|(k, _)| k.as_str() != operator_did)
            .map(|(k, v)| (k.clone(), *v))
            .collect()
    }

    fn persist(&self, snapshot: HashMap<String, i64>) {
        if let Some(pp) = &self.persist_path {
            if let Ok(s) = serde_json::to_string(&snapshot) {
                let _ = std::fs::write(pp, s);
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn econ(cost: i64, op: &str) -> Arc<Econ> {
        // Bypass env by constructing directly (from_env reads env).
        Arc::new(Econ {
            cost_per_datom: cost,
            operator_did: op.to_string(),
            balances: RwLock::new({
                let mut m = HashMap::new();
                m.insert(op.to_string(), i64::MAX);
                m
            }),
            persist_path: None,
        })
    }

    #[tokio::test]
    async fn operator_is_exempt_and_unlimited() {
        let e = econ(10, "did:key:op");
        // 1M datoms — operator never blocked, balance stays MAX.
        assert!(e.charge("did:key:op", e.cost_for(1_000_000)).await.is_ok());
        assert_eq!(e.balance("did:key:op").await, i64::MAX);
    }

    #[tokio::test]
    async fn external_writer_needs_credit_and_is_debited() {
        let e = econ(10, "did:key:op");
        // Unfunded external writer cannot write.
        assert_eq!(e.charge("did:key:ext", 30).await, Err((30, 0)));
        // Credit then write.
        assert_eq!(e.credit("did:key:ext", 100).await, 100);
        assert_eq!(e.charge("did:key:ext", 30).await, Ok(70));
        // Overdraw rejected; balance unchanged.
        assert_eq!(e.charge("did:key:ext", 1000).await, Err((1000, 70)));
        assert_eq!(e.balance("did:key:ext").await, 70);
    }

    #[tokio::test]
    async fn cost_scales_with_datom_count() {
        let e = econ(10, "did:key:op");
        assert_eq!(e.cost_for(0), 0);
        assert_eq!(e.cost_for(5), 50);
    }

    #[tokio::test]
    async fn disabled_when_cost_zero() {
        let e = econ(0, "did:key:op");
        assert!(!e.enabled());
        // cost 0 → charge always succeeds even for unfunded writers.
        assert!(e.charge("did:key:ext", e.cost_for(99)).await.is_ok());
    }

    #[tokio::test]
    async fn refund_restores_balance_after_charge() {
        // The commit-failed-after-charge path: a charge followed by an equal refund
        // must leave the member exactly where they started — no mKOTO lost or minted.
        let e = econ(10, "did:key:op");
        assert_eq!(e.credit("did:key:ext", 100).await, 100);
        assert_eq!(e.charge("did:key:ext", 30).await, Ok(70));
        e.refund("did:key:ext", 30).await;
        assert_eq!(
            e.balance("did:key:ext").await,
            100,
            "charge + equal refund must restore the original balance"
        );
    }

    #[tokio::test]
    async fn refund_operator_and_nonpositive_are_noops() {
        let e = econ(10, "did:key:op");
        // Operator balance is sentinel-unlimited; refund must not perturb it.
        e.refund("did:key:op", 50).await;
        assert_eq!(e.balance("did:key:op").await, i64::MAX);
        // Zero / negative refunds are no-ops (cannot be used to mint).
        e.credit("did:key:ext", 40).await;
        e.refund("did:key:ext", 0).await;
        e.refund("did:key:ext", -100).await;
        assert_eq!(e.balance("did:key:ext").await, 40);
    }

    #[tokio::test]
    async fn credit_negative_debit_floors_at_zero() {
        // Operator-mint can debit (negative amount), but a balance must never go
        // negative — the `.max(0)` floor protects the accounting invariant.
        let e = econ(10, "did:key:op");
        assert_eq!(e.credit("did:key:ext", 30).await, 30);
        assert_eq!(
            e.credit("did:key:ext", -50).await,
            0,
            "debiting below zero must floor at 0, not go negative"
        );
        // Already-zero balance stays at zero under further debit.
        assert_eq!(e.credit("did:key:ext", -10).await, 0);
    }
}
