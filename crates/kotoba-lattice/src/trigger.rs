//! datom-Δ triggers (KOTOBA Mesh M6): data-driven serverless.
//!
//! kotoba's distinctive trigger (ADR §8): instead of HTTP/cron, a component
//! fires when a **new datom matching a pattern** appears in the graph — e.g.
//! "when some entity gets `kg/claim/role = admin`, run the audit component".
//! The reactive Δ stream comes from `kotoba-query` (Delta/MV); this module is
//! the pure matcher between trigger patterns and incoming datoms.

use std::collections::BTreeSet;

use serde::{Deserialize, Serialize};

use crate::manifest::AppManifest;

/// A resolved datom-Δ trigger: fire `component` when a datom with `predicate`
/// (and, if set, object == `value`) is asserted.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DeltaTrigger {
    /// Component key (artifact CID when known, else `kotoba:<name>`).
    pub component: String,
    pub predicate: String,
    /// Optional object-value filter; `None` matches any value.
    pub value: Option<String>,
}

impl DeltaTrigger {
    /// Does this trigger fire for an asserted datom `(predicate, object)`?
    pub fn matches(&self, predicate: &str, object: &str) -> bool {
        self.predicate == predicate && self.value.as_deref().is_none_or(|v| v == object)
    }
}

/// Collect every `datom-delta` trigger declared in an app's components, keyed by
/// the same component key the reconciler uses (cid, else `kotoba:<name>`).
/// Triggers missing a `:predicate` are skipped (nothing to match on).
pub fn delta_triggers(app: &AppManifest) -> Vec<DeltaTrigger> {
    let mut out = Vec::new();
    for c in &app.components {
        let key = c
            .cid
            .clone()
            .unwrap_or_else(|| format!("kotoba:{}", c.name));
        for t in &c.triggers {
            if t.kind == "datom-delta" {
                if let Some(predicate) = &t.predicate {
                    out.push(DeltaTrigger {
                        component: key.clone(),
                        predicate: predicate.clone(),
                        value: t.value.clone(),
                    });
                }
            }
        }
    }
    out
}

/// Components to invoke for a single asserted datom `(predicate, object)`.
pub fn fired_by_datom<'a>(
    triggers: &'a [DeltaTrigger],
    predicate: &str,
    object: &str,
) -> Vec<&'a str> {
    triggers
        .iter()
        .filter(|t| t.matches(predicate, object))
        .map(|t| t.component.as_str())
        .collect()
}

/// Components to invoke for a whole Δ batch of asserted datoms. De-duplicated:
/// a component fires at most once per batch no matter how many datoms match.
pub fn fired_by_batch(triggers: &[DeltaTrigger], datoms: &[(String, String)]) -> BTreeSet<String> {
    let mut fired = BTreeSet::new();
    for (predicate, object) in datoms {
        for t in triggers.iter().filter(|t| t.matches(predicate, object)) {
            fired.insert(t.component.clone());
        }
    }
    fired
}

#[cfg(test)]
mod tests {
    use super::*;

    const APP: &str = r#"{:kotoba.app/name "audit-bot"
        :kotoba.app/components
        [{:name "audit" :cid "bafyAudit"
          :triggers [{:type :datom-delta :predicate "kg/claim/role" :value "admin"}]}
         {:name "indexer" :cid "bafyIndex"
          :triggers [{:type :datom-delta :predicate "kg/claim/role"}]}  ; any value
         {:name "web" :cid "bafyWeb"
          :triggers [{:type :http :route "/"}]}]}"#;

    fn triggers() -> Vec<DeltaTrigger> {
        delta_triggers(&AppManifest::from_edn(APP).unwrap())
    }

    #[test]
    fn collects_only_datom_delta_triggers() {
        let t = triggers();
        // audit (value-filtered) + indexer (any value); the http `web` is excluded
        assert_eq!(t.len(), 2);
        assert!(t
            .iter()
            .any(|d| d.component == "bafyAudit" && d.value.as_deref() == Some("admin")));
        assert!(t
            .iter()
            .any(|d| d.component == "bafyIndex" && d.value.is_none()));
    }

    #[test]
    fn value_filter_is_respected() {
        let t = triggers();
        // role=admin → both audit (admin) and indexer (any) fire
        let mut fired = fired_by_datom(&t, "kg/claim/role", "admin");
        fired.sort();
        assert_eq!(fired, vec!["bafyAudit", "bafyIndex"]);
        // role=user → only indexer (audit is admin-only)
        assert_eq!(
            fired_by_datom(&t, "kg/claim/role", "user"),
            vec!["bafyIndex"]
        );
        // different predicate → nothing
        assert!(fired_by_datom(&t, "kg/claim/name", "admin").is_empty());
    }

    #[test]
    fn batch_dedups_components() {
        let t = triggers();
        let batch = vec![
            ("kg/claim/role".to_string(), "admin".to_string()),
            ("kg/claim/role".to_string(), "admin".to_string()), // duplicate
            ("kg/claim/role".to_string(), "user".to_string()),
            ("kg/claim/name".to_string(), "x".to_string()), // no trigger
        ];
        let fired = fired_by_batch(&t, &batch);
        // indexer fires (any role), audit fires (admin present) — each once
        assert_eq!(fired.len(), 2);
        assert!(fired.contains("bafyAudit") && fired.contains("bafyIndex"));
    }

    #[test]
    fn trigger_without_predicate_is_skipped() {
        let app = AppManifest::from_edn(
            r#"{:kotoba.app/name "a" :kotoba.app/components
                [{:name "c" :cid "x" :triggers [{:type :datom-delta}]}]}"#,
        )
        .unwrap();
        assert!(delta_triggers(&app).is_empty());
    }

    #[test]
    fn uses_name_placeholder_when_no_cid() {
        let app = AppManifest::from_edn(
            r#"{:kotoba.app/name "a" :kotoba.app/components
                [{:name "c" :src "c.kotoba" :triggers [{:type :datom-delta :predicate "p"}]}]}"#,
        )
        .unwrap();
        let t = delta_triggers(&app);
        assert_eq!(t[0].component, "kotoba:c");
    }
}
