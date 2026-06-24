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
                        r.cron
                            .push((cid.clone(), t.schedule.clone().unwrap_or_default()));
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

/// Parse a cron trigger `:schedule` string into a fire interval in milliseconds
/// (M14). Accepts `"every <N><unit>"` or bare `"<N><unit>"`, unit ∈
/// s/sec/second(s), m/min/minute(s), h/hr/hour(s), d/day(s). Returns `None` for
/// an empty/unrecognized schedule (callers fall back to a node default).
pub fn parse_schedule_ms(schedule: &str) -> Option<u64> {
    let s = schedule.trim();
    let s = s.strip_prefix("every").map(str::trim).unwrap_or(s);
    let split = s.find(|c: char| c.is_ascii_alphabetic())?;
    let n: u64 = s[..split].trim().parse().ok()?;
    let mult = match s[split..].trim() {
        "s" | "sec" | "secs" | "second" | "seconds" => 1_000,
        "m" | "min" | "mins" | "minute" | "minutes" => 60_000,
        "h" | "hr" | "hour" | "hours" => 3_600_000,
        "d" | "day" | "days" => 86_400_000,
        _ => return None,
    };
    n.checked_mul(mult)
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
        assert_eq!(
            r.cron,
            vec![("bafyReply".to_string(), "every 5m".to_string())]
        );
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
        assert!(r
            .kse_targets("kotoba/mail/in")
            .contains(&"bafyFanout".to_string()));
    }

    #[test]
    fn empty_app_has_empty_routes() {
        let r = TriggerRoutes::from_app(
            &AppManifest::from_edn(r#"{:kotoba.app/name "x"}"#).unwrap(),
            &BTreeMap::new(),
        );
        assert!(r.is_empty());
    }

    #[test]
    fn parse_schedule_ms_units_and_every_prefix() {
        assert_eq!(parse_schedule_ms("every 5m"), Some(300_000));
        assert_eq!(parse_schedule_ms("30s"), Some(30_000));
        assert_eq!(parse_schedule_ms("every 5 minutes"), Some(300_000));
        assert_eq!(parse_schedule_ms("1 h"), Some(3_600_000));
        assert_eq!(parse_schedule_ms("2d"), Some(172_800_000));
        assert_eq!(parse_schedule_ms("  every  10 sec  "), Some(10_000));
    }

    #[test]
    fn parse_schedule_ms_rejects_garbage() {
        assert_eq!(parse_schedule_ms(""), None);
        assert_eq!(parse_schedule_ms("soon"), None);
        assert_eq!(parse_schedule_ms("5 lightyears"), None);
        assert_eq!(parse_schedule_ms("m"), None); // no number
    }
}
