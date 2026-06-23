//! Trigger routing index (KOTOBA Mesh M13).
//!
//! Maps a deployed app's component trigger specs to the event sources that fire
//! them — KSE topic → components, cron components, HTTP route → component. A
//! node builds this from the manifest (propagated via
//! [`crate::protocol::LatticeMessage::PutRoutes`]) and consults it on each
//! incoming event to call `invoke_trigger`. (datom-Δ triggers keep their own
//! index in [`crate::trigger`].)

use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};

use crate::manifest::AppManifest;

/// Event-source → component routing for a deployed app.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct TriggerRoutes {
    /// KSE topic → component cids subscribed to it.
    #[serde(default)]
    pub kse: BTreeMap<String, Vec<String>>,
    /// (component cid, schedule) for cron triggers. Empty schedule = node default.
    #[serde(default)]
    pub cron: Vec<(String, String)>,
    /// HTTP route → component cid.
    #[serde(default)]
    pub http: BTreeMap<String, String>,
}

impl TriggerRoutes {
    /// Build routes from a manifest + resolved component CIDs (name → cid).
    /// Components are keyed by their resolved CID (explicit `:cid`, else the
    /// `resolved` map, else a `clj:<name>` placeholder — matching the reconciler).
    pub fn from_app(app: &AppManifest, resolved: &BTreeMap<String, String>) -> Self {
        let mut r = TriggerRoutes::default();
        for c in &app.components {
            let cid = resolved
                .get(&c.name)
                .cloned()
                .or_else(|| c.cid.clone())
                .unwrap_or_else(|| format!("clj:{}", c.name));
            for t in &c.triggers {
                match t.kind.as_str() {
                    "kse" => {
                        if let Some(topic) = &t.topic {
                            r.kse.entry(topic.clone()).or_default().push(cid.clone());
                        }
                    }
                    "cron" => {
                        r.cron.push((cid.clone(), t.schedule.clone().unwrap_or_default()));
                    }
                    "http" => {
                        if let Some(route) = &t.route {
                            r.http.insert(route.clone(), cid.clone());
                        }
                    }
                    _ => {} // datom-delta / room handled elsewhere
                }
            }
        }
        r
    }

    /// Component cids that should fire for a KSE message on `topic`.
    pub fn kse_targets(&self, topic: &str) -> &[String] {
        self.kse.get(topic).map(|v| v.as_slice()).unwrap_or(&[])
    }

    /// Component cid bound to an HTTP `route`, if any.
    pub fn http_target(&self, route: &str) -> Option<&str> {
        self.http.get(route).map(|s| s.as_str())
    }

    /// All KSE topics a node must subscribe to.
    pub fn kse_topics(&self) -> impl Iterator<Item = &String> {
        self.kse.keys()
    }

    pub fn is_empty(&self) -> bool {
        self.kse.is_empty() && self.cron.is_empty() && self.http.is_empty()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const APP: &str = r#"{:kotoba.app/name "bot"
        :kotoba.app/components
        [{:name "ingest" :cid "bafyIngest"
          :triggers [{:type :kse :topic "kotoba/mail/in"}]}
         {:name "reply" :cid "bafyReply"
          :triggers [{:type :http :route "/reply"}
                     {:type :cron :schedule "every 5m"}]}
         {:name "fanout" :src "fanout.clj"
          :triggers [{:type :kse :topic "kotoba/mail/in"}]}]}"#;

    fn routes() -> TriggerRoutes {
        TriggerRoutes::from_app(&AppManifest::from_edn(APP).unwrap(), &BTreeMap::new())
    }

    #[test]
    fn indexes_kse_by_topic_with_multiple_subscribers() {
        let r = routes();
        let mut t = r.kse_targets("kotoba/mail/in").to_vec();
        t.sort();
        // ingest (cid) + fanout (clj:fanout placeholder, no cid)
        assert_eq!(t, vec!["bafyIngest".to_string(), "clj:fanout".to_string()]);
        assert!(r.kse_targets("unknown/topic").is_empty());
    }

    #[test]
    fn indexes_http_routes_and_cron() {
        let r = routes();
        assert_eq!(r.http_target("/reply"), Some("bafyReply"));
        assert_eq!(r.http_target("/nope"), None);
        assert_eq!(r.cron, vec![("bafyReply".to_string(), "every 5m".to_string())]);
    }

    #[test]
    fn kse_topics_lists_all_subscribed() {
        let r = routes();
        let topics: Vec<&String> = r.kse_topics().collect();
        assert_eq!(topics, vec![&"kotoba/mail/in".to_string()]);
    }

    #[test]
    fn resolved_cid_overrides_placeholder() {
        let resolved = BTreeMap::from([("fanout".to_string(), "bafyFanout".to_string())]);
        let r = TriggerRoutes::from_app(&AppManifest::from_edn(APP).unwrap(), &resolved);
        assert!(r.kse_targets("kotoba/mail/in").contains(&"bafyFanout".to_string()));
    }

    #[test]
    fn empty_app_has_empty_routes() {
        let r = TriggerRoutes::from_app(&AppManifest::from_edn(r#"{:kotoba.app/name "x"}"#).unwrap(), &BTreeMap::new());
        assert!(r.is_empty());
    }
}
