//! Deploy plan (KOTOBA Mesh M16).
//!
//! Turns a deployed app's manifest into the lattice control messages an operator
//! publishes to make the app live: its datom-Δ triggers ([`LatticeMessage::PutTriggers`])
//! and its event-source routes ([`LatticeMessage::PutRoutes`] — KSE topic / cron /
//! HTTP route). Each node ingests them and fires the bound component's
//! `run`/`on-kse`/`on-tick`/`on-http` export on a matching event.
//!
//! This is the pure "manifest → control messages" step; transport (publishing
//! each pair onto the gossip mesh) is the caller's job (e.g. the server's
//! `mesh.deploy` XRPC endpoint via its gossip channel).

use std::collections::BTreeMap;

use crate::manifest::AppManifest;
use crate::protocol::{topic, LatticeMessage};
use crate::routes::TriggerRoutes;
use crate::trigger::delta_triggers;

/// Build the `(topic, message)` pairs to publish for deploying `app`'s triggers
/// and routes. `resolved` maps component name → CID (for components compiled at
/// deploy time); components carrying an explicit `:cid` need no entry. Returns an
/// empty vec for an app with no triggers/routes (nothing to announce).
pub fn deploy_messages(
    app: &AppManifest,
    resolved: &BTreeMap<String, String>,
) -> Vec<(&'static str, LatticeMessage)> {
    let mut msgs = Vec::new();

    // Desired placement state (scale per resolved CID) → drives the auction so
    // that *hosted-only* triggers (cron `on-tick`) actually fire. Without this a
    // deployed app is merely ROUTED (http/kse dispatch by CID) but never PLACED,
    // so a node never adds the component to `hosted` and the cron loop skips it.
    let quads = crate::control::app_to_quads(app, resolved);
    let (desired, constraints) = crate::control::desired_from_quads(&quads);
    if !desired.is_empty() {
        msgs.push((
            topic::CMD,
            LatticeMessage::PutApp {
                app: app.name.clone(),
                desired,
                constraints,
            },
        ));
    }

    let triggers = delta_triggers(app);
    if !triggers.is_empty() {
        msgs.push((
            topic::CMD,
            LatticeMessage::PutTriggers {
                app: app.name.clone(),
                triggers,
            },
        ));
    }

    let routes = TriggerRoutes::from_app(app, resolved);
    if !routes.is_empty() {
        msgs.push((
            topic::CMD,
            LatticeMessage::PutRoutes {
                app: app.name.clone(),
                routes,
            },
        ));
    }

    msgs
}

#[cfg(test)]
mod tests {
    use super::*;

    // datom-Δ + kse + http + cron triggers across two components
    const APP: &str = r#"{:kotoba.app/name "bot"
        :kotoba.app/components
        [{:name "ingest" :cid "bafyIngest"
          :triggers [{:type :kse :topic "kotoba/mail/in"}
                     {:type :datom-delta :predicate "mail/received"}]}
         {:name "reply" :cid "bafyReply"
          :triggers [{:type :http :route "/reply"}
                     {:type :cron :schedule "every 5m"}]}]}"#;

    fn app() -> AppManifest {
        AppManifest::from_edn(APP).unwrap()
    }

    #[test]
    fn deploy_emits_putapp_puttriggers_and_putroutes() {
        let msgs = deploy_messages(&app(), &BTreeMap::new());
        // PutApp (desired placement) + PutTriggers (datom-Δ) + PutRoutes (event src)
        assert_eq!(msgs.len(), 3);
        // all go on the CMD control topic
        assert!(msgs.iter().all(|(t, _)| *t == topic::CMD));
        let has_app = msgs.iter().any(|(_, m)| {
            matches!(m, LatticeMessage::PutApp { app, desired, .. }
                if app == "bot" && !desired.is_empty())
        });
        let has_triggers = msgs.iter().any(|(_, m)| {
            matches!(m, LatticeMessage::PutTriggers { app, triggers }
                if app == "bot" && !triggers.is_empty())
        });
        let has_routes = msgs.iter().any(|(_, m)| {
            matches!(m, LatticeMessage::PutRoutes { app, routes }
                if app == "bot" && !routes.kse.is_empty() && !routes.http.is_empty() && !routes.cron.is_empty())
        });
        assert!(has_app, "expected a PutApp message (desired placement)");
        assert!(has_triggers, "expected a PutTriggers message");
        assert!(has_routes, "expected a PutRoutes message");
    }

    #[test]
    fn deploy_routes_only_app_emits_putapp_and_putroutes() {
        let src = r#"{:kotoba.app/name "r"
            :kotoba.app/components
            [{:name "h" :cid "bafyH" :triggers [{:type :http :route "/x"}]}]}"#;
        let msgs = deploy_messages(&AppManifest::from_edn(src).unwrap(), &BTreeMap::new());
        // a component with a CID is placeable → PutApp + PutRoutes
        assert_eq!(msgs.len(), 2);
        assert!(msgs
            .iter()
            .any(|(_, m)| matches!(m, LatticeMessage::PutApp { .. })));
        assert!(msgs
            .iter()
            .any(|(_, m)| matches!(m, LatticeMessage::PutRoutes { .. })));
    }

    #[test]
    fn deploy_empty_app_emits_nothing() {
        let msgs = deploy_messages(
            &AppManifest::from_edn(r#"{:kotoba.app/name "x"}"#).unwrap(),
            &BTreeMap::new(),
        );
        assert!(msgs.is_empty());
    }

    #[test]
    fn deploy_resolves_compiled_component_cid() {
        let src = r#"{:kotoba.app/name "r"
            :kotoba.app/components
            [{:name "h" :src "h.kotoba" :triggers [{:type :kse :topic "t"}]}]}"#;
        let resolved = BTreeMap::from([("h".to_string(), "bafyCompiled".to_string())]);
        let msgs = deploy_messages(&AppManifest::from_edn(src).unwrap(), &resolved);
        let routes_msg = msgs
            .iter()
            .find_map(|(_, m)| match m {
                LatticeMessage::PutRoutes { routes, .. } => Some(routes),
                _ => None,
            })
            .expect("expected a PutRoutes message");
        assert!(routes_msg
            .kse_targets("t")
            .contains(&"bafyCompiled".to_string()));
        // the compiled CID is also the placement target in PutApp
        assert!(msgs.iter().any(|(_, m)| matches!(
            m,
            LatticeMessage::PutApp { desired, .. } if desired.contains_key("bafyCompiled")
        )));
    }
}
