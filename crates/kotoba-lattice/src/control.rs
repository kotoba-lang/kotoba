//! Control-graph data model (KOTOBA Mesh M4 / wadm).
//!
//! Desired state is stored as **datoms** in a control graph — the same datom DB
//! that is the source of truth for everything else (ADR §7). `kotoba app deploy`
//! writes these; every node's reconciler reads them (or receives them live via
//! [`crate::protocol::LatticeMessage::PutApp`]) and converges on them.
//!
//! This module is the pure, deterministic bridge between an [`AppManifest`] (+
//! its resolved component CIDs) and those control datoms — and back to the
//! reconciler's desired-state + constraints.

use std::collections::BTreeMap;

use crate::manifest::AppManifest;
use crate::protocol::Constraints;

/// Predicate namespace for mesh control datoms.
pub mod pred {
    /// `(component-subject, app, <app-name>)`
    pub const APP: &str = "kotoba.mesh/app";
    /// `(component-subject, cid, <artifact-cid>)`
    pub const CID: &str = "kotoba.mesh/cid";
    /// `(component-subject, scale, <n>)`
    pub const SCALE: &str = "kotoba.mesh/scale";
    /// `(component-subject, requires, <cap>)` — one datom per required cap
    pub const REQUIRES: &str = "kotoba.mesh/requires";
    /// `(component-subject, label, <k>=<v>)` — one datom per placement label
    pub const LABEL: &str = "kotoba.mesh/label";
}

/// A control datom in legacy-quad projection (graph is the control graph).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ControlQuad {
    pub subject: String,
    pub predicate: String,
    pub object: String,
}

impl ControlQuad {
    fn new(subject: &str, predicate: &str, object: impl Into<String>) -> Self {
        Self {
            subject: subject.to_string(),
            predicate: predicate.to_string(),
            object: object.into(),
        }
    }
}

/// Stable per-component subject id within an app: `mesh:<app>/<component>`.
pub fn component_subject(app: &str, component: &str) -> String {
    format!("mesh:{app}/{component}")
}

/// Project an app + its resolved component CIDs into control datoms.
/// `resolved`: component name → artifact CID (from `kotoba app deploy`).
pub fn app_to_quads(app: &AppManifest, resolved: &BTreeMap<String, String>) -> Vec<ControlQuad> {
    let mut out = Vec::new();
    for c in &app.components {
        let subj = component_subject(&app.name, &c.name);
        out.push(ControlQuad::new(&subj, pred::APP, app.name.clone()));
        if let Some(cid) = resolved.get(&c.name).or(c.cid.as_ref()) {
            out.push(ControlQuad::new(&subj, pred::CID, cid.clone()));
        }
        out.push(ControlQuad::new(&subj, pred::SCALE, c.scale.to_string()));
        for cap in &c.requires {
            out.push(ControlQuad::new(&subj, pred::REQUIRES, cap.clone()));
        }
        for (k, v) in &app.placement.require {
            out.push(ControlQuad::new(&subj, pred::LABEL, format!("{k}={v}")));
        }
    }
    out.sort_by(|a, b| {
        (&a.subject, &a.predicate, &a.object).cmp(&(&b.subject, &b.predicate, &b.object))
    });
    out
}

/// Read control datoms back into the reconciler's inputs: desired (cid → count)
/// and per-cid placement constraints. Components missing a CID are skipped
/// (their artifact has not been resolved/built yet). Deterministic.
pub fn desired_from_quads(
    quads: &[ControlQuad],
) -> (BTreeMap<String, u32>, BTreeMap<String, Constraints>) {
    // group datoms by subject
    let mut by_subject: BTreeMap<&str, Vec<&ControlQuad>> = BTreeMap::new();
    for q in quads {
        by_subject.entry(&q.subject).or_default().push(q);
    }

    let mut desired = BTreeMap::new();
    let mut constraints = BTreeMap::new();

    for (_subj, qs) in by_subject {
        let cid = qs.iter().find(|q| q.predicate == pred::CID).map(|q| q.object.clone());
        let Some(cid) = cid else { continue };
        let scale = qs
            .iter()
            .find(|q| q.predicate == pred::SCALE)
            .and_then(|q| q.object.parse::<u32>().ok())
            .unwrap_or(1);
        let requires_caps: Vec<String> = qs
            .iter()
            .filter(|q| q.predicate == pred::REQUIRES)
            .map(|q| q.object.clone())
            .collect();
        let require_labels: BTreeMap<String, String> = qs
            .iter()
            .filter(|q| q.predicate == pred::LABEL)
            .filter_map(|q| q.object.split_once('=').map(|(k, v)| (k.to_string(), v.to_string())))
            .collect();

        desired.insert(cid.clone(), scale);
        constraints.insert(
            cid,
            Constraints {
                require_labels,
                requires_caps,
            },
        );
    }
    (desired, constraints)
}

#[cfg(test)]
mod tests {
    use super::*;

    const APP: &str = r#"{:kotoba.app/name "bot"
        :kotoba.app/components
        [{:name "reply" :cid "bafyReply" :scale 3 :requires [:cap/kqe :cap/llm]}]
        :kotoba.app/placement {:require {:tier "edge"}}}"#;

    #[test]
    fn roundtrip_app_to_quads_to_desired() {
        let app = AppManifest::from_edn(APP).unwrap();
        let resolved = BTreeMap::new(); // cid already in manifest
        let quads = app_to_quads(&app, &resolved);

        // datoms are present for cid/scale/requires/label
        assert!(quads.iter().any(|q| q.predicate == pred::CID && q.object == "bafyReply"));
        assert!(quads.iter().any(|q| q.predicate == pred::SCALE && q.object == "3"));
        assert_eq!(quads.iter().filter(|q| q.predicate == pred::REQUIRES).count(), 2);
        assert!(quads.iter().any(|q| q.predicate == pred::LABEL && q.object == "tier=edge"));

        let (desired, constraints) = desired_from_quads(&quads);
        assert_eq!(desired.get("bafyReply"), Some(&3));
        let c = &constraints["bafyReply"];
        assert!(c.requires_caps.contains(&"cap/llm".to_string()));
        assert_eq!(c.require_labels.get("tier").map(|s| s.as_str()), Some("edge"));
    }

    #[test]
    fn resolved_cid_overrides_when_manifest_has_none() {
        let src = r#"{:kotoba.app/name "x"
            :kotoba.app/components [{:name "n" :src "n.clj" :scale 2 :requires [:cap/kqe]}]}"#;
        let app = AppManifest::from_edn(src).unwrap();
        let resolved = BTreeMap::from([("n".to_string(), "bafyBuilt".to_string())]);
        let quads = app_to_quads(&app, &resolved);
        let (desired, _) = desired_from_quads(&quads);
        assert_eq!(desired.get("bafyBuilt"), Some(&2));
    }

    #[test]
    fn component_without_cid_is_skipped() {
        // a component with neither :cid nor resolved entry → no CID datom → skipped
        let src = r#"{:kotoba.app/name "x"
            :kotoba.app/components [{:name "n" :src "n.clj" :scale 2}]}"#;
        let app = AppManifest::from_edn(src).unwrap();
        let quads = app_to_quads(&app, &BTreeMap::new());
        let (desired, _) = desired_from_quads(&quads);
        assert!(desired.is_empty());
    }

    #[test]
    fn quads_are_deterministic() {
        let app = AppManifest::from_edn(APP).unwrap();
        assert_eq!(app_to_quads(&app, &BTreeMap::new()), app_to_quads(&app, &BTreeMap::new()));
    }
}
