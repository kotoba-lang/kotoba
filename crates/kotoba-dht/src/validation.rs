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

/// Enforce a DNA over a proposed transaction in one call — the single entry
/// point the transact (and merge-result) path invokes. Loads the DNA's rules via
/// `fetch`, then validates `tx`. A DNA that fails to load is itself a rejection:
/// you must never enforce a DNA you cannot fully assemble (partial physics is no
/// physics). Pure + deterministic, so every replica reaches the same verdict.
pub fn enforce<F>(dna: &DnaManifest, fetch: F, tx: &[Datom]) -> ValidationOutcome
where
    F: Fn(&KotobaCid) -> Option<Vec<u8>>,
{
    match load_rules(dna, fetch) {
        Ok(rules) => validate_tx(&rules, tx),
        Err(reason) => ValidationOutcome::Rejected {
            rule_id: "<dna-load>".to_string(),
            reason,
        },
    }
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
    fn rulespec_wire_format_is_stable_across_all_variants() {
        // RuleSpec blobs are content-addressed and fetched/decoded by load_rules,
        // so their CBOR is a wire contract: every variant must CBOR round-trip to
        // an equal value, content_cid must be deterministic, and into_rule must
        // preserve the id + accept/reject semantics.
        let specs = vec![
            RuleSpec::AllowedAttributes { id: "schema".into(), allowed: vec!["name".into()] },
            RuleSpec::ForbiddenAttribute { id: "noroot".into(), attr: "system/root".into() },
            RuleSpec::MaxTxSize { id: "size".into(), max: 2 },
        ];
        for spec in specs {
            // CBOR round-trips to an equal RuleSpec.
            let back: RuleSpec = ciborium::from_reader(spec.to_cbor().as_slice()).unwrap();
            assert_eq!(back, spec, "RuleSpec wire round-trip changed the value");
            // content id is deterministic and = hash of the canonical CBOR.
            assert_eq!(spec.content_cid(), back.content_cid());
            assert_eq!(spec.content_cid(), KotobaCid::from_bytes(&spec.to_cbor()));
            // into_rule preserves the id.
            let id = match &spec {
                RuleSpec::AllowedAttributes { id, .. }
                | RuleSpec::ForbiddenAttribute { id, .. }
                | RuleSpec::MaxTxSize { id, .. } => id.clone(),
            };
            assert_eq!(spec.into_rule().id(), id);
        }
        // a decoded spec enforces identically to the original (semantics preserved).
        let orig = RuleSpec::ForbiddenAttribute { id: "f".into(), attr: "x".into() };
        let decoded: RuleSpec =
            ciborium::from_reader(orig.clone().to_cbor().as_slice()).unwrap();
        let ro: Vec<Box<dyn PhysicsRule>> = vec![orig.into_rule()];
        let rd: Vec<Box<dyn PhysicsRule>> = vec![decoded.into_rule()];
        for tx in [vec![assert_d("x")], vec![assert_d("ok")], vec![retract_d("x")]] {
            assert_eq!(
                validate_tx(&ro, &tx).is_valid(),
                validate_tx(&rd, &tx).is_valid(),
                "decoded rule enforces differently"
            );
        }
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

    #[test]
    fn load_rules_is_tamper_evident_under_any_byte_mutation() {
        // Shared physics must be unforgeable: ANY single-byte change to a rule
        // blob the DNA references is caught by content-address verification — no
        // mutation yields a loadable-but-different ruleset. Sweep every byte.
        let spec = RuleSpec::AllowedAttributes {
            id: "schema".into(),
            allowed: vec!["name".into(), "role".into()],
        };
        let dna = DnaManifest::new("d", "1").with_rule("schema", spec.content_cid());
        let good = spec.to_cbor();

        // the untouched blob loads.
        assert!(load_rules(&dna, |_| Some(good.clone())).is_ok());

        // flipping the low bit of any byte must make load_rules reject.
        for i in 0..good.len() {
            let mut bad = good.clone();
            bad[i] ^= 0x01;
            if bad == good {
                continue;
            }
            let res = load_rules(&dna, |_| Some(bad.clone()));
            assert!(
                res.is_err(),
                "byte {i} mutation slipped past content-address verification"
            );
        }
    }

    #[test]
    fn closed_schema_never_admits_an_out_of_schema_assert() {
        // Safety completeness: whatever the tx mixes in — allowed asserts,
        // retracts of anything, repeats — a closed-schema rule MUST reject the
        // moment any asserted attribute is outside the schema, and accept only
        // when every asserted attribute is allowed. Adversarial sweep.
        let allowed: std::collections::HashSet<String> =
            ["name", "role"].iter().map(|s| s.to_string()).collect();
        let rule: Vec<Box<dyn PhysicsRule>> = vec![Box::new(AllowedAttributes {
            id: "schema".into(),
            allowed: allowed.clone(),
        })];
        let universe = ["name", "role", "evil", "system/x"];
        // every subset (as a bitmask) of asserts, plus a retract of "evil".
        for mask in 0u32..(1 << universe.len()) {
            let mut tx = vec![retract_d("evil")]; // a retract must never cause rejection
            let mut has_forbidden_assert = false;
            for (i, a) in universe.iter().enumerate() {
                if mask & (1 << i) != 0 {
                    tx.push(assert_d(a));
                    if !allowed.contains(*a) {
                        has_forbidden_assert = true;
                    }
                }
            }
            let valid = validate_tx(&rule, &tx).is_valid();
            assert_eq!(
                valid, !has_forbidden_assert,
                "closed-schema verdict wrong for mask {mask:#b}"
            );
        }
    }

    #[test]
    fn enforce_loads_then_validates_in_one_call() {
        let schema = RuleSpec::AllowedAttributes {
            id: "schema".into(),
            allowed: vec!["name".into()],
        };
        let dna = DnaManifest::new("d", "1").with_rule("schema", schema.content_cid());
        let store: std::collections::HashMap<KotobaCid, Vec<u8>> =
            [(schema.content_cid(), schema.to_cbor())].into_iter().collect();
        let fetch = |c: &KotobaCid| store.get(c).cloned();

        assert!(enforce(&dna, fetch, &[assert_d("name")]).is_valid());
        assert!(!enforce(&dna, fetch, &[assert_d("evil")]).is_valid());
    }

    #[test]
    fn enforce_rejects_when_dna_cannot_load() {
        let spec = RuleSpec::MaxTxSize { id: "size".into(), max: 1 };
        let dna = DnaManifest::new("d", "1").with_rule("size", spec.content_cid());
        // content missing → enforce rejects (not silently accepts).
        match enforce(&dna, |_| None, &[assert_d("x")]) {
            ValidationOutcome::Rejected { rule_id, .. } => assert_eq!(rule_id, "<dna-load>"),
            ValidationOutcome::Valid => panic!("must not enforce a DNA it can't load"),
        }
    }
}
