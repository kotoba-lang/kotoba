//! # Validation hook — enforcing a DNA's shared physics (ADR-001 phase 3 / GROWTH p9)
//!
//! The enforcement side of [`crate::dna`]: a proposed transaction is checked
//! against the DNA's [`ValidationRule`]s before it commits (and on merge results).
//! Validation is **pure and deterministic** — the same transaction under the same
//! rules yields the same verdict on every replica, which is what lets a
//! merge-on-conflict Merkle-CRDT converge without coordination (ADR-001).
//!
//! This is the engine + a set of schema-style built-in rules. Loading rules from
//! their content CIDs (EDN Datalog blobs / WASM validators referenced by
//! [`crate::dna::ValidationRuleRef`]) is the next layer; these built-ins are the
//! interpreter targets and are useful on their own.

use kotoba_query::datom::Datom;
use std::collections::HashSet;

/// The verdict of validating a proposed transaction.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ValidationOutcome {
    Valid,
    /// Rejected by `rule_id` with a human-readable `reason`.
    Rejected { rule_id: String, reason: String },
}

impl ValidationOutcome {
    pub fn is_valid(&self) -> bool {
        matches!(self, ValidationOutcome::Valid)
    }
}

/// One shared-physics rule. `check` returns `Err(reason)` to reject the
/// transaction; `Ok(())` to accept. Must be a pure function of `tx` so all
/// replicas agree.
pub trait PhysicsRule: Send + Sync {
    fn id(&self) -> &str;
    fn check(&self, tx: &[Datom]) -> Result<(), String>;
}

/// Run a DNA's rules over a proposed transaction, short-circuiting on the first
/// rejection (rules run in their given order, so order the DNA's rules
/// deterministically for a stable failing-rule report). `Valid` iff every rule
/// accepts.
pub fn validate_tx(rules: &[Box<dyn PhysicsRule>], tx: &[Datom]) -> ValidationOutcome {
    for rule in rules {
        if let Err(reason) = rule.check(tx) {
            return ValidationOutcome::Rejected {
                rule_id: rule.id().to_string(),
                reason,
            };
        }
    }
    ValidationOutcome::Valid
}

// ── Built-in rules (schema-style shared physics) ──────────────────────────────

/// Reject the transaction unless every asserted attribute is in `allowed` — a
/// closed schema. Retractions are ignored (you can always retract).
pub struct AllowedAttributes {
    pub id: String,
    pub allowed: HashSet<String>,
}

impl PhysicsRule for AllowedAttributes {
    fn id(&self) -> &str {
        &self.id
    }
    fn check(&self, tx: &[Datom]) -> Result<(), String> {
        for d in tx {
            if d.op && !self.allowed.contains(&d.a) {
                return Err(format!("attribute `{}` is not in the DNA schema", d.a));
            }
        }
        Ok(())
    }
}

/// Reject the transaction if any datom touches `attr` — a write-protected /
/// system attribute this DNA forbids members from setting.
pub struct ForbiddenAttribute {
    pub id: String,
    pub attr: String,
}

impl PhysicsRule for ForbiddenAttribute {
    fn id(&self) -> &str {
        &self.id
    }
    fn check(&self, tx: &[Datom]) -> Result<(), String> {
        if tx.iter().any(|d| d.a == self.attr) {
            return Err(format!("attribute `{}` is write-protected", self.attr));
        }
        Ok(())
    }
}

/// Reject transactions larger than `max` datoms — anti-spam physics.
pub struct MaxTxSize {
    pub id: String,
    pub max: usize,
}

impl PhysicsRule for MaxTxSize {
    fn id(&self) -> &str {
        &self.id
    }
    fn check(&self, tx: &[Datom]) -> Result<(), String> {
        if tx.len() > self.max {
            return Err(format!("transaction has {} datoms, max is {}", tx.len(), self.max));
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use kotoba_core::cid::KotobaCid;
    use kotoba_query::datom::{Datom, Value};

    fn cid(s: &str) -> KotobaCid {
        KotobaCid::from_bytes(s.as_bytes())
    }

    fn assert_d(attr: &str) -> Datom {
        Datom::assert(cid("e"), attr.into(), Value::Bool(true), cid("g"))
    }

    fn retract_d(attr: &str) -> Datom {
        let mut d = assert_d(attr);
        d.op = false;
        d
    }

    fn rules(v: Vec<Box<dyn PhysicsRule>>) -> Vec<Box<dyn PhysicsRule>> {
        v
    }

    #[test]
    fn empty_ruleset_accepts_everything() {
        assert!(validate_tx(&[], &[assert_d("anything")]).is_valid());
    }

    #[test]
    fn allowed_attributes_is_a_closed_schema() {
        let r = rules(vec![Box::new(AllowedAttributes {
            id: "schema".into(),
            allowed: ["name", "role"].iter().map(|s| s.to_string()).collect(),
        })]);
        assert!(validate_tx(&r, &[assert_d("name"), assert_d("role")]).is_valid());
        match validate_tx(&r, &[assert_d("name"), assert_d("evil")]) {
            ValidationOutcome::Rejected { rule_id, reason } => {
                assert_eq!(rule_id, "schema");
                assert!(reason.contains("evil"));
            }
            ValidationOutcome::Valid => panic!("expected rejection"),
        }
        // retractions bypass the closed schema (you can always retract).
        assert!(validate_tx(&r, &[retract_d("evil")]).is_valid());
    }

    #[test]
    fn forbidden_attribute_blocks_writes_and_retracts() {
        let r = rules(vec![Box::new(ForbiddenAttribute {
            id: "no-system".into(),
            attr: "system/root".into(),
        })]);
        assert!(validate_tx(&r, &[assert_d("name")]).is_valid());
        assert!(!validate_tx(&r, &[assert_d("system/root")]).is_valid());
        // forbidden means truly untouchable — even a retraction is rejected.
        assert!(!validate_tx(&r, &[retract_d("system/root")]).is_valid());
    }

    #[test]
    fn max_tx_size_caps_transaction() {
        let r = rules(vec![Box::new(MaxTxSize { id: "size".into(), max: 2 })]);
        assert!(validate_tx(&r, &[assert_d("a"), assert_d("b")]).is_valid());
        assert!(!validate_tx(&r, &[assert_d("a"), assert_d("b"), assert_d("c")]).is_valid());
    }

    #[test]
    fn first_failing_rule_is_reported_deterministically() {
        // size runs first and fails; schema would also fail but size short-circuits.
        let r = rules(vec![
            Box::new(MaxTxSize { id: "size".into(), max: 0 }),
            Box::new(AllowedAttributes {
                id: "schema".into(),
                allowed: HashSet::new(),
            }),
        ]);
        match validate_tx(&r, &[assert_d("x")]) {
            ValidationOutcome::Rejected { rule_id, .. } => assert_eq!(rule_id, "size"),
            ValidationOutcome::Valid => panic!("expected rejection"),
        }
    }
}
