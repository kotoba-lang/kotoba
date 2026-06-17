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

use crate::dna::DnaManifest;
use kotoba_core::cid::KotobaCid;
use kotoba_query::datom::Datom;
use serde::{Deserialize, Serialize};
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

// ── Content-addressed rule specs (bridge manifest → engine) ───────────────────

/// The serializable form of a built-in rule — the content a DNA's
/// [`crate::dna::ValidationRuleRef`] points at (CBOR, content-addressed). New
/// rule kinds (EDN Datalog, WASM validators) become additional variants.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum RuleSpec {
    AllowedAttributes { id: String, allowed: Vec<String> },
    ForbiddenAttribute { id: String, attr: String },
    MaxTxSize { id: String, max: usize },
}

impl RuleSpec {
    /// Canonical CBOR — the bytes a `ValidationRuleRef.content` CID addresses.
    pub fn to_cbor(&self) -> Vec<u8> {
        let mut buf = Vec::new();
        ciborium::into_writer(self, &mut buf).expect("rulespec cbor");
        buf
    }

    /// Content address of this rule spec (what the DNA references it by).
    pub fn content_cid(&self) -> KotobaCid {
        KotobaCid::from_bytes(&self.to_cbor())
    }

    /// Interpret into a runnable [`PhysicsRule`].
    pub fn into_rule(self) -> Box<dyn PhysicsRule> {
        match self {
            RuleSpec::AllowedAttributes { id, allowed } => Box::new(AllowedAttributes {
                id,
                allowed: allowed.into_iter().collect(),
            }),
            RuleSpec::ForbiddenAttribute { id, attr } => Box::new(ForbiddenAttribute { id, attr }),
            RuleSpec::MaxTxSize { id, max } => Box::new(MaxTxSize { id, max }),
        }
    }
}

/// Load a DNA's rules into runnable [`PhysicsRule`]s by resolving each
/// [`crate::dna::ValidationRuleRef`]'s content CID via `fetch` (e.g. a block
/// store) and decoding it as a [`RuleSpec`]. Rules come out in the manifest's
/// canonical order (so `validate_tx`'s failing-rule report is stable).
///
/// Integrity-checked: a fetched blob whose recomputed CID ≠ the referenced CID is
/// rejected (content-addressing means the DNA pins exact rule bytes). Missing or
/// undecodable content is an error — a DNA you can't fully load you must not
/// enforce partially.
pub fn load_rules<F>(dna: &DnaManifest, fetch: F) -> Result<Vec<Box<dyn PhysicsRule>>, String>
where
    F: Fn(&KotobaCid) -> Option<Vec<u8>>,
{
    let mut rules = Vec::with_capacity(dna.rules().len());
    for r in dna.rules() {
        let bytes = fetch(&r.content)
            .ok_or_else(|| format!("rule `{}`: content {} not found", r.id, r.content.to_multibase()))?;
        if KotobaCid::from_bytes(&bytes) != r.content {
            return Err(format!("rule `{}`: content CID mismatch (tampered blob)", r.id));
        }
        let spec: RuleSpec = ciborium::from_reader(bytes.as_slice())
            .map_err(|e| format!("rule `{}`: undecodable RuleSpec: {e}", r.id))?;
        rules.push(spec.into_rule());
    }
    Ok(rules)
}

#[cfg(test)]
mod tests {
    use super::*;
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

    // ── RuleSpec + load_rules (manifest → engine bridge) ──────────────────

    #[test]
    fn rulespec_content_cid_is_deterministic_and_interprets() {
        let spec = RuleSpec::MaxTxSize { id: "size".into(), max: 5 };
        assert_eq!(spec.content_cid(), spec.content_cid());
        assert_eq!(spec.content_cid(), KotobaCid::from_bytes(&spec.to_cbor()));
        let rule = spec.into_rule();
        assert_eq!(rule.id(), "size");
        assert!(rule.check(&[assert_d("a")]).is_ok());
    }

    #[test]
    fn load_rules_resolves_a_dna_end_to_end() {
        // Build specs, address them, assemble a DNA referencing those CIDs.
        let schema = RuleSpec::AllowedAttributes {
            id: "schema".into(),
            allowed: vec!["name".into(), "role".into()],
        };
        let size = RuleSpec::MaxTxSize { id: "size".into(), max: 3 };
        let dna = DnaManifest::new("market", "1.0.0")
            .with_rule("schema", schema.content_cid())
            .with_rule("size", size.content_cid());
        // in-memory content store: CID → CBOR.
        let store: std::collections::HashMap<KotobaCid, Vec<u8>> = [
            (schema.content_cid(), schema.to_cbor()),
            (size.content_cid(), size.to_cbor()),
        ]
        .into_iter()
        .collect();

        let rules = load_rules(&dna, |c| store.get(c).cloned()).expect("load");
        assert_eq!(rules.len(), 2);
        // the loaded rules actually enforce the DNA's physics.
        assert!(validate_tx(&rules, &[assert_d("name"), assert_d("role")]).is_valid());
        assert!(!validate_tx(&rules, &[assert_d("evil")]).is_valid()); // schema
        let big: Vec<Datom> = (0..4).map(|_| assert_d("name")).collect();
        assert!(!validate_tx(&rules, &big).is_valid()); // size
    }

    #[test]
    fn load_rules_errors_on_missing_content() {
        let spec = RuleSpec::MaxTxSize { id: "size".into(), max: 1 };
        let dna = DnaManifest::new("d", "1").with_rule("size", spec.content_cid());
        let Err(err) = load_rules(&dna, |_| None) else {
            panic!("expected missing-content error");
        };
        assert!(err.contains("not found"), "got: {err}");
    }

    #[test]
    fn load_rules_rejects_tampered_content() {
        let spec = RuleSpec::MaxTxSize { id: "size".into(), max: 1 };
        let dna = DnaManifest::new("d", "1").with_rule("size", spec.content_cid());
        // serve different bytes than the referenced CID addresses → integrity fail.
        let tampered = RuleSpec::MaxTxSize { id: "size".into(), max: 999 }.to_cbor();
        let Err(err) = load_rules(&dna, |_| Some(tampered.clone())) else {
            panic!("expected integrity error");
        };
        assert!(err.contains("mismatch"), "got: {err}");
    }
}
