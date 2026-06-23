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
    fn deploy_emits_puttriggers_and_putroutes() {
        let msgs = deploy_messages(&app(), &BTreeMap::new());
        assert_eq!(msgs.len(), 2);
        // both go on the CMD control topic
        assert!(msgs.iter().all(|(t, _)| *t == topic::CMD));
        let has_triggers = msgs.iter().any(|(_, m)| {
            matches!(m, LatticeMessage::PutTriggers { app, triggers }
                if app == "bot" && !triggers.is_empty())
        });
        let has_routes = msgs.iter().any(|(_, m)| {
            matches!(m, LatticeMessage::PutRoutes { app, routes }
                if app == "bot" && !routes.kse.is_empty() && !routes.http.is_empty() && !routes.cron.is_empty())
        });
        assert!(has_triggers, "expected a PutTriggers message");
        assert!(has_routes, "expected a PutRoutes message");
    }

    #[test]
    fn deploy_routes_only_app_emits_one_message() {
        let src = r#"{:kotoba.app/name "r"
            :kotoba.app/components
            [{:name "h" :cid "bafyH" :triggers [{:type :http :route "/x"}]}]}"#;
        let msgs = deploy_messages(&AppManifest::from_edn(src).unwrap(), &BTreeMap::new());
        assert_eq!(msgs.len(), 1);
        assert!(matches!(msgs[0].1, LatticeMessage::PutRoutes { .. }));
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
            [{:name "h" :src "h.clj" :triggers [{:type :kse :topic "t"}]}]}"#;
        let resolved = BTreeMap::from([("h".to_string(), "bafyCompiled".to_string())]);
        let msgs = deploy_messages(&AppManifest::from_edn(src).unwrap(), &resolved);
        match &msgs[0].1 {
            LatticeMessage::PutRoutes { routes, .. } => {
                assert!(routes.kse_targets("t").contains(&"bafyCompiled".to_string()));
            }
            _ => panic!("expected PutRoutes"),
        }
    }
}
