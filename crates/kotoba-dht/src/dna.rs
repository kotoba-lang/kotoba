//! # DNA manifest — packaged, content-addressed "shared physics" (GROWTH p9)
//!
//! A graph's validation rules — its `:db.validate/*` rules and optional WASM
//! validators (ADR-001 phase 3, the "shared physics") — are packaged into a
//! versioned [`DnaManifest`] whose content hash is its identity, exactly like a
//! Holochain DNA hash. Two nodes that agree on a DNA id are running byte-identical
//! validation: that is what makes them the same network. Third parties can pin,
//! distribute, and pin-contract a DNA by its [`dna_id`](DnaManifest::dna_id).
//!
//! The id is order-independent: the same rule *set* yields the same id regardless
//! of insertion order (rules are canonicalised — sorted + deduped by `id` — before
//! hashing). Packaging is independent of enforcement: this names and addresses the
//! rules; wiring them into the transact path is the validation-hook work.

use kotoba_core::cid::KotobaCid;
use serde::{Deserialize, Serialize};

/// A reference to one validation rule in a DNA: a stable `id` (e.g. the
/// `:db.validate/*` attribute it guards) and the CID of its content (an EDN
/// Datalog rule blob, or a WASM validator component).
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ValidationRuleRef {
    pub id: String,
    pub content: KotobaCid,
}

/// A versioned, content-addressed package of a graph's validation rules — the
/// "shared physics" every replica enforces.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct DnaManifest {
    pub name: String,
    pub version: String,
    /// Rules, kept canonical (sorted + deduped by `id`) so the id is stable.
    rules: Vec<ValidationRuleRef>,
}

impl DnaManifest {
    /// An empty DNA (no rules) — a starting point for `with_rule`.
    pub fn new(name: impl Into<String>, version: impl Into<String>) -> Self {
        Self {
            name: name.into(),
            version: version.into(),
            rules: Vec::new(),
        }
    }

    /// Add (or replace, by `id`) a rule, keeping the rule set canonical. Chainable.
    pub fn with_rule(mut self, id: impl Into<String>, content: KotobaCid) -> Self {
        let id = id.into();
        self.rules.retain(|r| r.id != id);
        self.rules.push(ValidationRuleRef { id, content });
        self.rules.sort_by(|a, b| a.id.cmp(&b.id));
        self
    }

    /// The rules, in canonical (sorted, deduped) order.
    pub fn rules(&self) -> &[ValidationRuleRef] {
        &self.rules
    }

    /// Canonical CBOR encoding (rules already canonical) — the bytes that are
    /// content-addressed into the DNA id.
    pub fn to_cbor(&self) -> Vec<u8> {
        let mut buf = Vec::new();
        ciborium::into_writer(self, &mut buf).expect("dna cbor");
        buf
    }

    /// The DNA id: CIDv1 dag-cbor sha2-256 over the canonical CBOR. Stable across
    /// insertion order; changes iff name, version, or the rule set changes.
    pub fn dna_id(&self) -> KotobaCid {
        KotobaCid::from_bytes(&self.to_cbor())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn cid(seed: &str) -> KotobaCid {
        KotobaCid::from_bytes(seed.as_bytes())
    }

    #[test]
    fn dna_id_is_order_independent() {
        let a = DnaManifest::new("market", "1.0.0")
            .with_rule("role", cid("rule-role"))
            .with_rule("bond", cid("rule-bond"));
        let b = DnaManifest::new("market", "1.0.0")
            .with_rule("bond", cid("rule-bond"))
            .with_rule("role", cid("rule-role"));
        assert_eq!(a.dna_id(), b.dna_id(), "same rule set → same DNA id");
        assert_eq!(a.rules(), b.rules(), "canonicalised identically");
    }

    #[test]
    fn dna_id_changes_with_rules_name_or_version() {
        let base = DnaManifest::new("market", "1.0.0").with_rule("role", cid("r1"));
        let more_rules = base.clone().with_rule("bond", cid("r2"));
        let bumped = DnaManifest::new("market", "1.1.0").with_rule("role", cid("r1"));
        let renamed = DnaManifest::new("forum", "1.0.0").with_rule("role", cid("r1"));
        assert_ne!(
            base.dna_id(),
            more_rules.dna_id(),
            "adding a rule changes id"
        );
        assert_ne!(base.dna_id(), bumped.dna_id(), "version bump changes id");
        assert_ne!(base.dna_id(), renamed.dna_id(), "rename changes id");
    }

    #[test]
    fn with_rule_replaces_by_id() {
        let m = DnaManifest::new("d", "1")
            .with_rule("role", cid("old"))
            .with_rule("role", cid("new"));
        assert_eq!(m.rules().len(), 1, "same id replaces, not duplicates");
        assert_eq!(m.rules()[0].content, cid("new"), "last write wins");
    }

    #[test]
    fn dna_id_is_deterministic_and_roundtrips() {
        let m = DnaManifest::new("market", "2.0.0")
            .with_rule("a", cid("ra"))
            .with_rule("b", cid("rb"));
        assert_eq!(m.dna_id(), m.dna_id(), "pure / stable");
        // CBOR round-trips back to an equal manifest.
        let back: DnaManifest = ciborium::from_reader(m.to_cbor().as_slice()).unwrap();
        assert_eq!(back, m);
        assert_eq!(back.dna_id(), m.dna_id());
    }

    #[test]
    fn empty_dna_has_a_stable_id() {
        let e1 = DnaManifest::new("empty", "0.1.0");
        let e2 = DnaManifest::new("empty", "0.1.0");
        assert_eq!(e1.dna_id(), e2.dna_id());
        assert!(e1.rules().is_empty());
    }
}
